# Robo-Trader Development Tracking

> **Purpose**: This file tracks all development progress, planned features, and implementation status. When resuming work after a crash or session break, start here to understand the current state.

---

## Last Updated
**Date**: 2025-12-13
**Session**: Session 5 - Phase 2 Complete (Silver Bullet + SMT Divergence)

---

## Project Overview

**Robo-Trader** is a production-grade ML-powered cryptocurrency trading bot with:
- ML-based signal generation (XGBoost, LightGBM, Random Forest)
- Paper trading, backtesting, and live trading modes
- Real-time web dashboard with WebSocket updates
- 70+ technical indicators
- ICT (Inner Circle Trader) concepts implementation

---

## Current State Summary

### What Exists (Completed)

| Module | Location | Status | Description |
|--------|----------|--------|-------------|
| Data Fetcher | `data/fetcher.py` | COMPLETE | CCXT-based market data acquisition |
| Data Storage | `data/storage.py` | COMPLETE | SQLite persistence layer |
| Kraken WebSocket | `data/kraken_ws.py` | COMPLETE | Real-time market data |
| Candle Collector | `data/candle_collector.py` | COMPLETE | 5-minute candle aggregation |
| Technical Indicators | `features/indicators.py` | COMPLETE | 70+ indicators (RSI, MACD, BB, etc.) |
| DR/IDR Indicators | `features/dr_idr.py` | COMPLETE | Session-based range indicators |
| ICT Indicators | `features/ict_indicators.py` | COMPLETE | Core ICT concepts (see below) |
| ML Models | `models/ml_models.py` | COMPLETE | XGBoost, LightGBM, RF, Ensemble |
| ML Strategy | `strategy/ml_strategy.py` | COMPLETE | Signal generation engine |
| Backtester | `engine/backtester.py` | COMPLETE | Historical backtesting |
| Paper Trader | `engine/paper.py` | COMPLETE | Simulated trading |
| Live Trader | `engine/live.py` | COMPLETE | Real exchange trading |
| Web Dashboard | `web/server.py` | COMPLETE | FastAPI + WebSocket |
| CLI | `main.py` | COMPLETE | Typer-based CLI |
| Background Tasks | `workers/` | COMPLETE | Celery task queue |

### ICT Indicators Already Implemented (`features/ict_indicators.py`)

| Concept | Method | Status | Notes |
|---------|--------|--------|-------|
| Fair Value Gap (FVG) | `detect_fair_value_gaps()` | COMPLETE | Bullish/Bearish FVG detection, fill tracking |
| Market Structure Shift (MSS) | `detect_market_structure_shift()` | COMPLETE | Trend reversal detection |
| Order Blocks (OB) | `detect_order_blocks()` | COMPLETE | Institutional zones with volume confirmation |
| Breaker Blocks | `detect_breaker_blocks()` | COMPLETE | Failed OBs that flip polarity |
| OTE Levels | `calculate_ote_levels()` | COMPLETE | Fibonacci retracement (62%, 70.5%, 79%) |
| Liquidity Zones | `detect_liquidity_zones()` | COMPLETE | Equal highs/lows (stop hunt targets) |
| Premium/Discount Zones | `calculate_premium_discount_zones()` | COMPLETE | Buy/sell territory identification |
| Displacement | `detect_displacement()` | COMPLETE | Strong impulsive moves |
| Swing Points | `detect_swing_points()` | COMPLETE | HH, HL, LH, LL detection |
| Market Structure | `analyze_market_structure()` | COMPLETE | Trend analysis |
| Trading Bias | `get_trading_bias()` | COMPLETE | Combined ICT signal scoring |

---

## What Needs To Be Done (Planned)

### Phase 1: ICT Strategy Integration (HIGH PRIORITY) - COMPLETE

| Task | Location | Status | Description |
|------|----------|--------|-------------|
| ICT Signal Generator | `strategy/ict_strategy.py` | COMPLETE | Generate BUY/SELL/HOLD signals from ICT concepts |
| Session Time Filter | `features/sessions.py` | COMPLETE | NY Killzone (8:30-11:00 AM EST), London, Asia sessions |
| ICT ML Features | `features/ict_features.py` | COMPLETE | 50+ ICT features for ML model integration |
| Confluence Detector | `strategy/confluence.py` | COMPLETE | Multi-factor ICT confluence scoring |
| Daily Bias Calculator | `strategy/daily_bias.py` | COMPLETE | Determine daily direction using higher timeframe analysis |
| API Endpoints | `web/server.py` | COMPLETE | 6 new ICT Strategy API endpoints |
| ICT Backtest | `web/server.py` | COMPLETE | Backtest endpoint for ICT strategy |

### Phase 2: Advanced ICT Concepts (MEDIUM PRIORITY)

| Task | Location | Status | Description |
|------|----------|--------|-------------|
| ICT Dashboard UI | `web/templates/dashboard.html` | **COMPLETE** | Full ICT Strategy page with confluence visualization |
| Silver Bullet Strategy | `strategy/silver_bullet.py` | **COMPLETE** | 10:00-11:00 AM & 2:00-3:00 PM EST setups |
| SMT Divergence | `features/smt_divergence.py` | **COMPLETE** | Smart Money Tool - correlated asset divergence |
| Judas Swing Detector | `features/ict_indicators.py` | NOT STARTED | False move/trap detection |
| Inducement Detection | `features/ict_indicators.py` | NOT STARTED | Stop raid / liquidity hunt patterns |
| Mitigation Block | `features/ict_indicators.py` | NOT STARTED | Imbalance mitigation zones |

