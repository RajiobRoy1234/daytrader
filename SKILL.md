# Application Plan

## Goal
Build a lightweight trading data pipeline that can:
1. Pull end-of-day market and option data into storage.
2. Support ad-hoc refreshes for immediate updates.
3. Run hourly intermediate refreshes to keep data current during the trading day.

## Initial Scope
Use the existing option data service as the backbone and extend it with a simple scheduling layer and storage workflow.

## Phase 1 - Data Ingestion Foundation
- Keep the current FastAPI service as the ingestion entry point.
- Add a configurable data source for option quotes and market metadata.
- Persist rows into PostgreSQL with a clear timestamp and symbol/expiration/strike model.
- Expose a health endpoint and a manual ingestion endpoint.

## Phase 2 - End-of-Day Data Pull
- Create a daily job that runs after market close.
- Pull the latest available end-of-day data for the configured symbols.
- Store the snapshot as the canonical daily dataset.
- Mark records with a daily batch identifier or ingestion timestamp for later analysis.

## Phase 3 - Ad-Hoc Refresh
- Add an endpoint or admin command to trigger an immediate refresh.
- Use this for manual updates during development, debugging, or a one-off market event.
- Keep the refresh logic reusable so the same code path can be used for both manual and scheduled jobs.

## Phase 4 - Hourly Intermediate Refresh
- Add a scheduler that runs every hour during market hours.
- Pull the latest intraday/intermediate data snapshot.
- Update existing records when newer data arrives and insert new rows when needed.
- Avoid duplicate inserts by using a stable key based on symbol, expiration, strike, option type, and timestamp bucket.

## Recommended Architecture
- API layer: FastAPI endpoints for health, ingest, and quote retrieval.
- Service layer: reusable ingestion service for EOD, adhoc, and hourly refreshes.
- Provider layer: Yahoo Finance or another market data provider abstraction.
- Database layer: PostgreSQL with SQLAlchemy models for quotes and ingestion runs.
- Scheduler layer: a simple background worker or cron-based job for hourly execution.

## MVP Deliverables
- Manual ingestion works end to end.
- Daily EOD pull stores data successfully.
- Hourly refresh runs automatically during trading hours.
- Basic API can return the latest stored data for analysis.

## Suggested Next Steps
1. Add a job runner and configuration for scheduled refreshes.
2. Introduce a data freshness status field for each symbol/contract.
3. Add a small dashboard or API response showing last updated time and data source.
4. Add tests around ingestion, deduplication, and scheduler behavior.
