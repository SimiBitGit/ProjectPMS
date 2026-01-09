"""
Base Repository
Generische Repository-Basisklasse mit CRUD-Operationen.
"""
from typing import TypeVar, Generic, List, Optional, Type
from sqlalchemy.orm import Session
from src.models.base import Base

# Type Variable für Generic Repository
ModelType = TypeVar('ModelType', bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generisches Repository für CRUD-Operationen.
    
    Beispiel:
        class TickerRepository(BaseRepository[Ticker]):
            def __init__(self, session: Session):
                super().__init__(Ticker, session)
    """
    
    def __init__(self, model: Type[ModelType], session: Session):
        """
        Initialisiert das Repository.
        
        Args:
            model: SQLAlchemy Model-Klasse
            session: Aktive Datenbank-Session
        """
        self.model = model
        self.session = session
    
    def get_by_id(self, id: int) -> Optional[ModelType]:
        """
        Findet einen Datensatz anhand der ID.
        
        Args:
            id: Primary Key
            
        Returns:
            Model-Instanz oder None
        """
        return self.session.query(self.model).filter_by(id=id).first()
    
    def get_all(self, limit: Optional[int] = None, offset: int = 0) -> List[ModelType]:
        """
        Gibt alle Datensätze zurück.
        
        Args:
            limit: Maximale Anzahl
            offset: Offset für Paginierung
            
        Returns:
            Liste von Model-Instanzen
        """
        query = self.session.query(self.model)
        
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
            
        return query.all()
    
    def create(self, obj: ModelType) -> ModelType:
        """
        Erstellt einen neuen Datensatz.
        
        Args:
            obj: Model-Instanz
            
        Returns:
            Erstellte Model-Instanz mit ID
        """
        self.session.add(obj)
        self.session.flush()  # Damit ID verfügbar ist
        return obj
    
    def update(self, obj: ModelType) -> ModelType:
        """
        Aktualisiert einen bestehenden Datensatz.
        
        Args:
            obj: Model-Instanz mit Änderungen
            
        Returns:
            Aktualisierte Model-Instanz
        """
        self.session.merge(obj)
        self.session.flush()
        return obj
    
    def delete(self, obj: ModelType) -> None:
        """
        Löscht einen Datensatz.
        
        Args:
            obj: Zu löschende Model-Instanz
        """
        self.session.delete(obj)
        self.session.flush()
    
    def delete_by_id(self, id: int) -> bool:
        """
        Löscht einen Datensatz anhand der ID.
        
        Args:
            id: Primary Key
            
        Returns:
            True wenn gelöscht, False wenn nicht gefunden
        """
        obj = self.get_by_id(id)
        if obj:
            self.delete(obj)
            return True
        return False
    
    def count(self) -> int:
        """
        Zählt alle Datensätze.
        
        Returns:
            Anzahl der Datensätze
        """
        return self.session.query(self.model).count()
    
    def exists(self, id: int) -> bool:
        """
        Prüft, ob ein Datensatz mit der ID existiert.
        
        Args:
            id: Primary Key
            
        Returns:
            True wenn vorhanden, sonst False
        """
        return self.session.query(
            self.session.query(self.model).filter_by(id=id).exists()
        ).scalar()
    
    def commit(self) -> None:
        """Committed die aktuelle Transaction."""
        self.session.commit()
    
    def rollback(self) -> None:
        """Rollt die aktuelle Transaction zurück."""
        self.session.rollback()
    
    def refresh(self, obj: ModelType) -> ModelType:
        """
        Lädt ein Objekt neu aus der Datenbank.
        
        Args:
            obj: Model-Instanz
            
        Returns:
            Aktualisierte Model-Instanz
        """
        self.session.refresh(obj)
        return obj
