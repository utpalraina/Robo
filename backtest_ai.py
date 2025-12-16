#!/usr/bin/env python3
"""
AI Trading Recommendation Backtester

Tests AI recommendations against historical data to measure performance.
Uses recent data to avoid API rate limiting issues.
"""

import ccxt
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
import os
import sys
from dotenv import load_dotenv
import google.generativeai as genai
import json
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

# Import ICT indicators
try:
    from features.ict_indicators import ICTIndicators
    ICT_AVAILABLE = True
except ImportError:
    ICT_AVAILABLE = False
    print("Warning: ICT indicators not available")

# Import ML models
try:
    from models.ml_models import EnsembleModel
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("Warning: ML models not available")

# Initialize exchange (using Binance for better rate limits on historical data)
exchange = ccxt.binance()

# Load strategies from config file
def load_strategies():
    """Load trading strategies from strategies.json"""
    strategies_file = os.path.join(os.path.dirname(__file__), 'strategies.json')
    try:
        with open(strategies_file, 'r') as f:
            data = json.load(f)
            return data.get('strategies', {})
    except FileNotFoundError:
        print("Warning: strategies.json not found, using default strategy")
        return {}
    except json.JSONDecodeError:
        print("Warning: Error parsing strategies.json")
        return {}

def get_strategy(strategy_name):
    """Get a specific strategy by name"""
    strategies = load_strategies()
    if strategy_name in strategies:
        return strategies[strategy_name]
    # Default fallback strategy
    return {
        "name": "Default",
        "description": "Basic trend following",
        "direction": "BOTH",
        "rules": "Trade with the trend. LONG in uptrend, SHORT in downtrend. Use 1:3 R:R."
    }

def list_strategies():
    """List all available strategies"""
    strategies = load_strategies()
    return [(key, s['name'], s['description']) for key, s in strategies.items()]

def calculate_sma(prices, period):
    """Calculate Simple Moving Average"""
    if len(prices) < period:
        return np.mean(prices) if len(prices) > 0 else None
    return np.mean(prices[-period:])

def calculate_ema(prices, period):
    """Calculate Exponential Moving Average"""
    if len(prices) < 2:
        return prices[0] if len(prices) > 0 else None
    multiplier = 2 / (period + 1)
    ema = prices[0]
    for price in prices[1:]:
        ema = (price - ema) * multiplier + ema
    return ema

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    if len(prices) < period + 1:
        return 50

    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])

    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_atr(highs, lows, closes, period=14):
    """Calculate Average True Range"""
    if len(highs) < period + 1:
        return closes[-1] * 0.02 if len(closes) > 0 else 0

    tr = []
    for i in range(1, len(highs)):
        tr.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        ))
    return np.mean(tr[-period:])

def get_ict_analysis(df):
    """Get ICT indicators analysis for the dataframe."""
    if not ICT_AVAILABLE:
        return None

    try:
        ict = ICTIndicators()
        results = ict.detect_all(df)
        return results
    except Exception as e:
        print(f"  ICT Error: {e}")
        return None

def summarize_ict_for_prompt(ict_data):
    """Summarize ICT data for the AI prompt."""
    if not ict_data:
        return "ICT data not available"

    summary = []

    # Market Structure
    ms = ict_data.get('market_structure', {})
    if ms:
        summary.append(f"Market Structure: {ms.get('trend', 'N/A')} (last break: {ms.get('last_break', 'N/A')})")

    # Fair Value Gaps
    fvgs = ict_data.get('fvg', [])
    bullish_fvg = [f for f in fvgs if f.get('type') == 'bullish' and not f.get('filled', True)]
    bearish_fvg = [f for f in fvgs if f.get('type') == 'bearish' and not f.get('filled', True)]
    if bullish_fvg:
        nearest = bullish_fvg[-1]
        summary.append(f"Bullish FVG: ${nearest.get('gap_low', 0):,.0f} - ${nearest.get('gap_high', 0):,.0f}")
    if bearish_fvg:
        nearest = bearish_fvg[-1]
        summary.append(f"Bearish FVG: ${nearest.get('gap_low', 0):,.0f} - ${nearest.get('gap_high', 0):,.0f}")
    if not bullish_fvg and not bearish_fvg:
        summary.append("No unfilled FVGs nearby")

    # Order Blocks
    obs = ict_data.get('order_blocks', [])
    bullish_ob = [o for o in obs if o.get('type') == 'bullish' and o.get('valid', False)]
    bearish_ob = [o for o in obs if o.get('type') == 'bearish' and o.get('valid', False)]
    if bullish_ob:
        nearest = bullish_ob[-1]
        summary.append(f"Bullish OB: ${nearest.get('low', 0):,.0f} - ${nearest.get('high', 0):,.0f}")
    if bearish_ob:
        nearest = bearish_ob[-1]
        summary.append(f"Bearish OB: ${nearest.get('low', 0):,.0f} - ${nearest.get('high', 0):,.0f}")

    # Premium/Discount
    pd_zones = ict_data.get('premium_discount', {})
    if pd_zones:
        zone = pd_zones.get('current_zone', 'N/A')
        eq = pd_zones.get('equilibrium', 0)
        summary.append(f"Zone: {zone} (Equilibrium: ${eq:,.0f})")

    # Liquidity
    liq = ict_data.get('liquidity_zones', [])
    if isinstance(liq, dict):
        buy_liq = liq.get('buy_side', [])
        sell_liq = liq.get('sell_side', [])
        if buy_liq:
            summary.append(f"Buy-side liquidity: ${buy_liq[-1].get('level', 0):,.0f}")
        if sell_liq:
            summary.append(f"Sell-side liquidity: ${sell_liq[-1].get('level', 0):,.0f}")
    elif isinstance(liq, list) and liq:
        # Handle list format
        for zone in liq[-3:]:  # Last 3 zones
            if isinstance(zone, dict):
                summary.append(f"Liquidity zone: ${zone.get('level', 0):,.0f} ({zone.get('type', 'N/A')})")

    return "\n".join(summary) if summary else "No significant ICT levels detected"


