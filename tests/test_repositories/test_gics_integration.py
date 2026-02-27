# tests/test_repositories/test_gics_integration.py
"""
Tests für die GICS-Integration:
  - ForeignKey tickers.gics_sub_industry_code → gics_reference.sub_industry_code
  - Relationship Ticker.gics_classification → GicsReference
  - Property Ticker.gics_full_path
  - GicsRepository Abfragen
"""

import pytest
from src.models.metadata import Ticker, AssetType, GicsLevel
from src.models.gics import GicsReference
from src.database.gics_repository import GicsRepository
from src.database.ticker_repository import TickerRepository


@pytest.fixture
def gics_it_sector(session):
    """Erstellt GICS-Referenzdaten für den IT-Sektor (exemplarisch)."""
    entries = [
        GicsReference(
            sector_code="45", sector_name="Information Technology",
            industry_group_code="4530", industry_group_name="Semiconductors & Semiconductor Equipment",
            industry_code="453010", industry_name="Semiconductors & Semiconductor Equipment",
            sub_industry_code="45301010", sub_industry_name="Semiconductor Materials & Equipment",
        ),
        GicsReference(
            sector_code="45", sector_name="Information Technology",
            industry_group_code="4530", industry_group_name="Semiconductors & Semiconductor Equipment",
            industry_code="453010", industry_name="Semiconductors & Semiconductor Equipment",
            sub_industry_code="45301020", sub_industry_name="Semiconductors",
        ),
        GicsReference(
            sector_code="45", sector_name="Information Technology",
            industry_group_code="4510", industry_group_name="Software & Services",
            industry_code="451030", industry_name="Software",
            sub_industry_code="45103010", sub_industry_name="Application Software",
        ),
    ]
    session.add_all(entries)
    session.flush()
    return entries


class TestGicsRelationship:
    """Tests für FK + Relationship zwischen Ticker und GicsReference."""

    def test_ticker_with_gics_fk(self, session, gics_it_sector):
        """Ticker mit gültigem GICS-Code → FK-Constraint erfüllt."""
        ticker = Ticker(
            symbol="NVDA",
            name="NVIDIA Corp.",
            asset_type=AssetType.STOCK,
            gics_sub_industry_code="45301020",
            gics_sector_code="45",
            gics_level=GicsLevel.SUB_INDUSTRY,
        )
        session.add(ticker)
        session.flush()

        assert ticker.ticker_id is not None
        assert ticker.gics_sub_industry_code == "45301020"

    def test_gics_classification_relationship(self, session, gics_it_sector):
        """Relationship Ticker.gics_classification gibt GicsReference zurück."""
        ticker = Ticker(
            symbol="NVDA",
            name="NVIDIA Corp.",
            asset_type=AssetType.STOCK,
            gics_sub_industry_code="45301020",
        )
        session.add(ticker)
        session.flush()

        # Relationship laden
        assert ticker.gics_classification is not None
        assert ticker.gics_classification.sub_industry_name == "Semiconductors"
        assert ticker.gics_classification.sector_name == "Information Technology"

    def test_gics_full_path(self, session, gics_it_sector):
        """Property gics_full_path gibt den vollständigen Hierarchie-Pfad zurück."""
        ticker = Ticker(
            symbol="NVDA",
            name="NVIDIA Corp.",
            asset_type=AssetType.STOCK,
            gics_sub_industry_code="45301020",
        )
        session.add(ticker)
        session.flush()

        path = ticker.gics_full_path
        assert path is not None
        assert "Information Technology" in path
        assert "Semiconductors & Semiconductor Equipment" in path
        assert "Semiconductors" in path
        # Format: "Sektor > Industry Group > Industry > Sub-Industry"
        assert path.count(" > ") == 3

    def test_gics_full_path_none_without_code(self, session):
        """Ticker ohne GICS-Code → gics_full_path ist None."""
        ticker = Ticker(
            symbol="EURUSD",
            asset_type=AssetType.FX,
        )
        session.add(ticker)
        session.flush()

        assert ticker.gics_full_path is None

    def test_gics_reference_back_populates(self, session, gics_it_sector):
        """GicsReference.tickers gibt zugehörige Ticker zurück."""
        session.add(Ticker(
            symbol="NVDA", asset_type=AssetType.STOCK,
            gics_sub_industry_code="45301020",
        ))
        session.add(Ticker(
            symbol="AMD", asset_type=AssetType.STOCK,
            gics_sub_industry_code="45301020",
        ))
        session.flush()

        # Über GicsReference → Ticker navigieren
        gics = session.query(GicsReference).filter_by(
            sub_industry_code="45301020"
        ).first()
        assert len(gics.tickers) == 2
        symbols = {t.symbol for t in gics.tickers}
        assert symbols == {"NVDA", "AMD"}


