"""ML model implementations for trading."""

import pandas as pd
import numpy as np
from typing import Optional, List
from sklearn.model_selection import train_test_split, cross_val_score, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from loguru import logger

from .base import BaseModel


class XGBoostModel(BaseModel):
    """XGBoost-based trading model."""

    def __init__(self, config: dict):
        super().__init__("xgboost", config)
        self.scaler = StandardScaler()

        model_config = config.get("model", {})
        # Note: early_stopping_rounds is set during fit() when eval_set is provided
        self.model = XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric="logloss"
        )

    def train(self, X: pd.DataFrame, y: pd.Series, eval_set: bool = True) -> None:
        """Train the XGBoost model."""
        self.feature_names = list(X.columns)

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Split for early stopping
        if eval_set:
            X_train, X_val, y_train, y_val = train_test_split(
                X_scaled, y, test_size=0.2, shuffle=False
            )
            # Set early stopping only when we have a validation set
            self.model.set_params(early_stopping_rounds=20)
            self.model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False
            )
        else:
            # No early stopping without validation set
            self.model.set_params(early_stopping_rounds=None)
            self.model.fit(X_scaled, y)

        self.is_trained = True
        logger.info(f"XGBoost model trained on {len(X)} samples")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions."""
        X_scaled = self.scaler.transform(X[self.feature_names])
        return self.model.predict(X_scaled)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Get prediction probabilities."""
        X_scaled = self.scaler.transform(X[self.feature_names])
        return self.model.predict_proba(X_scaled)


class LightGBMModel(BaseModel):
    """LightGBM-based trading model."""

    def __init__(self, config: dict):
        super().__init__("lightgbm", config)
        self.scaler = StandardScaler()

        self.model = LGBMClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbose=-1
        )

    def train(self, X: pd.DataFrame, y: pd.Series, eval_set: bool = True) -> None:
        """Train the LightGBM model."""
        self.feature_names = list(X.columns)
        X_scaled = self.scaler.fit_transform(X)

        if eval_set:
            X_train, X_val, y_train, y_val = train_test_split(
                X_scaled, y, test_size=0.2, shuffle=False
            )
            self.model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
            )
        else:
            self.model.fit(X_scaled, y)

        self.is_trained = True
        logger.info(f"LightGBM model trained on {len(X)} samples")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        X_scaled = self.scaler.transform(X[self.feature_names])
        return self.model.predict(X_scaled)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        X_scaled = self.scaler.transform(X[self.feature_names])
        return self.model.predict_proba(X_scaled)


class RandomForestModel(BaseModel):
    """Random Forest-based trading model."""

    def __init__(self, config: dict):
        super().__init__("random_forest", config)
        self.scaler = StandardScaler()

        self.model = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> None:
        """Train the Random Forest model."""
        self.feature_names = list(X.columns)
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_trained = True
        logger.info(f"Random Forest model trained on {len(X)} samples")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        X_scaled = self.scaler.transform(X[self.feature_names])
        return self.model.predict(X_scaled)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        X_scaled = self.scaler.transform(X[self.feature_names])
        return self.model.predict_proba(X_scaled)


