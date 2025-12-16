"""ML-based trading strategy."""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Tuple
from enum import Enum
from loguru import logger

from models.base import BaseModel
from features.indicators import FeatureEngineer


class Signal(Enum):
    """Trading signal types."""
    BUY = 1
    SELL = -1
    HOLD = 0


class MLStrategy:
    """ML-based trading strategy with risk management."""

    def __init__(
        self,
        model: BaseModel,
        feature_engineer: FeatureEngineer,
        config: dict
    ):
        """
        Initialize ML Strategy.

        Args:
            model: Trained ML model
            feature_engineer: Feature engineering instance
            config: Strategy configuration
        """
        self.model = model
        self.feature_engineer = feature_engineer
        self.config = config
        self.risk_config = config.get("risk", {})

        # Signal thresholds
        self.buy_threshold = 0.6   # Probability threshold for buy
        self.sell_threshold = 0.4  # Probability threshold for sell

        # Position tracking
        self.current_position = 0  # 1 = long, -1 = short, 0 = flat
        self.entry_price = None

    def generate_signal(self, df: pd.DataFrame) -> Tuple[Signal, float]:
        """
        Generate trading signal from current market data.

        Args:
            df: DataFrame with OHLCV data (latest candle should be most recent)

        Returns:
            Tuple of (Signal, confidence score)
        """
        # Generate features for the latest data
        df_features = self.feature_engineer.generate_features(df)

        if df_features.empty:
            return Signal.HOLD, 0.0

        # Get the latest row for prediction
        latest = df_features.iloc[[-1]]
        feature_cols = self.feature_engineer.get_feature_names(df_features)
        X = latest[feature_cols]

        # Get model prediction and probability
        try:
            proba = self.model.predict_proba(X)[0]
            # Probability of price going up
            up_prob = proba[1] if len(proba) > 1 else proba[0]

            if up_prob >= self.buy_threshold:
                return Signal.BUY, up_prob
            elif up_prob <= self.sell_threshold:
                return Signal.SELL, 1 - up_prob
            else:
                return Signal.HOLD, 0.5

        except Exception as e:
            logger.error(f"Error generating signal: {e}")
            return Signal.HOLD, 0.0

    def calculate_position_size(
        self,
        capital: float,
        current_price: float
    ) -> float:
        """
        Calculate position size based on risk management rules.

        Args:
            capital: Available capital
            current_price: Current asset price

        Returns:
            Position size in base currency
        """
        max_position_pct = self.risk_config.get("max_position_size", 0.1)
        stop_loss_pct = self.risk_config.get("stop_loss_pct", 0.02)

        # Calculate position value
        max_position_value = capital * max_position_pct

        # Adjust for stop loss (risk-based sizing)
        risk_adjusted_value = (capital * 0.01) / stop_loss_pct  # Risk 1% per trade

        position_value = min(max_position_value, risk_adjusted_value)
        position_size = position_value / current_price

        return position_size

    def check_stop_loss(self, current_price: float) -> bool:
        """Check if stop loss should be triggered."""
        if self.entry_price is None or self.current_position == 0:
            return False

        stop_loss_pct = self.risk_config.get("stop_loss_pct", 0.02)

        if self.current_position > 0:  # Long position
            loss_pct = (self.entry_price - current_price) / self.entry_price
            return loss_pct >= stop_loss_pct

        return False

    def check_take_profit(self, current_price: float) -> bool:
        """Check if take profit should be triggered."""
        if self.entry_price is None or self.current_position == 0:
            return False

        take_profit_pct = self.risk_config.get("take_profit_pct", 0.04)

        if self.current_position > 0:  # Long position
            profit_pct = (current_price - self.entry_price) / self.entry_price
            return profit_pct >= take_profit_pct

        return False

    def should_close_position(
        self,
        current_price: float,
        signal: Signal
    ) -> Tuple[bool, str]:
        """
        Determine if current position should be closed.

        Args:
            current_price: Current market price
            signal: Latest trading signal

        Returns:
            Tuple of (should_close, reason)
        """
        if self.current_position == 0:
            return False, ""

        # Check stop loss
        if self.check_stop_loss(current_price):
            return True, "stop_loss"

        # Check take profit
        if self.check_take_profit(current_price):
            return True, "take_profit"

        # Check signal reversal
        if self.current_position > 0 and signal == Signal.SELL:
            return True, "signal_reversal"

        return False, ""

    def update_position(self, position: int, entry_price: Optional[float] = None):
        """
        Update current position state.

        Args:
            position: New position (1 = long, 0 = flat, -1 = short)
            entry_price: Entry price for new position
        """
        self.current_position = position
        self.entry_price = entry_price if position != 0 else None

    def get_signal_with_risk_check(
        self,
        df: pd.DataFrame,
        current_price: float,
        open_positions: int,
        daily_pnl: float,
        capital: float
    ) -> Dict:
        """
        Generate signal with full risk management checks.

        Args:
            df: OHLCV DataFrame
            current_price: Current price
            open_positions: Number of open positions
            daily_pnl: Current day's PnL
            capital: Available capital

        Returns:
            Dictionary with signal and action details
        """
        # Check daily loss limit
        daily_loss_limit = self.risk_config.get("daily_loss_limit", 0.05)
        if daily_pnl / capital <= -daily_loss_limit:
            logger.warning("Daily loss limit reached - no new trades")
            return {"action": "hold", "reason": "daily_loss_limit"}

        # Check max positions
        max_positions = self.risk_config.get("max_open_positions", 3)
        if open_positions >= max_positions and self.current_position == 0:
            return {"action": "hold", "reason": "max_positions_reached"}

        # Generate signal
        signal, confidence = self.generate_signal(df)

        # Check if should close current position
        should_close, close_reason = self.should_close_position(current_price, signal)

        if should_close:
            return {
                "action": "close",
                "reason": close_reason,
                "confidence": confidence
            }

        # Check for new position entry
        if self.current_position == 0 and signal in [Signal.BUY, Signal.SELL]:
            position_size = self.calculate_position_size(capital, current_price)
            return {
                "action": "buy" if signal == Signal.BUY else "sell",
                "size": position_size,
                "confidence": confidence,
                "stop_loss": current_price * (1 - self.risk_config.get("stop_loss_pct", 0.02)),
                "take_profit": current_price * (1 + self.risk_config.get("take_profit_pct", 0.04))
            }

        return {"action": "hold", "confidence": confidence}
