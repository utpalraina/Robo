# CLI Reference

Complete command-line interface reference for Robo Trader.

---

## Overview

```bash
python main.py [COMMAND] [OPTIONS]
```

### Available Commands

| Command | Description |
|---------|-------------|
| `train` | Train the ML model on historical data |
| `backtest` | Run backtest on historical data |
| `paper` | Start paper trading simulation |
| `live` | Start live trading (real money) |
| `status` | Show trading status and recent trades |
| `fetch-data` | Fetch and store historical data |
| `validate` | Cross-validate the model |
| `web` | Launch the web dashboard |

---

## Command Details

### train

Train the ML model on historical data.

```bash
python main.py train [OPTIONS]
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--symbol` | BTC/USDT | Trading pair to train on |
| `--start-date` | 2024-01-01 | Training start date |
| `--end-date` | 2024-11-01 | Training end date |
| `--config-path` | config/config.yaml | Path to config file |
| `--output-path` | models/trained_model.joblib | Path to save model |

**Examples:**
```bash
# Train with defaults
python main.py train

# Train on ETH/USDT
python main.py train --symbol ETH/USDT

# Train with custom date range
python main.py train --start-date 2023-01-01 --end-date 2024-01-01

# Train with custom output
python main.py train --output-path models/btc_model.joblib
```

**Output:**
```
╭─────────────────────────────────────╮
│        Training ML Model            │
╰─────────────────────────────────────╯
Fetched 8760 candles
Generated 85 features
Training samples: 8500

┏━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Metric       ┃ Value    ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ accuracy     │ 0.5823   │
│ precision    │ 0.5912   │
│ recall       │ 0.5734   │
│ f1_score     │ 0.5821   │
└──────────────┴──────────┘

Model saved to models/trained_model.joblib
```

---

### backtest

Run backtest on historical data.

```bash
python main.py backtest [OPTIONS]
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--symbol` | BTC/USDT | Trading pair |
| `--start-date` | 2024-01-01 | Backtest start date |
| `--end-date` | 2024-11-01 | Backtest end date |
| `--config-path` | config/config.yaml | Path to config file |
| `--model-path` | models/trained_model.joblib | Path to trained model |
| `--plot/--no-plot` | --plot | Generate result plots |

**Examples:**
```bash
# Backtest with defaults
python main.py backtest

# Backtest different symbol
python main.py backtest --symbol ETH/USDT

# Backtest without plots
python main.py backtest --no-plot

# Backtest specific period
python main.py backtest --start-date 2024-06-01 --end-date 2024-12-01
```

**Output:**
```
╭─────────────────────────────────────╮
│          Running Backtest           │
╰─────────────────────────────────────╯

================================================================================
                           BACKTEST REPORT
================================================================================

PERFORMANCE METRICS
-------------------
Total Return:            12.45%
Sharpe Ratio:             1.23
Max Drawdown:            -8.34%
Profit Factor:            1.45

TRADE STATISTICS
----------------
Total Trades:               156
Winning Trades:              89
Losing Trades:               67
Win Rate:                57.05%
Average Win:             $45.23
Average Loss:           -$32.15
================================================================================
```

---

### paper

Start paper trading simulation with fake money.

```bash
python main.py paper [OPTIONS]
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--symbols` | BTC/USDT,ETH/USDT | Comma-separated trading pairs |
| `--config-path` | config/config.yaml | Path to config file |
| `--model-path` | models/trained_model.joblib | Path to trained model |
| `--interval` | 60 | Trading interval in seconds |

**Examples:**
```bash
# Paper trade with defaults
python main.py paper

# Paper trade single symbol
python main.py paper --symbols BTC/USDT

# Paper trade multiple symbols
python main.py paper --symbols "BTC/USDT,ETH/USDT,SOL/USDT"

# Faster interval (30 seconds)
python main.py paper --interval 30
```

**Output:**
```
╭─────────────────────────────────────╮
│       Starting Paper Trading        │
╰─────────────────────────────────────╯

Paper trading uses simulated funds - no real money at risk

Trading symbols: ['BTC/USDT', 'ETH/USDT']
Interval: 60 seconds

Press Ctrl+C to stop

[12:00:01] Signal for BTC/USDT: BUY (confidence: 0.72)
[12:00:01] PAPER BUY: 0.001234 BTC/USDT @ $45,234.56
[12:01:01] Account: Cash=$9,500.00, Equity=$9,556.78, PnL=$56.78
```

---

### live

Start live trading with real money.

