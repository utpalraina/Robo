"""
Celery Application Configuration
Professional background task processing for trading operations
"""

import os
import sys
from pathlib import Path
from celery import Celery
from celery.schedules import crontab

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# Create Celery app
celery_app = Celery(
    "robo_trader",
    broker=os.getenv("CELERY_BROKER_URL", REDIS_URL),
    backend=os.getenv("CELERY_RESULT_BACKEND", REDIS_URL),
    include=[
        "workers.tasks.trading",
        "workers.tasks.data",
        "workers.tasks.model"
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3300,  # 55 min soft limit

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,

    # Result backend
    result_expires=86400,  # 24 hours

    # Retry settings
    task_default_retry_delay=60,
    task_max_retries=3,

    # Logging
    worker_hijack_root_logger=False,

    # Beat schedule for periodic tasks
    beat_schedule={
        # Fetch latest market data every minute
        "fetch-market-data": {
            "task": "workers.tasks.data.fetch_latest_prices",
            "schedule": 60.0,  # Every minute
            "options": {"queue": "data"}
        },

        # Update technical indicators every 5 minutes
        "update-indicators": {
            "task": "workers.tasks.data.update_indicators",
            "schedule": 300.0,  # Every 5 minutes
            "options": {"queue": "data"}
        },

        # Generate trading signals every minute
        "generate-signals": {
            "task": "workers.tasks.trading.generate_signals",
            "schedule": 60.0,
            "options": {"queue": "trading"}
        },

        # Execute trades based on signals
        "execute-trades": {
            "task": "workers.tasks.trading.execute_pending_trades",
            "schedule": 30.0,  # Every 30 seconds
            "options": {"queue": "trading"}
        },

        # Daily model evaluation
        "evaluate-model": {
            "task": "workers.tasks.model.evaluate_model_performance",
            "schedule": crontab(hour=0, minute=0),  # Daily at midnight
            "options": {"queue": "model"}
        },

        # Weekly model retraining
        "retrain-model": {
            "task": "workers.tasks.model.retrain_model",
            "schedule": crontab(hour=2, minute=0, day_of_week=0),  # Sunday 2 AM
            "options": {"queue": "model"}
        },

        # Cleanup old data daily
        "cleanup-old-data": {
            "task": "workers.tasks.data.cleanup_old_data",
            "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
            "options": {"queue": "maintenance"}
        },

        # Health check every 5 minutes
        "health-check": {
            "task": "workers.tasks.trading.health_check",
            "schedule": 300.0,
            "options": {"queue": "default"}
        }
    },

    # Task routes
    task_routes={
        "workers.tasks.trading.*": {"queue": "trading"},
        "workers.tasks.data.*": {"queue": "data"},
        "workers.tasks.model.*": {"queue": "model"},
    },

    # Queue configuration
    task_queues={
        "default": {
            "exchange": "default",
            "routing_key": "default"
        },
        "trading": {
            "exchange": "trading",
            "routing_key": "trading"
        },
        "data": {
            "exchange": "data",
            "routing_key": "data"
        },
        "model": {
            "exchange": "model",
            "routing_key": "model"
        },
        "maintenance": {
            "exchange": "maintenance",
            "routing_key": "maintenance"
        }
    }
)


if __name__ == "__main__":
    celery_app.start()
