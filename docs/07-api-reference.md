# API Reference

Complete REST API and WebSocket reference for Robo Trader.

---

## Base URL

| Environment | URL |
|-------------|-----|
| Development | `http://localhost:8000` |
| Production | `http://localhost` or `https://your-domain.com` |

---

## Authentication

Currently, the API does not require authentication. For production, implement authentication before exposing to the internet.

---

## REST API Endpoints

### System

#### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-12-10T12:00:00.000Z"
}
```

#### GET /api/status
Get current trading status.

**Response:**
```json
{
  "is_trading": true,
  "trading_mode": "paper",
  "active_symbols": ["BTC/USDT", "ETH/USDT"],
  "model_loaded": true,
  "timestamp": "2024-12-10T12:00:00.000Z"
}
```

---

### Account

#### GET /api/account
Get account information.

**Response:**
```json
{
  "cash": 9500.00,
  "equity": 10234.56,
  "total_pnl": 234.56,
  "daily_pnl": 56.78,
  "positions": 2,
  "mode": "paper"
}
```

---

### Positions

#### GET /api/positions
Get current open positions.

**Response:**
```json
{
  "positions": [
    {
      "symbol": "BTC/USDT",
      "side": "long",
      "size": 0.001234,
      "entry_price": 45234.56,
      "unrealized_pnl": 56.78,
      "entry_time": "2024-12-10T10:00:00.000Z"
    }
  ]
}
```

---

### Trades

#### GET /api/trades
Get trade history.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Maximum trades to return |

**Example:**
```
GET /api/trades?limit=100
```

**Response:**
```json
{
  "trades": [
    {
      "id": 1,
      "symbol": "BTC/USDT",
      "side": "buy",
      "price": 45234.56,
      "amount": 0.001234,
      "cost": 55.82,
      "timestamp": "2024-12-10T10:00:00.000Z",
      "is_paper": true
    }
  ]
}
```

---

### Market Data

#### GET /api/prices/{symbol}
Get OHLCV price data for charting.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `symbol` | string | Trading pair (use `-` instead of `/`) |

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 100 | Number of candles |

**Example:**
```
GET /api/prices/BTC-USDT?limit=200
```

**Response:**
```json
{
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "data": [
    {
      "time": "2024-12-10T10:00:00.000Z",
      "open": 45000.00,
      "high": 45500.00,
      "low": 44800.00,
      "close": 45234.56,
      "volume": 1234.56
    }
  ]
}
```

#### GET /api/ticker/{symbol}
Get current ticker data.

**Example:**
```
GET /api/ticker/BTC-USDT
```

**Response:**
```json
{
  "symbol": "BTC/USDT",
  "bid": 45230.00,
  "ask": 45235.00,
  "last": 45234.56,
  "volume": 12345.67,
  "timestamp": "2024-12-10T12:00:00.000Z"
}
```

#### GET /api/indicators/{symbol}
Get technical indicators.

**Example:**
```
GET /api/indicators/BTC-USDT
```

**Response:**
```json
{
  "symbol": "BTC/USDT",
  "timestamp": "2024-12-10T12:00:00.000Z",
  "price": 45234.56,
  "rsi_14": 55.23,
  "macd": 123.45,
  "macd_signal": 100.23,
  "bb_upper": 46000.00,
  "bb_lower": 44000.00,
  "ema_9": 45100.00,
  "ema_21": 45000.00,
  "atr_14": 500.00,
  "volume_ratio": 1.23
}
```

---

### Signals

#### GET /api/signal/{symbol}
Get ML trading signal.

**Example:**
```
GET /api/signal/BTC-USDT
```

**Response:**
```json
{
  "symbol": "BTC/USDT",
  "signal": "BUY",
  "confidence": 0.72,
  "timestamp": "2024-12-10T12:00:00.000Z"
}
```

**Signal Values:**
| Signal | Description |
|--------|-------------|
| `BUY` | Model predicts price increase |
| `SELL` | Model predicts price decrease |
| `HOLD` | No strong signal |

---

### Trading Control

#### POST /api/start
Start trading.

**Request Body:**
```json
{
  "symbols": ["BTC/USDT", "ETH/USDT"],
  "mode": "paper"
}
```

**Response:**
```json
{
  "status": "started",
  "mode": "paper",
  "symbols": ["BTC/USDT", "ETH/USDT"]
}
```

#### POST /api/stop
Stop trading.

**Response:**
```json
{
  "status": "stopped"
}
```

---

### Model Training

#### POST /api/train
Start model training (background task).

**Request Body:**
```json
{
  "symbol": "BTC/USDT",
  "start_date": "2024-01-01",
  "end_date": "2024-11-01"
}
```

**Response:**
```json
{
  "status": "training_started"
}
```

Training progress is sent via WebSocket.

---

### Backtesting

#### POST /api/backtest
Run backtest.

**Request Body:**
```json
{
  "symbol": "BTC/USDT",
  "start_date": "2024-01-01",
  "end_date": "2024-11-01"
}
```

**Response:**
```json
{
  "total_return": 0.1245,
  "sharpe_ratio": 1.23,
  "max_drawdown": -0.0834,
  "win_rate": 0.5705,
  "profit_factor": 1.45,
  "total_trades": 156,
  "winning_trades": 89,
  "losing_trades": 67
}
```

---

## WebSocket API

### Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  console.log('Connected');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};
```

