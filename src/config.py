"""
Configuration Management
Lädt und verwaltet Applikations-Konfiguration aus settings.yaml und .env
"""
import yaml
import os
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv


class Config:
    """
    Singleton-Klasse für Applikations-Konfiguration.
    """
    _instance = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """Lädt Konfiguration aus .env und settings.yaml"""
        # Lade .env Datei
        env_path = Path(__file__).parent.parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
        
        # Lade settings.yaml
        settings_path = Path(__file__).parent.parent / 'config' / 'settings.yaml'
        if settings_path.exists():
            with open(settings_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
        else:
            # Default-Config wenn keine Datei vorhanden
            self._config = self._get_default_config()
        
        # Ersetze Environment-Variablen in Config
        self._replace_env_vars(self._config)
    
    def _replace_env_vars(self, config: Dict) -> None:
        """Ersetzt ${VAR} Platzhalter mit Environment-Variablen"""
        for key, value in config.items():
            if isinstance(value, dict):
                self._replace_env_vars(value)
            elif isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                config[key] = os.getenv(env_var, value)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Standard-Konfiguration"""
        return {
            'database': {
                'type': 'sqlite',
                'sqlite': {
                    'path': 'data/database/portfolio.db'
                }
            },
            'data_sources': {
                'primary': 'eodhd',
                'cache_enabled': True,
                'cache_duration': 3600
            },
            'ui': {
                'theme': 'light',
                'default_chart_type': 'candlestick',
                'table_rows_per_page': 100,
                'window_width': 1400,
                'window_height': 900
            },
            'logging': {
                'level': 'INFO',
                'file': 'logs/portfolio_manager.log',
                'max_bytes': 10485760,
                'backup_count': 5
            }
        }
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Holt einen Config-Wert über Pfad-Notation.
        
        Args:
            key_path: Pfad zum Wert, z.B. 'database.type'
            default: Default-Wert wenn nicht gefunden
            
        Returns:
            Config-Wert oder Default
            
        Example:
            >>> config = Config()
            >>> config.get('database.type')
            'sqlite'
        """
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_database_config(self) -> Dict[str, Any]:
        """Gibt die Datenbank-Konfiguration zurück"""
        return self.get('database', {})
    
    def get_ui_config(self) -> Dict[str, Any]:
        """Gibt die UI-Konfiguration zurück"""
        return self.get('ui', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Gibt die Logging-Konfiguration zurück"""
        return self.get('logging', {})
    
    def get_data_source_config(self) -> Dict[str, Any]:
        """Gibt die Datenquellen-Konfiguration zurück"""
        return self.get('data_sources', {})
    
    def get_api_key(self, service: str) -> str:
        """
        Holt einen API-Key aus den Environment-Variablen.
        
        Args:
            service: Service-Name (z.B. 'eodhd', 'alphavantage')
            
        Returns:
            API-Key oder leerer String
        """
        env_var = f"{service.upper()}_API_KEY"
        return os.getenv(env_var, '')
    
    @property
    def database_type(self) -> str:
        """Gibt den Datenbank-Typ zurück"""
        return self.get('database.type', 'sqlite')
    
    @property
    def log_level(self) -> str:
        """Gibt das Log-Level zurück"""
        return self.get('logging.level', 'INFO')


# Singleton-Instanz
config = Config()
