# src/views/widgets/market_data_panel.py
"""
Market Data Panel – Rechtes Hauptpanel des Portfolio Managers.

Koordiniert die echten Widgets:
  - ChartWidget     (chart_widget.py)  → load_data(symbol, bars: list[OHLCVBar])
  - DataTableWidget (data_table.py)    → load_data(symbol, rows: list[dict])
  - IndicatorsTab   (lokal)

Tabs: [Chart] [Tabelle] [Indikatoren]
"""

from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QDateEdit, QComboBox,
    QTableWidget, QFrame
)
from PySide6.QtCore import Qt, Signal, QDate, Slot

from src.views.widgets.chart_widget import ChartWidget, OHLCVBar
from src.views.widgets.data_table import DataTableWidget
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EmptyStateWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        icon = QLabel("⬡")
        icon.setStyleSheet("color: #1e2433; font-size: 64px;")
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)

        title = QLabel("Kein Ticker ausgewählt")
        title.setStyleSheet("color: #475569; font-size: 16px; font-weight: 600;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        hint = QLabel("Wähle einen Ticker aus der Watchlist\noder füge einen neuen hinzu.")
        hint.setStyleSheet("color: #334155; font-size: 13px;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)


class HeaderBar(QWidget):
    """Ticker-Info + Datumsbereich-Steuerung."""

    load_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #0a0d14; border-bottom: 1px solid #1e2433;")
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 16, 0)
        layout.setSpacing(16)

        self.lbl_symbol = QLabel("—")
        self.lbl_symbol.setStyleSheet(
            "color: #e2e8f0; font-size: 18px; font-weight: 700; letter-spacing: -0.5px;"
        )
        layout.addWidget(self.lbl_symbol)

        self.lbl_price = QLabel("")
        self.lbl_price.setStyleSheet("color: #22c55e; font-size: 14px; font-weight: 600;")
        layout.addWidget(self.lbl_price)

        self.lbl_change = QLabel("")
        self.lbl_change.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(self.lbl_change)

        layout.addStretch()

        lbl_von = QLabel("Von")
        lbl_von.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(lbl_von)

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addYears(-1))
        self.date_from.setFixedWidth(110)
        layout.addWidget(self.date_from)

        lbl_bis = QLabel("bis")
        lbl_bis.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(lbl_bis)

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setFixedWidth(110)
        layout.addWidget(self.date_to)

        for label, days in [("1M", 30), ("3M", 90), ("6M", 180), ("1J", 365), ("3J", 1095)]:
            btn = QPushButton(label)
            btn.setFixedSize(34, 26)
            btn.setStyleSheet(
                "QPushButton { background: transparent; color: #64748b; "
                "border: 1px solid #1e2433; border-radius: 4px; "
                "font-size: 11px; font-weight: 600; }"
                "QPushButton:hover { background: #1e2433; color: #94a3b8; }"
            )
            btn.clicked.connect(lambda _, d=days: self._set_quick_range(d))
            layout.addWidget(btn)

        layout.addSpacing(4)

        self.btn_load = QPushButton("Laden")
        self.btn_load.setObjectName("primaryBtn")
        self.btn_load.setFixedSize(72, 30)
        self.btn_load.clicked.connect(self.load_requested.emit)
        layout.addWidget(self.btn_load)

    def set_ticker(self, symbol: str, last_close: float = None, change_pct: float = None):
        self.lbl_symbol.setText(symbol)
        if last_close is not None:
            self.lbl_price.setText(f"{last_close:,.4f}")
            color = "#22c55e" if (change_pct or 0) >= 0 else "#f87171"
            sign  = "+" if (change_pct or 0) >= 0 else ""
            self.lbl_change.setText(f"{sign}{change_pct:.2f}%")
            self.lbl_change.setStyleSheet(f"color: {color}; font-size: 12px;")
        else:
            self.lbl_price.setText("")
            self.lbl_change.setText("")

    def _set_quick_range(self, days: int):
        self.date_to.setDate(QDate.currentDate())
        self.date_from.setDate(QDate.currentDate().addDays(-days))

    def get_date_range(self) -> tuple:
        qf = self.date_from.date()
        qt = self.date_to.date()
        return (
            date(qf.year(), qf.month(), qf.day()),
            date(qt.year(), qt.month(), qt.day()),
        )


