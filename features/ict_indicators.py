"""
ICT (Inner Circle Trader) Indicators Detection Module.

This module implements detection algorithms for various ICT concepts:
- Fair Value Gaps (FVG)
- Market Structure Shifts (MSS)
- Order Blocks (OB)
- Breaker Blocks
- Optimal Trade Entry (OTE) levels
- Liquidity Zones
- Premium/Discount Zones
- Displacement
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from loguru import logger


class ICTIndicators:
    """ICT trading concepts detector."""

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize ICT indicators detector.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}

        # Default parameters
        self.fvg_min_gap_pct = self.config.get('fvg_min_gap_pct', 0.1)  # Min 0.1% gap
        self.displacement_atr_mult = self.config.get('displacement_atr_mult', 1.5)
        self.ob_volume_mult = self.config.get('ob_volume_mult', 1.3)
        self.swing_lookback = self.config.get('swing_lookback', 5)
        self.liquidity_touches = self.config.get('liquidity_touches', 2)

    def detect_all(self, df: pd.DataFrame) -> Dict:
        """
        Detect all ICT indicators on the given OHLCV data.

        Args:
            df: DataFrame with OHLCV data (columns: open, high, low, close, volume)

        Returns:
            Dictionary containing all detected ICT indicators
        """
        if len(df) < 20:
            return self._empty_results()

        # Ensure we have required columns
        required = ['open', 'high', 'low', 'close', 'volume']
        for col in required:
            if col not in df.columns:
                logger.warning(f"Missing column: {col}")
                return self._empty_results()

        # Calculate ATR for various detections
        df = self._calculate_atr(df.copy())

        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'current_price': float(df['close'].iloc[-1]),
            'fvg': self.detect_fair_value_gaps(df),
            'mss': self.detect_market_structure_shift(df),
            'order_blocks': self.detect_order_blocks(df),
            'breaker_blocks': self.detect_breaker_blocks(df),
            'ote_levels': self.calculate_ote_levels(df),
            'liquidity_zones': self.detect_liquidity_zones(df),
            'premium_discount': self.calculate_premium_discount_zones(df),
            'displacement': self.detect_displacement(df),
            'swing_points': self.detect_swing_points(df),
            'market_structure': self.analyze_market_structure(df)
        }

        return results

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Calculate Average True Range."""
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)

        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=period).mean()

        return df

    def detect_fair_value_gaps(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detect Fair Value Gaps (FVG).

        A bullish FVG occurs when candle 3's low is higher than candle 1's high.
        A bearish FVG occurs when candle 3's high is lower than candle 1's low.

        Returns:
            List of detected FVGs with their properties
        """
        fvgs = []

        for i in range(2, len(df)):
            candle_1 = df.iloc[i-2]
            candle_2 = df.iloc[i-1]  # The displacement candle
            candle_3 = df.iloc[i]

            # Bullish FVG: gap between candle 1 high and candle 3 low
            if candle_3['low'] > candle_1['high']:
                gap_size = candle_3['low'] - candle_1['high']
                gap_pct = (gap_size / candle_1['high']) * 100

                if gap_pct >= self.fvg_min_gap_pct:
                    fvgs.append({
                        'type': 'bullish',
                        'index': i,
                        'timestamp': df.index[i].isoformat() if hasattr(df.index[i], 'isoformat') else str(df.index[i]),
                        'top': float(candle_3['low']),
                        'bottom': float(candle_1['high']),
                        'gap_size': float(gap_size),
                        'gap_pct': round(gap_pct, 3),
                        'midpoint': float((candle_3['low'] + candle_1['high']) / 2),
                        'filled': False,
                        'filled_pct': 0
                    })

            # Bearish FVG: gap between candle 1 low and candle 3 high
            elif candle_3['high'] < candle_1['low']:
                gap_size = candle_1['low'] - candle_3['high']
                gap_pct = (gap_size / candle_1['low']) * 100

                if gap_pct >= self.fvg_min_gap_pct:
                    fvgs.append({
                        'type': 'bearish',
                        'index': i,
                        'timestamp': df.index[i].isoformat() if hasattr(df.index[i], 'isoformat') else str(df.index[i]),
                        'top': float(candle_1['low']),
                        'bottom': float(candle_3['high']),
                        'gap_size': float(gap_size),
                        'gap_pct': round(gap_pct, 3),
                        'midpoint': float((candle_1['low'] + candle_3['high']) / 2),
                        'filled': False,
                        'filled_pct': 0
                    })

        # Check if FVGs have been filled by subsequent price action
        for fvg in fvgs:
            fvg_idx = fvg['index']
            for j in range(fvg_idx + 1, len(df)):
                candle = df.iloc[j]

                if fvg['type'] == 'bullish':
                    # Bullish FVG is filled when price comes back down into the gap
                    if candle['low'] <= fvg['top']:
                        fill_depth = fvg['top'] - max(candle['low'], fvg['bottom'])
                        fvg['filled_pct'] = min(100, (fill_depth / fvg['gap_size']) * 100)
                        if candle['low'] <= fvg['bottom']:
                            fvg['filled'] = True
                            break
                else:
                    # Bearish FVG is filled when price comes back up into the gap
                    if candle['high'] >= fvg['bottom']:
                        fill_depth = min(candle['high'], fvg['top']) - fvg['bottom']
                        fvg['filled_pct'] = min(100, (fill_depth / fvg['gap_size']) * 100)
                        if candle['high'] >= fvg['top']:
                            fvg['filled'] = True
                            break

        # Return most recent unfilled FVGs (limit to 10)
        unfilled = [f for f in fvgs if not f['filled']]
        return unfilled[-10:]

    def detect_market_structure_shift(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detect Market Structure Shifts (MSS).

        MSS occurs when the market breaks a significant swing high/low,
        indicating a potential trend reversal.

        Returns:
            List of detected MSS events
        """
        swing_points = self.detect_swing_points(df)
        mss_events = []

        swing_highs = [sp for sp in swing_points if sp['type'] == 'high']
        swing_lows = [sp for sp in swing_points if sp['type'] == 'low']

        # Detect bullish MSS (break of lower high in downtrend)
        for i in range(1, len(swing_highs)):
            current = swing_highs[i]
            previous = swing_highs[i-1]

            # Check if we were making lower highs (downtrend)
            if current['price'] < previous['price']:
                # Look for break above this lower high
                start_idx = current['index']
                for j in range(start_idx + 1, len(df)):
                    if df.iloc[j]['high'] > current['price']:
                        mss_events.append({
                            'type': 'bullish',
                            'trigger_index': j,
                            'timestamp': df.index[j].isoformat() if hasattr(df.index[j], 'isoformat') else str(df.index[j]),
                            'broken_level': float(current['price']),
                            'break_price': float(df.iloc[j]['high']),
                            'strength': round((df.iloc[j]['high'] - current['price']) / current['price'] * 100, 3)
                        })
                        break

        # Detect bearish MSS (break of higher low in uptrend)
        for i in range(1, len(swing_lows)):
            current = swing_lows[i]
            previous = swing_lows[i-1]

            # Check if we were making higher lows (uptrend)
            if current['price'] > previous['price']:
                # Look for break below this higher low
                start_idx = current['index']
                for j in range(start_idx + 1, len(df)):
                    if df.iloc[j]['low'] < current['price']:
                        mss_events.append({
                            'type': 'bearish',
                            'trigger_index': j,
                            'timestamp': df.index[j].isoformat() if hasattr(df.index[j], 'isoformat') else str(df.index[j]),
                            'broken_level': float(current['price']),
                            'break_price': float(df.iloc[j]['low']),
                            'strength': round((current['price'] - df.iloc[j]['low']) / current['price'] * 100, 3)
                        })
                        break

        # Return most recent MSS events (limit to 5)
        return mss_events[-5:]

    def detect_order_blocks(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detect Order Blocks (OB).

        Order blocks are the last opposing candle before a strong move.
        Bullish OB: Last bearish candle before a strong bullish move
        Bearish OB: Last bullish candle before a strong bearish move

        Returns:
            List of detected order blocks
        """
        order_blocks = []
        avg_volume = df['volume'].rolling(20).mean()

        for i in range(2, len(df) - 1):
            candle = df.iloc[i]
            next_candle = df.iloc[i + 1]

            # Skip if no ATR
            if pd.isna(df['atr'].iloc[i]):
                continue

            atr = df['atr'].iloc[i]
            candle_body = abs(candle['close'] - candle['open'])
            next_body = abs(next_candle['close'] - next_candle['open'])

            # Check for significant next move (displacement)
            is_displacement = next_body > atr * self.displacement_atr_mult

            if not is_displacement:
                continue

            # Bullish Order Block: Bearish candle followed by strong bullish move
            if candle['close'] < candle['open'] and next_candle['close'] > next_candle['open']:
                # Check for high volume
                is_high_volume = candle['volume'] > avg_volume.iloc[i] * self.ob_volume_mult if not pd.isna(avg_volume.iloc[i]) else True

                order_blocks.append({
                    'type': 'bullish',
                    'index': i,
                    'timestamp': df.index[i].isoformat() if hasattr(df.index[i], 'isoformat') else str(df.index[i]),
                    'high': float(candle['high']),
                    'low': float(candle['low']),
                    'open': float(candle['open']),
                    'close': float(candle['close']),
                    'volume': float(candle['volume']),
                    'is_high_volume': bool(is_high_volume),
                    'displacement_size': round(next_body / atr, 2),
                    'mitigated': False,
                    'tested': False
                })

            # Bearish Order Block: Bullish candle followed by strong bearish move
            elif candle['close'] > candle['open'] and next_candle['close'] < next_candle['open']:
                is_high_volume = candle['volume'] > avg_volume.iloc[i] * self.ob_volume_mult if not pd.isna(avg_volume.iloc[i]) else True

                order_blocks.append({
                    'type': 'bearish',
                    'index': i,
                    'timestamp': df.index[i].isoformat() if hasattr(df.index[i], 'isoformat') else str(df.index[i]),
                    'high': float(candle['high']),
                    'low': float(candle['low']),
                    'open': float(candle['open']),
                    'close': float(candle['close']),
                    'volume': float(candle['volume']),
                    'is_high_volume': bool(is_high_volume),
                    'displacement_size': round(next_body / atr, 2),
                    'mitigated': False,
                    'tested': False
                })

        # Check if order blocks have been tested/mitigated
        for ob in order_blocks:
            ob_idx = ob['index']
            for j in range(ob_idx + 2, len(df)):
                candle = df.iloc[j]

                if ob['type'] == 'bullish':
                    # Bullish OB tested when price comes back to it
                    if candle['low'] <= ob['high']:
                        ob['tested'] = True
                        if candle['low'] < ob['low']:
                            ob['mitigated'] = True
                            break
                else:
                    # Bearish OB tested when price comes back to it
                    if candle['high'] >= ob['low']:
                        ob['tested'] = True
                        if candle['high'] > ob['high']:
                            ob['mitigated'] = True
                            break

        # Return most recent unmitigated order blocks
        unmitigated = [ob for ob in order_blocks if not ob['mitigated']]
        return unmitigated[-10:]

    def detect_breaker_blocks(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detect Breaker Blocks.

        A breaker block is a failed order block that was mitigated and
        now acts as the opposite zone (support becomes resistance and vice versa).

        Returns:
            List of detected breaker blocks
        """
        order_blocks = self.detect_order_blocks(df)
        breaker_blocks = []

        # Get mitigated order blocks
        all_obs = []
        avg_volume = df['volume'].rolling(20).mean()

        for i in range(2, len(df) - 1):
            candle = df.iloc[i]
            next_candle = df.iloc[i + 1]

            if pd.isna(df['atr'].iloc[i]):
                continue

            atr = df['atr'].iloc[i]
            candle_body = abs(candle['close'] - candle['open'])
            next_body = abs(next_candle['close'] - next_candle['open'])

            is_displacement = next_body > atr * self.displacement_atr_mult

            if not is_displacement:
                continue

            if candle['close'] < candle['open'] and next_candle['close'] > next_candle['open']:
                all_obs.append({
                    'type': 'bullish',
                    'index': i,
                    'high': float(candle['high']),
                    'low': float(candle['low']),
                    'timestamp': df.index[i].isoformat() if hasattr(df.index[i], 'isoformat') else str(df.index[i]),
                })
            elif candle['close'] > candle['open'] and next_candle['close'] < next_candle['open']:
                all_obs.append({
                    'type': 'bearish',
                    'index': i,
                    'high': float(candle['high']),
                    'low': float(candle['low']),
                    'timestamp': df.index[i].isoformat() if hasattr(df.index[i], 'isoformat') else str(df.index[i]),
                })

        # Check for breakers (mitigated OBs that now act as opposite)
        for ob in all_obs:
            ob_idx = ob['index']
            mitigated_at = None

            for j in range(ob_idx + 2, len(df)):
                candle = df.iloc[j]

                if ob['type'] == 'bullish' and candle['low'] < ob['low']:
                    mitigated_at = j
                    break
                elif ob['type'] == 'bearish' and candle['high'] > ob['high']:
                    mitigated_at = j
                    break

            if mitigated_at:
                # Check if price has come back to this breaker
                tested = False
                for k in range(mitigated_at + 1, len(df)):
                    candle = df.iloc[k]
                    if ob['type'] == 'bullish':
                        # Bullish OB becomes bearish breaker (resistance)
                        if candle['high'] >= ob['low'] and candle['high'] <= ob['high']:
                            tested = True
                            break
                    else:
                        # Bearish OB becomes bullish breaker (support)
                        if candle['low'] <= ob['high'] and candle['low'] >= ob['low']:
                            tested = True
                            break

                if tested:
                    breaker_blocks.append({
                        'type': 'bearish' if ob['type'] == 'bullish' else 'bullish',
                        'original_type': ob['type'],
                        'index': ob['index'],
                        'timestamp': ob['timestamp'],
                        'high': ob['high'],
                        'low': ob['low'],
                        'mitigated_at': mitigated_at
                    })

        return breaker_blocks[-5:]

    def calculate_ote_levels(self, df: pd.DataFrame) -> Dict:
        """
        Calculate Optimal Trade Entry (OTE) Fibonacci levels.

        OTE levels based on recent swing high/low:
        - 0.5 (50%): Equilibrium
        - 0.62 (62%): Optimal Entry #1
        - 0.705 (70.5%): Optimal Entry #2
        - 0.79 (79%): Optimal Entry #3
        - -0.27: Target 1
        - -0.62: Target 2

        Returns:
            Dictionary with OTE levels for both bullish and bearish scenarios
        """
        swing_points = self.detect_swing_points(df)

        if len(swing_points) < 2:
            return {'bullish': None, 'bearish': None}

        # Find recent swing high and low
        swing_highs = [sp for sp in swing_points if sp['type'] == 'high']
        swing_lows = [sp for sp in swing_points if sp['type'] == 'low']

        if not swing_highs or not swing_lows:
            return {'bullish': None, 'bearish': None}

        recent_high = swing_highs[-1]
        recent_low = swing_lows[-1]

        swing_range = recent_high['price'] - recent_low['price']

        # Bullish OTE (price retraces down from high)
        bullish_ote = {
            'swing_high': float(recent_high['price']),
            'swing_low': float(recent_low['price']),
            'range': float(swing_range),
            'levels': {
                'equilibrium_50': float(recent_high['price'] - swing_range * 0.5),
                'ote_62': float(recent_high['price'] - swing_range * 0.62),
                'ote_705': float(recent_high['price'] - swing_range * 0.705),
                'ote_79': float(recent_high['price'] - swing_range * 0.79),
            },
            'targets': {
                'target_1_neg27': float(recent_high['price'] + swing_range * 0.27),
                'target_2_neg62': float(recent_high['price'] + swing_range * 0.62),
                'target_final': float(recent_high['price'] + swing_range),
            },
            'zone': 'premium' if df['close'].iloc[-1] > recent_high['price'] - swing_range * 0.5 else 'discount'
        }

        # Bearish OTE (price retraces up from low)
        bearish_ote = {
            'swing_high': float(recent_high['price']),
            'swing_low': float(recent_low['price']),
            'range': float(swing_range),
            'levels': {
                'equilibrium_50': float(recent_low['price'] + swing_range * 0.5),
                'ote_62': float(recent_low['price'] + swing_range * 0.62),
                'ote_705': float(recent_low['price'] + swing_range * 0.705),
                'ote_79': float(recent_low['price'] + swing_range * 0.79),
            },
            'targets': {
                'target_1_neg27': float(recent_low['price'] - swing_range * 0.27),
                'target_2_neg62': float(recent_low['price'] - swing_range * 0.62),
                'target_final': float(recent_low['price'] - swing_range),
            },
            'zone': 'premium' if df['close'].iloc[-1] > recent_low['price'] + swing_range * 0.5 else 'discount'
        }

        return {
            'bullish': bullish_ote,
            'bearish': bearish_ote,
            'current_price': float(df['close'].iloc[-1])
        }

    def detect_liquidity_zones(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detect liquidity zones (equal highs/lows where stops cluster).

        Equal highs/lows indicate areas where stop losses accumulate,
        making them targets for liquidity sweeps.

        Returns:
            List of detected liquidity zones
        """
        liquidity_zones = []
        tolerance = df['atr'].iloc[-1] * 0.1 if not pd.isna(df['atr'].iloc[-1]) else df['close'].iloc[-1] * 0.001

        # Detect equal highs (resistance liquidity)
        highs = df['high'].values
        for i in range(self.swing_lookback, len(df) - 1):
            level = highs[i]
            touches = 1
            touch_indices = [i]

            for j in range(i + 1, len(df)):
                if abs(highs[j] - level) <= tolerance:
                    touches += 1
                    touch_indices.append(j)

            if touches >= self.liquidity_touches:
                # Check if this level hasn't been swept
                swept = any(df['high'].iloc[k] > level + tolerance for k in range(touch_indices[-1] + 1, len(df)))

                if not swept:
                    liquidity_zones.append({
                        'type': 'buy_side',  # Buy side liquidity (stops above)
                        'level': float(level),
                        'touches': touches,
                        'first_touch_index': i,
                        'last_touch_index': touch_indices[-1],
                        'timestamp': df.index[i].isoformat() if hasattr(df.index[i], 'isoformat') else str(df.index[i]),
                        'swept': False
                    })

        # Detect equal lows (support liquidity)
        lows = df['low'].values
        for i in range(self.swing_lookback, len(df) - 1):
            level = lows[i]
            touches = 1
            touch_indices = [i]

            for j in range(i + 1, len(df)):
                if abs(lows[j] - level) <= tolerance:
                    touches += 1
                    touch_indices.append(j)

            if touches >= self.liquidity_touches:
                # Check if this level hasn't been swept
                swept = any(df['low'].iloc[k] < level - tolerance for k in range(touch_indices[-1] + 1, len(df)))

                if not swept:
                    liquidity_zones.append({
                        'type': 'sell_side',  # Sell side liquidity (stops below)
                        'level': float(level),
                        'touches': touches,
                        'first_touch_index': i,
                        'last_touch_index': touch_indices[-1],
                        'timestamp': df.index[i].isoformat() if hasattr(df.index[i], 'isoformat') else str(df.index[i]),
                        'swept': False
                    })

        # Remove duplicates and return most relevant
        seen = set()
        unique_zones = []
        for zone in liquidity_zones:
            key = (zone['type'], round(zone['level'], 2))
            if key not in seen:
                seen.add(key)
                unique_zones.append(zone)

        return sorted(unique_zones, key=lambda x: x['touches'], reverse=True)[:10]

    def calculate_premium_discount_zones(self, df: pd.DataFrame) -> Dict:
        """
        Calculate Premium and Discount zones based on recent range.

        Premium zone: Above 50% of range (sell territory)
        Discount zone: Below 50% of range (buy territory)

        Returns:
            Dictionary with zone information
        """
        lookback = min(50, len(df))
        recent_df = df.iloc[-lookback:]

        range_high = recent_df['high'].max()
        range_low = recent_df['low'].min()
        range_size = range_high - range_low
        equilibrium = range_low + range_size * 0.5

        current_price = df['close'].iloc[-1]

        # Calculate position within range
        if range_size > 0:
            position_pct = ((current_price - range_low) / range_size) * 100
        else:
            position_pct = 50

        # Determine current zone
        if position_pct > 70:
            zone = 'deep_premium'
            bias = 'bearish'
        elif position_pct > 50:
            zone = 'premium'
            bias = 'bearish'
        elif position_pct > 30:
            zone = 'discount'
            bias = 'bullish'
        else:
            zone = 'deep_discount'
            bias = 'bullish'

        return {
            'range_high': float(range_high),
            'range_low': float(range_low),
            'range_size': float(range_size),
            'equilibrium': float(equilibrium),
            'current_price': float(current_price),
            'position_pct': round(position_pct, 2),
            'zone': zone,
            'bias': bias,
            'premium_zone': {
                'start': float(equilibrium),
                'end': float(range_high)
            },
            'discount_zone': {
                'start': float(range_low),
                'end': float(equilibrium)
            }
        }

    def detect_displacement(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detect displacement candles (strong impulsive moves).

        Displacement creates FVGs and often initiates trends.

        Returns:
            List of detected displacement events
        """
        displacements = []
        avg_volume = df['volume'].rolling(20).mean()

        for i in range(14, len(df)):
            candle = df.iloc[i]
            atr = df['atr'].iloc[i]

            if pd.isna(atr):
                continue

            body_size = abs(candle['close'] - candle['open'])
            candle_range = candle['high'] - candle['low']

            # Displacement criteria
            is_large_body = body_size > atr * self.displacement_atr_mult
            is_high_volume = candle['volume'] > avg_volume.iloc[i] * 1.5 if not pd.isna(avg_volume.iloc[i]) else False
            body_to_range_ratio = body_size / candle_range if candle_range > 0 else 0

            if is_large_body and body_to_range_ratio > 0.6:
                direction = 'bullish' if candle['close'] > candle['open'] else 'bearish'

                displacements.append({
                    'type': direction,
                    'index': i,
                    'timestamp': df.index[i].isoformat() if hasattr(df.index[i], 'isoformat') else str(df.index[i]),
                    'open': float(candle['open']),
                    'close': float(candle['close']),
                    'high': float(candle['high']),
                    'low': float(candle['low']),
                    'body_size': float(body_size),
                    'body_atr_ratio': round(body_size / atr, 2),
                    'body_to_range_ratio': round(body_to_range_ratio, 2),
                    'is_high_volume': bool(is_high_volume),
                    'volume': float(candle['volume'])
                })

        return displacements[-10:]

    def detect_swing_points(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detect swing highs and swing lows.

        Returns:
            List of swing points
        """
        swing_points = []
        lookback = self.swing_lookback

        for i in range(lookback, len(df) - lookback):
            # Swing High: High is highest in lookback period on both sides
            is_swing_high = True
            for j in range(i - lookback, i + lookback + 1):
                if j != i and df['high'].iloc[j] >= df['high'].iloc[i]:
                    is_swing_high = False
                    break

            if is_swing_high:
                swing_points.append({
                    'type': 'high',
                    'index': i,
                    'timestamp': df.index[i].isoformat() if hasattr(df.index[i], 'isoformat') else str(df.index[i]),
                    'price': float(df['high'].iloc[i])
                })

            # Swing Low: Low is lowest in lookback period on both sides
            is_swing_low = True
            for j in range(i - lookback, i + lookback + 1):
                if j != i and df['low'].iloc[j] <= df['low'].iloc[i]:
                    is_swing_low = False
                    break

            if is_swing_low:
                swing_points.append({
                    'type': 'low',
                    'index': i,
                    'timestamp': df.index[i].isoformat() if hasattr(df.index[i], 'isoformat') else str(df.index[i]),
                    'price': float(df['low'].iloc[i])
                })

        return swing_points

    def analyze_market_structure(self, df: pd.DataFrame) -> Dict:
        """
        Analyze overall market structure.

        Returns:
            Dictionary with market structure analysis
        """
        swing_points = self.detect_swing_points(df)

        swing_highs = [sp for sp in swing_points if sp['type'] == 'high']
        swing_lows = [sp for sp in swing_points if sp['type'] == 'low']

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return {
                'trend': 'undefined',
                'structure': 'insufficient_data',
                'hh_count': 0,
                'hl_count': 0,
                'lh_count': 0,
                'll_count': 0
            }

        # Count higher highs, lower highs, higher lows, lower lows
        hh_count = 0
        lh_count = 0
        hl_count = 0
        ll_count = 0

        for i in range(1, len(swing_highs)):
            if swing_highs[i]['price'] > swing_highs[i-1]['price']:
                hh_count += 1
            else:
                lh_count += 1

        for i in range(1, len(swing_lows)):
            if swing_lows[i]['price'] > swing_lows[i-1]['price']:
                hl_count += 1
            else:
                ll_count += 1

        # Determine trend
        bullish_score = hh_count + hl_count
        bearish_score = lh_count + ll_count

        if bullish_score > bearish_score * 1.5:
            trend = 'bullish'
            structure = 'uptrend'
        elif bearish_score > bullish_score * 1.5:
            trend = 'bearish'
            structure = 'downtrend'
        else:
            trend = 'neutral'
            structure = 'ranging'

        return {
            'trend': trend,
            'structure': structure,
            'hh_count': hh_count,
            'hl_count': hl_count,
            'lh_count': lh_count,
            'll_count': ll_count,
            'bullish_score': bullish_score,
            'bearish_score': bearish_score,
            'last_swing_high': swing_highs[-1] if swing_highs else None,
            'last_swing_low': swing_lows[-1] if swing_lows else None
        }

    def _empty_results(self) -> Dict:
        """Return empty results structure."""
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'current_price': None,
            'fvg': [],
            'mss': [],
            'order_blocks': [],
            'breaker_blocks': [],
            'ote_levels': {'bullish': None, 'bearish': None},
            'liquidity_zones': [],
            'premium_discount': None,
            'displacement': [],
            'swing_points': [],
            'market_structure': {'trend': 'undefined', 'structure': 'insufficient_data'}
        }

    def get_trading_bias(self, df: pd.DataFrame) -> Dict:
        """
        Get overall trading bias based on ICT concepts.

        Returns:
            Dictionary with trading bias and confidence
        """
        results = self.detect_all(df)

        bullish_signals = 0
        bearish_signals = 0

        # Check premium/discount zone
        if results['premium_discount']:
            if results['premium_discount']['bias'] == 'bullish':
                bullish_signals += 2
            else:
                bearish_signals += 2

        # Check market structure
        ms = results['market_structure']
        if ms['trend'] == 'bullish':
            bullish_signals += 3
        elif ms['trend'] == 'bearish':
            bearish_signals += 3

        # Check recent FVGs
        for fvg in results['fvg'][-3:]:
            if fvg['type'] == 'bullish':
                bullish_signals += 1
            else:
                bearish_signals += 1

        # Check order blocks
        for ob in results['order_blocks'][-3:]:
            if ob['type'] == 'bullish' and not ob['tested']:
                bullish_signals += 1
            elif ob['type'] == 'bearish' and not ob['tested']:
                bearish_signals += 1

        # Check recent MSS
        for mss in results['mss'][-2:]:
            if mss['type'] == 'bullish':
                bullish_signals += 2
            else:
                bearish_signals += 2

        total = bullish_signals + bearish_signals
        if total == 0:
            return {'bias': 'neutral', 'confidence': 0, 'bullish_score': 0, 'bearish_score': 0}

        if bullish_signals > bearish_signals:
            bias = 'bullish'
            confidence = (bullish_signals / total) * 100
        elif bearish_signals > bullish_signals:
            bias = 'bearish'
            confidence = (bearish_signals / total) * 100
        else:
            bias = 'neutral'
            confidence = 50

        return {
            'bias': bias,
            'confidence': round(confidence, 1),
            'bullish_score': bullish_signals,
            'bearish_score': bearish_signals
        }
