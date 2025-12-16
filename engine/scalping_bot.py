"""
Scalping Bot - Confluence-Based Automated Trading Bot.

This bot makes trading decisions based on MAXIMUM CONFLUENCE of signals:
1. ICT Strategy (FVG, MSS, OB, OTE, Liquidity)
2. SMT Divergence (BTC vs ETH correlation)
3. Multi-Timeframe Analysis (1m, 5m, 15m)
4. ML Model Predictions
5. Technical Momentum (RSI, MACD, BB)

Features:
1. Confluence-based entry decisions
2. Paper and live trading modes
3. Real-time position management
4. Automatic stop loss and take profit
5. Risk management with daily limits
6. Performance tracking and statistics

Only trades when multiple signals AGREE (high confluence).
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import ccxt

from strategy.scalping import ScalpingStrategy, ScalpSignal, TradingMode, TRADING_MODE_PRESETS
from data.fetcher import DataFetcher
from data.storage import DataStorage


class BotMode(Enum):
    PAPER = "paper"
    LIVE = "live"


class BotStatus(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class ScalpPosition:
    """Active scalp position."""
    id: str
    symbol: str
    side: str  # 'long' or 'short'
    entry_price: float
    size: float
    stop_loss: float
    take_profit: float
    entry_time: datetime
    order_id: Optional[str] = None
    unrealized_pnl: float = 0.0


@dataclass
class ScalpTrade:
    """Completed scalp trade."""
    id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_pct: float
    entry_time: datetime
    exit_time: datetime
    exit_reason: str  # 'take_profit', 'stop_loss', 'signal', 'manual'
    duration_seconds: float


@dataclass
class BotStats:
    """Bot performance statistics."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    avg_trade_duration: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    peak_equity: float = 0.0


