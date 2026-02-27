# src/views/main_window.py
"""
Portfolio Manager - Main Window
PySide6 Desktop Application
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QStatusBar, QMenuBar, QMenu, QToolBar,
    QLabel, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QAction, QIcon, QFont, QColor, QPalette

from src.views.widgets.ticker_list import TickerListWidget, TickerItem
from src.views.widgets.market_data_panel import MarketDataPanel
from src.views.widgets.status_bar_widget import StatusBarWidget
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────
#  Application Stylesheet  (refined dark theme)
# ─────────────────────────────────────────────
APP_STYLESHEET = """
/* ── Global ── */
QMainWindow, QWidget {
    background-color: #0f1117;
    color: #e2e8f0;
    font-family: "Segoe UI", "SF Pro Display", "Helvetica Neue", sans-serif;
    font-size: 13px;
}

/* ── Menu Bar ── */
QMenuBar {
    background-color: #0f1117;
    color: #94a3b8;
    border-bottom: 1px solid #1e2433;
    padding: 2px 4px;
    font-size: 12px;
}
QMenuBar::item:selected {
    background-color: #1e2433;
    color: #e2e8f0;
    border-radius: 4px;
}
QMenu {
    background-color: #1a1f2e;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 20px;
    border-radius: 4px;
    color: #cbd5e0;
}
QMenu::item:selected {
    background-color: #2d3748;
    color: #e2e8f0;
}
QMenu::separator {
    height: 1px;
    background: #2d3748;
    margin: 4px 8px;
}

/* ── Toolbar ── */
QToolBar {
    background-color: #0f1117;
    border-bottom: 1px solid #1e2433;
    padding: 4px 8px;
    spacing: 6px;
}
QToolBar QToolButton {
    background: transparent;
    color: #94a3b8;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 500;
}
QToolBar QToolButton:hover {
    background-color: #1e2433;
    color: #e2e8f0;
}
QToolBar QToolButton:pressed {
    background-color: #2d3748;
}
QToolBar::separator {
    width: 1px;
    background: #1e2433;
    margin: 6px 4px;
}

/* ── Splitter ── */
QSplitter::handle {
    background-color: #1e2433;
    width: 2px;
}
QSplitter::handle:hover {
    background-color: #3b82f6;
}

/* ── Status Bar ── */
QStatusBar {
    background-color: #0a0d14;
    color: #64748b;
    border-top: 1px solid #1e2433;
    font-size: 11px;
    padding: 0 8px;
}
QStatusBar::item {
    border: none;
}

/* ── Scroll Bars ── */
QScrollBar:vertical {
    background: #0f1117;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #2d3748;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #4a5568;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #0f1117;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #2d3748;
    border-radius: 4px;
}

/* ── Frame / Panels ── */
QFrame#sidePanel {
    background-color: #0d1018;
    border-right: 1px solid #1e2433;
}
QFrame#mainPanel {
    background-color: #0f1117;
}

/* ── Labels ── */
QLabel#sectionTitle {
    color: #64748b;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    padding: 12px 16px 6px 16px;
}

/* ── Push Buttons ── */
QPushButton {
    background-color: #1e2433;
    color: #cbd5e0;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #2d3748;
    color: #e2e8f0;
    border-color: #4a5568;
}
QPushButton:pressed {
    background-color: #374151;
}
QPushButton#primaryBtn {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
}
QPushButton#primaryBtn:hover {
    background-color: #1d4ed8;
}
QPushButton#dangerBtn {
    background-color: transparent;
    color: #f87171;
    border-color: #7f1d1d;
}
QPushButton#dangerBtn:hover {
    background-color: #450a0a;
    border-color: #f87171;
}

/* ── Line Edit ── */
QLineEdit {
    background-color: #1a1f2e;
    color: #e2e8f0;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
    selection-background-color: #2563eb;
}
QLineEdit:focus {
    border-color: #3b82f6;
    background-color: #1e2433;
}