class IndicatorsTab(QWidget):
    """Platzhalter für Analyse-Services (Phase 2)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        controls = QWidget()
        controls.setStyleSheet(
            "background: #0d1018; border: 1px solid #1e2433; border-radius: 8px;"
        )
        ctrl_layout = QHBoxLayout(controls)
        ctrl_layout.setContentsMargins(16, 10, 16, 10)
        ctrl_layout.setSpacing(12)

        lbl1 = QLabel("Indikator:")
        lbl1.setStyleSheet("color: #94a3b8; font-size: 12px;")
        ctrl_layout.addWidget(lbl1)
        self.combo_indicator = QComboBox()
        self.combo_indicator.addItems(["SMA", "EMA", "MACD", "ROC", "Bollinger Bands"])
        self.combo_indicator.setFixedWidth(160)
        ctrl_layout.addWidget(self.combo_indicator)

        lbl2 = QLabel("Periode:")
        lbl2.setStyleSheet("color: #94a3b8; font-size: 12px;")
        ctrl_layout.addWidget(lbl2)
        self.combo_period = QComboBox()
        self.combo_period.addItems(["5", "10", "20", "50", "100", "200"])
        self.combo_period.setCurrentText("20")
        self.combo_period.setFixedWidth(80)
        ctrl_layout.addWidget(self.combo_period)

        ctrl_layout.addStretch()

        btn_calc = QPushButton("Berechnen")
        btn_calc.setObjectName("primaryBtn")
        btn_calc.setFixedHeight(30)
        ctrl_layout.addWidget(btn_calc)
        layout.addWidget(controls)

        self.results_table = QTableWidget(0, 3)
        self.results_table.setHorizontalHeaderLabels(["Datum", "Indikator", "Wert"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setFrameShape(QFrame.NoFrame)
        self.results_table.setAlternatingRowColors(True)
        layout.addWidget(self.results_table)

        hint = QLabel("Wähle einen Indikator und klicke «Berechnen»")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: #334155; font-size: 13px;")
        layout.addWidget(hint)
        layout.addStretch()


class MarketDataPanel(QWidget):
    """
    Rechtes Hauptpanel – koordiniert HeaderBar, ChartWidget,
    DataTableWidget und IndicatorsTab.
    """

    def __init__(self, session=None, parent=None):
        super().__init__(parent)
        self.session = session
        self._current_ticker: str | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.empty_state = EmptyStateWidget()
        layout.addWidget(self.empty_state)

        self.content = QWidget()
        self.content.setVisible(False)
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.header = HeaderBar()
        self.header.load_requested.connect(self._load_data)
        content_layout.addWidget(self.header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        content_layout.addWidget(self.tabs, 1)

        # Tab 1: ChartWidget (bestehend, mit Volumen + Crosshair + Slider)
        self.chart_widget = ChartWidget()
        self.tabs.addTab(self.chart_widget, "Chart")

        # Tab 2: DataTableWidget (bestehend, mit Inline-Edit + CSV-Export)
        self.data_table = DataTableWidget()
        self.tabs.addTab(self.data_table, "Tabelle")

        # Tab 3: Indikatoren (Phase 2)
        self.indicators_tab = IndicatorsTab()
        self.tabs.addTab(self.indicators_tab, "Indikatoren")

        layout.addWidget(self.content, 1)

    # ──────────────────────────────────────────
    #  Slots
    # ──────────────────────────────────────────

    @Slot(str)
    def on_ticker_selected(self, symbol: str):
        """Wird von TickerListWidget.tickerSelected aufgerufen (via main_window)."""
        self._current_ticker = symbol
        self.empty_state.setVisible(False)
        self.content.setVisible(True)
        self.header.set_ticker(symbol)
        logger.info(f"Ticker selected in panel: {symbol}")
        self._load_data()

    def _load_data(self):
        if not self._current_ticker:
            return
        start_date, end_date = self.header.get_date_range()
        logger.info(f"Loading data for {self._current_ticker}: {start_date} → {end_date}")
        if self.session:
            self._load_from_db(start_date, end_date)
        else:
            self._load_demo()

    def _load_from_db(self, start_date: date, end_date: date):
        try:
            from src.database.ticker_repository import TickerRepository
            from src.database.market_data_repository import MarketDataRepository
            from decimal import Decimal

            ticker_repo = TickerRepository(self.session)
            ticker = ticker_repo.get_by_symbol(self._current_ticker)
            if not ticker:
                logger.warning(f"Ticker {self._current_ticker} nicht in DB gefunden")
                self._load_demo()
                return

            records = MarketDataRepository(self.session).get_by_ticker_and_daterange(
                ticker.ticker_id, start_date, end_date
            )

            bars: list[OHLCVBar] = []
            table_rows: list[dict] = []

            for r in records:
                # OHLCVBar für ChartWidget
                bars.append(OHLCVBar(
                    date      = r.date,
                    open      = float(r.open)      if r.open      else 0.0,
                    high      = float(r.high)       if r.high      else 0.0,
                    low       = float(r.low)        if r.low       else 0.0,
                    close     = float(r.close)      if r.close     else 0.0,
                    volume    = float(r.volume)     if r.volume    else 0.0,
                    adj_close = float(r.adj_close)  if r.adj_close else 0.0,
                ))
                # Dict für DataTableWidget
                table_rows.append({
                    "data_id":   r.data_id,
                    "date":      r.date,
                    "open":      r.open,
                    "high":      r.high,
                    "low":       r.low,
                    "close":     r.close,
                    "volume":    r.volume,
                    "adj_close": r.adj_close,
                    "source":    r.source or "",
                    "_edited":   set(),
                })

            # Widgets befüllen
            self.chart_widget.load_data(self._current_ticker, bars)
            self.data_table.load_data(self._current_ticker, table_rows)

            # Header-Kurs aktualisieren
            if bars:
                sorted_bars = sorted(bars, key=lambda b: b.date, reverse=True)
                last  = sorted_bars[0]
                prev  = sorted_bars[1] if len(sorted_bars) > 1 else None
                chg   = ((last.close - prev.close) / prev.close * 100) if prev and prev.close else None
                self.header.set_ticker(self._current_ticker, last.close, chg)

        except Exception as e:
            logger.error(f"Fehler beim DB-Laden: {e}", exc_info=True)
            self._load_demo()

    def _load_demo(self):
        """Demo-Modus: ChartWidget mit zufälligen Bars befüllen."""
        import random
        from datetime import timedelta

        bars: list[OHLCVBar] = []
        price = 185.0
        d = date.today() - timedelta(days=365)
        while d <= date.today():
            if d.weekday() < 5:
                o = round(price + random.uniform(-3, 3), 4)
                h = round(o + random.uniform(0, 5), 4)
                l = round(o - random.uniform(0, 5), 4)
                c = round(l + random.uniform(0, h - l), 4)
                price = c
                bars.append(OHLCVBar(
                    date=d, open=o, high=h, low=l, close=c,
                    volume=random.randint(20_000_000, 80_000_000),
                    adj_close=c,
                ))
            d += timedelta(days=1)

        symbol = self._current_ticker or "DEMO"
        self.chart_widget.load_data(symbol, bars)

        # DataTableWidget Demo
        table_rows = [{
            "data_id":   i,
            "date":      b.date,
            "open":      b.open,
            "high":      b.high,
            "low":       b.low,
            "close":     b.close,
            "volume":    int(b.volume),
            "adj_close": b.adj_close,
            "source":    "demo",
            "_edited":   set(),
        } for i, b in enumerate(reversed(bars))]
        self.data_table.load_data(symbol, table_rows)
