"""
Installations-Test
Überprüft, ob alle Komponenten korrekt installiert sind.
"""
import sys
from pathlib import Path

# Füge src zum Python-Path hinzu
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))


def test_imports():
    """Testet alle wichtigen Imports"""
    print("=== Portfolio Manager - Installations-Test ===\n")
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Config
    try:
        from src.config import config
        db_type = config.database_type
        print(f"✓ Config geladen - Datenbank-Typ: {db_type}")
        tests_passed += 1
    except Exception as e:
        print(f"✗ Config-Import fehlgeschlagen: {e}")
        tests_failed += 1
    
    # Test 2: Logger
    try:
        from src.utils.logger import get_logger
        logger = get_logger('test')
        logger.info("Test-Log-Nachricht")
        print("✓ Logger funktioniert")
        tests_passed += 1
    except Exception as e:
        print(f"✗ Logger-Import fehlgeschlagen: {e}")
        tests_failed += 1
    
    # Test 3: Models
    try:
        from src.models import Ticker, MarketData, ProcessedData, AssetType
        print("✓ Models importiert")
        tests_passed += 1
    except Exception as e:
        print(f"✗ Models-Import fehlgeschlagen: {e}")
        tests_failed += 1
    
    # Test 4: Repositories
    try:
        from src.database import TickerRepository, MarketDataRepository, ProcessedDataRepository
        print("✓ Repositories importiert")
        tests_passed += 1
    except Exception as e:
        print(f"✗ Repository-Import fehlgeschlagen: {e}")
        tests_failed += 1
    
    # Test 5: Database Base
    try:
        from src.models.base import get_database_url
        db_url = get_database_url('sqlite')
        print(f"✓ Database URL: {db_url}")
        tests_passed += 1
    except Exception as e:
        print(f"✗ Database Base fehlgeschlagen: {e}")
        tests_failed += 1
    
    # Zusammenfassung
    print(f"\n{'='*50}")
    print(f"Tests bestanden: {tests_passed}")
    print(f"Tests fehlgeschlagen: {tests_failed}")
    print(f"{'='*50}\n")
    
    if tests_failed == 0:
        print("✓ Alle Tests erfolgreich! Die Basis-Installation ist korrekt.")
        print("\nNächste Schritte:")
        print("1. Erstelle .env Datei: cp .env.example .env")
        print("2. Trage EODHD_API_KEY in .env ein")
        print("3. Initialisiere Datenbank: python -m src.database.init_db")
        return True
    else:
        print("✗ Einige Tests sind fehlgeschlagen. Bitte Fehler beheben.")
        return False


if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
