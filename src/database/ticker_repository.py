"""
Ticker Repository
Data Access Layer für Ticker/Symbol-Daten.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from src.models.metadata import Ticker, AssetType
from .base_repository import BaseRepository


class TickerRepository(BaseRepository[Ticker]):
    """Repository für Ticker-Operationen."""
    
    def __init__(self, session: Session):
        super().__init__(Ticker, session)
    
    def get_by_id(self, ticker_id: int) -> Optional[Ticker]:
        """
        Findet einen Ticker anhand der ID.
        
        Args:
            ticker_id: Ticker ID
            
        Returns:
            Ticker-Instanz oder None
        """
        return self.session.query(Ticker).filter_by(ticker_id=ticker_id).first()
    
    def get_by_symbol(self, symbol: str) -> Optional[Ticker]:
        """
        Findet einen Ticker anhand des Symbols.
        
        Args:
            symbol: Ticker-Symbol (z.B. 'AAPL')
            
        Returns:
            Ticker-Instanz oder None
        """
        return self.session.query(Ticker).filter_by(symbol=symbol.upper()).first()
    
    def get_by_isin(self, isin: str) -> Optional[Ticker]:
        """
        Findet einen Ticker anhand der ISIN.
        
        Args:
            isin: ISIN (z.B. 'US0378331005')
            
        Returns:
            Ticker-Instanz oder None
        """
        return self.session.query(Ticker).filter_by(isin=isin.upper()).first()
    
    def get_all_active(self) -> List[Ticker]:
        """
        Gibt alle aktiven Ticker zurück.
        
        Returns:
            Liste von aktiven Ticker-Instanzen
        """
        return self.session.query(Ticker).filter_by(is_active=True).order_by(Ticker.symbol).all()
    
    def get_by_asset_type(self, asset_type: AssetType, active_only: bool = True) -> List[Ticker]:
        """
        Findet alle Ticker eines bestimmten Asset-Types.
        
        Args:
            asset_type: Asset-Typ (STOCK, ETF, FX, etc.)
            active_only: Nur aktive Ticker
            
        Returns:
            Liste von Ticker-Instanzen
        """
        query = self.session.query(Ticker).filter_by(asset_type=asset_type)
        
        if active_only:
            query = query.filter_by(is_active=True)
        
        return query.order_by(Ticker.symbol).all()
    
    def get_by_exchange(self, exchange: str, active_only: bool = True) -> List[Ticker]:
        """
        Findet alle Ticker einer bestimmten Börse.
        
        Args:
            exchange: Börse (z.B. 'NASDAQ', 'NYSE')
            active_only: Nur aktive Ticker
            
        Returns:
            Liste von Ticker-Instanzen
        """
        query = self.session.query(Ticker).filter_by(exchange=exchange.upper())
        
        if active_only:
            query = query.filter_by(is_active=True)
        
        return query.order_by(Ticker.symbol).all()
    
    def search(self, search_term: str, active_only: bool = True) -> List[Ticker]:
        """
        Sucht Ticker nach Symbol oder Name.
        
        Args:
            search_term: Suchbegriff
            active_only: Nur aktive Ticker
            
        Returns:
            Liste von Ticker-Instanzen
        """
        search_pattern = f"%{search_term}%"
        query = self.session.query(Ticker).filter(
            or_(
                Ticker.symbol.ilike(search_pattern),
                Ticker.name.ilike(search_pattern)
            )
        )
        
        if active_only:
            query = query.filter_by(is_active=True)
        
        return query.order_by(Ticker.symbol).limit(50).all()
    
    def create_or_update(self, symbol: str, **kwargs) -> Ticker:
        """
        Erstellt einen neuen Ticker oder aktualisiert einen bestehenden.
        
        Args:
            symbol: Ticker-Symbol
            **kwargs: Weitere Ticker-Attribute
            
        Returns:
            Ticker-Instanz
        """
        ticker = self.get_by_symbol(symbol)
        
        if ticker:
            # Update bestehenden Ticker
            for key, value in kwargs.items():
                if hasattr(ticker, key):
                    setattr(ticker, key, value)
            self.session.flush()
        else:
            # Erstelle neuen Ticker
            ticker = Ticker(symbol=symbol.upper(), **kwargs)
            self.session.add(ticker)
            self.session.flush()
        
        return ticker
    
    def deactivate(self, ticker_id: int) -> bool:
        """
        Deaktiviert einen Ticker (Soft Delete).
        
        Args:
            ticker_id: Ticker ID
            
        Returns:
            True wenn erfolgreich, False wenn nicht gefunden
        """
        ticker = self.get_by_id(ticker_id)
        if ticker:
            ticker.is_active = False
            self.session.flush()
            return True
        return False
    
    def activate(self, ticker_id: int) -> bool:
        """
        Aktiviert einen Ticker.
        
        Args:
            ticker_id: Ticker ID
            
        Returns:
            True wenn erfolgreich, False wenn nicht gefunden
        """
        ticker = self.get_by_id(ticker_id)
        if ticker:
            ticker.is_active = True
            self.session.flush()
            return True
        return False