### Phase 3: Entry & Risk Management (MEDIUM PRIORITY)

| Task | Location | Status | Description |
|------|----------|--------|-------------|
| OTE Entry Logic | `strategy/ote_entry.py` | NOT STARTED | Entry at 62%/70.5%/79% retracements |
| FVG Entry Logic | `strategy/fvg_entry.py` | NOT STARTED | Enter when price returns to FVG |
| Target Calculator | `strategy/targets.py` | NOT STARTED | -27%, -62% extension targets |
| ICT Stop Loss | `risk/ict_stops.py` | NOT STARTED | Stops beyond liquidity zones |
| 3RR Minimum Filter | `risk/risk_reward.py` | NOT STARTED | Minimum 3:1 risk-reward filter |

### Phase 4: Multi-Timeframe Analysis (LOW PRIORITY)

| Task | Location | Status | Description |
|------|----------|--------|-------------|
| HTF Bias (4H/Daily) | `strategy/htf_analysis.py` | NOT STARTED | Higher timeframe direction |
| LTF Entry (5m/15m) | `strategy/ltf_entry.py` | NOT STARTED | Lower timeframe entry refinement |
| MTF Confluence | `strategy/mtf_confluence.py` | NOT STARTED | Cross-timeframe signal confirmation |

### Phase 5: Testing & Optimization (LOW PRIORITY)

| Task | Location | Status | Description |
|------|----------|--------|-------------|
| ICT Backtest Suite | `tests/test_ict_strategy.py` | NOT STARTED | Unit tests for ICT strategies |
| Strategy Optimizer | `optimization/ict_optimizer.py` | NOT STARTED | Parameter optimization |
| Performance Dashboard | `web/ict_dashboard.py` | NOT STARTED | ICT-specific visualization |

---

## Implementation Details

### ICT OTE (Optimal Trade Entry) Levels Reference

From PDF documentation:

| Level | Meaning | Usage |
|-------|---------|-------|
| 0.5 (50%) | Equilibrium | Fair value zone |
| 0.62 (62%) | OTE Entry #1 | Primary entry level |
| 0.705 (70.5%) | OTE Entry #2 | Best entry (highest probability) |
| 0.79 (79%) | OTE Entry #3 | Deep discount/premium entry |
| -0.27 (-27%) | Target 1 | First take profit |
| -0.62 (-62%) | Target 2 | Second take profit |
| -1.0 (-100%) | Symmetrical Swing | Extended target |
| -2.0 (-200%) | Final Target | Maximum extension |

### ICT Trading Rules (from PDF)

1. **15M Liquidity Taken** - Wait for liquidity sweep
2. **MSS on 5M** - Confirm break of structure on 5-minute
3. **Entry on 3M/2M/1M FVG** - Enter on lower timeframe FVG
4. **Trading Time**: London Session preferred
5. **Minimum Target**: 3RR (3:1 risk-reward)

### Key Time Sessions (EST/New York)

| Session | Time (EST) | Notes |
|---------|------------|-------|
| Asia | 7:00 PM - 4:00 AM | Lower volatility |
| London | 3:00 AM - 12:00 PM | High volatility |
| NY AM | 8:30 AM - 12:00 PM | **Optimal for OTE** |
| NY PM | 1:30 PM - 4:00 PM | Second opportunity |
| Silver Bullet AM | 10:00 AM - 11:00 AM | High probability setup |
| Silver Bullet PM | 2:00 PM - 3:00 PM | High probability setup |

---

## Configuration Reference

### ICT Indicator Parameters (`features/ict_indicators.py`)

```python
config = {
    'fvg_min_gap_pct': 0.1,        # Minimum FVG size (0.1%)
    'displacement_atr_mult': 1.5,  # Displacement = 1.5x ATR
    'ob_volume_mult': 1.3,         # Order block volume threshold
    'swing_lookback': 5,           # Bars for swing detection
    'liquidity_touches': 2,        # Min touches for liquidity zone
}
```

---

## File Structure Reference

```
robo-trader/
├── Agents.md                      # THIS FILE - Development tracking
├── main.py                        # CLI entry point
├── config/
│   └── config.yaml               # Trading configuration
├── data/
│   ├── fetcher.py                # Market data acquisition
│   ├── storage.py                # SQLite persistence
│   ├── kraken_ws.py              # WebSocket client
│   └── candle_collector.py       # Candle aggregation
├── features/
│   ├── indicators.py             # 70+ technical indicators
│   ├── dr_idr.py                 # Session range indicators
│   └── ict_indicators.py         # ICT concepts (COMPLETE)
├── models/
│   ├── base.py                   # Abstract model class
│   └── ml_models.py              # ML classifiers
├── strategy/
│   ├── ml_strategy.py            # ML signal generation
│   ├── ict_strategy.py           # ICT signal generation (PLANNED)
│   ├── confluence.py             # Confluence detection (PLANNED)
│   └── daily_bias.py             # Daily bias (PLANNED)
├── engine/
│   ├── backtester.py             # Backtesting engine
│   ├── paper.py                  # Paper trading
│   └── live.py                   # Live trading
├── risk/
│   └── (ICT risk management)     # (PLANNED)
├── web/
│   └── server.py                 # FastAPI dashboard
├── workers/
│   └── tasks/                    # Celery tasks
└── docs/                         # Documentation
```

