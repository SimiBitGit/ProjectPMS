"""
Processed Data Repository
Data Access Layer für berechnete/verarbeitete Daten (Indikatoren).
"""
from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from src.models.processed_data import ProcessedData
from .base_repository import BaseRepository


class ProcessedDataRepository(BaseRepository[ProcessedData]):
    """Repository für ProcessedData-Operationen."""
    
    def __init__(self, session: Session):
        super().__init__(ProcessedData, session)
    
    def get_by_ticker_indicator_date(
        self,
        ticker_id: int,
        indicator: str,
        data_date: date,
        version: int = 1
    ) -> Optional[ProcessedData]:
        """
        Findet einen Indikator für einen Ticker an einem bestimmten Datum.
        
        Args:
            ticker_id: Ticker ID
            indicator: Indikator-Name (z.B. 'SMA_20')
            data_date: Datum
            version: Indikator-Version
            
        Returns:
            ProcessedData-Instanz oder None
        """
        return self.session.query(ProcessedData).filter(
            and_(
                ProcessedData.ticker_id == ticker_id,
                ProcessedData.indicator == indicator,
                ProcessedData.date == data_date,
                ProcessedData.version == version
            )
        ).first()
    
    def get_by_ticker_indicator_daterange(
        self,
        ticker_id: int,
        indicator: str,
        start_date: date,
        end_date: date,
        version: int = 1
    ) -> List[ProcessedData]:
        """
        Findet Indikator-Daten für einen Ticker in einem Datumsbereich.
        
        Args:
            ticker_id: Ticker ID
            indicator: Indikator-Name
            start_date: Start-Datum
            end_date: End-Datum
            version: Indikator-Version
            
        Returns:
            Liste von ProcessedData-Instanzen, sortiert nach Datum
        """
        return self.session.query(ProcessedData).filter(
            and_(
                ProcessedData.ticker_id == ticker_id,
                ProcessedData.indicator == indicator,
                ProcessedData.date >= start_date,
                ProcessedData.date <= end_date,
                ProcessedData.version == version
            )
        ).order_by(ProcessedData.date).all()
    
    def get_all_indicators_for_date(
        self,
        ticker_id: int,
        data_date: date,
        version: int = 1
    ) -> List[ProcessedData]:
        """
        Gibt alle Indikatoren für einen Ticker an einem Datum zurück.
        
        Args:
            ticker_id: Ticker ID
            data_date: Datum
            version: Indikator-Version
            
        Returns:
            Liste von ProcessedData-Instanzen
        """
        return self.session.query(ProcessedData).filter(
            and_(
                ProcessedData.ticker_id == ticker_id,
                ProcessedData.date == data_date,
                ProcessedData.version == version
            )
        ).all()
    
    def get_available_indicators(self, ticker_id: int) -> List[str]:
        """
        Gibt alle verfügbaren Indikatoren für einen Ticker zurück.
        
        Args:
            ticker_id: Ticker ID
            
        Returns:
            Liste von Indikator-Namen
        """
        result = self.session.query(
            ProcessedData.indicator
        ).filter_by(ticker_id=ticker_id).distinct().all()
        
        return [row[0] for row in result]
    
    def get_latest(
        self,
        ticker_id: int,
        indicator: str,
        n: int = 1,
        version: int = 1
    ) -> List[ProcessedData]:
        """
        Gibt die neuesten N Indikator-Werte zurück.
        
        Args:
            ticker_id: Ticker ID
            indicator: Indikator-Name
            n: Anzahl der Datensätze
            version: Indikator-Version
            
        Returns:
            Liste von ProcessedData-Instanzen, sortiert absteigend
        """
        return self.session.query(ProcessedData).filter(
            and_(
                ProcessedData.ticker_id == ticker_id,
                ProcessedData.indicator == indicator,
                ProcessedData.version == version
            )
        ).order_by(desc(ProcessedData.date)).limit(n).all()
    
    def bulk_create(self, processed_data_list: List[ProcessedData]) -> int:
        """
        Erstellt mehrere ProcessedData-Einträge auf einmal.
        
        Args:
            processed_data_list: Liste von ProcessedData-Instanzen
            
        Returns:
            Anzahl erstellter Datensätze
        """
        self.session.bulk_save_objects(processed_data_list)
        self.session.flush()
        return len(processed_data_list)
    
    def delete_by_ticker_indicator(
        self,
        ticker_id: int,
        indicator: str,
        version: Optional[int] = None
    ) -> int:
        """
        Löscht alle Daten für einen bestimmten Indikator.
        
        Args:
            ticker_id: Ticker ID
            indicator: Indikator-Name
            version: Optional - nur bestimmte Version löschen
            
        Returns:
            Anzahl gelöschter Datensätze
        """
        query = self.session.query(ProcessedData).filter(
            and_(
                ProcessedData.ticker_id == ticker_id,
                ProcessedData.indicator == indicator
            )
        )
        
        if version is not None:
            query = query.filter_by(version=version)
        
        count = query.delete()
        self.session.flush()
        return count
    
    def delete_by_ticker_daterange(
        self,
        ticker_id: int,
        start_date: date,
        end_date: date
    ) -> int:
        """
        Löscht alle ProcessedData für einen Ticker in einem Datumsbereich.
        
        Args:
            ticker_id: Ticker ID
            start_date: Start-Datum
            end_date: End-Datum
            
        Returns:
            Anzahl gelöschter Datensätze
        """
        count = self.session.query(ProcessedData).filter(
            and_(
                ProcessedData.ticker_id == ticker_id,
                ProcessedData.date >= start_date,
                ProcessedData.date <= end_date
            )
        ).delete()
        
        self.session.flush()
        return count
    
    def count_by_ticker_indicator(
        self,
        ticker_id: int,
        indicator: str
    ) -> int:
        """
        Zählt Datensätze für einen Ticker und Indikator.
        
        Args:
            ticker_id: Ticker ID
            indicator: Indikator-Name
            
        Returns:
            Anzahl der Datensätze
        """
        return self.session.query(ProcessedData).filter(
            and_(
                ProcessedData.ticker_id == ticker_id,
                ProcessedData.indicator == indicator
            )
        ).count()
