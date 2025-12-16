# Services & Ports Reference

Complete reference for all services, ports, and URLs in the Robo Trader application.

---

## Quick Reference Table

| Service | Port | Protocol | URL | Description |
|---------|------|----------|-----|-------------|
| **Nginx** | 80 | HTTP | http://localhost | Reverse proxy (production) |
| **Nginx SSL** | 443 | HTTPS | https://localhost | Secure access (production) |
| **FastAPI App** | 8000 | HTTP | http://localhost:8000 | Application server |
| **WebSocket** | 8000 | WS | ws://localhost:8000/ws | Real-time updates |
| **Redis** | 6379 | TCP | redis://localhost:6379 | Cache & message broker |
| **PostgreSQL** | 5432 | TCP | postgresql://localhost:5432 | Database |
| **Prometheus** | 9090 | HTTP | http://localhost:9090 | Metrics |
| **Grafana** | 3000 | HTTP | http://localhost:3000 | Dashboards |

---

## Application URLs

### Development Mode
```
Dashboard:     http://localhost:8000
API:           http://localhost:8000/api
WebSocket:     ws://localhost:8000/ws
Health Check:  http://localhost:8000/health
API Docs:      http://localhost:8000/docs
```

### Production Mode (with Nginx)
```
Dashboard:     http://localhost (or https://your-domain.com)
API:           http://localhost/api
WebSocket:     ws://localhost/ws
Health Check:  http://localhost/health
Static Files:  http://localhost/static
```

---

## Service Details

### 1. Nginx (Reverse Proxy)

**Purpose:** Load balancing, SSL termination, static file serving, rate limiting

| Port | Protocol | Purpose |
|------|----------|---------|
| 80 | HTTP | Main web traffic |
| 443 | HTTPS | Secure web traffic |

**Features:**
- Load balancing across multiple app instances
- Rate limiting (10 requests/second per IP)
- Gzip compression
- Static file caching
- WebSocket proxy support
- Security headers

**Configuration:** `deploy/nginx/robo-trader.conf`

```nginx
# Main server block
server {
    listen 80;
    server_name localhost;

    # Proxy to application
    location / {
        proxy_pass http://127.0.0.1:8000;
    }

    # WebSocket endpoint
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

### 2. FastAPI Application (Gunicorn + Uvicorn)

**Purpose:** Main application server handling API requests and WebSocket connections

| Port | Protocol | Purpose |
|------|----------|---------|
| 8000 | HTTP/WS | Application server |

**Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web dashboard |
| `/api/status` | GET | Trading status |
| `/api/account` | GET | Account info |
| `/api/positions` | GET | Open positions |
| `/api/trades` | GET | Trade history |
| `/api/prices/{symbol}` | GET | Price data |
| `/api/signal/{symbol}` | GET | ML signal |
| `/api/start` | POST | Start trading |
| `/api/stop` | POST | Stop trading |
| `/api/train` | POST | Train model |
| `/api/backtest` | POST | Run backtest |
| `/ws` | WebSocket | Real-time updates |
| `/health` | GET | Health check |

**Configuration:** `deploy/gunicorn.conf.py`

---

### 3. Redis (Cache & Message Broker)

**Purpose:** Caching, real-time pub/sub, Celery task queue

| Port | Protocol | Purpose |
|------|----------|---------|
| 6379 | TCP | Redis server |

**Usage:**
- **Price Caching:** 30-second TTL for ticker data
- **OHLCV Caching:** 5-minute TTL for candlestick data
- **Session Storage:** User session management
- **Pub/Sub:** Real-time price updates
- **Task Queue:** Celery job broker

**Connection String:**
```
redis://localhost:6379/0
redis://:password@localhost:6379/0  # With password
```

**Test Connection:**
```bash
redis-cli ping
# Returns: PONG
```

---

### 4. PostgreSQL (Database)

**Purpose:** Persistent data storage for production

| Port | Protocol | Purpose |
|------|----------|---------|
| 5432 | TCP | PostgreSQL server |

**Databases:**
- `robotrader` - Main application database

**Tables:**
| Table | Purpose |
|-------|---------|
| `ohlcv` | Price candlestick data |
| `trades` | Trade history |
| `positions` | Position tracking |
| `signals` | ML signals |
| `model_performance` | Model metrics |
| `account_history` | Balance history |

**Connection String:**
```
postgresql://robotrader:password@localhost:5432/robotrader
```

**Configuration:** `deploy/postgres/init.sql`

---

### 5. Celery Workers (Background Tasks)

**Purpose:** Asynchronous task processing

| Queue | Purpose |
|-------|---------|
| `default` | General tasks |
| `trading` | Trading operations |
| `data` | Data fetching |
| `model` | ML training |
| `maintenance` | Cleanup tasks |

**Scheduled Tasks:**
| Task | Schedule | Description |
|------|----------|-------------|
| `fetch_latest_prices` | Every 1 min | Update price cache |
| `update_indicators` | Every 5 min | Calculate indicators |
| `generate_signals` | Every 1 min | ML signal generation |
| `execute_pending_trades` | Every 30 sec | Trade execution |
| `evaluate_model` | Daily | Model performance |
| `retrain_model` | Weekly | Model retraining |
| `cleanup_old_data` | Daily | Data cleanup |

**Commands:**
```bash
# Start worker
celery -A workers.celery_app worker --loglevel=info

