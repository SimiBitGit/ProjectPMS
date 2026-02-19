#!/usr/bin/env python
# src/scripts/import_data.py
"""
CLI-Tool für den EODHD-Marktdaten-Import

Verwendung:
    # Alle Standard-Underlyings auf einmal laden (ETFs + FX + Crypto + Metalle)
    python -m src.scripts.import_data import --defaults --from 2015-01-01

    # Einzelner Ticker (Kürzel oder EODHD-Symbol gleichwertig)
    python -m src.scripts.import_data import IWDA --from 2015-01-01
    python -m src.scripts.import_data import IWDA.AS --from 2015-01-01

    # FX / Metalle per Kürzel
    python -m src.scripts.import_data import EURUSD XAUUSD BTCUSD --from 2018-01-01

    # Mehrere Ticker (Bulk)
    python -m src.scripts.import_data import IWDA CSPX SPY --from 2020-01-01

    # Symbol-Liste aus Datei (ein Kürzel oder EODHD-Symbol pro Zeile)
    python -m src.scripts.import_data import --file etf_list.txt --from 2015-01-01

    # Mit explizitem Enddatum
    python -m src.scripts.import_data import IWDA --from 2020-01-01 --to 2024-12-31

    # Cache ignorieren (frische Daten)
    python -m src.scripts.import_data import IWDA --from 2024-01-01 --force

    # Alle aktiven Ticker auf heute bringen
    python -m src.scripts.import_data update

    # Nur bestimmte Ticker updaten
    python -m src.scripts.import_data update EURUSD XAUUSD

    # In der DB vorhandene Ticker anzeigen
    python -m src.scripts.import_data list

    # Ausgabe als JSON (für Scripts)
    python -m src.scripts.import_data import --defaults --from 2020-01-01 --json
"""

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

# Projekt-Root zum PYTHONPATH hinzufügen (für direkten Aufruf ohne -m)
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.models.base import get_session
from src.services.data_import import MarketDataImporter, KNOWN_SYMBOLS, DEFAULT_SYMBOLS
from src.utils.logger import setup_logger

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = setup_logger(__name__)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _parse_date_arg(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Ungültiges Datum '{value}'. Format: YYYY-MM-DD"
        )


def _resolve_symbols(raw: list[str]) -> list[str]:
    """
    Löst lesbare Kürzel in EODHD-Symbole auf.
    Unbekannte Werte werden unverändert weitergereicht (direkte EODHD-Symbole).
    Beispiel: "EURUSD" → "EURUSD.FOREX", "IWDA.AS" → "IWDA.AS"
    """
    resolved = []
    for s in raw:
        upper = s.upper().strip()
        resolved.append(KNOWN_SYMBOLS.get(upper, upper))
    return resolved


def _print_result(result: dict, use_json: bool) -> None:
    if use_json:
        print(json.dumps(result, indent=2, default=str))
        return

    symbol  = result["symbol"]
    ins     = result["inserted"]
    upd     = result["updated"]
    skip    = result["skipped"]
    errs    = result["errors"]
    gaps    = result["gaps"]

    status = "✅" if not errs else "⚠️"
    print(f"\n{status} {symbol}")
    print(f"   Inserted : {ins}")
    print(f"   Updated  : {upd}")
    print(f"   Skipped  : {skip}")
    if gaps:
        print(f"   Gaps     : {len(gaps)} erkannte Lücken (z.B. ab {gaps[0]})")
    if errs:
        print(f"   Errors   : {len(errs)}")
        for e in errs[:5]:
            print(f"     - {e}")


def _print_summary(results: list[dict]) -> None:
    total_ins  = sum(r["inserted"] for r in results)
    total_upd  = sum(r["updated"]  for r in results)
    total_skip = sum(r["skipped"]  for r in results)
    failed     = [r["symbol"] for r in results if r["errors"]]

    print("\n" + "=" * 50)
    print(f"  ZUSAMMENFASSUNG – {len(results)} Ticker")
    print("=" * 50)
    print(f"  Gesamt inserted : {total_ins}")
    print(f"  Gesamt updated  : {total_upd}")
    print(f"  Gesamt skipped  : {total_skip}")
    if failed:
        print(f"  Mit Fehlern     : {', '.join(failed)}")
    else:
        print("  Alle erfolgreich! ✅")
    print("=" * 50)


# ---------------------------------------------------------------------------
# Subcommand: import
# ---------------------------------------------------------------------------

