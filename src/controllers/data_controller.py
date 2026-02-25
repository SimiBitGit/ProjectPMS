# src/controllers/data_controller.py
"""
DataController — Steuerungsschicht für Marktdaten-Bearbeitung.

Verbindet:
  DataTableWidget.dataEdited(data_id, field, old, new, reason)
    → MarketDataRepository.update_with_log()
    → StatusBar-Feedback

  DataTableWidget.editLogRequested(data_id)
    → DataEditLog-Abfrage → Dialog (optional)
"""

from PySide6.QtCore import QObject, Slot
from sqlalchemy.orm import Session

from src.database.market_data_repository import MarketDataRepository
from src.models.market_data import MarketData
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DataController(QObject):
    """
    Controller für Marktdaten-Änderungen aus der DataTableWidget.

    Usage:
        controller = DataController(session=session)
        controller.connect_table(data_table_widget)
        controller.set_status_callback(main_window.set_status)
    """

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._repo = MarketDataRepository(session)
        self._status_callback = None

    def set_status_callback(self, callback):
        """Setzt eine Callback-Funktion für Status-Nachrichten (z.B. MainWindow.set_status)."""
        self._status_callback = callback

    def connect_table(self, data_table_widget):
        """
        Verbindet die Signale der DataTableWidget mit diesem Controller.

        Args:
            data_table_widget: DataTableWidget-Instanz
        """
        data_table_widget.dataEdited.connect(self._on_data_edited)
        data_table_widget.editLogRequested.connect(self._on_edit_log_requested)
        logger.info("DataController: DataTableWidget-Signale verbunden")

    # ──────────────────────────────────────────
    #  Slots
    # ──────────────────────────────────────────

    @Slot(int, str, object, object, str)
    def _on_data_edited(self, data_id: int, field: str, old_value, new_value, reason: str):
        """
        Slot für DataTableWidget.dataEdited.
        Schreibt die Änderung via Repository in die DB + Audit-Log.
        """
        try:
            # MarketData-Instanz laden
            market_data = self._session.get(MarketData, data_id)
            if not market_data:
                logger.error(f"MarketData mit data_id={data_id} nicht gefunden")
                self._set_status(f"Fehler: Datensatz {data_id} nicht gefunden")
                return

            # Update mit Audit-Log
            self._repo.update_with_log(
                market_data=market_data,
                field_name=field,
                new_value=new_value,
                edit_reason=reason,
            )
            self._session.commit()

            logger.info(
                f"MarketData updated: data_id={data_id}, "
                f"{field}: {old_value} → {new_value} (Grund: {reason})"
            )
            self._set_status(
                f"Gespeichert: {field} von {old_value} auf {new_value} geändert"
            )

        except Exception as e:
            self._session.rollback()
            logger.error(f"Fehler beim Speichern der Änderung: {e}", exc_info=True)
            self._set_status(f"Fehler beim Speichern: {e}")

    @Slot(int)
    def _on_edit_log_requested(self, data_id: int):
        """
        Slot für DataTableWidget.editLogRequested.
        Lädt den Audit-Log für einen Datensatz und loggt ihn.
        """
        try:
            from src.models.market_data import DataEditLog

            logs = (
                self._session.query(DataEditLog)
                .filter_by(data_id=data_id)
                .order_by(DataEditLog.edited_at.desc())
                .all()
            )

            if not logs:
                logger.info(f"Kein Edit-Log für data_id={data_id}")
                self._set_status(f"Keine Änderungen für Datensatz {data_id}")
                return

            logger.info(f"Edit-Log für data_id={data_id}: {len(logs)} Einträge")
            for log in logs:
                logger.info(
                    f"  [{log.edited_at}] {log.field_name}: "
                    f"{log.old_value} → {log.new_value} ({log.edit_reason})"
                )

            self._set_status(f"Edit-Log: {len(logs)} Änderungen für Datensatz {data_id}")

            # TODO: Dialog mit Edit-Log-Tabelle anzeigen (zukünftige Erweiterung)

        except Exception as e:
            logger.error(f"Fehler beim Laden des Edit-Logs: {e}", exc_info=True)

    # ──────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────

    def _set_status(self, message: str):
        """Status-Nachricht an die UI weiterleiten."""
        if self._status_callback:
            self._status_callback(message)
