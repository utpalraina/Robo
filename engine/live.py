"""Live trading engine for real execution."""

import ccxt
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import time
from loguru import logger

from strategy.ml_strategy import MLStrategy, Signal
from data.fetcher import DataFetcher
from data.storage import DataStorage


@dataclass
class LivePosition:
    """Represents a live trading position."""
    symbol: str
    side: str
    size: float
    entry_price: float
    entry_time: datetime
    order_id: str
    stop_loss_order_id: Optional[str] = None
    take_profit_order_id: Optional[str] = None


class LiveTrader:
    """Live trading engine for real order execution."""

    def __init__(
        self,
        strategy: MLStrategy,
        exchange: ccxt.Exchange,
        data_fetcher: DataFetcher,
        storage: DataStorage,
        config: dict
    ):
        """
        Initialize LiveTrader.

        Args:
            strategy: Trading strategy
            exchange: CCXT exchange instance
            data_fetcher: Data fetcher instance
            storage: Data storage instance
            config: Configuration dictionary
        """
        self.strategy = strategy
        self.exchange = exchange
        self.data_fetcher = data_fetcher
        self.storage = storage
        self.config = config

        self.risk_config = config.get("risk", {})
        self.positions: Dict[str, LivePosition] = {}
        self.running = False
        self.daily_pnl = 0.0

        # Validate exchange connection
        self._validate_exchange()

        # Load persisted positions from database
        self._load_persisted_positions()

    def _validate_exchange(self):
        """Validate exchange connection and permissions."""
        try:
            balance = self.exchange.fetch_balance()
            logger.info(f"Connected to {self.exchange.id}")
            # Use USD for Kraken, fallback to USDT for other exchanges
            quote_balance = balance.get('USD', {}) or balance.get('USDT', {})
            quote_currency = 'USD' if 'USD' in balance else 'USDT'
            logger.info(f"Available balance: {quote_balance.get('free', 0):.2f} {quote_currency}")
        except Exception as e:
            logger.error(f"Failed to connect to exchange: {e}")
            raise

    def _load_persisted_positions(self):
        """Load positions from database that were open before restart."""
        try:
            persisted = self.storage.get_open_positions(is_paper=False)
            for pos_data in persisted:
                position = LivePosition(
                    symbol=pos_data['symbol'],
                    side=pos_data['side'],
                    size=pos_data['size'],
                    entry_price=pos_data['entry_price'],
                    entry_time=pos_data['entry_time'],
                    order_id=pos_data.get('order_id', ''),
                    stop_loss_order_id=pos_data.get('stop_loss_order_id')
                )
                self.positions[pos_data['symbol']] = position
                # Update strategy state
                self.strategy.update_position(1, pos_data['entry_price'])
                logger.info(f"Restored position: {pos_data['symbol']} - {pos_data['size']} @ ${pos_data['entry_price']:.2f}")

            if persisted:
                logger.info(f"Loaded {len(persisted)} persisted positions from database")
        except Exception as e:
            logger.warning(f"Could not load persisted positions: {e}")

    def start(self, symbols: List[str], interval_seconds: int = 60):
        """
        Start live trading loop.

        Args:
            symbols: List of trading pairs
            interval_seconds: Time between iterations
        """
        self.running = True
        logger.warning("=" * 60)
        logger.warning("LIVE TRADING MODE - REAL MONEY AT RISK")
        logger.warning("=" * 60)
        logger.info(f"Starting live trading for {symbols}")

        while self.running:
            try:
                # Sync positions with exchange
                self._sync_positions()

                for symbol in symbols:
                    self._process_symbol(symbol)

                # Log status
                self._log_status()

                time.sleep(interval_seconds)

            except KeyboardInterrupt:
                logger.info("Live trading stopped by user")
                self.stop()
            except ccxt.NetworkError as e:
                logger.error(f"Network error: {e}")
                time.sleep(30)
            except ccxt.ExchangeError as e:
                logger.error(f"Exchange error: {e}")
                time.sleep(30)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(interval_seconds)

    def stop(self):
        """Stop live trading."""
        self.running = False
        logger.info("Live trading stopped")

    def _sync_positions(self):
        """Sync local positions with exchange."""
        try:
            exchange_positions = self.exchange.fetch_positions() if hasattr(self.exchange, 'fetch_positions') else []

            # Also check open orders
            open_orders = self.exchange.fetch_open_orders()

            logger.debug(f"Synced {len(exchange_positions)} positions, {len(open_orders)} open orders")
        except Exception as e:
            logger.warning(f"Could not sync positions: {e}")

    def _process_symbol(self, symbol: str):
        """Process trading logic for a symbol."""
        # Fetch latest data
        timeframe = self.config.get("trading", {}).get("timeframe", "1h")
        df = self.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=200)

        if df.empty:
            return

        current_price = df["close"].iloc[-1]

        # Get account balance (USD for Kraken, USDT for others)
        balance = self.exchange.fetch_balance()
        quote_balance = balance.get("USD", {}) or balance.get("USDT", {})
        available_capital = quote_balance.get("free", 0)

        # Generate trading signal
        signal_result = self.strategy.get_signal_with_risk_check(
            df=df,
            current_price=current_price,
            open_positions=len(self.positions),
            daily_pnl=self.daily_pnl,
            capital=available_capital
        )

        action = signal_result.get("action")

        if action == "buy" and symbol not in self.positions:
            self._open_position(symbol, "buy", signal_result, current_price)
        elif action == "sell" and symbol not in self.positions:
            # Note: For spot trading (Kraken), we only support long positions.
            # A "sell" signal when flat means we should wait for a buy opportunity.
            # Short selling would require margin trading which is not implemented.
            logger.debug(f"Sell signal received for {symbol} but no position open (long-only mode)")
        elif action == "close" and symbol in self.positions:
            self._close_position(symbol, signal_result.get("reason", "signal"))

    def _open_position(
        self,
        symbol: str,
        side: str,
        signal_result: Dict,
        current_price: float
    ):
        """Open a live position."""
        size = signal_result.get("size", 0)

        # Minimum order size check
        market = self.exchange.market(symbol)
        min_amount = market.get("limits", {}).get("amount", {}).get("min", 0)

        if size < min_amount:
            logger.warning(f"Order size {size} below minimum {min_amount} for {symbol}")
            return

        try:
            # Place market order
            order = self.exchange.create_market_buy_order(
                symbol=symbol,
                amount=size
            )

            fill_price = order.get("average", current_price)

            position = LivePosition(
                symbol=symbol,
                side="long",
                size=order.get("filled", size),
                entry_price=fill_price,
                entry_time=datetime.now(),
                order_id=order["id"]
            )

            self.positions[symbol] = position
            self.strategy.update_position(1, fill_price)

            logger.info(
                f"LIVE BUY: {position.size:.6f} {symbol} @ ${fill_price:.2f} | "
                f"Order ID: {order['id']}"
            )

            # Save trade to storage
            self.storage.save_trade(
                symbol=symbol,
                side="buy",
                price=fill_price,
                amount=position.size,
                cost=position.size * fill_price,
                order_id=order["id"],
                is_paper=False
            )

            # Persist position for recovery after restart
            self.storage.save_position(
                symbol=symbol,
                side="long",
                size=position.size,
                entry_price=fill_price,
                entry_time=position.entry_time,
                stop_loss=signal_result.get("stop_loss"),
                take_profit=signal_result.get("take_profit"),
                order_id=order["id"],
                is_paper=False
            )

            # Place stop loss order (if exchange supports)
            self._place_stop_loss(symbol, signal_result.get("stop_loss"))

        except ccxt.InsufficientFunds as e:
            logger.error(f"Insufficient funds to buy {symbol}: {e}")
        except Exception as e:
            logger.error(f"Failed to open position in {symbol}: {e}")

    def _close_position(self, symbol: str, reason: str):
        """Close a live position."""
        if symbol not in self.positions:
            return

        position = self.positions[symbol]

        try:
            # Cancel any stop loss orders
            if position.stop_loss_order_id:
                try:
                    self.exchange.cancel_order(position.stop_loss_order_id, symbol)
                except Exception as e:
                    logger.warning(f"Could not cancel stop loss order: {e}")

            # Place market sell order
            order = self.exchange.create_market_sell_order(
                symbol=symbol,
                amount=position.size
            )

            fill_price = order.get("average", 0)
            pnl = (fill_price - position.entry_price) * position.size

            self.daily_pnl += pnl
            del self.positions[symbol]
            self.strategy.update_position(0)

            logger.info(
                f"LIVE SELL: {position.size:.6f} {symbol} @ ${fill_price:.2f} | "
                f"PnL: ${pnl:.2f} | Reason: {reason} | Order ID: {order['id']}"
            )

            # Save trade to storage
            self.storage.save_trade(
                symbol=symbol,
                side="sell",
                price=fill_price,
                amount=position.size,
                cost=position.size * fill_price,
                order_id=order["id"],
                is_paper=False
            )

            # Remove position from persistence
            self.storage.remove_position(symbol)

        except Exception as e:
            logger.error(f"Failed to close position in {symbol}: {e}")

    def _place_stop_loss(self, symbol: str, stop_price: float):
        """Place a stop loss order."""
        if symbol not in self.positions or not stop_price:
            return

        position = self.positions[symbol]

        try:
            # Try to place stop loss (exchange dependent)
            if self.exchange.has.get("createStopLossOrder"):
                order = self.exchange.create_order(
                    symbol=symbol,
                    type="stop_loss",
                    side="sell",
                    amount=position.size,
                    price=stop_price,
                    params={"stopPrice": stop_price}
                )
                position.stop_loss_order_id = order["id"]
                logger.info(f"Stop loss placed for {symbol} at ${stop_price:.2f}")
        except Exception as e:
            logger.warning(f"Could not place stop loss for {symbol}: {e}")

    def _log_status(self):
        """Log current trading status."""
        try:
            balance = self.exchange.fetch_balance()
            # Use USD for Kraken, fallback to USDT for other exchanges
            quote_balance = balance.get("USD", {}) or balance.get("USDT", {})

            logger.info(
                f"Status: Free=${quote_balance.get('free', 0):.2f}, "
                f"Used=${quote_balance.get('used', 0):.2f}, "
                f"Positions={len(self.positions)}, "
                f"Daily PnL=${self.daily_pnl:.2f}"
            )
        except Exception as e:
            logger.warning(f"Could not fetch balance: {e}")

    def get_status(self) -> Dict:
        """Get current live trading status."""
        try:
            balance = self.exchange.fetch_balance()
            # Use USD for Kraken, fallback to USDT for other exchanges
            usdt = balance.get("USD", {}) or balance.get("USDT", {})
        except Exception as e:
            logger.warning(f"Could not fetch balance for status: {e}")
            usdt = {"free": 0, "used": 0, "total": 0}

        return {
            "running": self.running,
            "exchange": self.exchange.id,
            "free_balance": usdt.get("free", 0),
            "used_balance": usdt.get("used", 0),
            "total_balance": usdt.get("total", 0),
            "daily_pnl": self.daily_pnl,
            "open_positions": len(self.positions),
            "positions": {
                symbol: {
                    "side": pos.side,
                    "size": pos.size,
                    "entry_price": pos.entry_price,
                    "order_id": pos.order_id
                }
                for symbol, pos in self.positions.items()
            }
        }

    def emergency_close_all(self):
        """Emergency close all positions."""
        logger.warning("EMERGENCY: Closing all positions!")

        for symbol in list(self.positions.keys()):
            self._close_position(symbol, "emergency_close")

        self.stop()
