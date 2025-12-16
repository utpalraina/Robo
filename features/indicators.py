"""Feature engineering module for ML-based trading."""

import pandas as pd
import numpy as np
from ta import momentum, trend, volatility, volume
from typing import List, Optional
from loguru import logger


class FeatureEngineer:
    """Generate features for ML models from OHLCV data."""

    def __init__(self, config: dict):
        """
        Initialize FeatureEngineer.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.feature_config = config.get("features", {})
        self.lookback = config.get("model", {}).get("lookback_periods", 100)

    def generate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate all features from OHLCV data.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with all features added
        """
        df = df.copy()

        # Add technical indicators
        df = self._add_technical_indicators(df)

        # Add price-based features
        df = self._add_price_features(df)

        # Add time-based features
        df = self._add_time_features(df)

        # Add lagged features
        df = self._add_lagged_features(df)

        # Generate target variable
        df = self._generate_target(df)

        # Drop NaN values
        df = df.dropna()

        logger.debug(f"Generated {len(df.columns)} features")
        return df

    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical analysis indicators using ta library."""

        # RSI - Relative Strength Index
        df["rsi_14"] = momentum.RSIIndicator(df["close"], window=14).rsi()
        df["rsi_7"] = momentum.RSIIndicator(df["close"], window=7).rsi()

        # MACD
        macd_indicator = trend.MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
        df["macd"] = macd_indicator.macd()
        df["macd_signal"] = macd_indicator.macd_signal()
        df["macd_hist"] = macd_indicator.macd_diff()

        # Bollinger Bands
        bb_indicator = volatility.BollingerBands(df["close"], window=20, window_dev=2)
        df["bb_upper"] = bb_indicator.bollinger_hband()
        df["bb_middle"] = bb_indicator.bollinger_mavg()
        df["bb_lower"] = bb_indicator.bollinger_lband()
        df["bb_width"] = bb_indicator.bollinger_wband()
        df["bb_pct"] = bb_indicator.bollinger_pband()

        # Moving Averages
        df["ema_9"] = trend.EMAIndicator(df["close"], window=9).ema_indicator()
        df["ema_21"] = trend.EMAIndicator(df["close"], window=21).ema_indicator()
        df["ema_50"] = trend.EMAIndicator(df["close"], window=50).ema_indicator()
        df["sma_20"] = trend.SMAIndicator(df["close"], window=20).sma_indicator()
        df["sma_50"] = trend.SMAIndicator(df["close"], window=50).sma_indicator()

        # EMA crossovers
        df["ema_cross_9_21"] = (df["ema_9"] > df["ema_21"]).astype(int)
        df["ema_cross_21_50"] = (df["ema_21"] > df["ema_50"]).astype(int)

        # ATR - Average True Range (Volatility)
        atr_indicator = volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=14)
        df["atr_14"] = atr_indicator.average_true_range()
        df["atr_pct"] = df["atr_14"] / df["close"]

        # ADX - Average Directional Index (Trend Strength)
        adx_indicator = trend.ADXIndicator(df["high"], df["low"], df["close"], window=14)
        df["adx"] = adx_indicator.adx()
        df["di_plus"] = adx_indicator.adx_pos()
        df["di_minus"] = adx_indicator.adx_neg()

        # Stochastic Oscillator
        stoch_indicator = momentum.StochasticOscillator(df["high"], df["low"], df["close"], window=14, smooth_window=3)
        df["stoch_k"] = stoch_indicator.stoch()
        df["stoch_d"] = stoch_indicator.stoch_signal()

        # CCI - Commodity Channel Index
        df["cci"] = trend.CCIIndicator(df["high"], df["low"], df["close"], window=20).cci()

        # OBV - On Balance Volume
        df["obv"] = volume.OnBalanceVolumeIndicator(df["close"], df["volume"]).on_balance_volume()
        df["obv_sma"] = df["obv"].rolling(window=20).mean()

        # Volume indicators
        df["volume_sma_20"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma_20"]

        # VWAP (approximation)
        df["vwap"] = (df["volume"] * (df["high"] + df["low"] + df["close"]) / 3).cumsum() / df["volume"].cumsum()

        return df

    def _add_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add price-based features."""

        # Returns
        df["returns_1"] = df["close"].pct_change(1)
        df["returns_5"] = df["close"].pct_change(5)
        df["returns_10"] = df["close"].pct_change(10)
        df["returns_20"] = df["close"].pct_change(20)

        # Log returns
        df["log_returns"] = np.log(df["close"] / df["close"].shift(1))

        # Volatility (rolling std of returns)
        df["volatility_10"] = df["returns_1"].rolling(window=10).std()
        df["volatility_20"] = df["returns_1"].rolling(window=20).std()

        # Price momentum
        df["momentum_10"] = df["close"] - df["close"].shift(10)
        df["momentum_20"] = df["close"] - df["close"].shift(20)

        # Rate of change
        df["roc_10"] = momentum.ROCIndicator(df["close"], window=10).roc()
        df["roc_20"] = momentum.ROCIndicator(df["close"], window=20).roc()

        # Price relative to moving averages
        df["price_sma20_ratio"] = df["close"] / df["sma_20"]
        df["price_sma50_ratio"] = df["close"] / df["sma_50"]

        # High-Low range
        df["hl_range"] = (df["high"] - df["low"]) / df["close"]

        # Close position within candle
        df["close_position"] = (df["close"] - df["low"]) / (df["high"] - df["low"])

        # Gap (open vs previous close)
        df["gap"] = (df["open"] - df["close"].shift(1)) / df["close"].shift(1)

        return df

    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add time-based features."""

        if isinstance(df.index, pd.DatetimeIndex):
            df["hour"] = df.index.hour
            df["day_of_week"] = df.index.dayofweek
            df["day_of_month"] = df.index.day
            df["month"] = df.index.month

            # Cyclical encoding for hour
            df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
            df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

            # Cyclical encoding for day of week
            df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
            df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)

        return df

    def _add_lagged_features(self, df: pd.DataFrame, lags: List[int] = [1, 2, 3, 5]) -> pd.DataFrame:
        """Add lagged versions of key features."""

        lag_features = ["returns_1", "rsi_14", "macd_hist", "volume_ratio"]

        for feature in lag_features:
            if feature in df.columns:
                for lag in lags:
                    df[f"{feature}_lag_{lag}"] = df[feature].shift(lag)

        return df

    def _generate_target(self, df: pd.DataFrame, horizon: int = 1, threshold: float = 0.0) -> pd.DataFrame:
        """
        Generate target variable for ML model.

        Args:
            df: DataFrame with features
            horizon: Prediction horizon (number of periods ahead)
            threshold: Minimum return for positive class

        Returns:
            DataFrame with target column added
        """
        # Future returns
        df["future_return"] = df["close"].shift(-horizon) / df["close"] - 1

        # Binary classification target (1 = price goes up, 0 = price goes down)
        df["target"] = (df["future_return"] > threshold).astype(int)

        # Multi-class target (0 = down, 1 = neutral, 2 = up)
        # Use small epsilon if threshold is 0 to avoid duplicate bin edges
        thresh = threshold if threshold > 0 else 0.001
        target_3class = pd.cut(
            df["future_return"],
            bins=[-np.inf, -thresh, thresh, np.inf],
            labels=[0, 1, 2]
        )
        # Convert to numeric, NaN values will remain as NaN
        df["target_3class"] = pd.to_numeric(target_3class, errors='coerce')

        return df

    def get_feature_names(self, df: pd.DataFrame) -> List[str]:
        """Get list of feature column names (excluding target and OHLCV)."""
        exclude_cols = ["open", "high", "low", "close", "volume", "symbol",
                       "target", "target_3class", "future_return"]
        return [col for col in df.columns if col not in exclude_cols]

    def prepare_ml_data(
        self,
        df: pd.DataFrame,
        target_col: str = "target"
    ) -> tuple:
        """
        Prepare data for ML training.

        Args:
            df: DataFrame with features
            target_col: Name of target column

        Returns:
            Tuple of (X features DataFrame, y target Series)
        """
        feature_cols = self.get_feature_names(df)
        X = df[feature_cols].copy()
        y = df[target_col].copy()

        # Remove any remaining NaN
        mask = ~(X.isna().any(axis=1) | y.isna())
        X = X[mask]
        y = y[mask]

        return X, y