def prepare_ml_features(df):
    """Prepare features for ML model from OHLCV data."""
    features = pd.DataFrame(index=df.index)

    # Price-based features
    features['returns'] = df['close'].pct_change()
    features['log_returns'] = np.log(df['close'] / df['close'].shift(1))

    # Moving averages
    features['sma_5'] = df['close'].rolling(5).mean()
    features['sma_10'] = df['close'].rolling(10).mean()
    features['sma_20'] = df['close'].rolling(20).mean()
    features['sma_50'] = df['close'].rolling(50).mean()

    # Price vs MAs
    features['price_sma5_ratio'] = df['close'] / features['sma_5']
    features['price_sma20_ratio'] = df['close'] / features['sma_20']
    features['sma5_sma20_ratio'] = features['sma_5'] / features['sma_20']

    # Volatility
    features['volatility'] = features['returns'].rolling(20).std()
    features['atr'] = (df['high'] - df['low']).rolling(14).mean()
    features['atr_pct'] = features['atr'] / df['close']

    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    features['rsi'] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    features['macd'] = ema12 - ema26
    features['macd_signal'] = features['macd'].ewm(span=9, adjust=False).mean()
    features['macd_hist'] = features['macd'] - features['macd_signal']

    # Momentum
    features['momentum_5'] = df['close'].pct_change(5)
    features['momentum_10'] = df['close'].pct_change(10)
    features['momentum_20'] = df['close'].pct_change(20)

    # Volume features (if available)
    if 'volume' in df.columns:
        features['volume_sma'] = df['volume'].rolling(20).mean()
        features['volume_ratio'] = df['volume'] / features['volume_sma']

    # Candlestick features
    features['body_size'] = abs(df['close'] - df['open']) / df['close']
    features['upper_shadow'] = (df['high'] - df[['close', 'open']].max(axis=1)) / df['close']
    features['lower_shadow'] = (df[['close', 'open']].min(axis=1) - df['low']) / df['close']

    # Higher timeframe features
    features['high_20'] = df['high'].rolling(20).max()
    features['low_20'] = df['low'].rolling(20).min()
    features['price_in_range'] = (df['close'] - features['low_20']) / (features['high_20'] - features['low_20'])

    # Drop NaN rows
    features = features.dropna()

    return features


def create_ml_labels(df, lookahead=12, threshold=0.005):
    """Create labels for ML model: 1 if price goes up by threshold, 0 otherwise."""
    future_returns = df['close'].shift(-lookahead) / df['close'] - 1
    labels = (future_returns > threshold).astype(int)
    return labels


def get_ml_prediction(df_history, min_train_samples=200):
    """Get ML model prediction for the current data point."""
    if not ML_AVAILABLE:
        return None

    try:
        # Prepare features
        features = prepare_ml_features(df_history)

        if len(features) < min_train_samples:
            return None

        # Create labels (looking ahead 12 hours)
        labels = create_ml_labels(df_history.loc[features.index], lookahead=12, threshold=0.005)

        # Align features and labels
        valid_idx = features.index.intersection(labels.dropna().index)
        X = features.loc[valid_idx[:-1]]  # All except last (need label for training)
        y = labels.loc[valid_idx[:-1]]

        if len(X) < min_train_samples:
            return None

        # Use last portion for training (most recent data)
        train_size = min(500, len(X))
        X_train = X.iloc[-train_size:]
        y_train = y.iloc[-train_size:]

        # Train ensemble model
        model = EnsembleModel({})
        model.train(X_train, y_train)

        # Predict for the last data point
        X_current = features.iloc[[-1]]  # Last row as DataFrame
        proba = model.predict_proba(X_current)

        # Return probability of price going up
        return {
            'prob_up': float(proba[0, 1]),
            'prob_down': float(proba[0, 0]),
            'prediction': 'BULLISH' if proba[0, 1] > 0.55 else 'BEARISH' if proba[0, 1] < 0.45 else 'NEUTRAL',
            'confidence': float(max(proba[0, 0], proba[0, 1]))
        }
    except Exception as e:
        print(f"  ML Error: {e}")
        return None


def summarize_ml_for_prompt(ml_data):
    """Summarize ML prediction for the AI prompt."""
    if not ml_data:
        return "ML predictions not available"

    prediction = ml_data['prediction']
    prob_up = ml_data['prob_up'] * 100
    confidence = ml_data['confidence'] * 100

    return f"""ML Model Prediction: {prediction}
- Probability UP: {prob_up:.1f}%
- Probability DOWN: {100 - prob_up:.1f}%
- Model Confidence: {confidence:.1f}%
- Models Used: XGBoost + LightGBM + RandomForest (Ensemble)"""


