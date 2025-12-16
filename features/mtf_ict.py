"""
Multi-Timeframe ICT Analysis Module.

Implements ICT's top-down analysis approach:
1. Daily - Overall bias and key levels (PDH/PDL/PWH/PWL)
2. 4H - Intermediate structure and order blocks
3. 1H - Key swing points and FVGs
4. 15m - Setup identification and entry zones
5. 5m - Precision entries

This aligns with ICT methodology where higher timeframes
determine direction and lower timeframes provide entries.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from features.ict_indicators import ICTIndicators


class TimeframeBias(Enum):
    """Bias determination from a timeframe."""
    STRONGLY_BULLISH = "strongly_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONGLY_BEARISH = "strongly_bearish"


@dataclass
class TimeframeAnalysis:
    """Analysis result for a single timeframe."""
    timeframe: str
    bias: TimeframeBias
    trend: str
    structure: Dict
    key_levels: List[Dict]
    order_blocks: List[Dict]
    fvgs: List[Dict]
    swing_points: List[Dict]
    confidence: float
    lookback_candles: int
    lookback_period: str  # Human readable (e.g., "7 days", "24 hours")


@dataclass
class MTFAnalysisResult:
    """Complete multi-timeframe analysis result."""
    timestamp: datetime
    symbol: str
    overall_bias: TimeframeBias
    overall_confidence: float
    alignment_score: float  # How well timeframes align (0-100)
    timeframes: Dict[str, TimeframeAnalysis]
    recommended_direction: str  # 'long', 'short', or 'wait'
    key_levels: Dict  # Aggregated key levels from all timeframes
    entry_timeframe: str  # Recommended timeframe for entry
    explanation: str


class MTFICTAnalyzer:
    """
    Multi-Timeframe ICT Analysis System.

    Performs top-down analysis across multiple timeframes
    to determine high-probability trade direction and entries.
    """

    # Timeframe configurations
    TIMEFRAME_CONFIG = {
        '1d': {
            'name': 'Daily',
            'weight': 5,  # Highest weight for direction
            'lookback': 30,  # 30 days
            'lookback_desc': '30 days',
            'swing_lookback': 3,  # 3 candles each side
            'purpose': 'Overall bias and major levels',
        },
        '4h': {
            'name': '4-Hour',
            'weight': 4,
            'lookback': 100,  # ~16 days
            'lookback_desc': '16 days',
            'swing_lookback': 4,
            'purpose': 'Intermediate structure and OBs',
        },
        '1h': {
            'name': 'Hourly',
            'weight': 3,
            'lookback': 168,  # 7 days
            'lookback_desc': '7 days',
            'swing_lookback': 5,
            'purpose': 'Key swing points and FVGs',
        },
        '15m': {
            'name': '15-Minute',
            'weight': 2,
            'lookback': 200,  # ~50 hours
            'lookback_desc': '50 hours',
            'swing_lookback': 5,
            'purpose': 'Setup identification',
        },
        '5m': {
            'name': '5-Minute',
            'weight': 1,
            'lookback': 300,  # 25 hours
            'lookback_desc': '25 hours',
            'swing_lookback': 5,
            'purpose': 'Precision entries',
        },
    }

    def __init__(self, data_fetcher=None, config: Optional[Dict] = None):
        """
        Initialize MTF Analyzer.

        Args:
            data_fetcher: Data fetcher instance for retrieving OHLCV data
            config: Optional configuration overrides
        """
        self.data_fetcher = data_fetcher
        self.config = config or {}
        self.ict = ICTIndicators()

        # Override default lookbacks if provided
        for tf, settings in self.config.get('timeframes', {}).items():
            if tf in self.TIMEFRAME_CONFIG:
                self.TIMEFRAME_CONFIG[tf].update(settings)

    def analyze(
        self,
        symbol: str,
        timeframes: Optional[List[str]] = None,
        entry_tf: str = '5m'
    ) -> MTFAnalysisResult:
        """
        Perform complete multi-timeframe analysis.

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframes: List of timeframes to analyze (default: all)
            entry_tf: Timeframe for entry signals

        Returns:
            MTFAnalysisResult with complete analysis
        """
        if timeframes is None:
            timeframes = ['1d', '4h', '1h', '15m', '5m']

        tf_analyses = {}

        # Analyze each timeframe
        for tf in timeframes:
            try:
                analysis = self._analyze_timeframe(symbol, tf)
                if analysis:
                    tf_analyses[tf] = analysis
            except Exception as e:
                logger.warning(f"Failed to analyze {tf}: {e}")

        if not tf_analyses:
            return self._empty_result(symbol)

        # Calculate overall bias from higher timeframes
        overall_bias, overall_confidence = self._calculate_overall_bias(tf_analyses)

        # Calculate alignment score
        alignment_score = self._calculate_alignment(tf_analyses)

        # Determine recommended direction
        recommended_direction = self._determine_direction(
            overall_bias, alignment_score, overall_confidence
        )

        # Aggregate key levels
        key_levels = self._aggregate_key_levels(tf_analyses)

        # Generate explanation
        explanation = self._generate_explanation(
            tf_analyses, overall_bias, alignment_score, recommended_direction
        )

        # Generate detailed reasoning
        detailed_reasoning = self._generate_detailed_reasoning(
            tf_analyses, overall_bias, alignment_score, recommended_direction
        )

        result = MTFAnalysisResult(
            timestamp=datetime.utcnow(),
            symbol=symbol,
            overall_bias=overall_bias,
            overall_confidence=overall_confidence,
            alignment_score=alignment_score,
            timeframes=tf_analyses,
            recommended_direction=recommended_direction,
            key_levels=key_levels,
            entry_timeframe=entry_tf,
            explanation=explanation
        )

        # Attach detailed reasoning to result (not in dataclass, added dynamically)
        result.detailed_reasoning = detailed_reasoning

        return result

    def _analyze_timeframe(self, symbol: str, timeframe: str) -> Optional[TimeframeAnalysis]:
        """Analyze a single timeframe."""
        config = self.TIMEFRAME_CONFIG.get(timeframe)
        if not config:
            return None

        # Fetch data
        df = self.data_fetcher.fetch_ohlcv(
            symbol, timeframe, limit=config['lookback']
        )

        if df is None or df.empty or len(df) < 20:
            return None

        # Configure ICT detector for this timeframe
        self.ict.swing_lookback = config['swing_lookback']

        # Detect ICT patterns
        ict_data = self.ict.detect_all(df)

        # Determine bias from structure
        ms = ict_data.get('market_structure', {})
        trend = ms.get('trend', 'neutral')

        hh = ms.get('hh_count', 0)
        hl = ms.get('hl_count', 0)
        lh = ms.get('lh_count', 0)
        ll = ms.get('ll_count', 0)

        bullish_score = hh + hl
        bearish_score = lh + ll
        total = bullish_score + bearish_score

        if total > 0:
            if bullish_score > bearish_score * 2:
                bias = TimeframeBias.STRONGLY_BULLISH
                confidence = min(0.9, bullish_score / total + 0.2)
            elif bullish_score > bearish_score * 1.3:
                bias = TimeframeBias.BULLISH
                confidence = bullish_score / total
            elif bearish_score > bullish_score * 2:
                bias = TimeframeBias.STRONGLY_BEARISH
                confidence = min(0.9, bearish_score / total + 0.2)
            elif bearish_score > bullish_score * 1.3:
                bias = TimeframeBias.BEARISH
                confidence = bearish_score / total
            else:
                bias = TimeframeBias.NEUTRAL
                confidence = 0.5
        else:
            bias = TimeframeBias.NEUTRAL
            confidence = 0.3

        # Extract key levels
        key_levels = self._extract_key_levels(df, ict_data, timeframe)

        return TimeframeAnalysis(
            timeframe=timeframe,
            bias=bias,
            trend=trend,
            structure=ms,
            key_levels=key_levels,
            order_blocks=ict_data.get('order_blocks', [])[:5],
            fvgs=ict_data.get('fvg', [])[:5],
            swing_points=ict_data.get('swing_points', [])[-10:],
            confidence=round(confidence, 2),
            lookback_candles=len(df),
            lookback_period=config['lookback_desc']
        )

    def _extract_key_levels(
        self,
        df: pd.DataFrame,
        ict_data: Dict,
        timeframe: str
    ) -> List[Dict]:
        """Extract key price levels from a timeframe."""
        levels = []

        # Previous day high/low (for daily)
        if timeframe == '1d' and len(df) >= 2:
            levels.append({
                'name': 'PDH',
                'price': float(df['high'].iloc[-2]),
                'type': 'resistance',
                'timeframe': timeframe
            })
            levels.append({
                'name': 'PDL',
                'price': float(df['low'].iloc[-2]),
                'type': 'support',
                'timeframe': timeframe
            })

            # Previous week high/low
            if len(df) >= 7:
                levels.append({
                    'name': 'PWH',
                    'price': float(df['high'].iloc[-7:-1].max()),
                    'type': 'resistance',
                    'timeframe': timeframe
                })
                levels.append({
                    'name': 'PWL',
                    'price': float(df['low'].iloc[-7:-1].min()),
                    'type': 'support',
                    'timeframe': timeframe
                })

        # Recent swing highs/lows
        swing_points = ict_data.get('swing_points', [])
        swing_highs = [sp for sp in swing_points if sp['type'] == 'high'][-3:]
        swing_lows = [sp for sp in swing_points if sp['type'] == 'low'][-3:]

        for i, sh in enumerate(swing_highs):
            levels.append({
                'name': f'{timeframe.upper()} SH{i+1}',
                'price': sh['price'],
                'type': 'resistance',
                'timeframe': timeframe
            })

        for i, sl in enumerate(swing_lows):
            levels.append({
                'name': f'{timeframe.upper()} SL{i+1}',
                'price': sl['price'],
                'type': 'support',
                'timeframe': timeframe
            })

        # Order block levels
        for ob in ict_data.get('order_blocks', [])[:3]:
            if not ob.get('mitigated'):
                levels.append({
                    'name': f'{timeframe.upper()} {ob["type"].upper()} OB',
                    'price': (ob['high'] + ob['low']) / 2,
                    'high': ob['high'],
                    'low': ob['low'],
                    'type': 'order_block',
                    'ob_type': ob['type'],
                    'timeframe': timeframe
                })

        return levels

    def _calculate_overall_bias(
        self,
        tf_analyses: Dict[str, TimeframeAnalysis]
    ) -> Tuple[TimeframeBias, float]:
        """Calculate overall bias from all timeframes."""
        weighted_score = 0
        total_weight = 0

        bias_scores = {
            TimeframeBias.STRONGLY_BULLISH: 2,
            TimeframeBias.BULLISH: 1,
            TimeframeBias.NEUTRAL: 0,
            TimeframeBias.BEARISH: -1,
            TimeframeBias.STRONGLY_BEARISH: -2,
        }

        for tf, analysis in tf_analyses.items():
            config = self.TIMEFRAME_CONFIG.get(tf, {})
            weight = config.get('weight', 1)

            score = bias_scores.get(analysis.bias, 0)
            weighted_score += score * weight * analysis.confidence
            total_weight += weight

        if total_weight == 0:
            return TimeframeBias.NEUTRAL, 0.0

        avg_score = weighted_score / total_weight

        # Convert score back to bias
        if avg_score >= 1.5:
            bias = TimeframeBias.STRONGLY_BULLISH
        elif avg_score >= 0.5:
            bias = TimeframeBias.BULLISH
        elif avg_score <= -1.5:
            bias = TimeframeBias.STRONGLY_BEARISH
        elif avg_score <= -0.5:
            bias = TimeframeBias.BEARISH
        else:
            bias = TimeframeBias.NEUTRAL

        # Confidence based on agreement
        confidence = min(0.95, abs(avg_score) / 2 + 0.3)

        return bias, round(confidence, 2)

    def _calculate_alignment(
        self,
        tf_analyses: Dict[str, TimeframeAnalysis]
    ) -> float:
        """Calculate how well timeframes align (0-100)."""
        if len(tf_analyses) < 2:
            return 50.0

        biases = [a.bias for a in tf_analyses.values()]

        # Check if all bullish or all bearish
        all_bullish = all(b in [TimeframeBias.BULLISH, TimeframeBias.STRONGLY_BULLISH]
                         for b in biases)
        all_bearish = all(b in [TimeframeBias.BEARISH, TimeframeBias.STRONGLY_BEARISH]
                         for b in biases)

        if all_bullish or all_bearish:
            return 100.0

        # Count agreements
        bullish_count = sum(1 for b in biases
                          if b in [TimeframeBias.BULLISH, TimeframeBias.STRONGLY_BULLISH])
        bearish_count = sum(1 for b in biases
                          if b in [TimeframeBias.BEARISH, TimeframeBias.STRONGLY_BEARISH])
        neutral_count = sum(1 for b in biases if b == TimeframeBias.NEUTRAL)

        total = len(biases)
        max_agreement = max(bullish_count, bearish_count)

        alignment = (max_agreement / total) * 100

        # Reduce for neutrals
        alignment -= (neutral_count / total) * 20

        return max(0, min(100, round(alignment, 1)))

    def _determine_direction(
        self,
        bias: TimeframeBias,
        alignment: float,
        confidence: float
    ) -> str:
        """Determine recommended trading direction."""
        # Need good alignment and confidence
        if alignment < 60 or confidence < 0.5:
            return 'wait'

        if bias in [TimeframeBias.BULLISH, TimeframeBias.STRONGLY_BULLISH]:
            return 'long'
        elif bias in [TimeframeBias.BEARISH, TimeframeBias.STRONGLY_BEARISH]:
            return 'short'
        else:
            return 'wait'

    def _aggregate_key_levels(
        self,
        tf_analyses: Dict[str, TimeframeAnalysis]
    ) -> Dict:
        """Aggregate key levels from all timeframes."""
        all_levels = {
            'daily': [],
            'intermediate': [],  # 4H, 1H
            'entry': [],  # 15m, 5m
            'order_blocks': [],
        }

        for tf, analysis in tf_analyses.items():
            for level in analysis.key_levels:
                if tf == '1d':
                    all_levels['daily'].append(level)
                elif tf in ['4h', '1h']:
                    all_levels['intermediate'].append(level)
                else:
                    all_levels['entry'].append(level)

                if level.get('type') == 'order_block':
                    all_levels['order_blocks'].append(level)

        return all_levels

    def _generate_explanation(
        self,
        tf_analyses: Dict[str, TimeframeAnalysis],
        overall_bias: TimeframeBias,
        alignment: float,
        direction: str
    ) -> str:
        """Generate human-readable explanation of the analysis."""
        lines = []

        lines.append(f"=== Multi-Timeframe ICT Analysis ===")
        lines.append(f"Overall Bias: {overall_bias.value.upper()}")
        lines.append(f"Timeframe Alignment: {alignment:.0f}%")
        lines.append(f"Recommended Direction: {direction.upper()}")
        lines.append("")

        lines.append("Timeframe Breakdown:")
        for tf in ['1d', '4h', '1h', '15m', '5m']:
            if tf in tf_analyses:
                a = tf_analyses[tf]
                config = self.TIMEFRAME_CONFIG[tf]
                lines.append(f"  {config['name']} ({a.lookback_period}): "
                           f"{a.bias.value} ({a.confidence:.0%} confidence)")
                lines.append(f"    Structure: HH:{a.structure.get('hh_count', 0)} "
                           f"HL:{a.structure.get('hl_count', 0)} "
                           f"LH:{a.structure.get('lh_count', 0)} "
                           f"LL:{a.structure.get('ll_count', 0)}")

        lines.append("")

        if alignment >= 80:
            lines.append("✓ Strong alignment across timeframes - high probability setup")
        elif alignment >= 60:
            lines.append("~ Moderate alignment - proceed with caution")
        else:
            lines.append("✗ Poor alignment - wait for better confluence")

        return "\n".join(lines)

    def _generate_detailed_reasoning(
        self,
        tf_analyses: Dict[str, TimeframeAnalysis],
        overall_bias: TimeframeBias,
        alignment: float,
        direction: str
    ) -> Dict:
        """
        Generate detailed reasoning for the MTF analysis recommendation.

        Returns a dictionary with structured reasoning for display in the UI.
        """
        reasoning = {
            'summary': '',
            'direction_reason': '',
            'confidence_reason': '',
            'alignment_reason': '',
            'timeframe_reasons': {},
            'key_observations': [],
            'warnings': [],
            'action_items': []
        }

        # Count biases
        bullish_tfs = []
        bearish_tfs = []
        neutral_tfs = []

        for tf, analysis in tf_analyses.items():
            config = self.TIMEFRAME_CONFIG.get(tf, {})
            tf_name = config.get('name', tf)

            if analysis.bias in [TimeframeBias.BULLISH, TimeframeBias.STRONGLY_BULLISH]:
                bullish_tfs.append((tf, tf_name, analysis))
            elif analysis.bias in [TimeframeBias.BEARISH, TimeframeBias.STRONGLY_BEARISH]:
                bearish_tfs.append((tf, tf_name, analysis))
            else:
                neutral_tfs.append((tf, tf_name, analysis))

        # Generate summary
        if direction == 'long':
            reasoning['summary'] = f"LONG bias detected. {len(bullish_tfs)} of {len(tf_analyses)} timeframes showing bullish structure."
        elif direction == 'short':
            reasoning['summary'] = f"SHORT bias detected. {len(bearish_tfs)} of {len(tf_analyses)} timeframes showing bearish structure."
        else:
            if len(neutral_tfs) >= len(tf_analyses) / 2:
                reasoning['summary'] = f"WAIT recommended. {len(neutral_tfs)} timeframes are neutral - no clear direction."
            elif len(bullish_tfs) > 0 and len(bearish_tfs) > 0:
                reasoning['summary'] = f"WAIT recommended. Mixed signals: {len(bullish_tfs)} bullish vs {len(bearish_tfs)} bearish timeframes."
            else:
                reasoning['summary'] = f"WAIT recommended. Insufficient alignment ({alignment:.0f}%) for a high-probability trade."

        # Direction reasoning
        if direction == 'long':
            htf_bullish = any(tf in ['1d', '4h'] for tf, _, _ in bullish_tfs)
            if htf_bullish:
                reasoning['direction_reason'] = "Higher timeframes (Daily/4H) are bullish, supporting LONG entries on lower timeframes."
            else:
                reasoning['direction_reason'] = "Lower timeframes showing bullish structure, but watch for HTF confirmation."
        elif direction == 'short':
            htf_bearish = any(tf in ['1d', '4h'] for tf, _, _ in bearish_tfs)
            if htf_bearish:
                reasoning['direction_reason'] = "Higher timeframes (Daily/4H) are bearish, supporting SHORT entries on lower timeframes."
            else:
                reasoning['direction_reason'] = "Lower timeframes showing bearish structure, but watch for HTF confirmation."
        else:
            # Analyze why we're waiting
            if alignment < 60:
                reasoning['direction_reason'] = f"Alignment is only {alignment:.0f}% - timeframes are not agreeing on direction. Wait for 60%+ alignment."
            else:
                reasoning['direction_reason'] = "No clear directional bias. Wait for structure to develop."

        # Confidence reasoning
        avg_conf = sum(a.confidence for a in tf_analyses.values()) / len(tf_analyses) if tf_analyses else 0
        if avg_conf >= 0.7:
            reasoning['confidence_reason'] = f"High confidence ({avg_conf:.0%} avg). Structure is clear across timeframes."
        elif avg_conf >= 0.5:
            reasoning['confidence_reason'] = f"Moderate confidence ({avg_conf:.0%} avg). Some timeframes have clearer structure than others."
        else:
            reasoning['confidence_reason'] = f"Low confidence ({avg_conf:.0%} avg). Structure is unclear or choppy across timeframes."

        # Alignment reasoning
        if alignment >= 80:
            reasoning['alignment_reason'] = f"Excellent alignment ({alignment:.0f}%). All timeframes agree - high probability setup."
        elif alignment >= 60:
            reasoning['alignment_reason'] = f"Good alignment ({alignment:.0f}%). Most timeframes agree, but some divergence exists."
        elif alignment >= 40:
            reasoning['alignment_reason'] = f"Weak alignment ({alignment:.0f}%). Timeframes are mixed - higher risk trade."
        else:
            reasoning['alignment_reason'] = f"Poor alignment ({alignment:.0f}%). Timeframes are conflicting - avoid trading."

        # Per-timeframe reasoning
        for tf in ['1d', '4h', '1h', '15m', '5m']:
            if tf not in tf_analyses:
                continue

            analysis = tf_analyses[tf]
            config = self.TIMEFRAME_CONFIG.get(tf, {})
            tf_name = config.get('name', tf)

            ms = analysis.structure
            hh = ms.get('hh_count', 0)
            hl = ms.get('hl_count', 0)
            lh = ms.get('lh_count', 0)
            ll = ms.get('ll_count', 0)

            bullish_points = hh + hl
            bearish_points = lh + ll

            tf_reason = {
                'bias': analysis.bias.value,
                'confidence': analysis.confidence,
                'structure_summary': '',
                'pattern_observation': '',
                'key_level_observation': ''
            }

            # Structure summary
            if bullish_points > bearish_points:
                tf_reason['structure_summary'] = f"Bullish structure: {hh} Higher Highs and {hl} Higher Lows detected over {analysis.lookback_period}."
                tf_reason['pattern_observation'] = f"Price is making HH+HL pattern indicating uptrend. Bearish points: {lh} LH, {ll} LL."
            elif bearish_points > bullish_points:
                tf_reason['structure_summary'] = f"Bearish structure: {lh} Lower Highs and {ll} Lower Lows detected over {analysis.lookback_period}."
                tf_reason['pattern_observation'] = f"Price is making LH+LL pattern indicating downtrend. Bullish points: {hh} HH, {hl} HL."
            else:
                tf_reason['structure_summary'] = f"Neutral structure: Mixed HH/HL ({bullish_points}) vs LH/LL ({bearish_points}) over {analysis.lookback_period}."
                tf_reason['pattern_observation'] = "No clear trend pattern - price is ranging or consolidating."

            # Key level observations
            key_levels = analysis.key_levels[:3] if analysis.key_levels else []
            if key_levels:
                level_names = [l.get('name', 'Level') for l in key_levels]
                tf_reason['key_level_observation'] = f"Key levels: {', '.join(level_names)}"

            reasoning['timeframe_reasons'][tf] = tf_reason

        # Key observations
        # Check HTF vs LTF alignment
        htf_bias = None
        ltf_bias = None

        if '1d' in tf_analyses:
            htf_bias = tf_analyses['1d'].bias
        elif '4h' in tf_analyses:
            htf_bias = tf_analyses['4h'].bias

        if '5m' in tf_analyses:
            ltf_bias = tf_analyses['5m'].bias
        elif '15m' in tf_analyses:
            ltf_bias = tf_analyses['15m'].bias

        if htf_bias and ltf_bias:
            htf_bullish = htf_bias in [TimeframeBias.BULLISH, TimeframeBias.STRONGLY_BULLISH]
            ltf_bullish = ltf_bias in [TimeframeBias.BULLISH, TimeframeBias.STRONGLY_BULLISH]
            htf_bearish = htf_bias in [TimeframeBias.BEARISH, TimeframeBias.STRONGLY_BEARISH]
            ltf_bearish = ltf_bias in [TimeframeBias.BEARISH, TimeframeBias.STRONGLY_BEARISH]

            if htf_bullish and ltf_bullish:
                reasoning['key_observations'].append("HTF and LTF both bullish - ideal LONG setup alignment.")
            elif htf_bearish and ltf_bearish:
                reasoning['key_observations'].append("HTF and LTF both bearish - ideal SHORT setup alignment.")
            elif htf_bullish and ltf_bearish:
                reasoning['key_observations'].append("HTF bullish but LTF bearish - possible pullback in uptrend. Wait for LTF to align.")
            elif htf_bearish and ltf_bullish:
                reasoning['key_observations'].append("HTF bearish but LTF bullish - possible pullback in downtrend. Wait for LTF to align.")

        # Check for strong Daily bias
        if '1d' in tf_analyses:
            daily = tf_analyses['1d']
            if daily.bias == TimeframeBias.STRONGLY_BULLISH:
                reasoning['key_observations'].append(f"Daily timeframe is STRONGLY BULLISH ({daily.confidence:.0%} confidence) - favor LONG trades only.")
            elif daily.bias == TimeframeBias.STRONGLY_BEARISH:
                reasoning['key_observations'].append(f"Daily timeframe is STRONGLY BEARISH ({daily.confidence:.0%} confidence) - favor SHORT trades only.")

        # Warnings
        if len(neutral_tfs) >= 3:
            reasoning['warnings'].append(f"{len(neutral_tfs)} timeframes are neutral - market may be in consolidation. Avoid trading ranges.")

        if alignment < 40:
            reasoning['warnings'].append("Very low alignment - timeframes are conflicting. High risk of false signals.")

        # Check for divergence between consecutive timeframes
        tf_order = ['1d', '4h', '1h', '15m', '5m']
        for i in range(len(tf_order) - 1):
            tf1, tf2 = tf_order[i], tf_order[i+1]
            if tf1 in tf_analyses and tf2 in tf_analyses:
                b1 = tf_analyses[tf1].bias
                b2 = tf_analyses[tf2].bias
                b1_bull = b1 in [TimeframeBias.BULLISH, TimeframeBias.STRONGLY_BULLISH]
                b2_bull = b2 in [TimeframeBias.BULLISH, TimeframeBias.STRONGLY_BULLISH]
                b1_bear = b1 in [TimeframeBias.BEARISH, TimeframeBias.STRONGLY_BEARISH]
                b2_bear = b2 in [TimeframeBias.BEARISH, TimeframeBias.STRONGLY_BEARISH]

                if (b1_bull and b2_bear) or (b1_bear and b2_bull):
                    name1 = self.TIMEFRAME_CONFIG.get(tf1, {}).get('name', tf1)
                    name2 = self.TIMEFRAME_CONFIG.get(tf2, {}).get('name', tf2)
                    reasoning['warnings'].append(f"Divergence between {name1} and {name2} - structure conflict.")

        # Action items
        if direction == 'long':
            reasoning['action_items'].append("Look for LONG entries on pullbacks to OTE (0.618-0.786 Fib) levels.")
            reasoning['action_items'].append("Wait for MSS confirmation on entry timeframe before entering.")
            if '5m' in tf_analyses or '15m' in tf_analyses:
                reasoning['action_items'].append("Use 5m/15m for precision entries with tight stops.")
        elif direction == 'short':
            reasoning['action_items'].append("Look for SHORT entries on rallies to OTE (0.618-0.786 Fib) levels.")
            reasoning['action_items'].append("Wait for MSS confirmation on entry timeframe before entering.")
            if '5m' in tf_analyses or '15m' in tf_analyses:
                reasoning['action_items'].append("Use 5m/15m for precision entries with tight stops.")
        else:
            reasoning['action_items'].append("Wait for timeframe alignment before taking any trades.")
            if alignment < 60:
                reasoning['action_items'].append(f"Current alignment is {alignment:.0f}%. Wait for 60%+ before considering entries.")
            reasoning['action_items'].append("Monitor Daily and 4H for bias development.")

        return reasoning

    def _empty_result(self, symbol: str) -> MTFAnalysisResult:
        """Return empty result when analysis fails."""
        return MTFAnalysisResult(
            timestamp=datetime.utcnow(),
            symbol=symbol,
            overall_bias=TimeframeBias.NEUTRAL,
            overall_confidence=0.0,
            alignment_score=0.0,
            timeframes={},
            recommended_direction='wait',
            key_levels={},
            entry_timeframe='5m',
            explanation='Insufficient data for multi-timeframe analysis'
        )

    def get_htf_bias(self, symbol: str) -> Dict:
        """
        Quick method to get higher timeframe bias only (Daily + 4H).

        Useful for checking direction before lower timeframe entries.
        """
        result = self.analyze(symbol, timeframes=['1d', '4h'])

        return {
            'bias': result.overall_bias.value,
            'confidence': result.overall_confidence,
            'daily': result.timeframes.get('1d', {}).bias.value if '1d' in result.timeframes else 'unknown',
            '4h': result.timeframes.get('4h', {}).bias.value if '4h' in result.timeframes else 'unknown',
            'direction': result.recommended_direction
        }

    def to_dict(self, result: MTFAnalysisResult) -> Dict:
        """Convert MTFAnalysisResult to dictionary for JSON serialization."""
        data = {
            'timestamp': result.timestamp.isoformat(),
            'symbol': result.symbol,
            'overall_bias': result.overall_bias.value,
            'overall_confidence': result.overall_confidence,
            'alignment_score': result.alignment_score,
            'recommended_direction': result.recommended_direction,
            'entry_timeframe': result.entry_timeframe,
            'explanation': result.explanation,
            'timeframes': {
                tf: {
                    'timeframe': a.timeframe,
                    'name': self.TIMEFRAME_CONFIG.get(tf, {}).get('name', tf),
                    'bias': a.bias.value,
                    'trend': a.trend,
                    'confidence': a.confidence,
                    'lookback_candles': a.lookback_candles,
                    'lookback_period': a.lookback_period,
                    'structure': a.structure,
                    'key_levels': a.key_levels[:5],
                    'order_blocks': len(a.order_blocks),
                    'fvgs': len(a.fvgs),
                }
                for tf, a in result.timeframes.items()
            },
            'key_levels': result.key_levels
        }

        # Include detailed reasoning if available
        if hasattr(result, 'detailed_reasoning'):
            data['reasoning'] = result.detailed_reasoning

        return data
