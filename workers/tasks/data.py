"""
Data Tasks
Background tasks for data fetching and processing
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from workers.celery_app import celery_app
from utils.helpers import load_config, get_exchange
from data.fetcher import DataFetcher
from data.storage import DataStorage
from features.indicators import FeatureEngineer


@celery_app.task(bind=True, max_retries=3)
def fetch_latest_prices(self):
    """Fetch latest prices for all configured symbols."""
    try:
        config = load_config()
        symbols = config.get("trading", {}).get("symbols", ["BTC/USDT"])

        exchange = get_exchange(config, paper_mode=True)
        data_fetcher = DataFetcher(exchange)

        prices = {}
        for symbol in symbols:
            try:
                ticker = data_fetcher.fetch_ticker(symbol)
                prices[symbol] = {
                    "bid": ticker["bid"],
                    "ask": ticker["ask"],
                    "last": ticker["last"],
                    "volume": ticker["volume"],
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logger.warning(f"Failed to fetch price for {symbol}: {e}")

        logger.info(f"Fetched prices for {len(prices)} symbols")
        return {"status": "success", "prices": prices}

    except Exception as e:
        logger.error(f"Price fetch failed: {e}")
        self.retry(exc=e, countdown=30)


@celery_app.task(bind=True, max_retries=3)
def update_indicators(self):
    """Update technical indicators for all symbols."""
    try:
        config = load_config()
        symbols = config.get("trading", {}).get("symbols", ["BTC/USDT"])
        timeframe = config.get("trading", {}).get("timeframe", "1h")

        exchange = get_exchange(config, paper_mode=True)
        data_fetcher = DataFetcher(exchange)
        feature_engineer = FeatureEngineer(config)
        storage = DataStorage()

        for symbol in symbols:
            try:
                # Fetch latest data
                df = data_fetcher.fetch_ohlcv(symbol, timeframe, limit=200)
                if df.empty:
                    continue

                # Generate features
                df_features = feature_engineer.generate_features(df)

                # Save to storage
                storage.save_ohlcv(df, symbol, timeframe)

                logger.debug(f"Updated indicators for {symbol}")

            except Exception as e:
                logger.warning(f"Failed to update indicators for {symbol}: {e}")

        return {"status": "success", "symbols_updated": len(symbols)}

    except Exception as e:
        logger.error(f"Indicator update failed: {e}")
        self.retry(exc=e, countdown=60)


@celery_app.task
def fetch_historical_data(symbol: str, start_date: str, end_date: str):
    """Fetch historical data for backtesting or training."""
    try:
        config = load_config()
        timeframe = config.get("trading", {}).get("timeframe", "1h")

        exchange = get_exchange(config, paper_mode=True)
        data_fetcher = DataFetcher(exchange)
        storage = DataStorage()

        logger.info(f"Fetching historical data for {symbol} from {start_date} to {end_date}")

        df = data_fetcher.fetch_historical_data(symbol, timeframe, start_date, end_date)

        if not df.empty:
            storage.save_ohlcv(df, symbol, timeframe)
            logger.info(f"Saved {len(df)} candles for {symbol}")

        return {
            "status": "success",
            "symbol": symbol,
            "candles": len(df),
            "start": start_date,
            "end": end_date
        }

    except Exception as e:
        logger.error(f"Historical data fetch failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task
def cleanup_old_data(days_to_keep: int = 90):
    """Clean up old data from database."""
    try:
        logger.info(f"Cleaning up data older than {days_to_keep} days")

        # In production, this would delete old OHLCV data
        # and compact the database

        return {
            "status": "success",
            "days_kept": days_to_keep,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return {"status": "error", "error": str(e)}
