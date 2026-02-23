# src/views/dialogs/import_dialog.py
"""
Import Dialog – Lets the user import market data from EoD Historical Data.
"""

from datetime import date

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QDateEdit, QPushButton, QProgressBar, QTextEdit, QFrame,
    QComboBox, QCheckBox, QWidget
)
from PySide6.QtCore import Qt, Signal, QDate, QThread, QObject
from PySide6.QtGui import QFont

from src.utils.logger import get_logger

logger = get_logger(__name__)


DIALOG_STYLE = """
QDialog {
    background-color: #0f1117;
    color: #e2e8f0;
}
QLabel#dialogTitle {
    color: #e2e8f0;
    font-size: 16px;
    font-weight: 700;
}
QLabel#dialogSubtitle {
    color: #64748b;
    font-size: 12px;
}
QLabel {
    color: #cbd5e0;
    font-size: 12px;
}
QFrame#card {
    background: #0d1018;
    border: 1px solid #1e2433;
    border-radius: 8px;
}
QTextEdit {
    background: #0a0d14;
    color: #64748b;
    border: 1px solid #1e2433;
    border-radius: 6px;
    font-family: "Consolas", "Monaco", monospace;
    font-size: 11px;
    padding: 8px;
}
"""


class ImportWorker(QObject):
    """Runs import in background thread."""
    progress = Signal(int, str)
    finished = Signal(str, int)
    error = Signal(str)

    def __init__(self, symbol: str, start_date: date, end_date: date,
                 api_key: str, session=None):
        super().__init__()
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.api_key = api_key
        self.session = session

    def run(self):
        try:
            if self.session and self.api_key:
                from src.services.data_import import MarketDataImporter
                from src.database.ticker_repository import TickerRepository
                from src.database.market_data_repository import MarketDataRepository

                ticker_repo = TickerRepository(self.session)
                data_repo = MarketDataRepository(self.session)
                importer = MarketDataImporter(ticker_repo, data_repo, self.api_key)

                self.progress.emit(30, f"Lade Daten für {self.symbol}…")
                count = importer.import_data(self.symbol, self.start_date, self.end_date)
                self.progress.emit(100, "Fertig")
                self.finished.emit(self.symbol, count)
            else:
                # Demo mode
                import time
                self.progress.emit(20, "Verbinde mit EoD Historical Data…")
                time.sleep(0.5)
                self.progress.emit(60, f"Lade Daten für {self.symbol}…")
                time.sleep(0.5)
                self.progress.emit(90, "Speichere in Datenbank…")
                time.sleep(0.3)
                self.progress.emit(100, "Abgeschlossen")
                self.finished.emit(self.symbol, 252)

        except Exception as e:
            self.error.emit(str(e))


class ImportDialog(QDialog):
    """
    Dialog for importing market data from EoD Historical Data.

    Signals:
        import_completed(symbol, count): emitted when import finishes
    """

    import_completed = Signal(str, int)

    def __init__(self, session=None, parent=None, symbol: str = ""):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Daten importieren")
        self.setMinimumWidth(520)
        self.setStyleSheet(DIALOG_STYLE)
        self._thread = None
        self._worker = None
        self._setup_ui(symbol)

    def _setup_ui(self, symbol: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Marktdaten importieren")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        subtitle = QLabel("Daten von EoD Historical Data (eodhd.com) herunterladen")
        subtitle.setObjectName("dialogSubtitle")
        layout.addWidget(subtitle)

        # ── Card: Import Settings ──
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        # Symbol input
        row1 = QHBoxLayout()
        lbl_sym = QLabel("Symbol:")
        lbl_sym.setFixedWidth(90)
        row1.addWidget(lbl_sym)
        self.input_symbol = QLineEdit(symbol.upper())
        self.input_symbol.setPlaceholderText("z.B. AAPL, EURUSD, SPX.INDX")
        row1.addWidget(self.input_symbol)
        card_layout.addLayout(row1)

        # Exchange
        row2 = QHBoxLayout()
        lbl_ex = QLabel("Exchange:")
        lbl_ex.setFixedWidth(90)
        row2.addWidget(lbl_ex)
        self.combo_exchange = QComboBox()
        self.combo_exchange.addItems(["US", "XETRA", "LSE", "EUREX", "CC (Crypto)", "FOREX"])
        row2.addWidget(self.combo_exchange)
        card_layout.addLayout(row2)

        # Date range
        row3 = QHBoxLayout()
        lbl_dr = QLabel("Zeitraum:")
        lbl_dr.setFixedWidth(90)
        row3.addWidget(lbl_dr)

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addYears(-2))
        self.date_from.setFixedWidth(130)
        row3.addWidget(self.date_from)

        lbl_to = QLabel("bis")
        lbl_to.setStyleSheet("color: #64748b;")
        row3.addWidget(lbl_to)

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setFixedWidth(130)
        row3.addWidget(self.date_to)
        row3.addStretch()
        card_layout.addLayout(row3)

        # Options
        self.chk_adj = QCheckBox("Adjusted Close laden")
        self.chk_adj.setChecked(True)
        card_layout.addWidget(self.chk_adj)

        self.chk_overwrite = QCheckBox("Vorhandene Daten überschreiben")
        self.chk_overwrite.setChecked(False)
        card_layout.addWidget(self.chk_overwrite)

        layout.addWidget(card)

        # ── Progress ──
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_progress = QLabel("")
        self.lbl_progress.setStyleSheet("color: #64748b; font-size: 11px;")
        self.lbl_progress.setVisible(False)
        layout.addWidget(self.lbl_progress)

        # ── Log ──
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFixedHeight(100)
        self.log_output.setVisible(False)
        layout.addWidget(self.log_output)

        # ── Buttons ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_import = QPushButton("Importieren")
        self.btn_import.setObjectName("primaryBtn")
        self.btn_import.setFixedWidth(120)
        self.btn_import.clicked.connect(self._start_import)
        btn_row.addWidget(self.btn_import)

        layout.addLayout(btn_row)

    def _start_import(self):
        symbol = self.input_symbol.text().strip().upper()
        if not symbol:
            self.input_symbol.setFocus()
            return

        q_from = self.date_from.date()
        q_to = self.date_to.date()
        start_date = date(q_from.year(), q_from.month(), q_from.day())
        end_date = date(q_to.year(), q_to.month(), q_to.day())

        self.btn_import.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_progress.setVisible(True)
        self.log_output.setVisible(True)
        self.progress_bar.setValue(0)

        self._log(f"Starte Import: {symbol}  |  {start_date} → {end_date}")

        # Run in thread
        self._thread = QThread()
        self._worker = ImportWorker(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            api_key="",  # TODO: load from config
            session=self.session,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.start()

    def _on_progress(self, value: int, message: str):
        self.progress_bar.setValue(value)
        self.lbl_progress.setText(message)
        self._log(message)

    def _on_finished(self, symbol: str, count: int):
        msg = f"✓ {count:,} Datensätze für {symbol} importiert"
        self._log(msg)
        self.lbl_progress.setText(msg)
        self.lbl_progress.setStyleSheet("color: #22c55e; font-size: 11px;")
        self.btn_import.setEnabled(True)
        self.import_completed.emit(symbol, count)

    def _on_error(self, error: str):
        self._log(f"✗ Fehler: {error}")
        self.lbl_progress.setText(f"Fehler: {error}")
        self.lbl_progress.setStyleSheet("color: #f87171; font-size: 11px;")
        self.btn_import.setEnabled(True)

    def _log(self, message: str):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{ts}] {message}")
