"""
TickerService — Verwendungsbeispiele

Zeigt wie Stocks, Sektor-ETFs und Sub-Industry-ETFs erfasst werden.
Ausführen: python -m src.services.ticker_service_examples
"""

from decimal import Decimal
from src.models.base import get_session
from src.models.metadata import AssetType, GicsLevel, EtfReplicationMethod
from src.database.gics_repository import GicsRepository
from src.services.ticker_service import TickerService, TickerCreateDTO, TickerUpdateDTO


def main():
    session = get_session()

    # 0. GICS-Seed-Daten laden (einmalig nötig)
    gics_repo = GicsRepository(session)
    count = gics_repo.seed_gics_data()
    print(f"GICS-Daten geladen: {count} Einträge")

    service = TickerService(session)

    # ------------------------------------------------------------------
    # Beispiel 1: Einzelne Aktie (Stock) erfassen
    # sub_industry_code angeben → alle GICS-Codes werden automatisch befüllt
    # ------------------------------------------------------------------
    aapl = service.create_ticker(TickerCreateDTO(
        symbol="AAPL",
        asset_type=AssetType.STOCK,
        name="Apple Inc.",
        exchange="NASDAQ",
        currency="USD",
        isin="US0378331005",
        gics_sub_industry_code="45202030",  # Technology Hardware, Storage & Peripherals
    ))
    print(f"\nStock erstellt: {aapl.symbol}")
    print(f"  GICS-Pfad:  {aapl.gics_full_path}")
    print(f"  Sektor:     {aapl.gics_sector_code}")
    print(f"  Ind.Group:  {aapl.gics_industry_group_code}")

    # ------------------------------------------------------------------
    # Beispiel 2: Sektor-ETF (breiter IT-Sektor, z.B. XLK)
    # Nur sector_code + gics_level=SECTOR setzen
    # ------------------------------------------------------------------
    xlk = service.create_ticker(TickerCreateDTO(
        symbol="XLK",
        asset_type=AssetType.ETF,
        name="Technology Select Sector SPDR Fund",
        exchange="NYSE",
        currency="USD",
        isin="US81369Y8030",
        gics_sector_code="45",              # Information Technology
        gics_level=GicsLevel.SECTOR,
        etf_provider="SPDR",
        underlying_index="Technology Select Sector Index",
        ter_percent=Decimal("0.0009"),      # 0.09%
        aum_usd=Decimal("65000000000"),     # ~65 Mrd. USD
        replication_method=EtfReplicationMethod.PHYSICAL_FULL,
        domicile="US",
    ))
    print(f"\nSektor-ETF erstellt: {xlk.symbol}")
    print(f"  Sektor:     {xlk.gics_sector_code} (Level: {xlk.gics_level})")
    print(f"  Provider:   {xlk.etf_provider}")
    print(f"  TER:        {xlk.ter_percent}%")

    # ------------------------------------------------------------------
    # Beispiel 3: Sub-Industry-ETF (Semiconductors, z.B. SOXX)
    # sub_industry_code angeben → exakt wie bei Stocks
    # ------------------------------------------------------------------
    soxx = service.create_ticker(TickerCreateDTO(
        symbol="SOXX",
        asset_type=AssetType.ETF,
        name="iShares Semiconductor ETF",
        exchange="NASDAQ",
        currency="USD",
        isin="US4642876449",
        gics_sub_industry_code="45301020",  # Semiconductors
        etf_provider="iShares",
        underlying_index="ICE Semiconductor Index",
        ter_percent=Decimal("0.0035"),      # 0.35%
        aum_usd=Decimal("12000000000"),
        replication_method=EtfReplicationMethod.PHYSICAL_FULL,
        domicile="US",
    ))
    print(f"\nSub-Industry-ETF erstellt: {soxx.symbol}")
    print(f"  GICS-Pfad:  {soxx.gics_full_path}")
    print(f"  Level:      {soxx.gics_level}")

    # ------------------------------------------------------------------
    # Beispiel 4: FX-Paar (kein GICS)
    # ------------------------------------------------------------------
    eurusd = service.create_ticker(TickerCreateDTO(
        symbol="EURUSD",
        asset_type=AssetType.FX,
        name="Euro / US Dollar",
        currency="USD",
        # Kein GICS für FX
    ))
    print(f"\nFX erstellt: {eurusd.symbol} (GICS: {eurusd.gics_sector_code})")

    # ------------------------------------------------------------------
    # Beispiel 5: Ticker aktualisieren (AUM-Update)
    # ------------------------------------------------------------------
    updated = service.update_ticker("SOXX", TickerUpdateDTO(
        aum_usd=Decimal("13500000000"),
    ))
    print(f"\nAUM aktualisiert: {updated.symbol} → {updated.aum_usd:,.0f} USD")

    # ------------------------------------------------------------------
    # Beispiel 6: Alle ETFs im IT-Sektor abfragen
    # ------------------------------------------------------------------
    it_etfs = service.get_etfs_by_sector("45")
    print(f"\nETFs im IT-Sektor (45): {[t.symbol for t in it_etfs]}")

    session.close()


if __name__ == "__main__":
    main()
