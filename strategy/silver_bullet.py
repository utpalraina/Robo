"""
ICT Silver Bullet Strategy

The Silver Bullet strategy focuses on high-probability setups during specific
1-hour windows during the NY session:
- AM Silver Bullet: 10:00 AM - 11:00 AM EST
- PM Silver Bullet: 2:00 PM - 3:00 PM EST

Entry Conditions:
1. Within Silver Bullet time window
2. Liquidity has been swept (PDH/PDL, Asian High/Low, or equal highs/lows)
3. Market Structure Shift (MSS) on lower timeframe
4. Price returns to FVG or Order Block
5. Minimum 3:1 Risk/Reward

Target: -27% or -62% Fibonacci extension from the swing
Stop: Beyond the liquidity level that was swept
"""

import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import pytz


class SilverBulletWindow(Enum):
    """Silver Bullet time windows"""
    AM = "am"  # 10:00 AM - 11:00 AM EST
    PM = "pm"  # 2:00 PM - 3:00 PM EST
    NONE = "none"


class SilverBulletSignal(Enum):
    """Silver Bullet signal types"""
    LONG = "long"
    SHORT = "short"
    NO_SETUP = "no_setup"


@dataclass
class LiquiditySweep:
    """Represents a liquidity sweep event"""
    sweep_type: str  # 'pdh', 'pdl', 'asian_high', 'asian_low', 'equal_highs', 'equal_lows'
    level: float
    sweep_price: float
    sweep_time: datetime
    direction: str  # 'bullish' (swept lows) or 'bearish' (swept highs)


@dataclass
class SilverBulletSetup:
    """Complete Silver Bullet setup"""
    window: SilverBulletWindow
    signal: SilverBulletSignal
    confidence: float

    # Liquidity sweep info
    liquidity_sweep: Optional[LiquiditySweep]

    # MSS info
    mss_confirmed: bool
    mss_direction: str  # 'bullish' or 'bearish'
    mss_level: Optional[float]

    # Entry zone
    entry_zone_type: str  # 'fvg', 'order_block', 'ote'
    entry_zone_top: float
    entry_zone_bottom: float
    optimal_entry: float

    # Risk management
    stop_loss: float
    take_profit_1: float  # -27% extension
    take_profit_2: float  # -62% extension
    risk_reward: float

    # Additional info
    current_price: float
    timestamp: datetime
    reasons: List[str]


