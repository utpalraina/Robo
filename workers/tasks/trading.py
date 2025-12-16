"""
Trading Tasks
Background tasks for trading operations
"""

import sys
from pathlib import Path
from datetime import datetime
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from workers.celery_app import celery_app
from utils.helpers import load_config, get_exchange
from data.fetcher import DataFetcher
from data.storage import DataStorage
from features.indicators import FeatureEngineer
from models.ml_models import create_model
from strategy.ml_strategy import MLStrategy


@celery_app.task(bind=True, max_retries=3)
def generate_signals(self):
    """Generate trading signals for all configured symbols."""
    try:
        config = load_config()
        symbols = config.get("trading", {}).get("symbols", ["BTC/USDT"])
        timeframe = config.get("trading", {}).get("timeframe", "1h")

        exchange = get_exchange(config, paper_mode=True)
        data_fetcher = DataFetcher(exchange)
        feature_engineer = FeatureEngineer(config)

        # Load model
        model_path = Path(__file__).parent.parent.parent / "models" / "trained_model.joblib"
        if not model_path.exists():
            logger.warning("Model not found, skipping signal generation")
            return {"status": "skipped", "reason": "model_not_found"}

        model = create_model(config)
        model.load(str(model_path))
        strategy = MLStrategy(model, feature_engineer, config)

        signals = {}
        for symbol in symbols:
            try:
                df = data_fetcher.fetch_ohlcv(symbol, timeframe, limit=200)
                if df.empty:
                    continue

                signal, confidence = strategy.generate_signal(df)
                signals[symbol] = {
                    "signal": signal.name,
                    "confidence": confidence,
                    "price": df["close"].iloc[-1],
                    "timestamp": datetime.now().isoformat()
                }

                logger.info(f"Signal for {symbol}: {signal.name} ({confidence:.2%})")

            except Exception as e:
                logger.error(f"Error generating signal for {symbol}: {e}")

        return {"status": "success", "signals": signals}

    except Exception as e:
        logger.error(f"Signal generation failed: {e}")
        self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def execute_pending_trades(self):
    """Execute pending trades based on signals."""
    try:
        # This would integrate with your paper/live trading logic
        logger.info("Checking for pending trades to execute")

        # In production, this would:
        # 1. Check Redis for pending signals
        # 2. Validate risk management rules
        # 3. Execute trades via exchange API
        # 4. Update positions in database

        return {"status": "success", "trades_executed": 0}

    except Exception as e:
        logger.error(f"Trade execution failed: {e}")
        self.retry(exc=e, countdown=30)


@celery_app.task
def health_check():
    """Perform system health check."""
    try:
        config = load_config()
        exchange = get_exchange(config, paper_mode=True)

        # Check exchange connectivity
        exchange.load_markets()

        # Check database
        storage = DataStorage()

        return {
            "status": "healthy",
            "exchange": "connected",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
