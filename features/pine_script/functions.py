"""Built-in functions for Pine Script interpreter."""

import numpy as np
import pandas as pd
from typing import Union, Optional, List, Tuple
from loguru import logger


class BuiltinFunctions:
    """Implementation of Pine Script built-in functions using NumPy/Pandas."""

    @staticmethod
    def sma(source: np.ndarray, length: int) -> np.ndarray:
        """Simple Moving Average."""
        if length <= 0:
            return np.full_like(source, np.nan)
        return pd.Series(source).rolling(window=length, min_periods=length).mean().values

    @staticmethod
    def ema(source: np.ndarray, length: int) -> np.ndarray:
        """Exponential Moving Average."""
        if length <= 0:
            return np.full_like(source, np.nan)
        return pd.Series(source).ewm(span=length, adjust=False).mean().values

    @staticmethod
    def wma(source: np.ndarray, length: int) -> np.ndarray:
        """Weighted Moving Average."""
        if length <= 0:
            return np.full_like(source, np.nan)

        weights = np.arange(1, length + 1)
        result = np.full_like(source, np.nan, dtype=float)

        for i in range(length - 1, len(source)):
            window = source[i - length + 1:i + 1]
            result[i] = np.sum(window * weights) / np.sum(weights)

        return result

    @staticmethod
    def vwma(source: np.ndarray, volume: np.ndarray, length: int) -> np.ndarray:
        """Volume Weighted Moving Average."""
        if length <= 0:
            return np.full_like(source, np.nan)

        price_volume = source * volume
        sum_pv = pd.Series(price_volume).rolling(window=length, min_periods=length).sum().values
        sum_vol = pd.Series(volume).rolling(window=length, min_periods=length).sum().values

        return np.where(sum_vol != 0, sum_pv / sum_vol, np.nan)

    @staticmethod
    def rsi(source: np.ndarray, length: int) -> np.ndarray:
        """Relative Strength Index."""
        if length <= 0:
            return np.full_like(source, np.nan)

        delta = np.diff(source, prepend=source[0])
        gains = np.where(delta > 0, delta, 0)
        losses = np.where(delta < 0, -delta, 0)

        avg_gain = pd.Series(gains).ewm(alpha=1/length, adjust=False).mean().values
        avg_loss = pd.Series(losses).ewm(alpha=1/length, adjust=False).mean().values

        rs = np.where(avg_loss != 0, avg_gain / avg_loss, 100)
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def macd(source: np.ndarray, fast_length: int = 12, slow_length: int = 26,
             signal_length: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        MACD (Moving Average Convergence Divergence).

        Returns:
            Tuple of (macd_line, signal_line, histogram)
        """
        fast_ema = BuiltinFunctions.ema(source, fast_length)
        slow_ema = BuiltinFunctions.ema(source, slow_length)

        macd_line = fast_ema - slow_ema
        signal_line = BuiltinFunctions.ema(macd_line, signal_length)
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    @staticmethod
    def stoch(high: np.ndarray, low: np.ndarray, close: np.ndarray,
              length: int) -> np.ndarray:
        """Stochastic oscillator %K."""
        if length <= 0:
            return np.full_like(close, np.nan)

        lowest_low = pd.Series(low).rolling(window=length, min_periods=length).min().values
        highest_high = pd.Series(high).rolling(window=length, min_periods=length).max().values

        range_val = highest_high - lowest_low
        return np.where(range_val != 0, 100 * (close - lowest_low) / range_val, 50)

    @staticmethod
    def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray,
            length: int) -> np.ndarray:
        """Average True Range."""
        if length <= 0:
            return np.full_like(close, np.nan)

        tr = BuiltinFunctions.tr(high, low, close)
        return pd.Series(tr).ewm(span=length, adjust=False).mean().values

    @staticmethod
    def tr(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
        """True Range."""
        prev_close = np.roll(close, 1)
        prev_close[0] = close[0]

        tr1 = high - low
        tr2 = np.abs(high - prev_close)
        tr3 = np.abs(low - prev_close)

        return np.maximum(np.maximum(tr1, tr2), tr3)

    @staticmethod
    def bb(source: np.ndarray, length: int,
           mult: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Bollinger Bands.

        Returns:
            Tuple of (middle, upper, lower)
        """
        middle = BuiltinFunctions.sma(source, length)
        std = pd.Series(source).rolling(window=length, min_periods=length).std().values
        upper = middle + mult * std
        lower = middle - mult * std

        return middle, upper, lower

    @staticmethod
    def highest(source: np.ndarray, length: int) -> np.ndarray:
        """Highest value over a period."""
        if length <= 0:
            return np.full_like(source, np.nan)
        return pd.Series(source).rolling(window=length, min_periods=1).max().values

    @staticmethod
    def lowest(source: np.ndarray, length: int) -> np.ndarray:
        """Lowest value over a period."""
        if length <= 0:
            return np.full_like(source, np.nan)
        return pd.Series(source).rolling(window=length, min_periods=1).min().values

    @staticmethod
    def crossover(series1: np.ndarray, series2: np.ndarray) -> np.ndarray:
        """
        Detect crossover: series1 crosses above series2.

        Returns:
            Boolean array where True indicates crossover.
        """
        if isinstance(series2, (int, float)):
            series2 = np.full_like(series1, series2)

        prev1 = np.roll(series1, 1)
        prev2 = np.roll(series2, 1)

        # First element can't have a crossover
        result = (prev1 <= prev2) & (series1 > series2)
        result[0] = False
        return result

    @staticmethod
    def crossunder(series1: np.ndarray, series2: np.ndarray) -> np.ndarray:
        """
        Detect crossunder: series1 crosses below series2.

        Returns:
            Boolean array where True indicates crossunder.
        """
        if isinstance(series2, (int, float)):
            series2 = np.full_like(series1, series2)

        prev1 = np.roll(series1, 1)
        prev2 = np.roll(series2, 1)

        result = (prev1 >= prev2) & (series1 < series2)
        result[0] = False
        return result

    @staticmethod
    def cross(series1: np.ndarray, series2: np.ndarray) -> np.ndarray:
        """Detect any cross (either direction)."""
        return BuiltinFunctions.crossover(series1, series2) | BuiltinFunctions.crossunder(series1, series2)

    @staticmethod
    def change(source: np.ndarray, length: int = 1) -> np.ndarray:
        """Change from previous value."""
        result = np.zeros_like(source)
        result[length:] = source[length:] - source[:-length]
        result[:length] = np.nan
        return result

    @staticmethod
    def roc(source: np.ndarray, length: int) -> np.ndarray:
        """Rate of Change (percentage)."""
        prev = np.roll(source, length)
        prev[:length] = np.nan
        return np.where(prev != 0, 100 * (source - prev) / prev, 0)

    @staticmethod
    def sum_fn(source: np.ndarray, length: int) -> np.ndarray:
        """Sum over a period."""
        if length <= 0:
            return np.full_like(source, np.nan)
        return pd.Series(source).rolling(window=length, min_periods=length).sum().values

    @staticmethod
    def stdev(source: np.ndarray, length: int) -> np.ndarray:
        """Standard deviation."""
        if length <= 0:
            return np.full_like(source, np.nan)
        return pd.Series(source).rolling(window=length, min_periods=length).std().values

    @staticmethod
    def variance(source: np.ndarray, length: int) -> np.ndarray:
        """Variance."""
        if length <= 0:
            return np.full_like(source, np.nan)
        return pd.Series(source).rolling(window=length, min_periods=length).var().values

    # Math functions
    @staticmethod
    def abs_fn(x: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
        """Absolute value."""
        return np.abs(x)

    @staticmethod
    def max_fn(x: Union[np.ndarray, float], y: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
        """Maximum of two values."""
        return np.maximum(x, y)

    @staticmethod
    def min_fn(x: Union[np.ndarray, float], y: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
        """Minimum of two values."""
        return np.minimum(x, y)

    @staticmethod
    def pow_fn(base: Union[np.ndarray, float], exp: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
        """Power function."""
        return np.power(base, exp)

    @staticmethod
    def sqrt_fn(x: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
        """Square root."""
        return np.sqrt(x)

    @staticmethod
    def log_fn(x: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
        """Natural logarithm."""
        return np.log(x)

    @staticmethod
    def exp_fn(x: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
        """Exponential function."""
        return np.exp(x)

    @staticmethod
    def round_fn(x: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
        """Round to nearest integer."""
        return np.round(x)

    @staticmethod
    def floor_fn(x: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
        """Floor function."""
        return np.floor(x)

    @staticmethod
    def ceil_fn(x: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
        """Ceiling function."""
        return np.ceil(x)

    @staticmethod
    def sign_fn(x: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
        """Sign function."""
        return np.sign(x)


# Mapping of Pine Script function names to implementations
FUNCTION_MAP = {
    # Technical Analysis (ta.*)
    'ta.sma': BuiltinFunctions.sma,
    'ta.ema': BuiltinFunctions.ema,
    'ta.wma': BuiltinFunctions.wma,
    'ta.vwma': BuiltinFunctions.vwma,
    'ta.rsi': BuiltinFunctions.rsi,
    'ta.macd': BuiltinFunctions.macd,
    'ta.stoch': BuiltinFunctions.stoch,
    'ta.atr': BuiltinFunctions.atr,
    'ta.tr': BuiltinFunctions.tr,
    'ta.bb': BuiltinFunctions.bb,
    'ta.highest': BuiltinFunctions.highest,
    'ta.lowest': BuiltinFunctions.lowest,
    'ta.crossover': BuiltinFunctions.crossover,
    'ta.crossunder': BuiltinFunctions.crossunder,
    'ta.cross': BuiltinFunctions.cross,
    'ta.change': BuiltinFunctions.change,
    'ta.roc': BuiltinFunctions.roc,
    'ta.sum': BuiltinFunctions.sum_fn,
    'ta.stdev': BuiltinFunctions.stdev,
    'ta.variance': BuiltinFunctions.variance,

    # Math functions (math.*)
    'math.abs': BuiltinFunctions.abs_fn,
    'math.max': BuiltinFunctions.max_fn,
    'math.min': BuiltinFunctions.min_fn,
    'math.pow': BuiltinFunctions.pow_fn,
    'math.sqrt': BuiltinFunctions.sqrt_fn,
    'math.log': BuiltinFunctions.log_fn,
    'math.exp': BuiltinFunctions.exp_fn,
    'math.round': BuiltinFunctions.round_fn,
    'math.floor': BuiltinFunctions.floor_fn,
    'math.ceil': BuiltinFunctions.ceil_fn,
    'math.sign': BuiltinFunctions.sign_fn,
}


# Color mapping
COLOR_MAP = {
    'color.aqua': '#00FFFF',
    'color.black': '#000000',
    'color.blue': '#2962FF',
    'color.fuchsia': '#FF00FF',
    'color.gray': '#787B86',
    'color.green': '#089981',
    'color.lime': '#00FF00',
    'color.maroon': '#800000',
    'color.navy': '#000080',
    'color.olive': '#808000',
    'color.orange': '#FF9800',
    'color.purple': '#9C27B0',
    'color.red': '#F23645',
    'color.silver': '#C0C0C0',
    'color.teal': '#008080',
    'color.white': '#FFFFFF',
    'color.yellow': '#FFEB3B',
}