def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD indicator"""
    if len(prices) < slow + signal:
        return None, None, None
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    macd_line = ema_fast - ema_slow
    # Simple approximation of signal line
    macd_values = []
    for i in range(signal, len(prices)):
        fast_ema = calculate_ema(prices[:i+1], fast)
        slow_ema = calculate_ema(prices[:i+1], slow)
        macd_values.append(fast_ema - slow_ema)
    signal_line = calculate_ema(macd_values, signal) if len(macd_values) >= signal else macd_line
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def get_trend_direction(prices, period=50):
    """Determine trend direction based on price structure"""
    if len(prices) < period:
        return 'NEUTRAL', 0

    # Check if making higher highs and higher lows (uptrend)
    # or lower highs and lower lows (downtrend)
    recent = prices[-period:]
    mid = len(recent) // 2
    first_half = recent[:mid]
    second_half = recent[mid:]

    first_avg = sum(first_half) / len(first_half)
    second_avg = sum(second_half) / len(second_half)

    change_pct = ((second_avg - first_avg) / first_avg) * 100

    if change_pct > 2:
        return 'UPTREND', change_pct
    elif change_pct < -2:
        return 'DOWNTREND', change_pct
    else:
        return 'SIDEWAYS', change_pct

def get_technical_analysis(df):
    """Calculate all technical indicators"""
    prices = df['close'].values.tolist()
    highs = df['high'].values.tolist()
    lows = df['low'].values.tolist()
    current_price = prices[-1]

    # Moving Averages
    sma_20 = calculate_sma(prices, 20)
    sma_50 = calculate_sma(prices, 50)
    sma_200 = calculate_sma(prices, 200) if len(prices) >= 200 else None
    ema_20 = calculate_ema(prices, 20)

    # Oscillators
    rsi = calculate_rsi(prices)
    atr = calculate_atr(highs, lows, prices)

    # MACD
    macd_line, signal_line, macd_histogram = calculate_macd(prices)

    # Trend analysis
    trend, trend_strength = get_trend_direction(prices)

    # Volatility relative to price (ATR as % of price)
    volatility_pct = (atr / current_price) * 100 if current_price > 0 else 0

    # Recent price action (last 5 candles)
    recent_high = max(highs[-5:]) if len(highs) >= 5 else highs[-1]
    recent_low = min(lows[-5:]) if len(lows) >= 5 else lows[-1]

    # Count signals
    buy_count = 0
    sell_count = 0

    if sma_20 and current_price > sma_20: buy_count += 1
    elif sma_20: sell_count += 1

    if sma_50 and current_price > sma_50: buy_count += 1
    elif sma_50: sell_count += 1

    if sma_200 and current_price > sma_200: buy_count += 1
    elif sma_200: sell_count += 1

    if ema_20 and current_price > ema_20: buy_count += 1
    elif ema_20: sell_count += 1

    if rsi < 30: buy_count += 2  # Oversold
    elif rsi > 70: sell_count += 2  # Overbought
    elif rsi < 40: buy_count += 1  # Leaning oversold
    elif rsi > 60: sell_count += 1  # Leaning overbought

    # MACD signal
    if macd_histogram and macd_histogram > 0: buy_count += 1
    elif macd_histogram and macd_histogram < 0: sell_count += 1

    # Trend alignment
    if trend == 'UPTREND': buy_count += 2
    elif trend == 'DOWNTREND': sell_count += 2

    # Determine overall signal
    total = buy_count + sell_count
    if total == 0:
        overall = 'NEUTRAL'
    elif buy_count / total > 0.70:
        overall = 'STRONG BUY'
    elif buy_count / total > 0.55:
        overall = 'BUY'
    elif sell_count / total > 0.70:
        overall = 'STRONG SELL'
    elif sell_count / total > 0.55:
        overall = 'SELL'
    else:
        overall = 'NEUTRAL'

    return {
        'current_price': current_price,
        'overall_signal': overall,
        'rsi': rsi,
        'atr': atr,
        'sma_20': sma_20,
        'sma_50': sma_50,
        'sma_200': sma_200,
        'macd_histogram': macd_histogram,
        'trend': trend,
        'trend_strength': trend_strength,
        'volatility_pct': volatility_pct,
        'recent_high': recent_high,
        'recent_low': recent_low,
        'support_1': current_price - atr,
        'support_2': current_price - 2 * atr,
        'resistance_1': current_price + atr,
        'resistance_2': current_price + 2 * atr,
        'buy_signals': buy_count,
        'sell_signals': sell_count
    }

def get_ai_recommendation(ta_data, test_date_str, ict_data=None, ml_data=None, strategy=None):
    """Get AI recommendation for the given technical analysis using specified strategy"""

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return None

    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-2.0-flash')

    # Build trend info
    trend_info = ta_data.get('trend', 'NEUTRAL')
    trend_strength = ta_data.get('trend_strength', 0)
    macd_hist = ta_data.get('macd_histogram')
    macd_str = f"{macd_hist:+.2f}" if macd_hist else "N/A"
    sma_200 = ta_data.get('sma_200')
    sma_200_str = f"${sma_200:,.2f}" if sma_200 else "N/A"

    # Get ICT summary
    ict_summary = summarize_ict_for_prompt(ict_data) if ict_data else "ICT data not available"

    # Get ML summary
    ml_summary = summarize_ml_for_prompt(ml_data) if ml_data else "ML predictions not available"

    # Get strategy rules
    if strategy is None:
        strategy = get_strategy('trend_follower')  # Default strategy

    strategy_name = strategy.get('name', 'Unknown Strategy')
    strategy_rules = strategy.get('rules', 'Trade with the trend.')
    strategy_direction = strategy.get('direction', 'BOTH')

    # Build direction constraint
    if strategy_direction == 'LONG':
        direction_constraint = 'Only respond with "LONG" or "NO_TRADE". SHORT trades are NOT allowed for this strategy.'
        valid_directions = '"LONG" or "NO_TRADE"'
    elif strategy_direction == 'SHORT':
        direction_constraint = 'Only respond with "SHORT" or "NO_TRADE". LONG trades are NOT allowed for this strategy.'
        valid_directions = '"SHORT" or "NO_TRADE"'
    else:
        direction_constraint = 'You can respond with "LONG", "SHORT", or "NO_TRADE" based on your analysis.'
        valid_directions = '"LONG" or "SHORT" or "NO_TRADE"'

    prompt = f"""You are an expert crypto trader backtesting a specific strategy. Based on the market data from {test_date_str}, provide a trade recommendation following the strategy rules EXACTLY.