def cmd_import(args) -> int:
    symbols: list[str] = []

    # --defaults: alle Projekt-Standard-Underlyings
    if getattr(args, "defaults", False):
        symbols.extend(DEFAULT_SYMBOLS)

    # Symbole aus Argumenten (Kürzel oder EODHD-Symbole)
    if args.symbols:
        symbols.extend(_resolve_symbols(args.symbols))

    # Symbole aus Datei
    if args.file:
        f = Path(args.file)
        if not f.exists():
            print(f"❌ Datei nicht gefunden: {f}", file=sys.stderr)
            return 1
        lines = f.read_text(encoding="utf-8").splitlines()
        raw = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
        symbols.extend(_resolve_symbols(raw))

    if not symbols:
        print("❌ Keine Symbole angegeben (--file oder Positionsargumente).", file=sys.stderr)
        return 1

    # Doppelte entfernen, Reihenfolge behalten
    seen = set()
    symbols = [s for s in symbols if not (s in seen or seen.add(s))]

    start_date = args.start
    end_date   = args.end or date.today()

    print(f"\n📥 Import: {len(symbols)} Ticker | {start_date} → {end_date}")
    if args.force:
        print("   (Cache wird ignoriert)")

    session = get_session()
    try:
        importer = MarketDataImporter.from_config(session)

        if len(symbols) == 1:
            result = importer.import_ticker(
                symbols[0],
                start_date=start_date,
                end_date=end_date,
                force_refresh=args.force,
            )
            results = [result]
        else:
            results = importer.import_bulk(
                symbols,
                start_date=start_date,
                end_date=end_date,
                force_refresh=args.force,
                pause_between=args.pause,
            )

        for r in results:
            _print_result(r, args.json)

        if not args.json and len(results) > 1:
            _print_summary(results)

        # Exit-Code: 1 wenn mindestens ein Symbol Fehler hatte
        has_errors = any(r["errors"] for r in results)
        return 1 if has_errors else 0

    except ValueError as exc:
        # z.B. fehlender API-Key
        print(f"\n❌ Konfigurationsfehler: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        logger.exception("Unerwarteter Fehler")
        print(f"\n❌ Unerwarteter Fehler: {exc}", file=sys.stderr)
        return 3
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Subcommand: update
# ---------------------------------------------------------------------------

def cmd_update(args) -> int:
    symbols = [s.upper().strip() for s in args.symbols] if args.symbols else None
    lookback = args.lookback

    if symbols:
        print(f"\n🔄 Update: {len(symbols)} Ticker | letzte {lookback} Tage")
    else:
        print(f"\n🔄 Update: alle aktiven Ticker | letzte {lookback} Tage")

    session = get_session()
    try:
        importer = MarketDataImporter.from_config(session)
        results = importer.update_to_today(symbols=symbols, lookback_days=lookback)

        if not results:
            print("ℹ️  Keine aktiven Ticker in der Datenbank.")
            return 0

        for r in results:
            _print_result(r, args.json)

        if not args.json:
            _print_summary(results)

        return 1 if any(r["errors"] for r in results) else 0

    except ValueError as exc:
        print(f"\n❌ Konfigurationsfehler: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        logger.exception("Unerwarteter Fehler beim Update")
        print(f"\n❌ Fehler: {exc}", file=sys.stderr)
        return 3
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Subcommand: list
# ---------------------------------------------------------------------------

def cmd_list(args) -> int:
    """Zeigt alle aktiven Ticker in der Datenbank."""
    session = get_session()
    try:
        from src.database.ticker_repository import TickerRepository
        repo = TickerRepository(session)
        tickers = repo.get_all_active()

        if not tickers:
            print("ℹ️  Keine aktiven Ticker in der Datenbank.")
            return 0

        print(f"\n{'Symbol':<20} {'Name':<30} {'Exchange':<10} {'Typ':<12} {'Währung'}")
        print("-" * 85)
        for t in sorted(tickers, key=lambda x: x.symbol):
            print(
                f"{t.symbol:<20} {(t.name or ''):<30} "
                f"{(t.exchange or ''):<10} "
                f"{(t.asset_type.value if t.asset_type else ''):<12} "
                f"{t.currency or ''}"
            )
        print(f"\nGesamt: {len(tickers)} Ticker")
        return 0
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Argument-Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="import_data",
        description="Portfolio Manager – Marktdaten-Import CLI (EODHD)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ---- import ----
    p_import = sub.add_parser(
        "import",
        help="Historische OHLCV-Daten importieren",
    )
    p_import.add_argument(
        "symbols",
        nargs="*",
        metavar="SYMBOL",
        help="EODHD-Symbol(e), z.B. IWDA.AS SPY.US",
    )
    p_import.add_argument(
        "--file", "-f",
        metavar="DATEI",
        help="Textdatei mit einem Symbol pro Zeile",
    )
    p_import.add_argument(
        "--defaults",
        action="store_true",
        help=(
            "Alle Standard-Underlyings laden: "
            "ETFs (IWDA, CSPX, SPY, QQQ) · "
            "FX (EURUSD, USDCHF, GBPUSD, AUDUSD, USDCAD, USDJPY) · "
            "Crypto (BTCUSD) · Edelmetalle (XAUUSD, XAGUSD)"
        ),
    )
    p_import.add_argument(
        "--from", dest="start",
        required=True,
        type=_parse_date_arg,
        metavar="YYYY-MM-DD",
        help="Startdatum",
    )
    p_import.add_argument(
        "--to", dest="end",
        type=_parse_date_arg,
        metavar="YYYY-MM-DD",
        default=None,
        help="Enddatum (Standard: heute)",
    )
    p_import.add_argument(
        "--force",
        action="store_true",
        help="Cache ignorieren, frische Daten von API holen",
    )
    p_import.add_argument(
        "--pause",
        type=float,
        default=0.5,
        metavar="SEKS",
        help="Pause zwischen Bulk-API-Calls in Sekunden (Standard: 0.5)",
    )
    p_import.add_argument(
        "--json",
        action="store_true",
        help="Ausgabe als JSON",
    )
    p_import.set_defaults(func=cmd_import)

    # ---- update ----
    p_update = sub.add_parser(
        "update",
        help="Aktive Ticker auf den heutigen Stand bringen",
    )
    p_update.add_argument(
        "symbols",
        nargs="*",
        metavar="SYMBOL",
        help="Einzuschränkende Symbole (Standard: alle aktiven)",
    )
    p_update.add_argument(
        "--lookback",
        type=int,
        default=7,
        metavar="TAGE",
        help="Wie viele Tage zurück der Start-Offset ist (Standard: 7)",
    )
    p_update.add_argument(
        "--json",
        action="store_true",
        help="Ausgabe als JSON",
    )
    p_update.set_defaults(func=cmd_update)

    # ---- list ----
    p_list = sub.add_parser(
        "list",
        help="Alle aktiven Ticker in der Datenbank anzeigen",
    )
    p_list.set_defaults(func=cmd_list)

    return parser


# ---------------------------------------------------------------------------
# Entry-Point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
