"""
Trading Bots - Multi-Strategy Automated Trading Bots.

This module contains trading bots for different trading styles:
1. Short Term Bot - Intraday to multi-day positions (1-5 days)
2. Swing Trading Bot - Multi-day to weekly positions (3-14 days)
3. Long Term Bot - Position trading and DCA strategies (weeks to months)

All bots share common infrastructure but use different:
- Timeframes
- Entry/exit criteria
- Risk management parameters
- Profit targets
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import ccxt
import uuid

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


class BotType(Enum):
    SCALPING = "scalping"
    SHORT_TERM = "short_term"
    SWING = "swing"
    LONG_TERM = "long_term"


@dataclass
class Position:
    """Active trading position."""
    id: str
    symbol: str
    side: str  # 'long' or 'short'
    entry_price: float
    size: float
    stop_loss: float
    take_profit: float
    entry_time: datetime
    bot_type: str
    order_id: Optional[str] = None
    unrealized_pnl: float = 0.0


@dataclass
class Trade:
    """Completed trade."""
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
    exit_reason: str
    duration_seconds: float
    bot_type: str


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


# Strategy-specific presets
SHORT_TERM_PRESETS = {
    'conservative': {
        'min_confluence_score': 18,
        'min_confidence': 60,
        'take_profit_pct': 0.015,  # 1.5%
        'stop_loss_pct': 0.008,    # 0.8%
        'check_interval': 300,     # 5 minutes
        'timeframe': '4h',
    },
    'medium': {
        'min_confluence_score': 14,
        'min_confidence': 50,
        'take_profit_pct': 0.02,   # 2%
        'stop_loss_pct': 0.01,     # 1%
        'check_interval': 300,
        'timeframe': '4h',
    },
    'aggressive': {
        'min_confluence_score': 10,
        'min_confidence': 40,
        'take_profit_pct': 0.03,   # 3%
        'stop_loss_pct': 0.015,    # 1.5%
        'check_interval': 300,
        'timeframe': '4h',
    }
}

SWING_PRESETS = {
    'conservative': {
        'min_confluence_score': 20,
        'min_confidence': 65,
        'take_profit_pct': 0.08,   # 8%
        'stop_loss_pct': 0.03,     # 3%
        'check_interval': 3600,    # 1 hour
        'timeframe': '1d',
    },
    'medium': {
        'min_confluence_score': 15,
        'min_confidence': 55,
        'take_profit_pct': 0.12,   # 12%
        'stop_loss_pct': 0.04,     # 4%
        'check_interval': 3600,
        'timeframe': '1d',
    },
    'aggressive': {
        'min_confluence_score': 12,
        'min_confidence': 45,
        'take_profit_pct': 0.15,   # 15%
        'stop_loss_pct': 0.05,     # 5%
        'check_interval': 3600,
        'timeframe': '1d',
    }
}

LONG_TERM_PRESETS = {
    'conservative': {
        'min_confluence_score': 22,
        'min_confidence': 70,
        'take_profit_pct': 0.25,   # 25%
        'stop_loss_pct': 0.08,     # 8%
        'check_interval': 14400,   # 4 hours
        'timeframe': '1w',
        'dca_enabled': True,
        'dca_threshold': -0.05,    # DCA when down 5%
    },
    'medium': {
        'min_confluence_score': 18,
        'min_confidence': 60,
        'take_profit_pct': 0.35,   # 35%
        'stop_loss_pct': 0.10,     # 10%
        'check_interval': 14400,
        'timeframe': '1w',
        'dca_enabled': True,
        'dca_threshold': -0.08,
    },
    'aggressive': {
        'min_confluence_score': 14,
        'min_confidence': 50,
        'take_profit_pct': 0.50,   # 50%
        'stop_loss_pct': 0.15,     # 15%
        'check_interval': 14400,
        'timeframe': '1w',
        'dca_enabled': True,
        'dca_threshold': -0.10,
    }
}


class BaseTradingBot:
    """Base class for all trading bots."""

    def __init__(
        self,
        exchange: ccxt.Exchange,
        fetcher: DataFetcher,
        storage: DataStorage,
        config: Optional[Dict] = None,
        ml_strategy=None
    ):
        self.exchange = exchange
        self.fetcher = fetcher
        self.storage = storage
        self.config = config or {}
        self.ml_strategy = ml_strategy

        # Bot settings
        self.mode = BotMode(self.config.get('mode', 'paper'))
        self.symbol = self.config.get('symbol', 'BTC/USD')
        self.comparison_symbol = self.config.get('comparison_symbol', 'ETH/USD')

        # Capital and risk
        self.initial_capital = self.config.get('initial_capital', 1000)
        self.capital = self.initial_capital
        self.risk_per_trade = self.config.get('risk_per_trade', 0.02)
        self.max_daily_loss = self.config.get('max_daily_loss', 0.05)
        self.max_positions = self.config.get('max_positions', 1)

        # State
        self.status = BotStatus.STOPPED
        self.position: Optional[Position] = None
        self.trades: List[Trade] = []
        self.stats = BotStats()
        self.stats.peak_equity = self.initial_capital

        # Tracking
        self.daily_pnl = 0.0
        self.last_trade_time: Optional[datetime] = None
        self.start_time: Optional[datetime] = None
        self.last_signal: Optional[Dict] = None

        # To be set by subclasses
        self.bot_type: BotType = BotType.SCALPING
        self.timeframe = '1h'
        self.check_interval = 60
        self.take_profit_pct = 0.02
        self.stop_loss_pct = 0.01
        self.min_confluence_score = 12
        self.min_confidence = 50

    async def start(self):
        """Start the trading bot."""
        self.status = BotStatus.RUNNING
        self.start_time = datetime.now()
        logger.info(f"{self.bot_type.value} bot started in {self.mode.value} mode")

        while self.status == BotStatus.RUNNING:
            try:
                await self._trading_loop()
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(5)

            await asyncio.sleep(self.check_interval)

    async def stop(self):
        """Stop the trading bot."""
        self.status = BotStatus.STOPPED
        logger.info(f"{self.bot_type.value} bot stopped")

    async def pause(self):
        """Pause the trading bot."""
        self.status = BotStatus.PAUSED
        logger.info(f"{self.bot_type.value} bot paused")

    async def resume(self):
        """Resume the trading bot."""
        if self.status == BotStatus.PAUSED:
            self.status = BotStatus.RUNNING
            logger.info(f"{self.bot_type.value} bot resumed")

    async def _trading_loop(self):
        """Main trading loop - to be implemented by subclasses."""
        raise NotImplementedError

    async def _analyze_market(self) -> Dict:
        """Analyze market conditions - to be implemented by subclasses."""
        raise NotImplementedError

    async def _open_position(self, signal: Dict):
        """Open a new position."""
        if self.position is not None:
            return

        price = signal.get('price', 0)
        side = signal.get('direction', 'long')

        # Calculate position size based on risk
        risk_amount = self.capital * self.risk_per_trade
        stop_distance = price * self.stop_loss_pct
        size = risk_amount / stop_distance

        # Calculate stop loss and take profit
        if side == 'long':
            stop_loss = price * (1 - self.stop_loss_pct)
            take_profit = price * (1 + self.take_profit_pct)
        else:
            stop_loss = price * (1 + self.stop_loss_pct)
            take_profit = price * (1 - self.take_profit_pct)

        self.position = Position(
            id=str(uuid.uuid4())[:8],
            symbol=self.symbol,
            side=side,
            entry_price=price,
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_time=datetime.now(),
            bot_type=self.bot_type.value
        )

        self.last_trade_time = datetime.now()
        logger.info(f"Opened {side} position at {price:.2f} (SL: {stop_loss:.2f}, TP: {take_profit:.2f})")

    async def _close_position(self, price: float, reason: str):
        """Close current position."""
        if self.position is None:
            return

        pos = self.position

        # Calculate P&L
        if pos.side == 'long':
            pnl = (price - pos.entry_price) * pos.size
            pnl_pct = (price - pos.entry_price) / pos.entry_price * 100
        else:
            pnl = (pos.entry_price - price) * pos.size
            pnl_pct = (pos.entry_price - price) / pos.entry_price * 100

        duration = (datetime.now() - pos.entry_time).total_seconds()

        # Create trade record
        trade = Trade(
            id=pos.id,
            symbol=pos.symbol,
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=price,
            size=pos.size,
            pnl=pnl,
            pnl_pct=pnl_pct,
            entry_time=pos.entry_time,
            exit_time=datetime.now(),
            exit_reason=reason,
            duration_seconds=duration,
            bot_type=self.bot_type.value
        )

        self.trades.append(trade)
        self._update_stats(trade)

        # Update capital
        self.capital += pnl
        self.daily_pnl += pnl

        # Save to storage
        self._save_trade(trade)

        logger.info(f"Closed {pos.side} position at {price:.2f} ({reason}) - P&L: ${pnl:.2f} ({pnl_pct:.2f}%)")

        self.position = None

    def _update_stats(self, trade: Trade):
        """Update bot statistics."""
        self.stats.total_trades += 1
        self.stats.total_pnl += trade.pnl
        self.stats.total_pnl_pct += trade.pnl_pct

        if trade.pnl > 0:
            self.stats.winning_trades += 1
            self.stats.largest_win = max(self.stats.largest_win, trade.pnl)
        else:
            self.stats.losing_trades += 1
            self.stats.largest_loss = min(self.stats.largest_loss, trade.pnl)

        # Update win rate
        if self.stats.total_trades > 0:
            self.stats.win_rate = (self.stats.winning_trades / self.stats.total_trades) * 100

        # Update profit factor
        total_wins = sum(t.pnl for t in self.trades if t.pnl > 0)
        total_losses = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        if total_losses > 0:
            self.stats.profit_factor = total_wins / total_losses

        # Update drawdown
        if self.capital > self.stats.peak_equity:
            self.stats.peak_equity = self.capital
        self.stats.current_drawdown = (self.stats.peak_equity - self.capital) / self.stats.peak_equity * 100
        self.stats.max_drawdown = max(self.stats.max_drawdown, self.stats.current_drawdown)

        # Average trade duration
        total_duration = sum(t.duration_seconds for t in self.trades)
        self.stats.avg_trade_duration = total_duration / len(self.trades)

    def _save_trade(self, trade: Trade):
        """Save trade to storage."""
        try:
            self.storage.save_scalp_trade(
                symbol=trade.symbol,
                side=trade.side,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                amount=trade.size,
                pnl=trade.pnl,
                pnl_pct=trade.pnl_pct,
                exit_reason=f"{trade.bot_type}:{trade.exit_reason}",
                duration_seconds=trade.duration_seconds,
                is_paper=(self.mode == BotMode.PAPER)
            )
        except Exception as e:
            logger.warning(f"Failed to save trade: {e}")

    def get_status(self) -> Dict:
        """Get current bot status."""
        position_data = None
        if self.position:
            position_data = {
                'id': self.position.id,
                'symbol': self.position.symbol,
                'side': self.position.side,
                'entry_price': self.position.entry_price,
                'size': self.position.size,
                'stop_loss': self.position.stop_loss,
                'take_profit': self.position.take_profit,
                'unrealized_pnl': self.position.unrealized_pnl
            }

        return {
            'bot_type': self.bot_type.value,
            'status': self.status.value,
            'mode': self.mode.value,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'capital': self.capital,
            'initial_capital': self.initial_capital,
            'daily_pnl': self.daily_pnl,
            'position': position_data,
            'stats': {
                'total_trades': self.stats.total_trades,
                'winning_trades': self.stats.winning_trades,
                'losing_trades': self.stats.losing_trades,
                'win_rate': self.stats.win_rate,
                'total_pnl': self.stats.total_pnl,
                'profit_factor': self.stats.profit_factor,
                'max_drawdown': self.stats.max_drawdown
            },
            'last_signal': self.last_signal,
            'recent_trades': [
                {
                    'id': t.id,
                    'side': t.side,
                    'pnl': t.pnl,
                    'pnl_pct': t.pnl_pct,
                    'exit_reason': t.exit_reason,
                    'time': t.exit_time.isoformat()
                }
                for t in self.trades[-5:]
            ]
        }


class ShortTermBot(BaseTradingBot):
    """
    Short Term Trading Bot.

    Targets intraday to multi-day positions (1-5 days).
    Uses 4H/Daily timeframes with 1-3% profit targets.
    """

    def __init__(self, exchange, fetcher, storage, config=None, ml_strategy=None):
        super().__init__(exchange, fetcher, storage, config, ml_strategy)

        self.bot_type = BotType.SHORT_TERM

        # Load preset
        trading_mode = self.config.get('trading_mode', 'medium')
        preset = SHORT_TERM_PRESETS.get(trading_mode, SHORT_TERM_PRESETS['medium'])

        self.timeframe = preset['timeframe']
        self.check_interval = preset['check_interval']
        self.take_profit_pct = self.config.get('take_profit_pct', preset['take_profit_pct'])
        self.stop_loss_pct = self.config.get('stop_loss_pct', preset['stop_loss_pct'])
        self.min_confluence_score = self.config.get('min_confluence_score', preset['min_confluence_score'])
        self.min_confidence = self.config.get('min_confidence', preset['min_confidence'])

        # Short-term specific
        self.cooldown_period = 3600  # 1 hour between trades

    async def _trading_loop(self):
        """Main trading loop for short-term strategy."""
        # Check cooldown
        if self.last_trade_time:
            elapsed = (datetime.now() - self.last_trade_time).total_seconds()
            if elapsed < self.cooldown_period:
                return

        # Get current price
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            current_price = ticker['last']
        except Exception as e:
            logger.error(f"Failed to fetch ticker: {e}")
            return

        # Check position management
        if self.position:
            await self._manage_position(current_price)
            return

        # Analyze market
        signal = await self._analyze_market()
        self.last_signal = signal

        # Check entry conditions
        if signal and signal.get('score', 0) >= self.min_confluence_score:
            if signal.get('confidence', 0) >= self.min_confidence:
                signal['price'] = current_price
                await self._open_position(signal)

    async def _analyze_market(self) -> Dict:
        """Analyze market for short-term signals."""
        score = 0
        signals = []
        direction = None

        try:
            # Fetch 4H data
            df = await asyncio.to_thread(
                self.fetcher.fetch_ohlcv,
                self.symbol,
                self.timeframe,
                limit=100
            )

            if df is None or df.empty:
                return {}

            # Calculate indicators
            close = df['close'].values
            high = df['high'].values
            low = df['low'].values

            # 1. Trend Analysis (EMA crossover)
            ema_fast = self._ema(close, 9)
            ema_slow = self._ema(close, 21)

            if ema_fast[-1] > ema_slow[-1] and ema_fast[-2] <= ema_slow[-2]:
                score += 5
                signals.append('EMA bullish cross')
                direction = 'long'
            elif ema_fast[-1] < ema_slow[-1] and ema_fast[-2] >= ema_slow[-2]:
                score += 5
                signals.append('EMA bearish cross')
                direction = 'short'
            elif ema_fast[-1] > ema_slow[-1]:
                score += 2
                direction = direction or 'long'
            elif ema_fast[-1] < ema_slow[-1]:
                score += 2
                direction = direction or 'short'

            # 2. RSI
            rsi = self._rsi(close, 14)
            if rsi[-1] < 30:
                score += 4
                signals.append('RSI oversold')
                direction = direction or 'long'
            elif rsi[-1] > 70:
                score += 4
                signals.append('RSI overbought')
                direction = direction or 'short'
            elif 40 < rsi[-1] < 60:
                score += 2
                signals.append('RSI neutral')

            # 3. MACD
            macd_line, signal_line, histogram = self._macd(close)
            if histogram[-1] > 0 and histogram[-2] <= 0:
                score += 4
                signals.append('MACD bullish')
                direction = direction or 'long'
            elif histogram[-1] < 0 and histogram[-2] >= 0:
                score += 4
                signals.append('MACD bearish')
                direction = direction or 'short'

            # 4. Support/Resistance
            recent_high = max(high[-20:])
            recent_low = min(low[-20:])
            current = close[-1]

            if current <= recent_low * 1.02:
                score += 3
                signals.append('Near support')
                direction = direction or 'long'
            elif current >= recent_high * 0.98:
                score += 3
                signals.append('Near resistance')
                direction = direction or 'short'

            # 5. Volume confirmation
            volume = df['volume'].values
            avg_volume = sum(volume[-20:]) / 20
            if volume[-1] > avg_volume * 1.5:
                score += 3
                signals.append('High volume')

            # 6. ML prediction if available
            if self.ml_strategy:
                try:
                    prediction = self.ml_strategy.predict(df)
                    if prediction:
                        ml_direction = prediction.get('direction')
                        ml_confidence = prediction.get('confidence', 0)
                        if ml_direction and ml_confidence > 0.6:
                            score += 5
                            signals.append(f'ML: {ml_direction}')
                            if not direction:
                                direction = 'long' if ml_direction == 'up' else 'short'
                except:
                    pass

            confidence = min(100, score * 5)

            return {
                'score': score,
                'confidence': confidence,
                'direction': direction or 'hold',
                'signals': signals,
                'reason': ', '.join(signals) if signals else 'No clear signals'
            }

        except Exception as e:
            logger.error(f"Error analyzing market: {e}")
            return {}

    async def _manage_position(self, current_price: float):
        """Manage open position."""
        if not self.position:
            return

        pos = self.position

        # Update unrealized P&L
        if pos.side == 'long':
            pos.unrealized_pnl = (current_price - pos.entry_price) * pos.size

            # Check stop loss
            if current_price <= pos.stop_loss:
                await self._close_position(current_price, 'stop_loss')
                return

            # Check take profit
            if current_price >= pos.take_profit:
                await self._close_position(current_price, 'take_profit')
                return
        else:
            pos.unrealized_pnl = (pos.entry_price - current_price) * pos.size

            if current_price >= pos.stop_loss:
                await self._close_position(current_price, 'stop_loss')
                return

            if current_price <= pos.take_profit:
                await self._close_position(current_price, 'take_profit')
                return

        # Trailing stop for profitable positions
        profit_pct = abs(pos.unrealized_pnl / (pos.entry_price * pos.size))
        if profit_pct > 0.01:  # More than 1% profit
            if pos.side == 'long':
                new_stop = max(pos.stop_loss, current_price * 0.995)
                if new_stop > pos.stop_loss:
                    pos.stop_loss = new_stop
            else:
                new_stop = min(pos.stop_loss, current_price * 1.005)
                if new_stop < pos.stop_loss:
                    pos.stop_loss = new_stop

    def _ema(self, data, period):
        """Calculate EMA."""
        import numpy as np
        ema = np.zeros_like(data)
        ema[0] = data[0]
        multiplier = 2 / (period + 1)
        for i in range(1, len(data)):
            ema[i] = (data[i] * multiplier) + (ema[i-1] * (1 - multiplier))
        return ema

    def _rsi(self, data, period=14):
        """Calculate RSI."""
        import numpy as np
        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.zeros_like(data)
        avg_loss = np.zeros_like(data)

        avg_gain[period] = np.mean(gains[:period])
        avg_loss[period] = np.mean(losses[:period])

        for i in range(period + 1, len(data)):
            avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i-1]) / period
            avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i-1]) / period

        rs = np.where(avg_loss != 0, avg_gain / avg_loss, 0)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _macd(self, data, fast=12, slow=26, signal=9):
        """Calculate MACD."""
        ema_fast = self._ema(data, fast)
        ema_slow = self._ema(data, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self._ema(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram


class SwingTradingBot(BaseTradingBot):
    """
    Swing Trading Bot.

    Targets multi-day to weekly positions (3-14 days).
    Uses Daily/Weekly timeframes with 5-15% profit targets.
    """

    def __init__(self, exchange, fetcher, storage, config=None, ml_strategy=None):
        super().__init__(exchange, fetcher, storage, config, ml_strategy)

        self.bot_type = BotType.SWING

        # Load preset
        trading_mode = self.config.get('trading_mode', 'medium')
        preset = SWING_PRESETS.get(trading_mode, SWING_PRESETS['medium'])

        self.timeframe = preset['timeframe']
        self.check_interval = preset['check_interval']
        self.take_profit_pct = self.config.get('take_profit_pct', preset['take_profit_pct'])
        self.stop_loss_pct = self.config.get('stop_loss_pct', preset['stop_loss_pct'])
        self.min_confluence_score = self.config.get('min_confluence_score', preset['min_confluence_score'])
        self.min_confidence = self.config.get('min_confidence', preset['min_confidence'])

        # Swing-specific
        self.cooldown_period = 86400  # 24 hours between trades
        self.risk_per_trade = 0.03  # 3% risk for swing trades

    async def _trading_loop(self):
        """Main trading loop for swing strategy."""
        # Check cooldown
        if self.last_trade_time:
            elapsed = (datetime.now() - self.last_trade_time).total_seconds()
            if elapsed < self.cooldown_period:
                return

        # Get current price
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            current_price = ticker['last']
        except Exception as e:
            logger.error(f"Failed to fetch ticker: {e}")
            return

        # Check position management
        if self.position:
            await self._manage_position(current_price)
            return

        # Analyze market
        signal = await self._analyze_market()
        self.last_signal = signal

        # Check entry conditions
        if signal and signal.get('score', 0) >= self.min_confluence_score:
            if signal.get('confidence', 0) >= self.min_confidence:
                signal['price'] = current_price
                await self._open_position(signal)

    async def _analyze_market(self) -> Dict:
        """Analyze market for swing signals."""
        score = 0
        signals = []
        direction = None

        try:
            # Fetch daily data
            df = await asyncio.to_thread(
                self.fetcher.fetch_ohlcv,
                self.symbol,
                self.timeframe,
                limit=100
            )

            if df is None or df.empty:
                return {}

            close = df['close'].values
            high = df['high'].values
            low = df['low'].values

            # 1. Long-term trend (50 EMA vs 200 EMA)
            ema_50 = self._ema(close, 50) if len(close) >= 50 else self._ema(close, len(close)//2)
            ema_200 = self._ema(close, min(200, len(close)-1))

            if ema_50[-1] > ema_200[-1]:
                score += 4
                signals.append('Uptrend (EMA50>200)')
                direction = 'long'
            else:
                score += 4
                signals.append('Downtrend (EMA50<200)')
                direction = 'short'

            # 2. Weekly RSI
            rsi = self._rsi(close, 14)
            if rsi[-1] < 35:
                score += 5
                signals.append('Weekly RSI oversold')
                direction = 'long'
            elif rsi[-1] > 65:
                score += 5
                signals.append('Weekly RSI overbought')
                direction = 'short'

            # 3. Key levels
            all_time_high = max(high)
            all_time_low = min(low)
            current = close[-1]
            range_pct = (current - all_time_low) / (all_time_high - all_time_low)

            if range_pct < 0.3:
                score += 4
                signals.append('Near range lows')
                direction = direction or 'long'
            elif range_pct > 0.7:
                score += 4
                signals.append('Near range highs')
                direction = direction or 'short'

            # 4. Volume trend
            volume = df['volume'].values
            vol_ma = sum(volume[-20:]) / 20
            recent_vol_ma = sum(volume[-5:]) / 5

            if recent_vol_ma > vol_ma * 1.3:
                score += 3
                signals.append('Rising volume')

            # 5. Price structure
            higher_highs = high[-1] > high[-2] > high[-3]
            higher_lows = low[-1] > low[-2] > low[-3]
            lower_highs = high[-1] < high[-2] < high[-3]
            lower_lows = low[-1] < low[-2] < low[-3]

            if higher_highs and higher_lows:
                score += 4
                signals.append('Bullish structure')
                direction = 'long'
            elif lower_highs and lower_lows:
                score += 4
                signals.append('Bearish structure')
                direction = 'short'

            # 6. ML prediction
            if self.ml_strategy:
                try:
                    prediction = self.ml_strategy.predict(df)
                    if prediction:
                        ml_confidence = prediction.get('confidence', 0)
                        if ml_confidence > 0.65:
                            score += 6
                            signals.append(f'Strong ML signal')
                except:
                    pass

            confidence = min(100, score * 4)

            return {
                'score': score,
                'confidence': confidence,
                'direction': direction or 'hold',
                'signals': signals,
                'reason': ', '.join(signals) if signals else 'No clear signals'
            }

        except Exception as e:
            logger.error(f"Error analyzing market: {e}")
            return {}

    async def _manage_position(self, current_price: float):
        """Manage open position with wider stops for swing trades."""
        if not self.position:
            return

        pos = self.position

        if pos.side == 'long':
            pos.unrealized_pnl = (current_price - pos.entry_price) * pos.size

            if current_price <= pos.stop_loss:
                await self._close_position(current_price, 'stop_loss')
                return

            if current_price >= pos.take_profit:
                await self._close_position(current_price, 'take_profit')
                return

            # Scale out at 50% of target
            half_target = pos.entry_price * (1 + self.take_profit_pct / 2)
            if current_price >= half_target and pos.size > 0.5:
                # Could implement partial close here
                pass
        else:
            pos.unrealized_pnl = (pos.entry_price - current_price) * pos.size

            if current_price >= pos.stop_loss:
                await self._close_position(current_price, 'stop_loss')
                return

            if current_price <= pos.take_profit:
                await self._close_position(current_price, 'take_profit')
                return

    def _ema(self, data, period):
        import numpy as np
        ema = np.zeros_like(data)
        ema[0] = data[0]
        multiplier = 2 / (period + 1)
        for i in range(1, len(data)):
            ema[i] = (data[i] * multiplier) + (ema[i-1] * (1 - multiplier))
        return ema

    def _rsi(self, data, period=14):
        import numpy as np
        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.zeros_like(data)
        avg_loss = np.zeros_like(data)

        avg_gain[period] = np.mean(gains[:period])
        avg_loss[period] = np.mean(losses[:period])

        for i in range(period + 1, len(data)):
            avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i-1]) / period
            avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i-1]) / period

        rs = np.where(avg_loss != 0, avg_gain / avg_loss, 0)
        rsi = 100 - (100 / (1 + rs))
        return rsi


class LongTermBot(BaseTradingBot):
    """
    Long Term Investment Bot.

    Targets position trading and DCA strategies (weeks to months).
    Uses Weekly/Monthly timeframes with 20%+ profit targets.
    """

    def __init__(self, exchange, fetcher, storage, config=None, ml_strategy=None):
        super().__init__(exchange, fetcher, storage, config, ml_strategy)

        self.bot_type = BotType.LONG_TERM

        # Load preset
        trading_mode = self.config.get('trading_mode', 'medium')
        preset = LONG_TERM_PRESETS.get(trading_mode, LONG_TERM_PRESETS['medium'])

        self.timeframe = preset['timeframe']
        self.check_interval = preset['check_interval']
        self.take_profit_pct = self.config.get('take_profit_pct', preset['take_profit_pct'])
        self.stop_loss_pct = self.config.get('stop_loss_pct', preset['stop_loss_pct'])
        self.min_confluence_score = self.config.get('min_confluence_score', preset['min_confluence_score'])
        self.min_confidence = self.config.get('min_confidence', preset['min_confidence'])

        # Long-term specific
        self.dca_enabled = preset.get('dca_enabled', True)
        self.dca_threshold = preset.get('dca_threshold', -0.08)
        self.dca_positions: List[Position] = []
        self.max_dca_count = 3
        self.cooldown_period = 604800  # 7 days between trades
        self.risk_per_trade = 0.05  # 5% allocation per position

    async def _trading_loop(self):
        """Main trading loop for long-term strategy."""
        # Get current price
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            current_price = ticker['last']
        except Exception as e:
            logger.error(f"Failed to fetch ticker: {e}")
            return

        # Check DCA opportunities first
        if self.dca_enabled and self.position:
            await self._check_dca(current_price)

        # Check position management
        if self.position:
            await self._manage_position(current_price)
            return

        # Check cooldown for new positions
        if self.last_trade_time:
            elapsed = (datetime.now() - self.last_trade_time).total_seconds()
            if elapsed < self.cooldown_period:
                return

        # Analyze market
        signal = await self._analyze_market()
        self.last_signal = signal

        # Check entry conditions (more stringent for long-term)
        if signal and signal.get('score', 0) >= self.min_confluence_score:
            if signal.get('confidence', 0) >= self.min_confidence:
                signal['price'] = current_price
                await self._open_position(signal)

    async def _analyze_market(self) -> Dict:
        """Analyze market for long-term signals."""
        score = 0
        signals = []
        direction = None

        try:
            # Fetch weekly data
            df = await asyncio.to_thread(
                self.fetcher.fetch_ohlcv,
                self.symbol,
                '1d',  # Use daily for more data points
                limit=365
            )

            if df is None or df.empty:
                return {}

            close = df['close'].values
            high = df['high'].values
            low = df['low'].values

            # 1. Macro trend (200 SMA)
            sma_200 = sum(close[-200:]) / min(200, len(close)) if len(close) >= 50 else close[-1]

            if close[-1] > sma_200:
                score += 5
                signals.append('Above 200 SMA (bullish)')
                direction = 'long'
            else:
                score += 3
                signals.append('Below 200 SMA (cautious)')

            # 2. Distance from ATH
            ath = max(high)
            distance_from_ath = (ath - close[-1]) / ath * 100

            if distance_from_ath > 50:
                score += 6
                signals.append(f'{distance_from_ath:.0f}% below ATH (value zone)')
                direction = 'long'
            elif distance_from_ath > 30:
                score += 4
                signals.append(f'{distance_from_ath:.0f}% below ATH')
                direction = 'long'
            elif distance_from_ath < 10:
                score += 2
                signals.append('Near ATH (reduced allocation)')

            # 3. Monthly RSI
            rsi = self._rsi(close, 14)
            monthly_rsi = rsi[-1]

            if monthly_rsi < 30:
                score += 6
                signals.append('Monthly RSI extremely oversold')
                direction = 'long'
            elif monthly_rsi < 40:
                score += 4
                signals.append('Monthly RSI oversold')
                direction = 'long'
            elif monthly_rsi > 80:
                score += 2
                signals.append('Monthly RSI overbought (caution)')

            # 4. Accumulation pattern
            recent_range = max(high[-30:]) - min(low[-30:])
            prev_range = max(high[-60:-30]) - min(low[-60:-30]) if len(close) > 60 else recent_range

            if recent_range < prev_range * 0.7:
                score += 4
                signals.append('Consolidation (accumulation)')

            # 5. Volume analysis
            volume = df['volume'].values
            recent_vol = sum(volume[-30:]) / 30
            prev_vol = sum(volume[-90:-30]) / 60 if len(volume) > 90 else recent_vol

            if recent_vol > prev_vol * 1.2:
                score += 3
                signals.append('Increasing volume')

            # 6. Halving cycle (crypto specific)
            # This is a placeholder - in real implementation would track halving dates
            score += 2
            signals.append('Cycle analysis')

            confidence = min(100, score * 3.5)

            return {
                'score': score,
                'confidence': confidence,
                'direction': direction or 'long',  # Long-term is generally long-biased
                'signals': signals,
                'reason': ', '.join(signals) if signals else 'No clear signals'
            }

        except Exception as e:
            logger.error(f"Error analyzing market: {e}")
            return {}

    async def _check_dca(self, current_price: float):
        """Check if DCA (Dollar Cost Averaging) opportunity."""
        if not self.position or len(self.dca_positions) >= self.max_dca_count:
            return

        pos = self.position

        # Calculate current loss percentage
        if pos.side == 'long':
            loss_pct = (current_price - pos.entry_price) / pos.entry_price
        else:
            loss_pct = (pos.entry_price - current_price) / pos.entry_price

        # DCA if down more than threshold
        if loss_pct <= self.dca_threshold:
            # Check cooldown from last DCA
            if self.dca_positions:
                last_dca = self.dca_positions[-1]
                elapsed = (datetime.now() - last_dca.entry_time).total_seconds()
                if elapsed < 86400:  # 24 hours minimum between DCA
                    return

            # Add DCA position
            risk_amount = self.capital * self.risk_per_trade
            stop_distance = current_price * self.stop_loss_pct
            size = risk_amount / stop_distance

            dca_position = Position(
                id=str(uuid.uuid4())[:8],
                symbol=self.symbol,
                side=pos.side,
                entry_price=current_price,
                size=size,
                stop_loss=pos.stop_loss,
                take_profit=pos.take_profit,
                entry_time=datetime.now(),
                bot_type=self.bot_type.value
            )

            self.dca_positions.append(dca_position)

            # Update main position with average price
            total_size = pos.size + size
            avg_price = (pos.entry_price * pos.size + current_price * size) / total_size
            pos.entry_price = avg_price
            pos.size = total_size

            logger.info(f"DCA: Added position at {current_price:.2f}, new avg: {avg_price:.2f}")

    async def _manage_position(self, current_price: float):
        """Manage open position for long-term holds."""
        if not self.position:
            return

        pos = self.position

        if pos.side == 'long':
            pos.unrealized_pnl = (current_price - pos.entry_price) * pos.size

            # Wider stops for long-term
            if current_price <= pos.stop_loss:
                await self._close_position(current_price, 'stop_loss')
                self.dca_positions.clear()
                return

            if current_price >= pos.take_profit:
                await self._close_position(current_price, 'take_profit')
                self.dca_positions.clear()
                return

            # Move stop to break-even at 15% profit
            profit_pct = (current_price - pos.entry_price) / pos.entry_price
            if profit_pct >= 0.15:
                be_stop = pos.entry_price * 1.02  # 2% above entry
                if be_stop > pos.stop_loss:
                    pos.stop_loss = be_stop
                    logger.info(f"Moved stop to break-even: {be_stop:.2f}")
        else:
            pos.unrealized_pnl = (pos.entry_price - current_price) * pos.size

            if current_price >= pos.stop_loss:
                await self._close_position(current_price, 'stop_loss')
                self.dca_positions.clear()
                return

            if current_price <= pos.take_profit:
                await self._close_position(current_price, 'take_profit')
                self.dca_positions.clear()
                return

    def _ema(self, data, period):
        import numpy as np
        ema = np.zeros_like(data)
        ema[0] = data[0]
        multiplier = 2 / (period + 1)
        for i in range(1, len(data)):
            ema[i] = (data[i] * multiplier) + (ema[i-1] * (1 - multiplier))
        return ema

    def _rsi(self, data, period=14):
        import numpy as np
        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.zeros_like(data)
        avg_loss = np.zeros_like(data)

        avg_gain[period] = np.mean(gains[:period])
        avg_loss[period] = np.mean(losses[:period])

        for i in range(period + 1, len(data)):
            avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i-1]) / period
            avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i-1]) / period

        rs = np.where(avg_loss != 0, avg_gain / avg_loss, 0)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def get_status(self) -> Dict:
        """Get current bot status with DCA info."""
        status = super().get_status()
        status['dca_count'] = len(self.dca_positions)
        status['dca_enabled'] = self.dca_enabled
        return status
