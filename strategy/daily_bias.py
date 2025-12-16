"""
ICT Daily Bias Calculator.

This module determines the daily directional bias using higher timeframe
analysis based on ICT concepts. The daily bias helps filter trades to
only take setups that align with the overall market direction.

Key Concepts:
1. Previous Day High/Low (PDH/PDL) - Key reference levels
2. Previous Week High/Low (PWH/PWL) - Wider context
3. Higher Timeframe Structure - 4H/Daily trend
4. Asian Session Range - Initial reference for the day
5. London Open Direction - Early bias indicator
6. NY Opening Drive - Confirmation or reversal

Bias Determination:
- BULLISH: Look for longs only
- BEARISH: Look for shorts only
- NEUTRAL: No clear bias, wait for clarity
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from loguru import logger

try:
    import pytz
    NY_TZ = pytz.timezone('America/New_York')
    UTC_TZ = pytz.UTC
except ImportError:
    from zoneinfo import ZoneInfo
    NY_TZ = ZoneInfo('America/New_York')
    UTC_TZ = ZoneInfo('UTC')


class DailyBias(Enum):
    """Daily directional bias."""
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"


@dataclass
class BiasLevel:
    """Key level for bias analysis."""
    name: str
    price: float
    level_type: str  # 'high', 'low', 'open', 'close'
    timeframe: str  # 'daily', 'weekly', 'session'
    timestamp: datetime


@dataclass
class DailyBiasResult:
    """Complete daily bias analysis result."""
    bias: DailyBias
    confidence: float  # 0-100
    bullish_score: int
    bearish_score: int
    key_levels: List[BiasLevel]
    factors: Dict[str, Dict]
    recommendation: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'bias': self.bias.value,
            'confidence': self.confidence,
            'bullish_score': self.bullish_score,
            'bearish_score': self.bearish_score,
            'key_levels': [
                {
                    'name': l.name,
                    'price': l.price,
                    'level_type': l.level_type,
                    'timeframe': l.timeframe,
                    'timestamp': l.timestamp.isoformat() if l.timestamp else None
                }
                for l in self.key_levels
            ],
            'factors': self.factors,
            'recommendation': self.recommendation,
            'timestamp': self.timestamp.isoformat()
        }


class DailyBiasCalculator:
    """
    Calculate daily directional bias using ICT concepts.

    Uses multiple timeframes and session analysis to determine
    the most probable direction for the trading day.
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize Daily Bias Calculator.

        Args:
            config: Optional configuration
        """
        self.config = config or {}

        # Weights for different factors
        self.weights = {
            'htf_structure': 3,  # Higher timeframe structure (Daily/4H)
            'previous_day': 2,  # PDH/PDL analysis
            'previous_week': 2,  # PWH/PWL analysis
            'asian_range': 2,  # Asian session range
            'london_open': 2,  # London opening direction
            'gap_analysis': 1,  # Opening gap
        }

        self.max_score = sum(self.weights.values())

    def calculate_bias(
        self,
        df_5m: pd.DataFrame,
        df_1h: Optional[pd.DataFrame] = None,
        df_4h: Optional[pd.DataFrame] = None,
        df_daily: Optional[pd.DataFrame] = None
    ) -> DailyBiasResult:
        """
        Calculate daily bias from multiple timeframes.

        Args:
            df_5m: 5-minute OHLCV data (at least 2 days)
            df_1h: Optional 1-hour data
            df_4h: Optional 4-hour data
            df_daily: Optional daily data

        Returns:
            DailyBiasResult with complete analysis
        """
        factors = {}
        key_levels = []
        bullish_score = 0
        bearish_score = 0

        current_price = float(df_5m['close'].iloc[-1])

        # 1. Previous Day Analysis
        pd_result, pd_levels = self._analyze_previous_day(df_5m, current_price)
        factors['previous_day'] = pd_result
        key_levels.extend(pd_levels)
        if pd_result['bias'] == 'bullish':
            bullish_score += pd_result['points']
        elif pd_result['bias'] == 'bearish':
            bearish_score += pd_result['points']

        # 2. Previous Week Analysis (if daily data available)
        if df_daily is not None and len(df_daily) >= 7:
            pw_result, pw_levels = self._analyze_previous_week(df_daily, current_price)
            factors['previous_week'] = pw_result
            key_levels.extend(pw_levels)
            if pw_result['bias'] == 'bullish':
                bullish_score += pw_result['points']
            elif pw_result['bias'] == 'bearish':
                bearish_score += pw_result['points']
        else:
            factors['previous_week'] = {'bias': 'neutral', 'points': 0, 'reason': 'Insufficient daily data'}

        # 3. Higher Timeframe Structure
        # Select highest available timeframe
        htf_df = df_5m
        if df_1h is not None and not df_1h.empty:
            htf_df = df_1h
        if df_4h is not None and not df_4h.empty:
            htf_df = df_4h
        htf_result = self._analyze_htf_structure(htf_df)
        factors['htf_structure'] = htf_result
        if htf_result['bias'] == 'bullish':
            bullish_score += htf_result['points']
        elif htf_result['bias'] == 'bearish':
            bearish_score += htf_result['points']

        # 4. Asian Range Analysis
        asian_result, asian_levels = self._analyze_asian_range(df_5m, current_price)
        factors['asian_range'] = asian_result
        key_levels.extend(asian_levels)
        if asian_result['bias'] == 'bullish':
            bullish_score += asian_result['points']
        elif asian_result['bias'] == 'bearish':
            bearish_score += asian_result['points']

        # 5. London Open Analysis
        london_result = self._analyze_london_open(df_5m, current_price)
        factors['london_open'] = london_result
        if london_result['bias'] == 'bullish':
            bullish_score += london_result['points']
        elif london_result['bias'] == 'bearish':
            bearish_score += london_result['points']

        # 6. Gap Analysis
        gap_result = self._analyze_gap(df_5m, current_price)
        factors['gap_analysis'] = gap_result
        if gap_result['bias'] == 'bullish':
            bullish_score += gap_result['points']
        elif gap_result['bias'] == 'bearish':
            bearish_score += gap_result['points']

        # Determine overall bias
        total_score = bullish_score + bearish_score
        if total_score == 0:
            bias = DailyBias.NEUTRAL
            confidence = 0
        else:
            score_diff = bullish_score - bearish_score
            score_pct = abs(score_diff) / self.max_score * 100

            if score_diff >= 6:
                bias = DailyBias.STRONG_BULLISH
            elif score_diff >= 3:
                bias = DailyBias.BULLISH
            elif score_diff <= -6:
                bias = DailyBias.STRONG_BEARISH
            elif score_diff <= -3:
                bias = DailyBias.BEARISH
            else:
                bias = DailyBias.NEUTRAL

            confidence = min(100, score_pct * 1.5)

        # Generate recommendation
        recommendation = self._generate_recommendation(bias, factors, key_levels, current_price)

        return DailyBiasResult(
            bias=bias,
            confidence=round(confidence, 1),
            bullish_score=bullish_score,
            bearish_score=bearish_score,
            key_levels=key_levels,
            factors=factors,
            recommendation=recommendation
        )

    def _analyze_previous_day(
        self,
        df: pd.DataFrame,
        current_price: float
    ) -> Tuple[Dict, List[BiasLevel]]:
        """Analyze previous day high/low."""
        levels = []
        max_points = self.weights['previous_day']

        # Get previous day's data
        df_with_date = df.copy()
        if not isinstance(df_with_date.index, pd.DatetimeIndex):
            return {'bias': 'neutral', 'points': 0, 'reason': 'Invalid index'}, levels

        # Convert to NY time
        try:
            df_with_date.index = df_with_date.index.tz_convert('America/New_York')
        except:
            try:
                df_with_date.index = df_with_date.index.tz_localize('UTC').tz_convert('America/New_York')
            except:
                pass

        df_with_date['date'] = df_with_date.index.date
        dates = df_with_date['date'].unique()

        if len(dates) < 2:
            return {'bias': 'neutral', 'points': 0, 'reason': 'Need at least 2 days of data'}, levels

        prev_date = dates[-2]
        prev_day_data = df_with_date[df_with_date['date'] == prev_date]

        if prev_day_data.empty:
            return {'bias': 'neutral', 'points': 0, 'reason': 'No previous day data'}, levels

        pdh = float(prev_day_data['high'].max())  # Previous Day High
        pdl = float(prev_day_data['low'].min())  # Previous Day Low
        pdc = float(prev_day_data['close'].iloc[-1])  # Previous Day Close

        levels.append(BiasLevel('PDH', pdh, 'high', 'daily', datetime.combine(prev_date, time(0, 0))))
        levels.append(BiasLevel('PDL', pdl, 'low', 'daily', datetime.combine(prev_date, time(0, 0))))

        # Determine bias based on price position
        pd_range = pdh - pdl
        pd_mid = (pdh + pdl) / 2

        if current_price > pdh:
            # Price above PDH - bullish
            return {
                'bias': 'bullish',
                'points': max_points,
                'reason': f'Price above PDH ({pdh:.2f})',
                'pdh': pdh,
                'pdl': pdl,
                'pdc': pdc
            }, levels
        elif current_price < pdl:
            # Price below PDL - bearish
            return {
                'bias': 'bearish',
                'points': max_points,
                'reason': f'Price below PDL ({pdl:.2f})',
                'pdh': pdh,
                'pdl': pdl,
                'pdc': pdc
            }, levels
        elif current_price > pd_mid:
            # Price in upper half
            return {
                'bias': 'bullish',
                'points': max_points - 1,
                'reason': f'Price in upper half of PDR',
                'pdh': pdh,
                'pdl': pdl,
                'pdc': pdc
            }, levels
        elif current_price < pd_mid:
            # Price in lower half
            return {
                'bias': 'bearish',
                'points': max_points - 1,
                'reason': f'Price in lower half of PDR',
                'pdh': pdh,
                'pdl': pdl,
                'pdc': pdc
            }, levels
        else:
            return {
                'bias': 'neutral',
                'points': 0,
                'reason': 'Price at PDR midpoint',
                'pdh': pdh,
                'pdl': pdl,
                'pdc': pdc
            }, levels

    def _analyze_previous_week(
        self,
        df_daily: pd.DataFrame,
        current_price: float
    ) -> Tuple[Dict, List[BiasLevel]]:
        """Analyze previous week high/low."""
        levels = []
        max_points = self.weights['previous_week']

        if len(df_daily) < 7:
            return {'bias': 'neutral', 'points': 0, 'reason': 'Insufficient data'}, levels

        # Get last week's data (last 5 trading days before today)
        prev_week = df_daily.iloc[-7:-1]  # Last 6 days excluding today

        if prev_week.empty:
            return {'bias': 'neutral', 'points': 0, 'reason': 'No previous week data'}, levels

        pwh = float(prev_week['high'].max())  # Previous Week High
        pwl = float(prev_week['low'].min())  # Previous Week Low

        levels.append(BiasLevel('PWH', pwh, 'high', 'weekly', prev_week.index[0]))
        levels.append(BiasLevel('PWL', pwl, 'low', 'weekly', prev_week.index[0]))

        pw_mid = (pwh + pwl) / 2

        if current_price > pwh:
            return {
                'bias': 'bullish',
                'points': max_points,
                'reason': f'Price above PWH ({pwh:.2f})',
                'pwh': pwh,
                'pwl': pwl
            }, levels
        elif current_price < pwl:
            return {
                'bias': 'bearish',
                'points': max_points,
                'reason': f'Price below PWL ({pwl:.2f})',
                'pwh': pwh,
                'pwl': pwl
            }, levels
        elif current_price > pw_mid:
            return {
                'bias': 'bullish',
                'points': max_points - 1,
                'reason': 'Price in upper half of PWR',
                'pwh': pwh,
                'pwl': pwl
            }, levels
        elif current_price < pw_mid:
            return {
                'bias': 'bearish',
                'points': max_points - 1,
                'reason': 'Price in lower half of PWR',
                'pwh': pwh,
                'pwl': pwl
            }, levels
        else:
            return {
                'bias': 'neutral',
                'points': 0,
                'reason': 'Price at PWR midpoint',
                'pwh': pwh,
                'pwl': pwl
            }, levels

    def _analyze_htf_structure(self, df: pd.DataFrame) -> Dict:
        """Analyze higher timeframe market structure."""
        max_points = self.weights['htf_structure']

        if len(df) < 20:
            return {'bias': 'neutral', 'points': 0, 'reason': 'Insufficient data'}

        # Calculate swing points
        highs = df['high'].values
        lows = df['low'].values

        hh_count = 0
        hl_count = 0
        lh_count = 0
        ll_count = 0

        lookback = 5
        for i in range(lookback, len(df) - lookback):
            # Check for swing high
            if highs[i] == max(highs[i-lookback:i+lookback+1]):
                if i > lookback * 2:
                    prev_highs = [highs[j] for j in range(lookback, i)
                                 if highs[j] == max(highs[j-lookback:j+lookback+1])]
                    if prev_highs and highs[i] > max(prev_highs[-2:] if len(prev_highs) >= 2 else prev_highs):
                        hh_count += 1
                    elif prev_highs and highs[i] < min(prev_highs[-2:] if len(prev_highs) >= 2 else prev_highs):
                        lh_count += 1

            # Check for swing low
            if lows[i] == min(lows[i-lookback:i+lookback+1]):
                if i > lookback * 2:
                    prev_lows = [lows[j] for j in range(lookback, i)
                                if lows[j] == min(lows[j-lookback:j+lookback+1])]
                    if prev_lows and lows[i] > min(prev_lows[-2:] if len(prev_lows) >= 2 else prev_lows):
                        hl_count += 1
                    elif prev_lows and lows[i] < max(prev_lows[-2:] if len(prev_lows) >= 2 else prev_lows):
                        ll_count += 1

        bullish_structure = hh_count + hl_count
        bearish_structure = lh_count + ll_count

        if bullish_structure > bearish_structure + 2:
            return {
                'bias': 'bullish',
                'points': max_points,
                'reason': f'Bullish structure (HH:{hh_count} HL:{hl_count})',
                'hh': hh_count,
                'hl': hl_count,
                'lh': lh_count,
                'll': ll_count
            }
        elif bearish_structure > bullish_structure + 2:
            return {
                'bias': 'bearish',
                'points': max_points,
                'reason': f'Bearish structure (LH:{lh_count} LL:{ll_count})',
                'hh': hh_count,
                'hl': hl_count,
                'lh': lh_count,
                'll': ll_count
            }
        elif bullish_structure > bearish_structure:
            return {
                'bias': 'bullish',
                'points': max_points - 1,
                'reason': 'Slight bullish structure',
                'hh': hh_count,
                'hl': hl_count,
                'lh': lh_count,
                'll': ll_count
            }
        elif bearish_structure > bullish_structure:
            return {
                'bias': 'bearish',
                'points': max_points - 1,
                'reason': 'Slight bearish structure',
                'hh': hh_count,
                'hl': hl_count,
                'lh': lh_count,
                'll': ll_count
            }
        else:
            return {
                'bias': 'neutral',
                'points': 0,
                'reason': 'No clear structure',
                'hh': hh_count,
                'hl': hl_count,
                'lh': lh_count,
                'll': ll_count
            }

    def _analyze_asian_range(
        self,
        df: pd.DataFrame,
        current_price: float
    ) -> Tuple[Dict, List[BiasLevel]]:
        """Analyze Asian session range (7PM - 4AM NY time)."""
        levels = []
        max_points = self.weights['asian_range']

        df_copy = df.copy()
        try:
            df_copy.index = df_copy.index.tz_convert('America/New_York')
        except:
            try:
                df_copy.index = df_copy.index.tz_localize('UTC').tz_convert('America/New_York')
            except:
                return {'bias': 'neutral', 'points': 0, 'reason': 'Cannot convert timezone'}, levels

        # Get today's date
        today = df_copy.index[-1].date()

        # Asian session is 7PM previous day to 4AM today
        asian_start = datetime.combine(today - timedelta(days=1), time(19, 0))
        asian_end = datetime.combine(today, time(4, 0))

        try:
            asian_start = NY_TZ.localize(asian_start) if hasattr(NY_TZ, 'localize') else asian_start.replace(tzinfo=NY_TZ)
            asian_end = NY_TZ.localize(asian_end) if hasattr(NY_TZ, 'localize') else asian_end.replace(tzinfo=NY_TZ)
        except:
            pass

        # Filter Asian session data
        asian_data = df_copy[(df_copy.index >= asian_start) & (df_copy.index <= asian_end)]

        if asian_data.empty or len(asian_data) < 5:
            return {'bias': 'neutral', 'points': 0, 'reason': 'No Asian session data'}, levels

        asian_high = float(asian_data['high'].max())
        asian_low = float(asian_data['low'].min())
        asian_mid = (asian_high + asian_low) / 2

        levels.append(BiasLevel('Asian High', asian_high, 'high', 'session', asian_start))
        levels.append(BiasLevel('Asian Low', asian_low, 'low', 'session', asian_start))

        if current_price > asian_high:
            return {
                'bias': 'bullish',
                'points': max_points,
                'reason': f'Price above Asian High ({asian_high:.2f})',
                'asian_high': asian_high,
                'asian_low': asian_low
            }, levels
        elif current_price < asian_low:
            return {
                'bias': 'bearish',
                'points': max_points,
                'reason': f'Price below Asian Low ({asian_low:.2f})',
                'asian_high': asian_high,
                'asian_low': asian_low
            }, levels
        elif current_price > asian_mid:
            return {
                'bias': 'bullish',
                'points': max_points - 1,
                'reason': 'Price in upper half of Asian range',
                'asian_high': asian_high,
                'asian_low': asian_low
            }, levels
        else:
            return {
                'bias': 'bearish',
                'points': max_points - 1,
                'reason': 'Price in lower half of Asian range',
                'asian_high': asian_high,
                'asian_low': asian_low
            }, levels

    def _analyze_london_open(self, df: pd.DataFrame, current_price: float) -> Dict:
        """Analyze London session opening direction."""
        max_points = self.weights['london_open']

        df_copy = df.copy()
        try:
            df_copy.index = df_copy.index.tz_convert('America/New_York')
        except:
            try:
                df_copy.index = df_copy.index.tz_localize('UTC').tz_convert('America/New_York')
            except:
                return {'bias': 'neutral', 'points': 0, 'reason': 'Cannot convert timezone'}

        today = df_copy.index[-1].date()

        # London open is 3AM NY time
        london_open = datetime.combine(today, time(3, 0))
        london_first_hour = datetime.combine(today, time(4, 0))

        try:
            london_open = NY_TZ.localize(london_open) if hasattr(NY_TZ, 'localize') else london_open.replace(tzinfo=NY_TZ)
            london_first_hour = NY_TZ.localize(london_first_hour) if hasattr(NY_TZ, 'localize') else london_first_hour.replace(tzinfo=NY_TZ)
        except:
            pass

        london_data = df_copy[(df_copy.index >= london_open) & (df_copy.index <= london_first_hour)]

        if london_data.empty:
            return {'bias': 'neutral', 'points': 0, 'reason': 'No London open data'}

        london_open_price = float(london_data['open'].iloc[0])
        london_close_price = float(london_data['close'].iloc[-1])
        london_direction = london_close_price - london_open_price

        if london_direction > 0:
            return {
                'bias': 'bullish',
                'points': max_points,
                'reason': f'London opened bullish (+{london_direction:.2f})',
                'london_open': london_open_price,
                'london_close': london_close_price
            }
        elif london_direction < 0:
            return {
                'bias': 'bearish',
                'points': max_points,
                'reason': f'London opened bearish ({london_direction:.2f})',
                'london_open': london_open_price,
                'london_close': london_close_price
            }
        else:
            return {
                'bias': 'neutral',
                'points': 0,
                'reason': 'London open was flat',
                'london_open': london_open_price,
                'london_close': london_close_price
            }

    def _analyze_gap(self, df: pd.DataFrame, current_price: float) -> Dict:
        """Analyze opening gap from previous day close."""
        max_points = self.weights['gap_analysis']

        df_copy = df.copy()
        try:
            df_copy.index = df_copy.index.tz_convert('America/New_York')
        except:
            try:
                df_copy.index = df_copy.index.tz_localize('UTC').tz_convert('America/New_York')
            except:
                return {'bias': 'neutral', 'points': 0, 'reason': 'Cannot convert timezone'}

        df_copy['date'] = df_copy.index.date
        dates = df_copy['date'].unique()

        if len(dates) < 2:
            return {'bias': 'neutral', 'points': 0, 'reason': 'Need multiple days'}

        prev_date = dates[-2]
        today_date = dates[-1]

        prev_day = df_copy[df_copy['date'] == prev_date]
        today = df_copy[df_copy['date'] == today_date]

        if prev_day.empty or today.empty:
            return {'bias': 'neutral', 'points': 0, 'reason': 'Missing data'}

        prev_close = float(prev_day['close'].iloc[-1])
        today_open = float(today['open'].iloc[0])

        gap = today_open - prev_close
        gap_pct = gap / prev_close * 100

        if gap_pct > 0.3:
            return {
                'bias': 'bullish',
                'points': max_points,
                'reason': f'Gap up +{gap_pct:.2f}%',
                'gap': gap,
                'gap_pct': gap_pct
            }
        elif gap_pct < -0.3:
            return {
                'bias': 'bearish',
                'points': max_points,
                'reason': f'Gap down {gap_pct:.2f}%',
                'gap': gap,
                'gap_pct': gap_pct
            }
        else:
            return {
                'bias': 'neutral',
                'points': 0,
                'reason': f'No significant gap ({gap_pct:.2f}%)',
                'gap': gap,
                'gap_pct': gap_pct
            }

    def _generate_recommendation(
        self,
        bias: DailyBias,
        factors: Dict,
        key_levels: List[BiasLevel],
        current_price: float
    ) -> str:
        """Generate trading recommendation based on bias."""
        lines = []

        if bias == DailyBias.STRONG_BULLISH:
            lines.append("STRONG BULLISH BIAS - Look for LONG setups only")
            lines.append("- Wait for price to retrace to discount/FVG for entry")
            lines.append("- Target: Previous Day High or higher")
        elif bias == DailyBias.BULLISH:
            lines.append("BULLISH BIAS - Prefer LONG setups")
            lines.append("- Look for entries at order blocks or FVGs")
            lines.append("- Be cautious of short-term pullbacks")
        elif bias == DailyBias.STRONG_BEARISH:
            lines.append("STRONG BEARISH BIAS - Look for SHORT setups only")
            lines.append("- Wait for price to retrace to premium/FVG for entry")
            lines.append("- Target: Previous Day Low or lower")
        elif bias == DailyBias.BEARISH:
            lines.append("BEARISH BIAS - Prefer SHORT setups")
            lines.append("- Look for entries at order blocks or FVGs")
            lines.append("- Be cautious of short-term bounces")
        else:
            lines.append("NEUTRAL BIAS - Wait for clarity")
            lines.append("- No clear directional bias")
            lines.append("- Consider sitting out or scalping both directions")

        lines.append("")
        lines.append("Key Levels to Watch:")
        for level in key_levels[:5]:  # Top 5 levels
            lines.append(f"  - {level.name}: {level.price:.2f}")

        return "\n".join(lines)


# Convenience function for quick bias check
def get_daily_bias(df_5m: pd.DataFrame, df_daily: Optional[pd.DataFrame] = None) -> Dict:
    """
    Quick function to get daily bias.

    Args:
        df_5m: 5-minute OHLCV data
        df_daily: Optional daily OHLCV data

    Returns:
        Dictionary with bias info
    """
    calculator = DailyBiasCalculator()
    result = calculator.calculate_bias(df_5m, df_daily=df_daily)

    return {
        'bias': result.bias.value,
        'confidence': result.confidence,
        'recommendation': result.recommendation
    }
