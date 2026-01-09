"""
Logging Configuration
Stellt standardisiertes Logging für die gesamte Applikation bereit.
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

from src.config import config


def setup_logger(
    name: str,
    level: Optional[str] = None,
    log_to_file: bool = True,
    log_to_console: bool = True
) -> logging.Logger:
    """
    Erstellt und konfiguriert einen Logger.
    
    Args:
        name: Logger-Name (typischerweise __name__)
        level: Log-Level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: In Datei loggen
        log_to_console: In Console loggen
        
    Returns:
        Konfigurierter Logger
        
    Example:
        >>> logger = setup_logger(__name__)
        >>> logger.info("Application started")
    """
    logger = logging.getLogger(name)
    
    # Level aus Config oder Parameter
    if level is None:
        level = config.log_level
    logger.setLevel(getattr(logging, level.upper()))
    
    # Verhindere doppelte Handler
    if logger.handlers:
        return logger
    
    # Formatter
    log_format = config.get('logging.format', 
                           '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter(log_format)
    
    # Console Handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File Handler
    if log_to_file:
        log_file = config.get('logging.file', 'logs/portfolio_manager.log')
        log_path = Path(__file__).parent.parent / log_file
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        max_bytes = config.get('logging.max_bytes', 10485760)  # 10 MB
        backup_count = config.get('logging.backup_count', 5)
        
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Holt einen existierenden Logger oder erstellt einen neuen.
    
    Args:
        name: Logger-Name
        
    Returns:
        Logger-Instanz
    """
    return setup_logger(name)


# Root Logger für Applikation
app_logger = setup_logger('portfolio_manager')
