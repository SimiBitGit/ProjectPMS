"""
Ticker Model (erweitert) – Stammdaten für Securities, ETFs und FX
Erweiterung gegenüber Phase 1: GICS-Klassifikation + ETF-spezifische Felder

TODO (Phase 3): GicsReference-Model implementieren und Relationship reaktivieren.
     Suche nach "# GICS_TODO" um alle betroffenen Stellen zu finden.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
datetime.now(timezone.utc)
import enum
from .base import Base


class AssetType(str, enum.Enum):
    STOCK     = "STOCK"
    ETF       = "ETF"
    INDEX     = "INDEX"
    FX        = "FX"
    CRYPTO    = "CRYPTO"
    COMMODITY = "COMMODITY"
    BOND      = "BOND"


class EtfReplicationMethod(str, enum.Enum):
    """Replikationsmethode eines ETFs."""
    PHYSICAL_FULL      = "PHYSICAL_FULL"       # Vollständige physische Replikation
    PHYSICAL_SAMPLING  = "PHYSICAL_SAMPLING"   # Sampling / Optimized
    SYNTHETIC          = "SYNTHETIC"           # Swap-basiert


class GicsLevel(str, enum.Enum):
    """
    Auf welcher GICS-Ebene bildet dieser ETF ab?
    Wichtig für spätere Analysen (Sektor-ETF vs. Sub-Industry-ETF).
    """
    SECTOR         = "SECTOR"
    INDUSTRY_GROUP = "INDUSTRY_GROUP"
    INDUSTRY       = "INDUSTRY"
    SUB_INDUSTRY   = "SUB_INDUSTRY"


class Ticker(Base):
    __tablename__ = 'tickers'

    ticker_id  = Column(Integer, primary_key=True, autoincrement=True)
    symbol     = Column(String(20),  nullable=False, unique=True, index=True)
    name       = Column(String(200))
    exchange   = Column(String(50))
    currency   = Column(String(3))
    asset_type = Column(Enum(AssetType), nullable=False)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ------------------------------------------------------------------
    # GICS-Klassifikation
    # ------------------------------------------------------------------
    # GICS_TODO: ForeignKey-Constraint vorerst deaktiviert (GicsReference-Tabelle
    # existiert noch nicht). Spalte bleibt erhalten, wird in Phase 3 reaktiviert.
    gics_sub_industry_code = Column(
        String(8),
        # ForeignKey('gics_reference.sub_industry_code'),  # GICS_TODO: reaktivieren
        nullable=True,
        index=True
    )

    gics_level = Column(Enum(GicsLevel), nullable=True)

    # Denormalisierte Codes der übergeordneten GICS-Ebenen (Performance-Optimierung)
    gics_sector_code         = Column(String(2),  nullable=True, index=True)
    gics_industry_group_code = Column(String(4),  nullable=True)
    gics_industry_code       = Column(String(6),  nullable=True)

    # ------------------------------------------------------------------
    # ETF-spezifische Felder – nur relevant wenn asset_type = ETF
    # ------------------------------------------------------------------
    etf_provider       = Column(String(100), nullable=True)   # z.B. "iShares", "Invesco"
    underlying_index   = Column(String(200), nullable=True)   # z.B. "MSCI World Index"
    aum_usd            = Column(Numeric(20, 2), nullable=True) # AUM in USD
    ter_percent        = Column(Numeric(5, 4),  nullable=True) # Gesamtkostenquote in %
    replication_method = Column(Enum(EtfReplicationMethod), nullable=True)
    domicile           = Column(String(5),  nullable=True)    # z.B. "IE", "US", "DE"
    isin               = Column(String(12), nullable=True, unique=True)

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    market_data    = relationship("MarketData",    back_populates="ticker")
    processed_data = relationship("ProcessedData", back_populates="ticker")

    # GICS_TODO: Reaktivieren sobald GicsReference-Model existiert (Phase 3)
    # gics_classification = relationship(
    #     "GicsReference",
    #     back_populates="tickers",
    #     foreign_keys=[gics_sub_industry_code]
    # )

    def __repr__(self):
        return f"<Ticker(symbol='{self.symbol}', type='{self.asset_type}', name='{self.name}')>"

    @property
    def gics_full_path(self) -> str | None:
        """Gibt den GICS-Pfad zurück. Aktiv sobald GicsReference implementiert ist."""
        # GICS_TODO: return self.gics_classification.full_path if self.gics_classification else None
        return None
