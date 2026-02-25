# tests/test_services/test_analysis_service.py
"""
Tests für AnalysisService.

Testet:
  - load_bars() → OHLCVBar-Konvertierung aus DB
  - compute_and_store_sma/ema/macd/roc → Berechnung + DB-Persistierung
  - load_stored_indicator → Laden gespeicherter Indikatoren
  - delete-before-insert Verhalten
"""

import pytest
import numpy as np
from datetime import date
from decimal import Decimal

from src.services.analysis_service import AnalysisService
from src.database.processed_data_repository import ProcessedDataRepository
from src.views.widgets.chart_widget import OHLCVBar


class TestAnalysisService:
    """Tests für die zentrale Analyse-Service-Schicht."""

    # ──────────────────────────────────────────
    #  load_bars
    # ──────────────────────────────────────────

    def test_load_bars(self, session, sample_ticker, sample_market_data):
        """Lädt Marktdaten als OHLCVBar-Liste."""
        service = AnalysisService(session)
        bars = service.load_bars(
            sample_ticker.ticker_id,
            date(2024, 1, 2),
            date(2024, 12, 31),
        )
        assert len(bars) == len(sample_market_data)
        assert isinstance(bars[0], OHLCVBar)
        assert isinstance(bars[0].close, float)
        assert bars[0].date == sample_market_data[0].date

    def test_load_bars_empty(self, session, sample_ticker):
        """Gibt leere Liste zurück wenn keine Daten vorhanden."""
        service = AnalysisService(session)
        bars = service.load_bars(
            sample_ticker.ticker_id,
            date(2020, 1, 1),
            date(2020, 12, 31),
        )
        assert bars == []

    def test_resolve_ticker_id(self, session, sample_ticker):
        """Löst Symbol → ticker_id auf."""
        service = AnalysisService(session)
        assert service.resolve_ticker_id("AAPL") == sample_ticker.ticker_id
        assert service.resolve_ticker_id("UNKNOWN") is None

    # ──────────────────────────────────────────
    #  SMA
    # ──────────────────────────────────────────

    def test_compute_and_store_sma(self, session, sample_ticker, sample_market_data):
        """SMA berechnen und in DB speichern."""
        service = AnalysisService(session)
        bars = service.load_bars(
            sample_ticker.ticker_id,
            date(2024, 1, 1),
            date(2024, 12, 31),
        )

        series = service.compute_and_store_sma(
            sample_ticker.ticker_id, bars, period=20
        )

        # IndicatorSeries korrekt
        assert series.name == "SMA 20"
        assert series.panel == "main"
        assert len(series.values) == len(bars)
        # Erste 19 Werte sollten NaN sein
        assert np.isnan(series.values[0])
        assert not np.isnan(series.values[19])

        # In DB gespeichert
        repo = ProcessedDataRepository(session)
        count = repo.count_by_ticker_indicator(sample_ticker.ticker_id, "SMA_20")
        non_nan = int(np.sum(~np.isnan(series.values)))
        assert count == non_nan

    def test_sma_delete_before_insert(self, session, sample_ticker, sample_market_data):
        """Zweite SMA-Berechnung ersetzt die erste (delete-before-insert)."""
        service = AnalysisService(session)
        bars = service.load_bars(
            sample_ticker.ticker_id, date(2024, 1, 1), date(2024, 12, 31)
        )

        service.compute_and_store_sma(sample_ticker.ticker_id, bars, period=20)
        repo = ProcessedDataRepository(session)
        count1 = repo.count_by_ticker_indicator(sample_ticker.ticker_id, "SMA_20")

        # Zweite Berechnung → sollte gleiche Anzahl haben, nicht doppelt
        service.compute_and_store_sma(sample_ticker.ticker_id, bars, period=20)
        count2 = repo.count_by_ticker_indicator(sample_ticker.ticker_id, "SMA_20")
        assert count2 == count1

    # ──────────────────────────────────────────
    #  EMA
    # ──────────────────────────────────────────

    def test_compute_and_store_ema(self, session, sample_ticker, sample_market_data):
        """EMA berechnen und in DB speichern."""
        service = AnalysisService(session)
        bars = service.load_bars(
            sample_ticker.ticker_id, date(2024, 1, 1), date(2024, 12, 31)
        )

        series = service.compute_and_store_ema(
            sample_ticker.ticker_id, bars, period=10
        )

        assert series.name == "EMA 10"
        assert series.panel == "main"
        # Erste 9 Werte NaN, ab Index 9 gültig
        assert np.isnan(series.values[0])
        assert not np.isnan(series.values[9])

        repo = ProcessedDataRepository(session)
        count = repo.count_by_ticker_indicator(sample_ticker.ticker_id, "EMA_10")
        assert count > 0

    # ──────────────────────────────────────────
    #  MACD
    # ──────────────────────────────────────────

    def test_compute_and_store_macd(self, session, sample_ticker, sample_market_data):
        """MACD berechnen und in DB speichern."""
        service = AnalysisService(session)
        bars = service.load_bars(
            sample_ticker.ticker_id, date(2024, 1, 1), date(2024, 12, 31)
        )

        series_list = service.compute_and_store_macd(
            sample_ticker.ticker_id, bars
        )

        assert len(series_list) == 2
        assert series_list[0].name == "MACD"
        assert series_list[1].name == "Signal"
        assert series_list[0].panel == "sub"

        # In DB: MACD mit value + value_secondary
        repo = ProcessedDataRepository(session)
        count = repo.count_by_ticker_indicator(
            sample_ticker.ticker_id, "MACD_12_26_9"
        )
        assert count > 0

    # ──────────────────────────────────────────
    #  ROC
    # ──────────────────────────────────────────

    def test_compute_and_store_roc(self, session, sample_ticker, sample_market_data):
        """ROC berechnen und in DB speichern."""
        service = AnalysisService(session)
        bars = service.load_bars(
            sample_ticker.ticker_id, date(2024, 1, 1), date(2024, 12, 31)
        )

        series = service.compute_and_store_roc(
            sample_ticker.ticker_id, bars, period=10
        )

        assert series.name == "ROC 10"
        assert series.panel == "sub"
        # Erste 10 Werte sollten NaN sein
        assert np.isnan(series.values[0])
        assert not np.isnan(series.values[10])

        repo = ProcessedDataRepository(session)
        count = repo.count_by_ticker_indicator(sample_ticker.ticker_id, "ROC_10")
        assert count > 0

    # ──────────────────────────────────────────
    #  load_stored_indicator
    # ──────────────────────────────────────────

    def test_load_stored_indicator(self, session, sample_ticker, sample_market_data):
        """Gespeicherter Indikator kann als IndicatorSeries zurückgeladen werden."""
        service = AnalysisService(session)
        bars = service.load_bars(
            sample_ticker.ticker_id, date(2024, 1, 1), date(2024, 12, 31)
        )

        # SMA berechnen + speichern
        original = service.compute_and_store_sma(
            sample_ticker.ticker_id, bars, period=20
        )

        # Zurückladen
        loaded = service.load_stored_indicator(
            sample_ticker.ticker_id,
            "SMA_20",
            date(2024, 1, 1),
            date(2024, 12, 31),
        )
        assert loaded is not None
        assert loaded.name == "SMA 20"
        assert loaded.panel == "main"
        # Werte sollten übereinstimmen (nur nicht-NaN)
        non_nan_original = original.values[~np.isnan(original.values)]
        assert len(loaded.values) == len(non_nan_original)

    def test_load_stored_indicator_not_found(self, session, sample_ticker):
        """Gibt None zurück wenn kein gespeicherter Indikator existiert."""
        service = AnalysisService(session)
        result = service.load_stored_indicator(
            sample_ticker.ticker_id,
            "NONEXISTENT",
            date(2024, 1, 1),
            date(2024, 12, 31),
        )
        assert result is None

    # ──────────────────────────────────────────
    #  get_available_indicators
    # ──────────────────────────────────────────

    def test_get_available_indicators(self, session, sample_ticker, sample_market_data):
        """Gibt alle gespeicherten Indikator-Typen zurück."""
        service = AnalysisService(session)
        bars = service.load_bars(
            sample_ticker.ticker_id, date(2024, 1, 1), date(2024, 12, 31)
        )

        service.compute_and_store_sma(sample_ticker.ticker_id, bars, period=20)
        service.compute_and_store_roc(sample_ticker.ticker_id, bars, period=10)

        indicators = service.get_available_indicators(sample_ticker.ticker_id)
        assert "SMA_20" in indicators
        assert "ROC_10" in indicators


