# Installation Guide

## Prerequisites

### System Requirements
- **OS**: Linux, macOS, or Windows (WSL2 recommended)
- **Python**: 3.10 or higher
- **Memory**: 4GB RAM minimum (8GB recommended)
- **Storage**: 10GB free space

### Required Software
- Python 3.10+
- pip (Python package manager)
- Git

### Optional Software (for production)
- Docker & Docker Compose
- Redis
- PostgreSQL
- Nginx

---

## Installation Methods

### Method 1: Docker Installation (Recommended)

This is the easiest way to get started with all services pre-configured.

```bash
# 1. Clone the repository
cd /path/to/your/projects
git clone <repository-url> robo-trader
cd robo-trader

# 2. Create environment file
cp .env.production .env

# 3. Edit .env with your settings
nano .env  # or use any text editor

# 4. Start all services
docker-compose up -d

# 5. Check status
docker-compose ps

# 6. View logs
docker-compose logs -f
```

**Access the application at: http://localhost**

### Method 2: Manual Installation

For development or custom deployments.

```bash
# 1. Clone the repository
cd /path/to/your/projects
git clone <repository-url> robo-trader
cd robo-trader

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
.\venv\Scripts\activate

# 4. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 5. Create environment file
cp .env.production .env

# 6. Edit configuration
nano .env
nano config/config.yaml

# 7. Create necessary directories
mkdir -p logs data models

# 8. Run the application
python main.py web
```

**Access the application at: http://localhost:8000**

---

## Environment Configuration

### Required Environment Variables

Create a `.env` file in the project root:

```bash
# Environment
ENV=development  # or 'production'
DEBUG=true

# Server
HOST=0.0.0.0
PORT=8000

# Exchange API Keys (at least one required for live/paper trading)
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
BINANCE_TESTNET=true  # Use testnet for paper trading

# Optional: Additional exchanges
COINBASE_API_KEY=
COINBASE_API_SECRET=
KRAKEN_API_KEY=
KRAKEN_API_SECRET=
```

### Getting Exchange API Keys

#### Binance
1. Go to https://www.binance.com
2. Log in to your account
3. Navigate to API Management
4. Create a new API key
5. Enable "Spot Trading" permission
6. For testnet: https://testnet.binance.vision

#### Coinbase
1. Go to https://www.coinbase.com/settings/api
2. Create new API key
3. Select required permissions

#### Kraken
1. Go to https://www.kraken.com/u/security/api
2. Create new API key
3. Configure permissions

---

## Verifying Installation

### Check Python Dependencies
```bash
pip list | grep -E "ccxt|fastapi|pandas|scikit-learn"
```

### Test CLI
```bash
python main.py --help
```

Expected output:
```
Usage: main.py [OPTIONS] COMMAND [ARGS]...

  ML-based Cryptocurrency Trading Bot

Options:
  --help  Show this message and exit.

Commands:
  backtest    Run backtest on historical data.
  fetch-data  Fetch and store historical data.
  live        Start live trading with real money.
  paper       Start paper trading simulation.
  status      Show current trading status and recent trades.
  train       Train the ML model on historical data.
  validate    Cross-validate the model.
  web         Launch the web dashboard.
```

### Test Web Server
```bash
python main.py web --port 8000
```

Then open http://localhost:8000 in your browser.

---

## Installing Optional Components

### Redis (for production caching)

**macOS:**
```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis
```

**Verify:**
```bash
redis-cli ping
# Should return: PONG
```

### PostgreSQL (for production database)

**macOS:**
```bash
brew install postgresql
brew services start postgresql
createdb robotrader
```

**Ubuntu/Debian:**
```bash
sudo apt install postgresql postgresql-contrib
sudo -u postgres createuser --interactive
sudo -u postgres createdb robotrader
```

---

## Troubleshooting Installation

### Common Issues

#### 1. Python Version Error
```
Error: Python 3.10+ required
```
**Solution:** Install Python 3.10 or higher
```bash
# macOS
brew install python@3.11

# Ubuntu
sudo apt install python3.11
```

#### 2. Missing Dependencies
```
ModuleNotFoundError: No module named 'xxx'
```
**Solution:** Reinstall dependencies
```bash
pip install -r requirements.txt --force-reinstall
```

#### 3. Port Already in Use
```
Error: Address already in use
```
**Solution:** Use a different port or kill the existing process
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use different port
python main.py web --port 8080
```

#### 4. Permission Denied
```
PermissionError: [Errno 13] Permission denied
```
**Solution:** Fix file permissions
```bash
chmod +x deploy/*.sh
chmod -R 755 logs data models
```

---

## Next Steps

After installation:

1. **Configure Trading**: Edit `config/config.yaml`
2. **Train Model**: `python main.py train`
3. **Run Backtest**: `python main.py backtest`
4. **Start Paper Trading**: `python main.py paper`
5. **Launch Dashboard**: `python main.py web`

See [Configuration Guide](./03-configuration.md) for detailed setup instructions.
