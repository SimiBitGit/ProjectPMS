# src/main.py
"""
Portfolio Manager – Einstiegspunkt
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from src.views.main_window import MainWindow
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_session():
    try:
        from src.models.base import get_session as _get_session
        return _get_session()
    except Exception as e:
        logger.warning(f"Keine DB-Verbindung: {e} — Demo-Modus")
        return None


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Portfolio Manager")
    app.setApplicationVersion("0.1")
    app.setOrganizationName("PortfolioManager")

    session = get_session()
    window = MainWindow(session=session)
    window.show()

    if session:
        window.set_db_connected(True)
        window.set_status("Datenbankverbindung hergestellt")
        # Ticker-Liste initial aus DB laden
        window._reload_ticker_list()
    else:
        window.set_db_connected(False)
        window.set_status("Demo-Modus — Keine Datenbankverbindung")

    logger.info("Application started")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
