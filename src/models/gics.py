"""
GICS (Global Industry Classification Standard) Referenztabelle
Quelle: MSCI GICS Methodology, August 2024

Hierarchie: Sektor (2) → Industry Group (4) → Industry (6) → Sub-Industry (8)
"""

from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base


class GicsReference(Base):
    """
    Vollständige GICS-Hierarchie als Lookup-Tabelle.
    Jede Zeile repräsentiert eine Sub-Industry (unterste Ebene),
    enthält aber den vollständigen Pfad durch alle Hierarchie-Ebenen.
    """
    __tablename__ = 'gics_reference'

    gics_id = Column(Integer, primary_key=True, autoincrement=True)

    # Ebene 1: Sektor (2-stellig)
    sector_code        = Column(String(2),   nullable=False, index=True)
    sector_name        = Column(String(100), nullable=False)

    # Ebene 2: Industry Group (4-stellig)
    industry_group_code = Column(String(4),  nullable=False, index=True)
    industry_group_name = Column(String(100), nullable=False)

    # Ebene 3: Industry (6-stellig)
    industry_code      = Column(String(6),   nullable=False, index=True)
    industry_name      = Column(String(100), nullable=False)

    # Ebene 4: Sub-Industry (8-stellig) — Primary Key der Klassifikation
    sub_industry_code  = Column(String(8),   nullable=False, unique=True, index=True)
    sub_industry_name  = Column(String(200), nullable=False)
    sub_industry_description = Column(String(1000))

    # Metadaten
    gics_version       = Column(String(20), default='2024-08')  # GICS-Version
    created_at         = Column(DateTime, default=datetime.utcnow)
    updated_at         = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tickers = relationship("Ticker", back_populates="gics_classification")

    def __repr__(self):
        return (
            f"<GicsReference("
            f"sector='{self.sector_code} {self.sector_name}', "
            f"sub_industry='{self.sub_industry_code} {self.sub_industry_name}')>"
        )

    @property
    def full_path(self) -> str:
        """Gibt den vollständigen Hierarchie-Pfad zurück."""
        return (
            f"{self.sector_name} > "
            f"{self.industry_group_name} > "
            f"{self.industry_name} > "
            f"{self.sub_industry_name}"
        )