/* ── ComboBox ── */
QComboBox {
    background-color: #1a1f2e;
    color: #e2e8f0;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
    min-width: 100px;
}
QComboBox:hover {
    border-color: #4a5568;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #1a1f2e;
    border: 1px solid #2d3748;
    selection-background-color: #2d3748;
    color: #e2e8f0;
}

/* ── Table Widget ── */
QTableWidget {
    background-color: #0d1018;
    gridline-color: #1e2433;
    border: none;
    border-radius: 0;
    color: #cbd5e0;
    font-size: 12px;
    selection-background-color: #1e2d4d;
    alternate-background-color: #0f1219;
}
QTableWidget::item {
    padding: 6px 10px;
    border: none;
}
QTableWidget::item:selected {
    background-color: #1e2d4d;
    color: #93c5fd;
}
QHeaderView::section {
    background-color: #0a0d14;
    color: #64748b;
    border: none;
    border-bottom: 1px solid #1e2433;
    border-right: 1px solid #1e2433;
    padding: 8px 10px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}
QHeaderView::section:hover {
    background-color: #1e2433;
    color: #94a3b8;
}

/* ── Tab Widget ── */
QTabWidget::pane {
    border: none;
    background-color: #0f1117;
}
QTabBar::tab {
    background: transparent;
    color: #64748b;
    padding: 8px 18px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 12px;
    font-weight: 500;
}
QTabBar::tab:selected {
    color: #3b82f6;
    border-bottom-color: #3b82f6;
}
QTabBar::tab:hover:!selected {
    color: #94a3b8;
    border-bottom-color: #2d3748;
}

/* ── Date Edit ── */
QDateEdit {
    background-color: #1a1f2e;
    color: #e2e8f0;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
}
QDateEdit:focus {
    border-color: #3b82f6;
}
QDateEdit::drop-down {
    border: none;
    width: 20px;
}
QCalendarWidget {
    background-color: #1a1f2e;
    color: #e2e8f0;
}

/* ── Checkbox ── */
QCheckBox {
    color: #cbd5e0;
    font-size: 12px;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #4a5568;
    border-radius: 4px;
    background: #1a1f2e;
}
QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #2563eb;
    image: url(none);
}
QCheckBox::indicator:hover {
    border-color: #3b82f6;
}

/* ── Progress Bar ── */
QProgressBar {
    background-color: #1e2433;
    border: none;
    border-radius: 3px;
    height: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 3px;
}