```bash
python main.py live [OPTIONS]
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--symbols` | BTC/USDT | Comma-separated trading pairs |
| `--config-path` | config/config.yaml | Path to config file |
| `--model-path` | models/trained_model.joblib | Path to trained model |
| `--interval` | 60 | Trading interval in seconds |
| `--confirm` | Required | Confirm live trading |

**Examples:**
```bash
# Live trading (requires --confirm flag)
python main.py live --confirm

# Live trade specific symbol
python main.py live --symbols BTC/USDT --confirm

# Live trade with custom interval
python main.py live --symbols BTC/USDT --interval 120 --confirm
```

**Warning:**
```
╭─────────────────────────────────────╮
│   WARNING: LIVE TRADING MODE        │
│                                     │
│   This will trade with REAL MONEY.  │
│   Use --confirm flag to proceed.    │
╰─────────────────────────────────────╯
```

---

### status

Show current trading status and recent trades.

```bash
python main.py status [OPTIONS]
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--config-path` | config/config.yaml | Path to config file |

**Example:**
```bash
python main.py status
```

**Output:**
```
                    Recent Trades
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━┓
┃ Time                ┃ Symbol    ┃ Side  ┃ Price       ┃ Amount     ┃ Type  ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━┩
│ 2024-12-10 12:00:00 │ BTC/USDT  │ BUY   │ $45,234.56  │ 0.001234   │ Paper │
│ 2024-12-10 11:30:00 │ BTC/USDT  │ SELL  │ $45,456.78  │ 0.001234   │ Paper │
│ 2024-12-10 10:00:00 │ ETH/USDT  │ BUY   │ $2,345.67   │ 0.123456   │ Paper │
└─────────────────────┴───────────┴───────┴─────────────┴────────────┴───────┘
```

---

### fetch-data

Fetch and store historical data.

```bash
python main.py fetch-data [OPTIONS]
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--symbol` | BTC/USDT | Trading pair |
| `--start-date` | 2024-01-01 | Start date |
| `--end-date` | 2024-12-01 | End date |
| `--config-path` | config/config.yaml | Path to config file |

**Examples:**
```bash
# Fetch BTC/USDT data
python main.py fetch-data

# Fetch ETH/USDT data
python main.py fetch-data --symbol ETH/USDT

# Fetch specific date range
python main.py fetch-data --start-date 2023-01-01 --end-date 2024-01-01
```

**Output:**
```
╭─────────────────────────────────────╮
│      Fetching Historical Data       │
╰─────────────────────────────────────╯

Fetching BTC/USDT data...
Saved 8760 candles for BTC/USDT
```

---

### validate

Cross-validate the model.

```bash
python main.py validate [OPTIONS]
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--symbol` | BTC/USDT | Trading pair |
| `--start-date` | 2024-01-01 | Start date |
| `--end-date` | 2024-11-01 | End date |
| `--config-path` | config/config.yaml | Path to config file |
| `--folds` | 5 | Number of CV folds |

**Examples:**
```bash
# Validate with defaults
python main.py validate

# Validate with more folds
python main.py validate --folds 10
```

**Output:**
```
╭─────────────────────────────────────╮
│       Cross-Validating Model        │
╰─────────────────────────────────────╯

     Cross-Validation Results (5 folds)
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Metric             ┃ Value    ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ mean_accuracy      │ 0.5678   │
│ std_accuracy       │ 0.0234   │
│ mean_precision     │ 0.5723   │
│ mean_f1            │ 0.5645   │
└────────────────────┴──────────┘
```

---

### web

Launch the web dashboard.

```bash
python main.py web [OPTIONS]
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--host` | 0.0.0.0 | Host to bind to |
| `--port` | 8000 | Port to run on |

**Examples:**
```bash
# Start with defaults
python main.py web

# Custom port
python main.py web --port 3000

# Localhost only
python main.py web --host 127.0.0.1

# Custom host and port
python main.py web --host 0.0.0.0 --port 8080
```

**Output:**
```
╭─────────────────────────────────────╮
│      Launching Web Dashboard        │
╰─────────────────────────────────────╯

Open your browser at: http://localhost:8000

INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Global Options

### Help

Get help for any command:

```bash
# General help
python main.py --help

# Command-specific help
python main.py train --help
python main.py backtest --help
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error / Failure |
| 130 | Interrupted (Ctrl+C) |

---

## Environment Variables

CLI commands respect these environment variables:

```bash
export BINANCE_API_KEY=your_key
export BINANCE_API_SECRET=your_secret
export LOG_LEVEL=DEBUG

python main.py paper
```

---

## Next Steps

- [API Reference](./07-api-reference.md) - REST API endpoints
- [Trading Strategies](./08-trading-strategies.md) - ML models and strategies