=== STRATEGY: {strategy_name} ===
{strategy_rules}

=== MARKET CONTEXT ===
- Trend (50 period): {trend_info} ({trend_strength:+.1f}%)
- Volatility: {ta_data.get('volatility_pct', 0):.2f}% (ATR as % of price)

=== PRICE DATA ===
- Current Price: ${ta_data['current_price']:,.2f}
- Recent High (5 bars): ${ta_data.get('recent_high', 0):,.2f}
- Recent Low (5 bars): ${ta_data.get('recent_low', 0):,.2f}

=== MOVING AVERAGES ===
- SMA 20: {f"${ta_data['sma_20']:,.2f}" if ta_data['sma_20'] else 'N/A'}
- SMA 50: {f"${ta_data['sma_50']:,.2f}" if ta_data['sma_50'] else 'N/A'}
- SMA 200: {sma_200_str}
- EMA 20: {f"${ta_data.get('ema_20', 0):,.2f}" if ta_data.get('ema_20') else 'N/A'}
- Price vs SMA20: {"ABOVE" if ta_data['sma_20'] and ta_data['current_price'] > ta_data['sma_20'] else "BELOW" if ta_data['sma_20'] else "N/A"}

=== OSCILLATORS ===
- RSI (14): {ta_data['rsi']:.1f} {"(OVERSOLD)" if ta_data['rsi'] < 30 else "(OVERBOUGHT)" if ta_data['rsi'] > 70 else ""}
- MACD Histogram: {macd_str}
- ATR (14): ${ta_data['atr']:,.2f}

=== ICT ANALYSIS (Inner Circle Trader Concepts) ===
{ict_summary}

=== ML MODEL PREDICTIONS (Ensemble: XGBoost + LightGBM + RandomForest) ===
{ml_summary}

=== SIGNAL SUMMARY ===
- Overall Signal: {ta_data['overall_signal']}
- Buy Signals: {ta_data['buy_signals']} | Sell Signals: {ta_data['sell_signals']}

=== KEY LEVELS ===
- Support 1: ${ta_data['support_1']:,.2f}
- Resistance 1: ${ta_data['resistance_1']:,.2f}

=== RESPONSE FORMAT ===
Respond in this EXACT JSON format only (no markdown, no explanation):
{{"direction": {valid_directions}, "entry": <number>, "stop_loss": <number>, "take_profit": <number>}}
{direction_constraint}
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        # Clean up response
        text = text.replace('```json', '').replace('```', '').strip()
        return json.loads(text)
    except Exception as e:
        print(f"  AI Error: {e}")
        return None