class ScalpingBot:
    """
    Automated scalping bot for continuous trading.

    Usage:
        bot = ScalpingBot(exchange, fetcher, storage, config)
        await bot.start()  # Runs continuously
        await bot.stop()   # Graceful shutdown
    """

    def __init__(
        self,
        exchange: ccxt.Exchange,
        fetcher: DataFetcher,
        storage: DataStorage,
        config: Optional[Dict] = None,
        ml_strategy=None
    ):
        """
        Initialize scalping bot.

        Args:
            exchange: CCXT exchange instance
            fetcher: Data fetcher for market data
            storage: Storage for trade persistence
            config: Bot configuration
            ml_strategy: Optional ML strategy for predictions
        """
        self.exchange = exchange
        self.fetcher = fetcher
        self.storage = storage
        self.config = config or {}

        # ML Strategy for predictions
        self.ml_strategy = ml_strategy

        # Bot settings
        self.mode = BotMode(self.config.get('mode', 'paper'))
        self.symbol = self.config.get('symbol', 'BTC/USD')
        self.comparison_symbol = self.config.get('comparison_symbol', 'ETH/USD')  # For SMT
        self.timeframe = self.config.get('timeframe', '1m')
        self.check_interval = self.config.get('check_interval', 5)  # seconds

        # Capital and risk
        self.initial_capital = self.config.get('initial_capital', 1000)
        self.capital = self.initial_capital
        self.risk_per_trade = self.config.get('risk_per_trade', 0.01)  # 1%
        self.max_daily_loss = self.config.get('max_daily_loss', 0.05)  # 5%
        self.max_positions = self.config.get('max_positions', 1)  # Usually 1 for scalping

        # Trading mode
        trading_mode_str = self.config.get('trading_mode', 'medium')
        self.trading_mode = TradingMode(trading_mode_str)

        # Initialize strategy (now confluence-based with trading mode)
        strategy_config = self.config.get('strategy', {})
        self.strategy = ScalpingStrategy(strategy_config, mode=self.trading_mode)

        # Last signal details for UI
        self.last_signal = None
        self.last_signal_details = {}

        # State
        self.status = BotStatus.STOPPED
        self.positions: Dict[str, ScalpPosition] = {}
        self.trades: List[ScalpTrade] = []
        self.stats = BotStats(peak_equity=self.initial_capital)

        # Daily tracking
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.last_reset_date = datetime.utcnow().date()

        # Control
        self._running = False
        self._task: Optional[asyncio.Task] = None

        ml_status = "enabled" if ml_strategy else "disabled"
        logger.info(f"ScalpingBot initialized: mode={self.mode.value}, symbol={self.symbol}, capital=${self.capital}, ML={ml_status}")

    async def start(self):
        """Start the scalping bot."""
        if self._running:
            logger.warning("Bot is already running")
            return

        logger.info(f"Starting ScalpingBot in {self.mode.value} mode...")
        self._running = True
        self.status = BotStatus.RUNNING

        try:
            await self._run_loop()
        except Exception as e:
            logger.error(f"Bot error: {e}")
            self.status = BotStatus.ERROR
        finally:
            self._running = False
            if self.status != BotStatus.ERROR:
                self.status = BotStatus.STOPPED

    async def stop(self):
        """Stop the scalping bot gracefully."""
        logger.info("Stopping ScalpingBot...")
        self._running = False

        # Close all positions
        if self.positions:
            logger.info(f"Closing {len(self.positions)} open positions...")
            for pos_id in list(self.positions.keys()):
                await self._close_position(pos_id, "bot_stopped")

        self.status = BotStatus.STOPPED
        logger.info("ScalpingBot stopped")

    async def pause(self):
        """Pause the bot (keeps positions, stops new trades)."""
        self.status = BotStatus.PAUSED
        logger.info("ScalpingBot paused")

    async def resume(self):
        """Resume paused bot."""
        if self.status == BotStatus.PAUSED:
            self.status = BotStatus.RUNNING
            logger.info("ScalpingBot resumed")

    def set_trading_mode(self, mode: str, custom_config: Optional[Dict] = None):
        """
        Change trading mode at runtime.

        Args:
            mode: 'safe', 'medium', 'fast', or 'custom'
            custom_config: Custom parameters (for custom mode)
        """
        try:
            new_mode = TradingMode(mode)
            self.trading_mode = new_mode
            self.strategy.set_mode(new_mode, custom_config)
            logger.info(f"Trading mode changed to {mode.upper()}")
            return True
        except ValueError:
            logger.error(f"Invalid trading mode: {mode}")
            return False

    def get_trading_mode_info(self) -> Dict:
        """Get current trading mode information."""
        return self.strategy.get_mode_info()

    @staticmethod
    def get_available_trading_modes() -> Dict:
        """Get all available trading modes."""
        return ScalpingStrategy.get_available_modes()

    async def _run_loop(self):
        """Main bot execution loop."""
        logger.info("Scalping bot loop started")

        while self._running:
            try:
                # Reset daily stats if new day
                self._check_daily_reset()

                # Check daily loss limit
                if self._is_daily_limit_hit():
                    if self.status == BotStatus.RUNNING:
                        logger.warning(f"Daily loss limit hit ({self.daily_pnl:.2f}). Pausing...")
                        self.status = BotStatus.PAUSED
                    await asyncio.sleep(60)  # Check again in a minute
                    continue

                # Skip if paused
                if self.status == BotStatus.PAUSED:
                    await asyncio.sleep(self.check_interval)
                    continue

                # Fetch data for all confluence signals
                # Primary asset (1m)
                df = self.fetcher.fetch_ohlcv(self.symbol, self.timeframe, limit=200)

                if df.empty:
                    logger.warning("No data received")
                    await asyncio.sleep(self.check_interval)
                    continue

                current_price = float(df['close'].iloc[-1])

                # Comparison asset for SMT divergence (ETH)
                df_comparison = None
                try:
                    df_comparison = self.fetcher.fetch_ohlcv(self.comparison_symbol, self.timeframe, limit=200)
                except Exception as e:
                    logger.debug(f"Failed to fetch comparison data: {e}")

                # Multi-timeframe data (5m and 15m)
                df_5m = None
                df_15m = None
                try:
                    df_5m = self.fetcher.fetch_ohlcv(self.symbol, '5m', limit=200)
                    df_15m = self.fetcher.fetch_ohlcv(self.symbol, '15m', limit=200)
                except Exception as e:
                    logger.debug(f"Failed to fetch MTF data: {e}")

                # Update positions and check exits
                await self._update_positions(current_price)

                # Check for new entry if no position
                if len(self.positions) < self.max_positions:
                    await self._check_entry(df, df_comparison, df_5m, df_15m, current_price)

                # Log status periodically
                if int(time.time()) % 60 == 0:
                    self._log_status()

                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                logger.info("Bot loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in bot loop: {e}")
                await asyncio.sleep(self.check_interval)

    def _get_ml_prediction(self, df) -> Optional[Dict]:
        """
        Get ML model prediction if available.

        Returns:
            Dict with 'signal' ('BUY'/'SELL'/'HOLD') and 'confidence' (0-1)
            or None if ML strategy not available
        """
        if not self.ml_strategy:
            return None

        try:
            # Use the ML strategy to generate a signal
            from strategy.ml_strategy import Signal
            signal, confidence = self.ml_strategy.generate_signal(df)

            # Convert Signal enum to string
            signal_str = signal.name if hasattr(signal, 'name') else str(signal)

            return {
                'signal': signal_str,
                'confidence': confidence
            }
        except Exception as e:
            logger.debug(f"ML prediction failed: {e}")
            return None

    async def _check_entry(self, df, df_comparison, df_5m, df_15m, current_price: float):
        """Check for confluence-based entry signal and open position."""
        # Get ML prediction if available
        ml_prediction = self._get_ml_prediction(df)

        if ml_prediction:
            logger.debug(f"ML Prediction: {ml_prediction['signal']} ({ml_prediction['confidence']*100:.1f}%)")

        # Generate signal using ALL available data for confluence
        signal, confidence, details = self.strategy.generate_signal(
            df=df,
            df_comparison=df_comparison,
            df_5m=df_5m,
            df_15m=df_15m,
            ml_prediction=ml_prediction,
            current_price=current_price
        )

        # Store for UI
        self.last_signal = signal
        self.last_signal_details = details

        # Log confluence details periodically
        if int(time.time()) % 30 == 0:  # Every 30 seconds
            logger.info(f"Confluence: {details.get('aligned_signals', 0)}/5 signals aligned, "
                       f"Bullish: {details.get('bullish_score', 0):.1f}%, "
                       f"Bearish: {details.get('bearish_score', 0):.1f}%")

        if signal in [ScalpSignal.BUY, ScalpSignal.STRONG_BUY, ScalpSignal.SELL, ScalpSignal.STRONG_SELL]:
            if confidence >= self.strategy.min_confidence:
                side = 'long' if signal in [ScalpSignal.BUY, ScalpSignal.STRONG_BUY] else 'short'

                # Calculate position size (higher confidence = larger position)
                size = self.strategy.get_position_size(
                    capital=self.capital,
                    risk_per_trade=self.risk_per_trade,
                    entry_price=details['entry_price'],
                    stop_loss=details['stop_loss'],
                    confidence=confidence
                )

                if size > 0:
                    await self._open_position(
                        side=side,
                        price=current_price,
                        size=size,
                        stop_loss=details['stop_loss'],
                        take_profit=details['take_profit'],
                        reason=details.get('reason', 'Confluence signal'),
                        confluence_details=details
                    )

    async def _open_position(
        self,
        side: str,
        price: float,
        size: float,
        stop_loss: float,
        take_profit: float,
        reason: str,
        confluence_details: Dict = None
    ):
        """Open a new position based on confluence signal."""
        pos_id = f"scalp_{int(time.time()*1000)}"

        # Log confluence details
        if confluence_details:
            logger.info(f"CONFLUENCE ENTRY: {confluence_details.get('aligned_signals', 0)}/5 signals aligned")
            logger.info(f"  ICT Score: {confluence_details.get('ict_confluence_score', 0)}/30 ({confluence_details.get('ict_strength', 'N/A')})")
            logger.info(f"  Bullish: {confluence_details.get('bullish_score', 0):.1f}%, Bearish: {confluence_details.get('bearish_score', 0):.1f}%")

        if self.mode == BotMode.LIVE:
            try:
                # Place market order
                if side == 'long':
                    order = self.exchange.create_market_buy_order(self.symbol, size)
                else:
                    order = self.exchange.create_market_sell_order(self.symbol, size)

                actual_price = order.get('average', price)
                order_id = order.get('id')

                logger.info(f"LIVE ORDER: {side.upper()} {size:.6f} {self.symbol} @ ${actual_price:,.2f}")

            except Exception as e:
                logger.error(f"Failed to place order: {e}")
                return
        else:
            # Paper trading - immediate fill
            actual_price = price
            order_id = None
            logger.info(f"PAPER: {side.upper()} {size:.6f} {self.symbol} @ ${actual_price:,.2f}")

        # Create position
        position = ScalpPosition(
            id=pos_id,
            symbol=self.symbol,
            side=side,
            entry_price=actual_price,
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_time=datetime.utcnow(),
            order_id=order_id
        )

        self.positions[pos_id] = position
        self.strategy.record_trade()

        logger.info(f"Opened {side} position: entry=${actual_price:,.2f}, SL=${stop_loss:,.2f}, TP=${take_profit:,.2f}")
        logger.info(f"Reason: {reason}")

    async def _update_positions(self, current_price: float):
        """Update positions and check for exits."""
        for pos_id, pos in list(self.positions.items()):
            # Calculate unrealized PnL
            if pos.side == 'long':
                pos.unrealized_pnl = (current_price - pos.entry_price) * pos.size
                hit_sl = current_price <= pos.stop_loss
                hit_tp = current_price >= pos.take_profit
            else:
                pos.unrealized_pnl = (pos.entry_price - current_price) * pos.size
                hit_sl = current_price >= pos.stop_loss
                hit_tp = current_price <= pos.take_profit

            # Check exits
            if hit_sl:
                await self._close_position(pos_id, "stop_loss", current_price)
            elif hit_tp:
                await self._close_position(pos_id, "take_profit", current_price)

    async def _close_position(
        self,
        pos_id: str,
        reason: str,
        exit_price: Optional[float] = None
    ):
        """Close a position."""
        if pos_id not in self.positions:
            return

        pos = self.positions[pos_id]

        if exit_price is None:
            # Fetch current price
            ticker = self.exchange.fetch_ticker(self.symbol)
            exit_price = ticker['last']

        if self.mode == BotMode.LIVE:
            try:
                # Close position with market order
                if pos.side == 'long':
                    order = self.exchange.create_market_sell_order(self.symbol, pos.size)
                else:
                    order = self.exchange.create_market_buy_order(self.symbol, pos.size)

                exit_price = order.get('average', exit_price)
                logger.info(f"LIVE CLOSE: {pos.side} @ ${exit_price:,.2f}")

            except Exception as e:
                logger.error(f"Failed to close position: {e}")
                return
        else:
            logger.info(f"PAPER CLOSE: {pos.side} @ ${exit_price:,.2f}")

        # Calculate PnL
        if pos.side == 'long':
            pnl = (exit_price - pos.entry_price) * pos.size
            pnl_pct = (exit_price - pos.entry_price) / pos.entry_price * 100
        else:
            pnl = (pos.entry_price - exit_price) * pos.size
            pnl_pct = (pos.entry_price - exit_price) / pos.entry_price * 100

        duration = (datetime.utcnow() - pos.entry_time).total_seconds()

        # Record trade
        trade = ScalpTrade(
            id=pos_id,
            symbol=pos.symbol,
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            size=pos.size,
            pnl=pnl,
            pnl_pct=pnl_pct,
            entry_time=pos.entry_time,
            exit_time=datetime.utcnow(),
            exit_reason=reason,
            duration_seconds=duration
        )

        self.trades.append(trade)

        # Update stats
        self._update_stats(trade)

        # Update capital
        self.capital += pnl
        self.daily_pnl += pnl
        self.daily_trades += 1

        # Log result
        emoji = "+" if pnl >= 0 else ""
        logger.info(f"Trade closed ({reason}): {emoji}${pnl:.2f} ({pnl_pct:+.2f}%) in {duration:.1f}s")

        # Remove position
        del self.positions[pos_id]

        # Save complete scalp trade with P&L to storage
        try:
            self.storage.save_scalp_trade(
                symbol=pos.symbol,
                side=pos.side,
                entry_price=pos.entry_price,
                exit_price=exit_price,
                amount=pos.size,
                pnl=pnl,
                pnl_pct=pnl_pct,
                exit_reason=f"scalping:{reason}",
                duration_seconds=duration,
                is_paper=(self.mode == BotMode.PAPER)
            )
        except Exception as e:
            logger.warning(f"Failed to save scalp trade: {e}")

    def _update_stats(self, trade: ScalpTrade):
        """Update bot statistics."""
        self.stats.total_trades += 1

        if trade.pnl >= 0:
            self.stats.winning_trades += 1
            self.stats.largest_win = max(self.stats.largest_win, trade.pnl)
        else:
            self.stats.losing_trades += 1
            self.stats.largest_loss = min(self.stats.largest_loss, trade.pnl)

        self.stats.total_pnl += trade.pnl

        # Update win rate
        if self.stats.total_trades > 0:
            self.stats.win_rate = self.stats.winning_trades / self.stats.total_trades * 100

        # Update profit factor
        total_wins = sum(t.pnl for t in self.trades if t.pnl > 0)
        total_losses = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        if total_losses > 0:
            self.stats.profit_factor = total_wins / total_losses

        # Update avg duration
        self.stats.avg_trade_duration = sum(t.duration_seconds for t in self.trades) / len(self.trades)

        # Update drawdown
        if self.capital > self.stats.peak_equity:
            self.stats.peak_equity = self.capital
        else:
            dd = (self.stats.peak_equity - self.capital) / self.stats.peak_equity * 100
            self.stats.current_drawdown = dd
            self.stats.max_drawdown = max(self.stats.max_drawdown, dd)

    def _check_daily_reset(self):
        """Reset daily stats if new day."""
        today = datetime.utcnow().date()
        if today > self.last_reset_date:
            logger.info(f"New day - resetting daily stats. Yesterday: {self.daily_trades} trades, ${self.daily_pnl:.2f} PnL")
            self.daily_pnl = 0.0
            self.daily_trades = 0
            self.last_reset_date = today

    def _is_daily_limit_hit(self) -> bool:
        """Check if daily loss limit is hit."""
        max_loss = self.initial_capital * self.max_daily_loss
        return self.daily_pnl <= -max_loss

    def _log_status(self):
        """Log current bot status."""
        logger.info(
            f"Bot Status: {self.status.value} | "
            f"Capital: ${self.capital:.2f} | "
            f"Positions: {len(self.positions)} | "
            f"Daily: {self.daily_trades} trades, ${self.daily_pnl:+.2f} | "
            f"Total: {self.stats.total_trades} trades, ${self.stats.total_pnl:+.2f}"
        )

    def get_status(self) -> Dict[str, Any]:
        """Get current bot status including confluence signal details."""
        # Get current signal info
        signal_info = {}
        if self.last_signal_details:
            signal_info = {
                "signal": self.last_signal.value if self.last_signal else "HOLD",
                "confidence": self.last_signal_details.get("confidence", 0),
                "direction": self.last_signal_details.get("direction", "neutral"),
                "aligned_signals": self.last_signal_details.get("aligned_signals", 0),
                "total_signals": self.last_signal_details.get("total_signals", 5),
                "bullish_score": self.last_signal_details.get("bullish_score", 0),
                "bearish_score": self.last_signal_details.get("bearish_score", 0),
                "ict_confluence_score": self.last_signal_details.get("ict_confluence_score", 0),
                "ict_strength": self.last_signal_details.get("ict_strength", "none"),
                "reason": self.last_signal_details.get("reason", ""),
                # ML prediction info
                "ml_prediction": self.last_signal_details.get("signal_breakdown", {}).get("ml_prediction", {}),
            }

        # Get trading mode info
        mode_info = self.get_trading_mode_info()

        return {
            "status": self.status.value,
            "mode": self.mode.value,
            "trading_mode": mode_info,
            "ml_enabled": self.ml_strategy is not None,
            "symbol": self.symbol,
            "comparison_symbol": self.comparison_symbol,
            "capital": self.capital,
            "initial_capital": self.initial_capital,
            "total_pnl": self.stats.total_pnl,
            "total_pnl_pct": (self.capital - self.initial_capital) / self.initial_capital * 100,
            "positions": len(self.positions),
            "position_details": [
                {
                    "id": p.id,
                    "side": p.side,
                    "entry_price": p.entry_price,
                    "size": p.size,
                    "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit,
                    "unrealized_pnl": p.unrealized_pnl
                }
                for p in self.positions.values()
            ],
            "daily_trades": self.daily_trades,
            "daily_pnl": self.daily_pnl,
            "stats": {
                "total_trades": self.stats.total_trades,
                "winning_trades": self.stats.winning_trades,
                "losing_trades": self.stats.losing_trades,
                "win_rate": self.stats.win_rate,
                "profit_factor": self.stats.profit_factor,
                "largest_win": self.stats.largest_win,
                "largest_loss": self.stats.largest_loss,
                "max_drawdown": self.stats.max_drawdown,
                "avg_trade_duration": self.stats.avg_trade_duration
            },
            "recent_trades": [
                {
                    "side": t.side,
                    "entry": t.entry_price,
                    "exit": t.exit_price,
                    "pnl": t.pnl,
                    "pnl_pct": t.pnl_pct,
                    "reason": t.exit_reason,
                    "duration": t.duration_seconds
                }
                for t in self.trades[-10:]  # Last 10 trades
            ],
            "current_signal": signal_info
        }


