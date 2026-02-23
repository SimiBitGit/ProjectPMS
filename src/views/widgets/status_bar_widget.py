# src/views/widgets/status_bar_widget.py
"""
Status Bar Widget – Shows current operation status and timestamps.
"""

from datetime import datetime
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QTimer


class StatusBarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.lbl_message = QLabel("Bereit")
        self.lbl_message.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(self.lbl_message)

        layout.addStretch()

        self.lbl_time = QLabel("")
        self.lbl_time.setStyleSheet("color: #334155; font-size: 11px;")
        layout.addWidget(self.lbl_time)

    def set_message(self, message: str):
        self.lbl_message.setText(message)
        ts = datetime.now().strftime("%d.%m.%Y %H:%M")
        self.lbl_time.setText(f"Aktualisiert: {ts}")
