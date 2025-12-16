# Robo Trader - System Architecture

## Overview

Robo Trader is an ML-powered cryptocurrency trading bot that uses machine learning algorithms to generate buy/sell signals based on technical analysis indicators. The system connects to cryptocurrency exchanges via APIs, fetches real-time market data, processes it through feature engineering pipelines, and generates trading signals using trained XGBoost models.

---

## Objective & Purpose

### Primary Objective
To provide automated, data-driven cryptocurrency trading decisions by leveraging machine learning models trained on historical market data and technical indicators.

### Key Purposes

1. **Automated Signal Generation** - Generate BUY/SELL/HOLD signals based on ML predictions
2. **Risk Management** - Enforce stop-loss, take-profit, and position sizing rules
3. **Paper Trading** - Test strategies without risking real capital
4. **Backtesting** - Evaluate strategy performance on historical data
5. **Real-Time Monitoring** - Web dashboard for live market visualization
6. **Multi-Timeframe Analysis** - Support for 5m, 15m, 30m, 1h, 4h, 1d timeframes

---

## System Architecture Diagram

```
                                    ROBO TRADER ARCHITECTURE
    ================================================================================================

    +-------------------------------------------------------------------------------------------+
    |                                      WEB LAYER                                            |
    |  +-------------------------------------------------------------------------------------+  |
    |  |                           Web Dashboard (localhost:8000)                            |  |
    |  |  +-------------+  +-------------+  +-------------+  +-------------+  +------------+ |  |
    |  |  | Price Chart |  |  ML Signal  |  |  Account    |  |  Positions  |  | Indicators | |  |
    |  |  | (Chart.js)  |  |   Panel     |  |   Info      |  |    List     |  |   Panel    | |  |
    |  |  +-------------+  +-------------+  +-------------+  +-------------+  +------------+ |  |
    |  +-------------------------------------------------------------------------------------+  |
    |                                          |                                               |
    |                                          v                                               |
    |  +-------------------------------------------------------------------------------------+  |
    |  |                         FastAPI Server (web/server.py)                              |  |
    |  |                                                                                     |  |
    |  |   REST API Endpoints:                    WebSocket:                                 |  |
    |  |   - GET /api/prices/{symbol}             - /ws (real-time updates)                  |  |
    |  |   - GET /api/signal/{symbol}                                                        |  |
    |  |   - GET /api/indicators/{symbol}         Background Tasks:                          |  |
    |  |   - GET /api/account                     - Trading loop                             |  |
    |  |   - GET /api/positions                   - Model training                           |  |
    |  |   - POST /api/start                      - Backtesting                              |  |
    |  |   - POST /api/stop                                                                  |  |
    |  |   - POST /api/train                                                                 |  |
    |  |   - POST /api/backtest                                                              |  |
    |  +-------------------------------------------------------------------------------------+  |
    +-------------------------------------------------------------------------------------------+
                                               |
                                               v
    +-------------------------------------------------------------------------------------------+
    |                                    CORE LAYER                                             |
    |                                                                                           |
    |  +-------------------------+     +-------------------------+     +---------------------+  |
    |  |    ML Strategy          |     |    Feature Engineer     |     |     ML Model        |  |
    |  |  (strategy/ml_strategy) |<--->| (features/indicators)   |<--->| (models/ml_models)  |  |
    |  |                         |     |                         |     |                     |  |
    |  |  - generate_signal()    |     |  - 70+ Technical        |     |  - XGBoost          |  |
    |  |  - position_sizing()    |     |    Indicators:          |     |  - StandardScaler   |  |
    |  |  - stop_loss_check()    |     |    * RSI, MACD, BB      |     |  - train()          |  |
    |  |  - take_profit_check()  |     |    * EMA, SMA, ATR      |     |  - predict()        |  |
    |  |  - risk_management()    |     |    * ADX, Stochastic    |     |  - predict_proba()  |  |
    |  |                         |     |    * Volume, OBV        |     |  - save/load()      |  |
    |  +-------------------------+     +-------------------------+     +---------------------+  |
    |              |                              |                              |              |
    |              v                              v                              v              |
    |  +-----------------------------------------------------------------------------------+    |
    |  |                              Trading Engines                                      |    |
    |  |  +--------------------+    +--------------------+    +--------------------+       |    |
    |  |  |   Paper Trader     |    |    Backtester      |    |   Live Trader      |       |    |
    |  |  |  (engine/paper.py) |    | (engine/backtest)  |    |  (engine/live.py)  |       |    |
    |  |  |                    |    |                    |    |                    |       |    |
    |  |  | - Simulated trades |    | - Historical sim   |    | - Real order exec  |       |    |
    |  |  | - Virtual account  |    | - Performance      |    | - Exchange orders  |       |    |
    |  |  | - P&L tracking     |    |   metrics          |    | - Live positions   |       |    |
    |  |  +--------------------+    +--------------------+    +--------------------+       |    |
    |  +-----------------------------------------------------------------------------------+    |
    +-------------------------------------------------------------------------------------------+
                                               |
                                               v
    +-------------------------------------------------------------------------------------------+
    |                                    DATA LAYER                                             |
    |                                                                                           |
    |  +----------------------------------+        +----------------------------------+          |
    |  |         Data Fetcher             |        |         Data Storage            |          |
    |  |       (data/fetcher.py)          |        |        (data/storage.py)        |          |
    |  |                                  |        |                                 |          |
    |  |  - fetch_ohlcv()                 |        |  - SQLite database              |          |
    |  |  - fetch_historical_data()       |        |  - save_candles()               |          |
    |  |  - fetch_ticker()                |        |  - save_trade()                 |          |
    |  |  - fetch_order_book()            |        |  - get_trades()                 |          |
    |  +----------------------------------+        +----------------------------------+          |
    |                    |                                                                      |
    +-------------------------------------------------------------------------------------------+
                         |
                         v
    +-------------------------------------------------------------------------------------------+
    |                                  EXCHANGE LAYER                                           |
    |                                                                                           |
    |  +-----------------------------------------------------------------------------------+    |
    |  |                           CCXT Library (Exchange Agnostic)                        |    |
    |  |                                                                                   |    |
    |  |     +---------------+     +---------------+     +---------------+                 |    |
    |  |     |    Kraken     |     |    Binance    |     |   Coinbase    |     ...         |    |
    |  |     |     API       |     |     API       |     |      API      |                 |    |
    |  |     +---------------+     +---------------+     +---------------+                 |    |
    |  |                                                                                   |    |
    |  |  Supported Operations:                                                            |    |
    |  |  - fetch_ohlcv()        - fetch_balance()        - create_order()                |    |
    |  |  - fetch_ticker()       - fetch_positions()      - cancel_order()                |    |
    |  |  - fetch_order_book()   - fetch_orders()         - fetch_my_trades()             |    |
    |  +-----------------------------------------------------------------------------------+    |
    |                                                                                           |
    +-------------------------------------------------------------------------------------------+
```