---

## How to Resume Work

### Step 1: Check Current Status
1. Read this `Agents.md` file
2. Check the "What Needs To Be Done" section
3. Identify the next task based on priority

### Step 2: Understand Existing Code
1. **ICT Indicators**: `features/ict_indicators.py` (883 lines, fully implemented)
2. **ML Strategy**: `strategy/ml_strategy.py` (reference for new strategies)
3. **Configuration**: `config/config.yaml`

### Step 3: Continue Development
1. Pick the highest priority incomplete task
2. Follow the patterns established in existing code
3. Update this file after completing each task

---

## Session Log

### Session 1: 2025-12-13
**Focus**: Initial planning and analysis
**Completed**:
- Analyzed existing codebase structure
- Read ICT PDFs (Lesson Plan & OTE documentation)
- Discovered comprehensive ICT indicators already implemented
- Created this tracking document

**Key Findings**:
- `features/ict_indicators.py` already implements core ICT concepts
- Need to build strategy layer on top of existing indicators
- Focus should be on signal generation and entry logic

### Session 2: 2025-12-13 (Continued)
**Focus**: ICT Strategy Implementation
**Completed**:
1. Created `strategy/ict_strategy.py` (600+ lines)
   - ICT-based signal generation
   - Confluence scoring system
   - Session-aware trading
   - Entry/exit logic with SL/TP
   - ML model integration support

2. Created `features/sessions.py` (400+ lines)
   - Trading session identification (Asia, London, NY)
   - Silver Bullet window detection
   - NY Killzone detection
   - Session filtering for DataFrames
   - Session statistics calculation

3. Created `features/ict_features.py` (600+ lines)
   - 50+ ICT features for ML integration
   - FVG proximity features
   - MSS recency features
   - Order Block distance features
   - OTE level distance features
   - Premium/Discount zone features
   - Liquidity zone features
   - Market structure scores
   - Session indicators

4. Created `strategy/confluence.py` (700+ lines)
   - Sophisticated confluence scoring system
   - 10 confluence factors analyzed
   - Entry/SL/TP calculation
   - Risk/Reward validation
   - Human-readable explanations

**Files Created**:
- `strategy/ict_strategy.py` - ICT Strategy with confluence scoring
- `features/sessions.py` - Session time filtering
- `features/ict_features.py` - ICT features for ML
- `strategy/confluence.py` - Confluence detection system

### Session 3: 2025-12-13 (Continued)
**Focus**: API Integration & Daily Bias
**Completed**:
1. Added ICT Strategy API endpoints to `web/server.py`:
   - `GET /api/ict-strategy/signal/{symbol}` - Full ICT signal with confluence
   - `GET /api/ict-strategy/confluence/{symbol}` - Detailed confluence analysis
   - `GET /api/ict-strategy/session` - Current session info
   - `GET /api/ict-strategy/features/{symbol}` - ICT ML features
   - `POST /api/ict-strategy/backtest` - ICT strategy backtest
   - `GET /api/ict-strategy/daily-bias/{symbol}` - Daily directional bias

2. Created `strategy/daily_bias.py` (500+ lines):
   - Daily directional bias calculation
   - Previous Day/Week High/Low analysis
   - Asian Range analysis
   - London Open direction
   - Gap analysis
   - Higher timeframe structure analysis
   - Key levels identification (PDH, PDL, PWH, PWL)

**Files Created/Modified**:
- `strategy/daily_bias.py` - Daily Bias Calculator (NEW)
- `web/server.py` - Added 6 new ICT Strategy API endpoints

**Next Steps**:
1. ~~Create dashboard UI components for ICT visualization~~ DONE
2. Add WebSocket broadcast for ICT signals
3. Implement Silver Bullet specific strategy
4. Add SMT Divergence detection

### Session 4: 2025-12-13 (Continued)
**Focus**: ICT Dashboard UI Implementation
**Completed**:
1. Created ICT Strategy Dashboard Page (`web/templates/dashboard.html`):
   - ICT Strategy nav item added to sidebar
   - Header stats grid (Session, Daily Bias, ICT Signal, Confluence Score)
   - Signal Analysis card with entry/exit details
   - Key ICT Levels card (PDH, PDL, PWH, PWL, Premium/Discount zones)
   - Confluence Factors visualization (10 factors with progress bars)
   - Active ICT Patterns display (FVG, MSS, OB, OTE, Liquidity)
   - ICT Backtest form and results display

2. Added ICT CSS Styles (`web/static/css/style.css`):
   - ~430 lines of ICT-specific styles
   - Responsive design for different screen sizes
   - Signal badges, confluence bars, pattern icons
   - Level displays with premium/discount coloring

3. Added ICT JavaScript Handlers (`web/static/js/app.js`):
   - `loadIctData()` - Main ICT data loader
   - `loadIctSession()` - Session time API call
   - `loadIctDailyBias()` - Daily bias API call
   - `loadIctSignal()` - ICT signal API call
   - `loadIctConfluence()` - Confluence factors API call
   - `updateIctPatterns()` - Pattern display updater
   - `updateConfluenceFactor()` - Factor bar updater
   - `runIctBacktest()` - ICT backtest execution

