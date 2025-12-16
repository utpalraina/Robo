# Overview

## What is Robo Trader?

Robo Trader is a professional-grade, ML-based cryptocurrency trading bot with a full-featured web dashboard. It supports backtesting, paper trading, and live trading with multiple exchanges.

## Features

### Trading Capabilities
- **ML-Based Signals**: XGBoost, LightGBM, Random Forest, and Ensemble models
- **50+ Technical Indicators**: RSI, MACD, Bollinger Bands, ATR, ADX, and more
- **Risk Management**: Stop-loss, take-profit, position sizing, daily loss limits
- **Multiple Modes**: Backtesting, paper trading, live trading

### Exchange Support
- **Exchange-Agnostic**: Supports 100+ exchanges via CCXT
- **Primary Exchanges**: Binance, Coinbase, Kraken
- **Testnet Support**: Paper trading with exchange testnets

### Web Dashboard
- **Real-Time Updates**: WebSocket-based live data
- **Interactive Charts**: Price charts with indicators
- **Portfolio Management**: Position tracking, P&L monitoring
- **Trade History**: Complete trade log and analytics

### Production Features
- **Scalable Architecture**: Gunicorn + Uvicorn workers
- **Load Balancing**: Nginx reverse proxy
- **Caching**: Redis for real-time data
- **Background Tasks**: Celery for async operations
- **Containerized**: Full Docker support

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                            │
│                    (Web Browser / API)                          │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                         NGINX                                    │
│              (Reverse Proxy / Load Balancer)                     │
│                      Port: 80/443                                │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                    APPLICATION LAYER                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │    Gunicorn     │  │     Redis       │  │   PostgreSQL    │  │
│  │  + Uvicorn      │  │   (Cache)       │  │   (Database)    │  │
│  │   Port: 8000    │  │   Port: 6379    │  │   Port: 5432    │  │
│  └────────┬────────┘  └────────┬────────┘  └─────────────────┘  │
│           │                    │                                 │
│  ┌────────▼────────────────────▼────────┐                       │
│  │          CELERY WORKERS              │                       │
│  │     (Background Task Processing)     │                       │
│  └──────────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                      DATA LAYER                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  Exchange APIs  │  │   ML Models     │  │  Trade Storage  │  │
│  │  (CCXT)         │  │  (Scikit-learn) │  │  (SQLite/PG)    │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
robo-trader/
├── config/                 # Configuration files
│   ├── config.yaml         # Main trading configuration
│   └── production.py       # Production settings
├── data/                   # Data layer
│   ├── fetcher.py          # Exchange data fetching
│   └── storage.py          # Database operations
├── deploy/                 # Deployment files
│   ├── gunicorn.conf.py    # Gunicorn configuration
│   ├── nginx/              # Nginx configuration
│   ├── postgres/           # PostgreSQL init scripts
│   ├── supervisor/         # Process management
│   └── *.sh                # Deployment scripts
├── docs/                   # Documentation
├── engine/                 # Trading engines
│   ├── backtester.py       # Backtesting engine
│   ├── paper.py            # Paper trading
│   └── live.py             # Live trading
├── features/               # Feature engineering
│   └── indicators.py       # Technical indicators
├── models/                 # ML models
│   ├── base.py             # Base model class
│   └── ml_models.py        # Model implementations
├── strategy/               # Trading strategies
│   └── ml_strategy.py      # ML-based strategy
├── utils/                  # Utilities
│   └── helpers.py          # Helper functions
├── web/                    # Web dashboard
│   ├── server.py           # FastAPI server
│   ├── redis_manager.py    # Redis integration
│   ├── static/             # CSS, JS files
│   └── templates/          # HTML templates
├── workers/                # Background workers
│   ├── celery_app.py       # Celery configuration
│   └── tasks/              # Celery tasks
├── main.py                 # CLI entry point
├── Dockerfile              # Docker image
├── docker-compose.yml      # Docker Compose
├── requirements.txt        # Python dependencies
└── .env.production         # Environment template
```

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Backend | FastAPI | REST API and WebSocket server |
| Server | Gunicorn + Uvicorn | ASGI application server |
| Proxy | Nginx | Reverse proxy, load balancing |
| Cache | Redis | Caching, pub/sub, task queue |
| Database | PostgreSQL / SQLite | Data persistence |
| Tasks | Celery | Background job processing |
| ML | Scikit-learn, XGBoost, LightGBM | Machine learning models |
| Exchange | CCXT | Cryptocurrency exchange API |
| Frontend | HTML, CSS, JavaScript | Web dashboard |
| Charts | Chart.js | Interactive price charts |
| Container | Docker | Containerization |
