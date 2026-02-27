# src/views/dialogs/update_dialog.py
"""
Update-Dialog — Aktualisiert alle aktiven Ticker auf den neuesten Stand.

Verwendet MarketDataImporter.update_to_today() in einem QThread-Background-Worker
mit Live-Fortschrittsanzeige pro Ticker.
"""

from datetime import date, timedelta

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QFrame, QSpinBox, QCheckBox, QWidget
)
from PySide6.QtCore import Qt, Signal, QThread, QObject

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


# ──────────────────────────────────────────
#  Background Worker
# ──────────────────────────────────────────

class UpdateWorker(QObject):
    """
    Führt das Update aller aktiven Ticker in einem Background-Thread aus.

    Signale:
        ticker_progress(current, total, symbol, status_text)
        ticker_done(symbol, inserted, updated, errors_count)
        all_finished(total_tickers, total_inserted, total_updated, total_errors)
        error(error_message)
    """
    ticker_progress = Signal(int, int, str, str)
    ticker_done = Signal(str, int, int, int)
    all_finished = Signal(int, int, int, int)
    error = Signal(str)

    def __init__(self, session, lookback_days: int = 7, force_refresh: bool = False):
        super().__init__()
        self.session = session
        self.lookback_days = lookback_days
        self.force_refresh = force_refresh
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            from src.services.data_import import MarketDataImporter
            from src.database.ticker_repository import TickerRepository

            # Importer erstellen
            importer = MarketDataImporter.from_config(self.session)
            ticker_repo = TickerRepository(self.session)

            # Alle aktiven Ticker laden
            active_tickers = ticker_repo.get_all_active()
            if not active_tickers:
                self.error.emit("Keine aktiven Ticker in der Datenbank gefunden.")
                return

            total = len(active_tickers)
            start_date = date.today() - timedelta(days=self.lookback_days)
            end_date = date.today()

            total_inserted = 0
            total_updated = 0
            total_errors = 0

            for idx, ticker in enumerate(active_tickers, 1):
                if self._cancelled:
                    self.error.emit(f"Abgebrochen nach {idx - 1}/{total} Ticker.")
                    return

                symbol = ticker.symbol
                self.ticker_progress.emit(idx, total, symbol, f"Lade {symbol}…")

                try:
                    result = importer.import_ticker(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        force_refresh=self.force_refresh,
                    )

                    inserted = result.get("inserted", 0)
                    updated = result.get("updated", 0)
                    errors = len(result.get("errors", []))

                    total_inserted += inserted
                    total_updated += updated
                    total_errors += errors

                    self.ticker_done.emit(symbol, inserted, updated, errors)

                except Exception as exc:
                    logger.error(f"Fehler beim Update von {symbol}: {exc}", exc_info=True)
                    self.ticker_done.emit(symbol, 0, 0, 1)
                    total_errors += 1

            self.all_finished.emit(total, total_inserted, total_updated, total_errors)

        except ValueError as exc:
            # z.B. API-Key nicht gesetzt
            self.error.emit(str(exc))
        except Exception as exc:
            logger.error(f"Update-Worker Fehler: {exc}", exc_info=True)
            self.error.emit(f"Unerwarteter Fehler: {exc}")


# ──────────────────────────────────────────
#  Dialog
# ──────────────────────────────────────────

