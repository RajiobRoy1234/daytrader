from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

PRICE_TYPE = lambda: Numeric(18, 6)  # noqa: E731 - fixed precision for financial values, not float

# Tables partitioned by RANGE on their time column, and the column each is partitioned on.
# app/partitioning.py and the initial Alembic migration both read this to create/manage
# the actual child partitions (the ORM's create_all only creates the empty parent table).
PARTITIONED_TABLES = {
    "option_quotes": "quote_time",
    "stock_ticks": "tick_time",
    "option_ticks": "tick_time",
}


class DataSource(Base):
    """A vendor/feed a row of data can come from (bloomberg, cboe, schwab, yahoo, ...)."""

    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("name", name="uq_company_name"),)

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    legal_name = Column(String(255))
    cik = Column(String(10), index=True)  # SEC Central Index Key, zero-padded to 10 digits
    sector = Column(String(128))  # raw vendor string, kept as-is even where sector_id can't resolve it
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=True, index=True)
    industry = Column(String(128))
    country = Column(String(64))
    currency = Column(String(8))
    website = Column(String(255))
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    symbols = relationship("Symbol", back_populates="company")
    canonical_sector = relationship("Sector", back_populates="companies")


class Symbol(Base):
    """Canonical tradable instrument (equity, ETF, index, ...). Each vendor's own ticker
    spelling for this instrument is stored in SymbolSourceMap rather than here."""

    __tablename__ = "symbols"
    __table_args__ = (
        UniqueConstraint("ticker", name="uq_symbol_ticker"),
        CheckConstraint("asset_type in ('equity','etf','index','future','other')", name="ck_symbol_asset_type"),
    )

    id = Column(Integer, primary_key=True)
    ticker = Column(String(32), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    exchange = Column(String(32))
    asset_type = Column(String(16), nullable=False, default="equity")
    currency = Column(String(8), default="USD")
    is_active = Column(Boolean, default=True, nullable=False)
    listed_date = Column(Date)
    delisted_date = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    company = relationship("Company", back_populates="symbols")
    source_map = relationship("SymbolSourceMap", back_populates="symbol")


class SymbolSourceMap(Base):
    """Maps a canonical Symbol to each vendor's own identifier, e.g. Bloomberg 'AAPL US Equity',
    Schwab 'AAPL', CBOE's own symbology - so ingestion can resolve any feed to one internal row."""

    __tablename__ = "symbol_source_map"
    __table_args__ = (
        UniqueConstraint("source_id", "source_symbol", name="uq_symbol_source_symbol"),
        UniqueConstraint("symbol_id", "source_id", name="uq_symbol_source_once"),
    )

    id = Column(Integer, primary_key=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False, index=True)
    source_symbol = Column(String(64), nullable=False)

    symbol = relationship("Symbol", back_populates="source_map")
    source = relationship("DataSource")


class Sector(Base):
    """Canonical GICS sector (Information Technology, Financials, ...). companies.sector_id
    points here; companies.sector keeps whatever raw string the vendor sent, since not every
    vendor spells sectors the same way and not every company maps cleanly to one of the 11.
    benchmark_symbol_id is an ordinary Symbol (asset_type='index') whose price_history drives
    the sector's displayed price/change - same mechanism as any other tracked index, not a
    separate price-storage path."""

    __tablename__ = "sectors"
    __table_args__ = (UniqueConstraint("code", name="uq_sector_code"),)

    id = Column(Integer, primary_key=True)
    code = Column(String(32), nullable=False, index=True)  # 'information_technology', 'financials', ...
    name = Column(String(128), nullable=False)
    benchmark_symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=True)
    display_order = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    benchmark_symbol = relationship("Symbol")
    companies = relationship("Company", back_populates="canonical_sector")


class PriceBar(Base):
    """OHLCV bar for a symbol at any interval (1d/1h/5m/1m/...), from any source."""

    __tablename__ = "price_history"
    __table_args__ = (
        UniqueConstraint("symbol_id", "source_id", "interval", "bar_time", name="uq_price_bar"),
        Index("ix_price_history_symbol_time", "symbol_id", "interval", "bar_time"),
    )

    id = Column(BigInteger, primary_key=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)
    interval = Column(String(8), nullable=False)  # '1d' | '1h' | '5m' | '1m' | ...
    bar_time = Column(DateTime(timezone=True), nullable=False)
    open = Column(PRICE_TYPE())
    high = Column(PRICE_TYPE())
    low = Column(PRICE_TYPE())
    close = Column(PRICE_TYPE())
    adj_close = Column(PRICE_TYPE())
    volume = Column(BigInteger)

    symbol = relationship("Symbol")
    source = relationship("DataSource")