**Files Modified**:
- `web/templates/dashboard.html` - Added ~330 lines of ICT page HTML
- `web/static/css/style.css` - Added ~430 lines of ICT styles
- `web/static/js/app.js` - Added ~400 lines of ICT JavaScript

**Dashboard Features**:
- 4 header stat cards: Session, Daily Bias, ICT Signal, Confluence
- Signal details: Direction, Entry, Stop Loss, Take Profit, Risk/Reward
- Key levels: PDH/PDL, PWH/PWL, Equilibrium, Premium/Discount zones
- 10 confluence factors with visual scoring (0-30 points total)
- 5 pattern detectors: FVG, MSS, Order Block, OTE, Liquidity
- ICT-specific backtest with min confluence parameter

**Next Steps**:
1. ~~Implement Silver Bullet specific strategy~~ DONE
2. ~~Add SMT Divergence detection~~ DONE
3. Add WebSocket broadcast for real-time ICT updates

### Session 5: 2025-12-13 (Continued)
**Focus**: Silver Bullet Strategy & SMT Divergence
**Completed**:
1. Created Silver Bullet Strategy (`strategy/silver_bullet.py` ~650 lines):
   - AM Window: 10:00 AM - 11:00 AM EST
   - PM Window: 2:00 PM - 3:00 PM EST
   - Liquidity sweep detection (PDH/PDL, Asian High/Low, Equal Highs/Lows)
   - Market Structure Shift (MSS) confirmation
   - Entry zone identification (FVG, Order Block, OTE)
   - Risk management with Fibonacci extensions
   - Full setup analysis with confidence scoring

2. Created SMT Divergence Detector (`features/smt_divergence.py` ~500 lines):
   - Bullish SMT: Asset A lower low, Asset B higher low (accumulation)
   - Bearish SMT: Asset A higher high, Asset B lower high (distribution)
   - Correlation calculation between assets
   - Swing point detection algorithm
   - ML feature generation for SMT signals

3. Added API Endpoints to `web/server.py`:
   - `GET /api/ict-strategy/silver-bullet/{symbol}` - Full Silver Bullet setup analysis
   - `GET /api/ict-strategy/silver-bullet/status` - Current window status
   - `GET /api/ict-strategy/smt-divergence/{symbol}` - SMT divergence analysis
   - `GET /api/ict-strategy/smt-divergence/multi/{symbol}` - Multi-asset SMT analysis

**Files Created/Modified**:
- `strategy/silver_bullet.py` - Silver Bullet Strategy (NEW)
- `features/smt_divergence.py` - SMT Divergence Detection (NEW)
- `web/server.py` - Added 4 new API endpoints

**API Summary (Total ICT Endpoints: 12)**:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ict-strategy/signal/{symbol}` | GET | ICT signal with confluence |
| `/api/ict-strategy/confluence/{symbol}` | GET | Detailed confluence analysis |
| `/api/ict-strategy/session` | GET | Current trading session |
| `/api/ict-strategy/features/{symbol}` | GET | ICT ML features |
| `/api/ict-strategy/backtest` | POST | ICT strategy backtest |
| `/api/ict-strategy/daily-bias/{symbol}` | GET | Daily directional bias |
| `/api/ict-strategy/silver-bullet/{symbol}` | GET | Silver Bullet setup |
| `/api/ict-strategy/silver-bullet/status` | GET | Silver Bullet window status |
| `/api/ict-strategy/smt-divergence/{symbol}` | GET | SMT divergence |
| `/api/ict-strategy/smt-divergence/multi/{symbol}` | GET | Multi-asset SMT |

**Phase 2 Complete!**

---

## Notes & Decisions

### Design Decisions
1. **Modular Architecture**: Each ICT concept has its own detector
2. **Signal Scoring**: Multiple ICT factors combined for confidence
3. **Time-Based Filtering**: Only trade during optimal sessions
4. **Risk-Reward Minimum**: 3:1 minimum before entry

### PDF Reference Documents
- `ICT C0ncepts Lesson Plan Order.pdf` - Learning curriculum
- `ICT Optimal Trade Entry (OTE) (2) (1).pdf` - OTE strategy details

### External Resources
- TradingView Indicator: FVG (nephew_sam)
- Backtesting Data: backtestbull.com

---

## Quick Commands

```bash
# Train model
python main.py train --symbol BTC/USDT --start-date 2024-01-01 --end-date 2024-11-01

# Paper trade
python main.py paper --symbols BTC/USDT,ETH/USDT --interval 60

# Live trade
python main.py live --symbols BTC/USDT --confirm

# Start web dashboard
python main.py web --port 8000