# Start scheduler
celery -A workers.celery_app beat --loglevel=info
```

---

### 6. Prometheus (Monitoring)

**Purpose:** Metrics collection and alerting

| Port | Protocol | Purpose |
|------|----------|---------|
| 9090 | HTTP | Prometheus UI |

**Metrics Available:**
- Request latency
- Request count
- Error rates
- System resources

**URL:** http://localhost:9090

---

### 7. Grafana (Dashboards)

**Purpose:** Visualization and dashboards

| Port | Protocol | Purpose |
|------|----------|---------|
| 3000 | HTTP | Grafana UI |

**Default Credentials:**
- Username: `admin`
- Password: Set via `GRAFANA_PASSWORD` env var

**URL:** http://localhost:3000

---

## Network Architecture

### Docker Network
```
Network: robo-network (172.28.0.0/16)

┌─────────────────────────────────────────────────────┐
│                  robo-network                        │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  nginx   │  │   app    │  │    postgres      │  │
│  │ :80/:443 │  │  :8000   │  │     :5432        │  │
│  └────┬─────┘  └────┬─────┘  └──────────────────┘  │
│       │             │                               │
│       └─────────────┼───────────────────────────┐  │
│                     │                           │  │
│              ┌──────┴──────┐              ┌─────┴─┐│
│              │   redis     │              │worker ││
│              │   :6379     │              │       ││
│              └─────────────┘              └───────┘│
└─────────────────────────────────────────────────────┘
```

---

## Port Availability Check

Check if ports are available before starting:

```bash
# Check all required ports
for port in 80 443 8000 6379 5432 9090 3000; do
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null; then
        echo "Port $port is IN USE"
    else
        echo "Port $port is available"
    fi
done
```

---

## Firewall Configuration

### Allow Required Ports

**Ubuntu/Debian (ufw):**
```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp
```

**CentOS/RHEL (firewalld):**
```bash
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --reload
```

---

## Health Check Endpoints

| Service | Endpoint | Expected Response |
|---------|----------|-------------------|
| App | `http://localhost:8000/health` | `{"status": "healthy"}` |
| Nginx | `http://localhost/health` | `{"status": "healthy"}` |
| Redis | `redis-cli ping` | `PONG` |
| PostgreSQL | `pg_isready` | `accepting connections` |

---

## Next Steps

- [Docker Guide](./05-docker-guide.md) - Container deployment
- [CLI Reference](./06-cli-reference.md) - Command line interface
