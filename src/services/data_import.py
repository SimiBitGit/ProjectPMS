# src/services/data_import.py
"""
MarketData Import Service - EoD Historical Data (EODHD) API Integration

Verantwortlichkeiten:
- OHLCV-Daten für ETFs/Stocks/FX von EODHD laden
- Ticker automatisch anlegen falls nicht vorhanden
- Upsert-Logik: keine Duplikate, vorhandene Daten überschreiben
- File-basiertes JSON-Caching (TTL konfigurierbar)
- Strukturiertes Logging & Fehlerbehandlung
- Gap-Detection: fehlende Handelstage erkennen und melden
"""

import json
import logging
import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

import requests
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.config import config as app_config
from src.models.market_data import MarketData
from src.models.metadata import AssetType, Ticker
from src.database.ticker_repository import TickerRepository
from src.database.market_data_repository import MarketDataRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------
EODHD_BASE_URL = "https://eodhd.com/api"
SOURCE_NAME = "eodhd"

# Mapping: EODHD-Exchange-Suffix → Asset-Type (erweiterbar)
EXCHANGE_ASSET_TYPE_MAP: dict[str, AssetType] = {
    "FOREX": AssetType.FX,
    "CC":    AssetType.CRYPTO,
    "INDX":  AssetType.INDEX,
    "BOND":  AssetType.BOND,
    "COMM":  AssetType.COMMODITY,
}

# Kanonische EODHD-Symbole für die Standard-Underlyings dieses Projekts.
# Schlüssel: lesbares Kürzel (für CLI / Konfiguration)
# Wert:      exaktes EODHD-Symbol, das an die API übergeben wird
KNOWN_SYMBOLS: dict[str, str] = {
    # ---- ETFs ---------------------------------------------------------------
    "IWDA":   "IWDA.AS",     # iShares Core MSCI World – Euronext Amsterdam (EUR)
    "CSPX":   "CSPX.LSE",   # iShares Core S&P 500 – London (USD)
    "SPY":    "SPY.US",      # SPDR S&P 500 – US (USD)
    "QQQ":    "QQQ.US",      # Invesco QQQ – US (USD)
    # ---- FX-Paare -----------------------------------------------------------
    # EODHD-Format: <BASE><QUOTE>.FOREX
    "EURUSD": "EURUSD.FOREX",
    "USDCHF": "USDCHF.FOREX",
    "GBPUSD": "GBPUSD.FOREX",
    "AUDUSD": "AUDUSD.FOREX",
    "USDCAD": "USDCAD.FOREX",
    "USDJPY": "USDJPY.FOREX",
    # ---- Crypto -------------------------------------------------------------
    "BTCUSD": "BTC-USD.CC",  # Bitcoin – Crypto-Exchange-Feed
    # ---- Edelmetalle --------------------------------------------------------
    # EODHD behandelt Spot-Metalle wie FX (ISO 4217: XAU, XAG)
    "XAUUSD": "XAUUSD.FOREX",  # Gold Spot in USD
    "XAGUSD": "XAGUSD.FOREX",  # Silber Spot in USD
}

# Geordnete Standardliste aller Projekt-Underlyings
DEFAULT_SYMBOLS: list[str] = list(KNOWN_SYMBOLS.values())


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _to_decimal(value) -> Optional[Decimal]:
    """Konvertiert einen Wert sicher zu Decimal; None bei ungültigem Wert."""
    if value is None:
        return None
    try:
        d = Decimal(str(value))
        return d if d.is_finite() else None
    except (InvalidOperation, TypeError):
        return None


def _infer_asset_type(symbol: str, exchange: str) -> AssetType:
    """Leitet den Asset-Typ aus Exchange-Suffix oder Symbol-Konvention ab."""
    ex_upper = (exchange or "").upper()
    if ex_upper in EXCHANGE_ASSET_TYPE_MAP:
        return EXCHANGE_ASSET_TYPE_MAP[ex_upper]
    # Edelmetalle: ISO 4217 XAU / XAG Präfix
    name_part = symbol.split(".")[0].upper()
    if name_part.startswith(("XAU", "XAG", "XPT", "XPD")):
        return AssetType.FX   # Spot-Metalle werden wie FX behandelt
    # Einfache Heuristik: 6-stellige FX-Symbole ohne Punkt
    if len(name_part) == 6 and name_part.isalpha():
        return AssetType.FX
    return AssetType.ETF  # Default für dieses Projekt


