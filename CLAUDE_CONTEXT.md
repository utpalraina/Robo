# Claude Code Context - Robo Trader Project

> **Last Updated:** 2025-12-17
> **Purpose:** Context file for Claude Code to quickly understand the project state

---

## Project Overview

**Robo Trader** is an ML-based cryptocurrency trading bot for Kraken exchange with:
- Backtesting, paper trading, and live trading capabilities
- ML model predictions (XGBoost) with 79 technical features
- Confluence-based scalping strategy (ICT, SMT, MTF, ML, Technical)
- Web dashboard for monitoring

---

## Recent Setup (Dec 16, 2025)

### 1. Kraken MCP Server Configured
- **Location:** `~/.claude/mcp.json`
- **Status:** Configured, activates on Claude Code restart
- **Purpose:** Direct AI-to-Kraken communication for conversational trading

### 2. Strategies MCP Server Created
- **File:** `strategies_mcp_server.py`
- **MCP Config:** Added to `~/.claude/mcp.json`
- **Tools Available (after restart):**
  - `mcp_list_strategies` - List all trading strategies
  - `mcp_get_strategy(id)` - Get strategy details
  - `mcp_get_rules(id)` - Get trading rules
  - `mcp_compare_strategies(ids)` - Compare strategies
  - `mcp_recommend_strategy(condition)` - Get recommendation
  - `mcp_explain_ict` - Explain ICT concepts
  - `mcp_explain_confluence` - Explain confluence scoring

### 3. Kraken API Module Created
- **File:** `utils/kraken_api.py`
- **Features:**
  - Direct REST API access (no CCXT dependency)
  - Public endpoints: ticker, OHLC, order book, trades
  - Private endpoints: balance, orders, trade history
  - Helper functions: `get_btc_price()`, `get_eth_price()`, `get_account_summary()`

### 3. Unified Trading Runner Created
- **File:** `run_trader.py`
- **Commands:**
  ```bash
  python run_trader.py status          # Account & prices
  python run_trader.py prices          # Live crypto prices
  python run_trader.py paper           # Paper trading (safe)
  python run_trader.py scalp --mode paper  # Scalping bot
  python run_trader.py live --confirm  # LIVE trading (real money)
  python run_trader.py report          # Performance report
  python run_trader.py test-connection # Test API
  ```

### 4. Performance Tracker Created
- **File:** `utils/performance_tracker.py`
- **Database:** `data/performance.db` (SQLite)
- **Tracks:** All trades, daily stats, equity curve, readiness for live trading

### 5. Fixed Kraken Sandbox Issue
- **File:** `utils/helpers.py`
- **Issue:** Kraken doesn't have sandbox mode
- **Fix:** Gracefully handle NotSupported exception, use real data for paper trading

### 6. TARS AI Assistant Created (Dec 17, 2025)
- **Purpose:** TARS (Trading AI Response System) - Chat interface on dashboard for AI-assisted trading
- **Inspired by:** TARS from Interstellar movie
- **AI Provider:** Google Gemini 2.0 Flash (free tier) - switched from Anthropic due to credit limits
- **Files:**
  - `web/tars_assistant.py` - Backend AI assistant
  - `web/static/js/tars.js` - Frontend chat UI with chart integration
  - `web/static/css/tars.css` - Purple-themed styling
- **API Endpoints:**
  - `POST /api/tars/chat` - Send message, get AI response
  - `POST /api/tars/clear` - Clear conversation history
  - `GET /api/tars/status` - Check TARS online status
- **Features:**
  - Chat with AI about trading, strategies, ICT concepts
  - **Chart Drawing:** Draw price levels and zones directly on LightweightCharts
    - `draw_level` - Horizontal price line (support/resistance)
    - `draw_zone` - Two-line zone (e.g., FVG, order block)
  - Set price alerts (`set_alert`)
  - Place orders with confirmation (`place_order`)
  - Direct commands (no AI needed): `btc price`, `eth price`, `list strategies`, `explain ict`, `confluence`
- **UI Access:** Click robot icon button on dashboard header
- **Chart Integration:** Uses `window.state.charts[0]` and `window.state.candleSeries[0]` from trading.js
- **Example Commands:**
  - "BTC price" → Returns current BTC/USD price
  - "Draw support at 85000" → Draws green line at $85,000
  - "Draw FVG zone from 86000 to 87000" → Draws blue zone
  - "Explain ICT concepts" → Lists FVG, Order Blocks, OTE, etc.

---

## Kraken API Credentials

