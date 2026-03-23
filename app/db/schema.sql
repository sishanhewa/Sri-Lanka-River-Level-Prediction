-- ============================================================
-- River Level Prediction System — PostgreSQL Schema
-- ============================================================

-- 1. Stations: Metadata for each monitoring station
CREATE TABLE IF NOT EXISTS stations (
    station_id   SERIAL PRIMARY KEY,
    station_name VARCHAR(100) UNIQUE NOT NULL,
    river_basin  VARCHAR(100),
    latitude     DOUBLE PRECISION,
    longitude    DOUBLE PRECISION,
    minor_flood_level DOUBLE PRECISION,
    major_flood_level DOUBLE PRECISION,
    upstream_station_id INTEGER REFERENCES stations(station_id),
    created_at   TIMESTAMP DEFAULT NOW()
);

-- 2. Historical Observations: Backfilled from the training CSV
CREATE TABLE IF NOT EXISTS historical_observations (
    id           SERIAL PRIMARY KEY,
    station_id   INTEGER NOT NULL REFERENCES stations(station_id),
    observed_at  TIMESTAMP NOT NULL,
    water_level  DOUBLE PRECISION,
    rainfall_mm  DOUBLE PRECISION,
    rainfall_type VARCHAR(50),
    status       VARCHAR(50),
    source       VARCHAR(50) DEFAULT 'historical_csv',
    UNIQUE(station_id, observed_at)
);

-- 3. Live Observations: From Rivernet real-time scraper
CREATE TABLE IF NOT EXISTS live_observations (
    id           SERIAL PRIMARY KEY,
    station_id   INTEGER NOT NULL REFERENCES stations(station_id),
    observed_at  TIMESTAMP NOT NULL,
    water_level  DOUBLE PRECISION,
    rainfall_mm  DOUBLE PRECISION,
    status       VARCHAR(50),
    raw_payload  TEXT,
    source       VARCHAR(50) DEFAULT 'rivernet',
    created_at   TIMESTAMP DEFAULT NOW(),
    UNIQUE(station_id, observed_at)
);

-- 4. Predictions: Model outputs
CREATE TABLE IF NOT EXISTS predictions (
    id             SERIAL PRIMARY KEY,
    station_id     INTEGER NOT NULL REFERENCES stations(station_id),
    prediction_time TIMESTAMP NOT NULL,
    horizon_hours  INTEGER NOT NULL,
    predicted_water_level DOUBLE PRECISION NOT NULL,
    risk_class     VARCHAR(20) NOT NULL,
    model_version  VARCHAR(50),
    created_at     TIMESTAMP DEFAULT NOW()
);

-- 5. Simulation Runs: Scenario metadata
CREATE TABLE IF NOT EXISTS simulation_runs (
    run_id         SERIAL PRIMARY KEY,
    created_at     TIMESTAMP DEFAULT NOW(),
    scenario_name  VARCHAR(200),
    rainfall_input_json TEXT
);

-- 6. Simulation Results: Per-station simulated outputs
CREATE TABLE IF NOT EXISTS simulation_results (
    id             SERIAL PRIMARY KEY,
    run_id         INTEGER NOT NULL REFERENCES simulation_runs(run_id),
    station_id     INTEGER NOT NULL REFERENCES stations(station_id),
    horizon_hours  INTEGER NOT NULL,
    predicted_water_level DOUBLE PRECISION NOT NULL,
    risk_class     VARCHAR(20)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_hist_station_time ON historical_observations(station_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_live_station_time ON live_observations(station_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_pred_station_time ON predictions(station_id, prediction_time);

-- 7. Sync Logs: Tracks the 15-minute fetcher execution
CREATE TABLE IF NOT EXISTS sync_logs (
    id SERIAL PRIMARY KEY,
    sync_time TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50),
    inserted_records INT,
    predictions_run INT,
    message TEXT
);
