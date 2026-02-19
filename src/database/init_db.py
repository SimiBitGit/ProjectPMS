"""
Database Initialization Script
Initialisiert die Datenbank und erstellt alle Tabellen.
"""
from pathlib import Path
import sys

# Füge src zum Python-Path hinzu
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from src.models import (
    init_engine,
    create_all_tables,
    Base
)
# GICS-Model explizit importieren damit die Tabelle registriert wird
from src.models.gics import GicsReference 

from src.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def init_database():
    """Initialisiert die Datenbank und erstellt alle Tabellen."""
    try:
        logger.info("=== Datenbank-Initialisierung gestartet ===")
        
        # Lese Datenbank-Typ aus Config
        db_type = config.database_type
        logger.info(f"Datenbank-Typ: {db_type}")
        
        # Initialisiere Engine
        engine = init_engine(db_type=db_type, echo=True)
        logger.info(f"Engine initialisiert: {engine.url}")
        
        # Erstelle alle Tabellen
        logger.info("Erstelle Tabellen...")
        create_all_tables()
        
        # Liste alle erstellten Tabellen
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        logger.info(f"Erfolgreich {len(tables)} Tabellen erstellt:")
        for table in tables:
            logger.info(f"  - {table}")
        
        logger.info("=== Datenbank-Initialisierung abgeschlossen ===")
        return True
        
    except Exception as e:
        logger.error(f"Fehler bei Datenbank-Initialisierung: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
