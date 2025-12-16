# Troubleshooting Guide

Solutions for common issues in Robo Trader.

---

## Quick Diagnostics

```bash
# Check all services
docker-compose ps

# View recent logs
docker-compose logs --tail=50

# Check system resources
docker stats

# Test endpoints
curl http://localhost:8000/health
```

---

## Installation Issues

### Python Version Error

**Error:**
```
Python 3.10+ required
```

**Solution:**
```bash
# Check Python version
python --version

# Install Python 3.11
# macOS
brew install python@3.11

# Ubuntu
sudo apt install python3.11 python3.11-venv
```

### Dependency Installation Failed

**Error:**
```
ERROR: Could not build wheels for xxx
```

**Solution:**
```bash
# Install build tools
# macOS
xcode-select --install

# Ubuntu
sudo apt install build-essential python3-dev

# Reinstall
pip install -r requirements.txt
```

### Module Not Found

**Error:**
```
ModuleNotFoundError: No module named 'xxx'
```

**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

---

## Connection Issues

### Exchange Connection Failed

**Error:**
```
ccxt.NetworkError: Exchange not reachable
```

**Solutions:**

1. **Check API keys:**
```bash
# Verify environment variables
echo $BINANCE_API_KEY
```

2. **Test connection:**
```python
import ccxt
exchange = ccxt.binance({'apiKey': 'xxx', 'secret': 'xxx'})
exchange.load_markets()
```

3. **Check for IP restrictions** in exchange API settings

4. **Verify testnet setting:**
```yaml
exchange:
  testnet: true  # Use testnet for testing
```

### Redis Connection Failed

**Error:**
```
redis.exceptions.ConnectionError: Connection refused
```

**Solutions:**

1. **Check Redis is running:**
```bash
# Docker
docker-compose ps redis

# Local
redis-cli ping
```

2. **Verify connection settings:**
```bash
REDIS_HOST=localhost  # or 'redis' in Docker
REDIS_PORT=6379
```

3. **Restart Redis:**
```bash
docker-compose restart redis
```

### Database Connection Failed

**Error:**
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solutions:**

1. **Check PostgreSQL is running:**
```bash
docker-compose ps postgres
docker-compose exec postgres pg_isready
```

2. **Verify connection string:**
```bash
DATABASE_URL=postgresql://robotrader:password@postgres:5432/robotrader
```

3. **Check credentials:**
```bash
docker-compose exec postgres psql -U robotrader -d robotrader
```

---

## Application Issues

### Model Not Found

**Error:**
```
FileNotFoundError: models/trained_model.joblib not found
```

**Solution:**
```bash
# Train a model first
python main.py train --symbol BTC/USDT
```

### No Data Fetched

**Error:**
```
No data fetched. Check symbol and date range.
```

**Solutions:**

1. **Verify symbol format:**
```bash
# Correct: BTC/USDT
# Wrong: BTCUSDT, BTC-USDT
```

2. **Check date range:**
```bash
# Ensure dates are not in the future
python main.py train --start-date 2024-01-01 --end-date 2024-11-01
```

3. **Test exchange connection:**
```bash
python -c "
from utils.helpers import load_config, get_exchange
config = load_config()
exchange = get_exchange(config)
print(exchange.fetch_ticker('BTC/USDT'))
"
```

### WebSocket Disconnection

**Error:**
```
WebSocket disconnected
```

**Solutions:**

1. **Check Nginx WebSocket config:**
```nginx
location /ws {
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 86400s;
}
```

2. **Check server logs:**
```bash
docker-compose logs -f app
```

3. **Refresh the browser** and check console for errors

---

## Docker Issues

### Container Won't Start

**Error:**
```
Container exited with code 1
```

**Solutions:**

1. **Check logs:**
```bash
docker-compose logs app
```

2. **Verify .env file exists:**
```bash
ls -la .env
```

3. **Check port conflicts:**
```bash
lsof -i :8000
lsof -i :80
```

### Out of Disk Space

**Error:**
```
No space left on device
```

**Solution:**
```bash
# Clean up Docker
docker system prune -a
docker volume prune

# Check disk usage
df -h
```

### Permission Denied

**Error:**
```
PermissionError: [Errno 13] Permission denied
```

**Solution:**
```bash
# Fix permissions
sudo chown -R $USER:$USER data logs models
chmod -R 755 data logs models
```

### Build Failed