class ProphetModel(BaseModel):
    """Prophet-based trading model for time series forecasting.

    Prophet is designed for time series with strong seasonality patterns.
    For trading, we convert price predictions to classification signals.
    """

    def __init__(self, config: dict):
        super().__init__("prophet", config)
        self.model = None
        self.threshold = 0.0  # Threshold for up/down classification
        self.forecast_periods = 1  # How many periods ahead to forecast

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> None:
        """Train the Prophet model.

        Prophet requires a DataFrame with 'ds' (datetime) and 'y' (value) columns.
        We use the close price for forecasting.
        """
        from prophet import Prophet

        self.feature_names = list(X.columns)

        # Prophet needs datetime index
        if isinstance(X.index, pd.DatetimeIndex):
            df_prophet = pd.DataFrame({
                'ds': X.index,
                'y': X['close'] if 'close' in X.columns else X.iloc[:, 0]
            })
        else:
            # Create dummy datetime if not available
            df_prophet = pd.DataFrame({
                'ds': pd.date_range(start='2020-01-01', periods=len(X), freq='h'),
                'y': X['close'] if 'close' in X.columns else X.iloc[:, 0]
            })

        # Remove timezone if present
        if df_prophet['ds'].dt.tz is not None:
            df_prophet['ds'] = df_prophet['ds'].dt.tz_localize(None)

        # Initialize Prophet with trading-relevant settings
        self.model = Prophet(
            daily_seasonality=True,
            weekly_seasonality=True,
            yearly_seasonality=False,  # Crypto doesn't have strong yearly patterns
            changepoint_prior_scale=0.1,  # More flexible to changes
            seasonality_mode='multiplicative',
            interval_width=0.8
        )

        # Suppress Prophet's verbose output
        self.model.fit(df_prophet)
        self.is_trained = True
        self._last_training_data = df_prophet
        logger.info(f"Prophet model trained on {len(X)} samples")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make binary predictions (0 = down, 1 = up)."""
        probas = self.predict_proba(X)
        # Use probability of price going up
        return (probas[:, 1] >= 0.5).astype(int)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Get prediction probabilities.

        Prophet forecasts price, we convert to probability of going up.
        """
        if not self.is_trained or self.model is None:
            raise ValueError("Model not trained")

        # Create future dataframe for prediction
        if isinstance(X.index, pd.DatetimeIndex):
            future = pd.DataFrame({'ds': X.index})
        else:
            # Use last training dates + periods
            last_date = self._last_training_data['ds'].max()
            future = pd.DataFrame({
                'ds': pd.date_range(start=last_date, periods=len(X) + 1, freq='h')[1:]
            })

        # Remove timezone if present
        if future['ds'].dt.tz is not None:
            future['ds'] = future['ds'].dt.tz_localize(None)

        # Get forecast
        forecast = self.model.predict(future)

        # Calculate predicted returns
        current_prices = X['close'].values if 'close' in X.columns else X.iloc[:, 0].values
        predicted_prices = forecast['yhat'].values[:len(current_prices)]

        # Calculate probability based on predicted change
        predicted_returns = (predicted_prices - current_prices) / current_prices

        # Convert returns to probabilities using sigmoid-like transformation
        # Positive return -> higher probability of "up"
        scale = 100  # Sensitivity factor
        prob_up = 1 / (1 + np.exp(-predicted_returns * scale))
        prob_down = 1 - prob_up

        return np.column_stack([prob_down, prob_up])

    def get_forecast(self, periods: int = 24) -> pd.DataFrame:
        """Get full Prophet forecast with confidence intervals.

        Args:
            periods: Number of periods to forecast ahead

        Returns:
            DataFrame with yhat, yhat_lower, yhat_upper
        """
        if not self.is_trained or self.model is None:
            raise ValueError("Model not trained")

        future = self.model.make_future_dataframe(periods=periods, freq='h')
        forecast = self.model.predict(future)

        return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(periods)