class OptionContract(Base):
    """One row per unique option contract (underlying/expiration/strike/type), independent
    of any vendor's own contract symbol - the option-chain 'static' definition."""

    __tablename__ = "option_contracts"
    __table_args__ = (
        UniqueConstraint("underlying_symbol_id", "expiration", "strike", "option_type", name="uq_option_contract"),
        CheckConstraint("option_type in ('call','put')", name="ck_option_contract_type"),
    )

    id = Column(Integer, primary_key=True)
    underlying_symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False, index=True)
    expiration = Column(Date, nullable=False, index=True)
    strike = Column(PRICE_TYPE(), nullable=False)
    option_type = Column(String(4), nullable=False)
    multiplier = Column(Integer, nullable=False, default=100)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    underlying = relationship("Symbol")
    source_map = relationship("OptionContractSourceMap", back_populates="contract")


class OptionContractSourceMap(Base):
    """Maps a canonical OptionContract to each vendor's own option symbol (OCC/Bloomberg/
    Schwab/CBOE all spell option contracts differently)."""

    __tablename__ = "option_contract_source_map"
    __table_args__ = (
        UniqueConstraint("source_id", "source_symbol", name="uq_option_contract_source_symbol"),
        UniqueConstraint("option_contract_id", "source_id", name="uq_option_contract_source_once"),
    )

    id = Column(Integer, primary_key=True)
    option_contract_id = Column(Integer, ForeignKey("option_contracts.id"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False, index=True)
    source_symbol = Column(String(64), nullable=False)

    contract = relationship("OptionContract", back_populates="source_map")
    source = relationship("DataSource")


class OptionQuote(Base):
    """A timestamped option-chain snapshot for one contract from one source. Querying the
    latest quote_time per contract gives the current chain; a time range gives its history."""

    __tablename__ = "option_quotes"
    __table_args__ = (
        UniqueConstraint("option_contract_id", "source_id", "quote_time", name="uq_option_quote"),
        Index("ix_option_quotes_contract_time", "option_contract_id", "quote_time"),
        {"postgresql_partition_by": "RANGE (quote_time)"},
    )

    # quote_time must be part of the primary key: Postgres requires every unique index on a
    # partitioned table (PK included) to contain the partition key column.
    id = Column(BigInteger, Identity(), primary_key=True)
    option_contract_id = Column(Integer, ForeignKey("option_contracts.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)
    quote_time = Column(DateTime(timezone=True), nullable=False, primary_key=True)
    bid = Column(PRICE_TYPE())
    ask = Column(PRICE_TYPE())
    last_price = Column(PRICE_TYPE())
    volume = Column(BigInteger)
    open_interest = Column(BigInteger)
    implied_volatility = Column(Numeric(9, 6))
    delta = Column(Numeric(9, 6))
    gamma = Column(Numeric(9, 6))
    theta = Column(Numeric(9, 6))
    vega = Column(Numeric(9, 6))
    rho = Column(Numeric(9, 6))

    contract = relationship("OptionContract")
    source = relationship("DataSource")


class StockTick(Base):
    """Raw trade/quote tick for a stock. BigInteger PK + BRIN time index keep this cheap to
    store and scan at tick volume; see README for the partitioning upgrade path."""

    __tablename__ = "stock_ticks"
    __table_args__ = (
        CheckConstraint("tick_type in ('trade','quote')", name="ck_stock_tick_type"),
        Index("ix_stock_ticks_symbol_time", "symbol_id", "tick_time"),
        Index("ix_stock_ticks_time_brin", "tick_time", postgresql_using="brin"),
        {"postgresql_partition_by": "RANGE (tick_time)"},
    )

    id = Column(BigInteger, Identity(), primary_key=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)
    tick_time = Column(DateTime(timezone=True), nullable=False, primary_key=True)
    tick_type = Column(String(8), nullable=False, default="trade")
    price = Column(PRICE_TYPE())
    size = Column(BigInteger)
    bid = Column(PRICE_TYPE())
    ask = Column(PRICE_TYPE())
    exchange = Column(String(16))
    conditions = Column(String(64))

    symbol = relationship("Symbol")
    source = relationship("DataSource")


class OptionTick(Base):
    """Raw trade/quote tick for an option contract. Same storage/query shape as StockTick."""

    __tablename__ = "option_ticks"
    __table_args__ = (
        CheckConstraint("tick_type in ('trade','quote')", name="ck_option_tick_type"),
        Index("ix_option_ticks_contract_time", "option_contract_id", "tick_time"),
        Index("ix_option_ticks_time_brin", "tick_time", postgresql_using="brin"),
        {"postgresql_partition_by": "RANGE (tick_time)"},
    )

    id = Column(BigInteger, Identity(), primary_key=True)
    option_contract_id = Column(Integer, ForeignKey("option_contracts.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)
    tick_time = Column(DateTime(timezone=True), nullable=False, primary_key=True)
    tick_type = Column(String(8), nullable=False, default="trade")
    price = Column(PRICE_TYPE())
    size = Column(BigInteger)
    bid = Column(PRICE_TYPE())
    ask = Column(PRICE_TYPE())
    exchange = Column(String(16))
    conditions = Column(String(64))

    contract = relationship("OptionContract")
    source = relationship("DataSource")


class EarningsReport(Base):
    """Structured earnings release data for a symbol. Keyed with source_id, like every other
    vendor-data table here, so two vendors' reports for the same symbol/date don't collide."""

    __tablename__ = "earnings_reports"
    __table_args__ = (
        UniqueConstraint("symbol_id", "source_id", "report_date", name="uq_earnings_report"),
        Index("ix_earnings_reports_symbol_date", "symbol_id", "report_date"),
    )

    id = Column(BigInteger, primary_key=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False, index=True)
    report_date = Column(Date, nullable=False)
    release_time = Column(DateTime(timezone=True))
    estimated_eps = Column(PRICE_TYPE())
    reported_eps = Column(PRICE_TYPE())
    revenue = Column(PRICE_TYPE())
    estimated_revenue = Column(PRICE_TYPE())
    currency = Column(String(8), default="USD")
    guidance = Column(Text)
    raw_payload = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    symbol = relationship("Symbol")
    source = relationship("DataSource")


class NewsArticle(Base):
    """News article metadata and content, one row per vendor's own article id."""

    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint("source_id", "source_article_id", name="uq_news_article_source"),
        Index("ix_news_articles_published_at", "published_at"),
    )

    id = Column(BigInteger, primary_key=True)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False, index=True)
    source_article_id = Column(String(128), nullable=False, index=True)
    title = Column(String(1024), nullable=False)
    summary = Column(Text)
    url = Column(String(2048))
    published_at = Column(DateTime(timezone=True), nullable=False)
    author = Column(String(255))
    sentiment_score = Column(Numeric(9, 6))
    sentiment_label = Column(String(32))
    raw_payload = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    mentions = relationship("NewsMention", back_populates="article")
    source = relationship("DataSource")


class NewsMention(Base):
    """Association between a news article and a symbol it mentions. published_at is
    denormalized from the article so a symbol's news feed can be time-ranged without a join,
    the same tradeoff option_quotes/stock_ticks make by keying on their own time column."""

    __tablename__ = "news_mentions"
    __table_args__ = (
        UniqueConstraint("article_id", "symbol_id", name="uq_news_mention"),
        Index("ix_news_mentions_symbol_time", "symbol_id", "published_at"),
    )

    id = Column(BigInteger, primary_key=True)
    article_id = Column(BigInteger, ForeignKey("news_articles.id"), nullable=False, index=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False, index=True)
    published_at = Column(DateTime(timezone=True), nullable=False)
    relevance_score = Column(Numeric(9, 6))
    is_primary = Column(Boolean, default=False, nullable=False)

    article = relationship("NewsArticle", back_populates="mentions")
    symbol = relationship("Symbol")


class MarketIndex(Base):
    """A tracked index (S&P 500, DJIA, ...). Named MarketIndex, not Index, to avoid colliding
    with sqlalchemy.Index (used throughout this file for DB indexes)."""

    __tablename__ = "indices"
    __table_args__ = (UniqueConstraint("code", name="uq_index_code"),)

    id = Column(Integer, primary_key=True)
    code = Column(String(32), nullable=False, index=True)  # 'SP500', 'DJIA'
    name = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IndexConstituent(Base):
    """One membership span for a symbol in an index. `removed_date IS NULL` means it's a
    current member; a symbol that leaves and later rejoins gets a second row rather than
    reusing the first, so membership history is preserved rather than overwritten."""

    __tablename__ = "index_constituents"
    __table_args__ = (
        Index("ix_index_constituents_index_current", "index_id", "removed_date"),
        Index("ix_index_constituents_symbol", "symbol_id"),
    )

    id = Column(Integer, primary_key=True)
    index_id = Column(Integer, ForeignKey("indices.id"), nullable=False)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False)
    added_date = Column(Date)  # nullable - Wikipedia doesn't have a known add date for every row
    removed_date = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    index = relationship("MarketIndex")
    symbol = relationship("Symbol")


class CorporateAction(Base):
    """A split, dividend, or other corporate action for a symbol. Split/dividend get typed
    columns since they're the common cases with well-defined fields; rarer types (spinoff,
    merger, name_change, ticker_change) fall back to free-text `details`."""

    __tablename__ = "corporate_actions"
    __table_args__ = (
        UniqueConstraint("symbol_id", "source_id", "action_type", "effective_date", name="uq_corporate_action"),
        CheckConstraint(
            "action_type in ('split','dividend','spinoff','merger','name_change','ticker_change')",
            name="ck_corporate_action_type",
        ),
        Index("ix_corporate_actions_symbol_date", "symbol_id", "effective_date"),
    )

    id = Column(BigInteger, primary_key=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)
    action_type = Column(String(16), nullable=False)
    effective_date = Column(Date, nullable=False)
    split_ratio_from = Column(Numeric(12, 4))  # e.g. 4-for-1 split: from=1, to=4
    split_ratio_to = Column(Numeric(12, 4))
    dividend_amount = Column(PRICE_TYPE())
    dividend_currency = Column(String(8))
    details = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    symbol = relationship("Symbol")
    source = relationship("DataSource")
