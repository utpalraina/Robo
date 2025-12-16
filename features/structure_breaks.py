"""
Break of Structure (BOS) and Market Structure Shift (MSS) Indicator

ICT Concepts:
- BOS (Break of Structure): Price breaks a swing point IN the direction of the trend
  - Bullish BOS: In uptrend, price breaks above a swing high (trend continuation)
  - Bearish BOS: In downtrend, price breaks below a swing low (trend continuation)

- MSS (Market Structure Shift): Price breaks a swing point AGAINST the trend direction
  - Bullish MSS: In downtrend, price breaks above a swing high (potential reversal to uptrend)
  - Bearish MSS: In uptrend, price breaks below a swing low (potential reversal to downtrend)
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class StructureType(Enum):
    BOS_BULLISH = "bos_bullish"      # Trend continuation - bullish
    BOS_BEARISH = "bos_bearish"      # Trend continuation - bearish
    MSS_BULLISH = "mss_bullish"      # Trend reversal - to bullish
    MSS_BEARISH = "mss_bearish"      # Trend reversal - to bearish


class TrendDirection(Enum):
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    RANGING = "ranging"


@dataclass
class SwingPoint:
    """Represents a swing high or low."""
    index: int
    timestamp: str
    price: float
    is_high: bool  # True for swing high, False for swing low
    broken: bool = False
    broken_by_index: Optional[int] = None


@dataclass
class StructureBreak:
    """Represents a BOS or MSS event."""
    type: StructureType
    index: int                    # Candle that caused the break
    timestamp: str
    broken_level: float           # The swing level that was broken
    break_price: float            # Price at which the break occurred
    swing_index: int              # Index of the broken swing point
    strength: float               # Percentage strength of the break
    prior_trend: TrendDirection   # Trend before the break

    def to_dict(self) -> Dict:
        return {
            'type': self.type.value,
            'is_bos': self.type in [StructureType.BOS_BULLISH, StructureType.BOS_BEARISH],
            'is_mss': self.type in [StructureType.MSS_BULLISH, StructureType.MSS_BEARISH],
            'direction': 'bullish' if 'bullish' in self.type.value else 'bearish',
            'index': self.index,
            'timestamp': self.timestamp,
            'broken_level': self.broken_level,
            'break_price': self.break_price,
            'swing_index': self.swing_index,
            'strength': self.strength,
            'prior_trend': self.prior_trend.value
        }


class StructureBreakIndicator:
    """
    Detects Break of Structure (BOS) and Market Structure Shift (MSS).
    """

    def __init__(self, swing_lookback: int = 5, min_swing_distance: int = 3):
        """
        Initialize the indicator.

        Args:
            swing_lookback: Number of candles on each side to confirm swing point
            min_swing_distance: Minimum candles between swing points
        """
        self.swing_lookback = swing_lookback
        self.min_swing_distance = min_swing_distance

    def detect_swing_points(self, df: pd.DataFrame) -> List[SwingPoint]:
        """
        Detect swing highs and swing lows.

        A swing high is a high that is higher than the highs on both sides.
        A swing low is a low that is lower than the lows on both sides.
        """
        swing_points = []
        lookback = self.swing_lookback

        for i in range(lookback, len(df) - lookback):
            high = df['high'].iloc[i]
            low = df['low'].iloc[i]

            # Check for swing high
            is_swing_high = True
            for j in range(i - lookback, i + lookback + 1):
                if j != i and df['high'].iloc[j] >= high:
                    is_swing_high = False
                    break

            if is_swing_high:
                timestamp = df.index[i]
                if hasattr(timestamp, 'isoformat'):
                    timestamp = timestamp.isoformat()
                else:
                    timestamp = str(timestamp)

                swing_points.append(SwingPoint(
                    index=i,
                    timestamp=timestamp,
                    price=float(high),
                    is_high=True
                ))

            # Check for swing low
            is_swing_low = True
            for j in range(i - lookback, i + lookback + 1):
                if j != i and df['low'].iloc[j] <= low:
                    is_swing_low = False
                    break

            if is_swing_low:
                timestamp = df.index[i]
                if hasattr(timestamp, 'isoformat'):
                    timestamp = timestamp.isoformat()
                else:
                    timestamp = str(timestamp)

                swing_points.append(SwingPoint(
                    index=i,
                    timestamp=timestamp,
                    price=float(low),
                    is_high=False
                ))

        # Sort by index
        swing_points.sort(key=lambda x: x.index)
        return swing_points

    def determine_trend(self, swing_highs: List[SwingPoint],
                       swing_lows: List[SwingPoint]) -> TrendDirection:
        """
        Determine current trend based on swing point sequence.

        Uptrend: Higher Highs (HH) and Higher Lows (HL)
        Downtrend: Lower Highs (LH) and Lower Lows (LL)
        """
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return TrendDirection.RANGING

        # Check last 3 swing highs and lows
        recent_highs = swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs
        recent_lows = swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows

        # Count higher highs and higher lows
        hh_count = sum(1 for i in range(1, len(recent_highs))
                      if recent_highs[i].price > recent_highs[i-1].price)
        hl_count = sum(1 for i in range(1, len(recent_lows))
                      if recent_lows[i].price > recent_lows[i-1].price)

        # Count lower highs and lower lows
        lh_count = sum(1 for i in range(1, len(recent_highs))
                      if recent_highs[i].price < recent_highs[i-1].price)
        ll_count = sum(1 for i in range(1, len(recent_lows))
                      if recent_lows[i].price < recent_lows[i-1].price)

        bullish_score = hh_count + hl_count
        bearish_score = lh_count + ll_count

        if bullish_score > bearish_score:
            return TrendDirection.UPTREND
        elif bearish_score > bullish_score:
            return TrendDirection.DOWNTREND
        else:
            return TrendDirection.RANGING

    def detect_structure_breaks(self, df: pd.DataFrame) -> Dict:
        """
        Detect all BOS and MSS events in the dataframe.

        Returns:
            Dictionary containing:
            - swing_points: List of all swing points
            - bos_events: List of Break of Structure events
            - mss_events: List of Market Structure Shift events
            - all_breaks: Combined list sorted by index
            - current_trend: Current market trend
            - summary: Summary statistics
        """
        if len(df) < self.swing_lookback * 2 + 5:
            return self._empty_result()

        # Detect swing points
        all_swings = self.detect_swing_points(df)
        swing_highs = [s for s in all_swings if s.is_high]
        swing_lows = [s for s in all_swings if not s.is_high]

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return self._empty_result()

        bos_events = []
        mss_events = []

        # Track trend at each point
        for i in range(2, len(all_swings)):
            # Get swings up to this point
            swings_so_far = all_swings[:i]
            highs_so_far = [s for s in swings_so_far if s.is_high]
            lows_so_far = [s for s in swings_so_far if not s.is_high]

            if len(highs_so_far) < 2 or len(lows_so_far) < 2:
                continue

            # Determine trend at this point
            trend = self.determine_trend(highs_so_far, lows_so_far)
            current_swing = all_swings[i]

            # Look for breaks after this swing point
            start_idx = current_swing.index + 1

            if current_swing.is_high:
                # Check if this swing high gets broken
                for j in range(start_idx, min(len(df), start_idx + 50)):
                    if df['high'].iloc[j] > current_swing.price:
                        timestamp = df.index[j]
                        if hasattr(timestamp, 'isoformat'):
                            timestamp = timestamp.isoformat()
                        else:
                            timestamp = str(timestamp)

                        strength = (df['high'].iloc[j] - current_swing.price) / current_swing.price * 100

                        # Determine if BOS or MSS
                        if trend == TrendDirection.UPTREND:
                            # Break of swing high in uptrend = BOS (continuation)
                            break_event = StructureBreak(
                                type=StructureType.BOS_BULLISH,
                                index=j,
                                timestamp=timestamp,
                                broken_level=current_swing.price,
                                break_price=float(df['high'].iloc[j]),
                                swing_index=current_swing.index,
                                strength=round(strength, 3),
                                prior_trend=trend
                            )
                            bos_events.append(break_event)
                        elif trend == TrendDirection.DOWNTREND:
                            # Break of swing high in downtrend = MSS (reversal)
                            break_event = StructureBreak(
                                type=StructureType.MSS_BULLISH,
                                index=j,
                                timestamp=timestamp,
                                broken_level=current_swing.price,
                                break_price=float(df['high'].iloc[j]),
                                swing_index=current_swing.index,
                                strength=round(strength, 3),
                                prior_trend=trend
                            )
                            mss_events.append(break_event)

                        current_swing.broken = True
                        current_swing.broken_by_index = j
                        break

            else:  # Swing low
                # Check if this swing low gets broken
                for j in range(start_idx, min(len(df), start_idx + 50)):
                    if df['low'].iloc[j] < current_swing.price:
                        timestamp = df.index[j]
                        if hasattr(timestamp, 'isoformat'):
                            timestamp = timestamp.isoformat()
                        else:
                            timestamp = str(timestamp)

                        strength = (current_swing.price - df['low'].iloc[j]) / current_swing.price * 100

                        # Determine if BOS or MSS
                        if trend == TrendDirection.DOWNTREND:
                            # Break of swing low in downtrend = BOS (continuation)
                            break_event = StructureBreak(
                                type=StructureType.BOS_BEARISH,
                                index=j,
                                timestamp=timestamp,
                                broken_level=current_swing.price,
                                break_price=float(df['low'].iloc[j]),
                                swing_index=current_swing.index,
                                strength=round(strength, 3),
                                prior_trend=trend
                            )
                            bos_events.append(break_event)
                        elif trend == TrendDirection.UPTREND:
                            # Break of swing low in uptrend = MSS (reversal)
                            break_event = StructureBreak(
                                type=StructureType.MSS_BEARISH,
                                index=j,
                                timestamp=timestamp,
                                broken_level=current_swing.price,
                                break_price=float(df['low'].iloc[j]),
                                swing_index=current_swing.index,
                                strength=round(strength, 3),
                                prior_trend=trend
                            )
                            mss_events.append(break_event)

                        current_swing.broken = True
                        current_swing.broken_by_index = j
                        break

        # Combine and sort all breaks
        all_breaks = bos_events + mss_events
        all_breaks.sort(key=lambda x: x.index)

        # Current trend
        current_trend = self.determine_trend(swing_highs, swing_lows)

        # Summary
        summary = {
            'total_swings': len(all_swings),
            'swing_highs': len(swing_highs),
            'swing_lows': len(swing_lows),
            'total_bos': len(bos_events),
            'bos_bullish': len([b for b in bos_events if b.type == StructureType.BOS_BULLISH]),
            'bos_bearish': len([b for b in bos_events if b.type == StructureType.BOS_BEARISH]),
            'total_mss': len(mss_events),
            'mss_bullish': len([m for m in mss_events if m.type == StructureType.MSS_BULLISH]),
            'mss_bearish': len([m for m in mss_events if m.type == StructureType.MSS_BEARISH]),
            'current_trend': current_trend.value
        }

        # Get recent events (last 5 of each)
        recent_bos = bos_events[-5:] if bos_events else []
        recent_mss = mss_events[-5:] if mss_events else []

        return {
            'swing_points': [self._swing_to_dict(s) for s in all_swings],
            'swing_highs': [self._swing_to_dict(s) for s in swing_highs],
            'swing_lows': [self._swing_to_dict(s) for s in swing_lows],
            'bos_events': [b.to_dict() for b in bos_events],
            'mss_events': [m.to_dict() for m in mss_events],
            'recent_bos': [b.to_dict() for b in recent_bos],
            'recent_mss': [m.to_dict() for m in recent_mss],
            'all_breaks': [b.to_dict() for b in all_breaks],
            'current_trend': current_trend.value,
            'summary': summary,
            'last_break': all_breaks[-1].to_dict() if all_breaks else None
        }

    def get_trading_signal(self, df: pd.DataFrame) -> Dict:
        """
        Get trading signal based on BOS/MSS analysis.

        Returns trading recommendation based on structure breaks.
        """
        result = self.detect_structure_breaks(df)

        if not result['all_breaks']:
            return {
                'signal': 'NEUTRAL',
                'confidence': 0,
                'reason': 'No structure breaks detected',
                'last_break': None
            }

        last_break = result['all_breaks'][-1]
        recent_breaks = result['all_breaks'][-3:] if len(result['all_breaks']) >= 3 else result['all_breaks']

        # Count recent bullish vs bearish breaks
        bullish_breaks = sum(1 for b in recent_breaks if 'bullish' in b['type'])
        bearish_breaks = sum(1 for b in recent_breaks if 'bearish' in b['type'])

        signal = 'NEUTRAL'
        confidence = 0
        reason = ''

        if last_break['is_mss']:
            # MSS signals potential reversal - high significance
            if last_break['direction'] == 'bullish':
                signal = 'LONG'
                confidence = min(0.8 + last_break['strength'] / 100, 1.0)
                reason = f"Bullish MSS detected - potential trend reversal. Prior trend was {last_break['prior_trend']}."
            else:
                signal = 'SHORT'
                confidence = min(0.8 + last_break['strength'] / 100, 1.0)
                reason = f"Bearish MSS detected - potential trend reversal. Prior trend was {last_break['prior_trend']}."

        elif last_break['is_bos']:
            # BOS signals continuation - moderate significance
            if last_break['direction'] == 'bullish':
                signal = 'LONG'
                confidence = min(0.6 + last_break['strength'] / 100, 0.9)
                reason = f"Bullish BOS detected - trend continuation. Current trend: {result['current_trend']}."
            else:
                signal = 'SHORT'
                confidence = min(0.6 + last_break['strength'] / 100, 0.9)
                reason = f"Bearish BOS detected - trend continuation. Current trend: {result['current_trend']}."

        # Adjust confidence based on alignment
        if bullish_breaks > bearish_breaks and signal == 'LONG':
            confidence = min(confidence + 0.1, 1.0)
            reason += f" {bullish_breaks}/{len(recent_breaks)} recent breaks bullish."
        elif bearish_breaks > bullish_breaks and signal == 'SHORT':
            confidence = min(confidence + 0.1, 1.0)
            reason += f" {bearish_breaks}/{len(recent_breaks)} recent breaks bearish."
        elif bullish_breaks != bearish_breaks:
            confidence = max(confidence - 0.2, 0.3)
            reason += " Mixed signals in recent structure."

        return {
            'signal': signal,
            'confidence': round(confidence, 2),
            'reason': reason,
            'current_trend': result['current_trend'],
            'last_break': last_break,
            'summary': result['summary']
        }

    def _swing_to_dict(self, swing: SwingPoint) -> Dict:
        return {
            'type': 'high' if swing.is_high else 'low',
            'index': swing.index,
            'timestamp': swing.timestamp,
            'price': swing.price,
            'broken': swing.broken,
            'broken_by_index': swing.broken_by_index
        }

    def _empty_result(self) -> Dict:
        return {
            'swing_points': [],
            'swing_highs': [],
            'swing_lows': [],
            'bos_events': [],
            'mss_events': [],
            'recent_bos': [],
            'recent_mss': [],
            'all_breaks': [],
            'current_trend': 'ranging',
            'summary': {
                'total_swings': 0,
                'swing_highs': 0,
                'swing_lows': 0,
                'total_bos': 0,
                'bos_bullish': 0,
                'bos_bearish': 0,
                'total_mss': 0,
                'mss_bullish': 0,
                'mss_bearish': 0,
                'current_trend': 'ranging'
            },
            'last_break': None
        }


def calculate_bos_mss(df: pd.DataFrame, swing_lookback: int = 5) -> Dict:
    """
    Convenience function to calculate BOS/MSS for a dataframe.

    Args:
        df: DataFrame with OHLC data (columns: open, high, low, close)
        swing_lookback: Number of candles to confirm swing points

    Returns:
        Dictionary with all BOS/MSS analysis
    """
    indicator = StructureBreakIndicator(swing_lookback=swing_lookback)
    return indicator.detect_structure_breaks(df)


def get_structure_signal(df: pd.DataFrame, swing_lookback: int = 5) -> Dict:
    """
    Get trading signal based on structure analysis.

    Args:
        df: DataFrame with OHLC data
        swing_lookback: Number of candles to confirm swing points

    Returns:
        Trading signal dictionary
    """
    indicator = StructureBreakIndicator(swing_lookback=swing_lookback)
    return indicator.get_trading_signal(df)