---

## Data Flow Diagram

```
    +-------------+      +-------------+      +------------------+      +-------------+
    |   Kraken    | ---> | DataFetcher | ---> | FeatureEngineer  | ---> |  ML Model   |
    |  Exchange   |      |   (CCXT)    |      |  (70+ features)  |      |  (XGBoost)  |
    +-------------+      +-------------+      +------------------+      +-------------+
          |                    |                      |                       |
          |              OHLCV Data             Feature DataFrame        Prediction
          |            (timestamp,              (RSI, MACD, BB,         (probability)
          |             O, H, L, C, V)           EMA, ATR, ...)              |
          |                    |                      |                       |
          v                    v                      v                       v
    +-------------+      +-------------+      +------------------+      +-------------+
    |   Ticker    |      |   Storage   |      |    ML Strategy   | <--- |   Signal    |
    |   Update    |      |  (SQLite)   |      | (Risk Management)|      | BUY/SELL/   |
    +-------------+      +-------------+      +------------------+      |    HOLD     |
          |                                          |                 +-------------+
          |                                          |
          v                                          v
    +-------------+      +-------------+      +------------------+
    |  WebSocket  | ---> |  Dashboard  | <--- | Paper/Live Trade |
    |  Broadcast  |      |   (UI)      |      |    Execution     |
    +-------------+      +-------------+      +------------------+
```

