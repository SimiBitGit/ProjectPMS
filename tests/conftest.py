# tests/conftest.py
"""
Pytest Fixtures für Portfolio Manager Tests.

Zentrale Fixtures:
  - engine        → In-Memory SQLite Engine
  - session       → Frische DB-Session (pro Test isoliert, auto-rollback)
  - sample_ticker → Ticker-Factory
  - sample_bars   → OHLCVBar-Factory
  - sample_market_data → MarketData-Records in der DB
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.base import Base
from src.models.metadata import Ticker, AssetType
from src.models.gics import GicsReference  # Muss importiert sein damit FK-Constraint funktioniert
from src.models.market_data import MarketData, DataEditLog
from src.models.processed_data import ProcessedData
from src.views.widgets.chart_widget import OHLCVBar


# ──────────────────────────────────────────
#  DB-Engine & Session
# ──────────────────────────────────────────

@pytest.fixture(scope="session")
def engine():
    """In-Memory SQLite Engine (einmal pro Test-Session)."""
    eng = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    """
    Isolierte DB-Session pro Test.
    Verwendet eine verschachtelte Transaktion, die nach dem Test
    zurückgerollt wird → keine Seiteneffekte zwischen Tests.
    """
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    sess = Session()

    yield sess

    sess.close()
    transaction.rollback()
    connection.close()


# ──────────────────────────────────────────
#  Ticker-Factories
# ──────────────────────────────────────────

@pytest.fixture
def sample_ticker(session):
    """Erstellt einen AAPL-Ticker in der DB und gibt ihn zurück."""
    ticker = Ticker(
        symbol="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
        currency="USD",
        asset_type=AssetType.STOCK,
        is_active=True,
    )
    session.add(ticker)
    session.flush()
    return ticker


@pytest.fixture
def sample_ticker_etf(session):
    """Erstellt einen SPY-ETF-Ticker in der DB."""
    ticker = Ticker(
        symbol="SPY",
        name="SPDR S&P 500 ETF",
        exchange="NYSE",
        currency="USD",
        asset_type=AssetType.ETF,
        is_active=True,
        etf_provider="SPDR",
        ter_percent=Decimal("0.0945"),
    )
    session.add(ticker)
    session.flush()
    return ticker


@pytest.fixture
def multiple_tickers(session):
    """Erstellt mehrere Ticker verschiedener Typen."""
    tickers = [
        Ticker(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ",
               currency="USD", asset_type=AssetType.STOCK, is_active=True),
        Ticker(symbol="MSFT", name="Microsoft Corp.", exchange="NASDAQ",
               currency="USD", asset_type=AssetType.STOCK, is_active=True),
        Ticker(symbol="SPY", name="SPDR S&P 500 ETF", exchange="NYSE",
               currency="USD", asset_type=AssetType.ETF, is_active=True),
        Ticker(symbol="EURUSD", name="EUR/USD", exchange="FX",
               currency="USD", asset_type=AssetType.FX, is_active=True),
        Ticker(symbol="INACTIVE", name="Deactivated", exchange="NASDAQ",
               currency="USD", asset_type=AssetType.STOCK, is_active=False),
    ]
    session.add_all(tickers)
    session.flush()
    return tickers


# ──────────────────────────────────────────
#  MarketData-Factories
# ──────────────────────────────────────────

def _generate_market_data(ticker_id: int, num_days: int = 60, start_price: float = 150.0) -> list[MarketData]:
    """Generiert realistische Marktdaten-Einträge."""
    records = []
    price = start_price
    d = date(2024, 1, 2)

    for _ in range(num_days):
        # Wochenenden überspringen
        while d.weekday() >= 5:
            d += timedelta(days=1)

        import random
        random.seed(d.toordinal())  # Deterministisch pro Datum
        change = random.uniform(-3, 3)
        o = round(price + change, 4)
        h = round(o + abs(change) + random.uniform(0.5, 2), 4)
        l = round(o - abs(change) - random.uniform(0.5, 2), 4)
        c = round((o + h + l) / 3, 4)
        price = c

        records.append(MarketData(
            ticker_id=ticker_id,
            date=d,
            open=Decimal(str(o)),
            high=Decimal(str(h)),
            low=Decimal(str(l)),
            close=Decimal(str(c)),
            volume=random.randint(20_000_000, 80_000_000),
            adj_close=Decimal(str(c)),
            source="test",
        ))
        d += timedelta(days=1)

    return records


@pytest.fixture
def sample_market_data(session, sample_ticker):
    """Erstellt 60 Tage Marktdaten für den AAPL-Ticker."""
    records = _generate_market_data(sample_ticker.ticker_id, num_days=60)
    session.add_all(records)
    session.flush()
    return records


@pytest.fixture
def sample_bars():
    """Erstellt eine OHLCVBar-Liste (für Service/Controller-Tests ohne DB)."""
    bars = []
    price = 150.0
    d = date(2024, 1, 2)

    import random
    random.seed(42)

    for _ in range(60):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        o = round(price + random.uniform(-2, 2), 4)
        h = round(o + random.uniform(0.5, 3), 4)
        l = round(o - random.uniform(0.5, 3), 4)
        c = round((o + h + l) / 3, 4)
        price = c
        bars.append(OHLCVBar(
            date=d, open=o, high=h, low=l, close=c,
            volume=random.randint(20_000_000, 80_000_000),
            adj_close=c,
        ))
        d += timedelta(days=1)

    return bars