class SilverBulletStrategy:
    """
    ICT Silver Bullet Strategy Implementation

    Looks for high-probability setups during the Silver Bullet windows
    based on liquidity sweeps, MSS, and optimal entry zones.
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize Silver Bullet Strategy

        Args:
            config: Optional configuration parameters
        """
        self.config = config or {}

        # Time windows (EST)
        self.am_start = time(10, 0)  # 10:00 AM
        self.am_end = time(11, 0)    # 11:00 AM
        self.pm_start = time(14, 0)  # 2:00 PM
        self.pm_end = time(15, 0)    # 3:00 PM

        # Strategy parameters
        self.min_rr = self.config.get('min_risk_reward', 3.0)
        self.lookback_candles = self.config.get('lookback_candles', 50)
        self.sweep_threshold_pct = self.config.get('sweep_threshold_pct', 0.1)  # 0.1% beyond level
        self.fvg_min_size_pct = self.config.get('fvg_min_size_pct', 0.05)

        # Timezone
        self.est_tz = pytz.timezone('America/New_York')

    def get_current_window(self, timestamp: Optional[datetime] = None) -> SilverBulletWindow:
        """
        Determine if we're in a Silver Bullet window

        Args:
            timestamp: Timestamp to check (default: now)

        Returns:
            SilverBulletWindow enum value
        """
        if timestamp is None:
            timestamp = datetime.now(self.est_tz)
        elif timestamp.tzinfo is None:
            timestamp = self.est_tz.localize(timestamp)
        else:
            timestamp = timestamp.astimezone(self.est_tz)

        current_time = timestamp.time()

        if self.am_start <= current_time < self.am_end:
            return SilverBulletWindow.AM
        elif self.pm_start <= current_time < self.pm_end:
            return SilverBulletWindow.PM
        else:
            return SilverBulletWindow.NONE

    def get_time_until_next_window(self, timestamp: Optional[datetime] = None) -> Tuple[SilverBulletWindow, timedelta]:
        """
        Get time until next Silver Bullet window

        Returns:
            Tuple of (next_window, time_until)
        """
        if timestamp is None:
            timestamp = datetime.now(self.est_tz)
        elif timestamp.tzinfo is None:
            timestamp = self.est_tz.localize(timestamp)
        else:
            timestamp = timestamp.astimezone(self.est_tz)

        current_time = timestamp.time()
        today = timestamp.date()

        # Calculate next windows
        next_am_start = datetime.combine(today, self.am_start)
        next_am_start = self.est_tz.localize(next_am_start)

        next_pm_start = datetime.combine(today, self.pm_start)
        next_pm_start = self.est_tz.localize(next_pm_start)

        # If past PM window, next is tomorrow's AM
        if current_time >= self.pm_end:
            next_am_start += timedelta(days=1)
            next_pm_start += timedelta(days=1)
        # If past AM but before PM
        elif current_time >= self.am_end and current_time < self.pm_start:
            pass  # PM is today

        # Determine which is closer
        if next_am_start < next_pm_start and next_am_start > timestamp:
            return SilverBulletWindow.AM, next_am_start - timestamp
        elif next_pm_start > timestamp:
            return SilverBulletWindow.PM, next_pm_start - timestamp
        else:
            next_am_start += timedelta(days=1)
            return SilverBulletWindow.AM, next_am_start - timestamp

    def identify_liquidity_levels(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Identify key liquidity levels that could be swept

        Args:
            df: OHLCV DataFrame with at least 2 days of data

        Returns:
            Dictionary of liquidity levels
        """
        levels = {}

        if len(df) < 24:  # Need at least some data
            return levels

        # Convert index to datetime if needed
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        # Ensure timezone aware
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')

        df_est = df.copy()
        df_est.index = df_est.index.tz_convert(self.est_tz)

        # Get today and yesterday
        latest = df_est.index[-1]
        today = latest.date()
        yesterday = today - timedelta(days=1)

        # Previous Day High/Low
        yesterday_data = df_est[df_est.index.date == yesterday]
        if len(yesterday_data) > 0:
            levels['pdh'] = yesterday_data['high'].max()
            levels['pdl'] = yesterday_data['low'].min()

        # Asian Session High/Low (7 PM - 4 AM EST previous day to today)
        asian_start = datetime.combine(yesterday, time(19, 0))
        asian_end = datetime.combine(today, time(4, 0))
        asian_start = self.est_tz.localize(asian_start)
        asian_end = self.est_tz.localize(asian_end)

        asian_data = df_est[(df_est.index >= asian_start) & (df_est.index < asian_end)]
        if len(asian_data) > 0:
            levels['asian_high'] = asian_data['high'].max()
            levels['asian_low'] = asian_data['low'].min()

        # Equal Highs/Lows (recent swing points)
        levels['equal_highs'] = self._find_equal_levels(df_est, 'high')
        levels['equal_lows'] = self._find_equal_levels(df_est, 'low')

        # London Session High/Low (3 AM - 8:30 AM EST)
        london_start = datetime.combine(today, time(3, 0))
        london_end = datetime.combine(today, time(8, 30))
        london_start = self.est_tz.localize(london_start)
        london_end = self.est_tz.localize(london_end)

        london_data = df_est[(df_est.index >= london_start) & (df_est.index < london_end)]
        if len(london_data) > 0:
            levels['london_high'] = london_data['high'].max()
            levels['london_low'] = london_data['low'].min()

        return levels

    def _find_equal_levels(self, df: pd.DataFrame, price_type: str,
                          tolerance_pct: float = 0.05, min_touches: int = 2) -> Optional[float]:
        """
        Find equal highs or equal lows (liquidity pools)

        Args:
            df: OHLCV DataFrame
            price_type: 'high' or 'low'
            tolerance_pct: Percentage tolerance for considering levels "equal"
            min_touches: Minimum touches to consider it a valid level

        Returns:
            Price level of equal highs/lows or None
        """
        # Get swing points
        lookback = min(20, len(df) - 1)
        swing_points = []

        prices = df[price_type].values

        for i in range(lookback, len(df) - 1):
            if price_type == 'high':
                # Swing high: higher than surrounding
                if prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                    swing_points.append(prices[i])
            else:
                # Swing low: lower than surrounding
                if prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                    swing_points.append(prices[i])

        if len(swing_points) < min_touches:
            return None

        # Find levels with multiple touches
        swing_points = sorted(swing_points, reverse=(price_type == 'high'))

        for level in swing_points[:10]:  # Check top 10
            tolerance = level * tolerance_pct / 100
            touches = sum(1 for p in swing_points if abs(p - level) <= tolerance)
            if touches >= min_touches:
                return level

        return None

    def detect_liquidity_sweep(self, df: pd.DataFrame,
                               liquidity_levels: Dict[str, float]) -> Optional[LiquiditySweep]:
        """
        Detect if liquidity has been swept

        Args:
            df: OHLCV DataFrame
            liquidity_levels: Dictionary of liquidity levels

        Returns:
            LiquiditySweep object if sweep detected, None otherwise
        """
        if len(df) < 5 or not liquidity_levels:
            return None

        # Check recent candles (last 5)
        recent = df.iloc[-5:]
        current_price = df.iloc[-1]['close']

        # Check for sweeps of each level
        for level_name, level in liquidity_levels.items():
            if level is None:
                continue

            threshold = level * self.sweep_threshold_pct / 100

            # Check if we swept highs (bearish setup potential)
            if 'high' in level_name or level_name in ['pdh', 'asian_high', 'london_high']:
                for i, (_, row) in enumerate(recent.iterrows()):
                    # Swept high and closed back below
                    if row['high'] > level + threshold and row['close'] < level:
                        return LiquiditySweep(
                            sweep_type=level_name,
                            level=level,
                            sweep_price=row['high'],
                            sweep_time=row.name if isinstance(row.name, datetime) else datetime.now(),
                            direction='bearish'
                        )

            # Check if we swept lows (bullish setup potential)
            elif 'low' in level_name or level_name in ['pdl', 'asian_low', 'london_low']:
                for i, (_, row) in enumerate(recent.iterrows()):
                    # Swept low and closed back above
                    if row['low'] < level - threshold and row['close'] > level:
                        return LiquiditySweep(
                            sweep_type=level_name,
                            level=level,
                            sweep_price=row['low'],
                            sweep_time=row.name if isinstance(row.name, datetime) else datetime.now(),
                            direction='bullish'
                        )

        return None

    def detect_mss(self, df: pd.DataFrame, direction: str) -> Tuple[bool, Optional[float]]:
        """
        Detect Market Structure Shift

        Args:
            df: OHLCV DataFrame
            direction: Expected direction ('bullish' or 'bearish')

        Returns:
            Tuple of (mss_confirmed, mss_level)
        """
        if len(df) < 10:
            return False, None

        recent = df.iloc[-20:]  # Look at last 20 candles

        # Find recent swing points
        highs = []
        lows = []

        for i in range(2, len(recent) - 2):
            # Swing high
            if (recent.iloc[i]['high'] > recent.iloc[i-1]['high'] and
                recent.iloc[i]['high'] > recent.iloc[i-2]['high'] and
                recent.iloc[i]['high'] > recent.iloc[i+1]['high'] and
                recent.iloc[i]['high'] > recent.iloc[i+2]['high']):
                highs.append((i, recent.iloc[i]['high']))

            # Swing low
            if (recent.iloc[i]['low'] < recent.iloc[i-1]['low'] and
                recent.iloc[i]['low'] < recent.iloc[i-2]['low'] and
                recent.iloc[i]['low'] < recent.iloc[i+1]['low'] and
                recent.iloc[i]['low'] < recent.iloc[i+2]['low']):
                lows.append((i, recent.iloc[i]['low']))

        current_price = recent.iloc[-1]['close']

        if direction == 'bullish':
            # Looking for break above a recent lower high
            if len(highs) >= 2:
                # Check if we broke above the most recent swing high
                last_high = highs[-1][1]
                if current_price > last_high:
                    return True, last_high

        elif direction == 'bearish':
            # Looking for break below a recent higher low
            if len(lows) >= 2:
                # Check if we broke below the most recent swing low
                last_low = lows[-1][1]
                if current_price < last_low:
                    return True, last_low

        return False, None

    def find_entry_zone(self, df: pd.DataFrame, direction: str,
                       ict_data: Optional[Dict] = None) -> Tuple[str, float, float, float]:
        """
        Find optimal entry zone (FVG, Order Block, or OTE level)

        Args:
            df: OHLCV DataFrame
            direction: Trade direction ('bullish' or 'bearish')
            ict_data: Optional pre-calculated ICT indicator data

        Returns:
            Tuple of (zone_type, top, bottom, optimal_entry)
        """
        current_price = df.iloc[-1]['close']
        atr = self._calculate_atr(df)

        # Try to find FVG first (most precise)
        fvg = self._find_fvg(df, direction)
        if fvg:
            return 'fvg', fvg['top'], fvg['bottom'], (fvg['top'] + fvg['bottom']) / 2

        # Try Order Block
        ob = self._find_order_block(df, direction)
        if ob:
            return 'order_block', ob['high'], ob['low'], (ob['high'] + ob['low']) / 2

        # Fall back to OTE levels
        ote = self._calculate_ote_zone(df, direction)
        if ote:
            return 'ote', ote['entry_top'], ote['entry_bottom'], ote['optimal']

        # Default zone based on ATR
        if direction == 'bullish':
            return 'atr_zone', current_price, current_price - atr, current_price - 0.5 * atr
        else:
            return 'atr_zone', current_price + atr, current_price, current_price + 0.5 * atr

    def _find_fvg(self, df: pd.DataFrame, direction: str) -> Optional[Dict]:
        """Find recent Fair Value Gap"""
        if len(df) < 5:
            return None

        recent = df.iloc[-20:]
        current_price = recent.iloc[-1]['close']

        for i in range(2, len(recent) - 1):
            candle_before = recent.iloc[i-2]
            candle_after = recent.iloc[i]

            if direction == 'bullish':
                # Bullish FVG: gap between candle before's high and candle after's low
                gap_top = candle_after['low']
                gap_bottom = candle_before['high']

                if gap_top > gap_bottom:  # Valid gap
                    gap_size = (gap_top - gap_bottom) / current_price * 100
                    if gap_size >= self.fvg_min_size_pct:
                        # Check if price could reach this zone
                        if current_price > gap_bottom:
                            return {'top': gap_top, 'bottom': gap_bottom, 'type': 'bullish'}

            else:
                # Bearish FVG: gap between candle before's low and candle after's high
                gap_top = candle_before['low']
                gap_bottom = candle_after['high']

                if gap_top > gap_bottom:  # Valid gap
                    gap_size = (gap_top - gap_bottom) / current_price * 100
                    if gap_size >= self.fvg_min_size_pct:
                        # Check if price could reach this zone
                        if current_price < gap_top:
                            return {'top': gap_top, 'bottom': gap_bottom, 'type': 'bearish'}

        return None

    def _find_order_block(self, df: pd.DataFrame, direction: str) -> Optional[Dict]:
        """Find recent Order Block"""
        if len(df) < 10:
            return None

        recent = df.iloc[-30:]
        current_price = recent.iloc[-1]['close']
        avg_volume = recent['volume'].mean()

        for i in range(len(recent) - 3, 1, -1):
            candle = recent.iloc[i]
            next_candle = recent.iloc[i + 1]

            if direction == 'bullish':
                # Bullish OB: Last down candle before strong up move
                if candle['close'] < candle['open']:  # Bearish candle
                    if next_candle['close'] > next_candle['open']:  # Followed by bullish
                        body_size = abs(next_candle['close'] - next_candle['open'])
                        avg_body = abs(recent['close'] - recent['open']).mean()

                        # Strong move with volume
                        if body_size > 1.5 * avg_body and candle['volume'] > avg_volume:
                            if candle['low'] < current_price:  # Zone is below price
                                return {'high': candle['high'], 'low': candle['low'], 'type': 'demand'}

            else:
                # Bearish OB: Last up candle before strong down move
                if candle['close'] > candle['open']:  # Bullish candle
                    if next_candle['close'] < next_candle['open']:  # Followed by bearish
                        body_size = abs(next_candle['close'] - next_candle['open'])
                        avg_body = abs(recent['close'] - recent['open']).mean()

                        # Strong move with volume
                        if body_size > 1.5 * avg_body and candle['volume'] > avg_volume:
                            if candle['high'] > current_price:  # Zone is above price
                                return {'high': candle['high'], 'low': candle['low'], 'type': 'supply'}

        return None

    def _calculate_ote_zone(self, df: pd.DataFrame, direction: str) -> Optional[Dict]:
        """Calculate OTE (Optimal Trade Entry) zone using Fibonacci"""
        if len(df) < 20:
            return None

        recent = df.iloc[-50:]

        # Find swing high and swing low
        swing_high = recent['high'].max()
        swing_low = recent['low'].min()
        swing_range = swing_high - swing_low

        if direction == 'bullish':
            # OTE for buys: 62%-79% retracement from low
            ote_62 = swing_low + 0.62 * swing_range
            ote_705 = swing_low + 0.705 * swing_range
            ote_79 = swing_low + 0.79 * swing_range

            return {
                'entry_top': ote_62,
                'entry_bottom': ote_79,
                'optimal': ote_705,
                'type': 'bullish_ote'
            }
        else:
            # OTE for sells: 62%-79% retracement from high
            ote_62 = swing_high - 0.62 * swing_range
            ote_705 = swing_high - 0.705 * swing_range
            ote_79 = swing_high - 0.79 * swing_range

            return {
                'entry_top': ote_79,
                'entry_bottom': ote_62,
                'optimal': ote_705,
                'type': 'bearish_ote'
            }

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(df) < period:
            return abs(df['high'].iloc[-1] - df['low'].iloc[-1])

        high = df['high'].values
        low = df['low'].values
        close = df['close'].values

        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1])
            )
        )

        return np.mean(tr[-period:])

    def calculate_targets(self, entry: float, stop_loss: float,
                         direction: str) -> Tuple[float, float]:
        """
        Calculate take profit targets using Fibonacci extensions

        Args:
            entry: Entry price
            stop_loss: Stop loss price
            direction: Trade direction

        Returns:
            Tuple of (tp1, tp2) - -27% and -62% extensions
        """
        risk = abs(entry - stop_loss)

        if direction == 'bullish':
            tp1 = entry + (risk * 1.27)   # -27% extension = 1.27R
            tp2 = entry + (risk * 1.62)   # -62% extension = 1.62R
        else:
            tp1 = entry - (risk * 1.27)
            tp2 = entry - (risk * 1.62)

        return tp1, tp2

    def analyze(self, df: pd.DataFrame,
                timestamp: Optional[datetime] = None,
                ict_data: Optional[Dict] = None) -> SilverBulletSetup:
        """
        Analyze current market for Silver Bullet setup

        Args:
            df: OHLCV DataFrame (5-minute recommended)
            timestamp: Current timestamp (optional)
            ict_data: Pre-calculated ICT indicator data (optional)

        Returns:
            SilverBulletSetup with complete analysis
        """
        # Check if we're in a Silver Bullet window
        window = self.get_current_window(timestamp)

        # Get current price
        current_price = df.iloc[-1]['close']

        # Default setup (no trade)
        default_setup = SilverBulletSetup(
            window=window,
            signal=SilverBulletSignal.NO_SETUP,
            confidence=0.0,
            liquidity_sweep=None,
            mss_confirmed=False,
            mss_direction='none',
            mss_level=None,
            entry_zone_type='none',
            entry_zone_top=current_price,
            entry_zone_bottom=current_price,
            optimal_entry=current_price,
            stop_loss=current_price,
            take_profit_1=current_price,
            take_profit_2=current_price,
            risk_reward=0.0,
            current_price=current_price,
            timestamp=timestamp or datetime.now(self.est_tz),
            reasons=['Not in Silver Bullet window'] if window == SilverBulletWindow.NONE else []
        )

        # If not in Silver Bullet window, return no setup
        if window == SilverBulletWindow.NONE:
            return default_setup

        reasons = []
        confidence = 0.0

        # Step 1: Identify liquidity levels
        liquidity_levels = self.identify_liquidity_levels(df)

        if not liquidity_levels:
            default_setup.reasons = ['Could not identify liquidity levels']
            return default_setup

        # Step 2: Check for liquidity sweep
        sweep = self.detect_liquidity_sweep(df, liquidity_levels)

        if not sweep:
            default_setup.reasons = ['No liquidity sweep detected']
            return default_setup

        reasons.append(f"Liquidity swept: {sweep.sweep_type} at ${sweep.level:.2f}")
        confidence += 25.0

        # Step 3: Check for MSS in direction of sweep
        mss_confirmed, mss_level = self.detect_mss(df, sweep.direction)

        if not mss_confirmed:
            default_setup.liquidity_sweep = sweep
            default_setup.reasons = ['Liquidity swept but no MSS confirmed']
            default_setup.confidence = confidence
            return default_setup

        reasons.append(f"MSS confirmed {sweep.direction} at ${mss_level:.2f}")
        confidence += 25.0

        # Step 4: Find entry zone
        zone_type, zone_top, zone_bottom, optimal_entry = self.find_entry_zone(
            df, sweep.direction, ict_data
        )
        reasons.append(f"Entry zone: {zone_type}")
        confidence += 15.0

        # Step 5: Calculate stop loss
        atr = self._calculate_atr(df)
        if sweep.direction == 'bullish':
            # Stop below the swept low
            stop_loss = sweep.sweep_price - (0.5 * atr)
        else:
            # Stop above the swept high
            stop_loss = sweep.sweep_price + (0.5 * atr)

        # Step 6: Calculate targets
        tp1, tp2 = self.calculate_targets(optimal_entry, stop_loss, sweep.direction)

        # Step 7: Calculate risk/reward
        risk = abs(optimal_entry - stop_loss)
        reward = abs(tp1 - optimal_entry)
        risk_reward = reward / risk if risk > 0 else 0

        # Check minimum R:R
        if risk_reward < self.min_rr:
            reasons.append(f"R:R {risk_reward:.1f} below minimum {self.min_rr}")
            return SilverBulletSetup(
                window=window,
                signal=SilverBulletSignal.NO_SETUP,
                confidence=confidence,
                liquidity_sweep=sweep,
                mss_confirmed=True,
                mss_direction=sweep.direction,
                mss_level=mss_level,
                entry_zone_type=zone_type,
                entry_zone_top=zone_top,
                entry_zone_bottom=zone_bottom,
                optimal_entry=optimal_entry,
                stop_loss=stop_loss,
                take_profit_1=tp1,
                take_profit_2=tp2,
                risk_reward=risk_reward,
                current_price=current_price,
                timestamp=timestamp or datetime.now(self.est_tz),
                reasons=reasons
            )

        reasons.append(f"R:R ratio: {risk_reward:.1f}")
        confidence += 20.0

        # Step 8: Bonus confidence for window type
        if window == SilverBulletWindow.AM:
            reasons.append("AM Silver Bullet (higher probability)")
            confidence += 15.0
        else:
            reasons.append("PM Silver Bullet")
            confidence += 10.0

        # Determine signal
        signal = SilverBulletSignal.LONG if sweep.direction == 'bullish' else SilverBulletSignal.SHORT

        return SilverBulletSetup(
            window=window,
            signal=signal,
            confidence=min(confidence, 100.0),
            liquidity_sweep=sweep,
            mss_confirmed=True,
            mss_direction=sweep.direction,
            mss_level=mss_level,
            entry_zone_type=zone_type,
            entry_zone_top=zone_top,
            entry_zone_bottom=zone_bottom,
            optimal_entry=optimal_entry,
            stop_loss=stop_loss,
            take_profit_1=tp1,
            take_profit_2=tp2,
            risk_reward=risk_reward,
            current_price=current_price,
            timestamp=timestamp or datetime.now(self.est_tz),
            reasons=reasons
        )

    def to_dict(self, setup: SilverBulletSetup) -> Dict[str, Any]:
        """Convert SilverBulletSetup to dictionary for API response"""
        return {
            'window': setup.window.value,
            'signal': setup.signal.value,
            'confidence': setup.confidence,
            'liquidity_sweep': {
                'type': setup.liquidity_sweep.sweep_type,
                'level': setup.liquidity_sweep.level,
                'sweep_price': setup.liquidity_sweep.sweep_price,
                'direction': setup.liquidity_sweep.direction
            } if setup.liquidity_sweep else None,
            'mss': {
                'confirmed': setup.mss_confirmed,
                'direction': setup.mss_direction,
                'level': setup.mss_level
            },
            'entry_zone': {
                'type': setup.entry_zone_type,
                'top': setup.entry_zone_top,
                'bottom': setup.entry_zone_bottom,
                'optimal': setup.optimal_entry
            },
            'risk_management': {
                'entry': setup.optimal_entry,
                'stop_loss': setup.stop_loss,
                'take_profit_1': setup.take_profit_1,
                'take_profit_2': setup.take_profit_2,
                'risk_reward': setup.risk_reward
            },
            'current_price': setup.current_price,
            'timestamp': setup.timestamp.isoformat() if setup.timestamp else None,
            'reasons': setup.reasons
        }


# Example usage
if __name__ == "__main__":
    # Create sample data for testing
    np.random.seed(42)

    # Generate sample OHLCV data
    dates = pd.date_range(start='2024-01-01', periods=200, freq='5min')
    base_price = 100000

    data = []
    price = base_price
    for date in dates:
        change = np.random.randn() * 100
        open_price = price
        high_price = price + abs(np.random.randn() * 50)
        low_price = price - abs(np.random.randn() * 50)
        close_price = price + change
        volume = np.random.randint(100, 1000)

        data.append({
            'open': open_price,
            'high': max(high_price, open_price, close_price),
            'low': min(low_price, open_price, close_price),
            'close': close_price,
            'volume': volume
        })
        price = close_price

    df = pd.DataFrame(data, index=dates)

    # Test the strategy
    strategy = SilverBulletStrategy()

    # Check current window
    print(f"Current Window: {strategy.get_current_window()}")

    # Get time until next window
    next_window, time_until = strategy.get_time_until_next_window()
    print(f"Next Window: {next_window.value} in {time_until}")

    # Identify liquidity levels
    levels = strategy.identify_liquidity_levels(df)
    print(f"\nLiquidity Levels:")
    for name, level in levels.items():
        if level:
            print(f"  {name}: ${level:.2f}")

    # Analyze for setup
    setup = strategy.analyze(df)
    print(f"\nSilver Bullet Analysis:")
    print(f"  Window: {setup.window.value}")
    print(f"  Signal: {setup.signal.value}")
    print(f"  Confidence: {setup.confidence:.1f}%")
    print(f"  Reasons: {setup.reasons}")