# Run backtest
python main.py backtest --symbol BTC/USDT --start-date 2024-01-01 --end-date 2024-06-01
```

---

*This document should be updated after each development session to maintain continuity.*

---

## ICT Implementation Architecture (Data Flow)

### Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              ICT TRADING SYSTEM DATA FLOW                               │
└─────────────────────────────────────────────────────────────────────────────────────────┘

                                    ┌─────────────────┐
                                    │  EXTERNAL DATA  │
                                    │    (Kraken)     │
                                    └────────┬────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        ▼
         ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
         │  REST API Poll   │    │ WebSocket Feed   │    │ Historical Data  │
         │ (data/fetcher.py)│    │(data/kraken_ws.py│    │ (data/fetcher.py)│
         │   1-sec ticks    │    │  50-100ms ticks  │    │   Batch fetch    │
         └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
                  │                       │                       │
                  └───────────────────────┼───────────────────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │    OHLCV DataFrame    │
                              │   (Pandas in-memory)  │
                              └───────────┬───────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
                    ▼                     ▼                     ▼
┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
│   TECHNICAL INDICATORS  │ │    ICT INDICATORS       │ │    DR/IDR INDICATORS    │
│ (features/indicators.py)│ │(features/ict_indicators)│ │  (features/dr_idr.py)   │
│                         │ │                         │ │                         │
│ • RSI, MACD, BB, EMA    │ │ • FVG Detection         │ │ • Defining Range        │
│ • Stochastic, ADX       │ │ • MSS Detection         │ │ • Initial Def Range     │
│ • ATR, CCI, OBV         │ │ • Order Blocks          │ │ • Session Ranges        │
│ • 70+ indicators        │ │ • Breaker Blocks        │ │ • Extension Lines       │
│                         │ │ • OTE Levels (Fib)      │ │                         │
│                         │ │ • Liquidity Zones       │ │                         │
│                         │ │ • Premium/Discount      │ │                         │
│                         │ │ • Displacement          │ │                         │
│                         │ │ • Swing Points          │ │                         │
│                         │ │ • Market Structure      │ │                         │
│                         │ │ • Trading Bias          │ │                         │
└───────────┬─────────────┘ └───────────┬─────────────┘ └───────────┬─────────────┘
            │                           │                           │
            └───────────────────────────┼───────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                  DATABASE STORAGE                                        │
│                              (data/storage.py - SQLite)                                  │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │     ohlcv       │  │ candle_snapshots│  │     trades      │  │model_performance│    │
│  │                 │  │                 │  │                 │  │                 │    │
│  │ • timestamp     │  │ • OHLCV data    │  │ • symbol        │  │ • accuracy      │    │
│  │ • open,high,low │  │ • All indicators│  │ • side          │  │ • precision     │    │
│  │ • close,volume  │  │ • prediction    │  │ • price,amount  │  │ • recall, F1    │    │
│  │                 │  │ • confidence    │  │ • is_paper      │  │ • sharpe_ratio  │    │
│  │                 │  │ • explanation   │  │                 │  │                 │    │
│  │                 │  │ • validation    │  │                 │  │                 │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                           ICT INDICATOR TABLES                                   │   │
│  ├─────────────────────────────────────────────────────────────────────────────────┤   │
│  │                                                                                  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │   │
│  │  │   ict_fvg    │  │   ict_mss    │  │ict_order_blk │  │ict_breaker   │         │   │
│  │  │              │  │              │  │              │  │              │         │   │
│  │  │ • type       │  │ • type       │  │ • type       │  │ • type       │         │   │
│  │  │ • top/bottom │  │ • broken_lvl │  │ • high/low   │  │ • high/low   │         │   │
│  │  │ • gap_size   │  │ • break_price│  │ • volume     │  │ • original   │         │   │
│  │  │ • filled     │  │ • strength   │  │ • tested     │  │ • tested     │         │   │
│  │  │ • filled_pct │  │ • confirmed  │  │ • mitigated  │  │              │         │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘         │   │
│  │                                                                                  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │   │
│  │  │ict_liquidity │  │ict_displace │  │ict_swing_pts │  │ict_ote_lvls  │         │   │
│  │  │              │  │              │  │              │  │              │         │   │
│  │  │ • type       │  │ • type       │  │ • type       │  │ • swing_high │         │   │
│  │  │ • level      │  │ • body_size  │  │ • price      │  │ • swing_low  │         │   │
│  │  │ • touches    │  │ • atr_ratio  │  │ • broken     │  │ • ote_62/705 │         │   │
│  │  │ • swept      │  │ • is_hi_vol  │  │              │  │ • targets    │         │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘         │   │
│  │                                                                                  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                           │   │
│  │  │ict_premium_  │  │ict_market_  │  │ict_trading_  │                           │   │
│  │  │  discount    │  │  structure   │  │    bias      │                           │   │
│  │  │              │  │              │  │              │                           │   │
│  │  │ • zone       │  │ • trend      │  │ • bias       │                           │   │
│  │  │ • bias       │  │ • hh/hl/lh/ll│  │ • confidence │                           │   │
│  │  │ • position%  │  │ • scores     │  │ • validated  │                           │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                           │   │
│  │                                                                                  │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
└───────────────────────────────────────────┬─────────────────────────────────────────────┘
                                            │
              ┌─────────────────────────────┼─────────────────────────────┐
              │                             │                             │
              ▼                             ▼                             ▼
┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────┐
│    ML PREDICTION        │   │    STRATEGY ENGINE      │   │    WEB DISPLAY          │
│   (models/ml_models.py) │   │ (strategy/ml_strategy)  │   │    (web/server.py)      │
│                         │   │                         │   │                         │
│ Features from DB/Live:  │   │ • Signal Generation     │   │ REST API Endpoints:     │
│ • 70+ tech indicators   │   │ • Risk Management       │   │ • /api/ict/{symbol}     │
│ • ICT indicators as     │   │ • Position Sizing       │   │ • /api/ict/fvg/{symbol} │
│   additional features   │   │ • Stop Loss/Take Profit │   │ • /api/ict/ote/{symbol} │
│                         │   │                         │   │ • /api/ict/bias/{symbol}│
│ Models:                 │   │ Input Sources:          │   │ • /api/ict/mss/{symbol} │
│ • XGBoost               │   │ • ML model prediction   │   │                         │
│ • LightGBM              │   │ • ICT trading_bias      │   │ WebSocket (/ws):        │
│ • RandomForest          │   │ • Risk parameters       │   │ • Real-time ticker      │
│ • Ensemble              │   │                         │   │ • Trading signals       │
│                         │   │ Output:                 │   │ • Account updates       │
│ Output:                 │   │ • BUY/SELL/HOLD         │   │                         │
│ • Probability (0-1)     │   │ • Confidence score      │   │ Dashboard:              │
│                         │   │ • Position size         │   │ • /templates/dashboard  │
│                         │   │ • SL/TP levels          │   │ • /static/js/           │
└───────────┬─────────────┘   └───────────┬─────────────┘   └───────────┬─────────────┘
            │                             │                             │
            └─────────────────────────────┼─────────────────────────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │   EXECUTION ENGINE    │
                              ├───────────────────────┤
                              │ • engine/backtester.py│
                              │ • engine/paper.py     │
                              │ • engine/live.py      │
                              └───────────┬───────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
                    ▼                     ▼                     ▼
         ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
         │    BACKTEST      │  │   PAPER TRADE    │  │   LIVE TRADE     │
         │                  │  │                  │  │                  │
         │ Historical data  │  │ Simulated orders │  │ Real orders to   │
         │ Performance eval │  │ Virtual P&L      │  │ exchange (Kraken)│
         └──────────────────┘  └──────────────────┘  └──────────────────┘
```