def check_trade_outcome(df_future, entry, stop_loss, take_profit, direction, use_trailing=False, trail_after_r=1.0, breakeven_at_r=0):
    """
    Check if trade hit TP or SL first in the future data.

    Args:
        df_future: DataFrame with future candles
        entry: Entry price
        stop_loss: Initial stop loss price
        take_profit: Take profit price
        direction: 'LONG' or 'SHORT'
        use_trailing: Whether to use trailing stop loss
        trail_after_r: Start trailing after this R-multiple profit (e.g., 1.0 = after 1R profit)
        breakeven_at_r: Move SL to entry (breakeven) after this R profit (0 = disabled)

    Returns: (outcome, r_multiple, bars_to_outcome)
    """
    current_sl = stop_loss
    risk = abs(entry - stop_loss)
    highest_price = entry  # For LONG trailing
    lowest_price = entry   # For SHORT trailing
    trailing_active = False
    breakeven_active = False

    for i, (_, row) in enumerate(df_future.iterrows()):
        high = row['high']
        low = row['low']
        close = row['close']

        if direction == 'LONG':
            # Update highest price seen
            if high > highest_price:
                highest_price = high

            # Check if we should move to breakeven
            if breakeven_at_r > 0 and not breakeven_active:
                unrealized_r = (highest_price - entry) / risk
                if unrealized_r >= breakeven_at_r:
                    breakeven_active = True
                    current_sl = entry  # Move SL to entry (no loss)

            # Check if we should activate trailing stop (only if not using breakeven)
            if use_trailing and not trailing_active and not breakeven_at_r:
                unrealized_r = (highest_price - entry) / risk
                if unrealized_r >= trail_after_r:
                    trailing_active = True

            # Update trailing stop (trail 1 ATR / 1R behind highest)
            if trailing_active:
                new_sl = highest_price - risk  # Trail by 1R
                if new_sl > current_sl:
                    current_sl = new_sl

            # Check SL first (worst case)
            if low <= current_sl:
                actual_pnl = current_sl - entry
                r_multiple = actual_pnl / risk
                if breakeven_active and abs(r_multiple) < 0.1:
                    return 'BE', 0, i + 1  # Breakeven exit
                outcome = 'TP_HIT' if r_multiple > 0 else 'SL_HIT'
                return outcome, r_multiple, i + 1

            # Check TP
            if high >= take_profit:
                r_multiple = (take_profit - entry) / risk
                return 'TP_HIT', r_multiple, i + 1

        elif direction == 'SHORT':
            # Update lowest price seen
            if low < lowest_price:
                lowest_price = low

            # Check if we should move to breakeven
            if breakeven_at_r > 0 and not breakeven_active:
                unrealized_r = (entry - lowest_price) / risk
                if unrealized_r >= breakeven_at_r:
                    breakeven_active = True
                    current_sl = entry  # Move SL to entry (no loss)

            # Check if we should activate trailing stop
            if use_trailing and not trailing_active and not breakeven_at_r:
                unrealized_r = (entry - lowest_price) / risk
                if unrealized_r >= trail_after_r:
                    trailing_active = True

            # Update trailing stop (trail 1R above lowest)
            if trailing_active:
                new_sl = lowest_price + risk  # Trail by 1R
                if new_sl < current_sl:
                    current_sl = new_sl

            # Check SL first (worst case)
            if high >= current_sl:
                actual_pnl = entry - current_sl
                r_multiple = actual_pnl / risk
                if breakeven_active and abs(r_multiple) < 0.1:
                    return 'BE', 0, i + 1  # Breakeven exit
                outcome = 'TP_HIT' if r_multiple > 0 else 'SL_HIT'
                return outcome, r_multiple, i + 1

            # Check TP
            if low <= take_profit:
                r_multiple = (entry - take_profit) / risk
                return 'TP_HIT', r_multiple, i + 1

    # Neither hit - check final P/L
    final_price = df_future.iloc[-1]['close']
    if direction == 'LONG':
        pnl = final_price - entry
        r_multiple = pnl / risk if risk > 0 else 0
        return 'OPEN', r_multiple, len(df_future)
    else:
        pnl = entry - final_price
        r_multiple = pnl / risk if risk > 0 else 0
        return 'OPEN', r_multiple, len(df_future)

