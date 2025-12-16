"""
ICT Features for Machine Learning Integration.

This module converts ICT indicator signals into numerical features
that can be used by ML models for enhanced prediction.

Features generated:
- FVG proximity and type
- MSS recency and type
- Order Block proximity and type
- OTE level distances
- Premium/Discount zone position
- Liquidity zone distances
- Market structure scores
- Displacement strength
- Session indicators
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from loguru import logger

from features.ict_indicators import ICTIndicators
from features.sessions import SessionFilter, TradingSession


class ICTFeatureGenerator:
    """
    Generate ML-ready features from ICT indicators.

    This class transforms ICT concepts into numerical features
    that can be combined with traditional technical indicators
    for enhanced ML predictions.
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize ICT Feature Generator.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.ict = ICTIndicators(self.config.get('ict', {}))
        self.session_filter = SessionFilter(self.config.get('sessions', {}))

        # Feature configuration
        self.fvg_lookback = self.config.get('fvg_lookback', 10)  # FVGs to consider
        self.ob_lookback = self.config.get('ob_lookback', 10)  # Order blocks to consider
        self.mss_lookback = self.config.get('mss_lookback', 5)  # MSS events to consider

    def generate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate ICT features for the entire DataFrame.

        This method calculates ICT features for each row where possible.
        Features are added as new columns to the DataFrame.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with ICT features added
        """
        if len(df) < 50:
            logger.warning("Insufficient data for ICT features (need at least 50 rows)")
            return self._add_empty_features(df)

        df = df.copy()

        # Detect ICT patterns on the full DataFrame
        ict_data = self.ict.detect_all(df)

        # Generate features for the latest candle
        # (For backtesting, you'd want to do this in a rolling window)
        features = self._generate_single_row_features(
            df, ict_data, len(df) - 1
        )

        # Add features as columns (for the last row)
        for feature_name, value in features.items():
            df[feature_name] = np.nan
            df.iloc[-1, df.columns.get_loc(feature_name)] = value

        return df

    def generate_features_for_row(
        self,
        df: pd.DataFrame,
        row_idx: int = -1
    ) -> Dict[str, float]:
        """
        Generate ICT features for a specific row.

        Args:
            df: DataFrame with OHLCV data
            row_idx: Row index to generate features for

        Returns:
            Dictionary of feature names to values
        """
        if len(df) < 50:
            return self._empty_features()

        # Get data up to this row for proper backtesting
        if row_idx == -1:
            row_idx = len(df) - 1

        df_slice = df.iloc[:row_idx + 1].copy()

        # Detect ICT patterns
        ict_data = self.ict.detect_all(df_slice)

        return self._generate_single_row_features(df_slice, ict_data, len(df_slice) - 1)

    def _generate_single_row_features(
        self,
        df: pd.DataFrame,
        ict_data: Dict,
        row_idx: int
    ) -> Dict[str, float]:
        """
        Generate features for a single row.

        Args:
            df: DataFrame
            ict_data: ICT detection results
            row_idx: Row index

        Returns:
            Dictionary of features
        """
        current_price = float(df['close'].iloc[row_idx])
        current_high = float(df['high'].iloc[row_idx])
        current_low = float(df['low'].iloc[row_idx])

        # Calculate ATR for distance normalization
        atr = self._calculate_atr(df, row_idx)

        features = {}

        # 1. FVG Features
        fvg_features = self._calculate_fvg_features(ict_data, current_price, atr)
        features.update(fvg_features)

        # 2. MSS Features
        mss_features = self._calculate_mss_features(ict_data, row_idx)
        features.update(mss_features)

        # 3. Order Block Features
        ob_features = self._calculate_ob_features(ict_data, current_price, atr)
        features.update(ob_features)

        # 4. OTE Features
        ote_features = self._calculate_ote_features(ict_data, current_price, atr)
        features.update(ote_features)

        # 5. Premium/Discount Zone Features
        pd_features = self._calculate_premium_discount_features(ict_data)
        features.update(pd_features)

        # 6. Liquidity Zone Features
        liq_features = self._calculate_liquidity_features(ict_data, current_price, atr)
        features.update(liq_features)

        # 7. Market Structure Features
        ms_features = self._calculate_market_structure_features(ict_data)
        features.update(ms_features)

        # 8. Displacement Features
        disp_features = self._calculate_displacement_features(ict_data, row_idx)
        features.update(disp_features)

        # 9. Session Features
        session_features = self._calculate_session_features(df, row_idx)
        features.update(session_features)

        # 10. Combined ICT Bias Score
        bias_features = self._calculate_bias_features(ict_data)
        features.update(bias_features)

        return features

    def _calculate_fvg_features(
        self,
        ict_data: Dict,
        current_price: float,
        atr: float
    ) -> Dict[str, float]:
        """Calculate FVG-related features."""
        fvgs = ict_data.get('fvg', [])

        features = {
            'ict_fvg_count': len(fvgs),
            'ict_fvg_bullish_count': 0,
            'ict_fvg_bearish_count': 0,
            'ict_in_fvg': 0,  # 1 if price is inside an FVG
            'ict_fvg_type': 0,  # 1 bullish, -1 bearish, 0 none
            'ict_nearest_fvg_distance': 0,  # ATR-normalized distance
            'ict_nearest_fvg_type': 0,
            'ict_fvg_support_distance': 0,  # Distance to nearest bullish FVG below
            'ict_fvg_resistance_distance': 0,  # Distance to nearest bearish FVG above
        }

        if not fvgs:
            return features

        bullish_fvgs = [f for f in fvgs if f.get('type') == 'bullish' and not f.get('filled')]
        bearish_fvgs = [f for f in fvgs if f.get('type') == 'bearish' and not f.get('filled')]

        features['ict_fvg_bullish_count'] = len(bullish_fvgs)
        features['ict_fvg_bearish_count'] = len(bearish_fvgs)

        # Check if price is inside any FVG
        nearest_distance = float('inf')
        nearest_type = 0

        for fvg in fvgs:
            if fvg.get('filled'):
                continue

            top = fvg.get('top', 0)
            bottom = fvg.get('bottom', 0)
            fvg_type = 1 if fvg.get('type') == 'bullish' else -1

            # Check if inside FVG
            if bottom <= current_price <= top:
                features['ict_in_fvg'] = 1
                features['ict_fvg_type'] = fvg_type

            # Calculate distance
            if current_price > top:
                distance = current_price - top
            elif current_price < bottom:
                distance = bottom - current_price
            else:
                distance = 0

            if distance < nearest_distance:
                nearest_distance = distance
                nearest_type = fvg_type

        if nearest_distance != float('inf'):
            features['ict_nearest_fvg_distance'] = nearest_distance / atr if atr > 0 else 0
            features['ict_nearest_fvg_type'] = nearest_type

        # Calculate support/resistance distances
        support_fvgs = [f for f in bullish_fvgs if f.get('top', 0) < current_price]
        resistance_fvgs = [f for f in bearish_fvgs if f.get('bottom', 0) > current_price]

        if support_fvgs:
            nearest_support = max(support_fvgs, key=lambda x: x.get('top', 0))
            features['ict_fvg_support_distance'] = (current_price - nearest_support['top']) / atr if atr > 0 else 0

        if resistance_fvgs:
            nearest_resistance = min(resistance_fvgs, key=lambda x: x.get('bottom', 0))
            features['ict_fvg_resistance_distance'] = (nearest_resistance['bottom'] - current_price) / atr if atr > 0 else 0

        return features

    def _calculate_mss_features(
        self,
        ict_data: Dict,
        row_idx: int
    ) -> Dict[str, float]:
        """Calculate MSS-related features."""
        mss_events = ict_data.get('mss', [])

        features = {
            'ict_mss_count': len(mss_events),
            'ict_mss_bullish_count': 0,
            'ict_mss_bearish_count': 0,
            'ict_last_mss_type': 0,  # 1 bullish, -1 bearish
            'ict_last_mss_recency': 0,  # Candles since last MSS (normalized)
            'ict_last_mss_strength': 0,  # Strength of last MSS
        }

        if not mss_events:
            return features

        bullish_mss = [m for m in mss_events if m.get('type') == 'bullish']
        bearish_mss = [m for m in mss_events if m.get('type') == 'bearish']

        features['ict_mss_bullish_count'] = len(bullish_mss)
        features['ict_mss_bearish_count'] = len(bearish_mss)

        # Most recent MSS
        last_mss = mss_events[-1] if mss_events else None
        if last_mss:
            features['ict_last_mss_type'] = 1 if last_mss.get('type') == 'bullish' else -1
            features['ict_last_mss_strength'] = last_mss.get('strength', 0) / 100  # Normalize

            # Calculate recency
            trigger_idx = last_mss.get('trigger_index', row_idx)
            recency = row_idx - trigger_idx
            features['ict_last_mss_recency'] = min(1.0, recency / 20)  # Normalize to max 20 candles

        return features

    def _calculate_ob_features(
        self,
        ict_data: Dict,
        current_price: float,
        atr: float
    ) -> Dict[str, float]:
        """Calculate Order Block features."""
        order_blocks = ict_data.get('order_blocks', [])

        features = {
            'ict_ob_count': len(order_blocks),
            'ict_ob_bullish_count': 0,
            'ict_ob_bearish_count': 0,
            'ict_at_ob': 0,  # 1 if at order block
            'ict_ob_type': 0,  # Type of nearest OB
            'ict_nearest_ob_distance': 0,
            'ict_ob_support_distance': 0,
            'ict_ob_resistance_distance': 0,
        }

        if not order_blocks:
            return features

        # Filter unmitigated order blocks
        active_obs = [ob for ob in order_blocks if not ob.get('mitigated')]

        bullish_obs = [ob for ob in active_obs if ob.get('type') == 'bullish']
        bearish_obs = [ob for ob in active_obs if ob.get('type') == 'bearish']

        features['ict_ob_bullish_count'] = len(bullish_obs)
        features['ict_ob_bearish_count'] = len(bearish_obs)

        nearest_distance = float('inf')
        nearest_type = 0

        for ob in active_obs:
            high = ob.get('high', 0)
            low = ob.get('low', 0)
            ob_type = 1 if ob.get('type') == 'bullish' else -1

            # Check if at order block
            if low <= current_price <= high:
                features['ict_at_ob'] = 1
                features['ict_ob_type'] = ob_type

            # Calculate distance to midpoint
            midpoint = (high + low) / 2
            distance = abs(current_price - midpoint)

            if distance < nearest_distance:
                nearest_distance = distance
                nearest_type = ob_type

        if nearest_distance != float('inf'):
            features['ict_nearest_ob_distance'] = nearest_distance / atr if atr > 0 else 0
            features['ict_ob_type'] = nearest_type

        # Support/Resistance from order blocks
        support_obs = [ob for ob in bullish_obs if ob.get('high', 0) < current_price]
        resistance_obs = [ob for ob in bearish_obs if ob.get('low', 0) > current_price]

        if support_obs:
            nearest = max(support_obs, key=lambda x: x.get('high', 0))
            features['ict_ob_support_distance'] = (current_price - nearest['high']) / atr if atr > 0 else 0

        if resistance_obs:
            nearest = min(resistance_obs, key=lambda x: x.get('low', 0))
            features['ict_ob_resistance_distance'] = (nearest['low'] - current_price) / atr if atr > 0 else 0

        return features

    def _calculate_ote_features(
        self,
        ict_data: Dict,
        current_price: float,
        atr: float
    ) -> Dict[str, float]:
        """Calculate OTE level features."""
        ote_levels = ict_data.get('ote_levels', {})

        features = {
            'ict_ote_distance_50': 0,  # Distance to 50% (equilibrium)
            'ict_ote_distance_62': 0,  # Distance to 62% (primary OTE)
            'ict_ote_distance_705': 0,  # Distance to 70.5%
            'ict_ote_distance_79': 0,  # Distance to 79%
            'ict_ote_in_zone': 0,  # 1 if in OTE zone (62-79%)
            'ict_ote_range': 0,  # Current range size normalized
        }

        bullish_ote = ote_levels.get('bullish', {})
        bearish_ote = ote_levels.get('bearish', {})

        # Use whichever OTE is more relevant based on price position
        if bullish_ote and bearish_ote:
            # Determine which to use based on current price vs equilibrium
            b_eq = bullish_ote.get('levels', {}).get('equilibrium_50', 0)
            if current_price < b_eq:
                ote = bullish_ote
            else:
                ote = bearish_ote
        elif bullish_ote:
            ote = bullish_ote
        elif bearish_ote:
            ote = bearish_ote
        else:
            return features

        levels = ote.get('levels', {})
        range_size = ote.get('range', 0)

        if range_size > 0:
            features['ict_ote_range'] = range_size / atr if atr > 0 else 0

        # Calculate distances to each level
        for level_key, feature_key in [
            ('equilibrium_50', 'ict_ote_distance_50'),
            ('ote_62', 'ict_ote_distance_62'),
            ('ote_705', 'ict_ote_distance_705'),
            ('ote_79', 'ict_ote_distance_79'),
        ]:
            level_price = levels.get(level_key, 0)
            if level_price > 0:
                distance = abs(current_price - level_price) / atr if atr > 0 else 0
                features[feature_key] = distance

        # Check if in OTE zone
        ote_62 = levels.get('ote_62', 0)
        ote_79 = levels.get('ote_79', 0)
        if ote_62 and ote_79:
            if min(ote_62, ote_79) <= current_price <= max(ote_62, ote_79):
                features['ict_ote_in_zone'] = 1

        return features

    def _calculate_premium_discount_features(self, ict_data: Dict) -> Dict[str, float]:
        """Calculate Premium/Discount zone features."""
        pd_zone = ict_data.get('premium_discount', {})

        features = {
            'ict_zone_position': 0,  # -1 deep discount, -0.5 discount, 0.5 premium, 1 deep premium
            'ict_zone_pct': 0.5,  # Position percentage (0-1)
            'ict_zone_bias': 0,  # 1 bullish (discount), -1 bearish (premium)
        }

        if not pd_zone:
            return features

        zone = pd_zone.get('zone', '')
        position_pct = pd_zone.get('position_pct', 50) / 100  # Convert to 0-1

        features['ict_zone_pct'] = position_pct

        zone_values = {
            'deep_discount': -1,
            'discount': -0.5,
            'premium': 0.5,
            'deep_premium': 1
        }
        features['ict_zone_position'] = zone_values.get(zone, 0)

        bias = pd_zone.get('bias', '')
        features['ict_zone_bias'] = 1 if bias == 'bullish' else (-1 if bias == 'bearish' else 0)

        return features

    def _calculate_liquidity_features(
        self,
        ict_data: Dict,
        current_price: float,
        atr: float
    ) -> Dict[str, float]:
        """Calculate Liquidity zone features."""
        liquidity_zones = ict_data.get('liquidity_zones', [])

        features = {
            'ict_liq_above_distance': 0,  # Distance to nearest buy-side liquidity
            'ict_liq_below_distance': 0,  # Distance to nearest sell-side liquidity
            'ict_liq_above_touches': 0,  # Touches at nearest above
            'ict_liq_below_touches': 0,  # Touches at nearest below
            'ict_near_liquidity': 0,  # 1 if near a liquidity zone
        }

        if not liquidity_zones:
            return features

        buy_side = [lz for lz in liquidity_zones if lz.get('type') == 'buy_side' and not lz.get('swept')]
        sell_side = [lz for lz in liquidity_zones if lz.get('type') == 'sell_side' and not lz.get('swept')]

        # Nearest liquidity above (buy-side = stops above resistance)
        liq_above = [lz for lz in buy_side if lz.get('level', 0) > current_price]
        if liq_above:
            nearest = min(liq_above, key=lambda x: x.get('level', float('inf')))
            distance = (nearest['level'] - current_price) / atr if atr > 0 else 0
            features['ict_liq_above_distance'] = distance
            features['ict_liq_above_touches'] = nearest.get('touches', 1) / 10  # Normalize

            if distance < 1:  # Within 1 ATR
                features['ict_near_liquidity'] = 1

        # Nearest liquidity below (sell-side = stops below support)
        liq_below = [lz for lz in sell_side if lz.get('level', 0) < current_price]
        if liq_below:
            nearest = max(liq_below, key=lambda x: x.get('level', 0))
            distance = (current_price - nearest['level']) / atr if atr > 0 else 0
            features['ict_liq_below_distance'] = distance
            features['ict_liq_below_touches'] = nearest.get('touches', 1) / 10

            if distance < 1:
                features['ict_near_liquidity'] = 1

        return features

    def _calculate_market_structure_features(self, ict_data: Dict) -> Dict[str, float]:
        """Calculate Market Structure features."""
        ms = ict_data.get('market_structure', {})

        features = {
            'ict_trend': 0,  # 1 bullish, -1 bearish, 0 neutral
            'ict_hh_count': 0,
            'ict_hl_count': 0,
            'ict_lh_count': 0,
            'ict_ll_count': 0,
            'ict_bullish_score': 0,
            'ict_bearish_score': 0,
            'ict_structure_strength': 0,  # Absolute difference in scores
        }

        if not ms:
            return features

        trend = ms.get('trend', 'neutral')
        features['ict_trend'] = 1 if trend == 'bullish' else (-1 if trend == 'bearish' else 0)

        features['ict_hh_count'] = ms.get('hh_count', 0) / 10  # Normalize
        features['ict_hl_count'] = ms.get('hl_count', 0) / 10
        features['ict_lh_count'] = ms.get('lh_count', 0) / 10
        features['ict_ll_count'] = ms.get('ll_count', 0) / 10

        bullish = ms.get('bullish_score', 0)
        bearish = ms.get('bearish_score', 0)
        total = bullish + bearish

        features['ict_bullish_score'] = bullish / max(total, 1)
        features['ict_bearish_score'] = bearish / max(total, 1)
        features['ict_structure_strength'] = abs(bullish - bearish) / max(total, 1)

        return features

    def _calculate_displacement_features(
        self,
        ict_data: Dict,
        row_idx: int
    ) -> Dict[str, float]:
        """Calculate Displacement features."""
        displacements = ict_data.get('displacement', [])

        features = {
            'ict_disp_count': len(displacements),
            'ict_disp_bullish_count': 0,
            'ict_disp_bearish_count': 0,
            'ict_last_disp_type': 0,
            'ict_last_disp_strength': 0,
            'ict_last_disp_recency': 0,
        }

        if not displacements:
            return features

        bullish = [d for d in displacements if d.get('type') == 'bullish']
        bearish = [d for d in displacements if d.get('type') == 'bearish']

        features['ict_disp_bullish_count'] = len(bullish)
        features['ict_disp_bearish_count'] = len(bearish)

        # Most recent displacement
        last = displacements[-1] if displacements else None
        if last:
            features['ict_last_disp_type'] = 1 if last.get('type') == 'bullish' else -1
            features['ict_last_disp_strength'] = min(1.0, last.get('body_atr_ratio', 0) / 3)  # Normalize

            disp_idx = last.get('index', row_idx)
            recency = row_idx - disp_idx
            features['ict_last_disp_recency'] = min(1.0, recency / 20)

        return features

    def _calculate_session_features(
        self,
        df: pd.DataFrame,
        row_idx: int
    ) -> Dict[str, float]:
        """Calculate Session-related features."""
        features = {
            'ict_session_asia': 0,
            'ict_session_london': 0,
            'ict_session_ny_am': 0,
            'ict_session_ny_pm': 0,
            'ict_session_silver_bullet': 0,
            'ict_session_optimal': 0,
        }

        # Get timestamp
        if isinstance(df.index, pd.DatetimeIndex):
            timestamp = df.index[row_idx]
        else:
            return features

        session = self.session_filter.get_session(timestamp)

        session_mapping = {
            TradingSession.ASIA: 'ict_session_asia',
            TradingSession.LONDON: 'ict_session_london',
            TradingSession.LONDON_NY_OVERLAP: 'ict_session_london',
            TradingSession.NY_AM_KILLZONE: 'ict_session_ny_am',
            TradingSession.NY_PM: 'ict_session_ny_pm',
            TradingSession.SILVER_BULLET_AM: 'ict_session_silver_bullet',
            TradingSession.SILVER_BULLET_PM: 'ict_session_silver_bullet',
        }

        if session in session_mapping:
            features[session_mapping[session]] = 1

        # Check if optimal
        is_optimal, _, _ = self.session_filter.is_optimal_time(timestamp)
        features['ict_session_optimal'] = 1 if is_optimal else 0

        return features

    def _calculate_bias_features(self, ict_data: Dict) -> Dict[str, float]:
        """Calculate combined ICT bias features."""
        features = {
            'ict_bias': 0,  # Combined bias: -1 to 1
            'ict_bias_confidence': 0,  # Confidence: 0-1
        }

        # Calculate from market structure and premium/discount
        ms = ict_data.get('market_structure', {})
        pd_zone = ict_data.get('premium_discount', {})

        bullish_points = 0
        bearish_points = 0

        # Market structure contribution
        if ms.get('trend') == 'bullish':
            bullish_points += 2
        elif ms.get('trend') == 'bearish':
            bearish_points += 2

        # Zone contribution
        zone = pd_zone.get('zone', '')
        if zone in ['discount', 'deep_discount']:
            bullish_points += 1
        elif zone in ['premium', 'deep_premium']:
            bearish_points += 1

        # Recent MSS contribution
        mss = ict_data.get('mss', [])
        if mss:
            last_mss = mss[-1]
            if last_mss.get('type') == 'bullish':
                bullish_points += 1
            else:
                bearish_points += 1

        total = bullish_points + bearish_points
        if total > 0:
            features['ict_bias'] = (bullish_points - bearish_points) / total
            features['ict_bias_confidence'] = abs(bullish_points - bearish_points) / total

        return features

    def _calculate_atr(self, df: pd.DataFrame, row_idx: int, period: int = 14) -> float:
        """Calculate ATR at a specific row."""
        if row_idx < period:
            return float(df['close'].iloc[row_idx] * 0.02)  # 2% fallback

        slice_df = df.iloc[max(0, row_idx - period):row_idx + 1]

        high = slice_df['high']
        low = slice_df['low']
        close = slice_df['close'].shift(1)

        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.mean()

        return float(atr) if not pd.isna(atr) else float(df['close'].iloc[row_idx] * 0.02)

    def _empty_features(self) -> Dict[str, float]:
        """Return dictionary of empty features."""
        return {
            # FVG features
            'ict_fvg_count': 0,
            'ict_fvg_bullish_count': 0,
            'ict_fvg_bearish_count': 0,
            'ict_in_fvg': 0,
            'ict_fvg_type': 0,
            'ict_nearest_fvg_distance': 0,
            'ict_nearest_fvg_type': 0,
            'ict_fvg_support_distance': 0,
            'ict_fvg_resistance_distance': 0,
            # MSS features
            'ict_mss_count': 0,
            'ict_mss_bullish_count': 0,
            'ict_mss_bearish_count': 0,
            'ict_last_mss_type': 0,
            'ict_last_mss_recency': 0,
            'ict_last_mss_strength': 0,
            # OB features
            'ict_ob_count': 0,
            'ict_ob_bullish_count': 0,
            'ict_ob_bearish_count': 0,
            'ict_at_ob': 0,
            'ict_ob_type': 0,
            'ict_nearest_ob_distance': 0,
            'ict_ob_support_distance': 0,
            'ict_ob_resistance_distance': 0,
            # OTE features
            'ict_ote_distance_50': 0,
            'ict_ote_distance_62': 0,
            'ict_ote_distance_705': 0,
            'ict_ote_distance_79': 0,
            'ict_ote_in_zone': 0,
            'ict_ote_range': 0,
            # Zone features
            'ict_zone_position': 0,
            'ict_zone_pct': 0.5,
            'ict_zone_bias': 0,
            # Liquidity features
            'ict_liq_above_distance': 0,
            'ict_liq_below_distance': 0,
            'ict_liq_above_touches': 0,
            'ict_liq_below_touches': 0,
            'ict_near_liquidity': 0,
            # Structure features
            'ict_trend': 0,
            'ict_hh_count': 0,
            'ict_hl_count': 0,
            'ict_lh_count': 0,
            'ict_ll_count': 0,
            'ict_bullish_score': 0,
            'ict_bearish_score': 0,
            'ict_structure_strength': 0,
            # Displacement features
            'ict_disp_count': 0,
            'ict_disp_bullish_count': 0,
            'ict_disp_bearish_count': 0,
            'ict_last_disp_type': 0,
            'ict_last_disp_strength': 0,
            'ict_last_disp_recency': 0,
            # Session features
            'ict_session_asia': 0,
            'ict_session_london': 0,
            'ict_session_ny_am': 0,
            'ict_session_ny_pm': 0,
            'ict_session_silver_bullet': 0,
            'ict_session_optimal': 0,
            # Bias features
            'ict_bias': 0,
            'ict_bias_confidence': 0,
        }

    def _add_empty_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add empty feature columns to DataFrame."""
        df = df.copy()
        for feature_name, value in self._empty_features().items():
            df[feature_name] = value
        return df

    def get_feature_names(self) -> List[str]:
        """Get list of all ICT feature names."""
        return list(self._empty_features().keys())
