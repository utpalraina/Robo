#!/usr/bin/env python3
"""
Strategies MCP Server - Expose trading strategies for AI assistants.

This MCP server provides tools to:
1. List all available trading strategies
2. Get detailed information about each strategy
3. Understand strategy rules and parameters
4. Compare strategies
5. Get strategy recommendations based on market conditions

Usage:
    Run as MCP server: python strategies-mcp-server.py
    Or use the functions directly in code.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from fastmcp import FastMCP
    HAS_FASTMCP = True
except ImportError:
    HAS_FASTMCP = False
    print("FastMCP not installed - running in standalone mode")


# ============================================================
# STRATEGY DATA
# ============================================================

def load_strategies_json() -> Dict:
    """Load strategies from JSON file."""
    json_path = Path(__file__).parent / "strategies.json"
    if json_path.exists():
        with open(json_path) as f:
            return json.load(f)
    return {"strategies": {}}


def get_strategy_files_info() -> Dict[str, Dict]:
    """Get information about Python strategy files."""
    strategy_dir = Path(__file__).parent / "strategy"

    strategies_info = {
        "ml_strategy": {
            "file": "strategy/ml_strategy.py",
            "name": "ML Strategy",
            "type": "Machine Learning",
            "description": "XGBoost-based prediction strategy using 79 technical features",
            "features": [
                "RSI, MACD, Bollinger Bands, EMA, ATR",
                "Volume analysis",
                "Price momentum and volatility",
                "Multi-timeframe features"
            ],
            "signals": ["BUY", "SELL", "HOLD"],
            "risk_management": {
                "stop_loss": "2% default",
                "take_profit": "4% default",
                "position_sizing": "Based on risk per trade"
            }
        },

        "scalping": {
            "file": "strategy/scalping.py",
            "name": "Confluence Scalping Strategy",
            "type": "Scalping / High Frequency",
            "description": "Makes decisions based on MAXIMUM CONFLUENCE of all signals",
            "confluence_sources": [
                "ICT Strategy (FVG, MSS, OB, OTE, Liquidity)",
                "SMT Divergence (BTC vs ETH correlation)",
                "Multi-Timeframe Analysis (1m, 5m, 15m)",
                "ML Model Predictions",
                "Technical Indicators (RSI, MACD, BB)"
            ],
            "trading_modes": {
                "safe": {
                    "min_confluence": 18,
                    "min_confidence": "55%",
                    "take_profit": "0.2%",
                    "stop_loss": "0.1%",
                    "max_trades_per_hour": 5
                },
                "medium": {
                    "min_confluence": 12,
                    "min_confidence": "40%",
                    "take_profit": "0.15%",
                    "stop_loss": "0.1%",
                    "max_trades_per_hour": 10
                },
                "fast": {
                    "min_confluence": 8,
                    "min_confidence": "30%",
                    "take_profit": "0.1%",
                    "stop_loss": "0.08%",
                    "max_trades_per_hour": 20
                }
            },
            "signals": ["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]
        },

        "ict_strategy": {
            "file": "strategy/ict_strategy.py",
            "name": "ICT Smart Money Strategy",
            "type": "Institutional / Smart Money",
            "description": "Based on Inner Circle Trader concepts - trade like institutions",
            "concepts": [
                "Fair Value Gaps (FVG) - Imbalances in price",
                "Market Structure Shifts (MSS) - Trend changes",
                "Order Blocks (OB) - Institutional entry zones",
                "Optimal Trade Entry (OTE) - Fibonacci 62-79% retracement",
                "Premium/Discount Zones - Above/below 50% range",
                "Liquidity Zones - Stop hunt targets"
            ],
            "trading_sessions": {
                "asia": "7 PM - 4 AM EST",
                "london": "3 AM - 12 PM EST",
                "ny_am": "8:30 AM - 12 PM EST (Optimal)",
                "ny_pm": "1:30 PM - 4 PM EST",
                "silver_bullet_am": "10 AM - 11 AM EST",
                "silver_bullet_pm": "2 PM - 3 PM EST"
            },
            "confluence_scoring": {
                "min_score": 8,
                "strong_score": 12,
                "min_risk_reward": "3:1"
            },
            "signals": ["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]
        },

        "confluence": {
            "file": "strategy/confluence.py",
            "name": "Confluence Detector",
            "type": "Signal Aggregator",
            "description": "Combines multiple signal sources into a unified confluence score",
            "signal_sources": [
                "ICT Indicators",
                "SMT Divergence",
                "Multi-Timeframe Trends",
                "Technical Momentum",
                "ML Predictions"
            ],
            "output": "Confluence score (0-30) with strength rating"
        },

        "daily_bias": {
            "file": "strategy/daily_bias.py",
            "name": "Daily Bias Strategy",
            "type": "Swing / Position",
            "description": "Determines daily directional bias for longer-term trades",
            "factors": [
                "Higher timeframe trend",
                "Key support/resistance levels",
                "Previous day high/low",
                "Weekly open"
            ]
        },

        "silver_bullet": {
            "file": "strategy/silver_bullet.py",
            "name": "ICT Silver Bullet Strategy",
            "type": "Time-Based Scalping",
            "description": "Specific time-window strategy for high-probability setups",
            "time_windows": [
                "10:00 AM - 11:00 AM EST (Morning)",
                "2:00 PM - 3:00 PM EST (Afternoon)"
            ],
            "key_concepts": [
                "FVG during silver bullet window",
                "Displacement into FVG",
                "Market structure alignment"
            ]
        }
    }

    return strategies_info


def get_all_strategies() -> Dict:
    """Get all strategies (JSON + Python files)."""
    json_strategies = load_strategies_json().get("strategies", {})
    file_strategies = get_strategy_files_info()

    return {
        "rule_based_strategies": json_strategies,
        "implemented_strategies": file_strategies
    }


# ============================================================
# STRATEGY FUNCTIONS (Can be used standalone or via MCP)
# ============================================================

def list_strategies() -> Dict:
    """
    List all available trading strategies.

    Returns a summary of all strategies in the system.
    """
    all_strats = get_all_strategies()

    result = {
        "rule_based": [],
        "implemented": [],
        "total_count": 0
    }

    # Rule-based strategies from JSON
    for key, strat in all_strats["rule_based_strategies"].items():
        result["rule_based"].append({
            "id": key,
            "name": strat.get("name", key),
            "description": strat.get("description", ""),
            "direction": strat.get("direction", "BOTH")
        })

    # Implemented strategies from Python files
    for key, strat in all_strats["implemented_strategies"].items():
        result["implemented"].append({
            "id": key,
            "name": strat.get("name", key),
            "type": strat.get("type", ""),
            "description": strat.get("description", ""),
            "file": strat.get("file", "")
        })

    result["total_count"] = len(result["rule_based"]) + len(result["implemented"])

    return result


def get_strategy_details(strategy_id: str) -> Dict:
    """
    Get detailed information about a specific strategy.

    Args:
        strategy_id: The strategy identifier (e.g., 'scalping', 'ict_smart_money')

    Returns:
        Full strategy details including rules, parameters, and usage.
    """
    all_strats = get_all_strategies()

    # Check rule-based strategies
    if strategy_id in all_strats["rule_based_strategies"]:
        strat = all_strats["rule_based_strategies"][strategy_id]
        return {
            "type": "rule_based",
            "id": strategy_id,
            "name": strat.get("name"),
            "description": strat.get("description"),
            "direction": strat.get("direction"),
            "rules": strat.get("rules"),
            "usage": "Used by AI advisor to generate trading recommendations"
        }

    # Check implemented strategies
    if strategy_id in all_strats["implemented_strategies"]:
        strat = all_strats["implemented_strategies"][strategy_id]
        return {
            "type": "implemented",
            "id": strategy_id,
            **strat,
            "usage": f"Import from {strat.get('file', 'strategy/')}"
        }

    return {"error": f"Strategy '{strategy_id}' not found"}


def get_strategy_rules(strategy_id: str) -> str:
    """
    Get the trading rules for a rule-based strategy.

    Args:
        strategy_id: The strategy identifier

    Returns:
        The full rules text for the strategy.
    """
    all_strats = get_all_strategies()

    if strategy_id in all_strats["rule_based_strategies"]:
        strat = all_strats["rule_based_strategies"][strategy_id]
        return strat.get("rules", "No rules defined")

    return f"Strategy '{strategy_id}' is not a rule-based strategy or not found"


def compare_strategies(strategy_ids: List[str]) -> Dict:
    """
    Compare multiple strategies side by side.

    Args:
        strategy_ids: List of strategy IDs to compare

    Returns:
        Comparison table of strategies.
    """
    all_strats = get_all_strategies()
    comparison = {"strategies": []}

    for sid in strategy_ids:
        details = get_strategy_details(sid)
        if "error" not in details:
            comparison["strategies"].append({
                "id": sid,
                "name": details.get("name", sid),
                "type": details.get("type", ""),
                "description": details.get("description", "")[:100] + "..."
            })

    return comparison


def recommend_strategy(market_condition: str) -> Dict:
    """
    Recommend a strategy based on market conditions.

    Args:
        market_condition: Description of current market (e.g., 'trending', 'ranging', 'volatile')

    Returns:
        Strategy recommendation with reasoning.
    """
    recommendations = {
        "trending": {
            "primary": "trend_follower",
            "alternative": "ict_strategy",
            "reason": "Trend following strategies work best in directional markets"
        },
        "ranging": {
            "primary": "mean_reversion",
            "alternative": "scalping",
            "reason": "Mean reversion and scalping work well in sideways markets"
        },
        "volatile": {
            "primary": "scalping",
            "alternative": "breakout_trader",
            "reason": "Scalping can capture quick moves; breakouts work when volatility leads to range breaks"
        },
        "low_volatility": {
            "primary": "conservative_swing",
            "alternative": "mean_reversion",
            "reason": "Low volatility favors patient, high-probability setups"
        },
        "reversal": {
            "primary": "aggressive_reversal",
            "alternative": "ict_strategy",
            "reason": "ICT concepts help identify reversal points through liquidity sweeps"
        }
    }

    condition_lower = market_condition.lower()

    for key, rec in recommendations.items():
        if key in condition_lower:
            return {
                "market_condition": market_condition,
                "recommendation": rec,
                "strategies_details": {
                    "primary": get_strategy_details(rec["primary"]),
                    "alternative": get_strategy_details(rec["alternative"])
                }
            }

    return {
        "market_condition": market_condition,
        "recommendation": {
            "primary": "confluence",
            "reason": "When market condition is unclear, use confluence-based approach"
        },
        "available_conditions": list(recommendations.keys())
    }


def get_ict_concepts() -> Dict:
    """
    Get explanation of all ICT (Inner Circle Trader) concepts used in strategies.

    Returns:
        Dictionary explaining each ICT concept.
    """
    return {
        "concepts": {
            "FVG (Fair Value Gap)": {
                "description": "A 3-candle pattern where middle candle's body doesn't overlap with wicks of surrounding candles",
                "bullish": "Gap between candle 1 high and candle 3 low (price likely to fill gap going up)",
                "bearish": "Gap between candle 1 low and candle 3 high (price likely to fill gap going down)",
                "usage": "Enter trades when price returns to fill the gap"
            },
            "MSS (Market Structure Shift)": {
                "description": "Break of a significant swing high/low indicating trend change",
                "bullish": "Break above a lower high in a downtrend",
                "bearish": "Break below a higher low in an uptrend",
                "usage": "Confirms trend reversal, trade in new direction"
            },
            "Order Block (OB)": {
                "description": "The last opposing candle before a strong move - institutional entry zone",
                "bullish": "Last bearish candle before strong bullish move",
                "bearish": "Last bullish candle before strong bearish move",
                "usage": "Enter when price returns to order block zone"
            },
            "OTE (Optimal Trade Entry)": {
                "description": "Fibonacci retracement zone between 62% and 79%",
                "usage": "Best risk:reward entries during pullbacks",
                "levels": ["0.62 (62%)", "0.705 (70.5%)", "0.79 (79%)"]
            },
            "Premium/Discount Zones": {
                "description": "Market divided at 50% of range",
                "premium": "Above 50% - expensive, look for sells",
                "discount": "Below 50% - cheap, look for buys",
                "usage": "Buy in discount, sell in premium"
            },
            "Liquidity": {
                "description": "Clusters of stop losses at obvious levels (highs/lows)",
                "buy_side": "Above recent highs (stop losses of shorts)",
                "sell_side": "Below recent lows (stop losses of longs)",
                "usage": "Price often sweeps liquidity before reversing"
            },
            "Displacement": {
                "description": "Strong, impulsive price move that creates FVG",
                "characteristics": "Large candles with minimal wicks",
                "usage": "Confirms institutional activity and direction"
            },
            "Silver Bullet": {
                "description": "Specific 1-hour windows with high-probability setups",
                "am_window": "10:00 AM - 11:00 AM EST",
                "pm_window": "2:00 PM - 3:00 PM EST",
                "usage": "Focus trading during these windows for best results"
            }
        },
        "trading_sessions": {
            "Asia": "7 PM - 4 AM EST (accumulation, low volatility)",
            "London": "3 AM - 12 PM EST (manipulation, direction established)",
            "New York AM": "8:30 AM - 12 PM EST (distribution, best moves)",
            "New York PM": "1:30 PM - 4 PM EST (continuation or reversal)"
        }
    }


def get_confluence_explanation() -> Dict:
    """
    Explain how confluence scoring works in the scalping strategy.

    Returns:
        Detailed explanation of confluence system.
    """
    return {
        "what_is_confluence": "Multiple independent signals agreeing on direction",
        "why_it_matters": "More confluence = higher probability of success",

        "signal_sources": {
            "ict_signals": {
                "weight": "Up to 10 points",
                "includes": ["FVG", "Order Block", "OTE Zone", "Market Structure", "Liquidity"]
            },
            "smt_divergence": {
                "weight": "Up to 6 points",
                "includes": ["BTC vs ETH divergence", "Correlation breaks"]
            },
            "multi_timeframe": {
                "weight": "Up to 6 points",
                "includes": ["1m trend", "5m trend", "15m trend alignment"]
            },
            "technical": {
                "weight": "Up to 4 points",
                "includes": ["RSI", "MACD", "Bollinger Bands"]
            },
            "ml_prediction": {
                "weight": "Up to 4 points",
                "includes": ["XGBoost model confidence"]
            }
        },

        "total_possible_score": 30,

        "score_interpretation": {
            "0-7": "No trade - insufficient confluence",
            "8-11": "Weak signal - only for aggressive mode",
            "12-17": "Moderate signal - good for medium mode",
            "18-22": "Strong signal - good for safe mode",
            "23-30": "Very strong signal - high confidence trade"
        },

        "trading_modes": {
            "safe": "Requires 18+ confluence, 55%+ confidence",
            "medium": "Requires 12+ confluence, 40%+ confidence",
            "fast": "Requires 8+ confluence, 30%+ confidence"
        }
    }


# ============================================================
# MCP SERVER SETUP
# ============================================================

if HAS_FASTMCP:
    mcp = FastMCP("Trading Strategies MCP")

    @mcp.tool
    def mcp_list_strategies() -> Dict:
        """List all available trading strategies in the system."""
        return list_strategies()

    @mcp.tool
    def mcp_get_strategy(strategy_id: str) -> Dict:
        """
        Get detailed information about a specific strategy.

        Args:
            strategy_id: Strategy ID (e.g., 'scalping', 'ict_strategy', 'trend_follower')
        """
        return get_strategy_details(strategy_id)

    @mcp.tool
    def mcp_get_rules(strategy_id: str) -> str:
        """
        Get the trading rules for a rule-based strategy.

        Args:
            strategy_id: Strategy ID (e.g., 'trend_follower', 'mean_reversion')
        """
        return get_strategy_rules(strategy_id)

    @mcp.tool
    def mcp_compare_strategies(strategies: str) -> Dict:
        """
        Compare multiple strategies side by side.

        Args:
            strategies: Comma-separated strategy IDs (e.g., 'scalping,ict_strategy')
        """
        strategy_list = [s.strip() for s in strategies.split(",")]
        return compare_strategies(strategy_list)

    @mcp.tool
    def mcp_recommend_strategy(market_condition: str) -> Dict:
        """
        Get strategy recommendation based on market conditions.

        Args:
            market_condition: Current market state (trending, ranging, volatile, reversal)
        """
        return recommend_strategy(market_condition)

    @mcp.tool
    def mcp_explain_ict() -> Dict:
        """Get explanation of all ICT (Inner Circle Trader) concepts."""
        return get_ict_concepts()

    @mcp.tool
    def mcp_explain_confluence() -> Dict:
        """Explain how the confluence scoring system works."""
        return get_confluence_explanation()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    if HAS_FASTMCP and len(sys.argv) > 1 and sys.argv[1] == "--serve":
        # Run as MCP server
        mcp.run()
    else:
        # Standalone demo
        print("=" * 60)
        print("TRADING STRATEGIES OVERVIEW")
        print("=" * 60)

        strategies = list_strategies()

        print(f"\nTotal Strategies: {strategies['total_count']}")

        print("\n--- Rule-Based Strategies (from strategies.json) ---")
        for s in strategies["rule_based"]:
            print(f"  • {s['name']} ({s['id']})")
            print(f"    {s['description'][:60]}...")

        print("\n--- Implemented Strategies (Python files) ---")
        for s in strategies["implemented"]:
            print(f"  • {s['name']} ({s['id']})")
            print(f"    Type: {s['type']}")
            print(f"    {s['description'][:60]}...")

        print("\n--- ICT Concepts ---")
        ict = get_ict_concepts()
        for concept in list(ict["concepts"].keys())[:4]:
            print(f"  • {concept}")

        print("\n--- Confluence System ---")
        conf = get_confluence_explanation()
        print(f"  Total possible score: {conf['total_possible_score']}")
        print(f"  Signal sources: {len(conf['signal_sources'])}")

        print("\n" + "=" * 60)
        print("To run as MCP server: python strategies-mcp-server.py --serve")
        print("=" * 60)
