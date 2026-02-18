"""Add GICS reference table and extend tickers model

Revision ID: 0002_gics_extension
Revises: 0001_initial
Create Date: 2026-02-18

Änderungen:
- Neue Tabelle: gics_reference (vollständige GICS-Hierarchie als Lookup)
- Erweiterung tickers: GICS Foreign Key + denormalisierte Codes + ETF-Felder
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '0002_gics_extension'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Neue Tabelle: gics_reference
    # ------------------------------------------------------------------
    op.create_table(
        'gics_reference',
        sa.Column('gics_id',                  sa.Integer(),     primary_key=True, autoincrement=True),
        # Sektor-Ebene
        sa.Column('sector_code',              sa.String(2),     nullable=False),
        sa.Column('sector_name',              sa.String(100),   nullable=False),
        # Industry Group-Ebene
        sa.Column('industry_group_code',      sa.String(4),     nullable=False),
        sa.Column('industry_group_name',      sa.String(100),   nullable=False),
        # Industry-Ebene
        sa.Column('industry_code',            sa.String(6),     nullable=False),
        sa.Column('industry_name',            sa.String(100),   nullable=False),
        # Sub-Industry-Ebene (Primärschlüssel der Klassifikation)
        sa.Column('sub_industry_code',        sa.String(8),     nullable=False, unique=True),
        sa.Column('sub_industry_name',        sa.String(200),   nullable=False),
        sa.Column('sub_industry_description', sa.String(1000),  nullable=True),
        # Metadaten
        sa.Column('gics_version',             sa.String(20),    server_default='2024-08'),
        sa.Column('created_at',               sa.DateTime(),    server_default=sa.func.now()),
        sa.Column('updated_at',               sa.DateTime(),    server_default=sa.func.now()),
    )
    op.create_index('idx_gics_sector_code',         'gics_reference', ['sector_code'])
    op.create_index('idx_gics_industry_group_code', 'gics_reference', ['industry_group_code'])
    op.create_index('idx_gics_industry_code',       'gics_reference', ['industry_code'])
    op.create_index('idx_gics_sub_industry_code',   'gics_reference', ['sub_industry_code'])

    # ------------------------------------------------------------------
    # 2. Erweiterung tickers: GICS-Felder
    # ------------------------------------------------------------------
    # GICS Foreign Key (auf sub_industry_code)
    op.add_column('tickers', sa.Column(
        'gics_sub_industry_code',
        sa.String(8),
        sa.ForeignKey('gics_reference.sub_industry_code'),
        nullable=True
    ))
    op.create_index('idx_tickers_gics_sub_industry', 'tickers', ['gics_sub_industry_code'])

    # Auf welcher GICS-Ebene operiert dieses Instrument?
    op.add_column('tickers', sa.Column(
        'gics_level',
        sa.Enum('SECTOR', 'INDUSTRY_GROUP', 'INDUSTRY', 'SUB_INDUSTRY', name='gicslevel'),
        nullable=True
    ))

    # Denormalisierte Codes für schnelle Filterabfragen (ohne JOIN)
    op.add_column('tickers', sa.Column('gics_sector_code',         sa.String(2),  nullable=True))
    op.add_column('tickers', sa.Column('gics_industry_group_code', sa.String(4),  nullable=True))
    op.add_column('tickers', sa.Column('gics_industry_code',       sa.String(6),  nullable=True))
    op.create_index('idx_tickers_gics_sector', 'tickers', ['gics_sector_code'])

    # ------------------------------------------------------------------
    # 3. Erweiterung tickers: ETF-spezifische Felder
    # ------------------------------------------------------------------
    op.add_column('tickers', sa.Column('etf_provider',        sa.String(100),   nullable=True))
    op.add_column('tickers', sa.Column('underlying_index',    sa.String(200),   nullable=True))
    op.add_column('tickers', sa.Column('aum_usd',             sa.Numeric(20, 2), nullable=True))
    op.add_column('tickers', sa.Column('ter_percent',         sa.Numeric(5, 4),  nullable=True))
    op.add_column('tickers', sa.Column(
        'replication_method',
        sa.Enum('PHYSICAL_FULL', 'PHYSICAL_SAMPLING', 'SYNTHETIC', name='etfreplicationmethod'),
        nullable=True
    ))
    op.add_column('tickers', sa.Column('domicile',            sa.String(5),     nullable=True))
    op.add_column('tickers', sa.Column('isin',                sa.String(12),    nullable=True))
    op.create_unique_constraint('uq_tickers_isin', 'tickers', ['isin'])


def downgrade() -> None:
    # ETF-Felder entfernen
    op.drop_constraint('uq_tickers_isin', 'tickers', type_='unique')
    op.drop_column('tickers', 'isin')
    op.drop_column('tickers', 'domicile')
    op.drop_column('tickers', 'replication_method')
    op.drop_column('tickers', 'ter_percent')
    op.drop_column('tickers', 'aum_usd')
    op.drop_column('tickers', 'underlying_index')
    op.drop_column('tickers', 'etf_provider')

    # GICS-Felder entfernen
    op.drop_index('idx_tickers_gics_sector', 'tickers')
    op.drop_column('tickers', 'gics_industry_code')
    op.drop_column('tickers', 'gics_industry_group_code')
    op.drop_column('tickers', 'gics_sector_code')
    op.drop_column('tickers', 'gics_level')
    op.drop_index('idx_tickers_gics_sub_industry', 'tickers')
    op.drop_column('tickers', 'gics_sub_industry_code')

    # gics_reference Tabelle entfernen
    op.drop_index('idx_gics_sub_industry_code', 'gics_reference')
    op.drop_index('idx_gics_industry_code',     'gics_reference')
    op.drop_index('idx_gics_industry_group_code', 'gics_reference')
    op.drop_index('idx_gics_sector_code',       'gics_reference')
    op.drop_table('gics_reference')
