# tests/test_controllers/test_analysis_controller.py
"""
Tests für AnalysisController.

Testet die Berechnungslogik (_compute) direkt, ohne Qt-UI.
Die UI-Integration (Button-Click, Tabelle befüllen) erfordert pytest-qt
und wird in test_widgets/ separat getestet.
"""

import pytest
import numpy as np
from datetime import date
from decimal import Decimal

from src.controllers.analysis_controller import AnalysisController
from src.database.processed_data_repository import ProcessedDataRepository
from src.views.widgets.chart_widget import OHLCVBar


class TestAnalysisControllerCompute:
    """Tests für die _compute-Methode des AnalysisController."""

    def _setup_controller(self, session, sample_ticker, sample_market_data):
        """Erstellt einen konfigurierten AnalysisController."""
        from src.services.analysis_service import AnalysisService

        controller = AnalysisController(session=session)
        service = AnalysisService(session)

        bars = service.load_bars(
            sample_ticker.ticker_id, date(2024, 1, 1), date(2024, 12, 31)
        )
        controller._current_symbol = sample_ticker.symbol
        controller._current_ticker_id = sample_ticker.ticker_id
        controller._current_bars = bars
        return controller, bars

    def test_compute_sma(self, session, sample_ticker, sample_market_data):
        """SMA-Berechnung über _compute."""
        controller, bars = self._setup_controller(session, sample_ticker, sample_market_data)

        result = controller._compute("SMA", 20)
        assert len(result) == 1
        assert result[0].name == "SMA 20"
        assert result[0].panel == "main"

        # Persistiert
        repo = ProcessedDataRepository(session)
        assert repo.count_by_ticker_indicator(sample_ticker.ticker_id, "SMA_20") > 0

    def test_compute_ema(self, session, sample_ticker, sample_market_data):
        """EMA-Berechnung über _compute."""
        controller, bars = self._setup_controller(session, sample_ticker, sample_market_data)

        result = controller._compute("EMA", 10)
        assert len(result) == 1
        assert result[0].name == "EMA 10"

        repo = ProcessedDataRepository(session)
        assert repo.count_by_ticker_indicator(sample_ticker.ticker_id, "EMA_10") > 0

    def test_compute_macd(self, session, sample_ticker, sample_market_data):
        """MACD-Berechnung gibt 2 Serien zurück."""
        controller, bars = self._setup_controller(session, sample_ticker, sample_market_data)

        result = controller._compute("MACD", 20)  # Periode wird bei MACD ignoriert
        assert len(result) == 2
        names = {s.name for s in result}
        assert "MACD" in names
        assert "Signal" in names

    def test_compute_roc(self, session, sample_ticker, sample_market_data):
        """ROC-Berechnung über _compute."""
        controller, bars = self._setup_controller(session, sample_ticker, sample_market_data)

        result = controller._compute("ROC", 10)
        assert len(result) == 1
        assert result[0].name == "ROC 10"
        assert result[0].panel == "sub"

    def test_compute_bollinger_not_implemented(self, session, sample_ticker, sample_market_data):
        """Bollinger Bands gibt leere Liste zurück (noch nicht implementiert)."""
        controller, bars = self._setup_controller(session, sample_ticker, sample_market_data)
        status_messages = []
        controller._status_callback = lambda msg: status_messages.append(msg)

        result = controller._compute("Bollinger Bands", 20)
        assert result == []
        assert any("nicht implementiert" in msg for msg in status_messages)

    def test_compute_unknown_indicator(self, session, sample_ticker, sample_market_data):
        """Unbekannter Indikator gibt leere Liste zurück."""
        controller, bars = self._setup_controller(session, sample_ticker, sample_market_data)
        status_messages = []
        controller._status_callback = lambda msg: status_messages.append(msg)

        result = controller._compute("FANTASY_INDICATOR", 20)
        assert result == []
        assert any("Unbekannter" in msg for msg in status_messages)


class TestAnalysisControllerContext:
    """Tests für Ticker-Kontext-Verwaltung."""

    def test_set_ticker_context(self, session, sample_ticker, sample_bars):
        """set_ticker_context setzt alle internen Felder."""
        controller = AnalysisController(session=session)
        controller.set_ticker_context("AAPL", sample_bars)

        assert controller._current_symbol == "AAPL"
        assert controller._current_ticker_id == sample_ticker.ticker_id
        assert len(controller._current_bars) == len(sample_bars)

    def test_set_ticker_context_unknown_symbol(self, session, sample_bars):
        """Unbekanntes Symbol → ticker_id bleibt None."""
        controller = AnalysisController(session=session)
        controller.set_ticker_context("UNKNOWN", sample_bars)

        assert controller._current_symbol == "UNKNOWN"
        assert controller._current_ticker_id is None
        assert len(controller._current_bars) == len(sample_bars)

    def test_compute_without_db_fallback(self, session, sample_bars):
        """Wenn ticker_id None → Berechnung ohne Persistierung (Demo-Modus)."""
        controller = AnalysisController(session=session)
        controller._current_symbol = "DEMO"
        controller._current_ticker_id = None
        controller._current_bars = sample_bars

        result = controller._compute("SMA", 20)
        assert len(result) == 1
        assert result[0].name == "SMA 20"

        # Nichts in DB
        repo = ProcessedDataRepository(session)
        indicators = repo.get_available_indicators(0)
        assert indicators == []
