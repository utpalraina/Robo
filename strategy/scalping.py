"""
Scalping Strategy - Confluence-Based High Frequency Trading.

This strategy makes buy/sell decisions based on MAXIMUM CONFLUENCE of all
available signals in the system:

1. ICT Strategy Signals:
   - Market Structure (trend direction)
   - Premium/Discount Zone
   - Order Blocks
   - Fair Value Gaps
   - OTE Levels
   - Market Structure Shifts
   - Liquidity Zones
   - Displacement

2. SMT Divergence:
   - BTC vs ETH correlation divergence
   - Bullish/Bearish divergence signals

3. Multi-Timeframe Analysis:
   - 1m for entry precision
   - 5m for short-term trend
   - 15m for confirmation

4. ML Model Predictions:
   - XGBoost model confidence

5. Technical Indicators:
   - RSI
   - MACD
   - Bollinger Bands
   - Volume

DECISION RULE:
- Only enter when confluence score >= minimum threshold
- More confluence = higher confidence = larger position
- Conflicting signals = stay out
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from features.ict_indicators import ICTIndicators
from features.smt_divergence import SMTDivergenceDetector, SMTDivergenceType
from strategy.confluence import ConfluenceDetector, ConfluenceStrength


class ScalpSignal(Enum):
    """Scalping signal types."""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class TradingMode(Enum):
    """Trading mode presets with different risk/reward profiles."""
    SAFE = "safe"
    MEDIUM = "medium"
    FAST = "fast"
    CUSTOM = "custom"


# Preset configurations for each mode
TRADING_MODE_PRESETS = {
    TradingMode.SAFE: {
        "name": "Safe Mode",
        "description": "Conservative trading - waits for strong confluence (fewer trades, higher win rate)",
        "min_confluence_score": 18,      # High confluence required
        "strong_confluence_score": 22,
        "min_confidence": 55,            # 55% minimum confidence
        "strong_confidence": 70,
        "min_aligned_signals": 3,        # Need 3+ signals aligned
        "strong_aligned_signals": 4,
        "take_profit_pct": 0.002,        # 0.2% take profit
        "stop_loss_pct": 0.001,          # 0.1% stop loss (2:1 R:R)
        "cooldown_seconds": 60,          # 1 minute between trades
        "max_trades_per_hour": 5,
    },
    TradingMode.MEDIUM: {
        "name": "Medium Mode",
        "description": "Balanced trading - moderate confluence requirements",
        "min_confluence_score": 12,
        "strong_confluence_score": 17,
        "min_confidence": 40,
        "strong_confidence": 55,
        "min_aligned_signals": 2,
        "strong_aligned_signals": 3,
        "take_profit_pct": 0.0015,       # 0.15% take profit
        "stop_loss_pct": 0.001,          # 0.1% stop loss (1.5:1 R:R)
        "cooldown_seconds": 30,
        "max_trades_per_hour": 10,
    },
    TradingMode.FAST: {
        "name": "Fast Mode",
        "description": "Aggressive trading - lower confluence, more trades (higher risk)",
        "min_confluence_score": 8,
        "strong_confluence_score": 12,
        "min_confidence": 30,
        "strong_confidence": 45,
        "min_aligned_signals": 1,        # Just 1 signal can trigger
        "strong_aligned_signals": 2,
        "take_profit_pct": 0.001,        # 0.1% take profit
        "stop_loss_pct": 0.001,          # 0.1% stop loss (1:1 R:R)
        "cooldown_seconds": 15,
        "max_trades_per_hour": 20,
    },
    TradingMode.CUSTOM: {
        "name": "Custom Mode",
        "description": "User-defined parameters",
        # Uses whatever the user provides
    }
}


@dataclass
class ScalpEntry:
    """Scalp trade entry details."""
    signal: ScalpSignal
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    confidence: float
    reason: str
    timestamp: datetime
    confluence_details: Dict = None


class ScalpingStrategy:
    """
    Confluence-based scalping strategy.

    Makes trading decisions by aggregating ALL available signals:
    - ICT patterns (FVG, MSS, OB, OTE, Liquidity)
    - SMT Divergence (BTC/ETH correlation)
    - Multi-timeframe analysis
    - ML model predictions
    - Technical indicators

    Only trades when multiple signals AGREE (high confluence).

    Supports trading modes:
    - SAFE: Conservative, high confluence required, fewer trades
    - MEDIUM: Balanced approach
    - FAST: Aggressive, lower confluence, more trades
    - CUSTOM: User-defined parameters
    """

    # Mapping of confluence checkbox values to signal categories
    CONFLUENCE_MAPPING = {
        # ICT Strategy signals
        'fvg': 'ict_confluence',
        'mss': 'ict_confluence',
        'ob': 'ict_confluence',
        'ote': 'ict_confluence',
        'liquidity': 'ict_confluence',
        'premium_discount': 'ict_confluence',
        # SMT Divergence
        'smt': 'smt_divergence',
        # Multi-Timeframe
        'mtf_1m': 'mtf_alignment',
        'mtf_5m': 'mtf_alignment',
        'mtf_15m': 'mtf_alignment',
        # ML Prediction
        'ml_xgboost': 'ml_prediction',
        # Momentum indicators
        'rsi': 'momentum',
        'macd': 'momentum',
        'bollinger': 'momentum',
        'volume': 'momentum',
    }

    # All available confluences grouped by category
    ALL_CONFLUENCES = {
        'ict_confluence': ['fvg', 'mss', 'ob', 'ote', 'liquidity', 'premium_discount'],
        'smt_divergence': ['smt'],
        'mtf_alignment': ['mtf_1m', 'mtf_5m', 'mtf_15m'],
        'ml_prediction': ['ml_xgboost'],
        'momentum': ['rsi', 'macd', 'bollinger', 'volume'],
    }

    def __init__(self, config: Optional[Dict] = None, mode: TradingMode = TradingMode.MEDIUM):
        """
        Initialize scalping strategy with confluence detection.

        Args:
            config: Optional configuration dict (overrides preset values)
            mode: Trading mode preset (SAFE, MEDIUM, FAST, CUSTOM)
        """
        self.config = config or {}
        self.mode = mode

        # Apply mode preset first, then override with any custom config
        self._apply_mode_preset(mode)

        # Enabled confluences (None means all enabled)
        self.enabled_confluences = self.config.get('enabled_confluences', None)
        self._update_enabled_categories()

        # Signal weights for final decision (will be adjusted based on enabled confluences)
        self.base_weights = {
            'ict_confluence': 40,      # ICT patterns (40% weight)
            'smt_divergence': 20,      # SMT divergence (20% weight)
            'mtf_alignment': 15,       # Multi-timeframe (15% weight)
            'ml_prediction': 15,       # ML model (15% weight)
            'momentum': 10,            # Technical momentum (10% weight)
        }
        self._update_weights()

        # Initialize detectors
        self.ict = ICTIndicators()
        self.confluence_detector = ConfluenceDetector({
            'min_tradeable_score': self.min_confluence_score,
            'min_risk_reward': 1.5
        })
        self.smt_detector = SMTDivergenceDetector()

        # Trade tracking
        self.last_trade_time = None
        self.hourly_trades = []

        # Volatility filters (adjusted for 1m timeframe - ATR is much smaller)
        self.min_atr_pct = self.config.get('min_atr_pct', 0.00005)  # 0.005% min
        self.max_atr_pct = self.config.get('max_atr_pct', 0.01)      # 1% max

        logger.info(f"ScalpingStrategy initialized with {mode.value.upper()} mode")
        logger.info(f"Min confluence: {self.min_confluence_score}/30, Min confidence: {self.min_confidence}%")
        logger.info(f"TP: {self.take_profit_pct*100:.2f}%, SL: {self.stop_loss_pct*100:.2f}%")
        if self.enabled_confluences:
            logger.info(f"Enabled confluences: {self.enabled_confluences}")
            logger.info(f"Enabled categories: {list(self.enabled_categories)}")

    def _update_enabled_categories(self):
        """Update which signal categories are enabled based on selected confluences."""
        if self.enabled_confluences is None:
            # All enabled
            self.enabled_categories = set(self.base_weights.keys()) if hasattr(self, 'base_weights') else {
                'ict_confluence', 'smt_divergence', 'mtf_alignment', 'ml_prediction', 'momentum'
            }
            self.enabled_ict_signals = set(self.ALL_CONFLUENCES['ict_confluence'])
            self.enabled_momentum_signals = set(self.ALL_CONFLUENCES['momentum'])
            self.enabled_mtf_signals = set(self.ALL_CONFLUENCES['mtf_alignment'])
        else:
            self.enabled_categories = set()
            self.enabled_ict_signals = set()
            self.enabled_momentum_signals = set()
            self.enabled_mtf_signals = set()

            for confluence in self.enabled_confluences:
                category = self.CONFLUENCE_MAPPING.get(confluence)
                if category:
                    self.enabled_categories.add(category)
                    if category == 'ict_confluence':
                        self.enabled_ict_signals.add(confluence)
                    elif category == 'momentum':
                        self.enabled_momentum_signals.add(confluence)
                    elif category == 'mtf_alignment':
                        self.enabled_mtf_signals.add(confluence)

    def _update_weights(self):
        """Update weights based on enabled categories, redistributing to active signals."""
        if not hasattr(self, 'enabled_categories') or not self.enabled_categories:
            self.weights = self.base_weights.copy()
            return

        # Start with base weights for enabled categories
        self.weights = {}
        total_enabled_weight = 0

        for category, weight in self.base_weights.items():
            if category in self.enabled_categories:
                self.weights[category] = weight
                total_enabled_weight += weight
            else:
                self.weights[category] = 0

        # Normalize weights to sum to 100 if some categories are disabled
        if total_enabled_weight > 0 and total_enabled_weight < 100:
            scale_factor = 100 / total_enabled_weight
            for category in self.weights:
                if self.weights[category] > 0:
                    self.weights[category] = self.weights[category] * scale_factor

    def set_enabled_confluences(self, confluences: Optional[List[str]]):
        """
        Set which confluence signals are enabled.

        Args:
            confluences: List of confluence IDs to enable, or None for all
        """
        self.enabled_confluences = confluences
        self._update_enabled_categories()
        self._update_weights()
        logger.info(f"Updated enabled confluences: {confluences}")
        logger.info(f"Active categories: {self.enabled_categories}")
        logger.info(f"Adjusted weights: {self.weights}")

    def is_category_enabled(self, category: str) -> bool:
        """Check if a signal category is enabled."""
        return category in self.enabled_categories

    def is_confluence_enabled(self, confluence: str) -> bool:
        """Check if a specific confluence signal is enabled."""
        if self.enabled_confluences is None:
            return True
        return confluence in self.enabled_confluences

    def _apply_mode_preset(self, mode: TradingMode):
        """Apply trading mode preset values."""
        preset = TRADING_MODE_PRESETS.get(mode, TRADING_MODE_PRESETS[TradingMode.MEDIUM])

        # For CUSTOM mode, use config values with MEDIUM defaults
        if mode == TradingMode.CUSTOM:
            preset = TRADING_MODE_PRESETS[TradingMode.MEDIUM].copy()

        # Apply preset values, allowing config overrides
        self.take_profit_pct = self.config.get('take_profit_pct', preset.get('take_profit_pct', 0.0015))
        self.stop_loss_pct = self.config.get('stop_loss_pct', preset.get('stop_loss_pct', 0.001))
        self.min_confluence_score = self.config.get('min_confluence_score', preset.get('min_confluence_score', 12))
        self.strong_confluence_score = self.config.get('strong_confluence_score', preset.get('strong_confluence_score', 17))
        self.min_confidence = self.config.get('min_confidence', preset.get('min_confidence', 40))
        self.strong_confidence = self.config.get('strong_confidence', preset.get('strong_confidence', 55))
        self.min_aligned_signals = self.config.get('min_aligned_signals', preset.get('min_aligned_signals', 2))
        self.strong_aligned_signals = self.config.get('strong_aligned_signals', preset.get('strong_aligned_signals', 3))
        self.cooldown_seconds = self.config.get('cooldown_seconds', preset.get('cooldown_seconds', 30))
        self.max_trades_per_hour = self.config.get('max_trades_per_hour', preset.get('max_trades_per_hour', 10))

    def set_mode(self, mode: TradingMode, custom_config: Optional[Dict] = None):
        """
        Change trading mode at runtime.

        Args:
            mode: New trading mode
            custom_config: Optional custom parameters (for CUSTOM mode)
        """
        self.mode = mode
        if custom_config:
            self.config.update(custom_config)
        self._apply_mode_preset(mode)

        # Update confluence detector
        self.confluence_detector = ConfluenceDetector({
            'min_tradeable_score': self.min_confluence_score,
            'min_risk_reward': 1.5
        })

        logger.info(f"Trading mode changed to {mode.value.upper()}")
        logger.info(f"New settings - Confluence: {self.min_confluence_score}/30, Confidence: {self.min_confidence}%")

    def get_mode_info(self) -> Dict:
        """Get current mode information and settings."""
        preset = TRADING_MODE_PRESETS.get(self.mode, {})
        return {
            "mode": self.mode.value,
            "name": preset.get("name", "Custom Mode"),
            "description": preset.get("description", "User-defined parameters"),
            "settings": {
                "min_confluence_score": self.min_confluence_score,
                "strong_confluence_score": self.strong_confluence_score,
                "min_confidence": self.min_confidence,
                "strong_confidence": self.strong_confidence,
                "min_aligned_signals": self.min_aligned_signals,
                "strong_aligned_signals": self.strong_aligned_signals,
                "take_profit_pct": self.take_profit_pct,
                "stop_loss_pct": self.stop_loss_pct,
                "cooldown_seconds": self.cooldown_seconds,
                "max_trades_per_hour": self.max_trades_per_hour,
            },
            "enabled_confluences": self.enabled_confluences,
            "enabled_categories": list(self.enabled_categories),
            "weights": self.weights
        }

    @staticmethod
    def get_available_modes() -> Dict:
        """Get all available trading modes and their descriptions."""
        return {
            mode.value: {
                "name": preset.get("name"),
                "description": preset.get("description"),
                "settings": {k: v for k, v in preset.items() if k not in ["name", "description"]}
            }
            for mode, preset in TRADING_MODE_PRESETS.items()
        }

    def _check_cooldown(self) -> bool:
        """Check if cooldown period has passed."""
        if self.last_trade_time is None:
            return True
        elapsed = (datetime.utcnow() - self.last_trade_time).total_seconds()
        return elapsed >= self.cooldown_seconds

    def _check_hourly_limit(self) -> bool:
        """Check if hourly trade limit is reached."""
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        self.hourly_trades = [t for t in self.hourly_trades if t > hour_ago]
        return len(self.hourly_trades) < self.max_trades_per_hour

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

    def _get_ict_confluence(self, df: pd.DataFrame, current_price: float, atr: float) -> Dict:
        """
        Get ICT confluence analysis using all ICT patterns.

        Returns dict with:
        - score: 0-30 (ICT confluence score)
        - direction: 'long', 'short', or 'neutral'
        - details: breakdown of each factor
        """
        try:
            # Detect all ICT patterns
            ict_data = self.ict.detect_all(df)

            # Run full confluence analysis
            confluence_result = self.confluence_detector.analyze(
                ict_data=ict_data,
                current_price=current_price,
                atr=atr,
                direction='auto'
            )

            return {
                'score': confluence_result.total_score,
                'max_score': confluence_result.max_score,
                'score_pct': confluence_result.score_pct,
                'direction': confluence_result.direction,
                'strength': confluence_result.strength.value,
                'is_tradeable': confluence_result.is_tradeable,
                'entry_price': confluence_result.entry_price,
                'stop_loss': confluence_result.stop_loss,
                'take_profit_1': confluence_result.take_profit_1,
                'factors': [
                    {
                        'name': f.name,
                        'points': f.points,
                        'max_points': f.max_points,
                        'reason': f.reason,
                        'is_aligned': f.is_aligned
                    }
                    for f in confluence_result.factors
                ]
            }
        except Exception as e:
            logger.warning(f"ICT confluence error: {e}")
            return {
                'score': 0,
                'max_score': 30,
                'score_pct': 0,
                'direction': 'neutral',
                'strength': 'none',
                'is_tradeable': False,
                'factors': [],
                'error': str(e)
            }

    def _get_smt_divergence(self, df_primary: pd.DataFrame, df_comparison: pd.DataFrame,
                           primary_symbol: str = 'BTC/USD', comparison_symbol: str = 'ETH/USD') -> Dict:
        """
        Get SMT divergence signal between two correlated assets.

        Returns dict with:
        - signal: 'bullish', 'bearish', or 'none'
        - confidence: 0-100
        - details: divergence info
        """
        try:
            result = self.smt_detector.analyze(
                df_primary, df_comparison,
                primary_symbol, comparison_symbol
            )

            divergence = result.get('divergence')

            if divergence:
                return {
                    'signal': divergence['type'],
                    'confidence': divergence['confidence'],
                    'strength': divergence['strength'],
                    'correlation': result['correlation'],
                    'details': divergence
                }
            else:
                return {
                    'signal': 'none',
                    'confidence': 0,
                    'strength': 0,
                    'correlation': result['correlation'],
                    'details': None
                }
        except Exception as e:
            logger.warning(f"SMT divergence error: {e}")
            return {
                'signal': 'none',
                'confidence': 0,
                'strength': 0,
                'correlation': 0,
                'error': str(e)
            }

    def _get_momentum_score(self, df: pd.DataFrame) -> Tuple[float, str]:
        """
        Calculate momentum score from technical indicators.

        Returns: (score -100 to 100, reason string)
        """
        if len(df) < 20:
            return 0, "Insufficient data"

        score = 0
        reasons = []

        # 1. RSI Analysis
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50

        if current_rsi < 30:
            score += 30
            reasons.append(f"RSI oversold ({current_rsi:.1f})")
        elif current_rsi > 70:
            score -= 30
            reasons.append(f"RSI overbought ({current_rsi:.1f})")
        elif current_rsi < 45:
            score += 10
        elif current_rsi > 55:
            score -= 10

        # 2. MACD Analysis
        ema_12 = df['close'].ewm(span=12).mean()
        ema_26 = df['close'].ewm(span=26).mean()
        macd = ema_12 - ema_26
        signal_line = macd.ewm(span=9).mean()
        macd_hist = macd - signal_line

        if macd.iloc[-1] > signal_line.iloc[-1]:
            if macd.iloc[-2] <= signal_line.iloc[-2]:
                score += 25
                reasons.append("MACD bullish crossover")
            else:
                score += 10
        else:
            if macd.iloc[-2] >= signal_line.iloc[-2]:
                score -= 25
                reasons.append("MACD bearish crossover")
            else:
                score -= 10

        # 3. Bollinger Bands
        sma_20 = df['close'].rolling(20).mean()
        std_20 = df['close'].rolling(20).std()
        upper_band = sma_20 + (2 * std_20)
        lower_band = sma_20 - (2 * std_20)

        current_price = df['close'].iloc[-1]
        if current_price <= lower_band.iloc[-1]:
            score += 20
            reasons.append("Price at lower BB")
        elif current_price >= upper_band.iloc[-1]:
            score -= 20
            reasons.append("Price at upper BB")

        # 4. Volume Confirmation
        vol_sma = df['volume'].rolling(20).mean()
        current_vol = df['volume'].iloc[-1]

        if current_vol > vol_sma.iloc[-1] * 1.5:
            score = int(score * 1.3)  # Amplify signal on high volume
            reasons.append("High volume confirms")

        # Clamp score
        score = max(-100, min(100, score))

        return score, " | ".join(reasons) if reasons else "Neutral momentum"

    def _get_momentum_score_filtered(self, df: pd.DataFrame) -> Tuple[float, str]:
        """
        Calculate momentum score from ONLY enabled technical indicators.

        Returns: (score -100 to 100, reason string)
        """
        if len(df) < 20:
            return 0, "Insufficient data"

        score = 0
        reasons = []
        enabled_count = 0

        # 1. RSI Analysis - only if enabled
        if self.is_confluence_enabled('rsi'):
            enabled_count += 1
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50

            if current_rsi < 30:
                score += 30
                reasons.append(f"RSI oversold ({current_rsi:.1f})")
            elif current_rsi > 70:
                score -= 30
                reasons.append(f"RSI overbought ({current_rsi:.1f})")
            elif current_rsi < 45:
                score += 10
            elif current_rsi > 55:
                score -= 10

        # 2. MACD Analysis - only if enabled
        if self.is_confluence_enabled('macd'):
            enabled_count += 1
            ema_12 = df['close'].ewm(span=12).mean()
            ema_26 = df['close'].ewm(span=26).mean()
            macd = ema_12 - ema_26
            signal_line = macd.ewm(span=9).mean()

            if macd.iloc[-1] > signal_line.iloc[-1]:
                if macd.iloc[-2] <= signal_line.iloc[-2]:
                    score += 25
                    reasons.append("MACD bullish crossover")
                else:
                    score += 10
            else:
                if macd.iloc[-2] >= signal_line.iloc[-2]:
                    score -= 25
                    reasons.append("MACD bearish crossover")
                else:
                    score -= 10

        # 3. Bollinger Bands - only if enabled
        if self.is_confluence_enabled('bollinger'):
            enabled_count += 1
            sma_20 = df['close'].rolling(20).mean()
            std_20 = df['close'].rolling(20).std()
            upper_band = sma_20 + (2 * std_20)
            lower_band = sma_20 - (2 * std_20)

            current_price = df['close'].iloc[-1]
            if current_price <= lower_band.iloc[-1]:
                score += 20
                reasons.append("Price at lower BB")
            elif current_price >= upper_band.iloc[-1]:
                score -= 20
                reasons.append("Price at upper BB")

        # 4. Volume Confirmation - only if enabled
        if self.is_confluence_enabled('volume'):
            enabled_count += 1
            vol_sma = df['volume'].rolling(20).mean()
            current_vol = df['volume'].iloc[-1]

            if current_vol > vol_sma.iloc[-1] * 1.5:
                score = int(score * 1.3)  # Amplify signal on high volume
                reasons.append("High volume confirms")

        # Normalize score if not all indicators are enabled
        if enabled_count > 0 and enabled_count < 4:
            # Scale score proportionally to maintain relative weight
            score = int(score * (4 / enabled_count))

        # Clamp score
        score = max(-100, min(100, score))

        if not reasons:
            if enabled_count == 0:
                return 0, "No momentum indicators enabled"
            return 0, "Neutral momentum"

        return score, " | ".join(reasons)

    def _get_mtf_alignment(self, df_1m: pd.DataFrame, df_5m: pd.DataFrame = None,
                          df_15m: pd.DataFrame = None) -> Dict:
        """
        Check multi-timeframe alignment.

        Returns:
        - aligned: bool
        - direction: 'bullish', 'bearish', or 'mixed'
        - score: 0-100
        """
        signals = []

        # 1m trend
        if len(df_1m) >= 20:
            ema_9 = df_1m['close'].ewm(span=9).mean()
            ema_21 = df_1m['close'].ewm(span=21).mean()
            if ema_9.iloc[-1] > ema_21.iloc[-1]:
                signals.append('bullish')
            else:
                signals.append('bearish')

        # 5m trend (if provided)
        if df_5m is not None and len(df_5m) >= 20:
            ema_9 = df_5m['close'].ewm(span=9).mean()
            ema_21 = df_5m['close'].ewm(span=21).mean()
            if ema_9.iloc[-1] > ema_21.iloc[-1]:
                signals.append('bullish')
            else:
                signals.append('bearish')

        # 15m trend (if provided)
        if df_15m is not None and len(df_15m) >= 20:
            ema_9 = df_15m['close'].ewm(span=9).mean()
            ema_21 = df_15m['close'].ewm(span=21).mean()
            if ema_9.iloc[-1] > ema_21.iloc[-1]:
                signals.append('bullish')
            else:
                signals.append('bearish')

        if not signals:
            return {'aligned': False, 'direction': 'unknown', 'score': 0}

        bullish_count = signals.count('bullish')
        bearish_count = signals.count('bearish')
        total = len(signals)

        if bullish_count == total:
            return {'aligned': True, 'direction': 'bullish', 'score': 100}
        elif bearish_count == total:
            return {'aligned': True, 'direction': 'bearish', 'score': 100}
        else:
            # Partial alignment
            dominant = 'bullish' if bullish_count > bearish_count else 'bearish'
            score = max(bullish_count, bearish_count) / total * 100
            return {'aligned': False, 'direction': dominant, 'score': score}

    def generate_signal(
        self,
        df: pd.DataFrame,
        df_comparison: pd.DataFrame = None,
        df_5m: pd.DataFrame = None,
        df_15m: pd.DataFrame = None,
        ml_prediction: Dict = None,
        current_price: Optional[float] = None
    ) -> Tuple[ScalpSignal, float, Dict[str, Any]]:
        """
        Generate scalping signal based on MAXIMUM CONFLUENCE.

        Aggregates all signals:
        1. ICT Confluence (40% weight)
        2. SMT Divergence (20% weight)
        3. Multi-Timeframe (15% weight)
        4. ML Prediction (15% weight)
        5. Momentum (10% weight)

        Args:
            df: Primary OHLCV DataFrame (1m timeframe)
            df_comparison: Comparison asset for SMT (ETH)
            df_5m: 5-minute timeframe data
            df_15m: 15-minute timeframe data
            ml_prediction: ML model prediction {'signal': 'BUY'/'SELL', 'confidence': 0-1}
            current_price: Current price (uses last close if not provided)

        Returns:
            Tuple of (signal, confidence, detailed breakdown)
        """
        if len(df) < 50:
            return ScalpSignal.HOLD, 0, {"reason": "Insufficient data"}

        price = current_price or df['close'].iloc[-1]

        # Pre-checks
        if not self._check_cooldown():
            return ScalpSignal.HOLD, 0, {"reason": "Cooldown active"}

        if not self._check_hourly_limit():
            return ScalpSignal.HOLD, 0, {"reason": "Hourly trade limit reached"}

        # Calculate ATR for volatility filter
        atr = self._calculate_atr(df)
        atr_pct = atr / price

        if atr_pct < self.min_atr_pct:
            return ScalpSignal.HOLD, 0, {"reason": f"Volatility too low (ATR {atr_pct*100:.3f}%)"}

        if atr_pct > self.max_atr_pct:
            return ScalpSignal.HOLD, 0, {"reason": f"Volatility too high (ATR {atr_pct*100:.3f}%)"}

        # ==========================================
        # GATHER ALL SIGNALS (respecting enabled confluences)
        # ==========================================

        signal_breakdown = {}
        bullish_score = 0
        bearish_score = 0

        # 1. ICT CONFLUENCE (40% weight) - only if enabled
        if self.is_category_enabled('ict_confluence'):
            ict_result = self._get_ict_confluence(df, price, atr)
            signal_breakdown['ict_confluence'] = ict_result
            signal_breakdown['ict_confluence']['enabled'] = True

            if ict_result['direction'] == 'long' and ict_result['is_tradeable']:
                bullish_score += self.weights['ict_confluence'] * (ict_result['score_pct'] / 100)
            elif ict_result['direction'] == 'short' and ict_result['is_tradeable']:
                bearish_score += self.weights['ict_confluence'] * (ict_result['score_pct'] / 100)
        else:
            signal_breakdown['ict_confluence'] = {'enabled': False, 'reason': 'ICT signals disabled'}

        # 2. SMT DIVERGENCE (20% weight) - only if enabled
        if self.is_category_enabled('smt_divergence'):
            if df_comparison is not None and len(df_comparison) >= 50:
                smt_result = self._get_smt_divergence(df, df_comparison)
                signal_breakdown['smt_divergence'] = smt_result
                signal_breakdown['smt_divergence']['enabled'] = True

                if smt_result['signal'] == 'bullish' and smt_result['confidence'] > 50:
                    bullish_score += self.weights['smt_divergence'] * (smt_result['confidence'] / 100)
                elif smt_result['signal'] == 'bearish' and smt_result['confidence'] > 50:
                    bearish_score += self.weights['smt_divergence'] * (smt_result['confidence'] / 100)
            else:
                signal_breakdown['smt_divergence'] = {'signal': 'none', 'reason': 'No comparison data', 'enabled': True}
        else:
            signal_breakdown['smt_divergence'] = {'enabled': False, 'reason': 'SMT signals disabled'}

        # 3. MULTI-TIMEFRAME ALIGNMENT (15% weight) - only if enabled
        if self.is_category_enabled('mtf_alignment'):
            # Only use enabled timeframes
            df_5m_filtered = df_5m if self.is_confluence_enabled('mtf_5m') else None
            df_15m_filtered = df_15m if self.is_confluence_enabled('mtf_15m') else None

            mtf_result = self._get_mtf_alignment(df, df_5m_filtered, df_15m_filtered)
            signal_breakdown['mtf_alignment'] = mtf_result
            signal_breakdown['mtf_alignment']['enabled'] = True
            signal_breakdown['mtf_alignment']['enabled_timeframes'] = [
                tf for tf in ['mtf_1m', 'mtf_5m', 'mtf_15m'] if self.is_confluence_enabled(tf)
            ]

            if mtf_result['aligned']:
                if mtf_result['direction'] == 'bullish':
                    bullish_score += self.weights['mtf_alignment']
                elif mtf_result['direction'] == 'bearish':
                    bearish_score += self.weights['mtf_alignment']
            else:
                # Partial credit for partial alignment
                if mtf_result['direction'] == 'bullish':
                    bullish_score += self.weights['mtf_alignment'] * (mtf_result['score'] / 100) * 0.5
                elif mtf_result['direction'] == 'bearish':
                    bearish_score += self.weights['mtf_alignment'] * (mtf_result['score'] / 100) * 0.5
        else:
            signal_breakdown['mtf_alignment'] = {'enabled': False, 'reason': 'MTF signals disabled'}

        # 4. ML PREDICTION (15% weight) - only if enabled
        if self.is_category_enabled('ml_prediction'):
            if ml_prediction:
                signal_breakdown['ml_prediction'] = ml_prediction
                signal_breakdown['ml_prediction']['enabled'] = True
                ml_signal = ml_prediction.get('signal', 'HOLD')
                ml_conf = ml_prediction.get('confidence', 0)

                if ml_signal == 'BUY' and ml_conf > 0.5:
                    bullish_score += self.weights['ml_prediction'] * ml_conf
                elif ml_signal == 'SELL' and ml_conf > 0.5:
                    bearish_score += self.weights['ml_prediction'] * (1 - ml_conf)
            else:
                signal_breakdown['ml_prediction'] = {'signal': 'HOLD', 'reason': 'No ML prediction', 'enabled': True}
        else:
            signal_breakdown['ml_prediction'] = {'enabled': False, 'reason': 'ML signals disabled'}

        # 5. MOMENTUM (10% weight) - only if enabled
        if self.is_category_enabled('momentum'):
            momentum_score, momentum_reason = self._get_momentum_score_filtered(df)
            signal_breakdown['momentum'] = {
                'score': momentum_score,
                'reason': momentum_reason,
                'enabled': True,
                'enabled_indicators': list(self.enabled_momentum_signals)
            }

            if momentum_score > 0:
                bullish_score += self.weights['momentum'] * (momentum_score / 100)
            elif momentum_score < 0:
                bearish_score += self.weights['momentum'] * (abs(momentum_score) / 100)
        else:
            signal_breakdown['momentum'] = {'enabled': False, 'reason': 'Momentum signals disabled'}

        # ==========================================
        # MAKE FINAL DECISION
        # ==========================================

        total_weight = sum(self.weights.values())
        bullish_pct = (bullish_score / total_weight) * 100
        bearish_pct = (bearish_score / total_weight) * 100

        # Calculate net score and confidence
        net_score = bullish_score - bearish_score
        max_possible = total_weight

        # Confidence based on score dominance
        if bullish_score > bearish_score:
            confidence = (bullish_score / max_possible) * 100
            primary_direction = 'long'
        elif bearish_score > bullish_score:
            confidence = (bearish_score / max_possible) * 100
            primary_direction = 'short'
        else:
            confidence = 0
            primary_direction = 'neutral'

        # Count aligned signals (only count enabled categories)
        aligned_signals = 0
        total_signals = len(self.enabled_categories)

        if self.is_category_enabled('ict_confluence'):
            ict_result = signal_breakdown.get('ict_confluence', {})
            if ict_result.get('is_tradeable') and ict_result.get('direction') == primary_direction:
                aligned_signals += 1

        if self.is_category_enabled('smt_divergence'):
            expected_smt = 'bullish' if primary_direction == 'long' else 'bearish'
            if signal_breakdown.get('smt_divergence', {}).get('signal') == expected_smt:
                aligned_signals += 1

        if self.is_category_enabled('mtf_alignment'):
            expected_mtf = 'bullish' if primary_direction == 'long' else 'bearish'
            if signal_breakdown.get('mtf_alignment', {}).get('direction') == expected_mtf:
                aligned_signals += 1

        if self.is_category_enabled('ml_prediction'):
            expected_ml = 'BUY' if primary_direction == 'long' else 'SELL'
            if ml_prediction and ml_prediction.get('signal') == expected_ml:
                aligned_signals += 1

        if self.is_category_enabled('momentum'):
            mom_score = signal_breakdown.get('momentum', {}).get('score', 0)
            if (mom_score > 0 and primary_direction == 'long') or (mom_score < 0 and primary_direction == 'short'):
                aligned_signals += 1

        # Determine final signal based on mode settings
        signal = ScalpSignal.HOLD

        if primary_direction == 'long' and confidence >= self.min_confidence:
            if confidence >= self.strong_confidence and aligned_signals >= self.strong_aligned_signals:
                signal = ScalpSignal.STRONG_BUY
            elif confidence >= self.min_confidence and aligned_signals >= self.min_aligned_signals:
                signal = ScalpSignal.BUY
        elif primary_direction == 'short' and confidence >= self.min_confidence:
            if confidence >= self.strong_confidence and aligned_signals >= self.strong_aligned_signals:
                signal = ScalpSignal.STRONG_SELL
            elif confidence >= self.min_confidence and aligned_signals >= self.min_aligned_signals:
                signal = ScalpSignal.SELL

        # Calculate entry targets
        # Get ICT result from breakdown if available
        ict_for_targets = signal_breakdown.get('ict_confluence', {})

        if signal in [ScalpSignal.BUY, ScalpSignal.STRONG_BUY]:
            stop_loss = price * (1 - self.stop_loss_pct)
            take_profit = price * (1 + self.take_profit_pct)
            # Use ICT levels if available and enabled
            if ict_for_targets.get('enabled') and ict_for_targets.get('stop_loss') and ict_for_targets.get('take_profit_1'):
                stop_loss = ict_for_targets['stop_loss']
                take_profit = ict_for_targets['take_profit_1']
        elif signal in [ScalpSignal.SELL, ScalpSignal.STRONG_SELL]:
            stop_loss = price * (1 + self.stop_loss_pct)
            take_profit = price * (1 - self.take_profit_pct)
            if ict_for_targets.get('enabled') and ict_for_targets.get('stop_loss') and ict_for_targets.get('take_profit_1'):
                stop_loss = ict_for_targets['stop_loss']
                take_profit = ict_for_targets['take_profit_1']
        else:
            stop_loss = 0
            take_profit = 0

        # Get ICT result for details (might be disabled)
        ict_result_for_details = signal_breakdown.get('ict_confluence', {})

        # Build detailed response
        details = {
            "signal": signal.value,
            "confidence": round(confidence, 1),
            "direction": primary_direction,
            "entry_price": price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_reward": self.take_profit_pct / self.stop_loss_pct if self.stop_loss_pct > 0 else 0,

            # Score breakdown
            "bullish_score": round(bullish_pct, 1),
            "bearish_score": round(bearish_pct, 1),
            "net_score": round(net_score, 2),
            "aligned_signals": aligned_signals,
            "total_signals": total_signals,

            # Individual signal details
            "signal_breakdown": signal_breakdown,

            # ICT specific
            "ict_confluence_score": ict_result_for_details.get('score', 0),
            "ict_strength": ict_result_for_details.get('strength', 'none'),

            # Enabled confluence info
            "enabled_confluences": self.enabled_confluences,
            "enabled_categories": list(self.enabled_categories),
            "weights": self.weights,

            # Summary reason
            "reason": self._build_reason_summary(signal_breakdown, aligned_signals, primary_direction),

            "atr_pct": atr_pct * 100,
            "timestamp": datetime.utcnow().isoformat()
        }

        return signal, confidence, details

    def _build_reason_summary(self, breakdown: Dict, aligned: int, direction: str) -> str:
        """Build human-readable reason summary."""
        parts = []
        total_enabled = len(self.enabled_categories)

        # ICT
        ict = breakdown.get('ict_confluence', {})
        if ict.get('enabled', True):  # Default to True for backward compatibility
            if ict.get('is_tradeable'):
                parts.append(f"ICT: {ict.get('strength', 'N/A')} {ict.get('direction', 'N/A')} ({ict.get('score', 0)}/30)")
            else:
                parts.append(f"ICT: No trade ({ict.get('score', 0)}/30)")
        else:
            parts.append("ICT: Disabled")

        # SMT
        smt = breakdown.get('smt_divergence', {})
        if smt.get('enabled', True):
            if smt.get('signal') and smt.get('signal') != 'none':
                parts.append(f"SMT: {smt.get('signal', 'N/A')} ({smt.get('confidence', 0):.0f}%)")
            else:
                parts.append("SMT: No divergence")
        else:
            parts.append("SMT: Disabled")

        # MTF
        mtf = breakdown.get('mtf_alignment', {})
        if mtf.get('enabled', True):
            if mtf.get('aligned'):
                parts.append(f"MTF: Aligned {mtf.get('direction', 'N/A')}")
            else:
                parts.append(f"MTF: Mixed ({mtf.get('direction', 'N/A')} {mtf.get('score', 0):.0f}%)")
        else:
            parts.append("MTF: Disabled")

        # Momentum
        mom = breakdown.get('momentum', {})
        if mom.get('enabled', True):
            parts.append(f"Momentum: {mom.get('reason', 'N/A')}")
        else:
            parts.append("Momentum: Disabled")

        return f"{aligned}/{total_enabled} signals aligned for {direction}. " + " | ".join(parts)

    def record_trade(self):
        """Record a trade for rate limiting."""
        self.last_trade_time = datetime.utcnow()
        self.hourly_trades.append(self.last_trade_time)

    def get_position_size(
        self,
        capital: float,
        risk_per_trade: float = 0.01,
        entry_price: float = 0,
        stop_loss: float = 0,
        confidence: float = 50
    ) -> float:
        """
        Calculate position size based on risk and confidence.

        Higher confidence = larger position (up to max)
        """
        if entry_price <= 0 or stop_loss <= 0:
            return 0

        # Base risk amount
        risk_amount = capital * risk_per_trade

        # Adjust by confidence (50% confidence = base, 100% = 1.5x base)
        confidence_multiplier = 0.5 + (confidence / 100) * 0.5
        adjusted_risk = risk_amount * confidence_multiplier

        # Calculate position size
        stop_distance = abs(entry_price - stop_loss)
        if stop_distance <= 0:
            return 0

        size = adjusted_risk / stop_distance

        # Cap at 10% of capital
        max_size = (capital * 0.1) / entry_price

        return min(size, max_size)


# Quick test
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '/Users/utpalraina/robo-trader')

    from data.fetcher import DataFetcher
    from utils.helpers import load_config, get_exchange

    config = load_config('config/config.yaml')
    exchange = get_exchange(config, paper_mode=False)
    fetcher = DataFetcher(exchange)

    # Fetch data
    df_btc = fetcher.fetch_ohlcv('BTC/USD', '5m', limit=200)
    df_eth = fetcher.fetch_ohlcv('ETH/USD', '5m', limit=200)

    # Test strategy
    strategy = ScalpingStrategy()
    signal, confidence, details = strategy.generate_signal(
        df=df_btc,
        df_comparison=df_eth
    )

    print(f"\n{'='*60}")
    print(f"CONFLUENCE-BASED SCALPING SIGNAL")
    print(f"{'='*60}")
    print(f"Signal: {signal.value}")
    print(f"Confidence: {confidence:.1f}%")
    print(f"Direction: {details['direction']}")
    print(f"Aligned Signals: {details['aligned_signals']}/{details['total_signals']}")
    print(f"\nBullish Score: {details['bullish_score']:.1f}%")
    print(f"Bearish Score: {details['bearish_score']:.1f}%")
    print(f"\nEntry: ${details['entry_price']:,.2f}")
    print(f"Stop Loss: ${details['stop_loss']:,.2f}")
    print(f"Take Profit: ${details['take_profit']:,.2f}")
    print(f"\n{details['reason']}")