class TransformerModel(BaseModel):
    """Transformer-based trading model using self-attention mechanism.

    This is a simplified Transformer architecture adapted for time-series
    classification in trading. Uses positional encoding and multi-head attention.
    """

    def __init__(self, config: dict):
        super().__init__("transformer", config)
        self.scaler = StandardScaler()
        self.model = None
        self.sequence_length = 20  # Look back window

        # Model hyperparameters
        self.d_model = 64  # Embedding dimension
        self.n_heads = 4   # Number of attention heads
        self.n_layers = 2  # Number of transformer layers
        self.dropout = 0.1
        self.epochs = 50
        self.batch_size = 32

    def _build_model(self, input_dim: int):
        """Build the Transformer model using PyTorch."""
        import torch
        import torch.nn as nn

        class PositionalEncoding(nn.Module):
            def __init__(self, d_model, max_len=100):
                super().__init__()
                pe = torch.zeros(max_len, d_model)
                position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
                div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-np.log(10000.0) / d_model))
                pe[:, 0::2] = torch.sin(position * div_term)
                pe[:, 1::2] = torch.cos(position * div_term)
                pe = pe.unsqueeze(0)
                self.register_buffer('pe', pe)

            def forward(self, x):
                return x + self.pe[:, :x.size(1), :]

        class TradingTransformer(nn.Module):
            def __init__(self, input_dim, d_model, n_heads, n_layers, dropout):
                super().__init__()
                self.input_projection = nn.Linear(input_dim, d_model)
                self.pos_encoder = PositionalEncoding(d_model)
                encoder_layer = nn.TransformerEncoderLayer(
                    d_model=d_model, nhead=n_heads, dropout=dropout, batch_first=True
                )
                self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
                self.fc = nn.Sequential(
                    nn.Linear(d_model, 32),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.Linear(32, 2)  # Binary classification: down, up
                )

            def forward(self, x):
                x = self.input_projection(x)
                x = self.pos_encoder(x)
                x = self.transformer(x)
                x = x[:, -1, :]  # Take last timestep
                return self.fc(x)

        return TradingTransformer(input_dim, self.d_model, self.n_heads, self.n_layers, self.dropout)

    def _create_sequences(self, X: np.ndarray, y: np.ndarray = None):
        """Create sequences for transformer input."""
        sequences = []
        labels = []
        for i in range(len(X) - self.sequence_length):
            sequences.append(X[i:i + self.sequence_length])
            if y is not None:
                labels.append(y[i + self.sequence_length])
        return np.array(sequences), np.array(labels) if y is not None else None

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> None:
        """Train the Transformer model."""
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset

        self.feature_names = list(X.columns)
        X_scaled = self.scaler.fit_transform(X)

        # Create sequences
        X_seq, y_seq = self._create_sequences(X_scaled, y.values)

        if len(X_seq) < 10:
            raise ValueError("Not enough data for Transformer training")

        # Convert to tensors
        X_tensor = torch.FloatTensor(X_seq)
        y_tensor = torch.LongTensor(y_seq)

        # Create data loader
        dataset = TensorDataset(X_tensor, y_tensor)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        # Build model
        self.model = self._build_model(X.shape[1])
        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)

        # Training loop
        self.model.train()
        for epoch in range(self.epochs):
            total_loss = 0
            for batch_X, batch_y in loader:
                optimizer.zero_grad()
                outputs = self.model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()

        self.is_trained = True
        logger.info(f"Transformer model trained on {len(X)} samples")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions."""
        probas = self.predict_proba(X)
        return (probas[:, 1] >= 0.5).astype(int)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Get prediction probabilities."""
        import torch
        import torch.nn.functional as F

        if not self.is_trained or self.model is None:
            raise ValueError("Model not trained")

        X_scaled = self.scaler.transform(X[self.feature_names])

        # Need at least sequence_length samples
        if len(X_scaled) < self.sequence_length:
            # Pad with zeros if not enough data
            padding = np.zeros((self.sequence_length - len(X_scaled), X_scaled.shape[1]))
            X_scaled = np.vstack([padding, X_scaled])

        X_seq, _ = self._create_sequences(X_scaled)
        if len(X_seq) == 0:
            X_seq = X_scaled[-self.sequence_length:].reshape(1, self.sequence_length, -1)

        X_tensor = torch.FloatTensor(X_seq)

        self.model.eval()
        with torch.no_grad():
            outputs = self.model(X_tensor)
            probas = F.softmax(outputs, dim=1).numpy()

        return probas


