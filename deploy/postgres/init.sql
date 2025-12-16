-- PostgreSQL Initialization Script for Robo Trader
-- Production database schema

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- OHLCV Data Table (Time-series optimized)
CREATE TABLE IF NOT EXISTS ohlcv (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open DECIMAL(20, 8) NOT NULL,
    high DECIMAL(20, 8) NOT NULL,
    low DECIMAL(20, 8) NOT NULL,
    close DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(30, 8) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, timeframe, timestamp)
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_timeframe_timestamp
ON ohlcv(symbol, timeframe, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_ohlcv_timestamp
ON ohlcv(timestamp DESC);

-- Trades Table
CREATE TABLE IF NOT EXISTS trades (
    id BIGSERIAL PRIMARY KEY,
    trade_id UUID DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('buy', 'sell')),
    price DECIMAL(20, 8) NOT NULL,
    amount DECIMAL(20, 8) NOT NULL,
    cost DECIMAL(20, 8) NOT NULL,
    fee DECIMAL(20, 8) DEFAULT 0,
    timestamp TIMESTAMPTZ NOT NULL,
    order_id VARCHAR(100),
    exchange VARCHAR(50),
    is_paper BOOLEAN DEFAULT FALSE,
    pnl DECIMAL(20, 8),
    pnl_pct DECIMAL(10, 6),
    exit_reason VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol_timestamp
ON trades(symbol, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_trades_is_paper
ON trades(is_paper);

-- Positions Table
CREATE TABLE IF NOT EXISTS positions (
    id BIGSERIAL PRIMARY KEY,
    position_id UUID DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('long', 'short')),
    size DECIMAL(20, 8) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    current_price DECIMAL(20, 8),
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    unrealized_pnl DECIMAL(20, 8) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open', 'closed', 'liquidated')),
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ,
    exit_price DECIMAL(20, 8),
    realized_pnl DECIMAL(20, 8),
    is_paper BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_positions_symbol_status
ON positions(symbol, status);

-- Model Performance Table
CREATE TABLE IF NOT EXISTS model_performance (
    id BIGSERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50),
    symbol VARCHAR(20) NOT NULL,
    accuracy DECIMAL(10, 6),
    precision_score DECIMAL(10, 6),
    recall DECIMAL(10, 6),
    f1_score DECIMAL(10, 6),
    profit_factor DECIMAL(10, 4),
    sharpe_ratio DECIMAL(10, 4),
    max_drawdown DECIMAL(10, 6),
    total_trades INTEGER,
    winning_trades INTEGER,
    evaluation_period VARCHAR(50),
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_model_performance_timestamp
ON model_performance(timestamp DESC);

-- Signals Table
CREATE TABLE IF NOT EXISTS signals (
    id BIGSERIAL PRIMARY KEY,
    signal_id UUID DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    signal VARCHAR(10) NOT NULL CHECK (signal IN ('buy', 'sell', 'hold')),
    confidence DECIMAL(5, 4) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    model_name VARCHAR(100),
    features JSONB,
    executed BOOLEAN DEFAULT FALSE,
    execution_time TIMESTAMPTZ,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol_timestamp
ON signals(symbol, timestamp DESC);

-- Account Balance History
CREATE TABLE IF NOT EXISTS account_history (
    id BIGSERIAL PRIMARY KEY,
    account_type VARCHAR(20) NOT NULL CHECK (account_type IN ('paper', 'live')),
    cash DECIMAL(20, 8) NOT NULL,
    equity DECIMAL(20, 8) NOT NULL,
    total_pnl DECIMAL(20, 8) DEFAULT 0,
    daily_pnl DECIMAL(20, 8) DEFAULT 0,
    open_positions INTEGER DEFAULT 0,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_account_history_timestamp
ON account_history(timestamp DESC);

-- System Logs Table
CREATE TABLE IF NOT EXISTS system_logs (
    id BIGSERIAL PRIMARY KEY,
    level VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    module VARCHAR(100),
    details JSONB,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_logs_timestamp
ON system_logs(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_system_logs_level
ON system_logs(level);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add trigger to positions table
CREATE TRIGGER update_positions_updated_at
    BEFORE UPDATE ON positions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO robotrader;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO robotrader;