### Detailed Component Interactions

#### 1. Data Collection Layer

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA COLLECTION FLOW                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Kraken Exchange                                                │
│       │                                                         │
│       ├──► WebSocket (data/kraken_ws.py)                       │
│       │         │                                               │
│       │         ▼                                               │
│       │    on_kraken_tick() callback                           │
│       │         │                                               │
│       │         ▼                                               │
│       │    broadcast() to all WebSocket clients                │
│       │         │                                               │
│       │         ▼                                               │
│       │    Dashboard real-time price display                   │
│       │                                                         │
│       └──► REST API (data/fetcher.py)                          │
│                 │                                               │
│                 ├──► fetch_ohlcv() - Latest candles            │
│                 ├──► fetch_historical_data() - Bulk history    │
│                 └──► fetch_ticker() - Current price            │
│                                                                 │
│  Every 5 minutes (data/candle_collector.py):                   │
│       │                                                         │
│       ├──► Fetch latest 5-min candle                           │
│       ├──► Calculate ALL indicators                            │
│       ├──► Generate ML prediction                              │
│       ├──► Save to candle_snapshots table                      │
│       └──► Validate previous predictions                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 2. ICT Detection & Storage

```
┌─────────────────────────────────────────────────────────────────┐
│                 ICT DETECTION & STORAGE FLOW                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  API Request: GET /api/ict/{symbol}                            │
│       │                                                         │
│       ▼                                                         │
│  web/server.py: get_ict_indicators()                           │
│       │                                                         │
│       ├──► Fetch OHLCV data (200 candles)                      │
│       │                                                         │
│       ▼                                                         │
│  ICTIndicators(df).detect_all()                                │
│       │                                                         │
│       ├──► detect_fair_value_gaps()     ──► ict_fvg table      │
│       ├──► detect_market_structure_shift() ► ict_mss table     │
│       ├──► detect_order_blocks()        ──► ict_order_blocks   │
│       ├──► detect_breaker_blocks()      ──► ict_breaker_blocks │
│       ├──► calculate_ote_levels()       ──► ict_ote_levels     │
│       ├──► detect_liquidity_zones()     ──► ict_liquidity_zones│
│       ├──► calculate_premium_discount() ──► ict_premium_discount│
│       ├──► detect_displacement()        ──► ict_displacement   │
│       ├──► detect_swing_points()        ──► ict_swing_points   │
│       ├──► analyze_market_structure()   ──► ict_market_structure│
│       └──► get_trading_bias()           ──► ict_trading_bias   │
│                                                                 │
│       ▼                                                         │
│  storage.save_ict_indicators(results, symbol, timeframe)       │
│       │                                                         │
│       ▼                                                         │
│  Return JSON response to dashboard                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 3. Screen Display (Web Dashboard)

```
┌─────────────────────────────────────────────────────────────────┐
│                    WEB DISPLAY ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  FastAPI Server (web/server.py)                                │
│       │                                                         │
│       ├──► Static Files: /static/js/, /static/css/             │
│       ├──► Templates: /templates/dashboard.html                │
│       │                                                         │
│       │   REST API Endpoints:                                  │
│       │   ┌─────────────────────────────────────────────────┐  │
│       │   │ /api/ict/{symbol}           All ICT indicators  │  │
│       │   │ /api/ict/fvg/{symbol}       Fair Value Gaps     │  │
│       │   │ /api/ict/mss/{symbol}       Market Structure    │  │
│       │   │ /api/ict/ote/{symbol}       OTE Levels          │  │
│       │   │ /api/ict/bias/{symbol}      Trading Bias        │  │
│       │   │ /api/ict/order-blocks/{symbol}  Order Blocks    │  │
│       │   │ /api/ict/bias-accuracy/{symbol} Accuracy Stats  │  │
│       │   │ /api/ict/history/{type}/{symbol} Historical     │  │
│       │   └─────────────────────────────────────────────────┘  │
│       │                                                         │
│       │   WebSocket Endpoint: /ws                              │
│       │   ┌─────────────────────────────────────────────────┐  │
│       │   │ Real-time broadcasts:                           │  │
│       │   │ • ticker: price, bid, ask, volume               │  │
│       │   │ • update: signal, confidence                    │  │
│       │   │ • account: cash, equity, pnl                    │  │
│       │   │ • training: status updates                      │  │
│       │   └─────────────────────────────────────────────────┘  │
│       │                                                         │
│  Dashboard UI Components:                                      │
│       │                                                         │
│       ├──► Price Chart (TradingView/Lightweight Charts)        │
│       │         │                                               │
│       │         ├──► FVG zones (shaded rectangles)             │
│       │         ├──► Order Block zones                         │
│       │         ├──► OTE Fibonacci levels (horizontal lines)   │
│       │         ├──► Swing points (markers)                    │
│       │         └──► Liquidity zones (dotted lines)            │
│       │                                                         │
│       ├──► ICT Panel (sidebar/overlay)                         │
│       │         │                                               │
│       │         ├──► Current Bias: BULLISH/BEARISH (badge)     │
│       │         ├──► Confidence: 75% (progress bar)            │
│       │         ├──► Zone: Premium/Discount (indicator)        │
│       │         ├──► Active FVGs list                          │
│       │         ├──► Recent MSS events                         │
│       │         └──► OTE entry levels                          │
│       │                                                         │
│       └──► Signal Panel                                        │
│                 │                                               │
│                 ├──► ML Prediction: BUY/SELL/HOLD              │
│                 ├──► ICT Bias alignment indicator              │
│                 └──► Combined confidence score                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 4. ML Prediction Integration

