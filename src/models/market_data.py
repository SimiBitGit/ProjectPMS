"""
Market Data Models
Enthält Modelle für Marktdaten (OHLCV).
"""
from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, BigInteger, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime, date
from decimal import Decimal

from .base import Base


class MarketData(Base):
    """
    Market Data Model
    Speichert End-of-Day OHLCV Daten.
    """
    __tablename__ = 'market_data'
    
    # Primary Key
    data_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Keys
    ticker_id = Column(Integer, ForeignKey('tickers.ticker_id', ondelete='CASCADE'), nullable=False)
    
    # Date
    date = Column(Date, nullable=False, index=True)
    
    # OHLCV Data
    open = Column(Numeric(15, 4))
    high = Column(Numeric(15, 4))
    low = Column(Numeric(15, 4))
    close = Column(Numeric(15, 4), nullable=False)  # Close ist Pflichtfeld
    volume = Column(BigInteger)
    adj_close = Column(Numeric(15, 4))  # Adjusted Close (für Dividenden/Splits)
    
    # Metadata
    source = Column(String(50))  # z.B. 'eodhd', 'manual', etc.
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    ticker = relationship("Ticker", back_populates="market_data")
    edit_logs = relationship("DataEditLog", back_populates="market_data", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('ticker_id', 'date', 'source', name='uq_ticker_date_source'),
        Index('idx_market_data_ticker_date', 'ticker_id', 'date'),
    )
    
    def __repr__(self):
        return f"<MarketData(ticker_id={self.ticker_id}, date={self.date}, close={self.close})>"
    
    def to_dict(self):
        """Konvertiert das Model zu einem Dictionary."""
        return {
            'data_id': self.data_id,
            'ticker_id': self.ticker_id,
            'date': self.date.isoformat() if isinstance(self.date, date) else self.date,
            'open': float(self.open) if self.open else None,
            'high': float(self.high) if self.high else None,
            'low': float(self.low) if self.low else None,
            'close': float(self.close) if self.close else None,
            'volume': self.volume,
            'adj_close': float(self.adj_close) if self.adj_close else None,
            'source': self.source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class DataEditLog(Base):
    """
    Data Edit Log Model
    Audit-Trail für manuelle Bearbeitungen von Marktdaten.
    """
    __tablename__ = 'data_edit_log'
    
    # Primary Key
    edit_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Keys
    data_id = Column(Integer, ForeignKey('market_data.data_id', ondelete='CASCADE'), nullable=False)
    
    # Edit Information
    table_name = Column(String(50), nullable=False)  # Für zukünftige Erweiterungen
    field_name = Column(String(50), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    edit_reason = Column(Text)
    
    # Timestamp
    edited_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    market_data = relationship("MarketData", back_populates="edit_logs")
    
    def __repr__(self):
        return f"<DataEditLog(data_id={self.data_id}, field={self.field_name}, edited_at={self.edited_at})>"
    
    def to_dict(self):
        """Konvertiert das Model zu einem Dictionary."""
        return {
            'edit_id': self.edit_id,
            'data_id': self.data_id,
            'table_name': self.table_name,
            'field_name': self.field_name,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'edit_reason': self.edit_reason,
            'edited_at': self.edited_at.isoformat() if self.edited_at else None
        }