# Factory function
def create_scalping_bot(
    exchange: ccxt.Exchange,
    fetcher: DataFetcher,
    storage: DataStorage,
    mode: str = "paper",
    symbol: str = "BTC/USD",
    capital: float = 1000,
    trading_mode: str = "medium",
    ml_strategy=None,
    **kwargs
) -> ScalpingBot:
    """
    Create a configured scalping bot.

    Args:
        exchange: CCXT exchange instance
        fetcher: Data fetcher for market data
        storage: Storage for trade persistence
        mode: 'paper' or 'live'
        symbol: Trading symbol
        capital: Initial capital
        trading_mode: 'safe', 'medium', 'fast', or 'custom'
        ml_strategy: Optional ML strategy for predictions
        **kwargs: Additional configuration options
    """
    config = {
        "mode": mode,
        "symbol": symbol,
        "initial_capital": capital,
        "trading_mode": trading_mode,
        "timeframe": kwargs.get("timeframe", "1m"),
        "check_interval": kwargs.get("check_interval", 5),
        "risk_per_trade": kwargs.get("risk_per_trade", 0.01),
        "max_daily_loss": kwargs.get("max_daily_loss", 0.05),
        "max_positions": kwargs.get("max_positions", 1),
        "enabled_confluences": kwargs.get("enabled_confluences"),
        "strategy": {
            # These will override preset values if provided
            "take_profit_pct": kwargs.get("take_profit_pct"),
            "stop_loss_pct": kwargs.get("stop_loss_pct"),
            "min_confidence": kwargs.get("min_confidence"),
            "min_confluence_score": kwargs.get("min_confluence_score"),
            "min_aligned_signals": kwargs.get("min_aligned_signals"),
            "cooldown_seconds": kwargs.get("cooldown_seconds"),
            "max_trades_per_hour": kwargs.get("max_trades_per_hour"),
            "enabled_confluences": kwargs.get("enabled_confluences"),
        }
    }

    # Remove None values from strategy config
    config["strategy"] = {k: v for k, v in config["strategy"].items() if v is not None}

    return ScalpingBot(exchange, fetcher, storage, config, ml_strategy=ml_strategy)