```
┌─────────────────────────────────────────────────────────────────┐
│              ML PREDICTION WITH ICT FEATURES                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  CURRENT ML FLOW (70+ Technical Indicators):                   │
│                                                                 │
│  OHLCV Data ──► FeatureEngineer.generate_features()            │
│       │              │                                          │
│       │              ├──► RSI (7, 14)                          │
│       │              ├──► MACD, Signal, Histogram               │
│       │              ├──► Bollinger Bands (upper, lower, width) │
│       │              ├──► EMA (9, 21, 50), SMA (20, 50)        │
│       │              ├──► Stochastic (K, D)                    │
│       │              ├──► ADX, DI+, DI-                        │
│       │              ├──► ATR, CCI, OBV, VWAP                  │
│       │              └──► ... (70+ total)                      │
│       │                                                         │
│       ▼                                                         │
│  XGBoost/LightGBM Model                                        │
│       │                                                         │
│       ▼                                                         │
│  Probability [0.0 - 1.0]                                       │
│       │                                                         │
│       ├──► prob >= 0.6  ──► BUY signal                         │
│       ├──► prob <= 0.4  ──► SELL signal                        │
│       └──► otherwise    ──► HOLD signal                        │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  ENHANCED ML FLOW (With ICT Features) - TO IMPLEMENT:          │
│                                                                 │
│  OHLCV Data                                                    │
│       │                                                         │
│       ├──► Technical Indicators (70+)                          │
│       │                                                         │
│       └──► ICT Indicators (NEW FEATURES):                      │
│                 │                                               │
│                 ├──► is_in_fvg (0/1)                           │
│                 ├──► fvg_type (bullish=1, bearish=-1, none=0)  │
│                 ├──► distance_to_nearest_fvg                   │
│                 ├──► mss_type (bullish=1, bearish=-1, none=0)  │
│                 ├──► mss_recency (candles since last MSS)      │
│                 ├──► ob_proximity (distance to nearest OB)     │
│                 ├──► ob_type (bullish=1, bearish=-1)           │
│                 ├──► premium_discount_zone (-1 to 1)           │
│                 ├──► ote_distance (distance to 62% level)      │
│                 ├──► liquidity_above (distance)                │
│                 ├──► liquidity_below (distance)                │
│                 ├──► displacement_strength                     │
│                 ├──► market_structure_score                    │
│                 └──► ict_bias_score                            │
│                                                                 │
│       ▼                                                         │
│  Combined Feature Vector (85+ features)                        │
│       │                                                         │
│       ▼                                                         │
│  ML Model (retrained with ICT features)                        │
│       │                                                         │
│       ▼                                                         │
│  Enhanced Prediction with ICT awareness                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 5. Signal Generation with ICT Confluence

```
┌─────────────────────────────────────────────────────────────────┐
│              ICT CONFLUENCE SIGNAL GENERATION                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TO IMPLEMENT: strategy/ict_strategy.py                        │
│                                                                 │
│  Input Sources:                                                │
│       │                                                         │
│       ├──► ML Model Prediction (BUY/SELL/HOLD + confidence)    │
│       ├──► ICT Trading Bias (bullish/bearish + confidence)     │
│       └──► Individual ICT Signals:                             │
│                 │                                               │
│                 ├──► FVG: Price in unfilled gap?               │
│                 ├──► MSS: Recent structure shift?              │
│                 ├──► OB: Price at order block?                 │
│                 ├──► OTE: Price at Fibonacci level?            │
│                 ├──► Zone: Premium or Discount?                │
│                 └──► Liquidity: Near stop hunt level?          │
│                                                                 │
│  Confluence Scoring:                                           │
│       │                                                         │
│       │  Example BUY Confluence Score:                         │
│       │  ┌──────────────────────────────────────────────────┐  │
│       │  │ ML Model says BUY (0.75 conf)     +3 points      │  │
│       │  │ ICT Bias is BULLISH               +2 points      │  │
│       │  │ Price in DISCOUNT zone            +2 points      │  │
│       │  │ Price at bullish OB               +2 points      │  │
│       │  │ Price near OTE 62% level          +2 points      │  │
│       │  │ Recent bullish MSS                +2 points      │  │
│       │  │ Bullish FVG below (support)       +1 point       │  │
│       │  │ In NY Session (8:30-11 AM)        +1 point       │  │
│       │  │ ────────────────────────────────────────         │  │
│       │  │ TOTAL: 15/15 = HIGH CONFLUENCE                   │  │
│       │  └──────────────────────────────────────────────────┘  │
│       │                                                         │
│       ▼                                                         │
│  Signal Decision:                                              │
│       │                                                         │
│       ├──► Score >= 12: STRONG BUY (enter full position)       │
│       ├──► Score >= 8:  BUY (enter half position)              │
│       ├──► Score >= 5:  WEAK BUY (wait for confirmation)       │
│       └──► Score < 5:   HOLD (no trade)                        │
│                                                                 │
│  Risk Management:                                              │
│       │                                                         │
│       ├──► Stop Loss: Below nearest liquidity zone             │
│       ├──► Take Profit 1: OTE -27% extension                   │
│       ├──► Take Profit 2: OTE -62% extension                   │
│       └──► Minimum R:R: 3:1                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Database Schema Summary