### Message Types

#### Ping/Pong (Keep-alive)

**Send:**
```json
{"type": "ping"}
```

**Receive:**
```json
{"type": "pong"}
```

#### Price Update

**Receive:**
```json
{
  "type": "update",
  "symbol": "BTC/USDT",
  "price": 45234.56,
  "signal": "BUY",
  "confidence": 0.72,
  "timestamp": "2024-12-10T12:00:00.000Z"
}
```

#### Account Update

**Receive:**
```json
{
  "type": "account",
  "cash": 9500.00,
  "equity": 10234.56,
  "pnl": 234.56
}
```

#### Trading Status

**Receive:**
```json
{
  "type": "status",
  "is_trading": true,
  "trading_mode": "paper"
}
```

#### Training Progress

**Receive:**
```json
{
  "type": "training",
  "status": "training_model",
  "progress": 75
}
```

**Status values:** `fetching_data`, `generating_features`, `training_model`, `completed`, `error`

#### Trade Notification

**Receive:**
```json
{
  "type": "trade",
  "symbol": "BTC/USDT",
  "side": "buy",
  "amount": 0.001234,
  "price": 45234.56,
  "timestamp": "2024-12-10T12:00:00.000Z"
}
```

---

## Error Responses

### Error Format

```json
{
  "detail": "Error message here"
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request |
| 404 | Not Found |
| 422 | Validation Error |
| 500 | Internal Server Error |

### Common Errors

**Model not loaded:**
```json
{
  "detail": "Model not loaded. Train first."
}
```

**Trading already running:**
```json
{
  "detail": "Trading already running"
}
```

**Invalid symbol:**
```json
{
  "detail": "Invalid symbol format"
}
```

---

## Rate Limiting

When using Nginx, API endpoints are rate limited:

| Endpoint | Limit |
|----------|-------|
| `/api/*` | 10 requests/second per IP |
| `/health` | No limit |

**Rate Limit Response:**
```
HTTP/1.1 429 Too Many Requests
```

---

## Examples

### cURL

```bash
# Get status
curl http://localhost:8000/api/status

# Get account
curl http://localhost:8000/api/account

# Get prices
curl "http://localhost:8000/api/prices/BTC-USDT?limit=100"

# Start trading
curl -X POST http://localhost:8000/api/start \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["BTC/USDT"], "mode": "paper"}'

# Stop trading
curl -X POST http://localhost:8000/api/stop

# Run backtest
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTC/USDT", "start_date": "2024-01-01", "end_date": "2024-11-01"}'
```

### Python

```python
import requests

BASE_URL = "http://localhost:8000"

# Get status
response = requests.get(f"{BASE_URL}/api/status")
print(response.json())

# Start paper trading
response = requests.post(
    f"{BASE_URL}/api/start",
    json={"symbols": ["BTC/USDT"], "mode": "paper"}
)
print(response.json())
```

### JavaScript

```javascript
// Get prices
fetch('/api/prices/BTC-USDT?limit=100')
  .then(res => res.json())
  .then(data => console.log(data));

// WebSocket
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

---

## Next Steps

- [Trading Strategies](./08-trading-strategies.md) - ML models and strategies
- [Deployment](./09-deployment.md) - Production deployment guide
