# Trading Strategies

Guide to ML models, feature engineering, and trading strategies in Robo Trader.

---

## ML Models Overview

### Available Models

| Model | Type | Best For | Training Speed | Prediction Speed |
|-------|------|----------|----------------|------------------|
| **XGBoost** | Gradient Boosting | General purpose | Fast | Very Fast |
| **LightGBM** | Gradient Boosting | Large datasets | Very Fast | Very Fast |
| **Random Forest** | Ensemble | Stability | Medium | Fast |
| **Ensemble** | Voting Classifier | Best accuracy | Slow | Medium |

### Model Selection

```yaml
# In config/config.yaml
model:
  type: "xgboost"  # xgboost | lightgbm | random_forest | ensemble
```

---

## Feature Engineering

### Technical Indicators (50+)

#### Momentum Indicators
| Indicator | Description | Interpretation |
|-----------|-------------|----------------|
| **RSI (14)** | Relative Strength Index | >70 overbought, <30 oversold |
| **RSI (7)** | Fast RSI | More responsive |
| **MACD** | Moving Average Convergence Divergence | Trend direction |
| **Stochastic** | Stochastic Oscillator | Momentum |
| **CCI** | Commodity Channel Index | Trend strength |
| **ROC** | Rate of Change | Momentum |

#### Trend Indicators
| Indicator | Description | Interpretation |
|-----------|-------------|----------------|
| **EMA (9, 21, 50)** | Exponential Moving Averages | Short/medium/long trend |
| **SMA (20, 50)** | Simple Moving Averages | Trend direction |
| **ADX** | Average Directional Index | Trend strength (>25 strong) |
| **DI+/DI-** | Directional Indicators | Trend direction |

#### Volatility Indicators
| Indicator | Description | Interpretation |
|-----------|-------------|----------------|
| **Bollinger Bands** | Price channels | Volatility, overbought/oversold |
| **ATR (14)** | Average True Range | Volatility measure |
| **BB Width** | Bollinger Band Width | Volatility expansion/contraction |

#### Volume Indicators
| Indicator | Description | Interpretation |
|-----------|-------------|----------------|
| **OBV** | On Balance Volume | Volume trend |
| **Volume SMA** | Volume Moving Average | Average volume |
| **Volume Ratio** | Current vs Average Volume | Volume anomalies |

### Price Features

| Feature | Description |
|---------|-------------|
| `returns_1/5/10/20` | Price returns over periods |
| `log_returns` | Logarithmic returns |
| `volatility_10/20` | Rolling volatility |
| `momentum_10/20` | Price momentum |
| `hl_range` | High-Low range |
| `close_position` | Close position in candle |
| `gap` | Opening gap |

### Time Features

| Feature | Description |
|---------|-------------|
| `hour` | Hour of day (0-23) |
| `day_of_week` | Day of week (0-6) |
| `hour_sin/cos` | Cyclical hour encoding |
| `dow_sin/cos` | Cyclical day encoding |

### Lagged Features

Features with lag of 1, 2, 3, 5 periods:
- `returns_1_lag_N`
- `rsi_14_lag_N`
- `macd_hist_lag_N`
- `volume_ratio_lag_N`

---

## Target Variable

### Binary Classification

```python
# Price goes up (1) or down (0) in next period
target = 1 if future_return > 0 else 0
```

### Multi-class Classification

```python
# 0 = Down, 1 = Neutral, 2 = Up
target_3class = pd.cut(
    future_return,
    bins=[-inf, -threshold, threshold, inf],
    labels=[0, 1, 2]
)
```

---

## Signal Generation

### Signal Thresholds

```python
# In strategy/ml_strategy.py
buy_threshold = 0.6   # Probability >= 60% for BUY
sell_threshold = 0.4  # Probability <= 40% for SELL
```

### Signal Logic

```python
if up_probability >= 0.6:
    signal = BUY
elif up_probability <= 0.4:
    signal = SELL
else:
    signal = HOLD
```

---

## Risk Management

### Position Sizing

