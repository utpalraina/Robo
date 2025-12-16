"""
Production Configuration Settings
Professional-grade settings for deployment
"""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Environment
ENV = os.getenv("ENV", "production")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
WORKERS = int(os.getenv("WORKERS", 4))

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR}/data/production.db"
)

# Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_URL = os.getenv(
    "REDIS_URL",
    f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
)

# Celery
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Exchange API (load from environment for security)
EXCHANGE_CONFIG = {
    "binance": {
        "api_key": os.getenv("BINANCE_API_KEY", ""),
        "api_secret": os.getenv("BINANCE_API_SECRET", ""),
        "testnet": os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    },
    "coinbase": {
        "api_key": os.getenv("COINBASE_API_KEY", ""),
        "api_secret": os.getenv("COINBASE_API_SECRET", "")
    },
    "kraken": {
        "api_key": os.getenv("KRAKEN_API_KEY", ""),
        "api_secret": os.getenv("KRAKEN_API_SECRET", "")
    }
}

# Trading Configuration
TRADING_CONFIG = {
    "symbols": os.getenv("TRADING_SYMBOLS", "BTC/USDT,ETH/USDT").split(","),
    "timeframe": os.getenv("TRADING_TIMEFRAME", "1h"),
    "max_position_size": float(os.getenv("MAX_POSITION_SIZE", 0.1)),
    "stop_loss_pct": float(os.getenv("STOP_LOSS_PCT", 0.02)),
    "take_profit_pct": float(os.getenv("TAKE_PROFIT_PCT", 0.04)),
    "max_open_positions": int(os.getenv("MAX_OPEN_POSITIONS", 3)),
    "daily_loss_limit": float(os.getenv("DAILY_LOSS_LIMIT", 0.05))
}

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv(
    "LOG_FORMAT",
    "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)
LOG_FILE = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "app.log"))

# Model
MODEL_PATH = os.getenv("MODEL_PATH", str(BASE_DIR / "models" / "trained_model.joblib"))
MODEL_RETRAIN_INTERVAL_HOURS = int(os.getenv("MODEL_RETRAIN_INTERVAL", 168))  # 1 week

# Rate Limiting
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", 100))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", 60))

# Cache TTL (seconds)
CACHE_TTL = {
    "price": int(os.getenv("CACHE_TTL_PRICE", 30)),
    "ohlcv": int(os.getenv("CACHE_TTL_OHLCV", 300)),
    "indicators": int(os.getenv("CACHE_TTL_INDICATORS", 60)),
    "signal": int(os.getenv("CACHE_TTL_SIGNAL", 30))
}

# Monitoring
PROMETHEUS_ENABLED = os.getenv("PROMETHEUS_ENABLED", "false").lower() == "true"
PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", 9090))

# Health Check
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", 30))
