"""add companies cik, indices, index constituents, corporate actions

Revision ID: 99b70f880901
Revises: e436ad52e8f4
Create Date: 2026-07-24 21:16:06.518106

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '99b70f880901'
down_revision: Union[str, None] = 'e436ad52e8f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# NOTE: autogenerate also proposed dropping/recreating every monthly partition child table
# (option_quotes_2026_06, stock_ticks_2026_07, ...) because those are created at runtime by
# app/partitioning.py via raw DDL, not declared as SQLAlchemy Table objects - Alembic has no
# way to know they're expected to exist outside its metadata. That noise has been stripped
# from this migration by hand; only the real schema changes below are applied.


def upgrade() -> None:
    op.create_table('indices',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', name='uq_index_code')
    )
    op.create_index(op.f('ix_indices_code'), 'indices', ['code'], unique=False)
    op.create_table('corporate_actions',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('symbol_id', sa.Integer(), nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('action_type', sa.String(length=16), nullable=False),
    sa.Column('effective_date', sa.Date(), nullable=False),
    sa.Column('split_ratio_from', sa.Numeric(precision=12, scale=4), nullable=True),
    sa.Column('split_ratio_to', sa.Numeric(precision=12, scale=4), nullable=True),
    sa.Column('dividend_amount', sa.Numeric(precision=18, scale=6), nullable=True),
    sa.Column('dividend_currency', sa.String(length=8), nullable=True),
    sa.Column('details', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("action_type in ('split','dividend','spinoff','merger','name_change','ticker_change')", name='ck_corporate_action_type'),
    sa.ForeignKeyConstraint(['source_id'], ['data_sources.id'], ),
    sa.ForeignKeyConstraint(['symbol_id'], ['symbols.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('symbol_id', 'source_id', 'action_type', 'effective_date', name='uq_corporate_action')
    )
    op.create_index('ix_corporate_actions_symbol_date', 'corporate_actions', ['symbol_id', 'effective_date'], unique=False)
    op.create_table('index_constituents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('index_id', sa.Integer(), nullable=False),
    sa.Column('symbol_id', sa.Integer(), nullable=False),
    sa.Column('added_date', sa.Date(), nullable=True),
    sa.Column('removed_date', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['index_id'], ['indices.id'], ),
    sa.ForeignKeyConstraint(['symbol_id'], ['symbols.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_index_constituents_index_current', 'index_constituents', ['index_id', 'removed_date'], unique=False)
    op.create_index('ix_index_constituents_symbol', 'index_constituents', ['symbol_id'], unique=False)
    op.add_column('companies', sa.Column('cik', sa.String(length=10), nullable=True))
    op.create_index(op.f('ix_companies_cik'), 'companies', ['cik'], unique=False)
    op.create_unique_constraint('uq_company_name', 'companies', ['name'])


def downgrade() -> None:
    op.drop_constraint('uq_company_name', 'companies', type_='unique')
    op.drop_index(op.f('ix_companies_cik'), table_name='companies')
    op.drop_column('companies', 'cik')
    op.drop_index('ix_index_constituents_symbol', table_name='index_constituents')
    op.drop_index('ix_index_constituents_index_current', table_name='index_constituents')
    op.drop_table('index_constituents')
    op.drop_index('ix_corporate_actions_symbol_date', table_name='corporate_actions')
    op.drop_table('corporate_actions')
    op.drop_index(op.f('ix_indices_code'), table_name='indices')
    op.drop_table('indices')
