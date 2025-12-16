#!/usr/bin/env python3
"""
Robo Trader - ML-based Cryptocurrency Trading Bot

A comprehensive trading system with backtesting, paper trading, and live trading capabilities.
"""

import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from loguru import logger
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.helpers import load_config, setup_logging, get_exchange
from data.fetcher import DataFetcher
from data.storage import DataStorage
from features.indicators import FeatureEngineer
from models.ml_models import create_model, cross_validate_model
from strategy.ml_strategy import MLStrategy
from engine.backtester import Backtester
from engine.paper import PaperTrader
from engine.live import LiveTrader

app = typer.Typer(
    name="robo-trader",
    help="ML-based Cryptocurrency Trading Bot"
)
console = Console()


@app.command()
def train(
    symbol: str = typer.Option("BTC/USDT", help="Trading pair to train on"),
    start_date: str = typer.Option("2024-01-01", help="Training start date"),
    end_date: str = typer.Option("2024-11-01", help="Training end date"),
    config_path: str = typer.Option("config/config.yaml", help="Path to config file"),
    output_path: str = typer.Option("models/trained_model.joblib", help="Path to save model")
):
    """Train the ML model on historical data."""
    console.print(Panel.fit("[bold blue]Training ML Model[/bold blue]"))

    config = load_config(config_path)
    setup_logging(config)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        # Initialize components
        task = progress.add_task("Initializing exchange...", total=None)
        exchange = get_exchange(config)
        data_fetcher = DataFetcher(exchange)

        # Fetch historical data
        progress.update(task, description="Fetching historical data...")
        timeframe = config.get("trading", {}).get("timeframe", "1h")
        df = data_fetcher.fetch_historical_data(symbol, timeframe, start_date, end_date)

        if df.empty:
            console.print("[red]No data fetched. Check symbol and date range.[/red]")
            raise typer.Exit(1)

        console.print(f"Fetched {len(df)} candles")

        # Generate features
        progress.update(task, description="Generating features...")
        feature_engineer = FeatureEngineer(config)
        df_features = feature_engineer.generate_features(df)
        console.print(f"Generated {len(df_features.columns)} features")

        # Prepare ML data
        progress.update(task, description="Preparing training data...")
        X, y = feature_engineer.prepare_ml_data(df_features)
        console.print(f"Total samples: {len(X)}")

        # Split data for training and evaluation (time-series aware - no shuffle)
        from sklearn.model_selection import train_test_split
        split_ratio = config.get("model", {}).get("train_test_split", 0.8)
        split_idx = int(len(X) * split_ratio)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        console.print(f"Training samples: {len(X_train)}, Test samples: {len(X_test)}")

        # Train model
        progress.update(task, description="Training model...")
        model = create_model(config)
        model.train(X_train, y_train)

        # Evaluate on held-out test data
        progress.update(task, description="Evaluating model on test data...")
        metrics = model.evaluate(X_test, y_test)

        # Save model
        progress.update(task, description="Saving model...")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        model.save(output_path)

    # Display results
    table = Table(title="Training Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    for metric, value in metrics.items():
        table.add_row(metric, f"{value:.4f}")

    console.print(table)
    console.print(f"\n[green]Model saved to {output_path}[/green]")


@app.command()
def backtest(
    symbol: str = typer.Option("BTC/USDT", help="Trading pair"),
    start_date: str = typer.Option("2024-01-01", help="Backtest start date"),
    end_date: str = typer.Option("2024-11-01", help="Backtest end date"),
    config_path: str = typer.Option("config/config.yaml", help="Path to config file"),
    model_path: str = typer.Option("models/trained_model.joblib", help="Path to trained model"),
    plot: bool = typer.Option(True, help="Generate plots")
):
    """Run backtest on historical data."""
    console.print(Panel.fit("[bold blue]Running Backtest[/bold blue]"))

    config = load_config(config_path)
    setup_logging(config)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Loading model...", total=None)

        # Load model
        model = create_model(config)
        model.load(model_path)

        # Initialize components
        progress.update(task, description="Initializing components...")
        exchange = get_exchange(config)
        data_fetcher = DataFetcher(exchange)
        feature_engineer = FeatureEngineer(config)

        # Fetch data
        progress.update(task, description="Fetching historical data...")
        timeframe = config.get("trading", {}).get("timeframe", "1h")
        df = data_fetcher.fetch_historical_data(symbol, timeframe, start_date, end_date)

        if df.empty:
            console.print("[red]No data fetched.[/red]")
            raise typer.Exit(1)

        # Generate features
        progress.update(task, description="Generating features...")
        df_features = feature_engineer.generate_features(df)

        # Create strategy and backtester
        progress.update(task, description="Running backtest...")
        strategy = MLStrategy(model, feature_engineer, config)
        backtester = Backtester(config)

        # Run backtest
        result = backtester.run(strategy, df_features, symbol)

    # Display results
    console.print("\n" + backtester.generate_report(result))

    if plot:
        backtester.plot_results(result, save_path="backtest_results.png")


@app.command()
def paper(
    symbols: str = typer.Option("BTC/USDT,ETH/USDT", help="Comma-separated trading pairs"),
    config_path: str = typer.Option("config/config.yaml", help="Path to config file"),
    model_path: str = typer.Option("models/trained_model.joblib", help="Path to trained model"),
    interval: int = typer.Option(60, help="Trading interval in seconds")
):
    """Start paper trading simulation."""
    console.print(Panel.fit("[bold yellow]Starting Paper Trading[/bold yellow]"))
    console.print("[yellow]Paper trading uses simulated funds - no real money at risk[/yellow]\n")

    config = load_config(config_path)
    setup_logging(config)

    # Load model
    model = create_model(config)
    model.load(model_path)

    # Initialize components
    exchange = get_exchange(config, paper_mode=True)
    data_fetcher = DataFetcher(exchange)
    storage = DataStorage()
    feature_engineer = FeatureEngineer(config)

    # Create strategy and paper trader
    strategy = MLStrategy(model, feature_engineer, config)
    paper_trader = PaperTrader(strategy, data_fetcher, storage, config)

    # Start trading
    symbol_list = [s.strip() for s in symbols.split(",")]
    console.print(f"Trading symbols: {symbol_list}")
    console.print(f"Interval: {interval} seconds")
    console.print("\nPress Ctrl+C to stop\n")

    paper_trader.start(symbol_list, interval_seconds=interval)


@app.command()
def live(
    symbols: str = typer.Option("BTC/USDT", help="Comma-separated trading pairs"),
    config_path: str = typer.Option("config/config.yaml", help="Path to config file"),
    model_path: str = typer.Option("models/trained_model.joblib", help="Path to trained model"),
    interval: int = typer.Option(60, help="Trading interval in seconds"),
    confirm: bool = typer.Option(False, "--confirm", help="Confirm live trading")
):
    """Start live trading with real money."""
    if not confirm:
        console.print(Panel.fit(
            "[bold red]WARNING: LIVE TRADING MODE[/bold red]\n\n"
            "This will trade with REAL MONEY.\n"
            "Use --confirm flag to proceed.",
            border_style="red"
        ))
        raise typer.Exit(1)

    console.print(Panel.fit(
        "[bold red]LIVE TRADING MODE ACTIVATED[/bold red]\n"
        "Real money at risk!",
        border_style="red"
    ))

    config = load_config(config_path)
    setup_logging(config)

    # Load model
    model = create_model(config)
    model.load(model_path)

    # Initialize components
    exchange = get_exchange(config, paper_mode=False)
    data_fetcher = DataFetcher(exchange)
    storage = DataStorage()
    feature_engineer = FeatureEngineer(config)

    # Create strategy and live trader
    strategy = MLStrategy(model, feature_engineer, config)
    live_trader = LiveTrader(strategy, exchange, data_fetcher, storage, config)

    # Start trading
    symbol_list = [s.strip() for s in symbols.split(",")]
    console.print(f"Trading symbols: {symbol_list}")
    console.print(f"Interval: {interval} seconds")
    console.print("\nPress Ctrl+C to stop\n")

    live_trader.start(symbol_list, interval_seconds=interval)


@app.command()
def status(
    config_path: str = typer.Option("config/config.yaml", help="Path to config file")
):
    """Show current trading status and recent trades."""
    config = load_config(config_path)
    storage = DataStorage()

    # Get recent trades
    trades = storage.get_trades(limit=20)

    if trades.empty:
        console.print("[yellow]No trades recorded yet.[/yellow]")
        return

    table = Table(title="Recent Trades")
    table.add_column("Time", style="cyan")
    table.add_column("Symbol")
    table.add_column("Side")
    table.add_column("Price", justify="right")
    table.add_column("Amount", justify="right")
    table.add_column("Type")

    for _, trade in trades.iterrows():
        side_color = "green" if trade["side"] == "buy" else "red"
        trade_type = "Paper" if trade.get("is_paper") else "Live"

        table.add_row(
            str(trade["timestamp"])[:19],
            trade["symbol"],
            f"[{side_color}]{trade['side'].upper()}[/{side_color}]",
            f"${trade['price']:.2f}",
            f"{trade['amount']:.6f}",
            trade_type
        )

    console.print(table)


@app.command()
def fetch_data(
    symbol: str = typer.Option("BTC/USDT", help="Trading pair"),
    start_date: str = typer.Option("2024-01-01", help="Start date"),
    end_date: str = typer.Option("2024-12-01", help="End date"),
    config_path: str = typer.Option("config/config.yaml", help="Path to config file")
):
    """Fetch and store historical data."""
    console.print(Panel.fit("[bold blue]Fetching Historical Data[/bold blue]"))

    config = load_config(config_path)
    setup_logging(config)

    exchange = get_exchange(config)
    data_fetcher = DataFetcher(exchange)
    storage = DataStorage()

    timeframe = config.get("trading", {}).get("timeframe", "1h")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(f"Fetching {symbol} data...", total=None)
        df = data_fetcher.fetch_historical_data(symbol, timeframe, start_date, end_date)

        if df.empty:
            console.print("[red]No data fetched.[/red]")
            raise typer.Exit(1)

        progress.update(task, description="Saving to database...")
        storage.save_ohlcv(df, symbol, timeframe)

    console.print(f"[green]Saved {len(df)} candles for {symbol}[/green]")


@app.command()
def validate(
    symbol: str = typer.Option("BTC/USDT", help="Trading pair"),
    start_date: str = typer.Option("2024-01-01", help="Start date"),
    end_date: str = typer.Option("2024-11-01", help="End date"),
    config_path: str = typer.Option("config/config.yaml", help="Path to config file"),
    folds: int = typer.Option(5, help="Number of CV folds")
):
    """Cross-validate the model."""
    console.print(Panel.fit("[bold blue]Cross-Validating Model[/bold blue]"))

    config = load_config(config_path)
    setup_logging(config)

    exchange = get_exchange(config)
    data_fetcher = DataFetcher(exchange)
    feature_engineer = FeatureEngineer(config)

    timeframe = config.get("trading", {}).get("timeframe", "1h")
    df = data_fetcher.fetch_historical_data(symbol, timeframe, start_date, end_date)

    if df.empty:
        console.print("[red]No data fetched.[/red]")
        raise typer.Exit(1)

    df_features = feature_engineer.generate_features(df)
    X, y = feature_engineer.prepare_ml_data(df_features)

    model = create_model(config)
    results = cross_validate_model(model, X, y, n_splits=folds)

    table = Table(title=f"Cross-Validation Results ({folds} folds)")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    for metric, value in results.items():
        table.add_row(metric, f"{value:.4f}")

    console.print(table)


@app.command()
def web(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to run on")
):
    """Launch the web dashboard."""
    console.print(Panel.fit("[bold blue]Launching Web Dashboard[/bold blue]"))
    console.print(f"\nOpen your browser at: [cyan]http://localhost:{port}[/cyan]\n")

    import uvicorn
    from web.server import app as web_app

    uvicorn.run(web_app, host=host, port=port)


if __name__ == "__main__":
    app()
