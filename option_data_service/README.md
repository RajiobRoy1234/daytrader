# Option Data Service

A Python/FastAPI service for pulling company, equity, option-chain, and tick data from
multiple vendors and storing it in PostgreSQL under one normalized schema.

## Features
- FastAPI API for health checks and ingestion/retrieval of option chains, price history, and ticks
- Normalized SQLAlchemy schema for companies, symbols, price history, option chains, and ticks
- Native Postgres range partitioning (by month) on the two highest-volume tables, with a
  runtime safety net that creates a partition on demand if one doesn't exist yet
- Alembic migrations - schema changes are tracked, not created ad hoc with `create_all`
- A common `MarketDataProvider` interface with a working Yahoo Finance implementation plus
  Bloomberg / Cboe / Schwab providers wired up and ready for credentials (see "Providers" below)

## Schema

All tables live in `app/models.py`; `PARTITIONED_TABLES` there lists which ones are partitioned.

- `data_sources` - one row per vendor/feed (`yahoo`, `bloomberg`, `cboe`, `schwab`, ...).
  Every price/quote/tick row is tagged with a `source_id`, so the same instrument can carry
  data from multiple vendors side by side instead of one overwriting another.
- `companies` - issuer-level data (name, sector, industry, country, ...).
- `symbols` - canonical tradable instruments (ticker, exchange, asset type), linked to a
  `company` where applicable.
- `symbol_source_map` - each vendor's own spelling of a symbol (e.g. Bloomberg
  `AAPL US Equity` vs. Schwab `AAPL`) mapped back to one canonical `symbol`.
- `sectors` - the 11 canonical GICS sectors (seed with `scripts/seed_sectors.py`).
  `companies.sector_id` points here; `companies.sector` keeps whatever raw string the vendor
  sent, since not every vendor spells sectors the same way. `sectors.benchmark_symbol_id` is an
  ordinary `symbol` (`asset_type='index'`) whose `price_history` drives that sector's
  price/change - not a separate price-storage path.
- `price_history` - OHLCV bars for a symbol at any interval (`1d`, `1h`, `5m`, `1m`, ...),
  keyed by `(symbol_id, source_id, interval, bar_time)`.
- `option_contracts` - one row per unique contract (`underlying`, `expiration`, `strike`,
  `option_type`), independent of any vendor's own option symbol.
- `option_contract_source_map` - each vendor's own option symbol mapped back to one
  canonical `option_contract` (OCC/Bloomberg/CBOE/Schwab all spell these differently).
- `option_quotes` - timestamped option-chain snapshots per contract per source, **partitioned
  by month on `quote_time`**. The latest `quote_time` per contract is "the chain"; a time
  range is its history.
- `stock_ticks` / `option_ticks` - raw trade/quote ticks, **partitioned by month on
  `tick_time`**, `BigInteger` PK, indexed on `(instrument_id, tick_time)` plus a BRIN index on
  `tick_time` for cheap range scans within a partition.
- `indices` / `index_constituents` - tracked indices (S&P 500, DJIA) and their membership.
  `index_constituents.removed_date IS NULL` means a symbol is a *current* member; a symbol
  that drops out gets `removed_date` set rather than its row deleted, and rejoining later adds
  a new row - so index membership history is preserved, not overwritten.
- `corporate_actions` - splits and dividends (typed columns) plus spinoff/merger/name-change/
  ticker-change (free-text `details`), one row per `(symbol, source, action_type,
  effective_date)`.
- `earnings_reports` - one row per `(symbol, source, report_date)`, so two vendors covering the
  same release don't collide. Typed EPS/revenue columns plus a `raw_payload` JSONB column for
  whatever else the vendor returns.
- `news_articles` / `news_mentions` - articles keyed by `(source, source_article_id)`, linked to
  the symbols they mention via `news_mentions` (with a relevance score and a primary-mention
  flag). `news_mentions.published_at` is denormalized from the article so a symbol's news feed
  can be time-ranged without a join.

**How the partitioning works:** the initial Alembic migration pre-creates a rolling window of
monthly partitions (last month through 3 months out) for `option_quotes`, `stock_ticks`, and
`option_ticks`. `app/partitioning.py` also gets called by every ingest service before it
inserts, so a date outside that window still gets a partition created on the fly
(`CREATE TABLE IF NOT EXISTS ... PARTITION OF ...`) instead of failing. For a long-running
deployment, extend the window periodically (a monthly cron calling
`ensure_partitions_for_range` for the next few months is enough) so the on-demand path stays a
safety net rather than the normal case.