**Error:**
```
ERROR: failed to solve: process "/bin/sh -c pip install..." did not complete successfully
```

**Solutions:**

1. **Clean build:**
```bash
docker-compose build --no-cache
```

2. **Check Dockerfile syntax**

3. **Ensure requirements.txt is valid:**
```bash
pip install -r requirements.txt --dry-run
```

---

## Trading Issues

### No Signals Generated

**Possible Causes:**
1. Model not loaded
2. Insufficient data
3. Signal threshold not met

**Solutions:**

1. **Check model:**
```bash
ls -la models/trained_model.joblib
```

2. **Verify signal thresholds in strategy:**
```python
buy_threshold = 0.6   # Lower for more signals
sell_threshold = 0.4  # Raise for more signals
```

3. **Check logs for signal values:**
```bash
docker-compose logs -f app | grep "Signal"
```

### Trades Not Executing

**Possible Causes:**
1. Risk limits reached
2. Insufficient balance
3. Exchange API error

**Solutions:**

1. **Check risk limits:**
```yaml
risk:
  max_open_positions: 3
  daily_loss_limit: 0.05
```

2. **Check account balance:**
```bash
curl http://localhost:8000/api/account
```

3. **Check exchange logs:**
```bash
docker-compose logs -f app | grep -i "error\|failed"
```

### Wrong Prices

**Possible Causes:**
1. Cached data
2. Exchange data delay
3. Time zone issues

**Solutions:**

1. **Clear Redis cache:**
```bash
docker-compose exec redis redis-cli FLUSHALL
```

2. **Check exchange status**

3. **Verify time synchronization:**
```bash
date
ntpdate -q pool.ntp.org
```

---

## Performance Issues

### Slow Response Times

**Solutions:**

1. **Check resource usage:**
```bash
docker stats
```

2. **Increase workers:**
```python
# deploy/gunicorn.conf.py
workers = 8  # Increase from default
```

3. **Enable caching:**
```python
# Ensure Redis is running
REDIS_HOST=redis
```

4. **Optimize database:**
```bash
docker-compose exec postgres vacuumdb -U robotrader -d robotrader -z
```

### High Memory Usage

**Solutions:**

1. **Limit container memory:**
```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      memory: 2G
```

2. **Restart workers periodically:**
```python
# deploy/gunicorn.conf.py
max_requests = 1000
```

3. **Check for memory leaks in logs**

### High CPU Usage

**Solutions:**

1. **Reduce signal frequency:**
```yaml
# Increase interval between checks
interval: 120  # seconds
```

2. **Optimize model:**
```yaml
model:
  type: "lightgbm"  # Faster than xgboost
```

3. **Scale horizontally:**
```bash
docker-compose up -d --scale worker=2
```

---

## Log Analysis

### Finding Errors

```bash
# All errors
docker-compose logs | grep -i error

# Specific service errors
docker-compose logs app | grep -i "error\|exception\|failed"

# Last hour of logs
docker-compose logs --since 1h app
```

### Common Log Messages

| Message | Meaning | Action |
|---------|---------|--------|
| `Connected to Redis` | Normal | None |
| `Model loaded` | Normal | None |
| `Rate limit exceeded` | Too many API calls | Reduce frequency |
| `Insufficient funds` | Not enough balance | Deposit funds or reduce position size |
| `Connection refused` | Service not running | Restart service |

---

## Getting Help

### Collect Diagnostic Info

```bash
# Create diagnostic report
cat > /tmp/diagnostic.txt << EOF
=== System Info ===
$(uname -a)
$(docker --version)
$(docker-compose --version)

=== Service Status ===
$(docker-compose ps)

=== Recent Logs ===
$(docker-compose logs --tail=50)

=== Disk Usage ===
$(df -h)
$(docker system df)
EOF

cat /tmp/diagnostic.txt
```

### Useful Commands Summary

```bash
# Restart everything
docker-compose down && docker-compose up -d

# View real-time logs
docker-compose logs -f

# Enter container shell
docker-compose exec app bash

# Check health
curl http://localhost:8000/health

# Test Redis
docker-compose exec redis redis-cli ping

# Test PostgreSQL
docker-compose exec postgres pg_isready
```

---

## Contact Support

If issues persist:
1. Collect diagnostic info (see above)
2. Check existing issues on GitHub
3. Open a new issue with:
   - Error message
   - Steps to reproduce
   - Diagnostic info
   - Configuration (without secrets)