class TestComputeFunctions:
    """Tests für die reinen Berechnungsfunktionen (ohne DB)."""

    def test_sma_values(self, sample_bars):
        """SMA-Berechnung: Werte stimmen mit manuellem Durchschnitt überein."""
        from src.views.widgets.chart_widget import compute_sma

        series = compute_sma(sample_bars, period=5)
        closes = [b.close for b in sample_bars]

        # SMA(5) am Index 4 = Durchschnitt der ersten 5 Werte
        expected = sum(closes[:5]) / 5
        assert abs(series.values[4] - expected) < 1e-10

    def test_sma_nan_prefix(self, sample_bars):
        """SMA hat NaN-Werte vor dem ersten vollständigen Fenster."""
        from src.views.widgets.chart_widget import compute_sma

        series = compute_sma(sample_bars, period=20)
        assert all(np.isnan(series.values[i]) for i in range(19))
        assert not np.isnan(series.values[19])

    def test_roc_values(self, sample_bars):
        """ROC-Berechnung: Prozentualer Vergleich."""
        from src.views.widgets.chart_widget import compute_roc

        series = compute_roc(sample_bars, period=5)
        closes = [b.close for b in sample_bars]

        # ROC am Index 5 = (close[5] - close[0]) / close[0] * 100
        expected = (closes[5] - closes[0]) / closes[0] * 100
        assert abs(series.values[5] - expected) < 1e-10

    def test_macd_returns_two_series(self, sample_bars):
        """MACD gibt zwei IndicatorSeries zurück (MACD + Signal)."""
        from src.views.widgets.chart_widget import compute_macd

        result = compute_macd(sample_bars)
        assert len(result) == 2
        assert result[0].name == "MACD"
        assert result[1].name == "Signal"
        assert result[0].panel == "sub"

    def test_compute_with_short_data(self):
        """Berechnung mit weniger Bars als Periode gibt nur NaN."""
        from src.views.widgets.chart_widget import compute_sma

        short_bars = [
            OHLCVBar(date=date(2024, 1, i + 1), open=100, high=101,
                     low=99, close=100, volume=1000000, adj_close=100)
            for i in range(5)
        ]
        series = compute_sma(short_bars, period=20)
        assert all(np.isnan(v) for v in series.values)