class UpdateAllDialog(QDialog):
    """
    Dialog zum Aktualisieren aller aktiven Ticker.

    Signale:
        update_completed(total_tickers, total_inserted): nach erfolgreichem Abschluss
    """

    update_completed = Signal(int, int)

    def __init__(self, session=None, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Alle Ticker aktualisieren")
        self.setMinimumWidth(560)
        self.setMinimumHeight(400)
        self.setStyleSheet(DIALOG_STYLE)
        self._thread = None
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Alle Ticker aktualisieren")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Lädt fehlende Marktdaten für alle aktiven Ticker von EoD Historical Data"
        )
        subtitle.setObjectName("dialogSubtitle")
        layout.addWidget(subtitle)

        # ── Settings Card ──
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        # Lookback-Tage
        row1 = QHBoxLayout()
        lbl_lookback = QLabel("Lookback-Tage:")
        lbl_lookback.setFixedWidth(120)
        lbl_lookback.setToolTip(
            "Wie viele Tage zurück geprüft wird.\n"
            "7 reicht für normale Wochentags-Updates.\n"
            "Höher setzen nach längeren Pausen."
        )
        row1.addWidget(lbl_lookback)

        self.spin_lookback = QSpinBox()
        self.spin_lookback.setRange(1, 365)
        self.spin_lookback.setValue(7)
        self.spin_lookback.setFixedWidth(80)
        row1.addWidget(self.spin_lookback)
        row1.addStretch()
        card_layout.addLayout(row1)

        # Cache ignorieren
        self.chk_force = QCheckBox("Cache ignorieren (force refresh)")
        self.chk_force.setChecked(False)
        card_layout.addWidget(self.chk_force)

        # Ticker-Anzahl
        self.lbl_ticker_count = QLabel("")
        self.lbl_ticker_count.setStyleSheet("color: #94a3b8; font-size: 11px;")
        card_layout.addWidget(self.lbl_ticker_count)
        self._update_ticker_count()

        layout.addWidget(card)

        # ── Progress ──
        self.lbl_current = QLabel("")
        self.lbl_current.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 500;")
        layout.addWidget(self.lbl_current)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        # ── Log ──
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFixedHeight(150)
        layout.addWidget(self.log_output)

        # ── Buttons ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.btn_cancel)

        self.btn_start = QPushButton("Aktualisieren starten")
        self.btn_start.setObjectName("primaryBtn")
        self.btn_start.setFixedWidth(180)
        self.btn_start.clicked.connect(self._start_update)
        btn_row.addWidget(self.btn_start)

        layout.addLayout(btn_row)

    def _update_ticker_count(self):
        """Zeigt die Anzahl aktiver Ticker an."""
        if not self.session:
            self.lbl_ticker_count.setText("Kein DB-Zugang (Demo-Modus)")
            return
        try:
            from src.database.ticker_repository import TickerRepository
            repo = TickerRepository(self.session)
            count = len(repo.get_all_active())
            self.lbl_ticker_count.setText(f"{count} aktive Ticker werden aktualisiert")
        except Exception:
            self.lbl_ticker_count.setText("Ticker-Anzahl konnte nicht ermittelt werden")

    # ──────────────────────────────────────────
    #  Start / Cancel
    # ──────────────────────────────────────────

    def _start_update(self):
        if not self.session:
            self._log("Fehler: Keine Datenbankverbindung.")
            return

        self.btn_start.setEnabled(False)
        self.spin_lookback.setEnabled(False)
        self.chk_force.setEnabled(False)
        self.progress_bar.setValue(0)

        lookback = self.spin_lookback.value()
        force = self.chk_force.isChecked()

        self._log(f"Starte Update (Lookback: {lookback} Tage, Force: {force})")

        # Worker in Background-Thread
        self._thread = QThread()
        self._worker = UpdateWorker(
            session=self.session,
            lookback_days=lookback,
            force_refresh=force,
        )
        self._worker.moveToThread(self._thread)

        # Signale verbinden
        self._thread.started.connect(self._worker.run)
        self._worker.ticker_progress.connect(self._on_ticker_progress)
        self._worker.ticker_done.connect(self._on_ticker_done)
        self._worker.all_finished.connect(self._on_all_finished)
        self._worker.error.connect(self._on_error)

        # Thread-Cleanup
        self._worker.all_finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)

        self._thread.start()

    def _on_cancel(self):
        if self._worker and self._thread and self._thread.isRunning():
            self._worker.cancel()
            self._log("Abbruch angefordert… (warte auf laufenden Ticker)")
            self.btn_cancel.setEnabled(False)
        else:
            self.reject()

    # ──────────────────────────────────────────
    #  Worker Slots
    # ──────────────────────────────────────────

    def _on_ticker_progress(self, current: int, total: int, symbol: str, status: str):
        pct = int((current - 1) / total * 100)
        self.progress_bar.setValue(pct)
        self.lbl_current.setText(f"[{current}/{total}]  {status}")

    def _on_ticker_done(self, symbol: str, inserted: int, updated: int, errors: int):
        parts = []
        if inserted:
            parts.append(f"+{inserted} neu")
        if updated:
            parts.append(f"~{updated} aktualisiert")
        if errors:
            parts.append(f"✗ {errors} Fehler")
        if not parts:
            parts.append("keine neuen Daten")

        status = ", ".join(parts)
        icon = "✓" if errors == 0 else "⚠"
        self._log(f"  {icon} {symbol}: {status}")

    def _on_all_finished(self, total: int, inserted: int, updated: int, errors: int):
        self.progress_bar.setValue(100)
        self.lbl_current.setText("Aktualisierung abgeschlossen")
        self.lbl_current.setStyleSheet(
            "color: #22c55e; font-size: 12px; font-weight: 500;"
        )

        summary = (
            f"Fertig: {total} Ticker verarbeitet — "
            f"{inserted} eingefügt, {updated} aktualisiert"
        )
        if errors:
            summary += f", {errors} Fehler"
        self._log(f"\n{summary}")

        self.btn_start.setEnabled(True)
        self.btn_start.setText("Schliessen")
        self.btn_start.clicked.disconnect()
        self.btn_start.clicked.connect(self.accept)

        self.btn_cancel.setVisible(False)
        self.spin_lookback.setEnabled(True)
        self.chk_force.setEnabled(True)

        self.update_completed.emit(total, inserted)

    def _on_error(self, error_msg: str):
        self._log(f"✗ {error_msg}")
        self.lbl_current.setText(f"Fehler: {error_msg}")
        self.lbl_current.setStyleSheet(
            "color: #f87171; font-size: 12px; font-weight: 500;"
        )

        self.btn_start.setEnabled(True)
        self.btn_start.setText("Erneut versuchen")
        self.btn_cancel.setEnabled(True)
        self.spin_lookback.setEnabled(True)
        self.chk_force.setEnabled(True)

    # ──────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────

    def _log(self, message: str):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{ts}] {message}")

    def closeEvent(self, event):
        if self._thread and self._thread.isRunning():
            self._worker.cancel()
            self._thread.quit()
            self._thread.wait(3000)
        super().closeEvent(event)
