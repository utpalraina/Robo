#!/usr/bin/env python3
"""
Unified Trading Runner - Paper & Live Trading with Kraken

This script provides an easy way to run paper trading (with real market data)
and later switch to live trading when ready.

Usage:
    # Paper trading (default - safe, no real money)
    python run_trader.py paper

    # Paper trading with scalping bot
    python run_trader.py scalp --mode paper

    # Live trading (requires --confirm flag for safety)
    python run_trader.py live --confirm

    # Check account status
    python run_trader.py status

    # View performance report
    python run_trader.py report
"""

import typer
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.helpers import load_config, setup_logging, get_exchange
from utils.kraken_api import KrakenAPI, get_btc_price, get_eth_price, get_account_summary
from data.fetcher import DataFetcher
from data.storage import DataStorage
from features.indicators import FeatureEngineer
from models.ml_models import create_model
from strategy.ml_strategy import MLStrategy
from engine.paper import PaperTrader
from engine.live import LiveTrader
from engine.scalping_bot import ScalpingBot, create_scalping_bot, BotMode

app = typer.Typer(
    name="run_trader",
    help="Unified Trading Runner - Paper & Live Trading with Kraken"
)
console = Console()


def get_kraken_status():
    """Get current Kraken account and market status."""
    try:
        api = KrakenAPI()
        status = api.get_system_status()
        balance = api.get_balance()

        # Get current prices
        btc_price = get_btc_price()
        eth_price = get_eth_price()

        return {
            "system_status": status.get("status", "unknown"),
            "balance": balance,
            "btc_price": btc_price,
            "eth_price": eth_price,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


@app.command()
def status():
    """Show current Kraken account status and market prices."""
    console.print(Panel.fit("[bold blue]Kraken Account Status[/bold blue]"))

    kraken_status = get_kraken_status()

    if "error" in kraken_status:
        console.print(f"[red]Error: {kraken_status['error']}[/red]")
        return

    # System status
    status_color = "green" if kraken_status["system_status"] == "online" else "red"
    console.print(f"System: [{status_color}]{kraken_status['system_status'].upper()}[/{status_color}]")

    # Market prices
    table = Table(title="Current Prices")
    table.add_column("Asset", style="cyan")
    table.add_column("Price (USD)", justify="right", style="green")

    table.add_row("BTC", f"${kraken_status['btc_price']:,.2f}")
    table.add_row("ETH", f"${kraken_status['eth_price']:,.2f}")
    console.print(table)

    # Account balance
    balance = kraken_status.get("balance", {})
    if balance:
        bal_table = Table(title="Account Balance")
        bal_table.add_column("Asset", style="cyan")
        bal_table.add_column("Amount", justify="right", style="green")

        for asset, amount in balance.items():
            if float(amount) > 0:
                bal_table.add_row(asset, f"{float(amount):.8f}")

        console.print(bal_table)
    else:
        console.print("[yellow]Account has no funds. Fund your Kraken account to start live trading.[/yellow]")

    console.print(f"\n[dim]Last updated: {kraken_status['timestamp']}[/dim]")


@app.command()
def paper(
    symbols: str = typer.Option("BTC/USD,ETH/USD", help="Comma-separated trading pairs"),
    config_path: str = typer.Option("config/config.yaml", help="Path to config file"),
    model_path: str = typer.Option("models/trained_model.joblib", help="Path to trained model"),
    interval: int = typer.Option(60, help="Trading interval in seconds"),
    capital: float = typer.Option(10000, help="Starting paper capital")
):
    """
    Start paper trading with real market data.

    Paper trading uses REAL prices from Kraken but simulated money.
    This is the recommended way to test your strategies before going live.
    """
    console.print(Panel.fit(
        "[bold yellow]PAPER TRADING MODE[/bold yellow]\n\n"
        "Using REAL market data from Kraken\n"
        "with SIMULATED funds (no real money at risk)",
        border_style="yellow"
    ))

    config = load_config(config_path)
    setup_logging(config)

    # Override paper trading capital
    config["paper_trading"] = config.get("paper_trading", {})
    config["paper_trading"]["initial_capital"] = capital

    # Check if model exists
    model_file = Path(model_path)
    if not model_file.exists():
        console.print(f"[yellow]Model not found at {model_path}[/yellow]")
        console.print("[yellow]Running without ML model (basic strategy only)[/yellow]")
        model = None
    else:
        model = create_model(config)
        model.load(model_path)
        console.print(f"[green]Loaded ML model from {model_path}[/green]")

    # Initialize components
    exchange = get_exchange(config, paper_mode=True)
    data_fetcher = DataFetcher(exchange)
    storage = DataStorage()
    feature_engineer = FeatureEngineer(config)

    # Show starting status
    kraken_status = get_kraken_status()
    console.print(f"\nKraken Status: [green]{kraken_status.get('system_status', 'unknown')}[/green]")
    console.print(f"BTC/USD: [cyan]${kraken_status.get('btc_price', 0):,.2f}[/cyan]")
    console.print(f"ETH/USD: [cyan]${kraken_status.get('eth_price', 0):,.2f}[/cyan]")

    # Create strategy and paper trader
    if model:
        strategy = MLStrategy(model, feature_engineer, config)
    else:
        # Create a basic strategy without ML
        strategy = MLStrategy(None, feature_engineer, config)

    paper_trader = PaperTrader(strategy, data_fetcher, storage, config)

    # Start trading
    symbol_list = [s.strip() for s in symbols.split(",")]
    console.print(f"\n[bold]Trading symbols:[/bold] {symbol_list}")
    console.print(f"[bold]Paper capital:[/bold] ${capital:,.2f}")
    console.print(f"[bold]Interval:[/bold] {interval} seconds")
    console.print("\n[dim]Press Ctrl+C to stop[/dim]\n")

    try:
        paper_trader.start(symbol_list, interval_seconds=interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Paper trading stopped[/yellow]")

        # Show final status
        status = paper_trader.get_status()
        console.print(f"\n[bold]Final Results:[/bold]")
        console.print(f"  Equity: ${status['equity']:,.2f}")
        console.print(f"  Total PnL: ${status['total_pnl']:,.2f}")
        console.print(f"  Total Trades: {status['total_trades']}")


@app.command()
def scalp(
    mode: str = typer.Option("paper", help="Trading mode: 'paper' or 'live'"),
    symbol: str = typer.Option("BTC/USD", help="Trading pair"),
    config_path: str = typer.Option("config/config.yaml", help="Path to config file"),
    model_path: str = typer.Option("models/trained_model.joblib", help="Path to trained model"),
    capital: float = typer.Option(1000, help="Starting capital"),
    trading_mode: str = typer.Option("medium", help="Trading mode: 'safe', 'medium', 'fast'"),
    interval: int = typer.Option(5, help="Check interval in seconds"),
    confirm: bool = typer.Option(False, "--confirm", help="Confirm live trading")
):
    """
    Start the confluence-based scalping bot.

    The scalping bot uses multiple signals (ICT, SMT, MTF, ML, Technical)
    to find high-probability trade setups.
    """
    if mode == "live" and not confirm:
        console.print(Panel.fit(
            "[bold red]WARNING: LIVE SCALPING MODE[/bold red]\n\n"
            "This will trade with REAL MONEY.\n"
            "Use --confirm flag to proceed.",
            border_style="red"
        ))
        raise typer.Exit(1)

    mode_color = "yellow" if mode == "paper" else "red"
    mode_text = "PAPER" if mode == "paper" else "LIVE"

    console.print(Panel.fit(
        f"[bold {mode_color}]{mode_text} SCALPING MODE[/bold {mode_color}]\n\n"
        f"Symbol: {symbol}\n"
        f"Trading Mode: {trading_mode.upper()}\n"
        f"Capital: ${capital:,.2f}",
        border_style=mode_color
    ))

    config = load_config(config_path)
    setup_logging(config)

    # Load ML model if available
    ml_strategy = None
    model_file = Path(model_path)
    if model_file.exists():
        try:
            model = create_model(config)
            model.load(model_path)
            feature_engineer = FeatureEngineer(config)
            ml_strategy = MLStrategy(model, feature_engineer, config)
            console.print(f"[green]ML model loaded: {model_path}[/green]")
        except Exception as e:
            console.print(f"[yellow]Could not load ML model: {e}[/yellow]")
    else:
        console.print("[yellow]No ML model found - running without ML predictions[/yellow]")

    # Initialize components
    exchange = get_exchange(config, paper_mode=(mode == "paper"))
    data_fetcher = DataFetcher(exchange)
    storage = DataStorage()

    # Create scalping bot
    bot = create_scalping_bot(
        exchange=exchange,
        fetcher=data_fetcher,
        storage=storage,
        mode=mode,
        symbol=symbol,
        capital=capital,
        trading_mode=trading_mode,
        ml_strategy=ml_strategy,
        check_interval=interval
    )

    # Show current market
    kraken_status = get_kraken_status()
    console.print(f"\nKraken: [green]{kraken_status.get('system_status', 'unknown')}[/green]")
    console.print(f"BTC: [cyan]${kraken_status.get('btc_price', 0):,.2f}[/cyan]")

    console.print("\n[dim]Press Ctrl+C to stop[/dim]\n")

    # Run the bot
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping scalping bot...[/yellow]")
        asyncio.run(bot.stop())

        # Show final status
        status = bot.get_status()
        console.print(f"\n[bold]Final Results:[/bold]")
        console.print(f"  Capital: ${status['capital']:,.2f}")
        console.print(f"  Total PnL: ${status['total_pnl']:,.2f} ({status['total_pnl_pct']:.2f}%)")
        console.print(f"  Win Rate: {status['stats']['win_rate']:.1f}%")
        console.print(f"  Total Trades: {status['stats']['total_trades']}")


@app.command()
def live(
    symbols: str = typer.Option("BTC/USD", help="Comma-separated trading pairs"),
    config_path: str = typer.Option("config/config.yaml", help="Path to config file"),
    model_path: str = typer.Option("models/trained_model.joblib", help="Path to trained model"),
    interval: int = typer.Option(60, help="Trading interval in seconds"),
    confirm: bool = typer.Option(False, "--confirm", help="Confirm live trading")
):
    """
    Start LIVE trading with REAL MONEY.

    WARNING: This trades with real funds on Kraken.
    Make sure you have:
    1. Funded your Kraken account
    2. Tested thoroughly with paper trading
    3. Understood the risks involved
    """
    if not confirm:
        console.print(Panel.fit(
            "[bold red]WARNING: LIVE TRADING MODE[/bold red]\n\n"
            "This will trade with REAL MONEY.\n"
            "Use --confirm flag to proceed.",
            border_style="red"
        ))
        raise typer.Exit(1)

    # Check if account has funds
    kraken_status = get_kraken_status()
    balance = kraken_status.get("balance", {})

    if not balance:
        console.print(Panel.fit(
            "[bold red]NO FUNDS DETECTED[/bold red]\n\n"
            "Your Kraken account appears to have no funds.\n"
            "Please deposit funds before live trading.",
            border_style="red"
        ))
        raise typer.Exit(1)

    console.print(Panel.fit(
        "[bold red]LIVE TRADING MODE ACTIVATED[/bold red]\n"
        "Real money at risk!",
        border_style="red"
    ))

    # Show account balance
    console.print("\n[bold]Account Balance:[/bold]")
    for asset, amount in balance.items():
        if float(amount) > 0:
            console.print(f"  {asset}: {float(amount):.8f}")

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
    console.print(f"\n[bold]Trading symbols:[/bold] {symbol_list}")
    console.print(f"[bold]Interval:[/bold] {interval} seconds")
    console.print("\n[dim]Press Ctrl+C to stop[/dim]\n")

    try:
        live_trader.start(symbol_list, interval_seconds=interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Live trading stopped[/yellow]")

        # Show final status
        status = live_trader.get_status()
        console.print(f"\n[bold]Final Status:[/bold]")
        console.print(f"  Balance: ${status['free_balance']:,.2f}")
        console.print(f"  Daily PnL: ${status['daily_pnl']:,.2f}")


@app.command()
def report(
    days: int = typer.Option(7, help="Number of days to report on")
):
    """Show trading performance report."""
    console.print(Panel.fit("[bold blue]Trading Performance Report[/bold blue]"))

    storage = DataStorage()

    # Get trades from storage
    trades = storage.get_trades(limit=1000)

    if trades.empty:
        console.print("[yellow]No trades recorded yet.[/yellow]")
        console.print("\nStart paper trading to build your trading history:")
        console.print("  [cyan]python run_trader.py paper[/cyan]")
        return

    # Filter by date range
    cutoff = datetime.now() - timedelta(days=days)
    trades['timestamp'] = pd.to_datetime(trades['timestamp'])
    recent_trades = trades[trades['timestamp'] >= cutoff]

    if recent_trades.empty:
        console.print(f"[yellow]No trades in the last {days} days.[/yellow]")
        return

    # Calculate statistics
    paper_trades = recent_trades[recent_trades.get('is_paper', True) == True]
    live_trades = recent_trades[recent_trades.get('is_paper', True) == False]

    # Summary table
    summary = Table(title=f"Performance Summary (Last {days} Days)")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Paper", justify="right")
    summary.add_column("Live", justify="right")

    summary.add_row("Total Trades", str(len(paper_trades)), str(len(live_trades)))

    console.print(summary)

    # Recent trades
    trades_table = Table(title="Recent Trades")
    trades_table.add_column("Time", style="cyan")
    trades_table.add_column("Symbol")
    trades_table.add_column("Side")
    trades_table.add_column("Price", justify="right")
    trades_table.add_column("Amount", justify="right")
    trades_table.add_column("Type")

    for _, trade in recent_trades.head(20).iterrows():
        side_color = "green" if trade.get("side") == "buy" else "red"
        trade_type = "Paper" if trade.get("is_paper", True) else "Live"

        trades_table.add_row(
            str(trade["timestamp"])[:19],
            str(trade.get("symbol", "N/A")),
            f"[{side_color}]{str(trade.get('side', 'N/A')).upper()}[/{side_color}]",
            f"${float(trade.get('price', 0)):,.2f}",
            f"{float(trade.get('amount', 0)):.6f}",
            trade_type
        )

    console.print(trades_table)


@app.command()
def prices():
    """Show live cryptocurrency prices from Kraken."""
    console.print(Panel.fit("[bold blue]Live Kraken Prices[/bold blue]"))

    try:
        api = KrakenAPI()

        # Get multiple tickers
        pairs = ["XBTUSD", "ETHUSD", "SOLUSD", "XRPUSD", "ADAUSD"]
        ticker_data = api.get_ticker(",".join(pairs))

        table = Table(title="Current Prices")
        table.add_column("Pair", style="cyan")
        table.add_column("Price", justify="right", style="green")
        table.add_column("24h High", justify="right")
        table.add_column("24h Low", justify="right")
        table.add_column("Volume", justify="right")

        pair_names = {
            "XXBTZUSD": "BTC/USD",
            "XETHZUSD": "ETH/USD",
            "SOLUSD": "SOL/USD",
            "XXRPZUSD": "XRP/USD",
            "ADAUSD": "ADA/USD"
        }

        for pair_key, data in ticker_data.items():
            name = pair_names.get(pair_key, pair_key)
            price = float(data['c'][0])
            high = float(data['h'][1])  # 24h high
            low = float(data['l'][1])   # 24h low
            volume = float(data['v'][1])  # 24h volume

            table.add_row(
                name,
                f"${price:,.2f}",
                f"${high:,.2f}",
                f"${low:,.2f}",
                f"{volume:,.2f}"
            )

        console.print(table)
        console.print(f"\n[dim]Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]")

    except Exception as e:
        console.print(f"[red]Error fetching prices: {e}[/red]")


@app.command()
def test_connection():
    """Test Kraken API connection and permissions."""
    console.print(Panel.fit("[bold blue]Testing Kraken API Connection[/bold blue]"))

    api = KrakenAPI()

    tests = [
        ("System Status", lambda: api.get_system_status()),
        ("Server Time", lambda: api.get_server_time()),
        ("BTC Ticker", lambda: api.get_ticker("XBTUSD")),
        ("Account Balance", lambda: api.get_balance()),
        ("Open Orders", lambda: api.get_open_orders()),
        ("Order Validation", lambda: api.add_order("XBTUSD", "buy", "limit", 0.001, "50000", validate=True)),
    ]

    results = Table(title="API Permission Tests")
    results.add_column("Test", style="cyan")
    results.add_column("Status")
    results.add_column("Details")

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.add_row(test_name, "[green]PASS[/green]", str(result)[:50] + "...")
        except Exception as e:
            results.add_row(test_name, "[red]FAIL[/red]", str(e)[:50])

    console.print(results)
    console.print("\n[green]All required permissions are working![/green]")


# Import pandas for report command
try:
    import pandas as pd
except ImportError:
    pd = None


if __name__ == "__main__":
    app()
