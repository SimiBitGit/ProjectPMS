"""
TickerService — Geschäftslogik für Ticker-Verwaltung

Kernaufgaben:
- Ticker erstellen und aktualisieren (mit automatischer GICS-Denormalisierung)
- GICS-Codes validieren und befüllen
- ETF-spezifische Logik (Provider, TER, AUM)
- Soft-Delete (is_active Flag)

Verwendung:
    service = TickerService(session)
    ticker = service.create_ticker(TickerCreateDTO(...))
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List
from sqlalchemy.orm import Session

from src.models.metadata import Ticker, AssetType, GicsLevel, EtfReplicationMethod
from src.models.gics import GicsReference
from src.database.ticker_repository import TickerRepository
from src.database.gics_repository import GicsRepository
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ===========================================================================
# DTOs (Data Transfer Objects) — typsichere Eingabe-Strukturen
# ===========================================================================

@dataclass
class TickerCreateDTO:
    """Eingabedaten zum Erstellen eines neuen Tickers."""
    symbol:     str
    asset_type: AssetType
    name:       Optional[str]     = None
    exchange:   Optional[str]     = None
    currency:   Optional[str]     = None
    isin:       Optional[str]     = None

    # GICS-Klassifikation
    # Für Stocks: sub_industry_code setzen (8-stellig) → alles wird automatisch befüllt
    # Für Sektor-ETFs (z.B. XLK): nur sector_code + gics_level=SECTOR
    # Für Sub-Industry-ETFs (z.B. SOXX): sub_industry_code setzen
    gics_sub_industry_code:   Optional[str]       = None
    gics_sector_code:         Optional[str]       = None
    gics_industry_group_code: Optional[str]       = None
    gics_industry_code:       Optional[str]       = None
    gics_level:               Optional[GicsLevel] = None

    # ETF-spezifisch (nur relevant wenn asset_type = ETF)
    etf_provider:       Optional[str]                  = None
    underlying_index:   Optional[str]                  = None
    aum_usd:            Optional[Decimal]              = None
    ter_percent:        Optional[Decimal]              = None
    replication_method: Optional[EtfReplicationMethod] = None
    domicile:           Optional[str]                  = None


@dataclass
class TickerUpdateDTO:
    """Felder für ein Update — None bedeutet 'nicht ändern'."""
    name:                     Optional[str]                  = None
    exchange:                 Optional[str]                  = None
    currency:                 Optional[str]                  = None
    isin:                     Optional[str]                  = None
    gics_sub_industry_code:   Optional[str]                  = None
    gics_sector_code:         Optional[str]                  = None
    gics_industry_group_code: Optional[str]                  = None
    gics_industry_code:       Optional[str]                  = None
    gics_level:               Optional[GicsLevel]            = None
    etf_provider:             Optional[str]                  = None
    underlying_index:         Optional[str]                  = None
    aum_usd:                  Optional[Decimal]              = None
    ter_percent:              Optional[Decimal]              = None
    replication_method:       Optional[EtfReplicationMethod] = None
    domicile:                 Optional[str]                  = None
    is_active:                Optional[bool]                 = None


# ===========================================================================
# Exceptions
# ===========================================================================

class TickerAlreadyExistsError(Exception):
    pass

class TickerNotFoundError(Exception):
    pass

class InvalidGicsCodeError(Exception):
    pass

class InvalidTickerDataError(Exception):
    pass


# ===========================================================================
# TickerService
# ===========================================================================

class TickerService:
    """
    Service-Schicht für die Ticker-Verwaltung.

    Verantwortlichkeiten:
    - Validierung der Eingabedaten
    - Automatische GICS-Denormalisierung:
      Wenn sub_industry_code gesetzt wird, werden sector_code, industry_group_code
      und industry_code automatisch aus der gics_reference Tabelle befüllt.
    - Koordination zwischen TickerRepository und GicsRepository
    """

    def __init__(self, session: Session):
        self.session     = session
        self.ticker_repo = TickerRepository(session)
        self.gics_repo   = GicsRepository(session)

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def create_ticker(self, dto: TickerCreateDTO) -> Ticker:
        """
        Erstellt einen neuen Ticker.

        Raises:
            TickerAlreadyExistsError: Symbol existiert bereits
            InvalidGicsCodeError:    GICS-Code nicht in gics_reference gefunden
            InvalidTickerDataError:  Pflichtfelder fehlen oder inkonsistent
        """
        logger.info(f"Erstelle Ticker: {dto.symbol} ({dto.asset_type})")

        # 1. Duplikat prüfen
        if self.ticker_repo.get_by_symbol(dto.symbol):
            raise TickerAlreadyExistsError(
                f"Ticker '{dto.symbol}' existiert bereits."
            )

        # 2. Validierung
        self._validate_create_dto(dto)

        # 3. GICS-Felder auflösen (automatische Denormalisierung)
        gics_fields = self._resolve_gics_fields(
            sub_industry_code=dto.gics_sub_industry_code,
            sector_code=dto.gics_sector_code,
            industry_group_code=dto.gics_industry_group_code,
            industry_code=dto.gics_industry_code,
            gics_level=dto.gics_level,
        )

        # 4. Ticker-Objekt erstellen
        ticker = Ticker(
            symbol=dto.symbol.upper().strip(),
            asset_type=dto.asset_type,
            name=dto.name,
            exchange=dto.exchange,
            currency=dto.currency.upper() if dto.currency else None,
            isin=dto.isin,
            # GICS (automatisch befüllt)
            **gics_fields,
            # ETF-Felder
            etf_provider=dto.etf_provider,
            underlying_index=dto.underlying_index,
            aum_usd=dto.aum_usd,
            ter_percent=dto.ter_percent,
            replication_method=dto.replication_method,
            domicile=dto.domicile,
        )

        self.ticker_repo.create(ticker)
        logger.info(
            f"Ticker {ticker.symbol} erstellt — "
            f"Sektor: {ticker.gics_sector_code}, "
            f"Sub-Industry: {ticker.gics_sub_industry_code}"
        )
        return ticker

    def update_ticker(self, symbol: str, dto: TickerUpdateDTO) -> Ticker:
        """
        Aktualisiert einen bestehenden Ticker.
        Nur Felder die im DTO nicht None sind werden geändert.

        Wenn gics_sub_industry_code neu gesetzt wird, werden alle übergeordneten
        GICS-Codes automatisch neu denormalisiert.

        Raises:
            TickerNotFoundError:  Symbol nicht gefunden
            InvalidGicsCodeError: GICS-Code ungültig
        """
        ticker = self.ticker_repo.get_by_symbol(symbol)
        if not ticker:
            raise TickerNotFoundError(f"Ticker '{symbol}' nicht gefunden.")

        logger.info(f"Aktualisiere Ticker: {symbol}")

        # GICS-Update mit automatischer Denormalisierung
        if dto.gics_sub_industry_code is not None:
            gics_fields = self._resolve_gics_fields(
                sub_industry_code=dto.gics_sub_industry_code,
                sector_code=dto.gics_sector_code,
                industry_group_code=dto.gics_industry_group_code,
                industry_code=dto.gics_industry_code,
                gics_level=dto.gics_level,
            )
            for key, value in gics_fields.items():
                setattr(ticker, key, value)
        else:
            # Manuelle GICS-Felder direkt setzen (z.B. nur sector_code für Sektor-ETF)
            for attr in ['gics_sector_code', 'gics_industry_group_code',
                         'gics_industry_code', 'gics_level']:
                val = getattr(dto, attr, None)
                if val is not None:
                    setattr(ticker, attr, val)

        # Alle übrigen Felder
        for attr in ['name', 'exchange', 'currency', 'isin', 'etf_provider',
                     'underlying_index', 'aum_usd', 'ter_percent',
                     'replication_method', 'domicile', 'is_active']:
            val = getattr(dto, attr, None)
            if val is not None:
                setattr(ticker, attr, val)

        self.session.commit()
        logger.info(f"Ticker {symbol} aktualisiert.")
        return ticker

    def deactivate_ticker(self, symbol: str) -> Ticker:
        """Soft-Delete: setzt is_active = False."""
        return self.update_ticker(symbol, TickerUpdateDTO(is_active=False))

    def reactivate_ticker(self, symbol: str) -> Ticker:
        """Reaktiviert einen deaktivierten Ticker."""
        return self.update_ticker(symbol, TickerUpdateDTO(is_active=True))

    def get_ticker(self, symbol: str) -> Ticker:
        """Gibt einen Ticker zurück oder wirft TickerNotFoundError."""
        ticker = self.ticker_repo.get_by_symbol(symbol)
        if not ticker:
            raise TickerNotFoundError(f"Ticker '{symbol}' nicht gefunden.")
        return ticker

    def get_all_active(self) -> List[Ticker]:
        """Alle aktiven Ticker."""
        return self.ticker_repo.get_all_active()

    def get_etfs_by_sector(self, sector_code: str) -> List[Ticker]:
        """Alle aktiven ETFs eines GICS-Sektors."""
        return self.gics_repo.get_etfs_by_sector(sector_code)

    # ------------------------------------------------------------------
    # Private Hilfsmethoden
    # ------------------------------------------------------------------

    def _validate_create_dto(self, dto: TickerCreateDTO) -> None:
        """Validiert Pflichtfelder und Konsistenz der Eingabedaten."""
        if not dto.symbol or not dto.symbol.strip():
            raise InvalidTickerDataError("Symbol darf nicht leer sein.")

        if dto.ter_percent is not None and dto.ter_percent < 0:
            raise InvalidTickerDataError("TER kann nicht negativ sein.")

        if dto.aum_usd is not None and dto.aum_usd < 0:
            raise InvalidTickerDataError("AUM kann nicht negativ sein.")

        if dto.asset_type == AssetType.ETF:
            has_gics = any([
                dto.gics_sub_industry_code,
                dto.gics_sector_code,
                dto.gics_industry_group_code,
                dto.gics_industry_code,
            ])
            if not has_gics:
                logger.warning(
                    f"ETF '{dto.symbol}' hat keine GICS-Klassifikation — "
                    "Sektorrotations-Analysen werden eingeschränkt."
                )

    def _resolve_gics_fields(
        self,
        sub_industry_code: Optional[str],
        sector_code:        Optional[str],
        industry_group_code: Optional[str],
        industry_code:      Optional[str],
        gics_level:         Optional[GicsLevel],
    ) -> dict:
        """
        Löst GICS-Felder auf und denormalisiert automatisch.

        Priorität (höchste zuerst):
        1. sub_industry_code → DB-Lookup, alle übergeordneten Codes werden befüllt
        2. industry_code     → sector + group + industry werden aus Code abgeleitet
        3. industry_group_code → sector + group werden abgeleitet
        4. sector_code       → nur Sektor-Ebene

        Returns:
            dict mit gics_sub_industry_code, gics_sector_code,
            gics_industry_group_code, gics_industry_code, gics_level
        """
        result = {
            "gics_sub_industry_code":   None,
            "gics_sector_code":         None,
            "gics_industry_group_code": None,
            "gics_industry_code":       None,
            "gics_level":               None,
        }

        if not any([sub_industry_code, sector_code, industry_group_code, industry_code]):
            return result  # Kein GICS (z.B. FX)

        if sub_industry_code:
            # Vollständiger Pfad via DB-Lookup
            ref: Optional[GicsReference] = self.gics_repo.get_by_sub_industry_code(
                sub_industry_code
            )
            if not ref:
                raise InvalidGicsCodeError(
                    f"Sub-Industry-Code '{sub_industry_code}' nicht in gics_reference. "
                    "Bitte zuerst GICS-Daten laden: GicsRepository.seed_gics_data()"
                )
            result["gics_sub_industry_code"]   = ref.sub_industry_code
            result["gics_sector_code"]          = ref.sector_code
            result["gics_industry_group_code"]  = ref.industry_group_code
            result["gics_industry_code"]         = ref.industry_code
            result["gics_level"]                = GicsLevel.SUB_INDUSTRY
            logger.debug(
                f"GICS denormalisiert: {ref.sector_name} > "
                f"{ref.industry_group_name} > {ref.industry_name} > "
                f"{ref.sub_industry_name}"
            )

        elif industry_code:
            # Übergeordnete Codes aus dem Code selbst ableiten (GICS-Hierarchie ist prefix-basiert)
            result["gics_industry_code"]         = industry_code
            result["gics_industry_group_code"]  = industry_code[:4]
            result["gics_sector_code"]           = industry_code[:2]
            result["gics_level"]                 = gics_level or GicsLevel.INDUSTRY

        elif industry_group_code:
            result["gics_industry_group_code"]  = industry_group_code
            result["gics_sector_code"]           = industry_group_code[:2]
            result["gics_level"]                 = gics_level or GicsLevel.INDUSTRY_GROUP

        elif sector_code:
            result["gics_sector_code"] = sector_code
            result["gics_level"]       = gics_level or GicsLevel.SECTOR

        return result