class PPOModel(BaseModel):
    """PPO (Proximal Policy Optimization) based trading model.

    This implements a reinforcement learning approach where the agent
    learns to maximize trading rewards through experience.
    """

    def __init__(self, config: dict):
        super().__init__("ppo", config)
        self.scaler = StandardScaler()
        self.model = None
        self.env = None

        # PPO hyperparameters
        self.learning_rate = 0.0003
        self.n_steps = 2048
        self.batch_size = 64
        self.n_epochs = 10
        self.gamma = 0.99

    def _create_trading_env(self, X: np.ndarray, y: np.ndarray):
        """Create a custom trading environment for RL."""
        import gymnasium as gym
        from gymnasium import spaces

        class TradingEnv(gym.Env):
            def __init__(self, features, labels, window_size=20):
                super().__init__()
                self.features = features
                self.labels = labels
                self.window_size = window_size
                self.current_step = window_size

                # Action: 0 = predict down, 1 = predict up
                self.action_space = spaces.Discrete(2)

                # Observation: last window_size of features
                self.observation_space = spaces.Box(
                    low=-np.inf, high=np.inf,
                    shape=(window_size * features.shape[1],),
                    dtype=np.float32
                )

            def reset(self, seed=None, options=None):
                super().reset(seed=seed)
                self.current_step = self.window_size
                return self._get_observation(), {}

            def _get_observation(self):
                obs = self.features[self.current_step - self.window_size:self.current_step]
                return obs.flatten().astype(np.float32)

            def step(self, action):
                # Reward: +1 for correct prediction, -1 for wrong
                correct = int(action == self.labels[self.current_step])
                reward = 1.0 if correct else -1.0

                self.current_step += 1
                done = self.current_step >= len(self.features) - 1
                truncated = False

                return self._get_observation(), reward, done, truncated, {}

        return TradingEnv(X, y)

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> None:
        """Train the PPO model."""
        from stable_baselines3 import PPO
        from stable_baselines3.common.vec_env import DummyVecEnv

        self.feature_names = list(X.columns)
        X_scaled = self.scaler.fit_transform(X)
        y_values = y.values

        if len(X_scaled) < 100:
            raise ValueError("Not enough data for PPO training (need at least 100 samples)")

        # Create environment
        self.env = self._create_trading_env(X_scaled, y_values)
        vec_env = DummyVecEnv([lambda: self._create_trading_env(X_scaled, y_values)])

        # Initialize PPO
        self.model = PPO(
            "MlpPolicy",
            vec_env,
            learning_rate=self.learning_rate,
            n_steps=min(self.n_steps, len(X_scaled) - 50),
            batch_size=self.batch_size,
            n_epochs=self.n_epochs,
            gamma=self.gamma,
            verbose=0
        )

        # Train
        total_timesteps = min(len(X_scaled) * 5, 50000)
        self.model.learn(total_timesteps=total_timesteps)

        self.is_trained = True
        logger.info(f"PPO model trained on {len(X)} samples")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions using the trained PPO policy."""
        if not self.is_trained or self.model is None:
            raise ValueError("Model not trained")

        X_scaled = self.scaler.transform(X[self.feature_names])
        predictions = []

        window_size = 20
        for i in range(len(X_scaled)):
            if i < window_size:
                # Not enough history, use zeros
                obs = np.zeros(window_size * X_scaled.shape[1])
            else:
                obs = X_scaled[i - window_size:i].flatten()

            action, _ = self.model.predict(obs.astype(np.float32), deterministic=True)
            predictions.append(action)

        return np.array(predictions)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Get prediction probabilities from PPO policy."""
        import torch

        if not self.is_trained or self.model is None:
            raise ValueError("Model not trained")

        X_scaled = self.scaler.transform(X[self.feature_names])
        probabilities = []

        window_size = 20
        for i in range(len(X_scaled)):
            if i < window_size:
                obs = np.zeros(window_size * X_scaled.shape[1])
            else:
                obs = X_scaled[i - window_size:i].flatten()

            obs_tensor = torch.FloatTensor(obs.astype(np.float32)).unsqueeze(0)

            # Get action distribution from policy
            with torch.no_grad():
                dist = self.model.policy.get_distribution(obs_tensor)
                probs = dist.distribution.probs.numpy()[0]

            probabilities.append(probs)

        return np.array(probabilities)


class EnsembleModel(BaseModel):
    """Ensemble model combining multiple classifiers."""

    def __init__(self, config: dict):
        super().__init__("ensemble", config)
        self.scaler = StandardScaler()
        self.models = {}

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> None:
        """Train the ensemble model."""
        self.feature_names = list(X.columns)
        X_scaled = self.scaler.fit_transform(X)

        # Initialize individual models
        xgb = XGBClassifier(
            n_estimators=100, max_depth=5, learning_rate=0.1,
            random_state=42, eval_metric="logloss"
        )
        lgbm = LGBMClassifier(
            n_estimators=100, max_depth=5, learning_rate=0.1,
            random_state=42, verbose=-1
        )
        rf = RandomForestClassifier(
            n_estimators=100, max_depth=8, random_state=42, n_jobs=-1
        )

        # Create voting classifier
        self.model = VotingClassifier(
            estimators=[
                ("xgb", xgb),
                ("lgbm", lgbm),
                ("rf", rf)
            ],
            voting="soft",
            weights=[0.4, 0.4, 0.2]
        )

        self.model.fit(X_scaled, y)
        self.is_trained = True
        logger.info(f"Ensemble model trained on {len(X)} samples")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        X_scaled = self.scaler.transform(X[self.feature_names])
        return self.model.predict(X_scaled)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        X_scaled = self.scaler.transform(X[self.feature_names])
        return self.model.predict_proba(X_scaled)