---

## Component Details

### 1. Web Layer

| Component | File | Description |
|-----------|------|-------------|
| FastAPI Server | `web/server.py` | Main web server with REST API and WebSocket |
| Dashboard | `web/templates/dashboard.html` | Interactive trading dashboard |
| JavaScript App | `web/static/js/app.js` | Real-time chart updates and UI logic |
| Styles | `web/static/css/style.css` | Dark theme styling |

### 2. Core Layer

| Component | File | Description |
|-----------|------|-------------|
| ML Strategy | `strategy/ml_strategy.py` | Signal generation with risk management |
| Feature Engineer | `features/indicators.py` | Technical indicator calculations |
| XGBoost Model | `models/ml_models.py` | Machine learning model implementation |
| Base Model | `models/base.py` | Abstract base class for models |

### 3. Trading Engines

| Engine | File | Description |
|--------|------|-------------|
| Paper Trader | `engine/paper.py` | Simulated trading with virtual account |
| Backtester | `engine/backtester.py` | Historical strategy testing |
| Live Trader | `engine/live.py` | Real order execution (use with caution) |

### 4. Data Layer

| Component | File | Description |
|-----------|------|-------------|
| Data Fetcher | `data/fetcher.py` | Exchange data retrieval via CCXT |
| Data Storage | `data/storage.py` | SQLite persistence layer |

---

## Technical Indicators (70+ Features)

### Momentum Indicators
- RSI (7, 14 periods)
- Stochastic Oscillator (%K, %D)
- Rate of Change (ROC)
- MACD (12, 26, 9)

### Trend Indicators
- EMA (9, 21, 50 periods)
- SMA (20, 50 periods)
- ADX (trend strength)
- CCI (Commodity Channel Index)

### Volatility Indicators
- Bollinger Bands (upper, middle, lower, width, %B)
- ATR (Average True Range)
- Standard deviation of returns

### Volume Indicators
- OBV (On Balance Volume)
- Volume ratio (vs 20-period average)
- VWAP (approximation)

### Price Features
- Returns (1, 5, 10, 20 periods)
- Log returns
- Momentum
- Price position within candle
- Gap (open vs previous close)

### Time Features
- Hour, day of week, day of month
- Cyclical encodings (sin/cos transforms)

### Lagged Features
- Previous period values for key indicators

---

## Signal Generation Logic

```
                    +------------------+
                    |  Market Data     |
                    |  (200 candles)   |
                    +------------------+
                            |
                            v
                    +------------------+
                    | Feature Engineer |
                    | (70+ indicators) |
                    +------------------+
                            |
                            v
                    +------------------+
                    |   XGBoost Model  |
                    |  predict_proba() |
                    +------------------+
                            |
                            v
              +-------------+-------------+
              |                           |
              v                           v
    +------------------+        +------------------+
    | up_prob >= 0.60  |        | up_prob <= 0.40  |
    |      BUY         |        |      SELL        |
    +------------------+        +------------------+
              |                           |
              v                           v
    +------------------+        +------------------+
    | Risk Checks:     |        | Risk Checks:     |
    | - Daily loss     |        | - Daily loss     |
    | - Max positions  |        | - Max positions  |
    | - Position size  |        | - Position size  |
    +------------------+        +------------------+
              |                           |
              v                           v
    +------------------+        +------------------+
    | Execute Trade    |        | Execute Trade    |
    | (Paper or Live)  |        | (Paper or Live)  |
    +------------------+        +------------------+
```

---

## Risk Management Features

| Feature | Default | Description |
|---------|---------|-------------|
| Stop Loss | 2% | Close position if loss exceeds threshold |
| Take Profit | 4% | Close position if profit exceeds threshold |
| Max Position Size | 10% | Maximum % of capital per trade |
| Daily Loss Limit | 5% | Stop trading if daily losses exceed limit |
| Max Open Positions | 3 | Maximum concurrent positions |
| Risk Per Trade | 1% | Risk 1% of capital per trade |

---

## API Endpoints