def run_backtest(num_days=10, trades_per_day=10, capital=2000, risk_percent=0.5, start_date=None, use_trailing=False, trail_after_r=1.0, breakeven_at_r=0, strategy_name='trend_follower'):
    """Run backtest using historical data

    Args:
        num_days: Number of days to test
        trades_per_day: Number of trades per day
        capital: Starting capital in USD
        risk_percent: Risk per trade as percentage (0.5 = 0.5%)
        start_date: Start date as 'YYYY-MM-DD' string, or None for recent data
        use_trailing: Whether to use trailing stop loss
        trail_after_r: Start trailing after this R-multiple profit
        breakeven_at_r: Move SL to entry after this R profit (0 = disabled)
        strategy_name: Name of the strategy to use from strategies.json
    """

    # Load the selected strategy
    strategy = get_strategy(strategy_name)
    strategy_display_name = strategy.get('name', strategy_name)
    strategy_direction = strategy.get('direction', 'BOTH')

    total_trades = num_days * trades_per_day
    risk_per_trade = capital * (risk_percent / 100)  # 1R in dollars

    print("=" * 100)
    print(f"AI TRADING BACKTEST - Strategy: {strategy_display_name}")
    print("=" * 100)

    # Print all input parameters
    print(f"\n{'INPUT PARAMETERS':^50}")
    print("-" * 50)
    print(f"Strategy:              {strategy_display_name}")
    print(f"Direction:             {strategy_direction}")
    print(f"Symbol:                BTC/USDT")
    print(f"Timeframe:             1H (hourly)")
    print(f"Starting Capital:      ${capital:,.2f}")
    print(f"Risk per Trade:        {risk_percent}% (${risk_per_trade:.2f})")
    print(f"Number of Days:        {num_days}")
    print(f"Trades per Day:        {trades_per_day}")
    print(f"Total Trade Cases:     {total_trades}")
    print(f"Start Date:            {start_date if start_date else 'Recent data'}")
    if breakeven_at_r > 0:
        print(f"Breakeven Stop:        ENABLED (move SL to entry after {breakeven_at_r}R profit)")
    elif use_trailing:
        print(f"Trailing Stop:         ENABLED (activate after {trail_after_r}R profit)")
    else:
        print(f"Stop Loss Type:        FIXED")

    # Print data points used for AI
    print(f"\n{'DATA POINTS FOR AI ANALYSIS':^50}")
    print("-" * 50)
    print("Technical Indicators:")
    print("  - Current Price, SMA 20/50/200, EMA 20")
    print("  - RSI 14, ATR 14, MACD")
    print("  - Trend Direction, Volatility %")
    print("  - Support/Resistance Levels")
    print("ICT Concepts:")
    print(f"  - {('ENABLED' if ICT_AVAILABLE else 'DISABLED')}")
    print("  - FVGs, Order Blocks, Market Structure")
    print("  - Premium/Discount Zones, Liquidity")
    print("ML Models (Ensemble):")
    print(f"  - {('ENABLED' if ML_AVAILABLE else 'DISABLED')}")
    print("  - XGBoost + LightGBM + RandomForest")
    print("  - 24 Features, 12h lookahead prediction")

    print(f"\n{'':^50}")
    print("Fetching historical data from Binance...")
    print("=" * 80)

    symbol = 'BTC/USDT'
    timeframe = '1h'

    # Need: 100 candles for indicators + (24 * num_days) for test period + 48 for outcome checking
    candles_needed = 100 + (24 * num_days) + 48

    # Fetch data - either from specific date or recent
    try:
        if start_date:
            # Convert start_date to timestamp, go back 100 hours for indicator warmup
            from datetime import datetime, timedelta
            start_dt = datetime.strptime(start_date, '%Y-%m-%d') - timedelta(hours=100)
            since = int(start_dt.timestamp() * 1000)

            # Fetch in batches if needed (Binance limit is 1000 per request)
            all_ohlcv = []
            remaining = candles_needed + 100
            current_since = since

            while remaining > 0:
                batch_size = min(remaining, 1000)
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=current_since, limit=batch_size)
                if not ohlcv:
                    break
                all_ohlcv.extend(ohlcv)
                current_since = ohlcv[-1][0] + 3600000  # Move to next hour
                remaining -= len(ohlcv)
                time.sleep(0.2)  # Rate limit

            ohlcv = all_ohlcv
        else:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=min(candles_needed + 100, 1000))

        df_all = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_all['timestamp'] = pd.to_datetime(df_all['timestamp'], unit='ms')
        print(f"Fetched {len(df_all)} candles from {df_all.iloc[0]['timestamp']} to {df_all.iloc[-1]['timestamp']}")
    except Exception as e:
        print(f"Error fetching data: {e}")
        return [], 0, 0

    # Generate test indices: trades_per_day points per day for num_days days
    # Start at index 100 (for indicator history), end 48 candles before end (for outcome checking)
    start_idx = 100
    end_idx = len(df_all) - 48

    # Calculate indices spread across num_days days (24 candles per day)
    test_indices = []
    for day in range(num_days):
        day_start = start_idx + (day * 24)
        if day_start >= end_idx:
            break
        # Spread trades_per_day points across 24 hours
        for trade in range(trades_per_day):
            idx = day_start + int(trade * (24 / trades_per_day))
            if idx < end_idx:
                test_indices.append(idx)

    print(f"Generated {len(test_indices)} test points across {num_days} days")
    print("=" * 80)

    results = []
    total_r = 0
    wins = 0
    losses = 0
    no_trades = 0

    # Print header for detailed output
    print(f"\n{'TRADE LOG':^100}")
    print("=" * 100)
    print(f"{'#':<4} {'Date':<14} {'Entry':>10} {'SL':>10} {'TP':>10} {'Dir':<6} {'Outcome':<6} {'R':>6} {'P/L':>10} {'Cum R':>8}")
    print("-" * 100)

    for case_num, test_idx in enumerate(test_indices):
        test_date = df_all.iloc[test_idx]['timestamp']

        # Get data up to test point for indicator calculation
        df_history = df_all.iloc[:test_idx + 1].copy()

        # Get data after test point for outcome checking (next 48 candles for faster resolution)
        future_end_idx = min(test_idx + 49, len(df_all))
        df_future = df_all.iloc[test_idx + 1:future_end_idx].copy()

        if len(df_future) < 12:
            print(f"{case_num+1:<4} {test_date.strftime('%m-%d %H:%M'):<14} {'---':>10} {'---':>10} {'---':>10} {'SKIP':<6} {'---':<6} {'---':>6} {'---':>10} {total_r:>+7.1f}R")
            continue

        # Calculate technical analysis
        ta_data = get_technical_analysis(df_history)

        # Get ICT analysis
        ict_data = get_ict_analysis(df_history) if ICT_AVAILABLE else None

        # Get ML predictions (only retrain every 10 trades to save time)
        ml_data = None
        if ML_AVAILABLE and case_num % 10 == 0:  # Retrain every 10 trades
            ml_data = get_ml_prediction(df_history)
        elif ML_AVAILABLE and hasattr(run_backtest, '_last_ml_data'):
            # Use cached prediction (model was trained recently)
            ml_data = run_backtest._last_ml_data
        if ml_data:
            run_backtest._last_ml_data = ml_data

        # Get AI recommendation (reduced delay)
        time.sleep(0.5)
        recommendation = get_ai_recommendation(ta_data, test_date.strftime('%Y-%m-%d'), ict_data, ml_data, strategy)

        if recommendation is None:
            print(f"{case_num+1:<4} {test_date.strftime('%m-%d %H:%M'):<14} ${ta_data['current_price']:>9,.0f} {'---':>10} {'---':>10} {'ERR':<6} {'---':<6} {'---':>6} {'---':>10} {total_r:>+7.1f}R")
            no_trades += 1
            continue

        direction = recommendation.get('direction', 'NO_TRADE')

        # Apply strategy direction constraints
        if strategy_direction == 'LONG' and direction == 'SHORT':
            direction = 'NO_TRADE'
        elif strategy_direction == 'SHORT' and direction == 'LONG':
            direction = 'NO_TRADE'

        if direction == 'NO_TRADE':
            no_trades += 1
            print(f"{case_num+1:<4} {test_date.strftime('%m-%d %H:%M'):<14} ${ta_data['current_price']:>9,.0f} {'---':>10} {'---':>10} {'SKIP':<6} {'---':<6} {'---':>6} {'$0.00':>10} {total_r:>+7.1f}R")
            results.append({
                'date': test_date,
                'price': ta_data['current_price'],
                'direction': 'NO_TRADE',
                'outcome': 'N/A',
                'r_multiple': 0,
                'ta_data': ta_data
            })
            continue

        entry = float(recommendation.get('entry', ta_data['current_price']))
        stop_loss = float(recommendation.get('stop_loss', 0))
        take_profit = float(recommendation.get('take_profit', 0))

        # Validate the trade setup
        valid = True
        if direction == 'LONG':
            if stop_loss >= entry or take_profit <= entry:
                valid = False
            else:
                risk = entry - stop_loss
                reward = take_profit - entry
        else:  # SHORT
            if stop_loss <= entry or take_profit >= entry:
                valid = False
            else:
                risk = stop_loss - entry
                reward = entry - take_profit

        if not valid:
            print(f"{case_num+1:<4} {test_date.strftime('%m-%d %H:%M'):<14} ${entry:>9,.0f} ${stop_loss:>9,.0f} ${take_profit:>9,.0f} {direction:<6} {'INVLD':<6} {'---':>6} {'---':>10} {total_r:>+7.1f}R")
            continue

        # Check outcome
        outcome, r_multiple, bars = check_trade_outcome(df_future, entry, stop_loss, take_profit, direction, use_trailing, trail_after_r, breakeven_at_r)

        total_r += r_multiple
        pnl_dollars = r_multiple * risk_per_trade  # Calculate dollar P/L

        if outcome == 'TP_HIT':
            wins += 1
            outcome_str = 'WIN'
            r_str = f"+{r_multiple:.1f}R"
        elif outcome == 'BE':
            outcome_str = 'BE'
            r_str = "0R"
        elif outcome == 'SL_HIT':
            losses += 1
            outcome_str = 'LOSS'
            r_str = f"{r_multiple:.1f}R"
        else:
            outcome_str = 'OPEN'
            r_str = f"{r_multiple:+.1f}R"

        pnl_str = f"${pnl_dollars:+.2f}" if pnl_dollars != 0 else "$0.00"
        print(f"{case_num+1:<4} {test_date.strftime('%m-%d %H:%M'):<14} ${entry:>9,.0f} ${stop_loss:>9,.0f} ${take_profit:>9,.0f} {direction:<6} {outcome_str:<6} {r_str:>6} {pnl_str:>10} {total_r:>+7.1f}R")

        results.append({
            'date': test_date,
            'price': ta_data['current_price'],
            'direction': direction,
            'entry': entry,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'outcome': outcome,
            'r_multiple': r_multiple,
            'pnl_dollars': pnl_dollars,
            'bars_to_outcome': bars,
            'ta_data': ta_data  # Include all technical data
        })

    # Summary
    print("\n" + "=" * 80)
    print("BACKTEST SUMMARY")
    print("=" * 80)

    trades = wins + losses
    if trades > 0:
        win_rate = wins / trades * 100

        # Calculate additional stats
        long_trades = [r for r in results if r.get('direction') == 'LONG' and r.get('outcome') in ['TP_HIT', 'SL_HIT']]
        short_trades = [r for r in results if r.get('direction') == 'SHORT' and r.get('outcome') in ['TP_HIT', 'SL_HIT']]
        long_wins = len([r for r in long_trades if r.get('outcome') == 'TP_HIT'])
        short_wins = len([r for r in short_trades if r.get('outcome') == 'TP_HIT'])

        # Max drawdown calculation
        cumulative = 0
        peak = 0
        max_dd = 0
        for r in results:
            if r.get('outcome') in ['TP_HIT', 'SL_HIT']:
                cumulative += r['r_multiple']
                if cumulative > peak:
                    peak = cumulative
                dd = peak - cumulative
                if dd > max_dd:
                    max_dd = dd

        print(f"\n{'OVERALL PERFORMANCE':^40}")
        print("-" * 40)
        print(f"Total Cases Tested:    {len(test_indices)}")
        print(f"Trades Executed:       {trades}")
        print(f"Trades Skipped:        {no_trades}")
        print(f"Wins:                  {wins}")
        print(f"Losses:                {losses}")
        print(f"Win Rate:              {win_rate:.1f}%")
        print(f"Total R-Multiple:      {total_r:+.2f}R")
        print(f"Average R per Trade:   {total_r/trades:+.2f}R")
        print(f"Max Drawdown:          {max_dd:.1f}R")

        print(f"\n{'BY DIRECTION':^40}")
        print("-" * 40)
        if long_trades:
            print(f"LONG:  {len(long_trades)} trades, {long_wins} wins ({100*long_wins/len(long_trades):.0f}%)")
        if short_trades:
            print(f"SHORT: {len(short_trades)} trades, {short_wins} wins ({100*short_wins/len(short_trades):.0f}%)")

        # Capital-based P/L
        total_pnl = total_r * risk_per_trade
        final_capital = capital + total_pnl
        roi = (total_pnl / capital) * 100

        print(f"\n{'CAPITAL PERFORMANCE':^40}")
        print("-" * 40)
        print(f"Starting Capital:      ${capital:,.2f}")
        print(f"Risk per Trade (1R):   ${risk_per_trade:.2f} ({risk_percent}%)")
        print(f"Total P/L:             ${total_pnl:+,.2f}")
        print(f"Final Capital:         ${final_capital:,.2f}")
        print(f"ROI:                   {roi:+.1f}%")

        # Drawdown in dollars
        max_dd_dollars = max_dd * risk_per_trade
        print(f"Max Drawdown:          ${max_dd_dollars:,.2f} ({max_dd:.1f}R)")

        # Breakeven analysis
        breakeven_wr = 100 / (1 + 3)  # For 1:3 R:R
        print(f"\n{'ANALYSIS':^40}")
        print("-" * 40)
        print(f"Break-even Win Rate (1:3 R:R): {breakeven_wr:.1f}%")
        print(f"Your Win Rate: {win_rate:.1f}% ({'+' if win_rate > breakeven_wr else ''}{win_rate - breakeven_wr:.1f}% vs breakeven)")

        # Monthly projection
        if num_days > 0:
            daily_r = total_r / num_days
            monthly_r = daily_r * 30
            monthly_pnl = monthly_r * risk_per_trade
            print(f"\n{'PROJECTIONS (30 days)':^40}")
            print("-" * 40)
            print(f"Avg Daily R:           {daily_r:+.2f}R")
            print(f"Projected Monthly R:   {monthly_r:+.1f}R")
            print(f"Projected Monthly P/L: ${monthly_pnl:+,.2f}")

    else:
        print("No valid trades to analyze")

    print("\n" + "=" * 100)

    # Print detailed trade breakdown (first 10 trades with full technical data)
    executed_trades = [r for r in results if r.get('direction') in ['LONG', 'SHORT'] and r.get('outcome') in ['TP_HIT', 'SL_HIT', 'BE']]
    if executed_trades:
        print(f"\n{'DETAILED TRADE BREAKDOWN (First 10 executed trades)':^100}")
        print("=" * 100)
        for i, trade in enumerate(executed_trades[:10]):
            ta = trade.get('ta_data', {})
            print(f"\n--- Trade #{i+1} ---")
            print(f"Date:           {trade['date']}")
            print(f"Direction:      {trade['direction']}")
            print(f"Entry:          ${trade['entry']:,.2f}")
            print(f"Stop Loss:      ${trade['stop_loss']:,.2f}")
            print(f"Take Profit:    ${trade['take_profit']:,.2f}")
            print(f"Risk (SL dist): ${abs(trade['entry'] - trade['stop_loss']):,.2f}")
            print(f"Outcome:        {trade['outcome']}")
            print(f"R-Multiple:     {trade['r_multiple']:+.2f}R")
            print(f"P/L:            ${trade.get('pnl_dollars', 0):+.2f}")
            print(f"Bars to Exit:   {trade.get('bars_to_outcome', 'N/A')}")
            if ta:
                print(f"\nTechnical Data Used:")
                print(f"  Price:        ${ta.get('current_price', 0):,.2f}")
                print(f"  Overall:      {ta.get('overall_signal', 'N/A')}")
                print(f"  RSI (14):     {ta.get('rsi', 0):.2f}")
                print(f"  ATR (14):     ${ta.get('atr', 0):,.2f}")
                print(f"  SMA 20:       ${ta.get('sma_20', 0):,.2f}" if ta.get('sma_20') else "  SMA 20:       N/A")
                print(f"  SMA 50:       ${ta.get('sma_50', 0):,.2f}" if ta.get('sma_50') else "  SMA 50:       N/A")
                print(f"  Support 1:    ${ta.get('support_1', 0):,.2f}")
                print(f"  Resistance 1: ${ta.get('resistance_1', 0):,.2f}")
                print(f"  Buy Signals:  {ta.get('buy_signals', 0)}")
                print(f"  Sell Signals: {ta.get('sell_signals', 0)}")

    print("\n" + "=" * 100)
    return results, total_r, risk_per_trade

