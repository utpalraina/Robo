#!/usr/bin/env python3
"""Compare multiple trading strategies on the same period"""

import subprocess
import re
import sys

strategies = [
    'trend_follower',
    'mean_reversion',
    'ict_smart_money',
    'breakout_trader',
    'aggressive_reversal'
]

# Parse command line args
days = int(sys.argv[1]) if len(sys.argv) > 1 else 10
trades_per_day = int(sys.argv[2]) if len(sys.argv) > 2 else 3
start_date = sys.argv[3] if len(sys.argv) > 3 else '2025-10-01'

print("=" * 80)
print(f"STRATEGY COMPARISON - {days} days starting {start_date}")
print("=" * 80)
print()

results = []

for strategy in strategies:
    print(f"Running: {strategy}...", end=" ", flush=True)

    cmd = f"python backtest_ai.py {strategy} {days} {trades_per_day} 2000 0.5 {start_date}"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    output = result.stdout + result.stderr

    # Extract metrics
    trades = re.search(r'Trades Executed:\s+(\d+)', output)
    wins = re.search(r'^Wins:\s+(\d+)', output, re.MULTILINE)
    losses = re.search(r'^Losses:\s+(\d+)', output, re.MULTILINE)
    winrate = re.search(r'Win Rate:\s+([\d.]+)%', output)
    total_r = re.search(r'Total R-Multiple:\s+([\+\-]?[\d.]+)R', output)
    roi = re.search(r'^ROI:\s+([\+\-]?[\d.]+)%', output, re.MULTILINE)

    data = {
        'strategy': strategy,
        'trades': int(trades.group(1)) if trades else 0,
        'wins': int(wins.group(1)) if wins else 0,
        'losses': int(losses.group(1)) if losses else 0,
        'winrate': float(winrate.group(1)) if winrate else 0,
        'total_r': float(total_r.group(1)) if total_r else 0,
        'roi': float(roi.group(1)) if roi else 0
    }
    results.append(data)
    print(f"Done ({data['trades']} trades, {data['total_r']:+.1f}R)")

print()
print("=" * 80)
print(f"{'Strategy':<20} {'Trades':>8} {'Wins':>6} {'Losses':>7} {'WinRate':>10} {'Total R':>10} {'ROI':>8}")
print("-" * 80)

# Sort by total_r descending
results.sort(key=lambda x: x['total_r'], reverse=True)

for r in results:
    print(f"{r['strategy']:<20} {r['trades']:>8} {r['wins']:>6} {r['losses']:>7} {r['winrate']:>9.1f}% {r['total_r']:>+9.1f}R {r['roi']:>+7.1f}%")

print("-" * 80)
print()
print("Best Strategy:", results[0]['strategy'], f"({results[0]['total_r']:+.1f}R)")
print("Worst Strategy:", results[-1]['strategy'], f"({results[-1]['total_r']:+.1f}R)")
print()