### Market Data
```
GET /api/prices/{symbol}?limit=100&timeframe=1h
GET /api/ticker/{symbol}
GET /api/indicators/{symbol}
```

### Trading Signals
```
GET /api/signal/{symbol}
GET /api/status
```

### Account & Positions
```
GET /api/account
GET /api/positions
GET /api/trades?limit=50
```

### Trading Control
```
POST /api/start     {"symbols": ["BTC/USDT"], "mode": "paper"}
POST /api/stop
```

### Training & Backtesting
```
POST /api/train     {"symbol": "BTC/USDT", "start_date": "2024-01-01", "end_date": "2024-12-01"}
POST /api/backtest  {"symbol": "BTC/USDT", "start_date": "2024-01-01", "end_date": "2024-12-01"}
```

### WebSocket
```
WS /ws              Real-time updates (price, signals, account)
```

---

## Project Structure

```
robo-trader/
├── config/
│   └── config.yaml          # Main configuration
├── data/
│   ├── fetcher.py           # Exchange data fetching
│   └── storage.py           # SQLite persistence
├── features/
│   └── indicators.py        # Technical indicators (70+)
├── models/
│   ├── base.py              # Abstract model class
│   ├── ml_models.py         # XGBoost implementation
│   └── trained_model.joblib # Saved model weights
├── strategy/
│   └── ml_strategy.py       # Signal generation
├── engine/
│   ├── paper.py             # Paper trading
│   ├── backtester.py        # Historical testing
│   └── live.py              # Real trading
├── web/
│   ├── server.py            # FastAPI application
│   ├── templates/
│   │   └── dashboard.html   # Main UI
│   └── static/
│       ├── js/app.js        # Frontend logic
│       └── css/style.css    # Styling
├── workers/                 # Celery tasks (production)
├── deploy/                  # Docker, Nginx, etc.
├── .env                     # API keys (not in git)
└── main.py                  # CLI entry point
```

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | HTML5, CSS3, JavaScript, Chart.js, Luxon |
| Backend | Python 3.10+, FastAPI, Uvicorn |
| ML Framework | XGBoost, scikit-learn |
| Data Processing | Pandas, NumPy, TA-Lib (via `ta` library) |
| Exchange Integration | CCXT (100+ exchanges) |
| Database | SQLite (dev), PostgreSQL (prod) |
| Task Queue | Celery + Redis (production) |
| Containerization | Docker, Docker Compose |
| Web Server | Nginx (production) |

---

## Dashboard Features

### Main Display
- **Real-time Price Chart** - Line or candlestick view
- **ML Signal Panel** - Current BUY/SELL/HOLD with confidence %
- **Account Summary** - Cash, equity, P&L
- **Positions Table** - Open positions with unrealized P&L
- **Technical Indicators** - RSI, MACD, Bollinger Bands

### Controls
- **Timeframe Selector** - 5M, 15M, 30M, 1H, 4H, 1D
- **Chart Type Toggle** - Line / Candlestick
- **Timezone Selector** - Local, London, New York, Tokyo
- **Trading Controls** - Start/Stop paper trading
- **Model Training** - Train new model with date range

### Real-time Updates
- Price ticker: Every 5 seconds
- Full chart data: Every 10 seconds
- WebSocket: Instant trade notifications

---

## Security Considerations

1. **API Keys** - Store in `.env` file, never commit to git
2. **CORS** - Currently allows all origins (restrict in production)
3. **Paper Trading** - Always test thoroughly before live trading
4. **Rate Limits** - CCXT handles exchange rate limits automatically
5. **No Financial Advice** - This is a tool, not financial advice

---

## Deployment Options

### Development
```bash
python main.py web --port 8000
```

### Production (Docker)
```bash
docker-compose up -d
```

Services:
- Web: FastAPI + Gunicorn
- Database: PostgreSQL
- Cache: Redis
- Workers: Celery
- Proxy: Nginx

---

## Current Configuration

| Setting | Value |
|---------|-------|
| Exchange | Kraken |
| Trading Pair | BTC/USDT |
| Default Timeframe | 1 hour |
| Initial Capital | $10,000 (paper) |
| Model | XGBoost Classifier |

---

*Document generated: December 2025*
*Version: 1.0*
