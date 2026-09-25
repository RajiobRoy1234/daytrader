-- PostgreSQL: table for QQQ option-chain snapshots
-- Mirrors the "All Contracts" sheet of QQQ_options_snapshot_2026-09-24.xlsx,
-- plus snapshot_date / underlying fields so multiple daily snapshots can be stored.

CREATE TABLE IF NOT EXISTS options_snapshot (
    id                BIGSERIAL      PRIMARY KEY,
    snapshot_date     DATE           NOT NULL,                  -- trading session the data reflects (e.g. 2026-09-24)
    underlying        VARCHAR(10)    NOT NULL DEFAULT 'QQQ',
    underlying_price  NUMERIC(12,4),                            -- underlying price in the same snapshot
    option_symbol     VARCHAR(32)    NOT NULL,                  -- OCC symbol, e.g. QQQ260925C00480000
    expiration        DATE           NOT NULL,
    option_type       VARCHAR(4)     NOT NULL CHECK (option_type IN ('Call', 'Put')),
    strike            NUMERIC(12,3)  NOT NULL,
    prev_close        NUMERIC(12,4),
    open_price        NUMERIC(12,4),
    high_price        NUMERIC(12,4),
    low_price         NUMERIC(12,4),
    last_price        NUMERIC(12,4),
    change            NUMERIC(12,4),
    pct_change        NUMERIC(12,8),                            -- stored as a fraction (-0.0012 = -0.12%)
    last_trade_time   TIMESTAMP,
    bid               NUMERIC(12,4),
    bid_size          INTEGER,
    ask               NUMERIC(12,4),
    ask_size          INTEGER,
    mid               NUMERIC(12,4),
    spread            NUMERIC(12,4),
    volume            INTEGER        DEFAULT 0,
    open_interest     INTEGER        DEFAULT 0,
    iv                NUMERIC(10,6),                            -- implied volatility as a fraction (0.25 = 25%)
    delta             NUMERIC(10,6),
    gamma             NUMERIC(10,6),
    theta             NUMERIC(10,6),
    vega              NUMERIC(10,6),
    rho               NUMERIC(10,6),
    theo              NUMERIC(12,4),                            -- theoretical value
    source            TEXT           DEFAULT 'Cboe delayed quotes',
    loaded_at         TIMESTAMPTZ    NOT NULL DEFAULT now(),
    CONSTRAINT uq_options_snapshot UNIQUE (snapshot_date, option_symbol)
);

-- Helpful indexes for typical queries (by expiry, by strike, by date)
CREATE INDEX IF NOT EXISTS idx_opt_snap_date_exp
    ON options_snapshot (snapshot_date, expiration);
CREATE INDEX IF NOT EXISTS idx_opt_snap_exp_type_strike
    ON options_snapshot (underlying, expiration, option_type, strike);

-- Optional: bulk-load a CSV export of the "All Contracts" sheet (psql client-side)
-- Export the sheet to CSV first, then:
-- \copy options_snapshot (option_symbol, expiration, option_type, strike, prev_close,
--        open_price, high_price, low_price, last_price, change, pct_change, last_trade_time,
--        bid, bid_size, ask, ask_size, mid, spread, volume, open_interest, iv,
--        delta, gamma, theta, vega, rho, theo, snapshot_date, underlying_price)
--   FROM 'qqq_all_contracts.csv' WITH (FORMAT csv, HEADER true);
