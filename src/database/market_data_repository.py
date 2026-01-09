"""
Market Data Repository
Data Access Layer für Marktdaten (OHLCV).
"""
from typing import List, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from src.models.market_data import MarketData, DataEditLog
from .base_repository import BaseRepository


class MarketDataRepository(BaseRepository[MarketData]):
    """Repository für MarketData-Operationen."""
    
    def __init__(self, session: Session):
        super().__init__(MarketData, session)
    
    def get_by_ticker_and_date(
        self, 
        ticker_id: int, 
        data_date: date,
        source: Optional[str] = None
    ) -> Optional[MarketData]:
        """
        Findet Marktdaten für einen bestimmten Ticker und Datum.
        
        Args:
            ticker_id: Ticker ID
            data_date: Datum
            source: Optional - Datenquelle filtern
            
        Returns:
            MarketData-Instanz oder None
        """
        query = self.session.query(MarketData).filter(
            and_(
                MarketData.ticker_id == ticker_id,
                MarketData.date == data_date
            )
        )
        
        if source:
            query = query.filter_by(source=source)
        
        return query.first()
    
    def get_by_ticker_and_daterange(
        self,
        ticker_id: int,
        start_date: date,
        end_date: date,
        source: Optional[str] = None
    ) -> List[MarketData]:
        """
        Findet Marktdaten für einen Ticker in einem Datumsbereich.
        
        Args:
            ticker_id: Ticker ID
            start_date: Start-Datum
            end_date: End-Datum
            source: Optional - Datenquelle filtern
            
        Returns:
            Liste von MarketData-Instanzen, sortiert nach Datum
        """
        query = self.session.query(MarketData).filter(
            and_(
                MarketData.ticker_id == ticker_id,
                MarketData.date >= start_date,
                MarketData.date <= end_date
            )
        )
        
        if source:
            query = query.filter_by(source=source)
        
        return query.order_by(MarketData.date).all()
    
    def get_latest(self, ticker_id: int, n: int = 1) -> List[MarketData]:
        """
        Gibt die neuesten N Datensätze für einen Ticker zurück.
        
        Args:
            ticker_id: Ticker ID
            n: Anzahl der Datensätze
            
        Returns:
            Liste von MarketData-Instanzen, sortiert absteigend
        """
        return self.session.query(MarketData).filter_by(
            ticker_id=ticker_id
        ).order_by(desc(MarketData.date)).limit(n).all()
    
    def get_date_range(self, ticker_id: int) -> Optional[tuple[date, date]]:
        """
        Gibt den verfügbaren Datumsbereich für einen Ticker zurück.
        
        Args:
            ticker_id: Ticker ID
            
        Returns:
            Tuple (min_date, max_date) oder None wenn keine Daten
        """
        result = self.session.query(
            MarketData.date
        ).filter_by(ticker_id=ticker_id).order_by(MarketData.date).first()
        
        if not result:
            return None
        
        min_date = result[0]
        
        result = self.session.query(
            MarketData.date
        ).filter_by(ticker_id=ticker_id).order_by(desc(MarketData.date)).first()
        
        max_date = result[0]
        
        return (min_date, max_date)
    
    def bulk_create(self, market_data_list: List[MarketData]) -> int:
        """
        Erstellt mehrere Marktdaten-Einträge auf einmal.
        
        Args:
            market_data_list: Liste von MarketData-Instanzen
            
        Returns:
            Anzahl erstellter Datensätze
        """
        self.session.bulk_save_objects(market_data_list)
        self.session.flush()
        return len(market_data_list)
    
    def update_with_log(
        self,
        market_data: MarketData,
        field_name: str,
        new_value: any,
        edit_reason: str = ""
    ) -> MarketData:
        """
        Aktualisiert ein Feld und erstellt einen Edit-Log Eintrag.
        
        Args:
            market_data: MarketData-Instanz
            field_name: Name des zu ändernden Feldes
            new_value: Neuer Wert
            edit_reason: Grund für die Änderung
            
        Returns:
            Aktualisierte MarketData-Instanz
        """
        old_value = getattr(market_data, field_name)
        
        # Erstelle Edit-Log
        edit_log = DataEditLog(
            data_id=market_data.data_id,
            table_name='market_data',
            field_name=field_name,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
            edit_reason=edit_reason
        )
        self.session.add(edit_log)
        
        # Update Feld
        setattr(market_data, field_name, new_value)
        market_data.updated_at = datetime.utcnow()
        
        self.session.flush()
        return market_data
    
    def delete_by_ticker_and_daterange(
        self,
        ticker_id: int,
        start_date: date,
        end_date: date
    ) -> int:
        """
        Löscht Marktdaten für einen Ticker in einem Datumsbereich.
        
        Args:
            ticker_id: Ticker ID
            start_date: Start-Datum
            end_date: End-Datum
            
        Returns:
            Anzahl gelöschter Datensätze
        """
        count = self.session.query(MarketData).filter(
            and_(
                MarketData.ticker_id == ticker_id,
                MarketData.date >= start_date,
                MarketData.date <= end_date
            )
        ).delete()
        
        self.session.flush()
        return count
    
    def count_by_ticker(self, ticker_id: int) -> int:
        """
        Zählt Datensätze für einen Ticker.
        
        Args:
            ticker_id: Ticker ID
            
        Returns:
            Anzahl der Datensätze
        """
        return self.session.query(MarketData).filter_by(ticker_id=ticker_id).count()
