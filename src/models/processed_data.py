"""
Processed Data Models
Enthält Modelle für berechnete/verarbeitete Daten (Indikatoren).
"""
from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, ForeignKey, Text, UniqueConstraint, Index, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, date

from .base import Base


class ProcessedData(Base):
    """
    Processed Data Model
    Speichert berechnete Indikatoren und verarbeitete Marktdaten.
    """
    __tablename__ = 'processed_data'
    
    # Primary Key
    proc_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Keys
    ticker_id = Column(Integer, ForeignKey('tickers.ticker_id', ondelete='CASCADE'), nullable=False)
    
    # Date
    date = Column(Date, nullable=False, index=True)
    
    # Indicator Information
    indicator = Column(String(50), nullable=False, index=True)  # z.B. 'SMA_20', 'MACD', 'ROC_10'
    value = Column(Numeric(15, 6))  # Hauptwert des Indikators
    
    # Zusätzliche Werte (für komplexe Indikatoren wie MACD)
    value_secondary = Column(Numeric(15, 6))  # z.B. MACD Signal Line
    value_tertiary = Column(Numeric(15, 6))   # z.B. MACD Histogram
    
    # Parameters (JSON)
    parameters = Column(JSON)  # Berechnungsparameter als JSON
    # Beispiel: {"period": 20, "method": "simple"} für SMA_20
    
    # Version (für zukünftige Anpassungen der Berechnungslogik)
    version = Column(Integer, default=1, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    ticker = relationship("Ticker", back_populates="processed_data")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('ticker_id', 'date', 'indicator', 'version', name='uq_ticker_date_indicator_version'),
        Index('idx_processed_ticker_indicator', 'ticker_id', 'indicator', 'date'),
    )
    
    def __repr__(self):
        return f"<ProcessedData(ticker_id={self.ticker_id}, date={self.date}, indicator={self.indicator}, value={self.value})>"
    
    def to_dict(self):
        """Konvertiert das Model zu einem Dictionary."""
        return {
            'proc_id': self.proc_id,
            'ticker_id': self.ticker_id,
            'date': self.date.isoformat() if isinstance(self.date, date) else self.date,
            'indicator': self.indicator,
            'value': float(self.value) if self.value else None,
            'value_secondary': float(self.value_secondary) if self.value_secondary else None,
            'value_tertiary': float(self.value_tertiary) if self.value_tertiary else None,
            'parameters': self.parameters,
            'version': self.version,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def create_indicator_name(cls, base_indicator: str, **params) -> str:
        """
        Hilfsmethode zum Erstellen standardisierter Indikator-Namen.
        
        Args:
            base_indicator: Basis-Name (z.B. 'SMA', 'MACD', 'ROC')
            **params: Parameter (z.B. period=20)
            
        Returns:
            Standardisierter Name (z.B. 'SMA_20')
            
        Examples:
            >>> ProcessedData.create_indicator_name('SMA', period=20)
            'SMA_20'
            >>> ProcessedData.create_indicator_name('MACD', fast=12, slow=26, signal=9)
            'MACD_12_26_9'
        """
        if not params:
            return base_indicator
        
        param_str = '_'.join(str(v) for v in params.values())
        return f"{base_indicator}_{param_str}"
