# tests/test_controllers/test_data_controller.py
"""
Tests für DataController.

Testet die Geschäftslogik (DB-Update + Audit-Log) direkt,
ohne Qt-Event-Loop (kein pytest-qt nötig).
"""

import pytest
from datetime import date
from decimal import Decimal

from src.controllers.data_controller import DataController
from src.models.market_data import MarketData, DataEditLog


class TestDataController:
    """Tests für DataController Slots (direkt aufgerufen, ohne Qt-Signale)."""

    def test_on_data_edited_saves_change(self, session, sample_ticker, sample_market_data):
        """Slot _on_data_edited speichert Änderung in DB."""
        controller = DataController(session=session)
        status_messages = []
        controller.set_status_callback(lambda msg: status_messages.append(msg))

        record = sample_market_data[0]
        old_close = record.close

        # Direkt den Slot aufrufen (simuliert Signal)
        controller._on_data_edited(
            data_id=record.data_id,
            field="close",
            old_value=float(old_close),
            new_value=Decimal("999.99"),
            reason="Test-Korrektur",
        )

        # DB prüfen
        session.refresh(record)
        assert float(record.close) == 999.99

        # Audit-Log prüfen
        logs = session.query(DataEditLog).filter_by(data_id=record.data_id).all()
        assert len(logs) == 1
        assert logs[0].field_name == "close"
        assert logs[0].edit_reason == "Test-Korrektur"

        # Status-Callback wurde aufgerufen
        assert len(status_messages) == 1
        assert "Gespeichert" in status_messages[0]

    def test_on_data_edited_invalid_id(self, session, sample_ticker):
        """Slot mit ungültiger data_id gibt Fehler-Status."""
        controller = DataController(session=session)
        status_messages = []
        controller.set_status_callback(lambda msg: status_messages.append(msg))

        controller._on_data_edited(
            data_id=99999,
            field="close",
            old_value=100.0,
            new_value=200.0,
            reason="Ungültig",
        )

        assert len(status_messages) == 1
        assert "nicht gefunden" in status_messages[0]

    def test_on_data_edited_multiple_fields(self, session, sample_ticker, sample_market_data):
        """Mehrere Felder eines Records bearbeiten → mehrere Audit-Log-Einträge."""
        controller = DataController(session=session)
        record = sample_market_data[0]

        controller._on_data_edited(record.data_id, "close", 100, Decimal("200.00"), "Fix close")
        controller._on_data_edited(record.data_id, "volume", 1000000, 5000000, "Fix volume")

        logs = session.query(DataEditLog).filter_by(data_id=record.data_id).all()
        assert len(logs) == 2
        fields = {l.field_name for l in logs}
        assert fields == {"close", "volume"}

    def test_on_edit_log_requested(self, session, sample_ticker, sample_market_data):
        """Slot _on_edit_log_requested lädt Audit-Log und gibt Status."""
        controller = DataController(session=session)
        status_messages = []
        controller.set_status_callback(lambda msg: status_messages.append(msg))

        record = sample_market_data[0]

        # Erst eine Änderung machen
        controller._on_data_edited(record.data_id, "close", 100, Decimal("999.99"), "Test")
        status_messages.clear()

        # Dann Log abfragen
        controller._on_edit_log_requested(record.data_id)

        assert len(status_messages) == 1
        assert "1 Änderungen" in status_messages[0]

    def test_on_edit_log_requested_no_logs(self, session, sample_ticker, sample_market_data):
        """Keine Änderungen → Hinweis-Status."""
        controller = DataController(session=session)
        status_messages = []
        controller.set_status_callback(lambda msg: status_messages.append(msg))

        controller._on_edit_log_requested(sample_market_data[0].data_id)

        assert len(status_messages) == 1
        assert "Keine Änderungen" in status_messages[0]