class MultiModel(BaseModel):
    """Multi-model system allowing multiple models to run simultaneously with custom weights.

    This provides more flexibility than EnsembleModel by allowing:
    - Dynamic selection of which models to use
    - Custom weight configuration for each model
    - Individual model performance tracking
    """

    # Available model types that can be used in multi-model
    AVAILABLE_MODELS = ["xgboost", "lightgbm", "random_forest", "prophet", "transformer", "ppo"]

    def __init__(self, config: dict):
        super().__init__("multi_model", config)

        # Get multi-model config
        multi_config = config.get("model", {}).get("multi_model", {})

        # Models to use and their weights
        self.selected_models = multi_config.get("models", ["xgboost", "lightgbm"])
        self.weights = multi_config.get("weights", {})

        # Normalize weights - default to equal weight if not specified
        self._normalize_weights()

        # Store individual model instances
        self.models: dict = {}
        self.model_metrics: dict = {}  # Track individual model performance

        logger.info(f"MultiModel initialized with models: {self.selected_models}")
        logger.info(f"Model weights: {self.weights}")

    def _normalize_weights(self):
        """Ensure weights sum to 1.0 and all selected models have weights."""
        # Assign default weights for models without specified weights
        for model_name in self.selected_models:
            if model_name not in self.weights:
                self.weights[model_name] = 1.0

        # Normalize to sum to 1.0
        total_weight = sum(self.weights.get(m, 0) for m in self.selected_models)
        if total_weight > 0:
            for model_name in self.selected_models:
                self.weights[model_name] = self.weights[model_name] / total_weight

    def _create_model_instance(self, model_type: str) -> BaseModel:
        """Create a single model instance."""
        model_classes = {
            "xgboost": XGBoostModel,
            "lightgbm": LightGBMModel,
            "random_forest": RandomForestModel,
            "prophet": ProphetModel,
            "transformer": TransformerModel,
            "ppo": PPOModel
        }

        if model_type not in model_classes:
            raise ValueError(f"Unknown model type: {model_type}")

        return model_classes[model_type](self.config)

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> None:
        """Train all selected models."""
        self.feature_names = list(X.columns)

        for model_name in self.selected_models:
            logger.info(f"Training {model_name} model...")
            try:
                model = self._create_model_instance(model_name)
                model.train(X, y, **kwargs)
                self.models[model_name] = model
                logger.info(f"{model_name} trained successfully")
            except Exception as e:
                logger.error(f"Failed to train {model_name}: {e}")
                # Remove from selected models if training fails
                self.selected_models.remove(model_name)

        if not self.models:
            raise ValueError("No models were successfully trained")

        # Re-normalize weights after potentially removing failed models
        self._normalize_weights()

        self.is_trained = True
        logger.info(f"MultiModel trained with {len(self.models)} models: {list(self.models.keys())}")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions using weighted voting from all models."""
        probas = self.predict_proba(X)
        return (probas[:, 1] >= 0.5).astype(int)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Get weighted average of prediction probabilities from all models."""
        if not self.is_trained or not self.models:
            raise ValueError("Model not trained")

        weighted_probas = None

        for model_name, model in self.models.items():
            weight = self.weights.get(model_name, 0)
            try:
                probas = model.predict_proba(X)
                if weighted_probas is None:
                    weighted_probas = weight * probas
                else:
                    weighted_probas += weight * probas
            except Exception as e:
                logger.warning(f"Error getting predictions from {model_name}: {e}")

        if weighted_probas is None:
            raise ValueError("No models produced predictions")

        return weighted_probas

    def get_individual_predictions(self, X: pd.DataFrame) -> dict:
        """Get predictions from each individual model for comparison.

        Returns:
            Dictionary with model names as keys and their predictions as values
        """
        if not self.is_trained:
            raise ValueError("Model not trained")

        predictions = {}
        for model_name, model in self.models.items():
            try:
                probas = model.predict_proba(X)
                predictions[model_name] = {
                    "prediction": (probas[:, 1] >= 0.5).astype(int),
                    "probability": probas[:, 1],
                    "weight": self.weights.get(model_name, 0)
                }
            except Exception as e:
                logger.warning(f"Error getting predictions from {model_name}: {e}")

        return predictions

    def update_weights(self, new_weights: dict) -> None:
        """Update model weights dynamically.

        Args:
            new_weights: Dictionary of model_name -> weight
        """
        for model_name, weight in new_weights.items():
            if model_name in self.selected_models:
                self.weights[model_name] = weight

        self._normalize_weights()
        logger.info(f"Updated weights: {self.weights}")

    def add_model(self, model_name: str, weight: float = 1.0) -> None:
        """Add a new model to the multi-model system.

        Note: Requires retraining after adding.
        """
        if model_name not in self.AVAILABLE_MODELS:
            raise ValueError(f"Unknown model: {model_name}. Available: {self.AVAILABLE_MODELS}")

        if model_name not in self.selected_models:
            self.selected_models.append(model_name)
            self.weights[model_name] = weight
            self._normalize_weights()
            self.is_trained = False  # Require retraining
            logger.info(f"Added {model_name} with weight {weight}. Retraining required.")

    def remove_model(self, model_name: str) -> None:
        """Remove a model from the multi-model system."""
        if model_name in self.selected_models:
            self.selected_models.remove(model_name)
            if model_name in self.models:
                del self.models[model_name]
            if model_name in self.weights:
                del self.weights[model_name]
            self._normalize_weights()
            logger.info(f"Removed {model_name}")

    def get_model_info(self) -> dict:
        """Get information about all models in the system."""
        return {
            "selected_models": self.selected_models,
            "weights": self.weights,
            "trained_models": list(self.models.keys()),
            "is_trained": self.is_trained,
            "available_models": self.AVAILABLE_MODELS
        }


