# Configuration Guide

This guide covers all configuration files and options available in Robo Trader.

---

## Configuration Files Overview

| File | Purpose | Location |
|------|---------|----------|
| `.env` | Environment variables (secrets) | Project root |
| `config/config.yaml` | Trading configuration | `config/` |
| `config/production.py` | Production settings | `config/` |
| `deploy/gunicorn.conf.py` | Gunicorn server config | `deploy/` |
| `deploy/nginx/robo-trader.conf` | Nginx configuration | `deploy/nginx/` |

---

## 1. Environment Variables (.env)

Create by copying `.env.production`:
```bash
cp .env.production .env
```

### Complete .env Reference

```bash
# =====================================================
# ENVIRONMENT SETTINGS
# =====================================================
ENV=production                    # development | production
DEBUG=false                       # true | false
SECRET_KEY=your-secret-key-here   # Random string for security

# =====================================================
# SERVER SETTINGS
# =====================================================
HOST=0.0.0.0                      # Server bind address
PORT=8000                         # Server port
WORKERS=4                         # Number of Gunicorn workers

# =====================================================
# DATABASE
# =====================================================
# SQLite (default for development)
DATABASE_URL=sqlite:///data/trading.db

# PostgreSQL (recommended for production)
DATABASE_URL=postgresql://user:password@localhost:5432/robotrader
DB_PASSWORD=your-db-password

# =====================================================
# REDIS
# =====================================================
REDIS_HOST=localhost              # Redis server host
REDIS_PORT=6379                   # Redis server port
REDIS_PASSWORD=                   # Redis password (if set)
REDIS_DB=0                        # Redis database number

# =====================================================
# EXCHANGE API KEYS
# =====================================================
# Binance
BINANCE_API_KEY=your-api-key
BINANCE_API_SECRET=your-api-secret
BINANCE_TESTNET=true              # Use testnet for testing

# Coinbase
COINBASE_API_KEY=
COINBASE_API_SECRET=

# Kraken
KRAKEN_API_KEY=
KRAKEN_API_SECRET=

# =====================================================
# TRADING SETTINGS
# =====================================================
TRADING_SYMBOLS=BTC/USDT,ETH/USDT # Comma-separated symbols
TRADING_TIMEFRAME=1h              # Candle timeframe
MAX_POSITION_SIZE=0.1             # Max 10% per trade
STOP_LOSS_PCT=0.02                # 2% stop loss
TAKE_PROFIT_PCT=0.04              # 4% take profit
MAX_OPEN_POSITIONS=3              # Max concurrent positions
DAILY_LOSS_LIMIT=0.05             # 5% daily loss limit

# =====================================================
# LOGGING
# =====================================================
LOG_LEVEL=INFO                    # DEBUG | INFO | WARNING | ERROR
LOG_FILE=/app/logs/app.log        # Log file path

# =====================================================
# MONITORING (Optional)
# =====================================================
PROMETHEUS_ENABLED=false
GRAFANA_PASSWORD=admin
```

---

## 2. Trading Configuration (config/config.yaml)

Main trading configuration file.

```yaml
# =====================================================
# EXCHANGE SETTINGS
# =====================================================
exchange:
  name: "binance"           # Exchange to use
  testnet: true             # Use testnet/sandbox mode
  rate_limit: true          # Respect API rate limits

# =====================================================
# TRADING PAIRS
# =====================================================
trading:
  symbols:
    - "BTC/USDT"
    - "ETH/USDT"
    - "SOL/USDT"
  timeframe: "1h"           # 1m, 5m, 15m, 30m, 1h, 4h, 1d

# =====================================================
# RISK MANAGEMENT
# =====================================================
risk:
  max_position_size: 0.1    # Maximum 10% of portfolio per trade
  stop_loss_pct: 0.02       # 2% stop loss
  take_profit_pct: 0.04     # 4% take profit
  max_open_positions: 3     # Maximum concurrent positions
  daily_loss_limit: 0.05    # Stop trading at 5% daily loss

# =====================================================
# ML MODEL SETTINGS
# =====================================================
model:
  type: "xgboost"           # xgboost | lightgbm | random_forest | ensemble
  lookback_periods: 100     # Candles for feature generation
  train_test_split: 0.8     # 80% train, 20% test
  retrain_interval: 168     # Retrain every 168 hours (1 week)

# =====================================================
# FEATURE ENGINEERING
# =====================================================
features:
  technical_indicators:
    - rsi
    - macd
    - bollinger_bands
    - ema
    - atr
    - volume_sma
    - adx
    - stochastic
  price_features:
    - returns
    - volatility
    - momentum

# =====================================================
# BACKTESTING
# =====================================================
backtest:
  start_date: "2024-01-01"
  end_date: "2024-12-01"
  initial_capital: 10000    # Starting capital (USDT)
  commission: 0.001         # 0.1% trading fee

# =====================================================
# PAPER TRADING
# =====================================================
paper_trading:
  initial_capital: 10000    # Starting paper capital

# =====================================================
# LOGGING
# =====================================================
logging:
  level: "INFO"             # DEBUG, INFO, WARNING, ERROR
  file: "logs/trading.log"
```

