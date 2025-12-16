"""
Model Tasks
Background tasks for ML model training and evaluation
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
from models.ml_models import create_model, cross_validate_model


@celery_app.task(bind=True, max_retries=1)
def retrain_model(self, symbol: str = "BTC/USDT", days: int = 365):
    """Retrain the ML model with recent data."""
    try:
        logger.info(f"Starting model retraining for {symbol}")

        config = load_config()
        timeframe = config.get("trading", {}).get("timeframe", "1h")

        exchange = get_exchange(config, paper_mode=True)
        data_fetcher = DataFetcher(exchange)
        feature_engineer = FeatureEngineer(config)
        storage = DataStorage()

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Fetch training data
        logger.info("Fetching training data...")
        df = data_fetcher.fetch_historical_data(
            symbol,
            timeframe,
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")
        )

        if df.empty or len(df) < 1000:
            logger.warning("Insufficient data for training")
            return {"status": "skipped", "reason": "insufficient_data"}

        # Generate features
        logger.info("Generating features...")
        df_features = feature_engineer.generate_features(df)
        X, y = feature_engineer.prepare_ml_data(df_features)

        logger.info(f"Training samples: {len(X)}")

        # Train model
        logger.info("Training model...")
        model = create_model(config)
        model.train(X, y)

        # Evaluate
        metrics = model.evaluate(X, y)
        logger.info(f"Training metrics: {metrics}")

        # Save model
        model_path = Path(__file__).parent.parent.parent / "models" / "trained_model.joblib"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model.save(str(model_path))

        # Save backup with timestamp
        backup_path = model_path.parent / f"model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.joblib"
        model.save(str(backup_path))

        # Save metrics to database
        storage.save_model_performance(
            model_name=config.get("model", {}).get("type", "xgboost"),
            symbol=symbol,
            metrics=metrics
        )

        logger.info("Model retraining completed successfully")

        return {
            "status": "success",
            "symbol": symbol,
            "samples": len(X),
            "metrics": metrics,
            "model_path": str(model_path),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Model retraining failed: {e}")
        self.retry(exc=e, countdown=3600)  # Retry in 1 hour


@celery_app.task
def evaluate_model_performance(symbol: str = "BTC/USDT"):
    """Evaluate model performance on recent data."""
    try:
        logger.info(f"Evaluating model performance for {symbol}")

        config = load_config()
        timeframe = config.get("trading", {}).get("timeframe", "1h")

        exchange = get_exchange(config, paper_mode=True)
        data_fetcher = DataFetcher(exchange)
        feature_engineer = FeatureEngineer(config)
        storage = DataStorage()

        # Load model
        model_path = Path(__file__).parent.parent.parent / "models" / "trained_model.joblib"
        if not model_path.exists():
            return {"status": "skipped", "reason": "model_not_found"}

        model = create_model(config)
        model.load(str(model_path))

        # Get recent data (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        df = data_fetcher.fetch_historical_data(
            symbol,
            timeframe,
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")
        )

        if df.empty:
            return {"status": "skipped", "reason": "no_data"}

        # Generate features and evaluate
        df_features = feature_engineer.generate_features(df)
        X, y = feature_engineer.prepare_ml_data(df_features)

        metrics = model.evaluate(X, y)

        # Save metrics
        storage.save_model_performance(
            model_name=config.get("model", {}).get("type", "xgboost"),
            symbol=symbol,
            metrics=metrics
        )

        logger.info(f"Model performance: {metrics}")

        return {
            "status": "success",
            "symbol": symbol,
            "metrics": metrics,
            "evaluation_period": "30_days",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Model evaluation failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task
def cross_validate(symbol: str = "BTC/USDT", folds: int = 5):
    """Run cross-validation on the model."""
    try:
        logger.info(f"Running {folds}-fold cross-validation for {symbol}")

        config = load_config()
        timeframe = config.get("trading", {}).get("timeframe", "1h")

        exchange = get_exchange(config, paper_mode=True)
        data_fetcher = DataFetcher(exchange)
        feature_engineer = FeatureEngineer(config)

        # Get data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)

        df = data_fetcher.fetch_historical_data(
            symbol,
            timeframe,
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")
        )

        if df.empty:
            return {"status": "skipped", "reason": "no_data"}

        df_features = feature_engineer.generate_features(df)
        X, y = feature_engineer.prepare_ml_data(df_features)

        model = create_model(config)
        results = cross_validate_model(model, X, y, n_splits=folds)

        logger.info(f"Cross-validation results: {results}")

        return {
            "status": "success",
            "symbol": symbol,
            "folds": folds,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Cross-validation failed: {e}")
        return {"status": "error", "error": str(e)}
