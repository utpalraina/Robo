"""
ICT Confluence Detection System.

This module implements a sophisticated confluence scoring system
that combines multiple ICT signals to identify high-probability
trade setups.

Confluence Factors:
1. Market Structure (trend direction)
2. Premium/Discount Zone position
3. Order Block proximity
4. Fair Value Gap alignment
5. OTE Level proximity
6. Market Structure Shift confirmation
7. Liquidity Zone awareness
8. Displacement confirmation
9. Session timing
10. ML Model alignment (optional)

Scoring System:
- Each factor contributes 0-3 points
- Total max score: 30 points
- Strong signal: >= 20 points (66%+)
- Tradeable signal: >= 15 points (50%+)
- Weak signal: >= 10 points (33%+)
- No trade: < 10 points
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from loguru import logger


class ConfluenceStrength(Enum):
    """Confluence strength levels."""
    VERY_STRONG = "very_strong"  # >= 25 points (83%+)
    STRONG = "strong"  # >= 20 points (66%+)
    MODERATE = "moderate"  # >= 15 points (50%+)
    WEAK = "weak"  # >= 10 points (33%+)
    NONE = "none"  # < 10 points


@dataclass
class ConfluenceFactor:
    """Represents a single confluence factor."""
    name: str
    points: int
    max_points: int
    reason: str
    category: str  # 'structure', 'zone', 'level', 'timing', 'confirmation'
    is_aligned: bool = False


@dataclass
class ConfluenceResult:
    """Complete confluence analysis result."""
    direction: str  # 'long' or 'short'
    total_score: int
    max_score: int
    score_pct: float
    strength: ConfluenceStrength
    factors: List[ConfluenceFactor]
    is_tradeable: bool
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward_1: float
    risk_reward_2: float
    explanation: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'direction': self.direction,
            'total_score': self.total_score,
            'max_score': self.max_score,
            'score_pct': self.score_pct,
            'strength': self.strength.value,
            'factors': [
                {
                    'name': f.name,
                    'points': f.points,
                    'max_points': f.max_points,
                    'reason': f.reason,
                    'category': f.category,
                    'is_aligned': f.is_aligned
                }
                for f in self.factors
            ],
            'is_tradeable': self.is_tradeable,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit_1': self.take_profit_1,
            'take_profit_2': self.take_profit_2,
            'risk_reward_1': self.risk_reward_1,
            'risk_reward_2': self.risk_reward_2,
            'explanation': self.explanation,
            'timestamp': self.timestamp.isoformat()
        }


class ConfluenceDetector:
    """
    ICT Confluence Detection and Scoring System.

    Analyzes multiple ICT factors and calculates a confluence score
    to determine trade probability and optimal entry/exit levels.
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize Confluence Detector.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}

        # Scoring thresholds
        self.very_strong_threshold = self.config.get('very_strong_threshold', 25)  # 83%
        self.strong_threshold = self.config.get('strong_threshold', 20)  # 66%
        self.moderate_threshold = self.config.get('moderate_threshold', 15)  # 50%
        self.weak_threshold = self.config.get('weak_threshold', 10)  # 33%

        # Trade filters
        self.min_tradeable_score = self.config.get('min_tradeable_score', 15)
        self.min_risk_reward = self.config.get('min_risk_reward', 2.0)

        # Factor weights (max points per factor)
        self.weights = {
            'market_structure': 3,
            'premium_discount': 3,
            'order_block': 3,
            'fvg': 2,
            'ote_level': 3,
            'mss': 3,
            'liquidity': 2,
            'displacement': 2,
            'session': 2,
            'ml_model': 3,  # Optional bonus
        }

        self.max_score = sum(self.weights.values())

    def analyze(
        self,
        ict_data: Dict,
        current_price: float,
        atr: float,
        direction: str = 'auto',
        ml_signal: Optional[str] = None,
        ml_confidence: float = 0.0,
        timestamp: Optional[datetime] = None
    ) -> ConfluenceResult:
        """
        Perform full confluence analysis.

        Args:
            ict_data: ICT indicators data from ICTIndicators.detect_all()
            current_price: Current market price
            atr: Current ATR value
            direction: 'long', 'short', or 'auto' (determine from data)
            ml_signal: Optional ML model signal ('BUY', 'SELL', 'HOLD')
            ml_confidence: ML model confidence (0-1)
            timestamp: Timestamp for session analysis

        Returns:
            ConfluenceResult with complete analysis
        """
        # Auto-determine direction if needed
        if direction == 'auto':
            direction = self._determine_direction(ict_data)

        factors = []

        # 1. Market Structure Analysis
        factors.append(self._analyze_market_structure(ict_data, direction))

        # 2. Premium/Discount Zone Analysis
        factors.append(self._analyze_premium_discount(ict_data, direction))

        # 3. Order Block Analysis
        factors.append(self._analyze_order_blocks(ict_data, current_price, atr, direction))

        # 4. Fair Value Gap Analysis
        factors.append(self._analyze_fvg(ict_data, current_price, atr, direction))

        # 5. OTE Level Analysis
        factors.append(self._analyze_ote_levels(ict_data, current_price, atr, direction))

        # 6. Market Structure Shift Analysis
        factors.append(self._analyze_mss(ict_data, direction))

        # 7. Liquidity Zone Analysis
        factors.append(self._analyze_liquidity(ict_data, current_price, atr, direction))

        # 8. Displacement Analysis
        factors.append(self._analyze_displacement(ict_data, direction))

        # 9. Session Analysis
        factors.append(self._analyze_session(timestamp))

        # 10. ML Model Analysis (if provided)
        if ml_signal:
            factors.append(self._analyze_ml_model(ml_signal, ml_confidence, direction))

        # Calculate total score
        total_score = sum(f.points for f in factors)
        max_possible = sum(f.max_points for f in factors)
        score_pct = round(total_score / max_possible * 100, 1) if max_possible > 0 else 0

        # Determine strength
        strength = self._determine_strength(total_score)

        # Calculate entry and targets
        entry, sl, tp1, tp2 = self._calculate_levels(
            ict_data, current_price, atr, direction
        )

        # Calculate risk/reward
        risk = abs(entry - sl)
        rr1 = abs(tp1 - entry) / risk if risk > 0 else 0
        rr2 = abs(tp2 - entry) / risk if risk > 0 else 0

        # Determine if tradeable
        is_tradeable = (
            total_score >= self.min_tradeable_score and
            rr1 >= self.min_risk_reward
        )

        # Generate explanation
        explanation = self._generate_explanation(factors, direction, total_score, strength)

        return ConfluenceResult(
            direction=direction,
            total_score=total_score,
            max_score=max_possible,
            score_pct=score_pct,
            strength=strength,
            factors=factors,
            is_tradeable=is_tradeable,
            entry_price=entry,
            stop_loss=sl,
            take_profit_1=tp1,
            take_profit_2=tp2,
            risk_reward_1=round(rr1, 2),
            risk_reward_2=round(rr2, 2),
            explanation=explanation,
            timestamp=timestamp or datetime.now()
        )

    def _determine_direction(self, ict_data: Dict) -> str:
        """Determine trade direction from ICT data."""
        bullish_points = 0
        bearish_points = 0

        # Market structure
        ms = ict_data.get('market_structure', {})
        if ms.get('trend') == 'bullish':
            bullish_points += 2
        elif ms.get('trend') == 'bearish':
            bearish_points += 2

        # Premium/Discount zone
        pd_zone = ict_data.get('premium_discount', {})
        zone = pd_zone.get('zone', '')
        if zone in ['discount', 'deep_discount']:
            bullish_points += 1  # Buy in discount
        elif zone in ['premium', 'deep_premium']:
            bearish_points += 1  # Sell in premium

        # Recent MSS
        mss = ict_data.get('mss', [])
        if mss:
            last_mss = mss[-1]
            if last_mss.get('type') == 'bullish':
                bullish_points += 1
            else:
                bearish_points += 1

        return 'long' if bullish_points >= bearish_points else 'short'

    def _analyze_market_structure(self, ict_data: Dict, direction: str) -> ConfluenceFactor:
        """Analyze market structure alignment."""
        ms = ict_data.get('market_structure', {})
        trend = ms.get('trend', 'neutral')
        max_points = self.weights['market_structure']

        # Get swing point counts for detailed observation
        hh_count = ms.get('hh_count', 0)
        hl_count = ms.get('hl_count', 0)
        lh_count = ms.get('lh_count', 0)
        ll_count = ms.get('ll_count', 0)

        # Build observation string
        swing_info = f"HH:{hh_count} HL:{hl_count} LH:{lh_count} LL:{ll_count}"

        if direction == 'long':
            if trend == 'bullish':
                return ConfluenceFactor(
                    name='Market Structure',
                    points=3,
                    max_points=max_points,
                    reason=f'Bullish structure ({swing_info}) - Clear uptrend with higher highs and higher lows',
                    category='structure',
                    is_aligned=True
                )
            elif trend == 'neutral':
                return ConfluenceFactor(
                    name='Market Structure',
                    points=1,
                    max_points=max_points,
                    reason=f'Neutral structure ({swing_info}) - No clear trend, mixed swing points',
                    category='structure',
                    is_aligned=False
                )
        else:  # short
            if trend == 'bearish':
                return ConfluenceFactor(
                    name='Market Structure',
                    points=3,
                    max_points=max_points,
                    reason=f'Bearish structure ({swing_info}) - Clear downtrend with lower highs and lower lows',
                    category='structure',
                    is_aligned=True
                )
            elif trend == 'neutral':
                return ConfluenceFactor(
                    name='Market Structure',
                    points=1,
                    max_points=max_points,
                    reason=f'Neutral structure ({swing_info}) - No clear trend, mixed swing points',
                    category='structure',
                    is_aligned=False
                )

        return ConfluenceFactor(
            name='Market Structure',
            points=0,
            max_points=max_points,
            reason=f'{trend.title()} structure ({swing_info}) conflicts with {direction} direction',
            category='structure',
            is_aligned=False
        )

    def _analyze_premium_discount(self, ict_data: Dict, direction: str) -> ConfluenceFactor:
        """Analyze premium/discount zone alignment."""
        pd_zone = ict_data.get('premium_discount', {})
        zone = pd_zone.get('zone', '')
        max_points = self.weights['premium_discount']

        # Get actual price levels for observation
        range_high = pd_zone.get('range_high', 0)
        range_low = pd_zone.get('range_low', 0)
        equilibrium = pd_zone.get('equilibrium', 0)
        current_pct = pd_zone.get('current_pct', 50)

        # Format price observations
        level_info = ""
        if range_high and range_low:
            level_info = f" | Range: ${range_low:,.2f} - ${range_high:,.2f}, EQ: ${equilibrium:,.2f}, Currently at {current_pct:.0f}%"

        zone_scores = {
            'long': {
                'deep_discount': (3, f'Price in deep discount zone (<25%){level_info} - Optimal buy zone, price well below equilibrium'),
                'discount': (2, f'Price in discount zone (25-50%){level_info} - Good buy zone, below equilibrium'),
                'equilibrium': (1, f'Price at equilibrium (~50%){level_info} - Neutral zone'),
                'premium': (0, f'Price in premium zone (50-75%){level_info} - Not ideal for longs, above equilibrium'),
                'deep_premium': (0, f'Price in deep premium (>75%){level_info} - Avoid longs, price overextended'),
            },
            'short': {
                'deep_premium': (3, f'Price in deep premium zone (>75%){level_info} - Optimal sell zone, price well above equilibrium'),
                'premium': (2, f'Price in premium zone (50-75%){level_info} - Good sell zone, above equilibrium'),
                'equilibrium': (1, f'Price at equilibrium (~50%){level_info} - Neutral zone'),
                'discount': (0, f'Price in discount zone (25-50%){level_info} - Not ideal for shorts, below equilibrium'),
                'deep_discount': (0, f'Price in deep discount (<25%){level_info} - Avoid shorts, price oversold'),
            }
        }

        scores = zone_scores.get(direction, {})
        points, reason = scores.get(zone, (0, f'Unknown zone: {zone}'))

        return ConfluenceFactor(
            name='Premium/Discount Zone',
            points=points,
            max_points=max_points,
            reason=reason,
            category='zone',
            is_aligned=points >= 2
        )

    def _analyze_order_blocks(
        self,
        ict_data: Dict,
        current_price: float,
        atr: float,
        direction: str
    ) -> ConfluenceFactor:
        """Analyze order block proximity."""
        order_blocks = ict_data.get('order_blocks', [])
        max_points = self.weights['order_block']

        if not order_blocks:
            return ConfluenceFactor(
                name='Order Block',
                points=0,
                max_points=max_points,
                reason=f'No active order blocks detected in recent price action. Price: ${current_price:,.2f}',
                category='level',
                is_aligned=False
            )

        # Find relevant order blocks
        relevant_obs = []
        for ob in order_blocks:
            if ob.get('mitigated'):
                continue

            ob_type = ob.get('type', '')
            high = ob.get('high', 0)
            low = ob.get('low', 0)
            midpoint = (high + low) / 2

            # Check alignment
            if direction == 'long' and ob_type == 'bullish':
                if low <= current_price <= high:
                    relevant_obs.append(('at', ob, 0))
                elif current_price > high:
                    distance = (current_price - high) / atr
                    if distance < 1:
                        relevant_obs.append(('near', ob, distance))
            elif direction == 'short' and ob_type == 'bearish':
                if low <= current_price <= high:
                    relevant_obs.append(('at', ob, 0))
                elif current_price < low:
                    distance = (low - current_price) / atr
                    if distance < 1:
                        relevant_obs.append(('near', ob, distance))

        if not relevant_obs:
            # Count total OBs found
            bullish_obs = [ob for ob in order_blocks if ob.get('type') == 'bullish' and not ob.get('mitigated')]
            bearish_obs = [ob for ob in order_blocks if ob.get('type') == 'bearish' and not ob.get('mitigated')]
            return ConfluenceFactor(
                name='Order Block',
                points=0,
                max_points=max_points,
                reason=f'No aligned OBs nearby. Found {len(bullish_obs)} bullish, {len(bearish_obs)} bearish OBs but none within 1 ATR (${atr:,.2f}) of current price ${current_price:,.2f}',
                category='level',
                is_aligned=False
            )

        # Score based on proximity
        best = relevant_obs[0]
        ob = best[1]
        ob_high = ob.get('high', 0)
        ob_low = ob.get('low', 0)
        ob_type = "bullish" if direction == "long" else "bearish"

        if best[0] == 'at':
            return ConfluenceFactor(
                name='Order Block',
                points=3,
                max_points=max_points,
                reason=f'Price INSIDE {ob_type} order block zone: ${ob_low:,.2f} - ${ob_high:,.2f}. Current: ${current_price:,.2f}. This is the last opposite candle before a strong move - institutional entry zone.',
                category='level',
                is_aligned=True
            )
        else:
            distance = best[2]
            points = 2 if distance < 0.5 else 1
            distance_dollars = distance * atr
            return ConfluenceFactor(
                name='Order Block',
                points=points,
                max_points=max_points,
                reason=f'Price ${distance_dollars:,.2f} ({distance:.2f} ATR) from {ob_type} OB at ${ob_low:,.2f} - ${ob_high:,.2f}. {"Close enough for entry" if points >= 2 else "Waiting for price to reach OB"}',
                category='level',
                is_aligned=points >= 2
            )

    def _analyze_fvg(
        self,
        ict_data: Dict,
        current_price: float,
        atr: float,
        direction: str
    ) -> ConfluenceFactor:
        """Analyze Fair Value Gap alignment."""
        fvgs = ict_data.get('fvg', [])
        max_points = self.weights['fvg']

        # Count FVGs
        bullish_fvgs = [f for f in fvgs if f.get('type') == 'bullish' and not f.get('filled')]
        bearish_fvgs = [f for f in fvgs if f.get('type') == 'bearish' and not f.get('filled')]

        if not fvgs:
            return ConfluenceFactor(
                name='Fair Value Gap',
                points=0,
                max_points=max_points,
                reason=f'No FVGs detected in recent price action. FVGs form when price moves so fast it leaves a gap (3-candle pattern where middle candle doesnt overlap with sides).',
                category='level',
                is_aligned=False
            )

        # Find relevant FVGs
        for fvg in fvgs:
            if fvg.get('filled'):
                continue

            fvg_type = fvg.get('type', '')
            top = fvg.get('top', 0)
            bottom = fvg.get('bottom', 0)
            gap_size = top - bottom

            # Check if price is in FVG
            if bottom <= current_price <= top:
                if (direction == 'long' and fvg_type == 'bullish') or \
                   (direction == 'short' and fvg_type == 'bearish'):
                    return ConfluenceFactor(
                        name='Fair Value Gap',
                        points=2,
                        max_points=max_points,
                        reason=f'Price INSIDE {fvg_type} FVG zone: ${bottom:,.2f} - ${top:,.2f} (gap size: ${gap_size:,.2f}). Price is filling the imbalance - good entry zone.',
                        category='level',
                        is_aligned=True
                    )

            # Check for support/resistance
            if direction == 'long' and fvg_type == 'bullish' and top < current_price:
                distance = (current_price - top) / atr
                if distance < 0.5:
                    return ConfluenceFactor(
                        name='Fair Value Gap',
                        points=1,
                        max_points=max_points,
                        reason=f'Bullish FVG at ${bottom:,.2f} - ${top:,.2f} acts as support below. Current price ${current_price:,.2f} is ${(current_price - top):,.2f} above FVG.',
                        category='level',
                        is_aligned=True
                    )
            elif direction == 'short' and fvg_type == 'bearish' and bottom > current_price:
                distance = (bottom - current_price) / atr
                if distance < 0.5:
                    return ConfluenceFactor(
                        name='Fair Value Gap',
                        points=1,
                        max_points=max_points,
                        reason=f'Bearish FVG at ${bottom:,.2f} - ${top:,.2f} acts as resistance above. Current price ${current_price:,.2f} is ${(bottom - current_price):,.2f} below FVG.',
                        category='level',
                        is_aligned=True
                    )

        return ConfluenceFactor(
            name='Fair Value Gap',
            points=0,
            max_points=max_points,
            reason=f'Found {len(bullish_fvgs)} bullish and {len(bearish_fvgs)} bearish FVGs but none aligned with {direction} direction or price not at FVG levels.',
            category='level',
            is_aligned=False
        )

    def _analyze_ote_levels(
        self,
        ict_data: Dict,
        current_price: float,
        atr: float,
        direction: str
    ) -> ConfluenceFactor:
        """Analyze OTE level proximity."""
        ote_levels = ict_data.get('ote_levels', {})
        max_points = self.weights['ote_level']

        ote = ote_levels.get('bullish' if direction == 'long' else 'bearish', {})
        levels = ote.get('levels', {})
        swing_high = ote.get('swing_high', 0)
        swing_low = ote.get('swing_low', 0)

        if not levels:
            return ConfluenceFactor(
                name='OTE Level',
                points=0,
                max_points=max_points,
                reason=f'No OTE levels calculated. OTE requires a clear swing high/low to draw Fibonacci retracement (62%-79% zone).',
                category='level',
                is_aligned=False
            )

        # Check proximity to each level
        ote_checks = [
            ('ote_62', 3, 'OTE 62%'),
            ('ote_705', 3, 'OTE 70.5%'),
            ('ote_79', 2, 'OTE 79%'),
            ('equilibrium_50', 1, '50% equilibrium'),
        ]

        for level_key, points, name in ote_checks:
            level_price = levels.get(level_key, 0)
            if level_price > 0:
                distance = abs(current_price - level_price) / atr
                distance_dollars = abs(current_price - level_price)
                if distance < 0.3:
                    return ConfluenceFactor(
                        name='OTE Level',
                        points=points,
                        max_points=max_points,
                        reason=f'Price at {name} level (${level_price:,.2f}). Swing range: ${swing_low:,.2f} - ${swing_high:,.2f}. Distance: ${distance_dollars:,.2f} ({distance:.2f} ATR). This is the optimal entry zone.',
                        category='level',
                        is_aligned=True
                    )
                elif distance < 0.5 and points >= 2:
                    return ConfluenceFactor(
                        name='OTE Level',
                        points=points - 1,
                        max_points=max_points,
                        reason=f'Price near {name} level (${level_price:,.2f}). Currently ${distance_dollars:,.2f} away ({distance:.2f} ATR). Wait for price to reach the level.',
                        category='level',
                        is_aligned=True
                    )

        # Show calculated OTE levels if not at any
        ote_62 = levels.get('ote_62', 0)
        ote_79 = levels.get('ote_79', 0)
        return ConfluenceFactor(
            name='OTE Level',
            points=0,
            max_points=max_points,
            reason=f'Price not at OTE levels. OTE zone is ${ote_79:,.2f} - ${ote_62:,.2f} (62-79% retracement). Current: ${current_price:,.2f}. Wait for pullback to this zone.',
            category='level',
            is_aligned=False
        )

    def _analyze_mss(self, ict_data: Dict, direction: str) -> ConfluenceFactor:
        """Analyze Market Structure Shift."""
        mss_events = ict_data.get('mss', [])
        max_points = self.weights['mss']

        if not mss_events:
            return ConfluenceFactor(
                name='Market Structure Shift',
                points=0,
                max_points=max_points,
                reason=f'No MSS events detected. MSS occurs when price breaks and closes beyond the most recent swing high (bullish) or swing low (bearish).',
                category='confirmation',
                is_aligned=False
            )

        # Check recent MSS
        last_mss = mss_events[-1]
        mss_type = last_mss.get('type', '')
        strength = last_mss.get('strength', 0)
        break_level = last_mss.get('break_level', 0)
        candles_ago = last_mss.get('candles_ago', 0)

        expected_type = 'bullish' if direction == 'long' else 'bearish'

        if mss_type == expected_type:
            points = 3 if strength > 70 else (2 if strength > 50 else 1)
            return ConfluenceFactor(
                name='Market Structure Shift',
                points=points,
                max_points=max_points,
                reason=f'Recent {mss_type} MSS at ${break_level:,.2f} ({candles_ago} candles ago). Strength: {strength}%. Price broke {"above resistance" if mss_type == "bullish" else "below support"} confirming trend change.',
                category='confirmation',
                is_aligned=True
            )
        elif mss_type != expected_type:
            return ConfluenceFactor(
                name='Market Structure Shift',
                points=0,
                max_points=max_points,
                reason=f'Last MSS was {mss_type} at ${break_level:,.2f} ({candles_ago} candles ago) - conflicts with {direction} direction. Wait for new {expected_type} MSS.',
                category='confirmation',
                is_aligned=False
            )

        return ConfluenceFactor(
            name='Market Structure Shift',
            points=0,
            max_points=max_points,
            reason='No recent MSS confirmation. Need price to break structure before entry.',
            category='confirmation',
            is_aligned=False
        )

    def _analyze_liquidity(
        self,
        ict_data: Dict,
        current_price: float,
        atr: float,
        direction: str
    ) -> ConfluenceFactor:
        """Analyze liquidity zone awareness."""
        liquidity_zones = ict_data.get('liquidity_zones', [])
        max_points = self.weights['liquidity']

        if not liquidity_zones:
            return ConfluenceFactor(
                name='Liquidity Zone',
                points=1,
                max_points=max_points,
                reason=f'No obvious liquidity pools detected (equal highs/lows where stops cluster). Neutral for entry - no major stop hunt risk visible.',
                category='level',
                is_aligned=False
            )

        # Count zones
        buy_side_count = len([lz for lz in liquidity_zones if lz.get('type') == 'buy_side'])
        sell_side_count = len([lz for lz in liquidity_zones if lz.get('type') == 'sell_side'])

        if direction == 'long':
            # Check for nearby sell-side liquidity (danger zone)
            sell_side = [lz for lz in liquidity_zones
                        if lz.get('type') == 'sell_side' and not lz.get('swept')]
            liq_below = [lz for lz in sell_side if lz.get('level', 0) < current_price]

            if liq_below:
                nearest = max(liq_below, key=lambda x: x.get('level', 0))
                level = nearest['level']
                distance = (current_price - level) / atr
                distance_dollars = current_price - level

                if distance < 0.5:
                    return ConfluenceFactor(
                        name='Liquidity Zone',
                        points=0,
                        max_points=max_points,
                        reason=f'RISK: Sell-side liquidity at ${level:,.2f} is only ${distance_dollars:,.2f} ({distance:.2f} ATR) below. Stop losses likely clustered there - price may sweep down before going up.',
                        category='level',
                        is_aligned=False
                    )
                else:
                    return ConfluenceFactor(
                        name='Liquidity Zone',
                        points=2,
                        max_points=max_points,
                        reason=f'Sell-side liquidity at ${level:,.2f} is ${distance_dollars:,.2f} ({distance:.2f} ATR) below. Safe distance - good stop loss target. Found {sell_side_count} sell-side, {buy_side_count} buy-side zones.',
                        category='level',
                        is_aligned=True
                    )
        else:  # short
            buy_side = [lz for lz in liquidity_zones
                       if lz.get('type') == 'buy_side' and not lz.get('swept')]
            liq_above = [lz for lz in buy_side if lz.get('level', 0) > current_price]

            if liq_above:
                nearest = min(liq_above, key=lambda x: x.get('level', 0))
                level = nearest['level']
                distance = (level - current_price) / atr
                distance_dollars = level - current_price

                if distance < 0.5:
                    return ConfluenceFactor(
                        name='Liquidity Zone',
                        points=0,
                        max_points=max_points,
                        reason=f'RISK: Buy-side liquidity at ${level:,.2f} is only ${distance_dollars:,.2f} ({distance:.2f} ATR) above. Stop losses clustered there - price may sweep up before going down.',
                        category='level',
                        is_aligned=False
                    )
                else:
                    return ConfluenceFactor(
                        name='Liquidity Zone',
                        points=2,
                        max_points=max_points,
                        reason=f'Buy-side liquidity at ${level:,.2f} is ${distance_dollars:,.2f} ({distance:.2f} ATR) above. Safe distance - good stop loss target. Found {buy_side_count} buy-side, {sell_side_count} sell-side zones.',
                        category='level',
                        is_aligned=True
                    )

        return ConfluenceFactor(
            name='Liquidity Zone',
            points=1,
            max_points=max_points,
            reason=f'Liquidity zones acceptable. Found {buy_side_count} buy-side (above) and {sell_side_count} sell-side (below) zones. No immediate risk.',
            category='level',
            is_aligned=True
        )

    def _analyze_displacement(self, ict_data: Dict, direction: str) -> ConfluenceFactor:
        """Analyze displacement confirmation."""
        displacements = ict_data.get('displacement', [])
        max_points = self.weights['displacement']

        if not displacements:
            return ConfluenceFactor(
                name='Displacement',
                points=0,
                max_points=max_points,
                reason=f'No displacement detected. Displacement = large-bodied candle (1.5x+ ATR) showing institutional aggression. Look for candles with body > 2x recent average.',
                category='confirmation',
                is_aligned=False
            )

        # Check recent displacement
        recent = [d for d in displacements[-5:]]  # Last 5
        expected_type = 'bullish' if direction == 'long' else 'bearish'

        aligned = [d for d in recent if d.get('type') == expected_type]

        if aligned:
            best = max(aligned, key=lambda x: x.get('body_atr_ratio', 0))
            strength = best.get('body_atr_ratio', 0)
            candle_size = best.get('body_size', 0)
            candles_ago = best.get('candles_ago', 0)
            points = 2 if strength > 2 else 1

            return ConfluenceFactor(
                name='Displacement',
                points=points,
                max_points=max_points,
                reason=f'Recent {expected_type} displacement {candles_ago} candles ago. Candle body: ${candle_size:,.2f} ({strength:.1f}x ATR). {"Strong institutional move!" if strength > 2 else "Moderate momentum."} Shows smart money commitment.',
                category='confirmation',
                is_aligned=True
            )

        # Check if opposite displacement exists
        opposite = [d for d in recent if d.get('type') != expected_type]
        if opposite:
            last_opp = opposite[-1]
            opp_type = last_opp.get('type', '')
            opp_strength = last_opp.get('body_atr_ratio', 0)
            return ConfluenceFactor(
                name='Displacement',
                points=0,
                max_points=max_points,
                reason=f'Recent displacement was {opp_type} ({opp_strength:.1f}x ATR) - conflicts with {direction}. Wait for {expected_type} displacement to confirm direction.',
                category='confirmation',
                is_aligned=False
            )

        return ConfluenceFactor(
            name='Displacement',
            points=0,
            max_points=max_points,
            reason=f'No {expected_type} displacement in last 5 candles. Found {len(displacements)} total displacements but none aligned with {direction}.',
            category='confirmation',
            is_aligned=False
        )

    def _analyze_session(self, timestamp: Optional[datetime]) -> ConfluenceFactor:
        """Analyze session timing."""
        from features.sessions import SessionFilter, TradingSession, get_ny_time

        max_points = self.weights['session']
        sf = SessionFilter()

        if timestamp is None:
            timestamp = datetime.now()

        session = sf.get_session(timestamp)
        ny_time = get_ny_time(timestamp)
        time_str = ny_time.strftime('%I:%M %p EST')

        optimal_sessions = [
            TradingSession.NY_AM_KILLZONE,
            TradingSession.SILVER_BULLET_AM,
            TradingSession.SILVER_BULLET_PM,
            TradingSession.LONDON_NY_OVERLAP,
        ]

        good_sessions = [
            TradingSession.LONDON,
            TradingSession.NY_PM,
        ]

        if session in [TradingSession.SILVER_BULLET_AM, TradingSession.SILVER_BULLET_PM]:
            window = "10-11 AM" if session == TradingSession.SILVER_BULLET_AM else "2-3 PM"
            return ConfluenceFactor(
                name='Session',
                points=2,
                max_points=max_points,
                reason=f'SILVER BULLET WINDOW! Current: {time_str} ({window} EST). This 1-hour window has highest probability setups. ICT calls this the "sniper" entry window.',
                category='timing',
                is_aligned=True
            )
        elif session in optimal_sessions:
            return ConfluenceFactor(
                name='Session',
                points=2,
                max_points=max_points,
                reason=f'Optimal session: {session.value}. Current: {time_str}. High institutional volume period - smart money is active. Best time for entries.',
                category='timing',
                is_aligned=True
            )
        elif session in good_sessions:
            return ConfluenceFactor(
                name='Session',
                points=1,
                max_points=max_points,
                reason=f'Good session: {session.value}. Current: {time_str}. Decent volume but not peak. Consider waiting for kill zones (7-10 AM or 1-3 PM EST).',
                category='timing',
                is_aligned=True
            )
        else:
            next_optimal = sf.get_next_optimal_session(timestamp)
            next_name = next_optimal.get('name', 'kill zone')
            mins_until = next_optimal.get('minutes_until', 0)
            return ConfluenceFactor(
                name='Session',
                points=0,
                max_points=max_points,
                reason=f'Sub-optimal: {session.value}. Current: {time_str}. Low volume period - avoid entries. Next {next_name} in {mins_until} mins.',
                category='timing',
                is_aligned=False
            )

    def _analyze_ml_model(
        self,
        ml_signal: str,
        ml_confidence: float,
        direction: str
    ) -> ConfluenceFactor:
        """Analyze ML model alignment."""
        max_points = self.weights['ml_model']

        expected_signal = 'BUY' if direction == 'long' else 'SELL'
        conf_pct = ml_confidence * 100

        if ml_signal == expected_signal:
            if ml_confidence >= 0.75:
                points = 3
                strength = "HIGH"
            elif ml_confidence >= 0.6:
                points = 2
                strength = "MODERATE"
            else:
                points = 1
                strength = "LOW"

            return ConfluenceFactor(
                name='ML Model',
                points=points,
                max_points=max_points,
                reason=f'ML CONFIRMS {ml_signal} with {conf_pct:.1f}% confidence ({strength}). Model analyzed 50+ features including ICT patterns, volume, momentum. Statistical confirmation aligns with ICT direction.',
                category='confirmation',
                is_aligned=True
            )
        elif ml_signal == 'HOLD':
            return ConfluenceFactor(
                name='ML Model',
                points=1,
                max_points=max_points,
                reason=f'ML model is NEUTRAL (HOLD) with {conf_pct:.1f}% confidence. Model sees mixed signals - neither strong buy nor sell. ICT factors should drive decision.',
                category='confirmation',
                is_aligned=False
            )
        else:
            return ConfluenceFactor(
                name='ML Model',
                points=0,
                max_points=max_points,
                reason=f'ML CONFLICTS: Predicts {ml_signal} ({conf_pct:.1f}%) but ICT suggests {direction}. Either wait for alignment or trust ICT if confluence is strong (20+).',
                category='confirmation',
                is_aligned=False
            )

    def _determine_strength(self, score: int) -> ConfluenceStrength:
        """Determine confluence strength from score."""
        if score >= self.very_strong_threshold:
            return ConfluenceStrength.VERY_STRONG
        elif score >= self.strong_threshold:
            return ConfluenceStrength.STRONG
        elif score >= self.moderate_threshold:
            return ConfluenceStrength.MODERATE
        elif score >= self.weak_threshold:
            return ConfluenceStrength.WEAK
        else:
            return ConfluenceStrength.NONE

    def _calculate_levels(
        self,
        ict_data: Dict,
        current_price: float,
        atr: float,
        direction: str
    ) -> Tuple[float, float, float, float]:
        """Calculate entry, stop loss, and take profit levels."""
        entry = current_price

        ote_levels = ict_data.get('ote_levels', {})
        liquidity_zones = ict_data.get('liquidity_zones', [])
        swing_points = ict_data.get('swing_points', [])

        if direction == 'long':
            # Stop loss below recent swing low or liquidity
            sl_candidates = [current_price - 2 * atr]  # Default

            for sp in swing_points[-5:]:
                if sp.get('type') == 'low' and sp.get('price', 0) < current_price:
                    sl_candidates.append(sp['price'] - 0.5 * atr)

            for lz in liquidity_zones:
                if lz.get('type') == 'sell_side' and lz.get('level', 0) < current_price:
                    sl_candidates.append(lz['level'] - 0.5 * atr)

            stop_loss = max(sl_candidates)  # Tightest stop

            # Take profits from OTE extensions
            ote = ote_levels.get('bullish', {})
            targets = ote.get('targets', {})
            tp1 = targets.get('target_1_neg27', current_price + 1.5 * atr)
            tp2 = targets.get('target_2_neg62', current_price + 3 * atr)

        else:  # short
            sl_candidates = [current_price + 2 * atr]

            for sp in swing_points[-5:]:
                if sp.get('type') == 'high' and sp.get('price', 0) > current_price:
                    sl_candidates.append(sp['price'] + 0.5 * atr)

            for lz in liquidity_zones:
                if lz.get('type') == 'buy_side' and lz.get('level', 0) > current_price:
                    sl_candidates.append(lz['level'] + 0.5 * atr)

            stop_loss = min(sl_candidates)

            ote = ote_levels.get('bearish', {})
            targets = ote.get('targets', {})
            tp1 = targets.get('target_1_neg27', current_price - 1.5 * atr)
            tp2 = targets.get('target_2_neg62', current_price - 3 * atr)

        return entry, stop_loss, tp1, tp2

    def _generate_explanation(
        self,
        factors: List[ConfluenceFactor],
        direction: str,
        score: int,
        strength: ConfluenceStrength
    ) -> str:
        """Generate human-readable explanation."""
        lines = []
        lines.append(f"Confluence Analysis: {direction.upper()}")
        lines.append(f"Score: {score}/{sum(f.max_points for f in factors)} ({strength.value})")
        lines.append("")

        # Group by category
        categories = {}
        for f in factors:
            if f.category not in categories:
                categories[f.category] = []
            categories[f.category].append(f)

        for cat, cat_factors in categories.items():
            lines.append(f"{cat.title()}:")
            for f in cat_factors:
                status = "+" if f.is_aligned else "-"
                lines.append(f"  {status} {f.name}: {f.points}/{f.max_points} - {f.reason}")

        return "\n".join(lines)
