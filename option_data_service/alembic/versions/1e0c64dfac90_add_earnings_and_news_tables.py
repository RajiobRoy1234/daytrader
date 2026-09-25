"""add earnings and news tables

Revision ID: 1e0c64dfac90
Revises: 99b70f880901
Create Date: 2026-07-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1e0c64dfac90'
down_revision: Union[str, None] = '99b70f880901'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('earnings_reports',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('symbol_id', sa.Integer(), nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('report_date', sa.Date(), nullable=False),
    sa.Column('release_time', sa.DateTime(timezone=True), nullable=True),
    sa.Column('estimated_eps', sa.Numeric(precision=18, scale=6), nullable=True),
    sa.Column('reported_eps', sa.Numeric(precision=18, scale=6), nullable=True),
    sa.Column('revenue', sa.Numeric(precision=18, scale=6), nullable=True),
    sa.Column('estimated_revenue', sa.Numeric(precision=18, scale=6), nullable=True),
    sa.Column('currency', sa.String(length=8), nullable=True),
    sa.Column('guidance', sa.Text(), nullable=True),
    sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['source_id'], ['data_sources.id'], ),
    sa.ForeignKeyConstraint(['symbol_id'], ['symbols.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('symbol_id', 'source_id', 'report_date', name='uq_earnings_report')
    )
    op.create_index(op.f('ix_earnings_reports_symbol_id'), 'earnings_reports', ['symbol_id'], unique=False)
    op.create_index(op.f('ix_earnings_reports_source_id'), 'earnings_reports', ['source_id'], unique=False)
    op.create_index('ix_earnings_reports_symbol_date', 'earnings_reports', ['symbol_id', 'report_date'], unique=False)

    op.create_table('news_articles',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('source_article_id', sa.String(length=128), nullable=False),
    sa.Column('title', sa.String(length=1024), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('url', sa.String(length=2048), nullable=True),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('author', sa.String(length=255), nullable=True),
    sa.Column('sentiment_score', sa.Numeric(precision=9, scale=6), nullable=True),
    sa.Column('sentiment_label', sa.String(length=32), nullable=True),
    sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['source_id'], ['data_sources.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source_id', 'source_article_id', name='uq_news_article_source')
    )
    op.create_index(op.f('ix_news_articles_source_id'), 'news_articles', ['source_id'], unique=False)
    op.create_index(op.f('ix_news_articles_source_article_id'), 'news_articles', ['source_article_id'], unique=False)
    op.create_index('ix_news_articles_published_at', 'news_articles', ['published_at'], unique=False)

    op.create_table('news_mentions',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('article_id', sa.BigInteger(), nullable=False),
    sa.Column('symbol_id', sa.Integer(), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('relevance_score', sa.Numeric(precision=9, scale=6), nullable=True),
    sa.Column('is_primary', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['article_id'], ['news_articles.id'], ),
    sa.ForeignKeyConstraint(['symbol_id'], ['symbols.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('article_id', 'symbol_id', name='uq_news_mention')
    )
    op.create_index(op.f('ix_news_mentions_article_id'), 'news_mentions', ['article_id'], unique=False)
    op.create_index(op.f('ix_news_mentions_symbol_id'), 'news_mentions', ['symbol_id'], unique=False)
    op.create_index('ix_news_mentions_symbol_time', 'news_mentions', ['symbol_id', 'published_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_news_mentions_symbol_time', table_name='news_mentions')
    op.drop_index(op.f('ix_news_mentions_symbol_id'), table_name='news_mentions')
    op.drop_index(op.f('ix_news_mentions_article_id'), table_name='news_mentions')
    op.drop_table('news_mentions')

    op.drop_index('ix_news_articles_published_at', table_name='news_articles')
    op.drop_index(op.f('ix_news_articles_source_article_id'), table_name='news_articles')
    op.drop_index(op.f('ix_news_articles_source_id'), table_name='news_articles')
    op.drop_table('news_articles')

    op.drop_index('ix_earnings_reports_symbol_date', table_name='earnings_reports')
    op.drop_index(op.f('ix_earnings_reports_source_id'), table_name='earnings_reports')
    op.drop_index(op.f('ix_earnings_reports_symbol_id'), table_name='earnings_reports')
    op.drop_table('earnings_reports')
