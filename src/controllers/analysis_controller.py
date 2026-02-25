# src/controllers/analysis_controller.py
"""
AnalysisController — Steuerungsschicht für Indikator-Berechnungen.

Verbindet:
  IndicatorsTab (UI) → AnalysisService → ChartWidget.add_indicator()
                                        → IndicatorsTab.results_table

Workflow:
  1. User wählt Indikator + Periode im IndicatorsTab
  2. Klickt "Berechnen"
  3. Controller lädt Bars, berechnet via AnalysisService
  4. Ergebnis wird im Chart als Overlay angezeigt
  5. Ergebnis wird in processed_data persistiert
  6. Ergebnis-Tabelle im IndicatorsTab wird befüllt
"""

from datetime import date

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QTableWidgetItem
from sqlalchemy.orm import Session

from src.services.analysis_service import AnalysisService
from src.views.widgets.chart_widget import ChartWidget, IndicatorSeries, OHLCVBar
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AnalysisController(QObject):
    """
    Controller für Indikator-Berechnungen.

    Koordiniert IndicatorsTab ↔ AnalysisService ↔ ChartWidget.

    Usage:
        controller = AnalysisController(session=session)
        controller.connect_ui(
            indicators_tab=panel.indicators_tab,
            chart_widget=panel.chart_widget,
        )
        controller.set_status_callback(main_window.set_status)
    """

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._service = AnalysisService(session)
        self._indicators_tab = None
        self._chart_widget = None
        self._status_callback = None

        # Aktueller Kontext
        self._current_symbol: str | None = None
        self._current_ticker_id: int | None = None
        self._current_bars: list[OHLCVBar] = []

    def set_status_callback(self, callback):
        """Setzt eine Callback-Funktion für Status-Nachrichten."""
        self._status_callback = callback

    def connect_ui(self, indicators_tab, chart_widget: ChartWidget):
        """
        Verbindet UI-Komponenten mit diesem Controller.

        Args:
            indicators_tab: IndicatorsTab-Instanz (aus market_data_panel.py)
            chart_widget: ChartWidget-Instanz
        """
        self._indicators_tab = indicators_tab
        self._chart_widget = chart_widget

        # "Berechnen"-Button verbinden
        # IndicatorsTab hat btn_calc als direktes Attribut im ctrl_layout
        # Wir suchen den Button über die controls-Gruppe
        btn = indicators_tab.btn_calc
        btn.clicked.connect(self._on_calculate_clicked)

        logger.info("AnalysisController: UI-Komponenten verbunden")

    # ──────────────────────────────────────────
    #  Kontext setzen
    # ──────────────────────────────────────────

    def set_ticker_context(self, symbol: str, bars: list[OHLCVBar]):
        """
        Wird aufgerufen, wenn ein neuer Ticker geladen wird.
        Speichert Symbol + Bars für spätere Berechnungen.
        """
        self._current_symbol = symbol
        self._current_bars = bars

        # ticker_id auflösen
        self._current_ticker_id = self._service.resolve_ticker_id(symbol)
        if not self._current_ticker_id:
            logger.warning(f"Ticker-ID für '{symbol}' konnte nicht aufgelöst werden")

        logger.debug(
            f"AnalysisController: Kontext gesetzt — {symbol} "
            f"(ticker_id={self._current_ticker_id}, {len(bars)} Bars)"
        )

    # ──────────────────────────────────────────
    #  Slots
    # ──────────────────────────────────────────

    @Slot()
    def _on_calculate_clicked(self):
        """Slot für den 'Berechnen'-Button im IndicatorsTab."""
        if not self._current_symbol or not self._current_bars:
            self._set_status("Kein Ticker ausgewählt oder keine Daten geladen")
            return

        indicator = self._indicators_tab.combo_indicator.currentText()
        period = int(self._indicators_tab.combo_period.currentText())

        logger.info(f"Berechne {indicator}({period}) für {self._current_symbol}")
        self._set_status(f"Berechne {indicator}({period}) für {self._current_symbol}...")

        try:
            series_list = self._compute(indicator, period)
            if not series_list:
                return

            # Chart-Overlays hinzufügen
            for series in series_list:
                self._chart_widget.add_indicator(series)

            # Ergebnis-Tabelle im IndicatorsTab befüllen
            self._update_results_table(series_list)

            count = sum(int(not __import__("numpy").isnan(v)) for s in series_list for v in s.values)
            self._set_status(
                f"{indicator}({period}) berechnet: {count} Datenpunkte für {self._current_symbol}"
            )

        except Exception as e:
            logger.error(f"Fehler bei Indikator-Berechnung: {e}", exc_info=True)
            self._set_status(f"Fehler bei Berechnung: {e}")

    def _compute(self, indicator: str, period: int) -> list[IndicatorSeries]:
        """
        Führt die Berechnung durch und gibt IndicatorSeries-Liste zurück.
        Persistiert gleichzeitig in der DB, falls ticker_id bekannt.
        """
        bars = self._current_bars
        ticker_id = self._current_ticker_id

        # Berechnung (mit Persistierung wenn ticker_id vorhanden)
        if indicator == "SMA":
            if ticker_id:
                series = self._service.compute_and_store_sma(ticker_id, bars, period)
            else:
                from src.views.widgets.chart_widget import compute_sma
                series = compute_sma(bars, period)
            return [series]

        elif indicator == "EMA":
            if ticker_id:
                series = self._service.compute_and_store_ema(ticker_id, bars, period)
            else:
                # Fallback: EMA direkt berechnen ohne Persistierung
                import numpy as np
                closes = np.array([b.close for b in bars], dtype=float)
                ema_values = np.full_like(closes, np.nan)
                k = 2 / (period + 1)
                if len(closes) >= period:
                    ema_values[period - 1] = closes[:period].mean()
                    for i in range(period, len(closes)):
                        ema_values[i] = closes[i] * k + ema_values[i - 1] * (1 - k)
                series = IndicatorSeries(
                    name=f"EMA {period}", values=ema_values, panel="main", color="#1ABC9C"
                )
            return [series]

        elif indicator == "MACD":
            if ticker_id:
                return self._service.compute_and_store_macd(ticker_id, bars)
            else:
                from src.views.widgets.chart_widget import compute_macd
                return compute_macd(bars)

        elif indicator == "ROC":
            if ticker_id:
                series = self._service.compute_and_store_roc(ticker_id, bars, period)
            else:
                from src.views.widgets.chart_widget import compute_roc
                series = compute_roc(bars, period)
            return [series]

        elif indicator == "Bollinger Bands":
            # Bollinger Bands: noch nicht implementiert → Hinweis
            self._set_status("Bollinger Bands sind noch nicht implementiert")
            logger.warning("Bollinger Bands: noch nicht implementiert")
            return []

        else:
            self._set_status(f"Unbekannter Indikator: {indicator}")
            return []

    # ──────────────────────────────────────────
    #  Ergebnis-Tabelle
    # ──────────────────────────────────────────

    def _update_results_table(self, series_list: list[IndicatorSeries]):
        """Befüllt die results_table im IndicatorsTab mit den berechneten Werten."""
        if not self._indicators_tab:
            return

        import numpy as np

        table = self._indicators_tab.results_table
        table.setRowCount(0)

        bars = self._current_bars

        # Alle Serien in die Tabelle einfügen (nur nicht-NaN-Werte)
        rows = []
        for series in series_list:
            for i, val in enumerate(series.values):
                if not np.isnan(val):
                    rows.append((bars[i].date, series.name, val))

        # Nach Datum absteigend sortieren (neueste zuerst)
        rows.sort(key=lambda r: r[0], reverse=True)

        # Maximal 500 Zeilen anzeigen (Performance)
        display_rows = rows[:500]

        table.setRowCount(len(display_rows))
        for row_idx, (dt, name, val) in enumerate(display_rows):
            table.setItem(row_idx, 0, QTableWidgetItem(dt.isoformat()))
            table.setItem(row_idx, 1, QTableWidgetItem(name))
            table.setItem(row_idx, 2, QTableWidgetItem(f"{val:.6f}"))

    # ──────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────

    def _set_status(self, message: str):
        """Status-Nachricht an die UI weiterleiten."""
        if self._status_callback:
            self._status_callback(message)