## Providers

`app/providers/` implements one `MarketDataProvider` subclass per vendor
(`app/providers/base.py`). Each returns plain dicts that the services in `app/services/`
resolve into `Symbol`/`OptionContract` rows and insert - no vendor SDK touches the DB layer
directly.

| Provider | Source code | Status | Config |
|---|---|---|---|
| Yahoo Finance | `yahoo` | Working (option chains + price history) | none required |
| Tradier | `tradier` | Real REST client; free Sandbox token, no approval wait | `TRADIER_ACCESS_TOKEN` |
| Alpaca | `alpaca` | Real REST client; free paper account, no approval wait | `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY` |
| Charles Schwab | `schwab` | Real OAuth2 + REST client, needs your app credentials | `SCHWAB_CLIENT_ID`, `SCHWAB_CLIENT_SECRET`, `SCHWAB_REFRESH_TOKEN` |
| Cboe DataShop | `cboe` | Real Basic-auth client; endpoint path is subscription-specific | `CBOE_API_USERNAME`, `CBOE_API_PASSWORD`, `CBOE_OPTION_CHAIN_PATH` |
| Bloomberg | `bloomberg` | Real blpapi client; needs a live Terminal/B-PIPE session | `BLOOMBERG_HOST`, `BLOOMBERG_PORT` (default `localhost:8194`), plus `blpapi` installed from Bloomberg's own package index |

All non-Yahoo providers raise `ProviderNotConfiguredError` with setup instructions if you call
them before their env vars (and, for Bloomberg, the `blpapi` package) are in place. None of
them have a working tick feed yet - Tradier/Schwab's REST APIs don't expose historical ticks,
and Cboe/Bloomberg/Alpaca tick access depends on subscription/entitlements or a separate
streaming connection, so `fetch_stock_ticks`/`fetch_option_ticks` are left raising
`NotImplementedError` until wired to a real feed.

### Connecting Tradier or Alpaca (fastest way to get real test data)

Both are free and don't have Schwab's approval wait:

- **Tradier**: sign up at [tradier.com](https://tradier.com), then generate a Sandbox token
  instantly at [web.tradier.com/user/api](https://web.tradier.com/user/api). Set
  `TRADIER_ACCESS_TOKEN` in `.env`. Sandbox data is delayed but otherwise fully functional for
  testing option chains and price history.
- **Alpaca**: sign up for a free paper-trading account at [alpaca.markets](https://alpaca.markets/)
  (email only), then generate an API key pair from the dashboard. Set `ALPACA_API_KEY_ID` and
  `ALPACA_API_SECRET_KEY` in `.env`.

Then use `source=tradier` or `source=alpaca` on any `/ingest/*` endpoint, e.g.:
```bash
curl -X POST "http://localhost:8000/ingest/options?symbol=SPY&source=tradier"
curl -X POST "http://localhost:8000/ingest/prices?symbol=SPY&source=alpaca&interval=1d&start=2026-01-01"
```

I verified both providers' base URLs, auth scheme, and core endpoints against their public
docs, but couldn't test against a live account (no credentials available here) - if a response
field comes back `null` unexpectedly, check the vendor's current docs for that field's exact
name (flagged with a comment at the relevant `.get()` call in each provider file).

### Connecting Schwab

This needs a step only you can do - logging into your own Schwab account to authorize the
app - so it can't be automated end to end. Once done, the `schwab` provider works exactly
like `yahoo` (`source=schwab` on any `/ingest/*` endpoint).

1. **Register an app.** Create an account at [developer.schwab.com](https://developer.schwab.com/register),
   then register an app at [developer.schwab.com/dashboard/apps](https://developer.schwab.com/dashboard/apps):
   - API Product: **Market Data Production** is enough for everything this project does
     (option chains, price history). Only pick "Accounts and Trading Production" if you plan
     to add order/account endpoints later.
   - Callback URL: `https://127.0.0.1:8182` (this doesn't need to be a real server - see step 3).
   - Approval isn't always instant; Schwab has taken anywhere from minutes to a few days in
     practice.
2. Once approved, copy the app's **App Key** and **Secret** into `.env`:
   ```
   SCHWAB_CLIENT_ID=<App Key>
   SCHWAB_CLIENT_SECRET=<Secret>
   SCHWAB_REDIRECT_URI=https://127.0.0.1:8182
   ```
3. Run the one-time authorization helper **yourself, locally** (it opens a real browser and
   needs your Schwab login/MFA, so it can't be run through an agent):
   ```bash
   python scripts/schwab_authorize.py
   ```
   It opens your browser to Schwab's login page; after you approve the app, Schwab redirects
   to the callback URL (which will look "unreachable" in the browser - that's expected, nothing
   needs to be listening there). Copy the full URL from the address bar back into the prompt,
   and the script exchanges it for a refresh token and prints the `.env` line to add.
4. Refresh tokens expire every 7 days and there's no headless way to renew one - re-run
   `schwab_authorize.py` when it does.

## Setup
1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements-dev.txt   # or requirements.txt if you don't need the test deps
   ```
2. Start PostgreSQL (via Docker if you have it):
   ```bash
   docker compose up -d
   ```
   If you don't have Docker, point `DATABASE_URL` (below) at any local Postgres instance and
   create the database yourself, e.g. `createdb options_db`.
3. Copy the environment file and adjust values if needed:
   ```bash
   copy .env.example .env
   ```
4. Apply migrations:
   ```bash
   alembic upgrade head
   ```
5. Seed the known data sources (optional - services also create a source row on first use)
   and the canonical sectors:
   ```bash
   python scripts/seed_data_sources.py
   python scripts/seed_sectors.py
   ```
6. Run the API:
   ```bash
   python run.py
   ```

## Schema changes

Don't hand-edit tables or call `create_all` - after changing `app/models.py`, generate a
migration and review it before applying (partitioned tables need the manual bits Alembic's
autogenerate can't infer; see the initial migration in `alembic/versions/` for the pattern):
```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## Endpoints
- `GET /health`
- `POST /ingest/options?symbol=SPY&source=yahoo` - ingest the current option chain
- `GET /options?limit=50` - most recent option-chain snapshots
- `POST /ingest/prices?symbol=SPY&source=yahoo&interval=1d&start=2024-01-01&end=2026-07-01` - ingest OHLCV bars
- `GET /prices?symbol=SPY&interval=1d&limit=100` - stored bars for a symbol
- `POST /ingest/stock-ticks?symbol=SPY&source=schwab&start=...&end=...` - ingest raw stock ticks
- `POST /ingest/option-ticks?underlying=SPY&expiration=2026-08-21&strike=450&option_type=call&contract_symbol=...&source=schwab&start=...&end=...` - ingest raw option ticks
- `GET /companies?search=Apple&limit=100` - company reference data
- `GET /indices/{code}/constituents` - current members of `SP500` or `DJIA`
- `GET /corporate-actions?symbol=AAPL` - splits/dividends/etc. for a symbol

## Reference data: S&P 500 / Dow constituents and corporate actions

```bash
python scripts/load_index_constituents.py   # ~500 companies, one Wikipedia fetch each for S&P 500 + DJIA
python scripts/load_corporate_actions.py --limit 20   # splits/dividends via yfinance; drop --limit to do all loaded symbols
```

`load_index_constituents.py` scrapes Wikipedia's S&P 500 and DJIA tables (there's no free
official API for index membership) and upserts `companies`/`symbols`/`index_constituents`.
It's safe to re-run periodically to pick up index changes - members no longer in the fetched
list get `removed_date` set rather than deleted. `load_corporate_actions.py` then pulls
historical splits/dividends per symbol via `yfinance`; since that's one Yahoo request per
symbol, `--sleep` (default 0.5s) paces it and `--limit`/`--symbols` let you run a subset first.

I ran `load_index_constituents.py` for real while building this (verified against the live
Wikipedia pages) - 503 S&P 500 companies and 30 DJIA companies, all 30 DJIA members correctly
overlapping with S&P 500 as expected. `load_corporate_actions.py` is written and unit-tested
but I couldn't demonstrate a live run - Yahoo's API was rate-limiting this environment's
outbound requests (HTTP 429) at the time; it should work fine from a normal connection.

## Testing

Tests run against a real Postgres database (the same one `DATABASE_URL` points at) rather than
mocking the DB - each test runs inside a transaction that's rolled back afterward, so nothing
persists. Apply migrations first, then:
```bash
pip install -r requirements-dev.txt
pytest test/
```
`test/fakes.py` has a `FakeProvider` with canned data, so the test suite doesn't depend on any
vendor's live API.
