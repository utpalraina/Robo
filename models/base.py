"""Base model class for trading models."""

from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
import joblib
from pathlib import Path
from loguru import logger


class BaseModel(ABC):
    """Abstract base class for ML trading models."""

    def __init__(self, name: str, config: dict):
        """
        Initialize base model.

        Args:
            name: Model name
            config: Model configuration
        """
        self.name = name
        self.config = config
        self.model = None
        self.is_trained = False
        self.feature_names = None
        self.metrics = {}

    @abstractmethod
    def train(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Train the model."""
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions."""
        pass

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Get prediction probabilities."""
        pass

    def save(self, path: str) -> None:
        """
        Save model to disk.

        Args:
            path: Path to save model
        """
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        model_data = {
            "model": self.model,
            "name": self.name,
            "config": self.config,
            "feature_names": self.feature_names,
            "metrics": self.metrics,
            "is_trained": self.is_trained,
            "scaler": getattr(self, 'scaler', None)  # Save scaler if exists
        }
        joblib.dump(model_data, path)
        logger.info(f"Model saved to {path}")

    def load(self, path: str) -> None:
        """
        Load model from disk.

        Args:
            path: Path to model file
        """
        model_data = joblib.load(path)
        self.model = model_data["model"]
        self.name = model_data["name"]
        self.config = model_data["config"]
        self.feature_names = model_data["feature_names"]
        self.metrics = model_data["metrics"]
        self.is_trained = model_data["is_trained"]
        # Load scaler if saved
        if "scaler" in model_data and model_data["scaler"] is not None:
            self.scaler = model_data["scaler"]
        logger.info(f"Model loaded from {path}")

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """
        Evaluate model performance.

        Args:
            X: Feature DataFrame
            y: True labels

        Returns:
            Dictionary of metrics
        """
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score,
            f1_score, roc_auc_score, classification_report
        )

        predictions = self.predict(X)
        probas = self.predict_proba(X)

        metrics = {
            "accuracy": accuracy_score(y, predictions),
            "precision": precision_score(y, predictions, average="weighted", zero_division=0),
            "recall": recall_score(y, predictions, average="weighted", zero_division=0),
            "f1_score": f1_score(y, predictions, average="weighted", zero_division=0),
        }

        # AUC for binary classification
        if len(np.unique(y)) == 2 and probas is not None:
            try:
                metrics["auc"] = roc_auc_score(y, probas[:, 1])
            except:
                pass

        self.metrics = metrics

        # Log classification report
        logger.info(f"\n{classification_report(y, predictions)}")

        return metrics

    def get_feature_importance(self) -> Optional[pd.Series]:
        """Get feature importance scores."""
        if not self.is_trained or self.feature_names is None:
            return None

        if hasattr(self.model, "feature_importances_"):
            importance = pd.Series(
                self.model.feature_importances_,
                index=self.feature_names
            ).sort_values(ascending=False)
            return importance

        return None
