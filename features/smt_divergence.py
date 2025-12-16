"""
SMT (Smart Money Tool) Divergence Detection

SMT Divergence is an ICT concept that identifies divergences between
correlated assets to detect institutional activity.

When two correlated assets (like BTC/ETH, ES/NQ, DXY/EURUSD) make
different swing points, it signals smart money manipulation.

Types of SMT Divergence:
1. Bullish SMT: Asset A makes lower low, Asset B makes higher low
   - Indicates accumulation / stop hunt before move up
2. Bearish SMT: Asset A makes higher high, Asset B makes lower high
   - Indicates distribution / stop hunt before move down

Usage:
- Compare BTC with ETH (high correlation in crypto)
- Compare index futures (ES vs NQ)
- Compare DXY with correlated forex pairs
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class SMTDivergenceType(Enum):
    """Type of SMT divergence"""
    BULLISH = "bullish"  # Asset A lower low, Asset B higher low
    BEARISH = "bearish"  # Asset A higher high, Asset B lower high
    NONE = "none"


@dataclass
class SwingPoint:
    """Represents a swing high or low"""
    timestamp: datetime
    price: float
    swing_type: str  # 'high' or 'low'
    index: int


@dataclass
class SMTDivergence:
    """Represents an SMT divergence event"""
    divergence_type: SMTDivergenceType
    timestamp: datetime

    # Asset A info
    asset_a_symbol: str
    asset_a_swing_type: str  # 'lower_low' or 'higher_high'
    asset_a_swing_price: float
    asset_a_prev_swing_price: float

    # Asset B info
    asset_b_symbol: str
    asset_b_swing_type: str  # 'higher_low' or 'lower_high'
    asset_b_swing_price: float
    asset_b_prev_swing_price: float

    # Analysis
    confidence: float
    strength: float  # Based on the magnitude of divergence
    lookback_candles: int


class SMTDivergenceDetector:
    """
    Detects SMT (Smart Money Tool) divergence between correlated assets.

    SMT divergence occurs when two correlated assets fail to confirm
    each other's swing points, indicating potential smart money activity.
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize SMT Divergence Detector

        Args:
            config: Optional configuration parameters
        """
        self.config = config or {}

        # Swing detection parameters
        self.swing_lookback = self.config.get('swing_lookback', 5)

        # Divergence parameters
        self.min_swing_count = self.config.get('min_swing_count', 2)
        self.max_lookback_candles = self.config.get('max_lookback_candles', 50)

        # Correlation thresholds
        self.min_correlation = self.config.get('min_correlation', 0.5)

        # Pre-defined correlated pairs for crypto
        self.crypto_pairs = {
            'BTC/USD': ['ETH/USD', 'SOL/USD'],
            'ETH/USD': ['BTC/USD', 'SOL/USD'],
            'SOL/USD': ['ETH/USD', 'BTC/USD'],
        }

    def detect_swing_points(self, df: pd.DataFrame,
                           swing_type: str = 'both',
                           lookback: Optional[int] = None) -> List[SwingPoint]:
        """
        Detect swing highs and/or lows in price data

        Args:
            df: OHLCV DataFrame
            swing_type: 'high', 'low', or 'both'
            lookback: Number of bars on each side to confirm swing

        Returns:
            List of SwingPoint objects
        """
        lookback = lookback or self.swing_lookback
        swings = []

        if len(df) < (2 * lookback + 1):
            return swings

        highs = df['high'].values
        lows = df['low'].values

        for i in range(lookback, len(df) - lookback):
            timestamp = df.index[i] if isinstance(df.index[i], datetime) else datetime.now()

            # Check for swing high
            if swing_type in ['high', 'both']:
                is_swing_high = True
                for j in range(1, lookback + 1):
                    if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                        is_swing_high = False
                        break

                if is_swing_high:
                    swings.append(SwingPoint(
                        timestamp=timestamp,
                        price=highs[i],
                        swing_type='high',
                        index=i
                    ))

            # Check for swing low
            if swing_type in ['low', 'both']:
                is_swing_low = True
                for j in range(1, lookback + 1):
                    if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                        is_swing_low = False
                        break

                if is_swing_low:
                    swings.append(SwingPoint(
                        timestamp=timestamp,
                        price=lows[i],
                        swing_type='low',
                        index=i
                    ))

        return sorted(swings, key=lambda x: x.index)

    def calculate_correlation(self, df_a: pd.DataFrame, df_b: pd.DataFrame,
                             period: int = 100) -> float:
        """
        Calculate price correlation between two assets

        Args:
            df_a: OHLCV DataFrame for asset A
            df_b: OHLCV DataFrame for asset B
            period: Number of periods for correlation calculation

        Returns:
            Correlation coefficient (-1 to 1)
        """
        # Align dataframes by timestamp
        common_idx = df_a.index.intersection(df_b.index)

        if len(common_idx) < period:
            return 0.0

        # Use most recent data
        returns_a = df_a.loc[common_idx]['close'].pct_change().dropna().tail(period)
        returns_b = df_b.loc[common_idx]['close'].pct_change().dropna().tail(period)

        if len(returns_a) < 20 or len(returns_b) < 20:
            return 0.0

        # Align again after pct_change
        common_idx = returns_a.index.intersection(returns_b.index)
        returns_a = returns_a.loc[common_idx]
        returns_b = returns_b.loc[common_idx]

        if len(returns_a) < 20:
            return 0.0

        correlation = returns_a.corr(returns_b)
        return correlation if not np.isnan(correlation) else 0.0

    def detect_divergence(self, df_a: pd.DataFrame, df_b: pd.DataFrame,
                         symbol_a: str, symbol_b: str) -> Optional[SMTDivergence]:
        """
        Detect SMT divergence between two assets

        Args:
            df_a: OHLCV DataFrame for asset A (primary)
            df_b: OHLCV DataFrame for asset B (comparison)
            symbol_a: Symbol for asset A
            symbol_b: Symbol for asset B

        Returns:
            SMTDivergence object if divergence detected, None otherwise
        """
        # Get swing points for both assets
        swings_a = self.detect_swing_points(df_a)
        swings_b = self.detect_swing_points(df_b)

        if len(swings_a) < self.min_swing_count or len(swings_b) < self.min_swing_count:
            return None

        # Filter to recent swings within max lookback
        current_idx = len(df_a) - 1
        max_idx = current_idx - self.max_lookback_candles

        recent_swings_a = [s for s in swings_a if s.index >= max_idx]
        recent_swings_b = [s for s in swings_b if s.index >= max_idx]

        if len(recent_swings_a) < 2 or len(recent_swings_b) < 2:
            return None

        # Get last two swing lows from each asset
        swing_lows_a = [s for s in recent_swings_a if s.swing_type == 'low']
        swing_lows_b = [s for s in recent_swings_b if s.swing_type == 'low']

        # Get last two swing highs from each asset
        swing_highs_a = [s for s in recent_swings_a if s.swing_type == 'high']
        swing_highs_b = [s for s in recent_swings_b if s.swing_type == 'high']

        divergence = None

        # Check for Bullish SMT: Asset A lower low, Asset B higher low
        if len(swing_lows_a) >= 2 and len(swing_lows_b) >= 2:
            # Get last two lows
            latest_low_a = swing_lows_a[-1]
            prev_low_a = swing_lows_a[-2]

            latest_low_b = swing_lows_b[-1]
            prev_low_b = swing_lows_b[-2]

            # Check for divergence: A makes lower low, B makes higher low
            if latest_low_a.price < prev_low_a.price and latest_low_b.price > prev_low_b.price:
                # Calculate divergence strength
                divergence_pct_a = abs(latest_low_a.price - prev_low_a.price) / prev_low_a.price * 100
                divergence_pct_b = abs(latest_low_b.price - prev_low_b.price) / prev_low_b.price * 100
                strength = (divergence_pct_a + divergence_pct_b) / 2

                # Calculate confidence based on how clear the divergence is
                confidence = min(100, 50 + strength * 10)

                divergence = SMTDivergence(
                    divergence_type=SMTDivergenceType.BULLISH,
                    timestamp=latest_low_a.timestamp,
                    asset_a_symbol=symbol_a,
                    asset_a_swing_type='lower_low',
                    asset_a_swing_price=latest_low_a.price,
                    asset_a_prev_swing_price=prev_low_a.price,
                    asset_b_symbol=symbol_b,
                    asset_b_swing_type='higher_low',
                    asset_b_swing_price=latest_low_b.price,
                    asset_b_prev_swing_price=prev_low_b.price,
                    confidence=confidence,
                    strength=strength,
                    lookback_candles=current_idx - min(latest_low_a.index, latest_low_b.index)
                )

        # Check for Bearish SMT: Asset A higher high, Asset B lower high
        if divergence is None and len(swing_highs_a) >= 2 and len(swing_highs_b) >= 2:
            # Get last two highs
            latest_high_a = swing_highs_a[-1]
            prev_high_a = swing_highs_a[-2]

            latest_high_b = swing_highs_b[-1]
            prev_high_b = swing_highs_b[-2]

            # Check for divergence: A makes higher high, B makes lower high
            if latest_high_a.price > prev_high_a.price and latest_high_b.price < prev_high_b.price:
                # Calculate divergence strength
                divergence_pct_a = abs(latest_high_a.price - prev_high_a.price) / prev_high_a.price * 100
                divergence_pct_b = abs(latest_high_b.price - prev_high_b.price) / prev_high_b.price * 100
                strength = (divergence_pct_a + divergence_pct_b) / 2

                # Calculate confidence
                confidence = min(100, 50 + strength * 10)

                divergence = SMTDivergence(
                    divergence_type=SMTDivergenceType.BEARISH,
                    timestamp=latest_high_a.timestamp,
                    asset_a_symbol=symbol_a,
                    asset_a_swing_type='higher_high',
                    asset_a_swing_price=latest_high_a.price,
                    asset_a_prev_swing_price=prev_high_a.price,
                    asset_b_symbol=symbol_b,
                    asset_b_swing_type='lower_high',
                    asset_b_swing_price=latest_high_b.price,
                    asset_b_prev_swing_price=prev_high_b.price,
                    confidence=confidence,
                    strength=strength,
                    lookback_candles=current_idx - min(latest_high_a.index, latest_high_b.index)
                )

        return divergence

    def analyze(self, primary_df: pd.DataFrame, comparison_df: pd.DataFrame,
                primary_symbol: str, comparison_symbol: str) -> Dict[str, Any]:
        """
        Full SMT divergence analysis

        Args:
            primary_df: OHLCV DataFrame for primary asset
            comparison_df: OHLCV DataFrame for comparison asset
            primary_symbol: Symbol for primary asset
            comparison_symbol: Symbol for comparison asset

        Returns:
            Dictionary with analysis results
        """
        result = {
            'primary_symbol': primary_symbol,
            'comparison_symbol': comparison_symbol,
            'correlation': 0.0,
            'divergence': None,
            'swing_points_primary': [],
            'swing_points_comparison': [],
            'timestamp': datetime.now().isoformat()
        }

        # Calculate correlation
        correlation = self.calculate_correlation(primary_df, comparison_df)
        result['correlation'] = round(correlation, 4)

        # Only look for divergence if correlation is significant
        if abs(correlation) < self.min_correlation:
            result['warning'] = f"Low correlation ({correlation:.2f}). SMT divergence may not be reliable."

        # Detect swing points
        swings_primary = self.detect_swing_points(primary_df)
        swings_comparison = self.detect_swing_points(comparison_df)

        result['swing_points_primary'] = [
            {'timestamp': s.timestamp.isoformat() if isinstance(s.timestamp, datetime) else str(s.timestamp),
             'price': s.price, 'type': s.swing_type}
            for s in swings_primary[-10:]  # Last 10 swings
        ]

        result['swing_points_comparison'] = [
            {'timestamp': s.timestamp.isoformat() if isinstance(s.timestamp, datetime) else str(s.timestamp),
             'price': s.price, 'type': s.swing_type}
            for s in swings_comparison[-10:]
        ]

        # Detect divergence
        divergence = self.detect_divergence(
            primary_df, comparison_df,
            primary_symbol, comparison_symbol
        )

        if divergence:
            result['divergence'] = {
                'type': divergence.divergence_type.value,
                'timestamp': divergence.timestamp.isoformat() if isinstance(divergence.timestamp, datetime) else str(divergence.timestamp),
                'confidence': round(divergence.confidence, 1),
                'strength': round(divergence.strength, 4),
                'primary': {
                    'symbol': divergence.asset_a_symbol,
                    'swing_type': divergence.asset_a_swing_type,
                    'current_price': divergence.asset_a_swing_price,
                    'previous_price': divergence.asset_a_prev_swing_price
                },
                'comparison': {
                    'symbol': divergence.asset_b_symbol,
                    'swing_type': divergence.asset_b_swing_type,
                    'current_price': divergence.asset_b_swing_price,
                    'previous_price': divergence.asset_b_prev_swing_price
                },
                'lookback_candles': divergence.lookback_candles,
                'signal': 'BUY' if divergence.divergence_type == SMTDivergenceType.BULLISH else 'SELL'
            }

        return result

    def analyze_crypto_pair(self, symbol: str,
                           fetcher_func) -> Dict[str, Any]:
        """
        Analyze SMT divergence for a crypto pair against its correlated assets

        Args:
            symbol: Primary symbol (e.g., 'BTC/USDT')
            fetcher_func: Function to fetch OHLCV data: fetcher_func(symbol, timeframe, limit)

        Returns:
            Dictionary with divergence analysis against all correlated assets
        """
        # Get correlated pairs
        correlated = self.crypto_pairs.get(symbol, [])

        if not correlated:
            # Default to BTC/ETH correlation for other pairs
            if 'BTC' not in symbol:
                correlated = ['BTC/USD']
            elif 'ETH' not in symbol:
                correlated = ['ETH/USD']

        results = {
            'symbol': symbol,
            'analyses': [],
            'strongest_divergence': None,
            'timestamp': datetime.now().isoformat()
        }

        try:
            # Fetch primary data
            primary_df = fetcher_func(symbol, '5m', 200)

            if primary_df.empty:
                results['error'] = 'Could not fetch primary asset data'
                return results

            strongest_div = None
            strongest_confidence = 0

            for comp_symbol in correlated:
                try:
                    # Fetch comparison data
                    comp_df = fetcher_func(comp_symbol, '5m', 200)

                    if comp_df.empty:
                        continue

                    # Analyze divergence
                    analysis = self.analyze(
                        primary_df, comp_df,
                        symbol, comp_symbol
                    )

                    results['analyses'].append(analysis)

                    # Track strongest divergence
                    if analysis['divergence']:
                        div_confidence = analysis['divergence']['confidence']
                        if div_confidence > strongest_confidence:
                            strongest_confidence = div_confidence
                            strongest_div = analysis['divergence']

                except Exception as e:
                    results['analyses'].append({
                        'comparison_symbol': comp_symbol,
                        'error': str(e)
                    })

            results['strongest_divergence'] = strongest_div

        except Exception as e:
            results['error'] = str(e)

        return results

    def get_smt_features(self, df_primary: pd.DataFrame,
                        df_comparison: pd.DataFrame) -> Dict[str, float]:
        """
        Generate SMT-related features for ML model

        Args:
            df_primary: Primary asset OHLCV
            df_comparison: Comparison asset OHLCV

        Returns:
            Dictionary of SMT features
        """
        features = {
            'smt_correlation': 0.0,
            'smt_bullish_divergence': 0,
            'smt_bearish_divergence': 0,
            'smt_divergence_strength': 0.0,
            'smt_divergence_confidence': 0.0,
            'smt_swing_alignment': 0.0,
        }

        # Calculate correlation
        features['smt_correlation'] = self.calculate_correlation(df_primary, df_comparison)

        # Detect divergence
        divergence = self.detect_divergence(
            df_primary, df_comparison,
            'primary', 'comparison'
        )

        if divergence:
            if divergence.divergence_type == SMTDivergenceType.BULLISH:
                features['smt_bullish_divergence'] = 1
            elif divergence.divergence_type == SMTDivergenceType.BEARISH:
                features['smt_bearish_divergence'] = 1

            features['smt_divergence_strength'] = divergence.strength
            features['smt_divergence_confidence'] = divergence.confidence / 100.0

        # Calculate swing alignment (how well swings match up)
        swings_primary = self.detect_swing_points(df_primary)
        swings_comparison = self.detect_swing_points(df_comparison)

        if swings_primary and swings_comparison:
            # Check last few swings for alignment
            recent_primary = swings_primary[-3:] if len(swings_primary) >= 3 else swings_primary
            recent_comparison = swings_comparison[-3:] if len(swings_comparison) >= 3 else swings_comparison

            aligned = 0
            for sp in recent_primary:
                for sc in recent_comparison:
                    # Within 5 bars of each other and same type
                    if abs(sp.index - sc.index) <= 5 and sp.swing_type == sc.swing_type:
                        aligned += 1
                        break

            features['smt_swing_alignment'] = aligned / len(recent_primary) if recent_primary else 0

        return features


# Example usage
if __name__ == "__main__":
    # Create sample data for testing
    np.random.seed(42)

    # Generate correlated sample data
    dates = pd.date_range(start='2024-01-01', periods=200, freq='5min')

    def generate_ohlcv(base_price, volatility, dates):
        data = []
        price = base_price
        for date in dates:
            change = np.random.randn() * volatility
            open_price = price
            high_price = price + abs(np.random.randn() * volatility / 2)
            low_price = price - abs(np.random.randn() * volatility / 2)
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
        return pd.DataFrame(data, index=dates)

    # BTC-like data
    df_btc = generate_ohlcv(100000, 500, dates)

    # ETH-like data (correlated but with some divergence)
    df_eth = generate_ohlcv(3000, 30, dates)

    # Add some artificial divergence
    # Make BTC make lower low while ETH makes higher low
    df_btc.iloc[-10:, 2] = df_btc.iloc[-10:, 2] - 200  # Lower the lows
    df_eth.iloc[-10:, 2] = df_eth.iloc[-10:, 2] + 10   # Raise the lows

    # Test the detector
    detector = SMTDivergenceDetector()

    # Calculate correlation
    correlation = detector.calculate_correlation(df_btc, df_eth)
    print(f"BTC/ETH Correlation: {correlation:.4f}")

    # Detect swing points
    btc_swings = detector.detect_swing_points(df_btc)
    eth_swings = detector.detect_swing_points(df_eth)
    print(f"\nBTC Swing Points: {len(btc_swings)}")
    print(f"ETH Swing Points: {len(eth_swings)}")

    # Analyze for divergence
    result = detector.analyze(df_btc, df_eth, 'BTC/USD', 'ETH/USD')
    print(f"\nSMT Analysis:")
    print(f"  Correlation: {result['correlation']}")
    if result['divergence']:
        div = result['divergence']
        print(f"  Divergence Type: {div['type']}")
        print(f"  Confidence: {div['confidence']}%")
        print(f"  Signal: {div['signal']}")
    else:
        print("  No divergence detected")

    # Get ML features
    features = detector.get_smt_features(df_btc, df_eth)
    print(f"\nSMT Features for ML:")
    for k, v in features.items():
        print(f"  {k}: {v}")
