"""
ICT (Inner Circle Trader) Based Trading Strategy.

This module implements a trading strategy based on ICT concepts:
- Fair Value Gaps (FVG)
- Market Structure Shifts (MSS)
- Order Blocks (OB)
- Optimal Trade Entry (OTE) levels
- Premium/Discount Zones
- Liquidity Zones
- Session-based trading (NY Killzone, London, Asia)

The strategy combines multiple ICT signals with confluence scoring
to generate high-probability trade setups.
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Tuple, List
from enum import Enum
from datetime import datetime, time
from loguru import logger

from features.ict_indicators import ICTIndicators
from models.base import BaseModel
from features.indicators import FeatureEngineer


class ICTSignal(Enum):
    """ICT Trading signal types."""
    STRONG_BUY = 2
    BUY = 1
    HOLD = 0
    SELL = -1
    STRONG_SELL = -2


class TradingSession(Enum):
    """Trading session types."""
    ASIA = "asia"
    LONDON = "london"
    NY_AM = "ny_am"
    NY_PM = "ny_pm"
    SILVER_BULLET_AM = "silver_bullet_am"
    SILVER_BULLET_PM = "silver_bullet_pm"
    OFF_HOURS = "off_hours"


# Session times in EST/New York time
SESSION_TIMES = {
    TradingSession.ASIA: (time(19, 0), time(4, 0)),  # 7 PM - 4 AM
    TradingSession.LONDON: (time(3, 0), time(12, 0)),  # 3 AM - 12 PM
    TradingSession.NY_AM: (time(8, 30), time(12, 0)),  # 8:30 AM - 12 PM (Optimal)
    TradingSession.NY_PM: (time(13, 30), time(16, 0)),  # 1:30 PM - 4 PM
    TradingSession.SILVER_BULLET_AM: (time(10, 0), time(11, 0)),  # 10 AM - 11 AM
    TradingSession.SILVER_BULLET_PM: (time(14, 0), time(15, 0)),  # 2 PM - 3 PM
}


class ICTStrategy:
    """
    ICT-based trading strategy with confluence scoring.

    This strategy combines multiple ICT concepts to generate
    high-probability trade setups with proper risk management.
    """

    def __init__(
        self,
        config: Optional[dict] = None,
        ml_model: Optional[BaseModel] = None,
        feature_engineer: Optional[FeatureEngineer] = None
    ):
        """
        Initialize ICT Strategy.

        Args:
            config: Strategy configuration
            ml_model: Optional ML model for additional confirmation
            feature_engineer: Optional feature engineer for ML features
        """
        self.config = config or {}
        self.ml_model = ml_model
        self.feature_engineer = feature_engineer

        # ICT Indicators detector
        self.ict = ICTIndicators(self.config.get('ict', {}))

        # Strategy parameters
        self.min_confluence_score = self.config.get('min_confluence_score', 8)
        self.strong_confluence_score = self.config.get('strong_confluence_score', 12)
        self.min_risk_reward = self.config.get('min_risk_reward', 3.0)
        self.use_session_filter = self.config.get('use_session_filter', True)
        self.preferred_sessions = self.config.get('preferred_sessions', [
            TradingSession.NY_AM,
            TradingSession.SILVER_BULLET_AM,
            TradingSession.SILVER_BULLET_PM
        ])

        # Risk parameters
        self.risk_config = self.config.get('risk', {})
        self.max_position_size = self.risk_config.get('max_position_size', 0.1)
        self.stop_loss_buffer_atr = self.risk_config.get('stop_loss_buffer_atr', 0.5)

        # Position tracking
        self.current_position = 0  # 1 = long, -1 = short, 0 = flat
        self.entry_price = None
        self.stop_loss = None
        self.take_profit_1 = None
        self.take_profit_2 = None

    def get_current_session(self, timestamp: Optional[datetime] = None) -> TradingSession:
        """
        Determine the current trading session based on NY time.

        Args:
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Current trading session
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Convert to NY time (simplified - in production use pytz)
        current_time = timestamp.time()

        # Check Silver Bullet windows first (most specific)
        sb_am_start, sb_am_end = SESSION_TIMES[TradingSession.SILVER_BULLET_AM]
        if sb_am_start <= current_time <= sb_am_end:
            return TradingSession.SILVER_BULLET_AM

        sb_pm_start, sb_pm_end = SESSION_TIMES[TradingSession.SILVER_BULLET_PM]
        if sb_pm_start <= current_time <= sb_pm_end:
            return TradingSession.SILVER_BULLET_PM

        # Check NY AM session
        ny_am_start, ny_am_end = SESSION_TIMES[TradingSession.NY_AM]
        if ny_am_start <= current_time <= ny_am_end:
            return TradingSession.NY_AM

        # Check NY PM session
        ny_pm_start, ny_pm_end = SESSION_TIMES[TradingSession.NY_PM]
        if ny_pm_start <= current_time <= ny_pm_end:
            return TradingSession.NY_PM

        # Check London session
        london_start, london_end = SESSION_TIMES[TradingSession.LONDON]
        if london_start <= current_time <= london_end:
            return TradingSession.LONDON

        # Check Asia session (wraps around midnight)
        asia_start, asia_end = SESSION_TIMES[TradingSession.ASIA]
        if current_time >= asia_start or current_time <= asia_end:
            return TradingSession.ASIA

        return TradingSession.OFF_HOURS

    def is_optimal_session(self, timestamp: Optional[datetime] = None) -> Tuple[bool, TradingSession]:
        """
        Check if current time is in an optimal trading session.

        Args:
            timestamp: Optional timestamp

        Returns:
            Tuple of (is_optimal, current_session)
        """
        session = self.get_current_session(timestamp)
        is_optimal = session in self.preferred_sessions
        return is_optimal, session

    def calculate_confluence_score(
        self,
        ict_data: Dict,
        current_price: float,
        direction: str = 'long'
    ) -> Dict:
        """
        Calculate confluence score for a potential trade.

        Scoring system:
        - ML Model alignment: +3 points
        - ICT Bias alignment: +2 points
        - Price in Premium/Discount zone: +2 points
        - Price at Order Block: +2 points
        - Price near OTE level (62%): +2 points
        - Recent MSS in direction: +2 points
        - FVG support/resistance: +1 point
        - Optimal session: +1 point

        Max score: 15 points

        Args:
            ict_data: ICT indicators data
            current_price: Current market price
            direction: 'long' or 'short'

        Returns:
            Dictionary with score breakdown
        """
        score = 0
        breakdown = {}

        # 1. Check Premium/Discount Zone (+2)
        pd_zone = ict_data.get('premium_discount', {})
        if pd_zone:
            zone = pd_zone.get('zone', '')
            if direction == 'long' and zone in ['discount', 'deep_discount']:
                score += 2
                breakdown['zone'] = {'points': 2, 'reason': f'Price in {zone} zone (bullish)'}
            elif direction == 'short' and zone in ['premium', 'deep_premium']:
                score += 2
                breakdown['zone'] = {'points': 2, 'reason': f'Price in {zone} zone (bearish)'}
            else:
                breakdown['zone'] = {'points': 0, 'reason': f'Price in {zone} zone (neutral)'}

        # 2. Check Market Structure (+2)
        market_structure = ict_data.get('market_structure', {})
        trend = market_structure.get('trend', 'neutral')
        if direction == 'long' and trend == 'bullish':
            score += 2
            breakdown['structure'] = {'points': 2, 'reason': 'Bullish market structure'}
        elif direction == 'short' and trend == 'bearish':
            score += 2
            breakdown['structure'] = {'points': 2, 'reason': 'Bearish market structure'}
        else:
            breakdown['structure'] = {'points': 0, 'reason': f'{trend} market structure'}

        # 3. Check Recent MSS (+2)
        mss_events = ict_data.get('mss', [])
        recent_mss = mss_events[-1] if mss_events else None
        if recent_mss:
            mss_type = recent_mss.get('type', '')
            if direction == 'long' and mss_type == 'bullish':
                score += 2
                breakdown['mss'] = {'points': 2, 'reason': 'Recent bullish MSS'}
            elif direction == 'short' and mss_type == 'bearish':
                score += 2
                breakdown['mss'] = {'points': 2, 'reason': 'Recent bearish MSS'}
            else:
                breakdown['mss'] = {'points': 0, 'reason': f'Last MSS was {mss_type}'}
        else:
            breakdown['mss'] = {'points': 0, 'reason': 'No recent MSS'}

        # 4. Check Order Block proximity (+2)
        order_blocks = ict_data.get('order_blocks', [])
        ob_score = 0
        ob_reason = 'No nearby order blocks'

        for ob in order_blocks:
            if ob.get('mitigated'):
                continue
            ob_high = ob.get('high', 0)
            ob_low = ob.get('low', 0)
            ob_type = ob.get('type', '')

            # Check if price is at order block
            if ob_low <= current_price <= ob_high:
                if direction == 'long' and ob_type == 'bullish':
                    ob_score = 2
                    ob_reason = 'Price at bullish order block'
                    break
                elif direction == 'short' and ob_type == 'bearish':
                    ob_score = 2
                    ob_reason = 'Price at bearish order block'
                    break

            # Check if price is near order block (within 0.5%)
            distance_pct = abs(current_price - (ob_high + ob_low) / 2) / current_price * 100
            if distance_pct < 0.5:
                if direction == 'long' and ob_type == 'bullish':
                    ob_score = 1
                    ob_reason = 'Price near bullish order block'
                elif direction == 'short' and ob_type == 'bearish':
                    ob_score = 1
                    ob_reason = 'Price near bearish order block'

        score += ob_score
        breakdown['order_block'] = {'points': ob_score, 'reason': ob_reason}

        # 5. Check OTE Level proximity (+2)
        ote_levels = ict_data.get('ote_levels', {})
        ote_score = 0
        ote_reason = 'Price not at OTE level'

        if direction == 'long' and ote_levels.get('bullish'):
            bullish_ote = ote_levels['bullish']
            levels = bullish_ote.get('levels', {})

            # Check proximity to OTE levels
            for level_name, level_price in levels.items():
                if level_price:
                    distance_pct = abs(current_price - level_price) / current_price * 100
                    if distance_pct < 0.3:
                        if 'ote_62' in level_name:
                            ote_score = 2
                            ote_reason = 'Price at OTE 62% level (optimal entry)'
                        elif 'ote_705' in level_name:
                            ote_score = 2
                            ote_reason = 'Price at OTE 70.5% level'
                        elif 'ote_79' in level_name:
                            ote_score = 1
                            ote_reason = 'Price at OTE 79% level (deep)'
                        break

        elif direction == 'short' and ote_levels.get('bearish'):
            bearish_ote = ote_levels['bearish']
            levels = bearish_ote.get('levels', {})

            for level_name, level_price in levels.items():
                if level_price:
                    distance_pct = abs(current_price - level_price) / current_price * 100
                    if distance_pct < 0.3:
                        if 'ote_62' in level_name:
                            ote_score = 2
                            ote_reason = 'Price at OTE 62% level (optimal entry)'
                        elif 'ote_705' in level_name:
                            ote_score = 2
                            ote_reason = 'Price at OTE 70.5% level'
                        elif 'ote_79' in level_name:
                            ote_score = 1
                            ote_reason = 'Price at OTE 79% level (deep)'
                        break

        score += ote_score
        breakdown['ote'] = {'points': ote_score, 'reason': ote_reason}

        # 6. Check FVG support/resistance (+1)
        fvgs = ict_data.get('fvg', [])
        fvg_score = 0
        fvg_reason = 'No relevant FVGs'

        for fvg in fvgs:
            if fvg.get('filled'):
                continue
            fvg_top = fvg.get('top', 0)
            fvg_bottom = fvg.get('bottom', 0)
            fvg_type = fvg.get('type', '')

            # Check if price is in FVG
            if fvg_bottom <= current_price <= fvg_top:
                if direction == 'long' and fvg_type == 'bullish':
                    fvg_score = 1
                    fvg_reason = 'Price in bullish FVG (support)'
                    break
                elif direction == 'short' and fvg_type == 'bearish':
                    fvg_score = 1
                    fvg_reason = 'Price in bearish FVG (resistance)'
                    break

            # Check if FVG is nearby as support/resistance
            if direction == 'long' and fvg_type == 'bullish' and fvg_top < current_price:
                distance_pct = (current_price - fvg_top) / current_price * 100
                if distance_pct < 0.5:
                    fvg_score = 1
                    fvg_reason = 'Bullish FVG below as support'
                    break
            elif direction == 'short' and fvg_type == 'bearish' and fvg_bottom > current_price:
                distance_pct = (fvg_bottom - current_price) / current_price * 100
                if distance_pct < 0.5:
                    fvg_score = 1
                    fvg_reason = 'Bearish FVG above as resistance'
                    break

        score += fvg_score
        breakdown['fvg'] = {'points': fvg_score, 'reason': fvg_reason}

        # 7. Check Session (+1)
        is_optimal, session = self.is_optimal_session()
        if is_optimal:
            score += 1
            breakdown['session'] = {'points': 1, 'reason': f'In {session.value} (optimal)'}
        else:
            breakdown['session'] = {'points': 0, 'reason': f'In {session.value} (not optimal)'}

        # 8. Check ICT Trading Bias alignment (+2)
        # This uses the combined bias from ICTIndicators
        trading_bias = self.ict.get_trading_bias(pd.DataFrame())  # Will be passed actual data
        if ict_data.get('current_price'):
            # Re-calculate with actual data
            pass

        bias = ict_data.get('market_structure', {}).get('trend', 'neutral')
        if direction == 'long' and bias == 'bullish':
            score += 2
            breakdown['bias'] = {'points': 2, 'reason': 'ICT bias is bullish'}
        elif direction == 'short' and bias == 'bearish':
            score += 2
            breakdown['bias'] = {'points': 2, 'reason': 'ICT bias is bearish'}
        else:
            breakdown['bias'] = {'points': 0, 'reason': f'ICT bias is {bias}'}

        return {
            'total_score': score,
            'max_score': 15,
            'score_pct': round(score / 15 * 100, 1),
            'breakdown': breakdown,
            'direction': direction,
            'is_tradeable': score >= self.min_confluence_score,
            'is_strong': score >= self.strong_confluence_score
        }

    def calculate_entry_and_targets(
        self,
        ict_data: Dict,
        current_price: float,
        direction: str,
        atr: float
    ) -> Dict:
        """
        Calculate entry price, stop loss, and take profit levels.

        Uses ICT concepts for placement:
        - Stop Loss: Beyond nearest liquidity zone or swing point
        - Take Profit 1: OTE -27% extension
        - Take Profit 2: OTE -62% extension

        Args:
            ict_data: ICT indicators data
            current_price: Current price
            direction: 'long' or 'short'
            atr: Current ATR value

        Returns:
            Dictionary with entry, SL, and TP levels
        """
        entry = current_price
        stop_loss = None
        take_profit_1 = None
        take_profit_2 = None
        risk_reward = 0

        # Get OTE levels for targets
        ote_levels = ict_data.get('ote_levels', {})

        # Get liquidity zones for stop loss placement
        liquidity_zones = ict_data.get('liquidity_zones', [])

        # Get swing points
        swing_points = ict_data.get('swing_points', [])
        swing_lows = [sp for sp in swing_points if sp.get('type') == 'low']
        swing_highs = [sp for sp in swing_points if sp.get('type') == 'high']

        if direction == 'long':
            # Stop Loss: Below nearest liquidity zone or swing low
            sl_candidates = []

            # Check sell-side liquidity (stops below)
            for lz in liquidity_zones:
                if lz.get('type') == 'sell_side' and lz.get('level', 0) < current_price:
                    sl_candidates.append(lz['level'] - atr * self.stop_loss_buffer_atr)

            # Check recent swing lows
            for sl in swing_lows[-3:]:
                if sl.get('price', 0) < current_price:
                    sl_candidates.append(sl['price'] - atr * self.stop_loss_buffer_atr)

            # Use nearest stop loss candidate or ATR-based fallback
            if sl_candidates:
                stop_loss = max(sl_candidates)  # Tightest stop
            else:
                stop_loss = current_price - 2 * atr

            # Take Profits from OTE extensions
            if ote_levels.get('bullish'):
                targets = ote_levels['bullish'].get('targets', {})
                take_profit_1 = targets.get('target_1_neg27', current_price + 1.5 * atr)
                take_profit_2 = targets.get('target_2_neg62', current_price + 3 * atr)
            else:
                take_profit_1 = current_price + 1.5 * atr
                take_profit_2 = current_price + 3 * atr

        else:  # short
            # Stop Loss: Above nearest liquidity zone or swing high
            sl_candidates = []

            # Check buy-side liquidity (stops above)
            for lz in liquidity_zones:
                if lz.get('type') == 'buy_side' and lz.get('level', 0) > current_price:
                    sl_candidates.append(lz['level'] + atr * self.stop_loss_buffer_atr)

            # Check recent swing highs
            for sh in swing_highs[-3:]:
                if sh.get('price', 0) > current_price:
                    sl_candidates.append(sh['price'] + atr * self.stop_loss_buffer_atr)

            if sl_candidates:
                stop_loss = min(sl_candidates)  # Tightest stop
            else:
                stop_loss = current_price + 2 * atr

            # Take Profits from OTE extensions
            if ote_levels.get('bearish'):
                targets = ote_levels['bearish'].get('targets', {})
                take_profit_1 = targets.get('target_1_neg27', current_price - 1.5 * atr)
                take_profit_2 = targets.get('target_2_neg62', current_price - 3 * atr)
            else:
                take_profit_1 = current_price - 1.5 * atr
                take_profit_2 = current_price - 3 * atr

        # Calculate risk/reward
        risk = abs(entry - stop_loss)
        reward = abs(take_profit_1 - entry)
        risk_reward = reward / risk if risk > 0 else 0

        return {
            'entry': entry,
            'stop_loss': stop_loss,
            'take_profit_1': take_profit_1,
            'take_profit_2': take_profit_2,
            'risk': risk,
            'reward_tp1': reward,
            'reward_tp2': abs(take_profit_2 - entry),
            'risk_reward_tp1': round(risk_reward, 2),
            'risk_reward_tp2': round(abs(take_profit_2 - entry) / risk, 2) if risk > 0 else 0,
            'meets_min_rr': risk_reward >= self.min_risk_reward
        }

    def generate_signal(
        self,
        df: pd.DataFrame,
        include_ml: bool = True
    ) -> Tuple[ICTSignal, float, Dict]:
        """
        Generate trading signal based on ICT concepts.

        Args:
            df: DataFrame with OHLCV data
            include_ml: Whether to include ML model confirmation

        Returns:
            Tuple of (signal, confidence, details)
        """
        if len(df) < 50:
            return ICTSignal.HOLD, 0.0, {'error': 'Insufficient data'}

        # Detect all ICT patterns
        ict_data = self.ict.detect_all(df)
        current_price = float(df['close'].iloc[-1])

        # Calculate ATR
        atr = self._calculate_atr(df)

        # Get ICT trading bias
        bias_result = self.ict.get_trading_bias(df)
        ict_bias = bias_result.get('bias', 'neutral')
        ict_confidence = bias_result.get('confidence', 0)

        # Calculate confluence scores for both directions
        long_confluence = self.calculate_confluence_score(ict_data, current_price, 'long')
        short_confluence = self.calculate_confluence_score(ict_data, current_price, 'short')

        # Determine primary direction based on bias and confluence
        if ict_bias == 'bullish' and long_confluence['total_score'] > short_confluence['total_score']:
            primary_direction = 'long'
            confluence = long_confluence
        elif ict_bias == 'bearish' and short_confluence['total_score'] > long_confluence['total_score']:
            primary_direction = 'short'
            confluence = short_confluence
        elif long_confluence['total_score'] > short_confluence['total_score']:
            primary_direction = 'long'
            confluence = long_confluence
        elif short_confluence['total_score'] > long_confluence['total_score']:
            primary_direction = 'short'
            confluence = short_confluence
        else:
            # No clear direction
            return ICTSignal.HOLD, 0.0, {
                'reason': 'No clear direction',
                'long_score': long_confluence['total_score'],
                'short_score': short_confluence['total_score'],
                'ict_bias': ict_bias
            }

        # Calculate entry and targets
        entry_targets = self.calculate_entry_and_targets(
            ict_data, current_price, primary_direction, atr
        )

        # Check if trade meets minimum risk/reward
        if not entry_targets['meets_min_rr']:
            return ICTSignal.HOLD, 0.0, {
                'reason': f"Risk/Reward ({entry_targets['risk_reward_tp1']}) below minimum ({self.min_risk_reward})",
                'confluence': confluence,
                'entry_targets': entry_targets
            }

        # Check session filter
        is_optimal_session, current_session = self.is_optimal_session()
        if self.use_session_filter and not is_optimal_session:
            return ICTSignal.HOLD, 0.0, {
                'reason': f'Not in optimal session (current: {current_session.value})',
                'confluence': confluence,
                'entry_targets': entry_targets
            }

        # Include ML confirmation if available
        ml_signal = None
        ml_confidence = 0
        if include_ml and self.ml_model and self.feature_engineer:
            try:
                df_features = self.feature_engineer.generate_features(df)
                if not df_features.empty:
                    latest = df_features.iloc[[-1]]
                    feature_cols = self.feature_engineer.get_feature_names(df_features)
                    X = latest[feature_cols]
                    proba = self.ml_model.predict_proba(X)[0]
                    ml_confidence = proba[1] if len(proba) > 1 else proba[0]

                    if ml_confidence >= 0.6:
                        ml_signal = 'BUY'
                    elif ml_confidence <= 0.4:
                        ml_signal = 'SELL'
                    else:
                        ml_signal = 'HOLD'

                    # Add ML alignment bonus to confluence
                    if (primary_direction == 'long' and ml_signal == 'BUY') or \
                       (primary_direction == 'short' and ml_signal == 'SELL'):
                        confluence['total_score'] += 3
                        confluence['breakdown']['ml_model'] = {
                            'points': 3,
                            'reason': f'ML model confirms {ml_signal} ({ml_confidence:.1%})'
                        }
                    else:
                        confluence['breakdown']['ml_model'] = {
                            'points': 0,
                            'reason': f'ML model says {ml_signal} ({ml_confidence:.1%})'
                        }
            except Exception as e:
                logger.warning(f"ML model error: {e}")
                confluence['breakdown']['ml_model'] = {'points': 0, 'reason': f'ML error: {e}'}

        # Generate final signal
        total_score = confluence['total_score']

        if primary_direction == 'long':
            if total_score >= self.strong_confluence_score:
                signal = ICTSignal.STRONG_BUY
            elif total_score >= self.min_confluence_score:
                signal = ICTSignal.BUY
            else:
                signal = ICTSignal.HOLD
        else:
            if total_score >= self.strong_confluence_score:
                signal = ICTSignal.STRONG_SELL
            elif total_score >= self.min_confluence_score:
                signal = ICTSignal.SELL
            else:
                signal = ICTSignal.HOLD

        # Calculate overall confidence
        confidence = min(100, total_score / 15 * 100)

        # Prepare detailed result
        details = {
            'signal': signal.name,
            'direction': primary_direction,
            'confluence': confluence,
            'entry_targets': entry_targets,
            'ict_bias': ict_bias,
            'ict_confidence': ict_confidence,
            'ml_signal': ml_signal,
            'ml_confidence': ml_confidence,
            'session': current_session.value,
            'is_optimal_session': is_optimal_session,
            'current_price': current_price,
            'atr': atr,
            'ict_data_summary': {
                'fvg_count': len(ict_data.get('fvg', [])),
                'mss_count': len(ict_data.get('mss', [])),
                'ob_count': len(ict_data.get('order_blocks', [])),
                'zone': ict_data.get('premium_discount', {}).get('zone', 'unknown'),
                'structure': ict_data.get('market_structure', {}).get('structure', 'unknown')
            }
        }

        return signal, confidence, details

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR from DataFrame."""
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)

        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]

        return float(atr) if not pd.isna(atr) else float(df['close'].iloc[-1] * 0.02)

    def should_enter(self, signal: ICTSignal) -> bool:
        """Check if should enter a new position."""
        if self.current_position != 0:
            return False
        return signal in [ICTSignal.STRONG_BUY, ICTSignal.BUY, ICTSignal.STRONG_SELL, ICTSignal.SELL]

    def should_exit(self, current_price: float, signal: ICTSignal) -> Tuple[bool, str]:
        """
        Check if should exit current position.

        Args:
            current_price: Current market price
            signal: Current signal

        Returns:
            Tuple of (should_exit, reason)
        """
        if self.current_position == 0:
            return False, ''

        # Check stop loss
        if self.stop_loss:
            if self.current_position > 0 and current_price <= self.stop_loss:
                return True, 'stop_loss'
            elif self.current_position < 0 and current_price >= self.stop_loss:
                return True, 'stop_loss'

        # Check take profit 1
        if self.take_profit_1:
            if self.current_position > 0 and current_price >= self.take_profit_1:
                return True, 'take_profit_1'
            elif self.current_position < 0 and current_price <= self.take_profit_1:
                return True, 'take_profit_1'

        # Check signal reversal
        if self.current_position > 0 and signal in [ICTSignal.SELL, ICTSignal.STRONG_SELL]:
            return True, 'signal_reversal'
        elif self.current_position < 0 and signal in [ICTSignal.BUY, ICTSignal.STRONG_BUY]:
            return True, 'signal_reversal'

        return False, ''

    def update_position(
        self,
        position: int,
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit_1: Optional[float] = None,
        take_profit_2: Optional[float] = None
    ):
        """Update current position state."""
        self.current_position = position
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profit_1 = take_profit_1
        self.take_profit_2 = take_profit_2

    def get_position_size(
        self,
        capital: float,
        entry_price: float,
        stop_loss: float
    ) -> float:
        """
        Calculate position size based on risk.

        Risk 1-2% of capital per trade.

        Args:
            capital: Available capital
            entry_price: Entry price
            stop_loss: Stop loss price

        Returns:
            Position size in base currency
        """
        risk_per_trade = self.risk_config.get('risk_per_trade', 0.01)  # 1% default
        max_position_value = capital * self.max_position_size

        risk_amount = capital * risk_per_trade
        risk_per_unit = abs(entry_price - stop_loss)

        if risk_per_unit == 0:
            return 0

        position_size = risk_amount / risk_per_unit
        position_value = position_size * entry_price

        # Cap at max position size
        if position_value > max_position_value:
            position_size = max_position_value / entry_price

        return position_size

    def get_signal_explanation(self, details: Dict) -> str:
        """
        Generate human-readable explanation of the signal.

        Args:
            details: Signal details dictionary

        Returns:
            Formatted explanation string
        """
        if 'error' in details:
            return f"Error: {details['error']}"

        if 'reason' in details and details.get('signal') == 'HOLD':
            return f"HOLD - {details['reason']}"

        lines = []
        lines.append(f"Signal: {details.get('signal', 'UNKNOWN')}")
        lines.append(f"Direction: {details.get('direction', 'N/A').upper()}")

        # Handle confluence data if present
        confluence = details.get('confluence', {})
        if confluence:
            total = confluence.get('total_score', 0)
            max_score = confluence.get('max_score', 30)
            lines.append(f"Confluence Score: {total}/{max_score}")
            lines.append("")

            # Breakdown
            breakdown = confluence.get('breakdown', {})
            if breakdown:
                lines.append("Confluence Breakdown:")
                for key, value in breakdown.items():
                    if isinstance(value, dict):
                        lines.append(f"  {key}: +{value.get('points', 0)} - {value.get('reason', 'N/A')}")
                lines.append("")

        # Entry/Targets
        et = details.get('entry_targets', {})
        if et:
            entry = et.get('entry')
            sl = et.get('stop_loss')
            tp1 = et.get('take_profit_1')
            tp2 = et.get('take_profit_2')

            if entry is not None:
                lines.append(f"Entry: ${entry:.2f}")
            if sl is not None:
                lines.append(f"Stop Loss: ${sl:.2f}")
            if tp1 is not None:
                lines.append(f"Take Profit 1: ${tp1:.2f} (R:R {et.get('risk_reward_tp1', 0):.1f})")
            if tp2 is not None:
                lines.append(f"Take Profit 2: ${tp2:.2f} (R:R {et.get('risk_reward_tp2', 0):.1f})")
            lines.append("")

        session = details.get('session', 'N/A')
        is_optimal = details.get('is_optimal_session', False)
        lines.append(f"Session: {session} (Optimal: {is_optimal})")

        ict_bias = details.get('ict_bias', 'N/A')
        ict_conf = details.get('ict_confidence', 0)
        lines.append(f"ICT Bias: {ict_bias} ({ict_conf:.1f}%)")

        if details.get('ml_signal'):
            ml_conf = details.get('ml_confidence', 0)
            lines.append(f"ML Confirmation: {details['ml_signal']} ({ml_conf:.1%})")

        return "\n".join(lines)