```python
def calculate_position_size(capital, price, risk_pct, stop_loss_pct):
    risk_amount = capital * risk_pct  # e.g., 1% of capital
    position_value = risk_amount / stop_loss_pct
    position_size = position_value / price
    return position_size
```

### Stop Loss & Take Profit

```python
entry_price = 45000
stop_loss_pct = 0.02  # 2%
take_profit_pct = 0.04  # 4%

stop_loss = entry_price * (1 - stop_loss_pct)  # 44100
take_profit = entry_price * (1 + take_profit_pct)  # 46800
```

### Risk:Reward Ratio

| Stop Loss | Take Profit | Risk:Reward |
|-----------|-------------|-------------|
| 1% | 2% | 1:2 |
| 2% | 4% | 1:2 |
| 2% | 6% | 1:3 |

---

## Backtesting Metrics

### Key Performance Metrics

| Metric | Good | Excellent | Description |
|--------|------|-----------|-------------|
| **Total Return** | >10% | >25% | Overall profit/loss |
| **Sharpe Ratio** | >1.0 | >2.0 | Risk-adjusted return |
| **Max Drawdown** | <15% | <10% | Largest peak-to-trough decline |
| **Win Rate** | >50% | >55% | Percentage of winning trades |
| **Profit Factor** | >1.2 | >1.5 | Gross profit / Gross loss |

### Interpreting Results

```
Total Return: 15.5%      ✓ Good
Sharpe Ratio: 1.45       ✓ Good
Max Drawdown: -12.3%     ✓ Acceptable
Win Rate: 54.2%          ✓ Good
Profit Factor: 1.38      ✓ Good
```

---

## Model Training Best Practices

### Data Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Training Period | 6 months | 1-2 years |
| Number of Candles | 1,000 | 5,000+ |
| Test Period | 1 month | 3 months |

### Train-Test Split

```python
# Time-series split (no shuffle!)
train_size = 0.8  # 80% training
test_size = 0.2   # 20% testing

# Example with 1 year of hourly data (8760 candles)
# Training: 7008 candles
# Testing: 1752 candles
```

### Cross-Validation

```python
# Time-series cross-validation
from sklearn.model_selection import TimeSeriesSplit

tscv = TimeSeriesSplit(n_splits=5)
# Each fold trains on past data, tests on future data
```

---

## Strategy Configuration Examples

### Conservative Strategy

```yaml
risk:
  max_position_size: 0.05   # 5% max per trade
  stop_loss_pct: 0.01       # 1% stop loss
  take_profit_pct: 0.02     # 2% take profit
  max_open_positions: 2
  daily_loss_limit: 0.03    # 3% daily limit

model:
  type: "ensemble"          # Most stable
```

### Moderate Strategy

```yaml
risk:
  max_position_size: 0.1    # 10% max per trade
  stop_loss_pct: 0.02       # 2% stop loss
  take_profit_pct: 0.04     # 4% take profit
  max_open_positions: 3
  daily_loss_limit: 0.05    # 5% daily limit

model:
  type: "xgboost"           # Good balance
```

### Aggressive Strategy

```yaml
risk:
  max_position_size: 0.2    # 20% max per trade
  stop_loss_pct: 0.03       # 3% stop loss
  take_profit_pct: 0.06     # 6% take profit
  max_open_positions: 5
  daily_loss_limit: 0.1     # 10% daily limit

model:
  type: "lightgbm"          # Fast signals
```

---

## Improving Strategy Performance

### 1. Feature Selection
- Use feature importance to remove weak features
- Add domain-specific indicators
- Test different lookback periods

### 2. Model Tuning
- Adjust classification threshold
- Try different model types
- Tune hyperparameters

### 3. Risk Management
- Adjust position sizing
- Optimize stop loss / take profit
- Implement trailing stops

### 4. Market Conditions
- Different strategies for trending vs ranging markets
- Adjust for volatility regimes
- Consider multiple timeframes

---

## Next Steps

- [Deployment](./09-deployment.md) - Production deployment guide
- [Troubleshooting](./10-troubleshooting.md) - Common issues and solutions
