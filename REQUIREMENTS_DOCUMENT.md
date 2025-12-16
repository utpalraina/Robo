# Robo-Trader Requirements Document

**Version:** 1.0
**Date:** December 15, 2025
**Status:** Production Ready with Enhancement Opportunities

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Current Features](#2-current-features)
3. [System Architecture](#3-system-architecture)
4. [Feature Gap Analysis](#4-feature-gap-analysis)
5. [Proposed Enhancements](#5-proposed-enhancements)
6. [Technical Requirements](#6-technical-requirements)
7. [Security Requirements](#7-security-requirements)
8. [Performance Requirements](#8-performance-requirements)
9. [Future Roadmap](#9-future-roadmap)

---

## 1. Executive Summary

### 1.1 Purpose
Robo-Trader is an ML-powered cryptocurrency trading bot designed for automated trading on the Kraken exchange. It combines machine learning predictions, ICT (Inner Circle Trader) concepts, and technical analysis to generate trading signals and execute trades.

### 1.2 Target Users
- Cryptocurrency traders seeking automation
- Quantitative traders testing ML strategies
- Developers building trading systems
- Researchers studying market microstructure

### 1.3 Current State
The application is **functional** with:
- 4 trading bots (Scalping, Short Term, Swing, Long Term)
- Paper and Live trading modes
- Web dashboard with real-time updates
- ML model integration (XGBoost, LightGBM)
- ICT strategy implementation

---

## 2. Current Features

### 2.1 Trading Bots

| Bot Type | Timeframe | Hold Period | Strategy |
|----------|-----------|-------------|----------|
| Scalping | 1m, 5m, 15m | Minutes to hours | Confluence + ML + ICT |
| Short Term | 4h | 1-5 days | Swing indicators |
| Swing Trading | 1d | 3-14 days | Trend following |
| Long Term | 1w | Weeks to months | DCA + Macro analysis |

### 2.2 Trading Modes
- **Paper Trading**: Simulated trades with virtual capital
- **Live Trading**: Real order execution on Kraken
- **Backtesting**: Historical strategy validation

### 2.3 Strategy Components

#### Machine Learning
- XGBoost classifier for price direction prediction
- LightGBM as alternative model
- 40+ technical features
- Model persistence and retraining

#### ICT Concepts
- Fair Value Gaps (FVG)
- Market Structure Shifts (MSS)
- Order Blocks (OB)
- Optimal Trade Entry (OTE)
- Liquidity zones
- Premium/Discount zones
- Session-based trading (NY, London, Asia)

#### Technical Analysis
- RSI, MACD, Stochastic
- Bollinger Bands, ATR
- EMA/SMA (9, 21, 50, 200)
- Volume analysis
- Multi-timeframe alignment

### 2.4 Dashboard Features
- Real-time price chart
- Live trading signals
- Bot status monitoring
- Confluence signal display
- Trade history
- Database viewer
- Settings management

### 2.5 Data Infrastructure
- Kraken WebSocket for real-time prices
- Binance API for historical OHLCV data (via CCXT)
- SQLite database storage
- Candle snapshot collection

### 2.6 Multi-Exchange Data Architecture

The system uses a **hybrid exchange approach** for optimal data access:

| Function | Exchange | Reason |
|----------|----------|--------|
| **Historical Data** | Binance | Kraken doesn't support historical OHLCV API; Binance provides full history |
| **Real-time Prices** | Kraken WebSocket | Sub-100ms latency for live trading |
| **Order Execution** | Kraken | Primary trading exchange |
| **Backtesting Data** | Binance | Years of historical data available |
| **ML Training Data** | Binance | Large datasets for model training |

#### Symbol Mapping
Automatic conversion between exchanges:
- `BTC/USD` (Kraken) ↔ `BTC/USDT` (Binance)
- `ETH/USD` (Kraken) ↔ `ETH/USDT` (Binance)

#### Data Flow Diagram
```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐                    ┌─────────────────┐        │
│  │     BINANCE     │                    │     KRAKEN      │        │
│  │  (Historical)   │                    │   (Real-time)   │        │
│  └────────┬────────┘                    └────────┬────────┘        │
│           │                                      │                  │
│           │ CCXT REST API                        │ WebSocket        │
│           │ (No auth needed)                     │ (Sub-100ms)      │
│           │                                      │                  │
│           ▼                                      ▼                  │
│  ┌─────────────────┐                    ┌─────────────────┐        │
│  │ Historical OHLCV│                    │ Live Price Feed │        │
│  │ • Backtesting   │                    │ • Trading Sigs  │        │
│  │ • ML Training   │                    │ • P&L Tracking  │        │
│  │ • Indicators    │                    │ • Order Exec    │        │
│  └────────┬────────┘                    └────────┬────────┘        │
│           │                                      │                  │
│           └──────────────┬───────────────────────┘                  │
│                          ▼                                          │
│                 ┌─────────────────┐                                 │
│                 │   SQLite DB     │                                 │
│                 │ • OHLCV data    │                                 │
│                 │ • Trade history │                                 │
│                 │ • Snapshots     │                                 │
│                 └─────────────────┘                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

#### Why This Architecture?
1. **Kraken Limitation**: Kraken's API doesn't provide historical OHLCV data
2. **Binance Strength**: Full historical data going back years, no API key needed for public data
3. **Best of Both**: Real-time from trading exchange, historical from data-rich exchange
4. **Cost Effective**: Binance public API is free for historical data

---

## 3. System Architecture

### 3.1 Current Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                      Web Dashboard                          │
│                    (FastAPI + HTML/JS)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Trading Engine                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Scalping │ │ Short    │ │ Swing    │ │ Long     │       │
│  │ Bot      │ │ Term Bot │ │ Bot      │ │ Term Bot │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│   ML Models      │ │   ICT Strategy   │ │ Technical        │
│   (XGBoost)      │ │   (FVG, MSS, OB) │ │ Indicators       │
└──────────────────┘ └──────────────────┘ └──────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Kraken WS    │  │ Binance API  │  │ SQLite DB    │      │
│  │ (Real-time)  │  │ (Historical) │  │ (Storage)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Technology Stack
- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **Frontend**: HTML5, CSS3, JavaScript, Chart.js
- **Database**: SQLite (dev), PostgreSQL (prod)
- **ML**: XGBoost, LightGBM, Scikit-learn
- **Exchange APIs**:
  - Kraken WebSocket (real-time prices, order execution)
  - Binance REST API via CCXT (historical data, no auth required)
- **Task Queue**: Celery + Redis (optional)
- **Deployment**: Docker, Nginx

---

## 4. Feature Gap Analysis

### 4.1 Critical Missing Features

| Feature | Priority | Impact | Effort |
|---------|----------|--------|--------|
| User Authentication | HIGH | Security | Medium |
| Multi-Exchange Support | HIGH | Flexibility | High |
| Mobile Responsive UI | HIGH | Accessibility | Medium |
| Automated Stop Loss | HIGH | Risk Management | Low |
| Email/SMS Alerts | MEDIUM | Notifications | Medium |
| Portfolio Analytics | MEDIUM | Insights | Medium |

### 4.2 Current Limitations

#### Security
- [ ] No user authentication system
- [ ] API keys stored in plain config
- [ ] No rate limiting on API endpoints
- [ ] No audit logging

#### Trading
- [ ] Single exchange only (Kraken)
- [ ] No trailing stop loss
- [ ] No partial position closing
- [ ] No portfolio rebalancing
- [ ] No hedging strategies

#### Analytics
- [ ] No detailed P&L reports
- [ ] No tax report generation
- [ ] No benchmark comparison
- [ ] No drawdown analysis charts
- [ ] No correlation analysis

#### User Experience
- [ ] Not mobile responsive
- [ ] No dark/light theme toggle
- [ ] No customizable dashboard
- [ ] No saved strategy presets
- [ ] Limited error feedback

#### Operations
- [ ] No automated backup
- [ ] No disaster recovery plan
- [ ] Limited monitoring/alerting
- [ ] No A/B testing framework

---

## 5. Proposed Enhancements

### 5.1 Phase 1: Essential Improvements (1-2 months)

#### 5.1.1 User Authentication System
```
Requirements:
- JWT-based authentication
- User registration and login
- Role-based access (Admin, Trader, Viewer)
- Secure password hashing (bcrypt)
- Session management
- API key encryption
```

#### 5.1.2 Enhanced Risk Management
```
Requirements:
- Trailing stop loss implementation
- Break-even stop feature
- Maximum drawdown limits per bot
- Correlation-based position limits
- Automated position sizing based on volatility
```

#### 5.1.3 Notification System
```
Requirements:
- Email notifications (trade execution, errors)
- Telegram bot integration
- Discord webhook support
- Customizable alert thresholds
- Daily summary reports
```

#### 5.1.4 Mobile Responsive Design
```
Requirements:
- Responsive CSS framework (Tailwind/Bootstrap)
- Mobile-friendly navigation
- Touch-optimized charts
- PWA capabilities
```

### 5.2 Phase 2: Advanced Features (2-4 months)

#### 5.2.1 Multi-Exchange Support
```
Requirements:
- Binance integration
- Coinbase Pro integration
- Bybit integration
- Exchange-agnostic order routing
- Cross-exchange arbitrage detection
```

#### 5.2.2 Advanced Analytics Dashboard
```
Requirements:
- Interactive P&L charts (daily, weekly, monthly)
- Drawdown visualization
- Win rate by time of day/day of week
- Strategy performance comparison
- Risk-adjusted return metrics (Sharpe, Sortino, Calmar)
- Correlation heatmaps
```

#### 5.2.3 Strategy Builder
```
Requirements:
- Visual strategy builder (drag-and-drop)
- Custom indicator combinations
- Backtesting integration
- Strategy optimization (parameter tuning)
- Walk-forward analysis
```

#### 5.2.4 Portfolio Management
```
Requirements:
- Multi-asset portfolio tracking
- Rebalancing automation
- Target allocation setting
- Performance attribution
- Currency exposure analysis
```

### 5.3 Phase 3: Enterprise Features (4-6 months)

#### 5.3.1 Advanced ML Pipeline
```
Requirements:
- AutoML for model selection
- Feature importance dashboard
- Model versioning and comparison
- Online learning (incremental updates)
- Ensemble model management
- Deep learning models (LSTM, Transformer)
```

#### 5.3.2 Social/Copy Trading
```
Requirements:
- Strategy sharing marketplace
- Copy trading functionality
- Leaderboard system
- Strategy subscription model
- Performance verification
```

#### 5.3.3 Compliance & Reporting
```
Requirements:
- Tax report generation (FIFO, LIFO, HIFO)
- Regulatory compliance reports
- Audit trail logging
- Data export (CSV, JSON, PDF)
- GDPR compliance
```

#### 5.3.4 High-Frequency Trading Infrastructure
```
Requirements:
- Co-location support
- Order book depth analysis
- Latency optimization
- Market making strategies
- Smart order routing
```

---

## 6. Technical Requirements

### 6.1 Performance Requirements

| Metric | Current | Target |
|--------|---------|--------|
| API Response Time | ~200ms | <100ms |
| WebSocket Latency | ~100ms | <50ms |
| Order Execution | ~500ms | <200ms |
| Dashboard Load | ~3s | <1s |
| Concurrent Users | ~10 | 100+ |

### 6.2 Scalability Requirements
- Horizontal scaling for web servers
- Database read replicas
- Redis cluster for caching
- Message queue for async processing
- CDN for static assets

### 6.3 Reliability Requirements
- 99.9% uptime SLA
- Automatic failover
- Data backup every 6 hours
- Point-in-time recovery
- Health monitoring with auto-restart

### 6.4 Data Requirements

#### Storage
| Data Type | Retention | Storage |
|-----------|-----------|---------|
| OHLCV Data | 5 years | PostgreSQL |
| Trade History | Indefinite | PostgreSQL |
| Model Artifacts | 1 year | S3/File |
| Logs | 90 days | ELK Stack |
| Snapshots | 30 days | PostgreSQL |

#### Backup
- Daily full backups
- Hourly incremental backups
- Cross-region replication
- Encrypted backup storage

---

## 7. Security Requirements

### 7.1 Authentication & Authorization
- [ ] Multi-factor authentication (MFA)
- [ ] OAuth2/OpenID Connect
- [ ] API key rotation policy
- [ ] Session timeout (configurable)
- [ ] IP whitelist for API access

### 7.2 Data Protection
- [ ] Encryption at rest (AES-256)
- [ ] Encryption in transit (TLS 1.3)
- [ ] API key encryption in database
- [ ] Secure credential management (HashiCorp Vault)
- [ ] PII data handling compliance

### 7.3 Application Security
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention
- [ ] XSS protection
- [ ] CSRF tokens
- [ ] Rate limiting (per IP, per user)
- [ ] DDoS protection

### 7.4 Audit & Compliance
- [ ] Comprehensive audit logging
- [ ] Login attempt tracking
- [ ] Trade execution audit trail
- [ ] Configuration change logging
- [ ] Security event alerting

---

## 8. Performance Requirements

### 8.1 Trading Performance Benchmarks

| Metric | Acceptable | Good | Excellent |
|--------|------------|------|-----------|
| Win Rate | >45% | >50% | >55% |
| Profit Factor | >1.2 | >1.5 | >2.0 |
| Max Drawdown | <25% | <15% | <10% |
| Sharpe Ratio | >0.5 | >1.0 | >1.5 |
| Monthly Return | >2% | >5% | >10% |

### 8.2 System Performance

| Component | Metric | Target |
|-----------|--------|--------|
| Web Server | Requests/sec | 1000+ |
| Database | Query time | <50ms |
| WebSocket | Message latency | <20ms |
| ML Prediction | Inference time | <10ms |
| Order Placement | Round-trip | <300ms |

---

## 9. Future Roadmap

### 9.1 Short Term (Q1 2026)
1. User authentication system
2. Email/Telegram notifications
3. Mobile responsive design
4. Enhanced error handling
5. Improved documentation

### 9.2 Medium Term (Q2-Q3 2026)
1. Multi-exchange support (Binance, Coinbase)
2. Advanced analytics dashboard
3. Strategy builder interface
4. Portfolio management
5. API rate limiting & security hardening

### 9.3 Long Term (Q4 2026+)
1. Social/copy trading platform
2. Advanced ML pipeline (AutoML, Deep Learning)
3. Tax reporting & compliance
4. Mobile native app (iOS/Android)
5. Institutional features

---

## Appendix A: API Endpoints (Current)

### Trading Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/scalping/start | Start scalping bot |
| POST | /api/scalping/stop | Stop scalping bot |
| GET | /api/scalping/status | Get scalping status |
| POST | /api/short-term/start | Start short-term bot |
| POST | /api/swing/start | Start swing bot |
| POST | /api/long-term/start | Start long-term bot |
| GET | /api/bots/status | Get all bot statuses |

### Data Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/prices | Get current prices |
| GET | /api/signal | Get trading signal |
| GET | /api/indicators | Get technical indicators |
| GET | /api/confluence | Get confluence signals |
| GET | /api/account | Get account info |
| GET | /api/positions | Get open positions |
| GET | /api/trades | Get trade history |

### Configuration Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/config | Get configuration |
| POST | /api/config | Update configuration |
| POST | /api/credentials | Update API keys |

---

## Appendix B: Database Schema

### Current Tables
```sql
-- OHLCV price data
CREATE TABLE ohlcv (
    id INTEGER PRIMARY KEY,
    symbol TEXT,
    timeframe TEXT,
    timestamp INTEGER,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    UNIQUE(symbol, timeframe, timestamp)
);

-- Trade records
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    symbol TEXT,
    side TEXT,
    price REAL,
    amount REAL,
    cost REAL,
    timestamp INTEGER,
    order_id TEXT,
    is_paper BOOLEAN
);

-- Model performance metrics
CREATE TABLE model_performance (
    id INTEGER PRIMARY KEY,
    model_name TEXT,
    symbol TEXT,
    accuracy REAL,
    precision REAL,
    recall REAL,
    f1_score REAL,
    profit_factor REAL,
    sharpe_ratio REAL,
    timestamp INTEGER
);

-- Candle snapshots with indicators
CREATE TABLE candle_snapshots (
    id INTEGER PRIMARY KEY,
    symbol TEXT,
    timestamp_utc TEXT,
    timestamp_ny TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    -- 50+ indicator columns
    rsi_14 REAL,
    macd REAL,
    macd_signal REAL,
    -- ... etc
);
```

### Proposed New Tables
```sql
-- User accounts
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE,
    password_hash TEXT,
    role TEXT,
    created_at TIMESTAMP,
    last_login TIMESTAMP
);

-- API keys (encrypted)
CREATE TABLE api_keys (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    exchange TEXT,
    api_key_encrypted TEXT,
    api_secret_encrypted TEXT,
    created_at TIMESTAMP
);

-- Audit log
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    action TEXT,
    details JSON,
    ip_address TEXT,
    timestamp TIMESTAMP
);

-- Notifications
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    type TEXT,
    message TEXT,
    read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP
);

-- Strategy presets
CREATE TABLE strategy_presets (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    name TEXT,
    bot_type TEXT,
    config JSON,
    created_at TIMESTAMP
);
```

---

## Appendix C: Configuration Options

### Current Configuration (config.yaml)
```yaml
exchange:
  name: kraken
  testnet: false
  rate_limit: true

trading:
  symbols:
    - BTC/USD
    - ETH/USD
  timeframe: 1h

risk:
  max_position_size: 0.1      # 10% of capital
  stop_loss_pct: 0.02         # 2%
  take_profit_pct: 0.04       # 4%
  max_open_positions: 3
  daily_loss_limit: 0.05      # 5%

model:
  type: xgboost
  lookback_periods: 100
  retrain_interval: 168       # hours

scalping:
  enabled: true
  mode: paper
  symbol: BTC/USD
  take_profit_pct: 0.0015     # 0.15%
  stop_loss_pct: 0.001        # 0.1%
  min_confidence: 60
  cooldown_seconds: 30
  max_trades_per_hour: 10
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-15 | Claude | Initial document |

---

*This document should be reviewed and updated quarterly to reflect the evolving state of the application.*


What's Missing (Key Improvements)

  1. Drawing Tools on Chart

  Kraken Pro has extensive drawing tools (trendlines, Fibonacci, rectangles, etc.) directly on the chart. Your current implementation has indicators but no
  freehand drawing capability.

  Missing:
  - Drawing toolbar (line, ray, horizontal line, vertical line, trend line)
  - Fibonacci retracement/extension tools
  - Rectangle, ellipse, price range tools
  - Text annotations
  - Magnet mode for snapping to OHLC

  2. Depth Chart Widget

  Kraken Pro has a dedicated depth chart showing cumulative bid/ask volume visually. You only have the order book table.

  Missing:
  - Visual depth chart (mountain chart showing bids in green, asks in red)
  - Cumulative volume visualization

  3. Recent Trades / Time & Sales Panel

  Your order book shows orders, but there's no live trade stream showing recent market executions.

  Missing:
  - Real-time trade ticker (price, size, time, buy/sell)
  - Aggregate trades by time interval
  - Volume profile

  4. Advanced Order Types

  Kraken Pro supports sophisticated order types.

  Missing:
  - OTOCO (One-Triggers-One-Cancels-Other) bracket orders
  - Trailing stop orders
  - Iceberg orders
  - Post-only / Reduce-only options
  - Time-in-Force options (GTC, IOC, FOK)

  5. Drag Orders on Chart

  Kraken Pro allows dragging pending orders directly on the chart to change price levels.

  Missing:
  - Interactive order handles on chart
  - Drag-to-modify order price
  - Visual SL/TP lines with drag capability



  7. Customizable Widget Layout

  Kraken Pro lets users drag, drop, resize 16+ widgets freely.

  Missing:
  - True drag-and-drop widget system
  - Widget tabs (stacking widgets)
  - Pop-out windows
  - Save/load custom layouts
  - Preset layouts (Simple, Terminal, Advanced)

  8. Watchlist / Market Overview

  A quick view of multiple trading pairs with prices and changes.

  Missing:
  - Watchlist widget with favorites
  - Market overview grid
  - Price alerts

  9. Account Summary Widget

  A dedicated widget for account health.

  Missing:
  - Total equity display
  - Unrealized P&L
  - Margin usage / Available margin
  - Daily P&L chart
  - Position summary

  10. Hotkeys / Trade Shortcuts

  Kraken Pro has keyboard shortcuts for fast trading.

  Missing:
  - Keyboard shortcuts (B for buy, S for sell, etc.)
  - Quick order shortcuts widget
  - One-click trading mode

  11. Mobile Responsiveness

  Your current CSS has basic responsive rules but hides panels under 900px.

  Missing:
  - Proper mobile layout
  - Touch-friendly controls
  - Swipe navigation between panels

  12. Notification System

  Real-time alerts and notifications.

  Missing:
  - Toast notifications for order fills
  - Price alerts
  - Sound alerts
  - Browser push notifications

  ---
  UI Polish Recommendations

  | Area           | Current           | Kraken Pro Standard            |
  |----------------|-------------------|--------------------------------|
  | Logo           | Unicode gear icon | SVG/PNG branded logo           |
  | Loading states | None visible      | Skeleton loaders, spinners     |
  | Empty states   | Basic text        | Illustrated empty states       |
  | Tooltips       | Basic title attr  | Rich tooltips with context     |
  | Animations     | Minimal           | Smooth micro-animations        |
  | Error handling | Basic             | Toast notifications with retry |
  | Font           | Inter (good)      | Add monospace for numbers      |

  ---
  Priority Implementation Order

  1. Drawing tools - Essential for technical analysis
  2. Depth chart - Visual market depth is expected
  3. Recent trades feed - Real-time trade ticker
  4. Hotkeys - Power users expect keyboard shortcuts
  5. Drag orders on chart - Modern trading UX
  6. Toast notifications - User feedback for actions
  7. Watchlist widget - Quick market overview
  8. Account summary widget - Portfolio health at a glance
  9. Advanced order types - OCO, trailing stops
  10. Custom layout system - Full drag-and-drop

  ---
  Quick Wins (Easy to Add)

  1. Add a proper logo - Replace the unicode gear
  2. Add loading spinners - When data is fetching
  3. Add keyboard shortcuts - Basic buy/sell hotkeys
  4. Add toast notifications - For order confirmations
  5. Add a recent trades panel - In bottom panel tabs
  6. Add spread percentage to header stats
  7. Add funding countdown (if supporting futures)
  8. Add a "Take Screenshot" button for chart

  Would you like me to start implementing any of these features? I'd recommend starting with the drawing tools or the depth chart as they add the most visual
   impact.

  ---
  Sources:
  - https://support.kraken.com/articles/kraken-pro-trading-interface-guide
  - https://blog.kraken.com/product/new-analytics-widgets-on-kraken-pro-elevate-your-trading-strategy
  - https://blog.kraken.com/product/create-custom-layouts-on-kraken-pro
  - https://blog.kraken.com/product/crypto-shouldnt-be-cryptic-introducing-krakens-refreshed-web-experience