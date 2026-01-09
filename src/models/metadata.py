"""
Metadata Models
Enthält Stammdaten-Modelle wie Ticker/Symbols.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from .base import Base


class AssetType(enum.Enum):
    """Asset-Typen Enumeration"""
    STOCK = "STOCK"
    ETF = "ETF"
    INDEX = "INDEX"
    CRYPTO = "CRYPTO"
    FX = "FX"  # Foreign Exchange / Währungen
    COMMODITY = "COMMODITY"
    BOND = "BOND"


class Ticker(Base):
    """
    Ticker/Symbol Model
    Speichert Stammdaten zu handelbaren Instrumenten.
    """
    __tablename__ = 'tickers'
    
    # Primary Key
    ticker_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Core Fields
    symbol = Column(String(20), nullable=False, unique=True, index=True)
    name = Column(String(200))
    exchange = Column(String(50))
    currency = Column(String(3))  # ISO 4217 (USD, EUR, CHF, etc.)
    asset_type = Column(SQLEnum(AssetType), nullable=False)
    
    # Additional Info
    isin = Column(String(12), unique=True, index=True)  # Optional: ISIN
    description = Column(String(1000))
    sector = Column(String(100))  # Für Stocks
    industry = Column(String(100))  # Für Stocks
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    market_data = relationship("MarketData", back_populates="ticker", cascade="all, delete-orphan")
    processed_data = relationship("ProcessedData", back_populates="ticker", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Ticker(symbol='{self.symbol}', name='{self.name}', type='{self.asset_type.value}')>"
    
    def to_dict(self):
        """Konvertiert das Model zu einem Dictionary."""
        return {
            'ticker_id': self.ticker_id,
            'symbol': self.symbol,
            'name': self.name,
            'exchange': self.exchange,
            'currency': self.currency,
            'asset_type': self.asset_type.value,
            'isin': self.isin,
            'sector': self.sector,
            'industry': self.industry,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