class TestGicsRepository:
    """Tests für GicsRepository Abfragen."""

    def test_get_all_sectors(self, session, gics_it_sector):
        """Gibt alle distinct Sektoren zurück."""
        repo = GicsRepository(session)
        sectors = repo.get_all_sectors()
        assert len(sectors) == 1
        assert sectors[0]["code"] == "45"
        assert sectors[0]["name"] == "Information Technology"

    def test_get_industry_groups_by_sector(self, session, gics_it_sector):
        """Gibt Industry Groups eines Sektors zurück."""
        repo = GicsRepository(session)
        groups = repo.get_industry_groups_by_sector("45")
        assert len(groups) == 2
        codes = {g["code"] for g in groups}
        assert codes == {"4510", "4530"}

    def test_get_by_sub_industry_code(self, session, gics_it_sector):
        """Lookup per Sub-Industry Code."""
        repo = GicsRepository(session)
        result = repo.get_by_sub_industry_code("45301020")
        assert result is not None
        assert result.sub_industry_name == "Semiconductors"

    def test_get_by_sub_industry_code_not_found(self, session, gics_it_sector):
        """Gibt None zurück bei unbekanntem Code."""
        repo = GicsRepository(session)
        assert repo.get_by_sub_industry_code("99999999") is None

    def test_get_tickers_by_sector(self, session, gics_it_sector):
        """Findet Ticker nach Sektor-Code (über denormalisierte Spalte)."""
        repo = GicsRepository(session)
        session.add(Ticker(
            symbol="NVDA", asset_type=AssetType.STOCK,
            gics_sub_industry_code="45301020",
            gics_sector_code="45",
        ))
        session.add(Ticker(
            symbol="MSFT", asset_type=AssetType.STOCK,
            gics_sub_industry_code="45103010",
            gics_sector_code="45",
        ))
        session.flush()

        tickers = repo.get_tickers_by_sector("45")
        assert len(tickers) == 2

    def test_get_etfs_by_sector(self, session, gics_it_sector):
        """Filtert nur ETFs eines Sektors."""
        repo = GicsRepository(session)
        session.add(Ticker(
            symbol="NVDA", asset_type=AssetType.STOCK,
            gics_sector_code="45",
        ))
        session.add(Ticker(
            symbol="SOXX", asset_type=AssetType.ETF,
            gics_sector_code="45",
            gics_sub_industry_code="45301020",
        ))
        session.flush()

        etfs = repo.get_etfs_by_sector("45")
        assert len(etfs) == 1
        assert etfs[0].symbol == "SOXX"

    def test_get_tickers_by_sub_industry(self, session, gics_it_sector):
        """Feingranulare Abfrage nach Sub-Industry."""
        repo = GicsRepository(session)
        session.add(Ticker(
            symbol="NVDA", asset_type=AssetType.STOCK,
            gics_sub_industry_code="45301020",
        ))
        session.add(Ticker(
            symbol="MSFT", asset_type=AssetType.STOCK,
            gics_sub_industry_code="45103010",
        ))
        session.flush()

        tickers = repo.get_tickers_by_sub_industry("45301020")
        assert len(tickers) == 1
        assert tickers[0].symbol == "NVDA"
