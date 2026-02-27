# Portfolio Management System

Ein Desktop-basiertes Portfolio Management System für quantitatives Trading und Investitions-Analysen.

## Aktueller Projektstand

| Phase | Inhalt | Status |
|---|---|---|
| Phase 1 | Fundament (DB, Models, Repositories) | ✅ Abgeschlossen |
| Phase 2 | Datenimport (EoD API) | ✅ Abgeschlossen |
| Phase 3 | UI Grundgerüst (MainWindow, Widgets) | ✅ Abgeschlossen |
| Phase 4 | Visualisierung (Chart, Tabelle) | ✅ Abgeschlossen |
| Phase 5 | Analyse-Services, Controller, Tests | ✅ Abgeschlossen |

## Features

### ✅ Implementiert
- **Datenbank** — SQLite mit SQLAlchemy ORM, Alembic-Migrationen, Migration-Ready für PostgreSQL
- **Datenimport** — EoD Historical Data API (Stocks, ETFs, Indices, FX, Crypto, Commodities, Bonds)
- **Bulk-Update** — Alle aktiven Ticker auf Knopfdruck aktualisieren (`UpdateAllDialog` mit Background-Worker, Lookback-Tage konfigurierbar, Abbruch möglich)
- **GICS-Klassifikation** — Vollständige GICS-Hierarchie (2024-08), ForeignKey + Relationship aktiv, `gics_full_path` Property, automatische Denormalisierung via `TickerService`
- **Erweitertes Ticker-Model** — GICS-Codes (denormalisiert), ETF-Felder (Provider, TER, AUM, Replikationsmethode, Domizil, ISIN)
- **TickerService** — Service-Schicht mit DTOs, GICS-Validierung, typsichere Ticker-Verwaltung
- **ETF-Universum-Import** — Bulk-Import aus Excel via CLI-Script
- **Desktop-UI** — PySide6 Dark Theme mit MVC-Architektur
  - `TickerListWidget` — Watchlist mit Suche, Asset-Typ-Filter, Add-Dialog
  - `ChartWidget` — Candlestick-Chart mit Volumen, Crosshair, Range-Slider, Indikator-Overlays, Klick-Selektion + Delete-Taste
  - `DataTableWidget` — OHLCV-Tabelle mit Inline-Editing, Audit-Log, CSV-Export
  - `IndicatorsTab` — Berechnen mit frei wählbarer Periode (SpinBox 1–999), aktive Indikatoren-Liste mit Entfernen-Buttons
  - `ImportDialog` — Datenimport mit Background-Thread und Live-Fortschrittsanzeige
  - `UpdateAllDialog` — Alle Ticker aktualisieren mit Fortschritt und Abbruch
  - `MainWindow` — MVC-Hauptfenster mit Menüleiste, Toolbar, Splitter-Layout
- **Technische Indikatoren** — SMA, EMA, MACD, ROC (berechnet, persistiert, als Chart-Overlay darstellbar)
- **Indikator-Management** — Einzeln oder alle entfernen (Tab + Chart), Auto-Recompute bei Ticker-Wechsel
- **Controller-Schicht** — `DataController` (Audit-Log), `AnalysisController` (Indikatoren + Auto-Recompute)
- **Analysis-Service** — Indikator-Berechnung + Persistierung in `processed_data` (delete-before-insert)
- **Audit-Trail** — Vollständiges Edit-Log für manuelle Datenänderungen
- **Unit Tests** — 79 Tests (Repositories, Services, Controller), alle grün

### ⏳ Geplant
- Bollinger Bands
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
│   │   ├── metadata.py                  # Ticker (+ GICS-FK + ETF-Felder)
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
│   │   ├── gics_repository.py
│   │   ├── init_db.py
│   │   └── migrations/
│   │       └── 0002_gics_extension.py
│   │
│   ├── services/
│   │   ├── data_import.py               # EoD API Integration
│   │   ├── ticker_service.py            # TickerService + DTOs
│   │   └── analysis_service.py          # Indikator-Berechnung + Persistierung
│   │
│   ├── scripts/
│   │   ├── import_data.py
│   │   └── import_etf_universe.py
│   │
│   ├── controllers/
│   │   ├── data_controller.py           # DataTable ↔ Audit-Log
│   │   └── analysis_controller.py       # Indikatoren + Auto-Recompute
│   │
│   ├── views/
│   │   ├── main_window.py
│   │   ├── widgets/
│   │   │   ├── ticker_list.py
│   │   │   ├── chart_widget.py          # + Klick-Selektion + Delete
│   │   │   ├── data_table.py
│   │   │   ├── market_data_panel.py     # + IndicatorsTab mit Entfernen-UI
│   │   │   └── status_bar_widget.py
│   │   └── dialogs/
│   │       ├── import_dialog.py
│   │       └── update_dialog.py         # Alle Ticker aktualisieren
│   │
│   └── utils/
│       └── logger.py
│
├── tests/                               # 79 Tests
│   ├── conftest.py
│   ├── test_repositories/
│   ├── test_services/
│   └── test_controllers/
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

## Tests ausführen

```bash
python -m pytest tests/ -v
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