- **Location:** `.env` file and `kraken-mcp-main/.env`
- **Permissions Verified:**
  - Query Funds
  - Query Orders
  - Query Trades
  - Create & Modify Orders
- **Account Status:** No funds (empty balance) - needs funding for live trading

---

## Key Files Structure

```
robo-trader/
├── run_trader.py              # NEW: Unified CLI for trading
├── main.py                    # Original CLI (train, backtest, etc.)
├── .env                       # Kraken API credentials
├── config/config.yaml         # Trading configuration
├── utils/
│   ├── kraken_api.py          # NEW: Direct Kraken API client
│   ├── performance_tracker.py # NEW: Trade performance tracking
│   └── helpers.py             # MODIFIED: Fixed sandbox error
├── engine/
│   ├── paper.py               # Paper trading engine
│   ├── live.py                # Live trading engine
│   └── scalping_bot.py        # Confluence-based scalping bot
├── strategy/
│   ├── ml_strategy.py         # ML-based strategy
│   └── scalping.py            # Scalping strategy with ICT concepts
├── models/
│   └── trained_model.joblib   # Trained XGBoost model
├── strategies_mcp_server.py   # Strategies MCP server
├── kraken-mcp-main/           # Kraken MCP server
│   ├── kraken-server.py       # FastMCP server
│   └── .env                   # API credentials for MCP
├── web/
│   ├── server.py              # FastAPI server with TARS endpoints
│   ├── tars_assistant.py      # TARS AI backend
│   ├── static/
│   │   ├── js/tars.js         # TARS chat frontend
│   │   └── css/tars.css       # TARS styling
│   └── templates/
│       └── trading.html       # Dashboard with TARS panel
└── data/
    └── performance.db         # Trade tracking database
```

---

## Current Status

| Component | Status |
|-----------|--------|
| Kraken API | ✅ Working |
| Paper Trading | ✅ Working (tested) |
| ML Model | ✅ Loaded (79 features) |
| Live Trading | ⏳ Ready (needs account funding) |
| MCP Server | ⏳ Configured (needs Claude restart) |
| Performance Tracking | ✅ Ready |
| TARS AI Chat | ✅ Working (Gemini 2.0, chart drawing enabled) |
| DR/IDR Indicator | ✅ Native (NY session 9:30-10:30 AM) |

---

## Trading Configuration (config/config.yaml)

- **Exchange:** Kraken
- **Symbols:** BTC/USD, ETH/USD
- **Timeframe:** 1h (main), 1m (scalping)
- **Risk:** 2% stop loss, 4% take profit, max 3 positions
- **Model:** XGBoost with RSI, MACD, Bollinger, EMA, ATR, Volume

---

## How to Start

1. **Start the web dashboard with TARS:**
   ```bash
   python -m uvicorn web.server:app --host 0.0.0.0 --port 8000 --reload
   ```
   Then open http://localhost:8000/trading

2. **Run paper trading** to test strategies:
   ```bash
   python run_trader.py paper
   ```

3. **Monitor performance** over days/weeks

4. **Fund Kraken account** when confident

5. **Switch to live trading:**
   ```bash
   python run_trader.py live --confirm
   ```

---

## Quick Commands for Claude

```python
# Check current prices
from utils.kraken_api import get_btc_price, get_eth_price
print(f"BTC: ${get_btc_price():,.2f}")
print(f"ETH: ${get_eth_price():,.2f}")

# Check account
from utils.kraken_api import get_account_summary
print(get_account_summary())

# Full API access
from utils.kraken_api import KrakenAPI
api = KrakenAPI()
api.get_ticker("XBTUSD")
api.get_balance()
api.get_open_orders()
```

---

## User Preferences

- Wants paper trading first before live
- Will fund account after successful backtesting
- Prefers automated/hands-off approach
- New to some concepts - explain things simply

---

## Important Notes

1. **Never place real orders** without `--confirm` flag
2. **Kraken uses USD** (not USDT like Binance)
3. **Pair format:** BTC/USD or XBTUSD (both work)
4. **API rate limits:** Enabled, handled by CCXT/requests
5. **No sandbox:** Kraken doesn't have testnet - paper trading simulates locally
6. **TARS AI Provider:** Using Gemini 2.0 Flash (Anthropic credits exhausted)
   - API key in `.env` as `GEMINI_API_KEY`
   - To switch providers, edit `tars_assistant.py` `_init_ai_client()` method
7. **Server auto-reload:** Use `--reload` flag for development to auto-pick up code changes

---

*Read this file at the start of new sessions to understand project context.*
