# src/controllers/analysis_controller.py
"""
AnalysisController — Steuerungsschicht für Indikator-Berechnungen.

Features:
  - Berechnen: Indikator + Periode → Chart-Overlay + DB-Persistierung
  - Entfernen: Einzelner Indikator oder alle aus Chart + Tab entfernen
  - Auto-Recompute: Bei Ticker-Wechsel werden aktive Indikatoren automatisch
    für das neue Underlying neu berechnet
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QTableWidgetItem
from sqlalchemy.orm import Session

from src.services.analysis_service import AnalysisService
from src.views.widgets.chart_widget import ChartWidget, IndicatorSeries, OHLCVBar
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────
#  Datenklasse für aktive Indikatoren
# ──────────────────────────────────────────

@dataclass
class ActiveIndicator:
    """Beschreibt einen aktiven Indikator (für Tracking + Recompute)."""
    key: str               # Eindeutiger Schlüssel, z.B. "SMA_20", "MACD_12_26_9"
    indicator_type: str    # z.B. "SMA", "EMA", "MACD", "ROC"
    period: int            # z.B. 20 (bei MACD wird dies ignoriert)
    display_name: str      # z.B. "SMA 20"
    color: str             # Farbe im Chart
    series_names: list[str] = field(default_factory=list)  # z.B. ["MACD", "Signal"]


class AnalysisController(QObject):
    """
    Controller für Indikator-Berechnungen.

    Koordiniert IndicatorsTab ↔ AnalysisService ↔ ChartWidget.
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

        # Aktive Indikatoren (für Tracking + Auto-Recompute)
        self._active_indicators: list[ActiveIndicator] = []

    def set_status_callback(self, callback):
        """Setzt eine Callback-Funktion für Status-Nachrichten."""
        self._status_callback = callback

    def connect_ui(self, indicators_tab, chart_widget: ChartWidget):
        """Verbindet UI-Komponenten mit diesem Controller."""
        self._indicators_tab = indicators_tab
        self._chart_widget = chart_widget

        # "Berechnen"-Button
        indicators_tab.btn_calc.clicked.connect(self._on_calculate_clicked)

        # Entfernen-Signale (Tab)
        indicators_tab.indicatorRemoveRequested.connect(self._on_remove_indicator)
        indicators_tab.clearAllRequested.connect(self._on_clear_all)

        # Entfernen-Signal (Chart — Delete-Taste)
        chart_widget.indicatorRemoved.connect(self._on_indicator_removed_from_chart)

        logger.info("AnalysisController: UI-Komponenten verbunden")

    # ──────────────────────────────────────────
    #  Kontext setzen (Ticker-Wechsel)
    # ──────────────────────────────────────────

    def set_ticker_context(self, symbol: str, bars: list[OHLCVBar]):
        """
        Wird aufgerufen, wenn ein neuer Ticker geladen wird.
        Speichert Symbol + Bars und berechnet aktive Indikatoren neu.
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

        # Auto-Recompute: Aktive Indikatoren für neues Underlying neu berechnen
        if self._active_indicators and bars:
            self._recompute_active_indicators()

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
        period = self._indicators_tab.spin_period.value()

        # Duplikat-Check
        key = self._make_key(indicator, period)
        if any(a.key == key for a in self._active_indicators):
            self._set_status(f"{indicator}({period}) ist bereits aktiv")
            return

        logger.info(f"Berechne {indicator}({period}) für {self._current_symbol}")
        self._set_status(f"Berechne {indicator}({period}) für {self._current_symbol}...")

        try:
            series_list = self._compute(indicator, period)
            if not series_list:
                return

            # Chart-Overlays hinzufügen
            for series in series_list:
                self._chart_widget.add_indicator(series)

            # Aktiven Indikator tracken
            active = ActiveIndicator(
                key=key,
                indicator_type=indicator,
                period=period,
                display_name=self._make_display_name(indicator, period),
                color=series_list[0].color or "#F5A623",
                series_names=[s.name for s in series_list],
            )
            self._active_indicators.append(active)

            # UI aktualisieren
            self._indicators_tab.add_active_indicator(
                key=active.key,
                display_name=active.display_name,
                color=active.color,
            )
            self._update_results_table()

            count = sum(int(not np.isnan(v)) for s in series_list for v in s.values)
            self._set_status(
                f"{active.display_name} berechnet: {count} Datenpunkte für {self._current_symbol}"
            )

        except Exception as e:
            logger.error(f"Fehler bei Indikator-Berechnung: {e}", exc_info=True)
            self._set_status(f"Fehler bei Berechnung: {e}")

    @Slot(str)
    def _on_remove_indicator(self, key: str):
        """Entfernt einen einzelnen Indikator aus Chart + Tab."""
        active = next((a for a in self._active_indicators if a.key == key), None)
        if not active:
            return

        # Aus Chart entfernen (alle zugehörigen Serien)
        for name in active.series_names:
            self._chart_widget.remove_indicator(name)

        # Aus Tracking entfernen
        self._active_indicators = [a for a in self._active_indicators if a.key != key]

        # Aus UI entfernen
        self._indicators_tab.remove_active_indicator(key)

        # Ergebnis-Tabelle aktualisieren
        self._update_results_table()

        logger.info(f"Indikator entfernt: {active.display_name}")
        self._set_status(f"{active.display_name} entfernt")

    @Slot()
    def _on_clear_all(self):
        """Entfernt alle Indikatoren aus Chart + Tab."""
        self._chart_widget.clear_indicators()
        self._active_indicators.clear()
        self._indicators_tab.clear_active_indicators()
        self._indicators_tab.results_table.setRowCount(0)

        logger.info("Alle Indikatoren entfernt")
        self._set_status("Alle Indikatoren entfernt")

    @Slot(str)
    def _on_indicator_removed_from_chart(self, series_name: str):
        """
        Wird aufgerufen, wenn ein Indikator im Chart per Delete-Taste entfernt wird.
        Findet den zugehörigen ActiveIndicator und räumt Tab + Tracking auf.
        """
        # Finde den ActiveIndicator, der diese Serie enthält
        active = next(
            (a for a in self._active_indicators if series_name in a.series_names),
            None,
        )
        if not active:
            return

        # Bei MACD: Auch die zweite Serie (Signal) aus dem Chart entfernen
        for name in active.series_names:
            if name != series_name:
                self._chart_widget.remove_indicator(name)

        # Aus Tracking + Tab entfernen
        self._active_indicators = [a for a in self._active_indicators if a.key != active.key]
        self._indicators_tab.remove_active_indicator(active.key)
        self._update_results_table()

        self._set_status(f"{active.display_name} entfernt")

    # ──────────────────────────────────────────
    #  Auto-Recompute bei Ticker-Wechsel
    # ──────────────────────────────────────────

    def _recompute_active_indicators(self):
        """Berechnet alle aktiven Indikatoren für das neue Underlying neu."""
        if not self._active_indicators:
            return

        indicators_to_recompute = list(self._active_indicators)
        logger.info(
            f"Auto-Recompute: {len(indicators_to_recompute)} Indikatoren "
            f"für {self._current_symbol}"
        )

        # Chart-Overlays entfernen (werden neu gezeichnet)
        self._chart_widget.clear_indicators()

        for active in indicators_to_recompute:
            try:
                series_list = self._compute(active.indicator_type, active.period)
                if not series_list:
                    continue

                # Farbe beibehalten
                for i, series in enumerate(series_list):
                    if i == 0:
                        series.color = active.color

                # Chart-Overlay hinzufügen
                for series in series_list:
                    self._chart_widget.add_indicator(series)

                # series_names aktualisieren
                active.series_names = [s.name for s in series_list]

            except Exception as e:
                logger.error(
                    f"Auto-Recompute fehlgeschlagen für {active.display_name}: {e}",
                    exc_info=True,
                )

        # Ergebnis-Tabelle aktualisieren
        self._update_results_table()

        self._set_status(
            f"{len(indicators_to_recompute)} Indikatoren neu berechnet für {self._current_symbol}"
        )

    # ──────────────────────────────────────────
    #  Berechnung
    # ──────────────────────────────────────────

    def _compute(self, indicator: str, period: int) -> list[IndicatorSeries]:
        """
        Führt die Berechnung durch und gibt IndicatorSeries-Liste zurück.
        Persistiert gleichzeitig in der DB, falls ticker_id bekannt.
        """
        bars = self._current_bars
        ticker_id = self._current_ticker_id

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
            self._set_status("Bollinger Bands sind noch nicht implementiert")
            logger.warning("Bollinger Bands: noch nicht implementiert")
            return []

        else:
            self._set_status(f"Unbekannter Indikator: {indicator}")
            return []

    # ──────────────────────────────────────────
    #  Ergebnis-Tabelle
    # ──────────────────────────────────────────

    def _update_results_table(self):
        """
        Befüllt die results_table im IndicatorsTab mit den Werten
        aller aktuell aktiven Indikatoren (aus dem Chart).
        """
        if not self._indicators_tab:
            return

        table = self._indicators_tab.results_table
        table.setRowCount(0)

        bars = self._current_bars
        if not bars:
            return

        # Alle aktiven Indikatoren aus dem Chart holen
        chart_indicators = self._chart_widget._indicators

        rows = []
        for series in chart_indicators:
            for i, val in enumerate(series.values):
                if i < len(bars) and not np.isnan(val):
                    rows.append((bars[i].date, series.name, val))

        rows.sort(key=lambda r: r[0], reverse=True)

        display_rows = rows[:500]
        table.setRowCount(len(display_rows))
        for row_idx, (dt, name, val) in enumerate(display_rows):
            table.setItem(row_idx, 0, QTableWidgetItem(dt.isoformat()))
            table.setItem(row_idx, 1, QTableWidgetItem(name))
            table.setItem(row_idx, 2, QTableWidgetItem(f"{val:.6f}"))

    # ──────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _make_key(indicator: str, period: int) -> str:
        """Erzeugt einen eindeutigen Schlüssel für einen Indikator."""
        if indicator == "MACD":
            return "MACD_12_26_9"
        return f"{indicator}_{period}"

    @staticmethod
    def _make_display_name(indicator: str, period: int) -> str:
        """Erzeugt einen lesbaren Anzeigenamen."""
        if indicator == "MACD":
            return "MACD (12/26/9)"
        return f"{indicator} {period}"

    def _set_status(self, message: str):
        """Status-Nachricht an die UI weiterleiten."""
        if self._status_callback:
            self._status_callback(message)
