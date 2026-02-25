# Portfolio Management System

Ein Desktop-basiertes Portfolio Management System für quantitatives Trading und Investitions-Analysen.

## Aktueller Projektstand

| Phase | Inhalt | Status |
|---|---|---|
| Phase 1 | Fundament (DB, Models, Repositories) | ✅ Abgeschlossen |
| Phase 2 | Datenimport (EoD API) | ✅ Abgeschlossen |
| Phase 3 | UI Grundgerüst (MainWindow, Widgets) | ✅ Abgeschlossen |
| Phase 4 | Visualisierung (Chart, Tabelle) | ✅ Abgeschlossen |
| Phase 5 | Analyse-Services & Controller | 🚧 In Arbeit |

## Features

### ✅ Implementiert
- **Datenbank** — SQLite mit SQLAlchemy ORM, Alembic-Migrationen, Migration-Ready für PostgreSQL
- **Datenimport** — EoD Historical Data API (Stocks, ETFs, Indices, FX, Crypto, Commodities, Bonds)
- **GICS-Klassifikation** — Vollständige GICS-Hierarchie (Sektor → Industry Group → Industry → Sub-Industry, 2024-08), Seed-Daten enthalten, automatische Denormalisierung via `TickerService`
- **Erweitertes Ticker-Model** — GICS-Codes (denormalisiert für Performance), ETF-spezifische Felder (Provider, TER, AUM, Replikationsmethode, Domizil, ISIN)
- **TickerService** — Service-Schicht mit DTOs (`TickerCreateDTO`, `TickerUpdateDTO`), GICS-Validierung, typsichere Ticker-Verwaltung
- **ETF-Universum-Import** — Bulk-Import aus Excel (`data/imports/sub_industry_etf_universe.xlsx`) via CLI-Script
- **Desktop-UI** — PySide6 Dark Theme mit MVC-Architektur
  - `TickerListWidget` — Watchlist mit Suche, Asset-Typ-Filter, Add-Dialog
  - `ChartWidget` — Candlestick-Chart mit Volumen, Crosshair, Range-Slider, Indikator-Overlays
  - `DataTableWidget` — OHLCV-Tabelle mit Inline-Editing, Audit-Log, CSV-Export
  - `ImportDialog` — Datenimport mit Background-Thread und Live-Fortschrittsanzeige
  - `MainWindow` — MVC-Hauptfenster mit Menüleiste, Toolbar, Splitter-Layout
- **Technische Indikatoren** — SMA, EMA, MACD, ROC (berechnet, als Chart-Overlay darstellbar)
- **Audit-Trail** — Vollständiges Edit-Log für manuelle Datenänderungen

### 🚧 In Arbeit / Nächste Schritte
- Controller-Schicht (`data_controller.py`, `analysis_controller.py`)
- Analysis-Service (`analysis_service.py`) mit Persistierung in `processed_data`
- ForeignKey-Constraint `tickers.gics_sub_industry_code → gics_reference` reaktivieren (GICS_TODO)
- Unit Tests

### ⏳ Geplant
- Trade-Erfassung und Portfolio-Verwaltung
- Reporting-Modul
- Weitere Marktdaten-Quellen
- Proprietäre, erweiterte Analyse-Indikatoren (Herzstück des Projekts)

## Technologie-Stack

| Bereich | Technologie |
|---|---|
| Sprache | Python 3.13 |
| UI-Framework | PySide6 (Qt for Python) |
| Charting | pyqtgraph |
| ORM | SQLAlchemy 2.0 |
| Datenbank | SQLite (→ PostgreSQL Migration-Ready) |
| Migrationen | Alembic |
| Datenverarbeitung | pandas, numpy |
| Marktdaten-API | EoD Historical Data (eodhd.com) |
| ETF-Import | openpyxl |
| Tests | pytest |

## Projektstruktur

```
ProjectPMS/
│
├── src/
│   ├── main.py
│   ├── config.py
│   │
│   ├── models/
│   │   ├── base.py                      # Engine & Session
│   │   ├── metadata.py                  # Ticker (+ GICS + ETF-Felder)
│   │   ├── gics.py                      # GicsReference Model
│   │   ├── gics_seed_data.py            # Vollständige GICS-Daten 2024-08
│   │   ├── market_data.py               # OHLCV + DataEditLog
│   │   └── processed_data.py            # Berechnete Indikatoren
│   │
│   ├── database/
│   │   ├── base_repository.py
│   │   ├── ticker_repository.py
│   │   ├── market_data_repository.py
│   │   ├── processed_data_repository.py
│   │   ├── gics_repository.py           # GICS-Lookup + Sektor-Abfragen
│   │   ├── init_db.py
│   │   └── migrations/
│   │       └── 0002_gics_extension.py
│   │
│   ├── services/
│   │   ├── data_import.py               # EoD API Integration
│   │   └── ticker_service.py            # TickerService + DTOs
│   │
│   ├── scripts/
│   │   ├── import_data.py               # CLI: Einzelner Ticker-Import
│   │   └── import_etf_universe.py       # CLI: Bulk-Import aus Excel
│   │
│   ├── controllers/                     # 🚧 ausstehend
│   │
│   ├── views/
│   │   ├── main_window.py
│   │   ├── widgets/
│   │   │   ├── ticker_list.py
│   │   │   ├── chart_widget.py
│   │   │   ├── data_table.py
│   │   │   ├── market_data_panel.py
│   │   │   └── status_bar_widget.py
│   │   └── dialogs/
│   │       └── import_dialog.py
│   │
│   └── utils/
│       └── logger.py
│
├── data/
│   ├── database/portfolio.db
│   └── imports/
│       └── sub_industry_etf_universe.xlsx
│
├── config/settings.yaml
├── .env.example
├── requirements.txt
└── test_installation.py
```

## Installation & Start

```bash
git clone https://github.com/SimiBitGit/ProjectPMS.git
cd ProjectPMS

python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac

pip install -r requirements.txt

cp .env.example .env
# EODHD_API_KEY in .env eintragen

python -m src.database.init_db
python src/main.py
```

## ETF-Universum importieren

```bash
python -m src.scripts.import_etf_universe --dry-run   # nur validieren
python -m src.scripts.import_etf_universe             # importieren
python -m src.scripts.import_etf_universe --update    # bestehende aktualisieren
```

## Kollaboration mit Claude

Zu Beginn jeder Session `src/` als ZIP + die drei Dokumente hochladen.

GitHub: [https://github.com/SimiBitGit/ProjectPMS](https://github.com/SimiBitGit/ProjectPMS)

## Lizenz

Privates Projekt — Alle Rechte vorbehalten