```sql
-- Existing Tables (Already in storage.py)
-- ─────────────────────────────────────────

-- Core Tables
ohlcv                    -- Raw OHLCV candle data
trades                   -- Trade execution records
model_performance        -- ML model metrics
candle_snapshots         -- 5-min snapshots with indicators + predictions

-- ICT Tables (Already Created)
ict_fvg                  -- Fair Value Gaps
ict_mss                  -- Market Structure Shifts
ict_order_blocks         -- Order Blocks
ict_breaker_blocks       -- Breaker Blocks
ict_liquidity_zones      -- Liquidity Zones
ict_displacement         -- Displacement Candles
ict_swing_points         -- Swing Highs/Lows
ict_ote_levels           -- OTE Fibonacci Levels
ict_premium_discount     -- Premium/Discount Zone Snapshots
ict_market_structure     -- Market Structure Analysis
ict_trading_bias         -- Combined ICT Bias + Validation
```

### API Endpoint Reference

```
ICT API Endpoints (Already Implemented in web/server.py)
────────────────────────────────────────────────────────

GET  /api/ict/{symbol}                    - All ICT indicators (live detection)
GET  /api/ict/fvg/{symbol}                - Fair Value Gaps from DB
GET  /api/ict/order-blocks/{symbol}       - Order Blocks from DB
GET  /api/ict/mss/{symbol}                - Market Structure Shifts from DB
GET  /api/ict/ote/{symbol}                - Calculate OTE levels live
GET  /api/ict/bias/{symbol}               - Get trading bias analysis
GET  /api/ict/bias-accuracy/{symbol}      - Bias prediction accuracy stats
GET  /api/ict/history/{type}/{symbol}     - Historical ICT data by type

Parameters:
  - symbol: Trading pair (e.g., BTC-USDT)
  - timeframe: 1m, 5m, 15m, 1h, 4h, 1d (default: 5m)
  - limit: Number of records (default: 50-200)
  - unfilled_only: Filter FVGs (true/false)
  - unmitigated_only: Filter OBs (true/false)
```

### What's Already Working vs What Needs Implementation

```
┌────────────────────────────────────────────────────────────────┐
│                    IMPLEMENTATION STATUS                        │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✅ COMPLETE (Ready to Use):                                   │
│  ─────────────────────────────────────────────────────────────  │
│  • ICT Indicators Detection (features/ict_indicators.py)       │
│  • Database Tables for all ICT data (data/storage.py)          │
│  • Save/Load ICT data to SQLite                                │
│  • REST API endpoints for ICT data (web/server.py)             │
│  • WebSocket real-time price feed                              │
│  • ML model training and prediction                            │
│  • Paper/Live trading engine                                   │
│  • Backtesting engine                                          │
│  • Web dashboard foundation                                    │
│                                                                 │
│  🔨 NEEDS IMPLEMENTATION:                                      │
│  ─────────────────────────────────────────────────────────────  │
│  • ICT-based Strategy (strategy/ict_strategy.py)               │
│  • Session Time Filtering (NY Killzone, London, Asia)          │
│  • ICT Features for ML (integrate into feature vector)         │
│  • Confluence Detection System                                 │
│  • Dashboard ICT Visualization (chart overlays)                │
│  • Silver Bullet Strategy                                      │
│  • Judas Swing Detection                                       │
│  • SMT Divergence                                              │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```
