"""Utility functions for the trading bot."""

import os
import yaml
import ccxt
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv


def load_config(config_path: str = "config/config.yaml") -> dict:
    """Load configuration from YAML file."""
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config


def setup_logging(config: dict) -> None:
    """Setup logging configuration."""
    log_config = config.get("logging", {})
    log_level = log_config.get("level", "INFO")
    log_file = log_config.get("file", "logs/trading.log")

    # Create logs directory
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # Configure loguru
    logger.remove()
    logger.add(
        log_file,
        rotation="10 MB",
        retention="7 days",
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    )
    logger.add(
        lambda msg: print(msg, end=""),
        level=log_level,
        format="{time:HH:mm:ss} | {level} | {message}\n"
    )


def get_exchange(config: dict, paper_mode: bool = False) -> ccxt.Exchange:
    """
    Initialize and return a ccxt exchange instance.

    Args:
        config: Configuration dictionary
        paper_mode: If True, use sandbox/testnet mode

    Returns:
        Configured ccxt exchange instance
    """
    load_dotenv()

    exchange_name = config["exchange"]["name"]
    exchange_class = getattr(ccxt, exchange_name)

    # Get API credentials from environment
    api_key = os.getenv(f"{exchange_name.upper()}_API_KEY", "")
    api_secret = os.getenv(f"{exchange_name.upper()}_API_SECRET", "")

    exchange = exchange_class({
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": config["exchange"].get("rate_limit", True),
        "options": {
            "defaultType": "spot"
        }
    })

    # Enable sandbox mode if configured or paper trading
    # Note: Kraken doesn't have a sandbox/testnet - paper trading uses real data
    # but simulates trades locally (no actual orders placed)
    if config["exchange"].get("testnet", False) or paper_mode:
        if hasattr(exchange, "set_sandbox_mode"):
            try:
                exchange.set_sandbox_mode(True)
                logger.info(f"Sandbox mode enabled for {exchange_name}")
            except ccxt.NotSupported:
                # Exchange doesn't support sandbox (e.g., Kraken)
                # Paper trading will use real market data but simulate trades locally
                logger.info(f"{exchange_name} doesn't have sandbox mode - using real data for paper trading")

    return exchange


def format_price(price: float, precision: int = 8) -> str:
    """Format price with appropriate precision."""
    return f"{price:.{precision}f}"


def calculate_position_size(
    capital: float,
    price: float,
    risk_pct: float,
    stop_loss_pct: float
) -> float:
    """
    Calculate position size based on risk management.

    Args:
        capital: Available capital
        price: Current asset price
        risk_pct: Maximum risk percentage per trade
        stop_loss_pct: Stop loss percentage

    Returns:
        Position size in base currency
    """
    risk_amount = capital * risk_pct
    position_value = risk_amount / stop_loss_pct
    position_size = position_value / price
    return position_size
