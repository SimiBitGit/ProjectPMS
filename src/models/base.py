"""
SQLAlchemy Base Configuration
Stellt die Basis-Klasse und Engine-Factory für alle Models bereit.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import os
from pathlib import Path

# Declarative Base für alle Models
Base = declarative_base()

# Global Engine und SessionLocal
_engine = None
_SessionLocal = None


def get_database_url(db_type: str = 'sqlite') -> str:
    """
    Generiert die Datenbank-URL basierend auf dem Typ.
    
    Args:
        db_type: 'sqlite' oder 'postgresql'
        
    Returns:
        Database URL String
    """
    if db_type == 'sqlite':
        # Stelle sicher, dass das data/database Verzeichnis existiert
        db_path = Path(__file__).parent.parent.parent / 'data' / 'database'
        db_path.mkdir(parents=True, exist_ok=True)
        
        db_file = db_path / 'portfolio.db'
        return f'sqlite:///{db_file}'
        
    elif db_type == 'postgresql':
        # Lade aus Environment Variables
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '5432')
        database = os.getenv('DB_NAME', 'portfolio_db')
        user = os.getenv('DB_USER', 'portfolio_user')
        password = os.getenv('DB_PASSWORD', '')
        
        return f'postgresql://{user}:{password}@{host}:{port}/{database}'
    
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def init_engine(db_type: str = 'sqlite', echo: bool = False):
    """
    Initialisiert die SQLAlchemy Engine.
    
    Args:
        db_type: Datenbank-Typ ('sqlite' oder 'postgresql')
        echo: SQL-Statements in Console ausgeben
    """
    global _engine, _SessionLocal
    
    database_url = get_database_url(db_type)
    
    # Erstelle Engine
    _engine = create_engine(
        database_url,
        echo=echo,
        # SQLite-spezifische Einstellungen
        connect_args={"check_same_thread": False} if db_type == 'sqlite' else {}
    )
    
    # Erstelle SessionLocal
    _SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=_engine
    )
    
    return _engine


def get_engine():
    """Gibt die globale Engine zurück."""
    global _engine
    if _engine is None:
        init_engine()
    return _engine


def get_session() -> Session:
    """
    Erstellt eine neue Session.
    
    Returns:
        SQLAlchemy Session
    """
    global _SessionLocal
    if _SessionLocal is None:
        init_engine()
    return _SessionLocal()


def get_session_context() -> Generator[Session, None, None]:
    """
    Context Manager für Sessions (für Dependency Injection).
    
    Usage:
        with get_session_context() as session:
            # Arbeit mit session
            pass
    
    Yields:
        SQLAlchemy Session
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all_tables():
    """Erstellt alle Tabellen in der Datenbank."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def drop_all_tables():
    """Löscht alle Tabellen aus der Datenbank. VORSICHT!"""
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
