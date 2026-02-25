# tests/test_repositories/test_market_data_repository.py
"""
Tests für MarketDataRepository.
"""

import pytest
from datetime import date
from decimal import Decimal

from src.database.market_data_repository import MarketDataRepository
from src.models.market_data import MarketData, DataEditLog


class TestMarketDataRepository:
    """Tests für MarketData CRUD + Audit-Log."""

    def test_get_by_ticker_and_daterange(self, session, sample_ticker, sample_market_data):
        """Lädt Marktdaten im Datumsbereich."""
        repo = MarketDataRepository(session)
        records = repo.get_by_ticker_and_daterange(
            sample_ticker.ticker_id,
            date(2024, 1, 2),
            date(2024, 3, 31),
        )
        assert len(records) > 0
        # Aufsteigend sortiert
        dates = [r.date for r in records]
        assert dates == sorted(dates)
        # Alle im Bereich
        assert all(date(2024, 1, 2) <= r.date <= date(2024, 3, 31) for r in records)

    def test_get_by_ticker_and_date(self, session, sample_ticker, sample_market_data):
        """Lädt Marktdaten für ein einzelnes Datum."""
        repo = MarketDataRepository(session)
        first_date = sample_market_data[0].date
        record = repo.get_by_ticker_and_date(sample_ticker.ticker_id, first_date)
        assert record is not None
        assert record.date == first_date
        assert record.ticker_id == sample_ticker.ticker_id

    def test_get_by_ticker_and_date_not_found(self, session, sample_ticker, sample_market_data):
        """Gibt None zurück wenn kein Datensatz für Datum existiert."""
        repo = MarketDataRepository(session)
        record = repo.get_by_ticker_and_date(sample_ticker.ticker_id, date(2020, 1, 1))
        assert record is None

    def test_get_latest(self, session, sample_ticker, sample_market_data):
        """Gibt die neuesten N Datensätze zurück."""
        repo = MarketDataRepository(session)
        latest = repo.get_latest(sample_ticker.ticker_id, n=5)
        assert len(latest) == 5
        # Absteigend sortiert
        dates = [r.date for r in latest]
        assert dates == sorted(dates, reverse=True)

    def test_get_date_range(self, session, sample_ticker, sample_market_data):
        """Gibt den verfügbaren Datumsbereich zurück."""
        repo = MarketDataRepository(session)
        result = repo.get_date_range(sample_ticker.ticker_id)
        assert result is not None
        min_date, max_date = result
        assert min_date <= max_date
        assert min_date == sample_market_data[0].date
        assert max_date == sample_market_data[-1].date

    def test_get_date_range_empty(self, session, sample_ticker):
        """Gibt None zurück wenn keine Daten vorhanden."""
        repo = MarketDataRepository(session)
        # sample_ticker hat hier keine market_data
        result = repo.get_date_range(sample_ticker.ticker_id)
        assert result is None

    def test_bulk_create(self, session, sample_ticker):
        """Erstellt mehrere Datensätze auf einmal."""
        repo = MarketDataRepository(session)
        records = [
            MarketData(
                ticker_id=sample_ticker.ticker_id,
                date=date(2024, 6, i),
                close=Decimal("100.00"),
                source="test",
            )
            for i in range(3, 8)  # 5 Tage
        ]
        count = repo.bulk_create(records)
        assert count == 5

    def test_update_with_log(self, session, sample_ticker, sample_market_data):
        """Update mit Audit-Log."""
        repo = MarketDataRepository(session)
        record = sample_market_data[0]
        old_close = record.close

        updated = repo.update_with_log(
            market_data=record,
            field_name="close",
            new_value=Decimal("999.99"),
            edit_reason="Korrektur Testdaten",
        )

        assert float(updated.close) == 999.99

        # Audit-Log prüfen
        logs = session.query(DataEditLog).filter_by(data_id=record.data_id).all()
        assert len(logs) == 1
        log = logs[0]
        assert log.field_name == "close"
        assert log.old_value == str(old_close)
        assert log.new_value == "999.99"
        assert log.edit_reason == "Korrektur Testdaten"
        assert log.table_name == "market_data"

    def test_update_with_log_multiple_edits(self, session, sample_ticker, sample_market_data):
        """Mehrere Edits erzeugen mehrere Log-Einträge."""
        repo = MarketDataRepository(session)
        record = sample_market_data[0]

        repo.update_with_log(record, "close", Decimal("100.00"), "Edit 1")
        repo.update_with_log(record, "close", Decimal("200.00"), "Edit 2")
        repo.update_with_log(record, "volume", 999999, "Volume fix")

        logs = session.query(DataEditLog).filter_by(data_id=record.data_id).all()
        assert len(logs) == 3

    def test_delete_by_ticker_and_daterange(self, session, sample_ticker, sample_market_data):
        """Löscht Daten im Datumsbereich."""
        repo = MarketDataRepository(session)
        total_before = repo.count_by_ticker(sample_ticker.ticker_id)

        deleted = repo.delete_by_ticker_and_daterange(
            sample_ticker.ticker_id,
            date(2024, 1, 2),
            date(2024, 1, 15),
        )
        assert deleted > 0

        total_after = repo.count_by_ticker(sample_ticker.ticker_id)
        assert total_after == total_before - deleted

    def test_count_by_ticker(self, session, sample_ticker, sample_market_data):
        """Zählt Datensätze für einen Ticker."""
        repo = MarketDataRepository(session)
        count = repo.count_by_ticker(sample_ticker.ticker_id)
        assert count == len(sample_market_data)

    def test_source_filter(self, session, sample_ticker):
        """Filtert Marktdaten nach Quelle."""
        repo = MarketDataRepository(session)
        # Zwei Records mit verschiedenen Quellen am gleichen Tag
        session.add(MarketData(
            ticker_id=sample_ticker.ticker_id,
            date=date(2024, 7, 1),
            close=Decimal("100.00"),
            source="eodhd",
        ))
        session.add(MarketData(
            ticker_id=sample_ticker.ticker_id,
            date=date(2024, 7, 1),
            close=Decimal("100.50"),
            source="manual",
        ))
        session.flush()

        all_records = repo.get_by_ticker_and_daterange(
            sample_ticker.ticker_id, date(2024, 7, 1), date(2024, 7, 1)
        )
        assert len(all_records) == 2

        eodhd_only = repo.get_by_ticker_and_daterange(
            sample_ticker.ticker_id, date(2024, 7, 1), date(2024, 7, 1),
            source="eodhd",
        )
        assert len(eodhd_only) == 1
        assert eodhd_only[0].source == "eodhd"
