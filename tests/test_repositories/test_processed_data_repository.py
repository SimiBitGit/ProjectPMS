# tests/test_repositories/test_processed_data_repository.py
"""
Tests für ProcessedDataRepository.
"""

import pytest
import json
from datetime import date
from decimal import Decimal

from src.database.processed_data_repository import ProcessedDataRepository
from src.models.processed_data import ProcessedData


class TestProcessedDataRepository:
    """Tests für ProcessedData CRUD-Operationen."""

    def _create_sma_records(self, session, ticker_id, num_days=10):
        """Hilfsmethode: Erstellt SMA_20-Testdaten."""
        records = []
        for i in range(num_days):
            records.append(ProcessedData(
                ticker_id=ticker_id,
                date=date(2024, 3, i + 1),
                indicator="SMA_20",
                value=Decimal(str(round(150 + i * 0.5, 6))),
                parameters=json.dumps({"period": 20, "method": "simple"}),
                version=1,
            ))
        session.add_all(records)
        session.flush()
        return records

    def test_bulk_create(self, session, sample_ticker):
        """Erstellt mehrere ProcessedData-Einträge."""
        repo = ProcessedDataRepository(session)
        records = [
            ProcessedData(
                ticker_id=sample_ticker.ticker_id,
                date=date(2024, 3, i),
                indicator="SMA_20",
                value=Decimal("150.123456"),
                parameters=json.dumps({"period": 20}),
                version=1,
            )
            for i in range(1, 6)
        ]
        count = repo.bulk_create(records)
        assert count == 5

    def test_get_by_ticker_indicator_daterange(self, session, sample_ticker):
        """Lädt Indikatoren im Datumsbereich."""
        repo = ProcessedDataRepository(session)
        self._create_sma_records(session, sample_ticker.ticker_id)

        results = repo.get_by_ticker_indicator_daterange(
            sample_ticker.ticker_id,
            "SMA_20",
            date(2024, 3, 1),
            date(2024, 3, 10),
        )
        assert len(results) == 10
        # Aufsteigend sortiert
        dates = [r.date for r in results]
        assert dates == sorted(dates)

    def test_get_by_ticker_indicator_date(self, session, sample_ticker):
        """Lädt einzelnen Indikator-Wert."""
        repo = ProcessedDataRepository(session)
        self._create_sma_records(session, sample_ticker.ticker_id)

        result = repo.get_by_ticker_indicator_date(
            sample_ticker.ticker_id, "SMA_20", date(2024, 3, 5)
        )
        assert result is not None
        assert result.indicator == "SMA_20"
        assert result.date == date(2024, 3, 5)

    def test_get_available_indicators(self, session, sample_ticker):
        """Gibt alle gespeicherten Indikator-Typen zurück."""
        repo = ProcessedDataRepository(session)

        # SMA erstellen
        self._create_sma_records(session, sample_ticker.ticker_id)

        # MACD erstellen
        session.add(ProcessedData(
            ticker_id=sample_ticker.ticker_id,
            date=date(2024, 3, 1),
            indicator="MACD_12_26_9",
            value=Decimal("1.5"),
            version=1,
        ))
        session.flush()

        indicators = repo.get_available_indicators(sample_ticker.ticker_id)
        assert "SMA_20" in indicators
        assert "MACD_12_26_9" in indicators
        assert len(indicators) == 2

    def test_get_latest(self, session, sample_ticker):
        """Gibt die neuesten N Werte zurück."""
        repo = ProcessedDataRepository(session)
        self._create_sma_records(session, sample_ticker.ticker_id)

        latest = repo.get_latest(sample_ticker.ticker_id, "SMA_20", n=3)
        assert len(latest) == 3
        # Absteigend sortiert
        dates = [r.date for r in latest]
        assert dates == sorted(dates, reverse=True)

    def test_delete_by_ticker_indicator(self, session, sample_ticker):
        """Löscht alle Daten für einen Indikator."""
        repo = ProcessedDataRepository(session)
        self._create_sma_records(session, sample_ticker.ticker_id)

        deleted = repo.delete_by_ticker_indicator(
            sample_ticker.ticker_id, "SMA_20"
        )
        assert deleted == 10

        # Prüfen, dass leer
        count = repo.count_by_ticker_indicator(sample_ticker.ticker_id, "SMA_20")
        assert count == 0

    def test_delete_by_ticker_daterange(self, session, sample_ticker):
        """Löscht ProcessedData im Datumsbereich."""
        repo = ProcessedDataRepository(session)
        self._create_sma_records(session, sample_ticker.ticker_id)

        deleted = repo.delete_by_ticker_daterange(
            sample_ticker.ticker_id, date(2024, 3, 1), date(2024, 3, 5)
        )
        assert deleted == 5

        remaining = repo.count_by_ticker_indicator(
            sample_ticker.ticker_id, "SMA_20"
        )
        assert remaining == 5

    def test_count_by_ticker_indicator(self, session, sample_ticker):
        """Zählt Datensätze für einen bestimmten Indikator."""
        repo = ProcessedDataRepository(session)
        self._create_sma_records(session, sample_ticker.ticker_id)

        count = repo.count_by_ticker_indicator(
            sample_ticker.ticker_id, "SMA_20"
        )
        assert count == 10

    def test_create_indicator_name(self):
        """Testet die Hilfsmethode für Indikator-Namen."""
        assert ProcessedData.create_indicator_name("SMA", period=20) == "SMA_20"
        assert ProcessedData.create_indicator_name("MACD", fast=12, slow=26, signal=9) == "MACD_12_26_9"
        assert ProcessedData.create_indicator_name("VWAP") == "VWAP"

    def test_version_isolation(self, session, sample_ticker):
        """Verschiedene Versionen des gleichen Indikators sind getrennt."""
        repo = ProcessedDataRepository(session)
        session.add(ProcessedData(
            ticker_id=sample_ticker.ticker_id,
            date=date(2024, 3, 1),
            indicator="SMA_20",
            value=Decimal("150.0"),
            version=1,
        ))
        session.add(ProcessedData(
            ticker_id=sample_ticker.ticker_id,
            date=date(2024, 3, 1),
            indicator="SMA_20",
            value=Decimal("155.0"),
            version=2,
        ))
        session.flush()

        v1 = repo.get_by_ticker_indicator_date(
            sample_ticker.ticker_id, "SMA_20", date(2024, 3, 1), version=1
        )
        v2 = repo.get_by_ticker_indicator_date(
            sample_ticker.ticker_id, "SMA_20", date(2024, 3, 1), version=2
        )
        assert float(v1.value) == 150.0
        assert float(v2.value) == 155.0