if __name__ == "__main__":
    import sys

    # Check for --list-strategies flag
    if len(sys.argv) > 1 and sys.argv[1] == '--list-strategies':
        print("\nAvailable Strategies:")
        print("-" * 60)
        for key, name, desc in list_strategies():
            print(f"  {key:<20} - {name}")
            print(f"  {'':20}   {desc}")
            print()
        sys.exit(0)

    # Default parameters - can be overridden via command line
    # Usage: python backtest_ai.py [strategy] [num_days] [trades_per_day] [capital] [risk_percent] [start_date]
    # Example: python backtest_ai.py mean_reversion 10 3 2000 0.5 2025-10-01
    strategy_name = sys.argv[1] if len(sys.argv) > 1 else 'trend_follower'
    num_days = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    trades_per_day = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    capital = float(sys.argv[4]) if len(sys.argv) > 4 else 2000
    risk_percent = float(sys.argv[5]) if len(sys.argv) > 5 else 0.5
    start_date = sys.argv[6] if len(sys.argv) > 6 else None
    use_trailing = bool(int(sys.argv[7])) if len(sys.argv) > 7 else False
    trail_after_r = float(sys.argv[8]) if len(sys.argv) > 8 else 1.0
    breakeven_at_r = float(sys.argv[9]) if len(sys.argv) > 9 else 0

    results, total_r, risk_per_trade = run_backtest(
        num_days=num_days,
        trades_per_day=trades_per_day,
        capital=capital,
        risk_percent=risk_percent,
        start_date=start_date,
        use_trailing=use_trailing,
        trail_after_r=trail_after_r,
        breakeven_at_r=breakeven_at_r,
        strategy_name=strategy_name
    )
