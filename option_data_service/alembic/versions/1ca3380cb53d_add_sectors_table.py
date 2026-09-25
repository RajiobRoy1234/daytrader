"""add sectors table

Revision ID: 1ca3380cb53d
Revises: 1e0c64dfac90
Create Date: 2026-07-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '1ca3380cb53d'
down_revision: Union[str, None] = '1e0c64dfac90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('sectors',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('benchmark_symbol_id', sa.Integer(), nullable=True),
    sa.Column('display_order', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['benchmark_symbol_id'], ['symbols.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', name='uq_sector_code')
    )
    op.create_index(op.f('ix_sectors_code'), 'sectors', ['code'], unique=False)

    op.add_column('companies', sa.Column('sector_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_companies_sector_id'), 'companies', ['sector_id'], unique=False)
    op.create_foreign_key('fk_companies_sector_id', 'companies', 'sectors', ['sector_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_companies_sector_id', 'companies', type_='foreignkey')
    op.drop_index(op.f('ix_companies_sector_id'), table_name='companies')
    op.drop_column('companies', 'sector_id')

    op.drop_index(op.f('ix_sectors_code'), table_name='sectors')
    op.drop_table('sectors')
