"""Paper trading engine for simulated trading."""

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
class PaperPosition:
    """Represents a paper trading position."""
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    unrealized_pnl: float = 0.0


@dataclass
class PaperAccount:
    """Paper trading account state."""
    initial_capital: float
    cash: float
    positions: Dict[str, PaperPosition] = field(default_factory=dict)
    trade_history: List[Dict] = field(default_factory=list)
    daily_pnl: float = 0.0

    @property
    def equity(self) -> float:
        """Calculate total account equity."""
        position_value = sum(
            p.size * p.entry_price + p.unrealized_pnl
            for p in self.positions.values()
        )
        return self.cash + position_value

    @property
    def total_pnl(self) -> float:
        """Calculate total PnL."""
        return self.equity - self.initial_capital


class PaperTrader:
    """Paper trading engine for strategy simulation."""

    def __init__(
        self,
        strategy: MLStrategy,
        data_fetcher: DataFetcher,
        storage: DataStorage,
        config: dict
    ):
        """
        Initialize PaperTrader.

        Args:
            strategy: Trading strategy
            data_fetcher: Data fetcher instance
            storage: Data storage instance
            config: Configuration dictionary
        """
        self.strategy = strategy
        self.data_fetcher = data_fetcher
        self.storage = storage
        self.config = config

        paper_config = config.get("paper_trading", {})
        initial_capital = paper_config.get("initial_capital", 10000)

        self.account = PaperAccount(
            initial_capital=initial_capital,
            cash=initial_capital
        )

        self.commission = config.get("backtest", {}).get("commission", 0.001)
        self.running = False

    def start(self, symbols: List[str], interval_seconds: int = 60):
        """
        Start paper trading loop.

        Args:
            symbols: List of trading pairs to trade
            interval_seconds: Time between trading iterations
        """
        self.running = True
        logger.info(f"Starting paper trading for {symbols}")

        while self.running:
            try:
                for symbol in symbols:
                    self._process_symbol(symbol)

                # Log account status
                logger.info(
                    f"Account: Cash=${self.account.cash:.2f}, "
                    f"Equity=${self.account.equity:.2f}, "
                    f"PnL=${self.account.total_pnl:.2f}"
                )

                time.sleep(interval_seconds)

            except KeyboardInterrupt:
                logger.info("Paper trading stopped by user")
                self.stop()
            except Exception as e:
                logger.error(f"Error in paper trading loop: {e}")
                time.sleep(interval_seconds)

    def stop(self):
        """Stop paper trading."""
        self.running = False
        logger.info("Paper trading stopped")

    def _process_symbol(self, symbol: str):
        """Process trading logic for a single symbol."""
        # Fetch latest data
        timeframe = self.config.get("trading", {}).get("timeframe", "1h")
        df = self.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=200)

        if df.empty:
            return

        current_price = df["close"].iloc[-1]

        # Update unrealized PnL for existing positions
        if symbol in self.account.positions:
            position = self.account.positions[symbol]
            if position.side == "long":
                position.unrealized_pnl = (current_price - position.entry_price) * position.size
            else:
                position.unrealized_pnl = (position.entry_price - current_price) * position.size

            # Check stop loss / take profit
            self._check_exit_conditions(symbol, current_price)

        # Generate trading signal
        signal_result = self.strategy.get_signal_with_risk_check(
            df=df,
            current_price=current_price,
            open_positions=len(self.account.positions),
            daily_pnl=self.account.daily_pnl,
            capital=self.account.cash
        )

        action = signal_result.get("action")

        if action == "buy" and symbol not in self.account.positions:
            self._open_position(symbol, "long", signal_result, current_price)
        elif action == "sell" and symbol not in self.account.positions:
            # For spot trading, we only go long. Skip short signals.
            pass
        elif action == "close" and symbol in self.account.positions:
            self._close_position(symbol, current_price, signal_result.get("reason", "signal"))

    def _open_position(
        self,
        symbol: str,
        side: str,
        signal_result: Dict,
        current_price: float
    ):
        """Open a new paper position."""
        size = signal_result.get("size", 0)
        cost = size * current_price * (1 + self.commission)

        if cost > self.account.cash:
            logger.warning(f"Insufficient cash to open position in {symbol}")
            return

        position = PaperPosition(
            symbol=symbol,
            side=side,
            size=size,
            entry_price=current_price,
            entry_time=datetime.now(),
            stop_loss=signal_result.get("stop_loss", current_price * 0.98),
            take_profit=signal_result.get("take_profit", current_price * 1.04)
        )

        self.account.positions[symbol] = position
        self.account.cash -= cost
        self.strategy.update_position(1, current_price)

        logger.info(
            f"PAPER BUY: {size:.6f} {symbol} @ ${current_price:.2f} | "
            f"Cost: ${cost:.2f} | SL: ${position.stop_loss:.2f} | TP: ${position.take_profit:.2f}"
        )

        # Save to storage
        self.storage.save_trade(
            symbol=symbol,
            side="buy",
            price=current_price,
            amount=size,
            cost=cost,
            is_paper=True
        )

    def _close_position(self, symbol: str, current_price: float, reason: str):
        """Close an existing paper position."""
        if symbol not in self.account.positions:
            return

        position = self.account.positions[symbol]
        proceeds = position.size * current_price * (1 - self.commission)
        pnl = proceeds - (position.size * position.entry_price)

        self.account.cash += proceeds
        self.account.daily_pnl += pnl
        del self.account.positions[symbol]
        self.strategy.update_position(0)

        # Record trade
        trade_record = {
            "symbol": symbol,
            "side": "sell",
            "entry_price": position.entry_price,
            "exit_price": current_price,
            "size": position.size,
            "pnl": pnl,
            "pnl_pct": pnl / (position.size * position.entry_price),
            "reason": reason,
            "timestamp": datetime.now()
        }
        self.account.trade_history.append(trade_record)

        logger.info(
            f"PAPER SELL: {position.size:.6f} {symbol} @ ${current_price:.2f} | "
            f"PnL: ${pnl:.2f} ({trade_record['pnl_pct']:.2%}) | Reason: {reason}"
        )

        # Save to storage
        self.storage.save_trade(
            symbol=symbol,
            side="sell",
            price=current_price,
            amount=position.size,
            cost=proceeds,
            is_paper=True
        )

    def _check_exit_conditions(self, symbol: str, current_price: float):
        """Check if stop loss or take profit should trigger."""
        if symbol not in self.account.positions:
            return

        position = self.account.positions[symbol]

        if position.side == "long":
            if current_price <= position.stop_loss:
                self._close_position(symbol, current_price, "stop_loss")
            elif current_price >= position.take_profit:
                self._close_position(symbol, current_price, "take_profit")

    def get_status(self) -> Dict:
        """Get current paper trading status."""
        return {
            "running": self.running,
            "cash": self.account.cash,
            "equity": self.account.equity,
            "total_pnl": self.account.total_pnl,
            "daily_pnl": self.account.daily_pnl,
            "open_positions": len(self.account.positions),
            "total_trades": len(self.account.trade_history),
            "positions": {
                symbol: {
                    "side": pos.side,
                    "size": pos.size,
                    "entry_price": pos.entry_price,
                    "unrealized_pnl": pos.unrealized_pnl
                }
                for symbol, pos in self.account.positions.items()
            }
        }

    def get_trade_history(self) -> pd.DataFrame:
        """Get trade history as DataFrame."""
        if not self.account.trade_history:
            return pd.DataFrame()
        return pd.DataFrame(self.account.trade_history)
