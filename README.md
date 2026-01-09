# Portfolio Management System

Ein Desktop-basiertes Portfolio Management System für quantitatives Trading und Investitions-Analysen.

## Features (MVP Phase 1)

- ✅ End-of-Day Marktdaten-Import (EoD Historical Data)
- ✅ Unterstützung für Securities (Stocks, ETFs, Indices) und FX (Währungen)
- ✅ Datenbank-gestützte Verwaltung von Markt- und berechneten Daten
- ✅ Interaktive UI für Daten-Visualisierung und -Bearbeitung
- ✅ Technische Analyse-Indikatoren (SMA, MACD, ROC)
- ✅ SQLite mit Migration-Pfad zu PostgreSQL

## Technologie-Stack

- **Python 3.11+**
- **PySide6** (Qt for Python) - Desktop UI
- **SQLAlchemy** - ORM und Datenbank-Abstraktionsschicht
- **Pandas & NumPy** - Datenverarbeitung
- **PyQtGraph** - Charting
- **EoD Historical Data API** - Marktdaten-Quelle

## Installation

1. **Repository klonen**
```bash
git clone <repository-url>
cd portfolio_manager
```

2. **Virtual Environment erstellen**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate  # Windows
```

3. **Dependencies installieren**
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Für Entwicklung
```

4. **Umgebungsvariablen konfigurieren**
```bash
cp .env.example .env
# .env bearbeiten und EODHD_API_KEY eintragen
```

5. **Datenbank initialisieren**
```bash
python -m src.database.init_db
```

## Projektstruktur

```
portfolio_manager/
├── src/                    # Quellcode
│   ├── models/            # SQLAlchemy Models
│   ├── database/          # DB-Verbindung & Repositories
│   ├── services/          # Geschäftslogik
│   ├── controllers/       # MVC Controller
│   ├── views/             # UI (PyQt6)
│   └── utils/             # Hilfsfunktionen
├── tests/                 # Unit & Integration Tests
├── data/                  # Datenbank & Cache
├── config/                # Konfigurationsdateien
└── docs/                  # Dokumentation
```

## Verwendung

### Applikation starten
```bash
python -m src.main
```

### Tests ausführen
```bash
pytest
pytest --cov=src  # Mit Coverage
```

### Daten importieren (CLI)
```bash
python -m src.scripts.import_data --symbol AAPL --start 2024-01-01 --end 2024-12-31
```

## Entwicklungs-Roadmap

### ✅ Phase 1: Fundament (Woche 1-2)
- Projektstruktur
- SQLAlchemy-Modelle
- Repository-Pattern
- Konfiguration

### 🚧 Phase 2: Datenimport (Woche 3)
- MarketDataImporter
- EoD Historical Data Integration
- CLI-Tool

### ⏳ Phase 3: UI Grundgerüst (Woche 4-5)
- Main Window
- Ticker-Liste
- Import-Dialog

### ⏳ Phase 4: Visualisierung (Woche 6)
- Chart-Widget
- Data-Table
- Date-Range Selector

### ⏳ Phase 5: Analyse (Woche 7-8)
- SMA, MACD, ROC Indikatoren
- Analysis-Service
- UI-Integration

## Konfiguration

Hauptkonfiguration in `config/settings.yaml`:
- Datenbank-Einstellungen
- API-Konfiguration
- UI-Preferences
- Logging

Sensitive Daten in `.env`:
- API-Keys
- Datenbank-Credentials

## Lizenz

Privates Projekt - Alle Rechte vorbehalten

## Kontakt

[Ihr Name/Email]