def create_model(config: dict) -> BaseModel:
    """
    Factory function to create a model based on config.

    Args:
        config: Configuration dictionary

    Returns:
        Initialized model instance
    """
    model_type = config.get("model", {}).get("type", "xgboost")

    models = {
        "xgboost": XGBoostModel,
        "lightgbm": LightGBMModel,
        "random_forest": RandomForestModel,
        "prophet": ProphetModel,
        "transformer": TransformerModel,
        "ppo": PPOModel,
        "ensemble": EnsembleModel,
        "multi_model": MultiModel
    }

    if model_type not in models:
        raise ValueError(f"Unknown model type: {model_type}")

    return models[model_type](config)


def cross_validate_model(
    model: BaseModel,
    X: pd.DataFrame,
    y: pd.Series,
    n_splits: int = 5
) -> dict:
    """
    Perform time-series cross-validation.

    Args:
        model: Model to validate
        X: Features
        y: Target
        n_splits: Number of CV splits

    Returns:
        Dictionary with CV scores
    """
    tscv = TimeSeriesSplit(n_splits=n_splits)

    scores = {
        "accuracy": [],
        "precision": [],
        "f1": []
    }

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        # Train on fold
        model.train(X_train, y_train, eval_set=False)
        metrics = model.evaluate(X_val, y_val)

        scores["accuracy"].append(metrics["accuracy"])
        scores["precision"].append(metrics["precision"])
        scores["f1"].append(metrics["f1_score"])

        logger.info(f"Fold {fold + 1}: Accuracy={metrics['accuracy']:.4f}")

    # Calculate mean scores
    results = {
        "mean_accuracy": np.mean(scores["accuracy"]),
        "std_accuracy": np.std(scores["accuracy"]),
        "mean_precision": np.mean(scores["precision"]),
        "mean_f1": np.mean(scores["f1"]),
    }

    logger.info(f"CV Results: Accuracy={results['mean_accuracy']:.4f} +/- {results['std_accuracy']:.4f}")
    return results
