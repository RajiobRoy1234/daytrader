# Draft data model for equities, options, corporate actions, earnings, and news

This draft extends the existing SQLAlchemy-based service with the domains needed for a broad market-data platform.

## Core entities

### 1. Securities and companies
- companies: company master data
- symbols: canonical ticker rows for equities, ETFs, indexes, and other tradables
- symbol_source_map: vendor-specific symbol aliases

### 2. Market/price data
- price_history: OHLCV bars at any interval (1d, 1h, 5m, 1m, etc.)
- stock_ticks: raw stock trade/quote ticks
- option_contracts: canonical option definitions
- option_contract_source_map: vendor-specific option symbols
- option_quotes: option snapshots by contract and time
- option_ticks: raw option trade/quote ticks

### 3. Corporate actions
- corporate_actions: splits, dividends, spinoffs, mergers, name changes, ticker changes

### 4. Earnings
- earnings_reports: release dates, EPS, revenue, guidance, raw payload

### 5. News
- news_articles: article metadata and content
- news_mentions: article-to-symbol links with relevance and primary-mention flags

## Recommended ingestion strategy

### Reference data ingestion
- Load all U.S.-listed securities meeting your price threshold
- Normalize to canonical symbols and company rows
- Store exchange, listing status, share class, and currency

### Price history ingestion
- Pull daily bars first for the full universe
- Add intraday bars for active watchlists or selected symbols
- Use adjusted close for corporate-action-aware analytics

### Options ingestion
- Build option contracts from chain data
- Store daily option snapshots and only retain intraday or raw tick data for selected contracts

### Corporate actions ingestion
- Pull dividends and splits regularly
- Apply them to historical data to create adjusted series

### Earnings ingestion
- Load earnings calendars and press-release details
- Join to symbols via ticker mapping

### News ingestion
- Pull articles from multiple feeds
- Link each article to securities via named entity matching or source metadata
- Keep raw payloads for auditability and future NLP work

## Storage guidance

- Keep relational Postgres tables for structured entities and historical bars.
- Keep very high-volume raw tick and quote-event data partitioned and retained selectively.
- Use a separate object-storage or time-series layer later if the raw feed volume becomes large.

## Suggested migration order

1. Companies and symbols
2. Price history
3. Corporate actions
4. Option contracts and option quotes
5. Earnings reports
6. News articles and mentions