# ---------------------------------------------------------------------------
# Cache-Manager
# ---------------------------------------------------------------------------

class _FileCache:
    """
    Einfacher dateibasierter JSON-Cache mit TTL.
    Cache-Dateien: data/cache/<safe_key>.json
    """

    def __init__(self, cache_dir: Path, ttl_seconds: int):
        self.cache_dir = cache_dir
        self.ttl = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace(".", "_")
        return self.cache_dir / f"{safe}.json"

    def get(self, key: str) -> Optional[list]:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
            age = time.time() - payload["ts"]
            if age > self.ttl:
                p.unlink(missing_ok=True)
                return None
            logger.debug("Cache-Hit: %s (Alter: %.0f s)", key, age)
            return payload["data"]
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def set(self, key: str, data: list) -> None:
        p = self._path(key)
        try:
            p.write_text(
                json.dumps({"ts": time.time(), "data": data}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Cache schreiben fehlgeschlagen (%s): %s", key, exc)

    def invalidate(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Haupt-Service
# ---------------------------------------------------------------------------

class MarketDataImporter:
    """
    Lädt OHLCV-Daten von der EODHD-API und speichert sie in der Datenbank.

    Verwendung:
        importer = MarketDataImporter.from_config(session)
        result = importer.import_ticker("IWDA.AS", date(2020, 1, 1), date.today())
        print(result)
    """

    def __init__(
        self,
        session: Session,
        api_key: str,
        cache_dir: Path,
        cache_ttl: int = 3600,
        request_timeout: int = 30,
        retry_attempts: int = 3,
        retry_delay: float = 2.0,
    ):
        self.session = session
        self.api_key = api_key
        self.timeout = request_timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay

        self._cache = _FileCache(cache_dir, cache_ttl)
        self._ticker_repo = TickerRepository(session)
        self._data_repo = MarketDataRepository(session)

        self._http = requests.Session()
        self._http.headers.update({"Accept": "application/json"})

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, session: Session) -> "MarketDataImporter":
        """Erstellt eine Instanz aus der Projekt-Konfiguration (settings.yaml / .env)."""
        api_key = app_config.get_api_key("eodhd")
        if not api_key:
            raise ValueError(
                "EODHD_API_KEY nicht gesetzt. Bitte in .env eintragen."
            )

        cache_dir = Path(app_config.get("data_sources.cache_dir", "data/cache"))
        cache_ttl = int(app_config.get("data_sources.cache_duration", 3600))

        return cls(
            session=session,
            api_key=api_key,
            cache_dir=cache_dir,
            cache_ttl=cache_ttl,
        )

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def import_ticker(
        self,
        symbol: str,
        start_date: date,
        end_date: Optional[date] = None,
        force_refresh: bool = False,
    ) -> dict:
        """
        Importiert OHLCV-Daten für ein Symbol.

        Args:
            symbol:        EODHD-Symbol, z.B. "IWDA.AS" oder "SPY.US"
            start_date:    Startdatum des Import-Zeitraums
            end_date:      Enddatum (Standard: heute)
            force_refresh: Cache ignorieren

        Returns:
            dict mit Statistiken:
                {
                    "symbol": "IWDA.AS",
                    "inserted": 520,
                    "updated":  3,
                    "skipped":  0,
                    "errors":   [],
                    "gaps":     ["2023-04-10", ...]   # fehlende Handelstage
                }
        """
        end_date = end_date or date.today()
        symbol = symbol.upper().strip()

        logger.info(
            "Import gestartet: %s | %s → %s",
            symbol, start_date, end_date,
        )

        # 1. Rohdaten von API (oder Cache) holen
        raw_data = self._fetch_eod_data(symbol, start_date, end_date, force_refresh)
        if not raw_data:
            logger.warning("Keine Daten für %s im Zeitraum %s–%s", symbol, start_date, end_date)
            return self._empty_result(symbol)

        # 2. Ticker sicherstellen (anlegen falls neu)
        ticker = self._ensure_ticker(symbol, raw_data)

        # 3. Daten in DB schreiben
        stats = self._upsert_market_data(ticker, raw_data)

        # 4. Gap-Analyse
        stats["gaps"] = self._detect_gaps(raw_data, start_date, end_date)
        if stats["gaps"]:
            logger.warning(
                "%s: %d fehlende Handelstage erkannt (erste 5: %s)",
                symbol, len(stats["gaps"]), stats["gaps"][:5],
            )

        logger.info(
            "Import abgeschlossen: %s | inserted=%d, updated=%d, skipped=%d, gaps=%d",
            symbol,
            stats["inserted"],
            stats["updated"],
            stats["skipped"],
            len(stats["gaps"]),
        )
        return stats

    def import_bulk(
        self,
        symbols: list[str],
        start_date: date,
        end_date: Optional[date] = None,
        force_refresh: bool = False,
        pause_between: float = 0.5,
    ) -> list[dict]:
        """
        Importiert mehrere Symbole nacheinander.

        Args:
            pause_between: Pause in Sekunden zwischen API-Calls (Rate-Limit-Schutz)

        Returns:
            Liste von Ergebnis-Dicts (eines pro Symbol)
        """
        results = []
        total = len(symbols)
        for idx, symbol in enumerate(symbols, 1):
            logger.info("Bulk-Import: %d/%d – %s", idx, total, symbol)
            try:
                result = self.import_ticker(symbol, start_date, end_date, force_refresh)
            except Exception as exc:
                logger.error("Fehler bei %s: %s", symbol, exc, exc_info=True)
                result = self._empty_result(symbol)
                result["errors"].append(str(exc))
            results.append(result)
            if idx < total:
                time.sleep(pause_between)
        return results

    def update_to_today(
        self,
        symbols: Optional[list[str]] = None,
        lookback_days: int = 7,
    ) -> list[dict]:
        """
        Aktualisiert alle (oder bestimmte) aktiven Ticker auf den heutigen Stand.
        Lädt nur die fehlenden Tage nach (lookback_days Puffer für Wochenenden).

        Args:
            symbols:       Einzuschränkende Symbole; None = alle aktiven Ticker
            lookback_days: Wie viele Tage zurück der Start-Offset gesetzt wird
        """
        if symbols:
            symbol_list = [s.upper().strip() for s in symbols]
        else:
            active = self._ticker_repo.get_all_active()
            symbol_list = [t.symbol for t in active]

        if not symbol_list:
            logger.info("Keine aktiven Ticker für Update gefunden.")
            return []

        start = date.today() - timedelta(days=lookback_days)
        logger.info(
            "Update für %d Ticker ab %s", len(symbol_list), start
        )
        return self.import_bulk(symbol_list, start_date=start)

    # ------------------------------------------------------------------
    # Interne Methoden
    # ------------------------------------------------------------------

    def _fetch_eod_data(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        force_refresh: bool,
    ) -> list[dict]:
        """Ruft EOD-Daten von der API ab (mit Cache-Fallback)."""
        cache_key = f"eod_{symbol}_{start_date}_{end_date}"

        if not force_refresh:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        url = f"{EODHD_BASE_URL}/eod/{symbol}"
        params = {
            "api_token": self.api_key,
            "from":      start_date.strftime("%Y-%m-%d"),
            "to":        end_date.strftime("%Y-%m-%d"),
            "fmt":       "json",
            "period":    "d",  # Tagesdaten
        }

        data = self._request_with_retry(url, params)

        if data:
            self._cache.set(cache_key, data)

        return data or []

    def _request_with_retry(self, url: str, params: dict) -> Optional[list]:
        """HTTP GET mit exponentiellem Retry-Backoff."""
        for attempt in range(1, self.retry_attempts + 1):
            try:
                resp = self._http.get(url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response else "?"
                if status == 401:
                    raise ValueError(
                        "EODHD API-Key ungültig oder abgelaufen (HTTP 401)."
                    ) from exc
                if status == 404:
                    logger.warning("Symbol nicht gefunden (HTTP 404): %s", url)
                    return None
                if status == 429:
                    wait = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        "Rate-Limit erreicht (HTTP 429). Warte %.1f s ...", wait
                    )
                    time.sleep(wait)
                elif attempt == self.retry_attempts:
                    raise
                else:
                    logger.warning(
                        "HTTP-Fehler %s (Versuch %d/%d): %s",
                        status, attempt, self.retry_attempts, exc,
                    )
                    time.sleep(self.retry_delay * attempt)
            except requests.exceptions.ConnectionError as exc:
                if attempt == self.retry_attempts:
                    raise
                logger.warning(
                    "Verbindungsfehler (Versuch %d/%d): %s",
                    attempt, self.retry_attempts, exc,
                )
                time.sleep(self.retry_delay * attempt)
            except requests.exceptions.Timeout:
                if attempt == self.retry_attempts:
                    raise
                logger.warning(
                    "Timeout (Versuch %d/%d)", attempt, self.retry_attempts
                )
                time.sleep(self.retry_delay * attempt)
        return None

    def _ensure_ticker(self, symbol: str, raw_data: list[dict]) -> Ticker:
        """
        Gibt den bestehenden Ticker zurück oder legt ihn an.
        Metadaten werden aus dem ersten Datenpunkt und dem Symbol-Suffix abgeleitet.
        """
        ticker = self._ticker_repo.get_by_symbol(symbol)
        if ticker:
            return ticker

        # Symbol-Teile: "IWDA.AS" → name_part="IWDA", exchange="AS"
        parts = symbol.split(".", 1)
        name_part = parts[0]
        exchange_suffix = parts[1] if len(parts) > 1 else ""

        # Währung aus ersten Daten ableiten (EODHD gibt kein Währungsfeld im EOD-Endpoint)
        # Fallback-Logik über bekannte Exchange-Suffixe
        currency = _infer_currency(exchange_suffix)
        asset_type = _infer_asset_type(symbol, exchange_suffix)

        ticker = Ticker(
            symbol=symbol,
            name=name_part,        # Wird ggf. später über /fundamentals ergänzt
            exchange=exchange_suffix or None,
            currency=currency,
            asset_type=asset_type,
            is_active=True,
        )
        try:
            self._ticker_repo.create(ticker)
            self.session.flush()
            logger.info("Neuer Ticker angelegt: %s (Type: %s)", symbol, asset_type.value)
        except IntegrityError:
            self.session.rollback()
            ticker = self._ticker_repo.get_by_symbol(symbol)
            logger.debug("Ticker %s bereits vorhanden (race condition).", symbol)

        return ticker

    def _upsert_market_data(self, ticker: Ticker, raw_data: list[dict]) -> dict:
        """
        Schreibt OHLCV-Datensätze in die DB (Insert oder Update bei bestehendem Datum).
        """
        stats = {"symbol": ticker.symbol, "inserted": 0, "updated": 0, "skipped": 0, "errors": []}

        for item in raw_data:
            try:
                record_date = _parse_date(item.get("date"))
                if record_date is None:
                    stats["skipped"] += 1
                    continue

                close = _to_decimal(item.get("close"))
                if close is None:
                    # Kein Close-Kurs = unbrauchbarer Datensatz
                    stats["skipped"] += 1
                    continue

                existing = self._data_repo.get_by_ticker_and_date(
                    ticker.ticker_id, record_date, SOURCE_NAME
                )

                if existing:
                    # Update nur wenn sich Werte geändert haben
                    changed = _update_fields(existing, item)
                    if changed:
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    new_record = MarketData(
                        ticker_id=ticker.ticker_id,
                        date=record_date,
                        open=_to_decimal(item.get("open")),
                        high=_to_decimal(item.get("high")),
                        low=_to_decimal(item.get("low")),
                        close=close,
                        volume=_safe_int(item.get("volume")),
                        adj_close=_to_decimal(item.get("adjusted_close")),
                        source=SOURCE_NAME,
                    )
                    self.session.add(new_record)
                    stats["inserted"] += 1

            except Exception as exc:
                date_str = item.get("date", "?")
                logger.error(
                    "Fehler beim Verarbeiten von %s / %s: %s",
                    ticker.symbol, date_str, exc, exc_info=True,
                )
                stats["errors"].append(f"{date_str}: {exc}")

        try:
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            logger.error("DB-Commit fehlgeschlagen: %s", exc, exc_info=True)
            stats["errors"].append(f"DB-Commit-Fehler: {exc}")

        return stats

    @staticmethod
    def _detect_gaps(
        raw_data: list[dict],
        start_date: date,
        end_date: date,
        min_expected_trading_days: int = 5,
    ) -> list[str]:
        """
        Prüft auf größere Lücken im Datensatz.
        Gibt Daten zurück, an denen ein Handelstag fehlt (>3 Werktage Abstand).
        Einfache Heuristik: berücksichtigt keine Feiertage.
        """
        if not raw_data:
            return []

        dates = sorted(_parse_date(d["date"]) for d in raw_data if d.get("date"))
        dates = [d for d in dates if d is not None]

        if len(dates) < min_expected_trading_days:
            return []

        gaps = []
        for i in range(1, len(dates)):
            delta = (dates[i] - dates[i - 1]).days
            # Mehr als 5 Kalendertage Abstand = potenzielle Lücke (über Feiertage/Wochenende hinaus)
            if delta > 5:
                gaps.append(dates[i - 1].isoformat())

        return gaps

    @staticmethod
    def _empty_result(symbol: str) -> dict:
        return {
            "symbol":   symbol,
            "inserted": 0,
            "updated":  0,
            "skipped":  0,
            "errors":   [],
            "gaps":     [],
        }


# ---------------------------------------------------------------------------
# Hilfsfunktionen (Modul-Ebene)
# ---------------------------------------------------------------------------

def _parse_date(value) -> Optional[date]:
    """Parst EODHD-Datumsstrings (YYYY-MM-DD) zu date-Objekten."""
    if not value:
        return None
    try:
        if isinstance(value, date):
            return value
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _safe_int(value) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _update_fields(record: MarketData, item: dict) -> bool:
    """Aktualisiert Felder eines bestehenden Datensatzes. Gibt True zurück wenn etwas geändert wurde."""
    changed = False
    field_map = {
        "open":           ("open",           _to_decimal),
        "high":           ("high",           _to_decimal),
        "low":            ("low",            _to_decimal),
        "close":          ("close",          _to_decimal),
        "volume":         ("volume",         _safe_int),
        "adjusted_close": ("adj_close",      _to_decimal),
    }
    for api_key, (attr, converter) in field_map.items():
        new_val = converter(item.get(api_key))
        if new_val is not None and getattr(record, attr) != new_val:
            setattr(record, attr, new_val)
            changed = True
    return changed


def _infer_currency(exchange_suffix: str) -> Optional[str]:
    """Leitet die Währung aus dem EODHD Exchange-Suffix ab."""
    suffix_currency_map = {
        "US":    "USD",
        "LSE":   "GBP",
        "AS":    "EUR",    # Euronext Amsterdam
        "PA":    "EUR",    # Euronext Paris
        "XETRA": "EUR",
        "F":     "EUR",    # Frankfurt
        "SW":    "CHF",
        "TO":    "CAD",
        "AU":    "AUD",
        "TYO":   "JPY",
        "FOREX": "USD",    # FX-Paare und Edelmetalle: Quote-Währung USD
        "CC":    "USD",    # Krypto: in USD quotiert
    }
    return suffix_currency_map.get((exchange_suffix or "").upper())
