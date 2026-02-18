"""
GicsRepository — Data Access Layer für GICS-Referenzdaten und GICS-basierte Ticker-Abfragen
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, distinct

from src.models.gics import GicsReference
from src.models.metadata import Ticker, AssetType
from src.models.gics_seed_data import GICS_DATA


class GicsRepository:
    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # Lookup: GICS-Hierarchie abfragen
    # ------------------------------------------------------------------

    def get_all_sectors(self) -> List[dict]:
        """Gibt alle 11 Sektoren zurück (distinct)."""
        rows = (
            self.session.query(
                GicsReference.sector_code,
                GicsReference.sector_name
            )
            .distinct()
            .order_by(GicsReference.sector_code)
            .all()
        )
        return [{"code": r.sector_code, "name": r.sector_name} for r in rows]

    def get_industry_groups_by_sector(self, sector_code: str) -> List[dict]:
        """Gibt alle Industry Groups eines Sektors zurück."""
        rows = (
            self.session.query(
                GicsReference.industry_group_code,
                GicsReference.industry_group_name
            )
            .filter(GicsReference.sector_code == sector_code)
            .distinct()
            .order_by(GicsReference.industry_group_code)
            .all()
        )
        return [{"code": r.industry_group_code, "name": r.industry_group_name} for r in rows]

    def get_industries_by_group(self, industry_group_code: str) -> List[dict]:
        """Gibt alle Industries einer Industry Group zurück."""
        rows = (
            self.session.query(
                GicsReference.industry_code,
                GicsReference.industry_name
            )
            .filter(GicsReference.industry_group_code == industry_group_code)
            .distinct()
            .order_by(GicsReference.industry_code)
            .all()
        )
        return [{"code": r.industry_code, "name": r.industry_name} for r in rows]

    def get_sub_industries_by_industry(self, industry_code: str) -> List[GicsReference]:
        """Gibt alle Sub-Industries einer Industry zurück."""
        return (
            self.session.query(GicsReference)
            .filter(GicsReference.industry_code == industry_code)
            .order_by(GicsReference.sub_industry_code)
            .all()
        )

    def get_by_sub_industry_code(self, sub_industry_code: str) -> Optional[GicsReference]:
        """Lookup per Sub-Industry Code (8-stellig)."""
        return (
            self.session.query(GicsReference)
            .filter(GicsReference.sub_industry_code == sub_industry_code)
            .first()
        )

    # ------------------------------------------------------------------
    # Ticker-Abfragen nach GICS-Klassifikation
    # ------------------------------------------------------------------

    def get_tickers_by_sector(
        self,
        sector_code: str,
        asset_type: Optional[AssetType] = None
    ) -> List[Ticker]:
        """
        Alle Ticker eines Sektors.
        Optional gefiltert nach Asset-Type (z.B. nur ETFs).
        """
        q = (
            self.session.query(Ticker)
            .filter(
                Ticker.gics_sector_code == sector_code,
                Ticker.is_active == True
            )
        )
        if asset_type:
            q = q.filter(Ticker.asset_type == asset_type)
        return q.order_by(Ticker.symbol).all()

    def get_tickers_by_industry_group(
        self,
        industry_group_code: str,
        asset_type: Optional[AssetType] = None
    ) -> List[Ticker]:
        """Alle Ticker einer Industry Group."""
        q = (
            self.session.query(Ticker)
            .filter(
                Ticker.gics_industry_group_code == industry_group_code,
                Ticker.is_active == True
            )
        )
        if asset_type:
            q = q.filter(Ticker.asset_type == asset_type)
        return q.order_by(Ticker.symbol).all()

    def get_tickers_by_sub_industry(
        self,
        sub_industry_code: str,
        asset_type: Optional[AssetType] = None
    ) -> List[Ticker]:
        """Alle Ticker einer Sub-Industry — feingranularste Abfrage."""
        q = (
            self.session.query(Ticker)
            .filter(
                Ticker.gics_sub_industry_code == sub_industry_code,
                Ticker.is_active == True
            )
        )
        if asset_type:
            q = q.filter(Ticker.asset_type == asset_type)
        return q.order_by(Ticker.symbol).all()

    def get_etfs_by_sector(self, sector_code: str) -> List[Ticker]:
        """Kurzform: Alle ETFs eines Sektors."""
        return self.get_tickers_by_sector(sector_code, asset_type=AssetType.ETF)

    # ------------------------------------------------------------------
    # Seed-Daten laden
    # ------------------------------------------------------------------

    def seed_gics_data(self) -> int:
        """
        Befüllt die gics_reference Tabelle mit den GICS-Daten aus gics_seed_data.py.
        Idempotent: überspringt bereits vorhandene Sub-Industry-Codes.
        Gibt die Anzahl neu eingefügter Einträge zurück.
        """
        inserted = 0
        for entry in GICS_DATA:
            existing = self.get_by_sub_industry_code(entry["sub_industry_code"])
            if existing:
                continue
            record = GicsReference(
                sector_code=entry["sector_code"],
                sector_name=entry["sector_name"],
                industry_group_code=entry["industry_group_code"],
                industry_group_name=entry["industry_group_name"],
                industry_code=entry["industry_code"],
                industry_name=entry["industry_name"],
                sub_industry_code=entry["sub_industry_code"],
                sub_industry_name=entry["sub_industry_name"],
                sub_industry_description=entry.get("sub_industry_description"),
            )
            self.session.add(record)
            inserted += 1
        self.session.commit()
        return inserted
