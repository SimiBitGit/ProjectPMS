# tests/test_repositories/test_ticker_repository.py
"""
Tests für TickerRepository.
"""

import pytest
from src.database.ticker_repository import TickerRepository
from src.models.metadata import Ticker, AssetType


class TestTickerRepository:
    """Tests für CRUD-Operationen und Abfragen auf Ticker."""

    def test_create_or_update_new(self, session):
        """Erstellt einen neuen Ticker via create_or_update."""
        repo = TickerRepository(session)
        ticker = repo.create_or_update(
            "GOOG",
            name="Alphabet Inc.",
            exchange="NASDAQ",
            currency="USD",
            asset_type=AssetType.STOCK,
        )
        assert ticker.ticker_id is not None
        assert ticker.symbol == "GOOG"
        assert ticker.asset_type == AssetType.STOCK

    def test_create_or_update_existing(self, session, sample_ticker):
        """Update eines bestehenden Tickers via create_or_update."""
        repo = TickerRepository(session)
        updated = repo.create_or_update("AAPL", name="Apple Inc. (Updated)")
        assert updated.ticker_id == sample_ticker.ticker_id
        assert updated.name == "Apple Inc. (Updated)"

    def test_get_by_symbol(self, session, sample_ticker):
        """Findet Ticker anhand des Symbols."""
        repo = TickerRepository(session)
        found = repo.get_by_symbol("AAPL")
        assert found is not None
        assert found.symbol == "AAPL"
        assert found.ticker_id == sample_ticker.ticker_id

    def test_get_by_symbol_case_insensitive(self, session, sample_ticker):
        """Symbol-Suche ist case-insensitive (upper)."""
        repo = TickerRepository(session)
        found = repo.get_by_symbol("aapl")
        assert found is not None
        assert found.symbol == "AAPL"

    def test_get_by_symbol_not_found(self, session):
        """Gibt None zurück bei unbekanntem Symbol."""
        repo = TickerRepository(session)
        assert repo.get_by_symbol("ZZZZ") is None

    def test_get_by_id(self, session, sample_ticker):
        """Findet Ticker anhand der ID."""
        repo = TickerRepository(session)
        found = repo.get_by_id(sample_ticker.ticker_id)
        assert found is not None
        assert found.symbol == "AAPL"

    def test_get_all_active(self, session, multiple_tickers):
        """Gibt nur aktive Ticker zurück (sortiert nach Symbol)."""
        repo = TickerRepository(session)
        active = repo.get_all_active()
        symbols = [t.symbol for t in active]
        assert "INACTIVE" not in symbols
        assert "AAPL" in symbols
        assert "MSFT" in symbols
        assert "SPY" in symbols
        # Alphabetisch sortiert
        assert symbols == sorted(symbols)

    def test_get_by_asset_type(self, session, multiple_tickers):
        """Filtert nach Asset-Typ."""
        repo = TickerRepository(session)
        stocks = repo.get_by_asset_type(AssetType.STOCK)
        symbols = [t.symbol for t in stocks]
        assert "AAPL" in symbols
        assert "MSFT" in symbols
        assert "SPY" not in symbols  # ist ETF

    def test_get_by_asset_type_includes_inactive(self, session, multiple_tickers):
        """active_only=False gibt auch inaktive zurück."""
        repo = TickerRepository(session)
        stocks = repo.get_by_asset_type(AssetType.STOCK, active_only=False)
        symbols = [t.symbol for t in stocks]
        assert "INACTIVE" in symbols

    def test_search_by_symbol(self, session, multiple_tickers):
        """Sucht Ticker nach Symbol-Muster."""
        repo = TickerRepository(session)
        results = repo.search("AAP")
        assert len(results) == 1
        assert results[0].symbol == "AAPL"

    def test_search_by_name(self, session, multiple_tickers):
        """Sucht Ticker nach Name."""
        repo = TickerRepository(session)
        results = repo.search("Microsoft")
        assert len(results) == 1
        assert results[0].symbol == "MSFT"

    def test_deactivate(self, session, sample_ticker):
        """Deaktiviert einen Ticker (Soft Delete)."""
        repo = TickerRepository(session)
        assert repo.deactivate(sample_ticker.ticker_id) is True
        session.refresh(sample_ticker)
        assert sample_ticker.is_active is False

    def test_deactivate_not_found(self, session):
        """Deaktivieren eines nicht-existierenden Tickers gibt False."""
        repo = TickerRepository(session)
        assert repo.deactivate(99999) is False

    def test_activate(self, session, sample_ticker):
        """Reaktiviert einen deaktivierten Ticker."""
        repo = TickerRepository(session)
        sample_ticker.is_active = False
        session.flush()

        assert repo.activate(sample_ticker.ticker_id) is True
        session.refresh(sample_ticker)
        assert sample_ticker.is_active is True

    def test_count(self, session, multiple_tickers):
        """Zählt alle Ticker (inkl. inaktive)."""
        repo = TickerRepository(session)
        assert repo.count() == 5