/* ── Tooltip ── */
QToolTip {
    background-color: #1a1f2e;
    color: #e2e8f0;
    border: 1px solid #2d3748;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
}
"""


class MainWindow(QMainWindow):
    """
    Portfolio Manager - Hauptfenster

    Layout:
    ┌─────────────────────────────────────────────────────┐
    │  MenuBar                                            │
    │  ToolBar                                            │
    ├──────────────┬──────────────────────────────────────┤
    │              │                                      │
    │  Ticker-     │  MarketData Panel                    │
    │  Liste       │  (Chart + Tabelle + Analyse)         │
    │              │                                      │
    ├──────────────┴──────────────────────────────────────┤
    │  StatusBar                                          │
    └─────────────────────────────────────────────────────┘
    """

    def __init__(self, session=None):
        super().__init__()
        self.session = session
        self._setup_window()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_status_bar()
        self._setup_controllers()
        self._connect_signals()
        logger.info("MainWindow initialized")

    # ──────────────────────────────────────────
    #  Window Setup
    # ──────────────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle("Portfolio Manager")
        self.setMinimumSize(1200, 750)
        self.resize(1440, 900)
        self.setStyleSheet(APP_STYLESHEET)

        # Center on screen
        screen = self.screen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    # ──────────────────────────────────────────
    #  Menu Bar
    # ──────────────────────────────────────────

    def _setup_menu(self):
        menubar = self.menuBar()

        # ── Datei ──
        file_menu = menubar.addMenu("Datei")

        self.action_new_ticker = QAction("Neuer Ticker...", self)
        self.action_new_ticker.setShortcut("Ctrl+N")
        file_menu.addAction(self.action_new_ticker)

        file_menu.addSeparator()

        self.action_settings = QAction("Einstellungen...", self)
        self.action_settings.setShortcut("Ctrl+,")
        file_menu.addAction(self.action_settings)

        file_menu.addSeparator()

        self.action_quit = QAction("Beenden", self)
        self.action_quit.setShortcut("Ctrl+Q")
        self.action_quit.triggered.connect(self.close)
        file_menu.addAction(self.action_quit)

        # ── Daten ──
        data_menu = menubar.addMenu("Daten")

        self.action_import = QAction("Daten importieren...", self)
        self.action_import.setShortcut("Ctrl+I")
        data_menu.addAction(self.action_import)

        self.action_update_all = QAction("Alle Ticker aktualisieren", self)
        self.action_update_all.setShortcut("Ctrl+Shift+U")
        data_menu.addAction(self.action_update_all)

        data_menu.addSeparator()

        self.action_export = QAction("Daten exportieren...", self)
        self.action_export.setShortcut("Ctrl+E")
        data_menu.addAction(self.action_export)

        # ── Analyse ──
        analysis_menu = menubar.addMenu("Analyse")

        self.action_run_sma = QAction("SMA berechnen", self)
        analysis_menu.addAction(self.action_run_sma)

        self.action_run_macd = QAction("MACD berechnen", self)
        analysis_menu.addAction(self.action_run_macd)

        self.action_run_roc = QAction("ROC berechnen", self)
        analysis_menu.addAction(self.action_run_roc)

        analysis_menu.addSeparator()

        self.action_run_all = QAction("Alle Indikatoren berechnen", self)
        self.action_run_all.setShortcut("Ctrl+Shift+A")
        analysis_menu.addAction(self.action_run_all)

        # ── Ansicht ──
        view_menu = menubar.addMenu("Ansicht")

        self.action_toggle_sidebar = QAction("Seitenleiste ein-/ausblenden", self)
        self.action_toggle_sidebar.setShortcut("Ctrl+B")
        self.action_toggle_sidebar.setCheckable(True)
        self.action_toggle_sidebar.setChecked(True)
        view_menu.addAction(self.action_toggle_sidebar)

        view_menu.addSeparator()

        chart_type_menu = view_menu.addMenu("Chart-Typ")
        self.action_chart_candlestick = QAction("Candlestick", self)
        self.action_chart_candlestick.setCheckable(True)
        self.action_chart_candlestick.setChecked(True)
        chart_type_menu.addAction(self.action_chart_candlestick)

        self.action_chart_line = QAction("Linie", self)
        self.action_chart_line.setCheckable(True)
        chart_type_menu.addAction(self.action_chart_line)

        self.action_chart_bar = QAction("OHLC-Bar", self)
        self.action_chart_bar.setCheckable(True)
        chart_type_menu.addAction(self.action_chart_bar)

        # ── Hilfe ──
        help_menu = menubar.addMenu("Hilfe")

        self.action_about = QAction("Über Portfolio Manager", self)
        help_menu.addAction(self.action_about)

        self.action_docs = QAction("Dokumentation", self)
        help_menu.addAction(self.action_docs)

    # ──────────────────────────────────────────
    #  Toolbar
    # ──────────────────────────────────────────

    def _setup_toolbar(self):
        toolbar = QToolBar("Hauptleiste", self)
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setObjectName("mainToolbar")
        self.addToolBar(toolbar)

        # Import Button
        btn_import = toolbar.addAction("⬇  Import")
        btn_import.setToolTip("Marktdaten von EoD Historical Data importieren")

        # Update Button
        self.btn_update = toolbar.addAction("↻  Aktualisieren")
        self.btn_update.setToolTip("Alle Ticker auf den neuesten Stand bringen")
        self.btn_update.triggered.connect(self._open_update_dialog)

        toolbar.addSeparator()

        # Analysis Buttons
        btn_analyse = toolbar.addAction("∿  Indikatoren")
        btn_analyse.setToolTip("Indikatoren für aktiven Ticker berechnen")

        toolbar.addSeparator()

        # DB Status (right-aligned spacer)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        self._db_status_label = QLabel("● SQLite  ")
        self._db_status_label.setStyleSheet("color: #22c55e; font-size: 11px;")
        toolbar.addWidget(self._db_status_label)

    # ──────────────────────────────────────────
    #  Central Widget  (Splitter Layout)
    # ──────────────────────────────────────────

    def _setup_central_widget(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Splitter ──
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(2)
        layout.addWidget(self.splitter)

        # ── Left: Ticker List ──
        self.side_panel = QFrame()
        self.side_panel.setObjectName("sidePanel")
        self.side_panel.setFixedWidth(240)
        side_layout = QVBoxLayout(self.side_panel)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(0)

        # TickerListWidget (hat eigenen Header mit Suchfeld + Filter-Buttons)
        self.ticker_list = TickerListWidget()
        side_layout.addWidget(self.ticker_list)

        self.splitter.addWidget(self.side_panel)

        # ── Right: Market Data Panel ──
        self.main_panel = QFrame()
        self.main_panel.setObjectName("mainPanel")
        self.splitter.addWidget(self.main_panel)

        main_layout = QVBoxLayout(self.main_panel)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.market_data_panel = MarketDataPanel(session=self.session)
        main_layout.addWidget(self.market_data_panel)

        # Splitter proportions
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

    # ──────────────────────────────────────────
    #  Status Bar
    # ──────────────────────────────────────────

    def _setup_status_bar(self):
        self.status_widget = StatusBarWidget()
        self.statusBar().addWidget(self.status_widget, 1)
        self.statusBar().addPermanentWidget(
            QLabel("Portfolio Manager v0.1  "),
        )
        self.set_status("Bereit")

    # ──────────────────────────────────────────
    #  Controllers
    # ──────────────────────────────────────────

    def _setup_controllers(self):
        """Initialisiert die Controller-Schicht (Phase 5)."""
        self._data_controller = None
        self._analysis_controller = None

        if not self.session:
            logger.info("Kein DB-Session — Controller werden nicht initialisiert (Demo-Modus)")
            return

        try:
            from src.controllers.data_controller import DataController
            from src.controllers.analysis_controller import AnalysisController

            # DataController: DataTableWidget.dataEdited → DB mit Audit-Log
            self._data_controller = DataController(session=self.session, parent=self)
            self._data_controller.set_status_callback(self.set_status)
            self._data_controller.connect_table(self.market_data_panel.data_table)

            # AnalysisController: IndicatorsTab → AnalysisService → ChartWidget
            self._analysis_controller = AnalysisController(session=self.session, parent=self)
            self._analysis_controller.set_status_callback(self.set_status)
            self._analysis_controller.connect_ui(
                indicators_tab=self.market_data_panel.indicators_tab,
                chart_widget=self.market_data_panel.chart_widget,
            )

            logger.info("Controller initialisiert: DataController + AnalysisController")

        except Exception as e:
            logger.error(f"Controller-Initialisierung fehlgeschlagen: {e}", exc_info=True)

    # ──────────────────────────────────────────
    #  Signal Connections
    # ──────────────────────────────────────────

    def _connect_signals(self):
        # tickerSelected emittiert TickerItem → nur Symbol weitergeben
        self.ticker_list.tickerSelected.connect(
            lambda item: self._on_ticker_selected(item)
        )

        # Menu actions
        self.action_toggle_sidebar.triggered.connect(self._toggle_sidebar)
        self.action_import.triggered.connect(self._open_import_dialog)
        self.action_update_all.triggered.connect(self._open_update_dialog)
        self.action_about.triggered.connect(self._show_about)

        # data_loaded: AnalysisController-Kontext aktualisieren bei Datumsbereich-Änderung
        self.market_data_panel.data_loaded.connect(self._on_data_loaded)

    # ──────────────────────────────────────────
    #  Public API
    # ──────────────────────────────────────────

    def set_status(self, message: str, timeout_ms: int = 0):
        """Update status bar message."""
        self.status_widget.set_message(message)
        logger.debug(f"Status: {message}")

    def set_db_connected(self, connected: bool, db_type: str = "SQLite"):
        """Update database connection indicator."""
        if connected:
            self._db_status_label.setText(f"● {db_type}  ")
            self._db_status_label.setStyleSheet("color: #22c55e; font-size: 11px;")
        else:
            self._db_status_label.setText(f"○ Getrennt  ")
            self._db_status_label.setStyleSheet("color: #f87171; font-size: 11px;")

    # ──────────────────────────────────────────
    #  Slots
    # ──────────────────────────────────────────

    def _toggle_sidebar(self, checked: bool):
        self.side_panel.setVisible(checked)

    def _on_ticker_selected(self, item: TickerItem):
        """
        Slot: Ticker in der Watchlist ausgewählt.
        Aktualisiert MarketDataPanel und setzt den AnalysisController-Kontext.
        """
        self.market_data_panel.on_ticker_selected(item.symbol)

    def _on_data_loaded(self, symbol: str, bars_count: int):
        """
        Slot: MarketDataPanel hat Daten geladen (bei Ticker-Auswahl oder Datumsbereich-Änderung).
        Aktualisiert den AnalysisController-Kontext mit den neuen Bars.
        """
        if self._analysis_controller:
            bars = self.market_data_panel.chart_widget._bars
            self._analysis_controller.set_ticker_context(symbol, bars)
            logger.debug(f"AnalysisController-Kontext aktualisiert: {symbol} ({bars_count} Bars)")

    def _open_import_dialog(self):
        from src.views.dialogs.import_dialog import ImportDialog
        dialog = ImportDialog(session=self.session, parent=self)
        dialog.import_completed.connect(self._on_import_completed)
        dialog.exec()

    def _open_update_dialog(self):
        from src.views.dialogs.update_dialog import UpdateAllDialog
        dialog = UpdateAllDialog(session=self.session, parent=self)
        dialog.update_completed.connect(self._on_update_completed)
        dialog.exec()

    def _on_update_completed(self, total_tickers: int, total_inserted: int):
        self.set_status(
            f"Update abgeschlossen: {total_tickers} Ticker, {total_inserted} neue Datensätze"
        )
        self._reload_ticker_list()

    def _on_import_completed(self, symbol: str, count: int):
        self.set_status(f"Import abgeschlossen: {count} Datensätze für {symbol} importiert")
        self._reload_ticker_list()

    def _reload_ticker_list(self):
        """Ticker-Liste aus DB neu laden."""
        if not self.session:
            return
        try:
            from src.database.ticker_repository import TickerRepository
            from src.views.widgets.ticker_list import TickerItem
            repo = TickerRepository(self.session)
            tickers = repo.get_all_active()
            items = [
                TickerItem(
                    ticker_id  = t.ticker_id,
                    symbol     = t.symbol,
                    name       = t.name or "",
                    exchange   = t.exchange or "",
                    currency   = t.currency or "",
                    asset_type = t.asset_type.value if hasattr(t.asset_type, "value") else str(t.asset_type),
                    is_active  = t.is_active,
                )
                for t in tickers
            ]
            self.ticker_list.load_tickers(items)
        except Exception as e:
            from src.utils.logger import get_logger
            get_logger(__name__).error(f"Ticker-Liste konnte nicht geladen werden: {e}")

    def _show_about(self):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "Über Portfolio Manager",
            "<h3>Portfolio Manager</h3>"
            "<p>Version 0.1 — Phase 1</p>"
            "<p>Quantitatives Portfolio Management System</p>"
            "<p>Powered by EoD Historical Data · SQLAlchemy · PySide6</p>"
        )

    def closeEvent(self, event):
        logger.info("Application closing...")
        if self.session:
            self.session.close()
        super().closeEvent(event)