---

## 3. Risk Management Settings

### Position Sizing

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_position_size` | 0.1 (10%) | Maximum portfolio % per trade |
| `max_open_positions` | 3 | Maximum concurrent positions |

### Stop Loss & Take Profit

| Parameter | Default | Description |
|-----------|---------|-------------|
| `stop_loss_pct` | 0.02 (2%) | Stop loss percentage |
| `take_profit_pct` | 0.04 (4%) | Take profit percentage |
| `daily_loss_limit` | 0.05 (5%) | Max daily loss before stopping |

### Example Risk Profiles

**Conservative:**
```yaml
risk:
  max_position_size: 0.05   # 5% per trade
  stop_loss_pct: 0.01       # 1% stop loss
  take_profit_pct: 0.02     # 2% take profit
  max_open_positions: 2
  daily_loss_limit: 0.03    # 3% daily limit
```

**Moderate:**
```yaml
risk:
  max_position_size: 0.1    # 10% per trade
  stop_loss_pct: 0.02       # 2% stop loss
  take_profit_pct: 0.04     # 4% take profit
  max_open_positions: 3
  daily_loss_limit: 0.05    # 5% daily limit
```

**Aggressive:**
```yaml
risk:
  max_position_size: 0.2    # 20% per trade
  stop_loss_pct: 0.03       # 3% stop loss
  take_profit_pct: 0.06     # 6% take profit
  max_open_positions: 5
  daily_loss_limit: 0.1     # 10% daily limit
```

---

## 4. ML Model Configuration

### Available Models

| Model | Best For | Speed | Accuracy |
|-------|----------|-------|----------|
| `xgboost` | General purpose | Fast | High |
| `lightgbm` | Large datasets | Very Fast | High |
| `random_forest` | Stability | Medium | Medium |
| `ensemble` | Best accuracy | Slow | Highest |

### Model Settings

```yaml
model:
  type: "ensemble"          # Model type
  lookback_periods: 100     # Historical periods for features
  train_test_split: 0.8     # Train/test ratio
  retrain_interval: 168     # Hours between retraining
```

---

## 5. Gunicorn Configuration (deploy/gunicorn.conf.py)

Production server settings.

```python
# Key settings
bind = "0.0.0.0:8000"       # Server address
workers = 4                  # Worker processes (CPU cores * 2 + 1)
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120               # Request timeout
max_requests = 5000         # Restart workers after N requests
```

### Worker Calculation

```python
# Recommended: (2 * CPU cores) + 1
# For 4 cores: (2 * 4) + 1 = 9 workers
workers = multiprocessing.cpu_count() * 2 + 1
```

---

## 6. Nginx Configuration (deploy/nginx/robo-trader.conf)

### Key Settings

```nginx
# Upstream servers
upstream robo_trader_app {
    server 127.0.0.1:8000;
}

# Rate limiting
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

# WebSocket support
location /ws {
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

---

## 7. Timeframe Reference

| Value | Description | Use Case |
|-------|-------------|----------|
| `1m` | 1 minute | Scalping |
| `5m` | 5 minutes | Short-term |
| `15m` | 15 minutes | Intraday |
| `30m` | 30 minutes | Intraday |
| `1h` | 1 hour | Swing trading (default) |
| `4h` | 4 hours | Swing trading |
| `1d` | 1 day | Position trading |

---

## 8. Configuration Validation

Check your configuration:

```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"

# Test environment loading
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('ENV'))"

# Verify exchange connection
python -c "
from utils.helpers import load_config, get_exchange
config = load_config()
exchange = get_exchange(config)
print('Connected to:', exchange.id)
"
```

---

## Next Steps

- [Services & Ports](./04-services-ports.md) - Understanding the service architecture
- [Docker Guide](./05-docker-guide.md) - Container deployment
