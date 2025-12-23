"""FastAPI Web Server for Robo Trader Dashboard."""

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import sys
from loguru import logger

# AI Analysis
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic SDK not installed.")

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("Google Gemini SDK not installed.")

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import pandas as pd
import numpy as np

from utils.helpers import load_config, setup_logging, get_exchange
from data.fetcher import DataFetcher
from data.storage import DataStorage
from data.kraken_ws import KrakenWebSocket
from data.candle_collector import CandleCollector
from features.indicators import FeatureEngineer
from features.dr_idr import DRIDRIndicator, calculate_dr_idr_for_chart
from features.ict_indicators import ICTIndicators
from features.mtf_ict import MTFICTAnalyzer
from features.structure_breaks import StructureBreakIndicator, calculate_bos_mss, get_structure_signal
from features.pine_script import parse_and_execute, validate_script
from data.postgres_storage import PostgresStorage
from models.ml_models import create_model
from strategy.ml_strategy import MLStrategy
from engine.paper import PaperTrader
from engine.backtester import Backtester
from engine.trading_bots import ShortTermBot, SwingTradingBot, LongTermBot
from web.tars_assistant import TARS, get_tars, TARSResponse, get_ny_time, NY_TZ


def convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif pd.isna(obj):
        return None
    return obj


# Initialize FastAPI app
app = FastAPI(title="Robo Trader", description="ML-based Crypto Trading Bot Dashboard")

# Add CORS middleware
# In production, replace with specific origins like ["https://yourdomain.com"]
ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://localhost:3000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Mount static files and templates
web_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=web_dir / "static"), name="static")
templates = Jinja2Templates(directory=web_dir / "templates")

# Global state
class TradingState:
    def __init__(self):
        self.config = None
        self.exchange = None
        self.data_fetcher = None
        self.storage = None
        self.feature_engineer = None
        self.model = None
        self.strategy = None
        self.paper_trader = None
        self.is_trading = False
        self.trading_mode = None  # 'paper' or 'live'
        self.active_symbols = []
        self.websocket_clients: List[WebSocket] = []
        self.kraken_ws: Optional[KrakenWebSocket] = None  # Real-time WebSocket feed
        self.use_websocket_feed = True  # Toggle for WebSocket vs REST polling
        self.candle_collector: Optional[CandleCollector] = None  # 5-min candle collector
        self.scalping_bot = None  # Scalping bot instance
        self.scalping_task = None  # Scalping bot async task
        # Additional trading bots
        self.short_term_bot = None
        self.short_term_task = None
        self.swing_bot = None
        self.swing_task = None
        self.long_term_bot = None
        self.long_term_task = None

state = TradingState()


# Pydantic models for API
class TradeConfig(BaseModel):
    symbols: List[str]
    mode: str = "paper"  # paper or live


class BacktestConfig(BaseModel):
    symbol: str
    start_date: str
    end_date: str


class TrainConfig(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    model_type: str = "xgboost"


# Custom Indicator Models
class CustomIndicatorCreate(BaseModel):
    name: str
    short_name: str
    pine_script: str
    description: Optional[str] = None
    is_overlay: bool = True
    category: Optional[str] = None
    default_settings: Optional[Dict] = None


class CustomIndicatorUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    pine_script: Optional[str] = None
    description: Optional[str] = None
    is_overlay: Optional[bool] = None
    is_enabled: Optional[bool] = None
    category: Optional[str] = None
    default_settings: Optional[Dict] = None


class IndicatorSettingsUpdate(BaseModel):
    settings: Dict
    chart_id: str = "default"


class PineScriptValidate(BaseModel):
    pine_script: str


# Custom Python Indicator Models
class CustomPythonIndicatorCreate(BaseModel):
    name: str
    short_name: str
    python_code: str
    description: Optional[str] = None
    is_overlay: bool = True
    default_settings: Optional[Dict] = None


class CustomPythonIndicatorUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    python_code: Optional[str] = None
    description: Optional[str] = None
    is_overlay: Optional[bool] = None
    is_enabled: Optional[bool] = None
    default_settings: Optional[Dict] = None


class PythonCodeExecute(BaseModel):
    python_code: str
    settings: Optional[Dict] = None


# Initialize PostgreSQL storage for custom indicators
postgres_storage: Optional[PostgresStorage] = None


def get_postgres_storage() -> PostgresStorage:
    """Get or create PostgreSQL storage instance."""
    global postgres_storage
    if postgres_storage is None:
        postgres_storage = PostgresStorage()
    return postgres_storage


# Helper to run sync functions in thread pool
async def run_in_executor(func, *args):
    """Run a synchronous function in a thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


# Callback for Kraken WebSocket tick updates - broadcasts to all clients instantly
async def on_kraken_tick(tick: dict):
    """Handle real-time tick from Kraken WebSocket and broadcast to clients."""
    if not state.websocket_clients:
        return

    try:
        # Format timestamp
        exchange_ts = tick.get('exchange_ts') or tick.get('timestamp')
        if exchange_ts:
            exchange_time = datetime.fromtimestamp(exchange_ts / 1000)
            timestamp_iso = exchange_time.isoformat()
        else:
            timestamp_iso = datetime.now().isoformat()

        await broadcast({
            "type": "ticker",
            "symbol": tick.get('symbol', 'BTC/USD'),
            "price": tick.get('price', 0),
            "bid": tick.get('bid', 0),
            "ask": tick.get('ask', 0),
            "high": tick.get('high', 0),
            "low": tick.get('low', 0),
            "change": tick.get('change', 0),  # 24h change percentage
            "volume": tick.get('volume', 0),
            "timestamp": timestamp_iso,
            "exchange_ts": exchange_ts,
            "source": "websocket"  # Indicate real-time source
        })
    except Exception as e:
        print(f"Error broadcasting tick: {e}")


# Background task for real-time price broadcasting via WebSocket
async def realtime_broadcast_loop():
    """
    Broadcast real-time price ticker to WebSocket clients.
    Uses Kraken WebSocket for instant updates, falls back to REST polling.
    """
    symbol = "BTC/USD"  # Default symbol

    # Try to start Kraken WebSocket feed
    if state.use_websocket_feed:
        try:
            if state.config:
                symbol = state.config.get("trading", {}).get("symbol", "BTC/USD")

            state.kraken_ws = KrakenWebSocket(on_ticker=on_kraken_tick)
            print(f"Starting Kraken WebSocket for real-time {symbol} data...")
            asyncio.create_task(state.kraken_ws.run([symbol]))
            print("Kraken WebSocket feed started - instant price updates enabled!")
            return  # WebSocket handles broadcasting, no need for polling loop
        except Exception as e:
            print(f"Failed to start Kraken WebSocket: {e}")
            print("Falling back to REST API polling...")
            state.use_websocket_feed = False

    # Fallback: REST API polling (slower but reliable)
    while True:
        try:
            if state.websocket_clients and state.exchange:
                if state.config:
                    symbol = state.config.get("trading", {}).get("symbol", "BTC/USD")

                # Fetch ticker price (run in thread to not block async loop)
                try:
                    ticker = await run_in_executor(state.exchange.fetch_ticker, symbol)
                    if ticker:
                        price = ticker.get("last", 0)
                        # Use exchange timestamp for accuracy (milliseconds since epoch)
                        exchange_ts = ticker.get("timestamp")  # ms since epoch from exchange
                        if exchange_ts:
                            exchange_time = datetime.fromtimestamp(exchange_ts / 1000)
                            timestamp_iso = exchange_time.isoformat()
                        else:
                            timestamp_iso = datetime.now().isoformat()

                        await broadcast({
                            "type": "ticker",
                            "symbol": symbol,
                            "price": price,
                            "bid": ticker.get("bid", 0),
                            "ask": ticker.get("ask", 0),
                            "high": ticker.get("high", 0),
                            "low": ticker.get("low", 0),
                            "change": ticker.get("percentage", 0),
                            "volume": ticker.get("baseVolume", 0),
                            "timestamp": timestamp_iso,
                            "exchange_ts": exchange_ts,
                            "source": "rest"  # Indicate polling source
                        })
                except Exception as e:
                    pass  # Silent fail for ticker

        except Exception as e:
            print(f"Broadcast loop error: {e}")

        await asyncio.sleep(1)  # Polling fallback: 1 second intervals


# Initialize on startup
@app.on_event("startup")
async def startup():
    """Initialize trading components on startup."""
    try:
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
        state.config = load_config(str(config_path))
        setup_logging(state.config)

        # Use paper_mode=False for exchanges without sandbox (like Kraken)
        # Paper trading is simulated in the application, not at exchange level
        state.exchange = get_exchange(state.config, paper_mode=False)
        state.data_fetcher = DataFetcher(state.exchange)
        state.storage = DataStorage()
        state.feature_engineer = FeatureEngineer(state.config)

        # Try to load existing model
        model_path = Path(__file__).parent.parent / "models" / "trained_model.joblib"
        if model_path.exists():
            state.model = create_model(state.config)
            state.model.load(str(model_path))
            state.strategy = MLStrategy(state.model, state.feature_engineer, state.config)

        exchange_name = state.config.get("exchange", {}).get("name", "unknown")
        print(f"Trading system initialized with {exchange_name.upper()}")

        # Start background WebSocket broadcasting
        asyncio.create_task(realtime_broadcast_loop())
        print("Real-time WebSocket broadcasting started")

        # Start 5-minute candle collector
        trading_symbol = state.config.get("trading", {}).get("symbols", ["BTC/USD"])[0]
        state.candle_collector = CandleCollector(
            data_fetcher=state.data_fetcher,
            feature_engineer=state.feature_engineer,
            storage=state.storage,
            strategy=state.strategy,
            symbol=trading_symbol
        )
        asyncio.create_task(state.candle_collector.run(interval_seconds=300))
        print("5-minute candle collector started")

        # Start SBC+DR data updater (runs at startup and every 4 hours)
        asyncio.create_task(sbc_dr_data_updater())
        print("SBC+DR data updater started")

    except Exception as e:
        print(f"Warning: Could not fully initialize: {e}")


async def sbc_dr_data_updater():
    """Background task to populate missing SBC+DR data on startup and periodically."""
    import subprocess
    while True:
        try:
            # Run the populate_missing_days.py script
            result = subprocess.run(
                ['python3', '/Users/utpalraina/robo-trader/populate_missing_days.py'],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                logger.info(f"SBC+DR data update completed: {result.stdout.strip().split(chr(10))[-1]}")
            else:
                logger.warning(f"SBC+DR data update failed: {result.stderr}")
        except Exception as e:
            logger.error(f"SBC+DR data update error: {e}")

        # Wait 4 hours before next update
        await asyncio.sleep(4 * 60 * 60)


# WebSocket connection manager
async def broadcast(message: dict):
    """Broadcast message to all connected WebSocket clients."""
    for client in state.websocket_clients:
        try:
            await client.send_json(message)
        except:
            pass


# Routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve pro trading dashboard (default)."""
    return templates.TemplateResponse("trading.html", {"request": request})


@app.get("/trading", response_class=HTMLResponse)
async def trading(request: Request):
    """Serve pro trading dashboard."""
    return templates.TemplateResponse("trading.html", {"request": request})


@app.get("/simulation", response_class=HTMLResponse)
async def simulation(request: Request):
    """Serve backtest simulation page."""
    return templates.TemplateResponse("simulation.html", {"request": request})


@app.get("/strategies", response_class=HTMLResponse)
async def strategies_page(request: Request):
    """Serve strategies management page."""
    return templates.TemplateResponse("strategies.html", {"request": request})


@app.get("/planetary", response_class=HTMLResponse)
async def planetary_page(request: Request):
    """Serve planetary analysis dashboard."""
    return templates.TemplateResponse("planetary.html", {"request": request})


# ================== PLANETARY ANALYSIS API ==================

from web.planetary_analysis import get_full_analysis, load_backtest_data

BACKTEST_CSV_FILE = Path(__file__).parent.parent / 'backtest_detailed_results.csv'


@app.get("/api/planetary/analysis")
async def get_planetary_analysis():
    """Get full planetary analysis data."""
    try:
        analysis = get_full_analysis()
        return convert_numpy_types(analysis)
    except Exception as e:
        logger.error(f"Error getting planetary analysis: {e}")
        return {"error": str(e)}


@app.get("/api/planetary/download-csv")
async def download_planetary_csv():
    """Download the full backtest CSV."""
    from fastapi.responses import FileResponse

    if not BACKTEST_CSV_FILE.exists():
        raise HTTPException(status_code=404, detail="Backtest CSV not found")

    return FileResponse(
        path=str(BACKTEST_CSV_FILE),
        filename="planetary_backtest_results.csv",
        media_type="text/csv"
    )


# ================== VEDIC ASTROLOGY ANALYSIS API ==================

from web.vedic_analysis import get_full_vedic_analysis, get_current_vedic_positions, calculate_current_signal, get_planetary_stats
from web.sbc_analysis import get_current_sbc_analysis, analyze_historical_vedhas, get_full_sbc_data, calculate_custom_sbc_analysis
from web.sbc_market_rules import forecast_vedha_weights, forecast_hourly_vedha_weights
from web.combined_signal import get_combined_signal

VEDIC_DATA_FILE = Path(__file__).parent.parent / 'btc_vedic_planetary_5years.csv'


@app.get("/vedic", response_class=HTMLResponse)
async def vedic_page(request: Request):
    """Serve Vedic astrology analysis dashboard."""
    return templates.TemplateResponse("vedic.html", {"request": request})


@app.get("/api/vedic/analysis")
async def get_vedic_analysis():
    """Get full Vedic astrology analysis data."""
    try:
        analysis = get_full_vedic_analysis()
        return convert_numpy_types(analysis)
    except Exception as e:
        logger.error(f"Error getting Vedic analysis: {e}")
        return {"error": str(e)}


@app.get("/api/vedic/positions")
async def get_vedic_positions():
    """Get current Vedic planetary positions."""
    try:
        positions = get_current_vedic_positions()
        return convert_numpy_types(positions)
    except Exception as e:
        logger.error(f"Error getting Vedic positions: {e}")
        return {"error": str(e)}


@app.get("/api/vedic/signal")
async def get_vedic_signal():
    """Get current trading signal based on Vedic analysis."""
    try:
        signal = calculate_current_signal()
        return convert_numpy_types(signal)
    except Exception as e:
        logger.error(f"Error calculating Vedic signal: {e}")
        return {"error": str(e)}


@app.get("/api/vedic/stats")
async def get_vedic_stats():
    """Get planetary statistics."""
    try:
        stats = get_planetary_stats()
        return convert_numpy_types(stats)
    except Exception as e:
        logger.error(f"Error getting Vedic stats: {e}")
        return {"error": str(e)}


@app.get("/api/vedic/download-csv")
async def download_vedic_csv():
    """Download the full Vedic planetary data CSV."""
    from fastapi.responses import FileResponse

    if not VEDIC_DATA_FILE.exists():
        raise HTTPException(status_code=404, detail="Vedic data CSV not found")

    return FileResponse(
        path=str(VEDIC_DATA_FILE),
        filename="btc_vedic_planetary_5years.csv",
        media_type="text/csv"
    )


# ================== SARVATO BHADRA CHAKRA (SBC) API ==================

@app.get("/sbc", response_class=HTMLResponse)
async def sbc_page(request: Request):
    """Serve Sarvato Bhadra Chakra analysis dashboard."""
    return templates.TemplateResponse("sbc.html", {"request": request})


@app.get("/api/sbc/current")
async def get_sbc_current():
    """Get current SBC analysis with vedhas."""
    try:
        analysis = get_current_sbc_analysis()
        return convert_numpy_types(analysis)
    except Exception as e:
        logger.error(f"Error getting SBC analysis: {e}")
        return {"error": str(e)}


@app.get("/api/sbc/historical")
async def get_sbc_historical():
    """Get historical vedha analysis (5 years correlation with BTC)."""
    try:
        analysis = analyze_historical_vedhas()
        return convert_numpy_types(analysis)
    except Exception as e:
        logger.error(f"Error getting historical SBC analysis: {e}")
        return {"error": str(e)}


@app.get("/api/sbc/full")
async def get_sbc_full():
    """Get complete SBC data for dashboard."""
    try:
        data = get_full_sbc_data()
        return convert_numpy_types(data)
    except Exception as e:
        logger.error(f"Error getting full SBC data: {e}")
        return {"error": str(e)}


class CustomSBCRequest(BaseModel):
    """Request model for custom SBC analysis."""
    name: str
    birth_date: str  # YYYY-MM-DD
    birth_time: str  # HH:MM
    latitude: float
    longitude: float
    analysis_date: str  # YYYY-MM-DD
    analysis_time: str = "12:00"  # HH:MM
    timezone: str = "UTC"


@app.get("/sbc-custom", response_class=HTMLResponse)
async def sbc_custom_page(request: Request):
    """Serve custom SBC analysis dashboard."""
    return templates.TemplateResponse("sbc_custom.html", {"request": request})


@app.get("/markets", response_class=HTMLResponse)
async def markets_page(request: Request):
    """Serve markets SBC dashboard for commodities, indexes, and stocks."""
    return templates.TemplateResponse("markets.html", {"request": request})


@app.get("/sbc-rules", response_class=HTMLResponse)
async def sbc_rules_page(request: Request):
    """Serve SBC trading rules dashboard."""
    return templates.TemplateResponse("sbc_rules.html", {"request": request})


@app.get("/api/sbc/rules")
async def get_sbc_rules():
    """Get all SBC trading rules from database."""
    import sqlite3
    try:
        db_path = Path(__file__).parent.parent / "data" / "robo_trader.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM sbc_trading_rules
            WHERE is_active = 1
            ORDER BY category, rule_number
        """)

        rules = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Group by category
        categories = {}
        for rule in rules:
            cat = rule['category']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(rule)

        return {
            "total_rules": len(rules),
            "categories": categories,
            "rules": rules
        }
    except Exception as e:
        logger.error(f"Error getting SBC rules: {e}")
        return {"error": str(e)}


@app.get("/sbc-backtest", response_class=HTMLResponse)
async def sbc_backtest_page(request: Request):
    """Serve SBC backtest dashboard."""
    return templates.TemplateResponse("sbc_backtest.html", {"request": request})


@app.get("/api/sbc/backtest/summary")
async def get_sbc_backtest_summary():
    """Get SBC backtest summary statistics."""
    import sqlite3
    try:
        db_path = Path(__file__).parent.parent / "data" / "robo_trader.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Overall stats
        cursor.execute("SELECT COUNT(*) as total FROM sbc_backtest_full")
        total = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as correct FROM sbc_backtest_full WHERE signal_correct = 'YES'")
        correct = cursor.fetchone()['correct']

        # Filtered stats
        cursor.execute("SELECT COUNT(*) as filtered FROM sbc_backtest_full WHERE should_trade = 'YES'")
        filtered_total = cursor.fetchone()['filtered']

        cursor.execute("SELECT COUNT(*) as filtered_correct FROM sbc_backtest_full WHERE should_trade = 'YES' AND signal_correct = 'YES'")
        filtered_correct = cursor.fetchone()['filtered_correct']

        # By confidence level
        cursor.execute("""
            SELECT confidence_level,
                   COUNT(*) as total,
                   SUM(CASE WHEN signal_correct = 'YES' THEN 1 ELSE 0 END) as correct
            FROM sbc_backtest_full
            GROUP BY confidence_level
        """)
        by_confidence = [dict(row) for row in cursor.fetchall()]

        # By signal type (filtered)
        cursor.execute("""
            SELECT signal,
                   COUNT(*) as total,
                   SUM(CASE WHEN signal_correct = 'YES' THEN 1 ELSE 0 END) as correct,
                   AVG(ny_session_change_pct) as avg_change
            FROM sbc_backtest_full
            WHERE should_trade = 'YES'
            GROUP BY signal
        """)
        by_signal = [dict(row) for row in cursor.fetchall()]

        # By year (filtered)
        cursor.execute("""
            SELECT substr(date, 1, 4) as year,
                   COUNT(*) as total,
                   SUM(CASE WHEN signal_correct = 'YES' THEN 1 ELSE 0 END) as correct,
                   SUM(CASE
                       WHEN signal LIKE '%BULLISH%' THEN ny_session_change_pct
                       WHEN signal LIKE '%BEARISH%' THEN -ny_session_change_pct
                       ELSE 0
                   END) as pnl
            FROM sbc_backtest_full
            WHERE should_trade = 'YES'
            GROUP BY substr(date, 1, 4)
            ORDER BY year
        """)
        by_year = [dict(row) for row in cursor.fetchall()]

        # By day of week (filtered)
        cursor.execute("""
            SELECT day_of_week,
                   COUNT(*) as total,
                   SUM(CASE WHEN signal_correct = 'YES' THEN 1 ELSE 0 END) as correct
            FROM sbc_backtest_full
            WHERE should_trade = 'YES'
            GROUP BY day_of_week
        """)
        by_day = [dict(row) for row in cursor.fetchall()]

        # By moon nakshatra (filtered, top 15)
        cursor.execute("""
            SELECT moon_nakshatra,
                   COUNT(*) as total,
                   SUM(CASE WHEN signal_correct = 'YES' THEN 1 ELSE 0 END) as correct
            FROM sbc_backtest_full
            WHERE should_trade = 'YES'
            GROUP BY moon_nakshatra
            ORDER BY total DESC
            LIMIT 15
        """)
        by_nakshatra = [dict(row) for row in cursor.fetchall()]

        # Calculate cumulative P&L
        cursor.execute("""
            SELECT SUM(CASE
                       WHEN signal LIKE '%BULLISH%' THEN ny_session_change_pct
                       WHEN signal LIKE '%BEARISH%' THEN -ny_session_change_pct
                       ELSE 0
                   END) as cumulative_pnl
            FROM sbc_backtest_full
            WHERE should_trade = 'YES'
        """)
        cumulative_pnl = cursor.fetchone()['cumulative_pnl'] or 0

        # Date range
        cursor.execute("SELECT MIN(date) as start_date, MAX(date) as end_date FROM sbc_backtest_full")
        date_range = dict(cursor.fetchone())

        conn.close()

        return {
            "date_range": date_range,
            "overall": {
                "total_days": total,
                "correct": correct,
                "accuracy": round(correct / total * 100, 1) if total > 0 else 0
            },
            "filtered": {
                "total_trades": filtered_total,
                "correct": filtered_correct,
                "accuracy": round(filtered_correct / filtered_total * 100, 1) if filtered_total > 0 else 0,
                "cumulative_pnl": round(cumulative_pnl, 2)
            },
            "by_confidence": by_confidence,
            "by_signal": by_signal,
            "by_year": by_year,
            "by_day": by_day,
            "by_nakshatra": by_nakshatra
        }
    except Exception as e:
        logger.error(f"Error getting backtest summary: {e}")
        return {"error": str(e)}


@app.get("/api/sbc/backtest/trades")
async def get_sbc_backtest_trades(
    year: str = None,
    signal: str = None,
    confidence: str = None,
    correct: str = None,
    limit: int = 100,
    offset: int = 0
):
    """Get SBC backtest trades with filters."""
    import sqlite3
    try:
        db_path = Path(__file__).parent.parent / "data" / "robo_trader.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        where_clauses = ["should_trade = 'YES'"]
        params = []

        if year:
            where_clauses.append("substr(date, 1, 4) = ?")
            params.append(year)
        if signal:
            where_clauses.append("signal = ?")
            params.append(signal)
        if confidence:
            where_clauses.append("confidence_level = ?")
            params.append(confidence)
        if correct:
            where_clauses.append("signal_correct = ?")
            params.append(correct)

        where_sql = " AND ".join(where_clauses)

        cursor.execute(f"""
            SELECT * FROM sbc_backtest_full
            WHERE {where_sql}
            ORDER BY date DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])

        trades = [dict(row) for row in cursor.fetchall()]

        cursor.execute(f"SELECT COUNT(*) as total FROM sbc_backtest_full WHERE {where_sql}", params)
        total = cursor.fetchone()['total']

        conn.close()

        return {
            "trades": trades,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error getting backtest trades: {e}")
        return {"error": str(e)}


@app.get("/api/sbc/backtest/equity-curve")
async def get_sbc_equity_curve():
    """Get equity curve data for charting."""
    import sqlite3
    try:
        db_path = Path(__file__).parent.parent / "data" / "robo_trader.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT date, ny_session_change_pct, signal, signal_correct
            FROM sbc_backtest_full
            WHERE should_trade = 'YES'
            ORDER BY date
        """)

        rows = cursor.fetchall()
        conn.close()

        equity = 100
        equity_curve = []

        for row in rows:
            change = row['ny_session_change_pct']
            signal = row['signal']

            if 'BULLISH' in signal:
                pnl = change
            elif 'BEARISH' in signal:
                pnl = -change
            else:
                pnl = 0

            equity *= (1 + pnl / 100)
            equity_curve.append({
                "date": row['date'],
                "equity": round(equity, 2),
                "pnl": round(pnl, 2),
                "correct": row['signal_correct'] == 'YES'
            })

        return {"equity_curve": equity_curve}
    except Exception as e:
        logger.error(f"Error getting equity curve: {e}")
        return {"error": str(e)}


# ============================================
# V6 BACKTEST API ENDPOINTS (PostgreSQL)
# ============================================

@app.get("/sbc-backtest-v6", response_class=HTMLResponse)
async def sbc_backtest_v6_page(request: Request):
    """Serve SBC V6 backtest dashboard."""
    return templates.TemplateResponse("sbc_backtest_v6.html", {"request": request})


@app.get("/api/sbc/backtest-v6/summary")
async def get_sbc_backtest_v6_summary():
    """Get V6 backtest summary statistics from PostgreSQL."""
    import psycopg2
    import psycopg2.extras
    try:
        conn = psycopg2.connect(dbname='robo_trader')
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Overall stats
        cursor.execute("SELECT COUNT(*) as total FROM sbc_backtest_v6")
        total = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as correct FROM sbc_backtest_v6 WHERE signal_correct_v6 = 'YES'")
        correct = cursor.fetchone()['correct']

        # Filtered stats (V6)
        cursor.execute("SELECT COUNT(*) as filtered FROM sbc_backtest_v6 WHERE should_trade = 'YES'")
        filtered_total = cursor.fetchone()['filtered']

        cursor.execute("SELECT COUNT(*) as filtered_correct FROM sbc_backtest_v6 WHERE should_trade = 'YES' AND signal_correct_v6 = 'YES'")
        filtered_correct = cursor.fetchone()['filtered_correct']

        # V6 P&L
        cursor.execute("SELECT SUM(pnl_v6) as cumulative_pnl FROM sbc_backtest_v6 WHERE should_trade = 'YES'")
        cumulative_pnl = cursor.fetchone()['cumulative_pnl'] or 0

        # By confidence level
        cursor.execute("""
            SELECT confidence_level,
                   COUNT(*) as total,
                   SUM(CASE WHEN signal_correct_v6 = 'YES' THEN 1 ELSE 0 END) as correct
            FROM sbc_backtest_v6
            GROUP BY confidence_level
        """)
        by_confidence = [dict(row) for row in cursor.fetchall()]

        # By V6 signal type (filtered)
        cursor.execute("""
            SELECT signal_v6 as signal,
                   COUNT(*) as total,
                   SUM(CASE WHEN signal_correct_v6 = 'YES' THEN 1 ELSE 0 END) as correct,
                   AVG(ny_session_change_pct) as avg_change,
                   SUM(pnl_v6) as pnl
            FROM sbc_backtest_v6
            WHERE should_trade = 'YES'
            GROUP BY signal_v6
            ORDER BY signal_v6
        """)
        by_signal = [dict(row) for row in cursor.fetchall()]

        # By year (filtered, V6)
        cursor.execute("""
            SELECT EXTRACT(YEAR FROM date)::text as year,
                   COUNT(*) as total,
                   SUM(CASE WHEN signal_correct_v6 = 'YES' THEN 1 ELSE 0 END) as correct,
                   SUM(pnl_v6) as pnl
            FROM sbc_backtest_v6
            WHERE should_trade = 'YES'
            GROUP BY EXTRACT(YEAR FROM date)
            ORDER BY year
        """)
        by_year = [dict(row) for row in cursor.fetchall()]

        # By day of week (filtered)
        cursor.execute("""
            SELECT day_of_week,
                   COUNT(*) as total,
                   SUM(CASE WHEN signal_correct_v6 = 'YES' THEN 1 ELSE 0 END) as correct
            FROM sbc_backtest_v6
            WHERE should_trade = 'YES'
            GROUP BY day_of_week
        """)
        by_day = [dict(row) for row in cursor.fetchall()]

        # By moon nakshatra (filtered, top 15)
        cursor.execute("""
            SELECT moon_nakshatra,
                   COUNT(*) as total,
                   SUM(CASE WHEN signal_correct_v6 = 'YES' THEN 1 ELSE 0 END) as correct
            FROM sbc_backtest_v6
            WHERE should_trade = 'YES'
            GROUP BY moon_nakshatra
            ORDER BY total DESC
            LIMIT 15
        """)
        by_nakshatra = [dict(row) for row in cursor.fetchall()]

        # Date range
        cursor.execute("SELECT MIN(date) as start_date, MAX(date) as end_date FROM sbc_backtest_v6")
        date_range = dict(cursor.fetchone())
        date_range['start_date'] = str(date_range['start_date'])
        date_range['end_date'] = str(date_range['end_date'])

        # NEUTRAL reduction stats
        cursor.execute("SELECT COUNT(*) as v5_neutral FROM sbc_backtest_v6 WHERE should_trade = 'YES' AND signal = 'NEUTRAL'")
        v5_neutral = cursor.fetchone()['v5_neutral']
        cursor.execute("SELECT COUNT(*) as v6_neutral FROM sbc_backtest_v6 WHERE should_trade = 'YES' AND signal_v6 = 'NEUTRAL'")
        v6_neutral = cursor.fetchone()['v6_neutral']

        conn.close()

        return {
            "version": "V6",
            "date_range": date_range,
            "overall": {
                "total_days": total,
                "correct": correct,
                "accuracy": round(correct / total * 100, 1) if total > 0 else 0
            },
            "filtered": {
                "total_trades": filtered_total,
                "correct": filtered_correct,
                "accuracy": round(filtered_correct / filtered_total * 100, 1) if filtered_total > 0 else 0,
                "cumulative_pnl": round(float(cumulative_pnl), 2)
            },
            "neutral_reduction": {
                "v5_neutral": v5_neutral,
                "v6_neutral": v6_neutral,
                "converted": v5_neutral - v6_neutral,
                "conversion_rate": round((v5_neutral - v6_neutral) / v5_neutral * 100, 1) if v5_neutral > 0 else 0
            },
            "by_confidence": by_confidence,
            "by_signal": by_signal,
            "by_year": by_year,
            "by_day": by_day,
            "by_nakshatra": by_nakshatra
        }
    except Exception as e:
        logger.error(f"Error getting V6 backtest summary: {e}")
        return {"error": str(e)}


@app.get("/api/sbc/backtest-v6/trades")
async def get_sbc_backtest_v6_trades(
    year: str = None,
    signal: str = None,
    confidence: str = None,
    correct: str = None,
    limit: int = 100,
    offset: int = 0
):
    """Get V6 backtest trades with filters."""
    import psycopg2
    import psycopg2.extras
    try:
        conn = psycopg2.connect(dbname='robo_trader')
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        where_clauses = ["should_trade = 'YES'"]
        params = []

        if year:
            where_clauses.append("EXTRACT(YEAR FROM date)::text = %s")
            params.append(year)
        if signal:
            where_clauses.append("signal_v6 = %s")
            params.append(signal)
        if confidence:
            where_clauses.append("confidence_level = %s")
            params.append(confidence)
        if correct:
            where_clauses.append("signal_correct_v6 = %s")
            params.append(correct)

        where_sql = " AND ".join(where_clauses)

        cursor.execute(f"""
            SELECT date, day_of_week, signal, signal_v6, ny_session_change_pct,
                   confidence_level, signal_correct, signal_correct_v6, pnl_v6,
                   moon_nakshatra, tithi
            FROM sbc_backtest_v6
            WHERE {where_sql}
            ORDER BY date DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])

        trades = []
        for row in cursor.fetchall():
            trade = dict(row)
            trade['date'] = str(trade['date'])
            trade['ny_session_change_pct'] = float(trade['ny_session_change_pct']) if trade['ny_session_change_pct'] else 0
            trade['pnl_v6'] = float(trade['pnl_v6']) if trade['pnl_v6'] else 0
            trades.append(trade)

        cursor.execute(f"SELECT COUNT(*) as total FROM sbc_backtest_v6 WHERE {where_sql}", params)
        total = cursor.fetchone()['total']

        conn.close()

        return {
            "trades": trades,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error getting V6 backtest trades: {e}")
        return {"error": str(e)}


@app.get("/api/sbc/backtest-v6/equity-curve")
async def get_sbc_v6_equity_curve():
    """Get V6 equity curve data for charting."""
    import psycopg2
    import psycopg2.extras
    try:
        conn = psycopg2.connect(dbname='robo_trader')
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("""
            SELECT date, ny_session_change_pct, signal_v6, signal_correct_v6, pnl_v6
            FROM sbc_backtest_v6
            WHERE should_trade = 'YES'
            ORDER BY date
        """)

        rows = cursor.fetchall()
        conn.close()

        equity = 100
        equity_curve = []

        for row in rows:
            pnl = float(row['pnl_v6']) if row['pnl_v6'] else 0
            equity *= (1 + pnl / 100)
            equity_curve.append({
                "date": str(row['date']),
                "equity": round(equity, 2),
                "pnl": round(pnl, 2),
                "signal": row['signal_v6'],
                "correct": row['signal_correct_v6'] == 'YES'
            })

        return {"equity_curve": equity_curve}
    except Exception as e:
        logger.error(f"Error getting V6 equity curve: {e}")
        return {"error": str(e)}


@app.post("/api/sbc/custom")
async def get_custom_sbc_analysis(request: CustomSBCRequest):
    """Get custom SBC analysis for any person on any date."""
    try:
        analysis = calculate_custom_sbc_analysis(
            name=request.name,
            birth_date=request.birth_date,
            birth_time=request.birth_time,
            latitude=request.latitude,
            longitude=request.longitude,
            analysis_date=request.analysis_date,
            analysis_time=request.analysis_time,
            timezone=request.timezone
        )
        # Debug logging
        logger.info(f"vedha_weights in analysis: {'vedha_weights' in analysis}")
        if 'vedha_weights' in analysis:
            vw = analysis['vedha_weights']
            logger.info(f"vedha_weights positive_weight: {vw.get('positive_weight')}")
        return convert_numpy_types(analysis)
    except Exception as e:
        logger.error(f"Error getting custom SBC analysis: {e}")
        return {"error": str(e)}


@app.get("/api/sbc/forecast")
async def get_sbc_forecast(days: int = 7):
    """Get vedha weight forecast for the next N days with optimal trade timing."""
    try:
        forecast = forecast_vedha_weights(days=days)
        return convert_numpy_types(forecast)
    except Exception as e:
        logger.error(f"Error getting SBC forecast: {e}")
        return {"error": str(e)}


@app.get("/api/sbc/forecast/hourly")
async def get_sbc_hourly_forecast(date: str = None, hours: int = 24):
    """Get hourly vedha weight forecast for intraday trade timing."""
    try:
        forecast = forecast_hourly_vedha_weights(target_date=date, hours=hours)
        return convert_numpy_types(forecast)
    except Exception as e:
        logger.error(f"Error getting hourly SBC forecast: {e}")
        return {"error": str(e)}


# ================== NY SESSION ANALYSIS API ==================

NY_SESSION_CSV = Path(__file__).parent.parent / "btc_sbc_ny_session_2025.csv"


@app.get("/sbc/ny-analysis", response_class=HTMLResponse)
async def ny_session_analysis_page(request: Request):
    """Serve NY Session Analysis dashboard."""
    return templates.TemplateResponse("ny_session_analysis.html", {"request": request})


@app.get("/api/sbc/ny-session-analysis")
async def get_ny_session_analysis():
    """Get NY session analysis data with statistics."""
    try:
        if not NY_SESSION_CSV.exists():
            return {"error": "NY session data file not found. Run generate_btc_sbc_ny_session.py first."}

        df = pd.read_csv(NY_SESSION_CSV)

        # Calculate overall stats
        total = len(df)
        correct = (df['signal_correct'] == 'YES').sum()
        overall_accuracy = round(correct / total * 100, 1) if total > 0 else 0

        # By signal type
        signal_stats = {}
        for sig in df['signal'].unique():
            sig_df = df[df['signal'] == sig]
            sig_correct = (sig_df['signal_correct'] == 'YES').sum()
            sig_total = len(sig_df)
            signal_stats[sig] = {
                'total': sig_total,
                'correct': sig_correct,
                'accuracy': round(sig_correct / sig_total * 100, 1) if sig_total > 0 else 0,
                'avg_change': round(sig_df['ny_session_change_pct'].mean(), 2)
            }

        # By day of week
        day_stats = {}
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
            day_df = df[df['day_of_week'] == day]
            if len(day_df) > 0:
                day_correct = (day_df['signal_correct'] == 'YES').sum()
                day_total = len(day_df)
                day_stats[day] = {
                    'total': day_total,
                    'correct': day_correct,
                    'accuracy': round(day_correct / day_total * 100, 1),
                    'avg_change': round(day_df['ny_session_change_pct'].mean(), 2)
                }

        # Monthly stats
        df['month'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m')
        monthly_stats = {}
        for month in df['month'].unique():
            month_df = df[df['month'] == month]
            month_correct = (month_df['signal_correct'] == 'YES').sum()
            month_total = len(month_df)
            monthly_stats[month] = {
                'total': month_total,
                'correct': month_correct,
                'accuracy': round(month_correct / month_total * 100, 1),
                'avg_change': round(month_df['ny_session_change_pct'].mean(), 2)
            }

        # Trading simulation
        bullish_days = df[df['signal'].str.contains('BULLISH')]
        bearish_days = df[df['signal'].str.contains('BEARISH')]
        bull_return = bullish_days['ny_session_change_pct'].sum()
        bear_return = -bearish_days['ny_session_change_pct'].sum()
        total_return = bull_return + bear_return
        bnh = ((df.iloc[-1]['ny_close'] - df.iloc[0]['ny_open']) / df.iloc[0]['ny_open']) * 100

        # Convert dataframe to records for table
        records = df.to_dict('records')

        # Panchang factor analysis
        panchang_stats = {}
        factors = ['nakshatra', 'tithi', 'rashi', 'akshara', 'swara']
        for factor in factors:
            pos_col = f'{factor}_positive'
            neg_col = f'{factor}_negative'

            has_pos = df[df[pos_col] != '-']
            has_neg = df[df[neg_col] != '-']

            panchang_stats[factor] = {
                'positive_days': len(has_pos),
                'positive_avg': round(has_pos['ny_session_change_pct'].mean(), 2) if len(has_pos) > 0 else 0,
                'negative_days': len(has_neg),
                'negative_avg': round(has_neg['ny_session_change_pct'].mean(), 2) if len(has_neg) > 0 else 0
            }

        # Calculate Paksha (Waxing/Waning Moon phase)
        df_sorted = df.sort_values('date').copy()
        paksha_list = []
        current_paksha = None

        for idx, row in df_sorted.iterrows():
            tithi = str(row['tithi']) if pd.notna(row['tithi']) else ''
            if 'Purnima' in tithi:
                paksha_list.append('Shukla')
                current_paksha = 'Krishna'
            elif 'Amavasya' in tithi:
                paksha_list.append('Krishna')
                current_paksha = 'Shukla'
            elif current_paksha:
                paksha_list.append(current_paksha)
            else:
                paksha_list.append('Unknown')

        df_sorted['paksha'] = paksha_list

        # Fix unknown values
        first_known_idx = df_sorted[df_sorted['paksha'] != 'Unknown'].index
        if len(first_known_idx) > 0:
            first_tithi = str(df_sorted.loc[first_known_idx[0], 'tithi'])
            if 'Purnima' in first_tithi:
                df_sorted.loc[df_sorted['paksha'] == 'Unknown', 'paksha'] = 'Shukla'
            elif 'Amavasya' in first_tithi:
                df_sorted.loc[df_sorted['paksha'] == 'Unknown', 'paksha'] = 'Krishna'

        # Paksha statistics
        paksha_analysis = {}
        for paksha in ['Shukla', 'Krishna']:
            paksha_df = df_sorted[df_sorted['paksha'] == paksha]
            if len(paksha_df) > 0:
                pos_days = len(paksha_df[paksha_df['ny_session_change_pct'] > 0])
                neg_days = len(paksha_df[paksha_df['ny_session_change_pct'] < 0])
                paksha_analysis[paksha] = {
                    'name': 'Waxing (Shukla)' if paksha == 'Shukla' else 'Waning (Krishna)',
                    'moon_nature': 'Benefic' if paksha == 'Shukla' else 'Malefic',
                    'total_days': len(paksha_df),
                    'up_days': pos_days,
                    'down_days': neg_days,
                    'avg_change': round(paksha_df['ny_session_change_pct'].mean(), 3),
                    'expected': 'Bullish' if paksha == 'Shukla' else 'Bearish'
                }

        # Moon analysis by Paksha
        moon_by_paksha = {}
        for paksha in ['Shukla', 'Krishna']:
            paksha_df = df_sorted[df_sorted['paksha'] == paksha]
            moon_pos = paksha_df[
                paksha_df['nakshatra_positive'].str.contains('Moon', na=False) |
                paksha_df['tithi_positive'].str.contains('Moon', na=False) |
                paksha_df['rashi_positive'].str.contains('Moon', na=False) |
                paksha_df['akshara_positive'].str.contains('Moon', na=False) |
                paksha_df['swara_positive'].str.contains('Moon', na=False)
            ]
            moon_neg = paksha_df[
                paksha_df['nakshatra_negative'].str.contains('Moon', na=False) |
                paksha_df['tithi_negative'].str.contains('Moon', na=False) |
                paksha_df['rashi_negative'].str.contains('Moon', na=False) |
                paksha_df['akshara_negative'].str.contains('Moon', na=False) |
                paksha_df['swara_negative'].str.contains('Moon', na=False)
            ]

            pos_avg = round(moon_pos['ny_session_change_pct'].mean(), 3) if len(moon_pos) > 0 else 0
            neg_avg = round(moon_neg['ny_session_change_pct'].mean(), 3) if len(moon_neg) > 0 else 0

            # Check if Moon is working correctly
            if paksha == 'Shukla':
                correct = pos_avg > 0  # Benefic Moon +vedha should be positive
            else:
                correct = neg_avg < 0  # Malefic Moon -vedha should be negative

            moon_by_paksha[paksha] = {
                'paksha_name': 'Waxing' if paksha == 'Shukla' else 'Waning',
                'moon_nature': 'Benefic' if paksha == 'Shukla' else 'Malefic',
                'positive_vedha_days': len(moon_pos),
                'positive_vedha_avg': pos_avg,
                'negative_vedha_days': len(moon_neg),
                'negative_vedha_avg': neg_avg,
                'working_correctly': correct
            }

        # Planet vedha analysis (excluding Moon - handled separately)
        benefics = ['Jupiter', 'Venus', 'Mercury']  # Moon handled by paksha
        malefics = ['Saturn', 'Mars', 'Rahu', 'Ketu', 'Sun']
        all_planets = ['Sun', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu', 'Ketu']

        planet_stats = {}
        for planet in all_planets:
            pos_mask = (df['nakshatra_positive'].str.contains(planet, na=False) |
                        df['tithi_positive'].str.contains(planet, na=False) |
                        df['rashi_positive'].str.contains(planet, na=False) |
                        df['akshara_positive'].str.contains(planet, na=False) |
                        df['swara_positive'].str.contains(planet, na=False))

            neg_mask = (df['nakshatra_negative'].str.contains(planet, na=False) |
                        df['tithi_negative'].str.contains(planet, na=False) |
                        df['rashi_negative'].str.contains(planet, na=False) |
                        df['akshara_negative'].str.contains(planet, na=False) |
                        df['swara_negative'].str.contains(planet, na=False))

            pos_days = df[pos_mask]
            neg_days = df[neg_mask]
            is_benefic = planet in benefics

            pos_avg = round(pos_days['ny_session_change_pct'].mean(), 3) if len(pos_days) > 0 else 0
            neg_avg = round(neg_days['ny_session_change_pct'].mean(), 3) if len(neg_days) > 0 else 0

            # Check for reversal
            reversal = False
            if is_benefic and pos_avg < 0:
                reversal = True
            if not is_benefic and neg_avg > 0:
                reversal = True

            planet_stats[planet] = {
                'type': 'benefic' if is_benefic else 'malefic',
                'positive_days': len(pos_days),
                'positive_avg': pos_avg,
                'negative_days': len(neg_days),
                'negative_avg': neg_avg,
                'reversal': reversal
            }

        # Add Moon with paksha breakdown
        planet_stats['Moon'] = {
            'type': 'conditional',
            'note': 'Benefic when Waxing, Malefic when Waning',
            'waxing': moon_by_paksha.get('Shukla', {}),
            'waning': moon_by_paksha.get('Krishna', {}),
            'reversal': False  # Moon works correctly when paksha is considered
        }

        # Retrograde analysis
        retrograde_stats = {}
        for planet in ['Mars', 'Jupiter', 'Saturn', 'Mercury', 'Venus']:
            retro_days = df[df['retrograde_planets'].str.contains(planet, na=False)]
            direct_days = df[~df['retrograde_planets'].str.contains(planet, na=False)]

            if len(retro_days) > 5:
                retrograde_stats[planet] = {
                    'retro_days': len(retro_days),
                    'retro_avg': round(retro_days['ny_session_change_pct'].mean(), 2),
                    'direct_days': len(direct_days),
                    'direct_avg': round(direct_days['ny_session_change_pct'].mean(), 2)
                }

        return convert_numpy_types({
            'summary': {
                'total_days': total,
                'correct': correct,
                'accuracy': overall_accuracy,
                'date_range': f"{df['date'].min()} to {df['date'].max()}"
            },
            'signal_stats': signal_stats,
            'day_stats': day_stats,
            'monthly_stats': monthly_stats,
            'trading_simulation': {
                'follow_signals': round(total_return, 2),
                'buy_and_hold': round(bnh, 2),
                'bullish_trades': len(bullish_days),
                'bearish_trades': len(bearish_days),
                'bull_return': round(bull_return, 2),
                'bear_return': round(bear_return, 2)
            },
            'panchang_stats': panchang_stats,
            'paksha_analysis': paksha_analysis,
            'moon_by_paksha': moon_by_paksha,
            'planet_stats': planet_stats,
            'retrograde_stats': retrograde_stats,
            'records': records
        })
    except Exception as e:
        logger.error(f"Error getting NY session analysis: {e}")
        return {"error": str(e)}


# ================== STRATEGIES API ==================

STRATEGIES_FILE = Path(__file__).parent.parent / "strategies.json"


def load_strategies():
    """Load strategies from JSON file."""
    if STRATEGIES_FILE.exists():
        with open(STRATEGIES_FILE, "r") as f:
            data = json.load(f)
            return data.get("strategies", {})
    return {}


def save_strategies(strategies: dict):
    """Save strategies to JSON file."""
    with open(STRATEGIES_FILE, "w") as f:
        json.dump({"strategies": strategies}, f, indent=2)


@app.get("/api/strategies")
async def get_strategies():
    """Get all strategies."""
    strategies = load_strategies()
    return {"strategies": strategies}


@app.get("/api/strategies/{strategy_id}")
async def get_strategy(strategy_id: str):
    """Get a specific strategy by ID."""
    strategies = load_strategies()
    if strategy_id not in strategies:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"id": strategy_id, **strategies[strategy_id]}


class StrategyData(BaseModel):
    """Strategy data model."""
    name: str
    description: str = ""
    direction: str = "BOTH"
    rules: str


@app.put("/api/strategies/{strategy_id}")
async def save_strategy(strategy_id: str, data: StrategyData):
    """Create or update a strategy."""
    strategies = load_strategies()
    strategies[strategy_id] = {
        "name": data.name,
        "description": data.description,
        "direction": data.direction,
        "rules": data.rules
    }
    save_strategies(strategies)
    return {"success": True, "id": strategy_id}


@app.delete("/api/strategies/{strategy_id}")
async def delete_strategy(strategy_id: str):
    """Delete a strategy."""
    strategies = load_strategies()
    if strategy_id not in strategies:
        raise HTTPException(status_code=404, detail="Strategy not found")
    del strategies[strategy_id]
    save_strategies(strategies)
    return {"success": True}


class BacktestConfig(BaseModel):
    """Configuration for strategy backtest."""
    strategy: str
    days: int = 5
    start_date: str = "2025-10-01"
    trades_per_day: int = 3
    capital: float = 2000
    risk_percent: float = 0.5


@app.post("/api/backtest")
async def run_backtest(config: BacktestConfig):
    """Run backtest for a strategy."""
    import subprocess
    import re

    try:
        # Run backtest script as subprocess
        result = subprocess.run(
            [
                "python", "backtest_ai.py",
                config.strategy,
                str(config.days),
                str(config.trades_per_day),
                str(config.capital),
                str(config.risk_percent),
                config.start_date
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(Path(__file__).parent.parent)
        )

        output = result.stdout + result.stderr

        # Parse results from output
        trades = re.search(r'Trades Executed:\s+(\d+)', output)
        wins = re.search(r'^Wins:\s+(\d+)', output, re.MULTILINE)
        losses = re.search(r'^Losses:\s+(\d+)', output, re.MULTILINE)
        winrate = re.search(r'Win Rate:\s+([\d.]+)%', output)
        total_r = re.search(r'Total R-Multiple:\s+([\+\-]?[\d.]+)R', output)
        roi = re.search(r'^ROI:\s+([\+\-]?[\d.]+)%', output, re.MULTILINE)

        # Parse individual trades from the TRADE LOG section
        # Format: #    Date           Entry        SL        TP Dir    Outcome R         P/L       Cum R
        # Example: 2    10-16 08:00    $  110,800 $  111,389 $  110,071 SHORT  LOSS    -1.0R    $-10.00    -1.0R
        trade_list = []
        trade_pattern = re.compile(
            r'^(\d+)\s+'                              # Trade number
            r'(\d{2}-\d{2}\s+\d{2}:\d{2})\s+'         # Date (MM-DD HH:MM)
            r'\$\s*([\d,]+)\s+'                       # Entry price (with optional spaces after $)
            r'(?:\$\s*([\d,]+)|---)\s+'               # Stop Loss
            r'(?:\$\s*([\d,]+)|---)\s+'               # Take Profit
            r'(LONG|SHORT|SKIP|ERR)\s+'               # Direction
            r'(WIN|LOSS|BE|OPEN|INVLD|---)\s+'        # Outcome
            r'([\+\-]?[\d.]+R|---)\s+'                # R-multiple
            r'(\$[\+\-]?[\d,.]+|---)\s+'              # P/L
            r'([\+\-]?[\d.]+R)',                      # Cumulative R
            re.MULTILINE
        )

        for match in trade_pattern.finditer(output):
            trade_num = int(match.group(1))
            date_str = match.group(2)
            entry = match.group(3).replace(',', '') if match.group(3) else None
            sl = match.group(4).replace(',', '') if match.group(4) else None
            tp = match.group(5).replace(',', '') if match.group(5) else None
            direction = match.group(6)
            outcome = match.group(7)
            r_mult = match.group(8)
            pnl = match.group(9)
            cum_r = match.group(10)

            # Include all trades (executed and skipped) so user can see full picture
            trade_list.append({
                "num": trade_num,
                "date": date_str,
                "entry": float(entry) if entry else None,
                "stop_loss": float(sl) if sl else None,
                "take_profit": float(tp) if tp else None,
                "direction": direction,
                "outcome": outcome,
                "r_multiple": r_mult,
                "pnl": pnl,
                "cumulative_r": cum_r
            })

        return {
            "trades": int(trades.group(1)) if trades else 0,
            "wins": int(wins.group(1)) if wins else 0,
            "losses": int(losses.group(1)) if losses else 0,
            "win_rate": float(winrate.group(1)) if winrate else 0,
            "total_r": float(total_r.group(1)) if total_r else 0,
            "roi": float(roi.group(1)) if roi else 0,
            "trade_list": trade_list,
            "raw_output": output
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Backtest timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AIBacktestConfig(BaseModel):
    """Configuration for AI recommendation backtest."""
    capital: float = 2000
    riskPercent: float = 0.5
    startDate: str = "2025-10-01"
    numDays: int = 31
    tradesPerDay: int = 10
    symbol: str = "BTC/USDT"


@app.post("/api/ai-backtest")
async def run_ai_backtest(config: AIBacktestConfig):
    """Run AI recommendation backtest using historical data."""
    import subprocess
    import json as json_module

    try:
        # Run backtest script as subprocess
        result = subprocess.run(
            [
                "python", "backtest_ai.py",
                str(config.numDays),
                str(config.tradesPerDay),
                str(config.capital),
                str(config.riskPercent),
                config.startDate
            ],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            cwd=str(Path(__file__).parent.parent)
        )

        if result.returncode != 0:
            logger.error(f"Backtest failed: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"Backtest failed: {result.stderr[:500]}")

        # Parse output to extract results
        import re
        output = result.stdout
        lines = output.split('\n')

        # Parse trade results from output
        results = []
        summary = {
            "totalTrades": 0,
            "wins": 0,
            "losses": 0,
            "skipped": 0,
            "totalR": 0,
            "winRate": 0,
            "maxDrawdown": 0,
            "longTrades": 0,
            "longWins": 0,
            "shortTrades": 0,
            "shortWins": 0
        }

        in_trades = False
        # Trade line pattern: "1    10-31 20:00      $ 109,494 STRONG SELL  SHORT  LOSS       -1.0R    -1.0R"
        trade_pattern = re.compile(
            r'^\s*(\d+)\s+'                       # Trade number
            r'(\d{2}-\d{2}\s+\d{2}:\d{2})\s+'    # Date time
            r'\$\s*([\d,]+)\s+'                   # Price
            r'(STRONG\s+BUY|STRONG\s+SELL|BUY|SELL)\s+'  # Signal
            r'(LONG|SHORT|SKIP)\s+'               # Direction
            r'(WIN|LOSS|BE|OPEN|---)\s+'          # Outcome
            r'([\d.+-]+R|---)\s+'                 # R multiple
            r'([\d.+-]+R)'                        # Cumulative R
        )

        for line in lines:
            # Check for header line to start parsing trades
            if '#' in line and 'Date' in line and 'Price' in line:
                in_trades = True
                continue

            if in_trades and line.strip() and not line.startswith('-') and not line.startswith('='):
                match = trade_pattern.match(line)
                if match:
                    try:
                        trade_num = int(match.group(1))
                        date = match.group(2)
                        price = float(match.group(3).replace(',', ''))
                        signal = match.group(4).replace('  ', ' ')
                        direction = match.group(5)
                        outcome = match.group(6)
                        r_str = match.group(7).replace('R', '').replace('+', '')

                        r_mult = float(r_str) if r_str != '---' else 0

                        results.append({
                            "date": date,
                            "price": price,
                            "signal": signal,
                            "direction": direction,
                            "outcome": outcome if outcome != '---' else 'N/A',
                            "rMultiple": r_mult
                        })

                        if direction in ['LONG', 'SHORT'] and outcome not in ['---', 'SKIP', 'BE']:
                            summary["totalTrades"] += 1
                            if direction == 'LONG':
                                summary["longTrades"] += 1
                                if outcome == 'WIN':
                                    summary["longWins"] += 1
                            elif direction == 'SHORT':
                                summary["shortTrades"] += 1
                                if outcome == 'WIN':
                                    summary["shortWins"] += 1

                            if outcome == 'WIN':
                                summary["wins"] += 1
                            elif outcome == 'LOSS':
                                summary["losses"] += 1

                            summary["totalR"] += r_mult
                        elif direction == 'SKIP' or outcome == '---':
                            summary["skipped"] += 1
                        elif outcome == 'BE':
                            # Breakeven trades - count in total but not wins/losses
                            summary["totalTrades"] += 1
                            if direction == 'LONG':
                                summary["longTrades"] += 1
                            elif direction == 'SHORT':
                                summary["shortTrades"] += 1

                    except (ValueError, IndexError) as e:
                        logger.debug(f"Failed to parse trade line: {line} - {e}")
                        continue

            # Check for summary stats (fallback)
            if 'Win Rate:' in line and '%' in line:
                try:
                    wr_match = re.search(r'Win Rate:\s*([\d.]+)%', line)
                    if wr_match:
                        summary["winRate"] = float(wr_match.group(1))
                except:
                    pass
            if 'Total R-Multiple:' in line:
                try:
                    tr_match = re.search(r'Total R-Multiple:\s*([+-]?[\d.]+)R', line)
                    if tr_match:
                        summary["totalR"] = float(tr_match.group(1))
                except:
                    pass
            if 'Max Drawdown:' in line and 'R)' in line:
                try:
                    # Extract R value from "Max Drawdown: $xxx.xx (yy.yR)"
                    md_match = re.search(r'\(([\d.]+)R\)', line)
                    if md_match:
                        summary["maxDrawdown"] = float(md_match.group(1))
                except:
                    pass

        if summary["totalTrades"] > 0 and summary["winRate"] == 0:
            summary["winRate"] = (summary["wins"] / summary["totalTrades"]) * 100

        return {
            "results": results,
            "summary": summary,
            "rawOutput": output[-2000:] if len(output) > 2000 else output  # Last 2000 chars for debugging
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Backtest timed out after 10 minutes")
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve original dashboard."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/api/status")
async def get_status():
    """Get current trading status."""
    return {
        "is_trading": state.is_trading,
        "trading_mode": state.trading_mode,
        "active_symbols": state.active_symbols,
        "model_loaded": state.model is not None,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/orderbook/{symbol:path}")
async def get_orderbook(symbol: str, limit: int = 25):
    """Get order book (depth) data for a symbol.

    Args:
        symbol: Trading pair (e.g., BTC/USD)
        limit: Number of price levels on each side (max 100)
    """
    try:
        if not state.exchange:
            return {"error": "Exchange not initialized", "bids": [], "asks": []}

        limit = min(limit, 100)

        # Fetch order book using CCXT
        orderbook = await run_in_executor(
            state.exchange.fetch_order_book,
            symbol,
            limit
        )

        if not orderbook:
            return {"bids": [], "asks": [], "symbol": symbol}

        return {
            "bids": orderbook.get("bids", [])[:limit],
            "asks": orderbook.get("asks", [])[:limit],
            "symbol": symbol,
            "timestamp": orderbook.get("timestamp"),
            "datetime": orderbook.get("datetime")
        }

    except Exception as e:
        return {"error": str(e), "bids": [], "asks": [], "symbol": symbol}


@app.get("/api/candles/{symbol:path}")
async def get_candles(symbol: str, timeframe: str = "1h", limit: int = 500, before: int = None):
    """Get historical candle data for charting.

    Args:
        symbol: Trading pair (e.g., BTC/USD)
        timeframe: Candle timeframe (1m, 5m, 15m, 1h, 4h, 1d)
        limit: Number of candles to return (max 1000)
        before: Unix timestamp (seconds) - fetch candles before this time for infinite scroll
    """
    try:
        if not state.data_fetcher:
            # Initialize data fetcher if not available
            if state.config and state.exchange:
                state.data_fetcher = DataFetcher(state.exchange)
            else:
                return {"error": "Data fetcher not initialized", "candles": []}

        limit = min(limit, 1000)

        # Calculate 'since' datetime for fetching older data
        since_dt = None
        if before is not None:
            # Convert timeframe to seconds
            timeframe_seconds = {
                '1m': 60,
                '2m': 2 * 60,
                '5m': 5 * 60,
                '15m': 15 * 60,
                '30m': 30 * 60,
                '1h': 60 * 60,
                '4h': 4 * 60 * 60,
                '1d': 24 * 60 * 60,
                '1w': 7 * 24 * 60 * 60,
                '1M': 30 * 24 * 60 * 60,
                '1y': 365 * 24 * 60 * 60,
            }.get(timeframe, 60 * 60)

            # Calculate since: go back 'limit' candles from 'before'
            # 'before' is Unix timestamp in seconds from frontend
            since_timestamp = before - (limit * timeframe_seconds)
            since_dt = datetime.fromtimestamp(since_timestamp)

        # Always use Binance for candle data (better historical data and more symbols)
        # Fall back to Kraken only if Binance doesn't have the symbol
        logger.info(f"Fetching candle data from Binance for {symbol} (timeframe={timeframe}, before={before})")
        df = await run_in_executor(
            state.data_fetcher.fetch_ohlcv_binance,
            symbol,
            timeframe,
            since_dt,
            limit
        )

        # If Binance returns empty (symbol not found), try Kraken
        if df is None or df.empty:
            logger.info(f"Binance returned empty, trying Kraken for {symbol}")
            try:
                df = await run_in_executor(
                    state.data_fetcher.fetch_ohlcv,
                    symbol,
                    timeframe,
                    since_dt,
                    limit
                )
            except Exception as e:
                logger.warning(f"Kraken also failed for {symbol}: {e}")
                df = None

        if df is None or df.empty:
            return {"candles": [], "symbol": symbol, "timeframe": timeframe}

        # Filter to only include candles strictly before the 'before' timestamp
        # This prevents duplicates when loading historical data for infinite scroll
        # Use Unix timestamp comparison to avoid timezone issues
        if before is not None:
            # Convert index to Unix timestamp (seconds) for comparison
            df = df[df.index.map(lambda x: x.timestamp()) < before]

        # Convert DataFrame to list of candle objects
        candles = []
        for idx, row in df.iterrows():
            candles.append({
                "timestamp": idx.isoformat() if hasattr(idx, 'isoformat') else str(idx),
                "time": int(idx.timestamp()) if hasattr(idx, 'timestamp') else 0,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            })
        return {
            "candles": candles,
            "symbol": symbol,
            "timeframe": timeframe,
            "count": len(candles)
        }

    except Exception as e:
        return {"error": str(e), "candles": [], "symbol": symbol}


@app.get("/api/ohlc/{symbol}")
async def get_daily_ohlc(symbol: str, date: str, timezone: str = None):
    """Get OHLC data for a specific date in the given timezone (00:00 to 23:59).

    Args:
        symbol: Trading pair or instrument symbol (e.g., BTC, ETH, GOLD, NIFTY)
        date: Date in YYYY-MM-DD format
        timezone: Timezone name (e.g., 'America/New_York', 'Asia/Kolkata', 'Europe/London')
                  If not provided, uses UTC
    """
    import aiohttp
    from datetime import datetime, timedelta
    import pytz

    try:
        # Parse the date
        target_date = datetime.strptime(date, '%Y-%m-%d')

        # Check if date is in the future
        today = datetime.now()
        if target_date.date() > today.date():
            return {"error": "Cannot fetch OHLC data for future dates", "is_future": True}

        # Timezone display names
        timezone_names = {
            'America/New_York': 'New York (EST/EDT)',
            'Asia/Kolkata': 'India (IST)',
            'Europe/London': 'London (GMT/BST)',
            'UTC': 'UTC'
        }

        # Symbol mapping for different data sources
        crypto_symbols = {
            'BTC': 'BTCUSDT',
            'ETH': 'ETHUSDT',
            'SOL': 'SOLUSDT',
            'XRP': 'XRPUSDT',
            'ADA': 'ADAUSDT',
            'DOGE': 'DOGEUSDT',
            'DOT': 'DOTUSDT',
            'LINK': 'LINKUSDT',
        }

        # For crypto, use Binance API with timezone-adjusted times
        if symbol.upper() in crypto_symbols:
            binance_symbol = crypto_symbols[symbol.upper()]

            if timezone:
                try:
                    # Get the timezone
                    tz = pytz.timezone(timezone)

                    # Create start of day (00:00) in the given timezone
                    local_start = tz.localize(target_date.replace(hour=0, minute=0, second=0, microsecond=0))
                    # Create end of day (23:59:59) in the given timezone
                    local_end = tz.localize(target_date.replace(hour=23, minute=59, second=59, microsecond=0))

                    # Convert to UTC timestamps
                    start_time = int(local_start.astimezone(pytz.UTC).timestamp() * 1000)
                    end_time = int(local_end.astimezone(pytz.UTC).timestamp() * 1000)

                    tz_display = timezone_names.get(timezone, timezone)
                except Exception as tz_error:
                    logger.warning(f"Timezone error: {tz_error}, falling back to UTC")
                    start_time = int(target_date.timestamp() * 1000)
                    end_time = int((target_date + timedelta(days=1)).timestamp() * 1000)
                    tz_display = "UTC"
            else:
                # Default to UTC
                start_time = int(target_date.timestamp() * 1000)
                end_time = int((target_date + timedelta(days=1)).timestamp() * 1000)
                tz_display = "UTC"

            # Fetch hourly data for the full day in the timezone
            url = "https://api.binance.com/api/v3/klines"
            params = {
                'symbol': binance_symbol,
                'interval': '1h',
                'startTime': start_time,
                'endTime': end_time,
                'limit': 25
            }

            async with aiohttp.ClientSession() as http_session:
                async with http_session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and len(data) > 0:
                            # Calculate OHLC from hourly candles
                            open_price = float(data[0][1])
                            high_price = max(float(k[2]) for k in data)
                            low_price = min(float(k[3]) for k in data)
                            close_price = float(data[-1][4])
                            volume = sum(float(k[5]) for k in data)

                            return {
                                "symbol": symbol.upper(),
                                "date": date,
                                "open": open_price,
                                "high": high_price,
                                "low": low_price,
                                "close": close_price,
                                "volume": volume,
                                "timezone": tz_display,
                                "source": "Binance"
                            }
                        else:
                            return {"error": f"No data found for {symbol} on {date}", "symbol": symbol}
                    else:
                        return {"error": f"Binance API error: {response.status}", "symbol": symbol}

        # For stocks and indices, use Yahoo Finance
        yahoo_symbols = {
            'NIFTY': '^NSEI',
            'SENSEX': '^BSESN',
            'SPX': '^GSPC',
            'DJI': '^DJI',
            'NASDAQ': '^IXIC',
            'GOLD': 'GC=F',
            'XAU': 'GC=F',
            'SILVER': 'SI=F',
            'XAG': 'SI=F',
            'CRUDE_OIL': 'CL=F',
            'CL': 'CL=F',
            'NATURAL_GAS': 'NG=F',
            'NG': 'NG=F',
            'COPPER': 'HG=F',
            'HG': 'HG=F',
            # Indian stocks
            'RELIANCE': 'RELIANCE.NS',
            'TCS': 'TCS.NS',
            'INFY': 'INFY.NS',
            'HDFC': 'HDFCBANK.NS',
            'ICICI': 'ICICIBANK.NS',
            # US stocks
            'AAPL': 'AAPL',
            'MSFT': 'MSFT',
            'GOOGL': 'GOOGL',
            'AMZN': 'AMZN',
            'TSLA': 'TSLA',
            'META': 'META',
            'NVDA': 'NVDA',
        }

        yahoo_symbol = yahoo_symbols.get(symbol.upper(), symbol.upper())

        # Get timezone display name
        tz_display = timezone_names.get(timezone, timezone) if timezone else "UTC"

        # Yahoo Finance API - for stocks we use daily data
        period1 = int(target_date.timestamp())
        period2 = int((target_date + timedelta(days=1)).timestamp())

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        params = {
            'period1': period1,
            'period2': period2,
            'interval': '1d'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        async with aiohttp.ClientSession() as http_session:
            async with http_session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get('chart', {}).get('result', [])
                    if result and len(result) > 0:
                        quote = result[0].get('indicators', {}).get('quote', [{}])[0]
                        if quote.get('open') and len(quote.get('open', [])) > 0:
                            return {
                                "symbol": symbol.upper(),
                                "date": date,
                                "open": quote['open'][0],
                                "high": quote['high'][0],
                                "low": quote['low'][0],
                                "close": quote['close'][0],
                                "volume": quote.get('volume', [0])[0],
                                "timezone": tz_display,
                                "source": "Yahoo Finance"
                            }
                        else:
                            return {"error": f"No data found for {symbol} on {date}", "symbol": symbol}
                    else:
                        return {"error": f"No data found for {symbol} on {date}", "symbol": symbol}
                else:
                    return {"error": f"Yahoo Finance API error: {response.status}", "symbol": symbol}

    except Exception as e:
        logger.error(f"Error fetching OHLC for {symbol} on {date}: {e}")
        return {"error": str(e), "symbol": symbol}


@app.get("/api/account")
async def get_account(filter_mode: Optional[str] = None):
    """Get account information - aggregates from all running bots.

    Args:
        filter_mode: Optional filter - 'paper', 'live', or 'all' (default)
    """
    total_equity = 0
    total_pnl = 0
    total_positions = 0
    active_bots = 0
    paper_bots = 0
    live_bots = 0
    modes = set()

    def get_bot_mode(bot):
        """Get the mode of a bot as a string."""
        if hasattr(bot, 'mode'):
            return bot.mode.value if hasattr(bot.mode, 'value') else str(bot.mode)
        return "paper"

    def should_include_bot(bot):
        """Check if bot should be included based on filter."""
        if filter_mode is None or filter_mode == "all":
            return True
        bot_mode = get_bot_mode(bot)
        return bot_mode == filter_mode

    # Aggregate from scalping bot
    if state.scalping_bot and state.scalping_bot.status and state.scalping_bot.status.value == "running":
        bot_mode = get_bot_mode(state.scalping_bot)
        if bot_mode == "paper":
            paper_bots += 1
        else:
            live_bots += 1
        if should_include_bot(state.scalping_bot):
            total_equity += float(state.scalping_bot.capital or 0)
            if hasattr(state.scalping_bot, 'stats') and state.scalping_bot.stats:
                total_pnl += float(getattr(state.scalping_bot.stats, 'total_pnl', 0) or 0)
            active_bots += 1
            modes.add(bot_mode)

    # Aggregate from short term bot
    if state.short_term_bot and state.short_term_bot.status and state.short_term_bot.status.value == "running":
        bot_mode = get_bot_mode(state.short_term_bot)
        if bot_mode == "paper":
            paper_bots += 1
        else:
            live_bots += 1
        if should_include_bot(state.short_term_bot):
            total_equity += float(state.short_term_bot.capital or 0)
            if hasattr(state.short_term_bot, 'stats') and state.short_term_bot.stats:
                total_pnl += float(getattr(state.short_term_bot.stats, 'total_pnl', 0) or 0)
            active_bots += 1
            modes.add(bot_mode)

    # Aggregate from swing bot
    if state.swing_bot and state.swing_bot.status and state.swing_bot.status.value == "running":
        bot_mode = get_bot_mode(state.swing_bot)
        if bot_mode == "paper":
            paper_bots += 1
        else:
            live_bots += 1
        if should_include_bot(state.swing_bot):
            total_equity += float(state.swing_bot.capital or 0)
            if hasattr(state.swing_bot, 'stats') and state.swing_bot.stats:
                total_pnl += float(getattr(state.swing_bot.stats, 'total_pnl', 0) or 0)
            active_bots += 1
            modes.add(bot_mode)

    # Aggregate from long term bot
    if state.long_term_bot and state.long_term_bot.status and state.long_term_bot.status.value == "running":
        bot_mode = get_bot_mode(state.long_term_bot)
        if bot_mode == "paper":
            paper_bots += 1
        else:
            live_bots += 1
        if should_include_bot(state.long_term_bot):
            total_equity += float(state.long_term_bot.capital or 0)
            if hasattr(state.long_term_bot, 'stats') and state.long_term_bot.stats:
                total_pnl += float(getattr(state.long_term_bot.stats, 'total_pnl', 0) or 0)
            active_bots += 1
            modes.add(bot_mode)

    # Determine mode (paper, live, or mixed)
    if len(modes) == 0:
        mode = "none"
    elif len(modes) == 1:
        mode = list(modes)[0]
    else:
        mode = "mixed"

    # If we have bot data, return aggregated values
    if total_equity > 0 or active_bots > 0:
        return {
            "cash": float(total_equity),
            "equity": float(total_equity),
            "total_pnl": float(total_pnl),
            "daily_pnl": float(total_pnl),  # For now, using total as daily
            "positions": int(total_positions),
            "mode": mode,
            "active_bots": int(active_bots),
            "paper_bots": int(paper_bots),
            "live_bots": int(live_bots)
        }

    # Fallback to paper trader if available
    if state.paper_trader and (filter_mode is None or filter_mode == "all" or filter_mode == "paper"):
        return {
            "cash": state.paper_trader.account.cash,
            "equity": state.paper_trader.account.equity,
            "total_pnl": state.paper_trader.account.total_pnl,
            "daily_pnl": state.paper_trader.account.daily_pnl,
            "positions": len(state.paper_trader.account.positions),
            "mode": "paper",
            "active_bots": 0,
            "paper_bots": paper_bots,
            "live_bots": live_bots
        }

    # Try to get real balance from exchange
    try:
        if state.exchange and (filter_mode is None or filter_mode == "all" or filter_mode == "live"):
            balance = state.exchange.fetch_balance()
            usdt = balance.get("USDT", {})
            return {
                "cash": usdt.get("free", 0),
                "equity": usdt.get("total", 0),
                "total_pnl": 0,
                "daily_pnl": 0,
                "positions": 0,
                "mode": "live",
                "active_bots": 0,
                "paper_bots": paper_bots,
                "live_bots": live_bots
            }
    except:
        pass

    # Default fallback
    return {
        "cash": 0,
        "equity": 0,
        "total_pnl": 0,
        "daily_pnl": 0,
        "positions": 0,
        "mode": "none",
        "active_bots": 0,
        "paper_bots": paper_bots,
        "live_bots": live_bots
    }


@app.get("/api/positions")
async def get_positions():
    """Get current positions from all bots."""
    all_positions = []

    # Get positions from scalping bot
    if state.scalping_bot and hasattr(state.scalping_bot, 'positions'):
        for pos_id, pos in state.scalping_bot.positions.items():
            all_positions.append({
                "bot": "Scalping",
                "bot_type": "scalping",
                "symbol": state.scalping_bot.symbol,
                "side": pos.side,
                "size": pos.size,
                "entry_price": pos.entry_price,
                "take_profit": getattr(pos, 'take_profit', None),
                "stop_loss": getattr(pos, 'stop_loss', None),
                "unrealized_pnl": getattr(pos, 'unrealized_pnl', 0),
                "mode": state.scalping_bot.mode.value if state.scalping_bot.mode else "paper"
            })

    # Get positions from short term bot
    if state.short_term_bot and hasattr(state.short_term_bot, 'positions'):
        for pos_id, pos in state.short_term_bot.positions.items():
            all_positions.append({
                "bot": "Short Term",
                "bot_type": "short-term",
                "symbol": state.short_term_bot.symbol,
                "side": pos.side,
                "size": pos.size,
                "entry_price": pos.entry_price,
                "take_profit": getattr(pos, 'take_profit', None),
                "stop_loss": getattr(pos, 'stop_loss', None),
                "unrealized_pnl": getattr(pos, 'unrealized_pnl', 0),
                "mode": state.short_term_bot.mode.value if hasattr(state.short_term_bot, 'mode') and state.short_term_bot.mode else "paper"
            })

    # Get positions from swing bot
    if state.swing_bot and hasattr(state.swing_bot, 'positions'):
        for pos_id, pos in state.swing_bot.positions.items():
            all_positions.append({
                "bot": "Swing",
                "bot_type": "swing",
                "symbol": state.swing_bot.symbol,
                "side": pos.side,
                "size": pos.size,
                "entry_price": pos.entry_price,
                "take_profit": getattr(pos, 'take_profit', None),
                "stop_loss": getattr(pos, 'stop_loss', None),
                "unrealized_pnl": getattr(pos, 'unrealized_pnl', 0),
                "mode": state.swing_bot.mode.value if hasattr(state.swing_bot, 'mode') and state.swing_bot.mode else "paper"
            })

    # Get positions from long term bot
    if state.long_term_bot and hasattr(state.long_term_bot, 'positions'):
        for pos_id, pos in state.long_term_bot.positions.items():
            all_positions.append({
                "bot": "Long Term",
                "bot_type": "long-term",
                "symbol": state.long_term_bot.symbol,
                "side": pos.side,
                "size": pos.size,
                "entry_price": pos.entry_price,
                "take_profit": getattr(pos, 'take_profit', None),
                "stop_loss": getattr(pos, 'stop_loss', None),
                "unrealized_pnl": getattr(pos, 'unrealized_pnl', 0),
                "mode": state.long_term_bot.mode.value if hasattr(state.long_term_bot, 'mode') and state.long_term_bot.mode else "paper"
            })

    # Fallback to paper_trader positions if no bot positions
    if not all_positions and state.paper_trader:
        for symbol, pos in state.paper_trader.account.positions.items():
            all_positions.append({
                "bot": "Paper Trader",
                "bot_type": "paper",
                "symbol": symbol,
                "side": pos.side,
                "size": pos.size,
                "entry_price": pos.entry_price,
                "take_profit": None,
                "stop_loss": None,
                "unrealized_pnl": pos.unrealized_pnl,
                "mode": "paper"
            })

    return {"positions": all_positions}


@app.get("/api/trades")
async def get_trades(limit: int = 50):
    """Get recent trades from database (scalp trades with P&L + regular trades)."""
    all_trades = []

    if state.storage:
        # Get scalp trades (with full P&L info) - prioritize these
        try:
            scalp_df = state.storage.get_scalp_trades(limit=limit)
            if not scalp_df.empty:
                for _, row in scalp_df.iterrows():
                    all_trades.append({
                        "id": row.get("id"),
                        "symbol": row.get("symbol"),
                        "side": row.get("side"),
                        "entry_price": row.get("entry_price"),
                        "exit_price": row.get("exit_price"),
                        "amount": row.get("amount"),
                        "pnl": row.get("pnl"),
                        "pnl_pct": row.get("pnl_pct"),
                        "timestamp": row.get("timestamp"),
                        "exit_reason": row.get("exit_reason"),
                        "duration": row.get("duration_seconds"),
                        "is_paper": bool(row.get("is_paper", 1)),
                        "source": "scalping_bot"
                    })
        except Exception as e:
            print(f"Error getting scalp trades: {e}")

        # Get regular trades (legacy format without P&L)
        trades_df = state.storage.get_trades(limit=limit)
        if not trades_df.empty:
            for _, row in trades_df.iterrows():
                all_trades.append({
                    "id": row.get("id"),
                    "symbol": row.get("symbol"),
                    "side": row.get("side"),
                    "price": row.get("price"),
                    "amount": row.get("amount"),
                    "timestamp": row.get("timestamp"),
                    "is_paper": bool(row.get("is_paper", 1)),
                    "source": "legacy"
                })

    # Also include in-memory scalping bot trades (not yet saved)
    if state.scalping_bot and state.scalping_bot.trades:
        for t in state.scalping_bot.trades:
            all_trades.append({
                "id": t.id,
                "symbol": t.symbol,
                "side": t.side,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "amount": t.size,
                "pnl": t.pnl,
                "pnl_pct": t.pnl_pct,
                "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                "exit_reason": t.exit_reason,
                "duration": t.duration_seconds,
                "is_paper": True,
                "source": "scalping_bot_memory"
            })

    return {"trades": all_trades}


@app.get("/api/prices/{symbol}")
async def get_prices(symbol: str, limit: int = 100, timeframe: str = None, days_back: int = None):
    """Get price data for charting.

    Args:
        symbol: Trading pair (e.g., BTC-USDT)
        limit: Number of candles (if days_back not specified)
        timeframe: Candle timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d)
        days_back: Number of days of historical data to fetch (overrides limit)
    """
    try:
        symbol = symbol.replace("-", "/")
        # Use provided timeframe or fall back to config
        if timeframe is None:
            timeframe = state.config.get("trading", {}).get("timeframe", "1h")

        # Validate timeframe
        valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
        if timeframe not in valid_timeframes:
            timeframe = "1h"

        # If days_back is specified, use fetch_historical_data for extended history
        if days_back is not None and days_back > 0:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            # Run in thread pool since this can take time
            df = await run_in_executor(
                state.data_fetcher.fetch_historical_data,
                symbol,
                timeframe,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )
        else:
            df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=limit)

        if df.empty:
            return {"error": "No data available"}

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "count": len(df),
            "data": [
                {
                    "time": row.name.isoformat(),
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"]
                }
                for _, row in df.iterrows()
            ]
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/ticker/{symbol:path}")
async def get_ticker(symbol: str):
    """Get current ticker data."""
    try:
        symbol = symbol.replace("-", "/")
        ticker = state.data_fetcher.fetch_ticker(symbol)
        return ticker
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/aggressor-ratio/{symbol:path}")
async def get_aggressor_ratio(symbol: str, limit: int = 500):
    """
    Get aggressor ratio analysis from recent market trades.

    The aggressor ratio measures the proportion of buy-initiated vs sell-initiated trades.
    - Ratio > 1: More aggressive buying (bullish pressure)
    - Ratio < 1: More aggressive selling (bearish pressure)
    - Ratio ≈ 1: Balanced market

    Returns detailed breakdown with volume-weighted analysis.
    """
    try:
        symbol = symbol.replace("-", "/")

        if not state.data_fetcher:
            return {"error": "Data fetcher not initialized"}

        # Fetch recent market trades
        trades = state.data_fetcher.fetch_market_trades(symbol, limit=limit)

        if not trades:
            return {"error": "No trade data available"}

        # Calculate aggressor metrics
        buy_count = sum(1 for t in trades if t['side'] == 'buy')
        sell_count = sum(1 for t in trades if t['side'] == 'sell')
        total_count = len(trades)

        buy_volume = sum(t['amount'] for t in trades if t['side'] == 'buy')
        sell_volume = sum(t['amount'] for t in trades if t['side'] == 'sell')
        total_volume = buy_volume + sell_volume

        buy_value = sum(t['cost'] for t in trades if t['side'] == 'buy' and t['cost'])
        sell_value = sum(t['cost'] for t in trades if t['side'] == 'sell' and t['cost'])
        total_value = buy_value + sell_value

        # Calculate ratios (avoid division by zero)
        count_ratio = buy_count / sell_count if sell_count > 0 else float('inf')
        volume_ratio = buy_volume / sell_volume if sell_volume > 0 else float('inf')
        value_ratio = buy_value / sell_value if sell_value > 0 else float('inf')

        # Calculate percentages
        buy_pct = (buy_count / total_count * 100) if total_count > 0 else 0
        sell_pct = (sell_count / total_count * 100) if total_count > 0 else 0
        buy_vol_pct = (buy_volume / total_volume * 100) if total_volume > 0 else 0
        sell_vol_pct = (sell_volume / total_volume * 100) if total_volume > 0 else 0

        # Determine sentiment
        if volume_ratio > 1.2:
            sentiment = "BULLISH"
            sentiment_strength = min((volume_ratio - 1) * 50, 100)
        elif volume_ratio < 0.8:
            sentiment = "BEARISH"
            sentiment_strength = min((1 - volume_ratio) * 50, 100)
        else:
            sentiment = "NEUTRAL"
            sentiment_strength = 50

        # Time range of trades
        if trades:
            oldest_trade = min(t['timestamp'] for t in trades if t['timestamp'])
            newest_trade = max(t['timestamp'] for t in trades if t['timestamp'])
            time_span_minutes = (newest_trade - oldest_trade) / 60000 if oldest_trade and newest_trade else 0
        else:
            time_span_minutes = 0

        # Average trade sizes
        avg_buy_size = buy_volume / buy_count if buy_count > 0 else 0
        avg_sell_size = sell_volume / sell_count if sell_count > 0 else 0

        return {
            "symbol": symbol,
            "total_trades": total_count,
            "time_span_minutes": round(time_span_minutes, 1),

            # Count-based metrics
            "buy_count": buy_count,
            "sell_count": sell_count,
            "count_ratio": round(count_ratio, 3) if count_ratio != float('inf') else None,
            "buy_pct": round(buy_pct, 1),
            "sell_pct": round(sell_pct, 1),

            # Volume-based metrics
            "buy_volume": round(buy_volume, 6),
            "sell_volume": round(sell_volume, 6),
            "total_volume": round(total_volume, 6),
            "volume_ratio": round(volume_ratio, 3) if volume_ratio != float('inf') else None,
            "buy_vol_pct": round(buy_vol_pct, 1),
            "sell_vol_pct": round(sell_vol_pct, 1),

            # Value-based metrics (USD)
            "buy_value": round(buy_value, 2),
            "sell_value": round(sell_value, 2),
            "total_value": round(total_value, 2),
            "value_ratio": round(value_ratio, 3) if value_ratio != float('inf') else None,

            # Average sizes
            "avg_buy_size": round(avg_buy_size, 6),
            "avg_sell_size": round(avg_sell_size, 6),

            # Sentiment
            "sentiment": sentiment,
            "sentiment_strength": round(sentiment_strength, 1),

            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/ai-analysis/{symbol:path}")
async def get_ai_analysis(symbol: str, request: Request):
    """
    Get AI-powered market analysis using Gemini (primary) or Claude (fallback).

    Sends current market data to AI and receives intelligent analysis
    with trading recommendations.
    """
    # Check for available AI providers
    gemini_key = os.getenv("GEMINI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if not GEMINI_AVAILABLE and not ANTHROPIC_AVAILABLE:
        return {"error": "No AI SDK installed. Run: pip install google-generativeai anthropic"}

    if not gemini_key and not anthropic_key:
        return {"error": "No AI API key configured. Set GEMINI_API_KEY or ANTHROPIC_API_KEY in .env"}

    try:
        symbol = symbol.replace("-", "/")

        # Get request body with market data
        body = await request.json()

        # Extract data from request (using names from JavaScript)
        aggressor_data = body.get("aggressor_ratio", {})
        market_analysis = body.get("market_analysis", {})
        factors = body.get("factors", {})
        performance = body.get("performance", {})
        global_stats = body.get("global_stats", {})
        technical_analysis = body.get("technical_analysis", {})
        current_price = body.get("current_price", "N/A")

        # NEW: Extract additional comprehensive data
        ticker_24h = body.get("ticker_24h", {})
        orderbook_depth = body.get("orderbook_depth", {})
        signal_analysis = body.get("signal_analysis", {})

        # Extract key levels from technical analysis
        key_levels = technical_analysis.get("key_levels", {})
        ta_summary = technical_analysis.get("summary", {})
        oscillators = technical_analysis.get("oscillators", [])
        moving_averages = technical_analysis.get("moving_averages", [])

        # Format moving averages and oscillators for prompt
        ma_text = "\n".join([f"  - {ma.get('name')}: ${ma.get('value')} ({ma.get('signal')})" for ma in moving_averages]) if moving_averages else "N/A"
        osc_text = "\n".join([f"  - {osc.get('name')}: {osc.get('value')} ({osc.get('signal')})" for osc in oscillators]) if oscillators else "N/A"

        # Format bid/ask walls
        bid_walls = orderbook_depth.get("bid_walls", [])
        ask_walls = orderbook_depth.get("ask_walls", [])
        bid_walls_text = "\n".join([f"    - ${w.get('price')}: {w.get('size'):.4f} BTC" for w in bid_walls]) if bid_walls else "    - None detected"
        ask_walls_text = "\n".join([f"    - ${w.get('price')}: {w.get('size'):.4f} BTC" for w in ask_walls]) if ask_walls else "    - None detected"

        # Format signal conflicts
        conflicts = signal_analysis.get("conflicts", [])
        conflicts_text = "\n".join([f"  - {c.get('signal1')} vs {c.get('signal2')} (Severity: {c.get('severity')})" for c in conflicts]) if conflicts else "  - No conflicts detected"

        # Format signals summary
        signals_summary = signal_analysis.get("signals_summary", [])
        signals_text = "\n".join([f"  - {s.get('source')}: {s.get('signal')}" for s in signals_summary]) if signals_summary else "  - No signals available"

        # Format global stats numbers safely
        market_cap = global_stats.get('market_cap')
        market_cap_str = f"${market_cap:,.0f}" if market_cap else "N/A"
        volume_24h = global_stats.get('volume_24h')
        volume_24h_str = f"${volume_24h:,.0f}" if volume_24h else "N/A"
        ath_val = global_stats.get('ath')
        ath_str = f"${ath_val:,.2f}" if ath_val else "N/A"

        # Format orderbook values safely
        ob_bid_vol = orderbook_depth.get('total_bid_volume_usd')
        ob_bid_str = f"${ob_bid_vol:,.0f}" if ob_bid_vol else "N/A"
        ob_ask_vol = orderbook_depth.get('total_ask_volume_usd')
        ob_ask_str = f"${ob_ask_vol:,.0f}" if ob_ask_vol else "N/A"

        # Build the prompt with all market data
        prompt = f"""You are an expert cryptocurrency trader and quantitative analyst. You have been provided with COMPREHENSIVE real-time market data for {symbol} from multiple sources. Your job is to synthesize ALL this data - even when signals contradict each other - and provide clear, actionable trading recommendations.

IMPORTANT: Some indicators may conflict (e.g., RSI oversold while price is below all moving averages). This is normal. Your expertise is in weighing these factors and explaining your reasoning.

═══════════════════════════════════════════════════════════════════
## 📊 PRICE & MARKET DATA
═══════════════════════════════════════════════════════════════════

### Current Price
- **Price**: ${current_price}
- **24h High**: ${ticker_24h.get('high', 'N/A')}
- **24h Low**: ${ticker_24h.get('low', 'N/A')}
- **24h Change**: {ticker_24h.get('change_percent', performance.get('24h', {}).get('change', 'N/A'))}%
- **24h Volume**: {ticker_24h.get('volume', 'N/A')} BTC
- **VWAP**: ${ticker_24h.get('vwap', 'N/A')}
- **Bid/Ask Spread**: {ticker_24h.get('spread', 'N/A')}%

### Multi-Timeframe Performance
- 24H: {performance.get('24h', {}).get('change', 'N/A')}% | Volatility: {performance.get('24h', {}).get('volatility', 'N/A')}% | Trend: {performance.get('24h', {}).get('trend', 'N/A')}
- 1 Week: {performance.get('1w', {}).get('change', 'N/A')}% | Volatility: {performance.get('1w', {}).get('volatility', 'N/A')}% | Trend: {performance.get('1w', {}).get('trend', 'N/A')}
- 1 Month: {performance.get('1m', {}).get('change', 'N/A')}% | Volatility: {performance.get('1m', {}).get('volatility', 'N/A')}% | Trend: {performance.get('1m', {}).get('trend', 'N/A')}

═══════════════════════════════════════════════════════════════════
## 📈 TECHNICAL ANALYSIS
═══════════════════════════════════════════════════════════════════

### Overall Technical Signal: **{technical_analysis.get('overall_signal', 'N/A')}**
- Moving Averages: {ta_summary.get('moving_averages', {}).get('buy', 0)} BUY / {ta_summary.get('moving_averages', {}).get('neutral', 0)} NEUTRAL / {ta_summary.get('moving_averages', {}).get('sell', 0)} SELL
- Oscillators: {ta_summary.get('oscillators', {}).get('buy', 0)} BUY / {ta_summary.get('oscillators', {}).get('neutral', 0)} NEUTRAL / {ta_summary.get('oscillators', {}).get('sell', 0)} SELL

### Oscillators (Momentum)
{osc_text}

### Moving Averages (Trend)
{ma_text}

### Key Price Levels (Based on ATR: ${key_levels.get('atr', 'N/A')})
- **Support 1**: ${key_levels.get('support_1', 'N/A')} (1 ATR below)
- **Support 2**: ${key_levels.get('support_2', 'N/A')} (2 ATR below)
- **Resistance 1**: ${key_levels.get('resistance_1', 'N/A')} (1 ATR above)
- **Resistance 2**: ${key_levels.get('resistance_2', 'N/A')} (2 ATR above)
- **SMA 20**: ${key_levels.get('sma_20', 'N/A')}
- **SMA 50**: ${key_levels.get('sma_50', 'N/A')}
- **SMA 200**: ${key_levels.get('sma_200', 'N/A')}

═══════════════════════════════════════════════════════════════════
## 📊 ORDER FLOW & DEPTH ANALYSIS
═══════════════════════════════════════════════════════════════════

### Orderbook Depth (Top 50 levels)
- **Total Bid Volume**: {ob_bid_str}
- **Total Ask Volume**: {ob_ask_str}
- **Imbalance**: {orderbook_depth.get('imbalance_percent', 'N/A')}% ({orderbook_depth.get('imbalance_signal', 'N/A')})
- **Best Bid**: ${orderbook_depth.get('best_bid', 'N/A')}
- **Best Ask**: ${orderbook_depth.get('best_ask', 'N/A')}
- **Spread**: {orderbook_depth.get('spread_percent', 'N/A')}%

### Bid Walls (Large buy orders - support):
{bid_walls_text}

### Ask Walls (Large sell orders - resistance):
{ask_walls_text}

### Aggressor Ratio (Last {aggressor_data.get('total_trades', 'N/A')} trades over {aggressor_data.get('time_span_minutes', 'N/A')} minutes)
- **Real-time Sentiment**: {aggressor_data.get('sentiment', 'N/A')} (Strength: {aggressor_data.get('sentiment_strength', 'N/A')}%)
- **Buy Volume**: {aggressor_data.get('buy_vol_pct', 'N/A')}%
- **Sell Volume**: {aggressor_data.get('sell_vol_pct', 'N/A')}%
- **Volume Ratio (Buy/Sell)**: {aggressor_data.get('volume_ratio', 'N/A')}

═══════════════════════════════════════════════════════════════════
## 🎯 SIGNAL SYNTHESIS & CONFLICTS
═══════════════════════════════════════════════════════════════════

### All Signals Summary:
{signals_text}

### Signal Conflicts Detected ({signal_analysis.get('conflict_count', 0)} conflicts):
{conflicts_text}

### Computed Consensus: **{signal_analysis.get('consensus', 'N/A')}** (Strength: {signal_analysis.get('consensus_strength', 'N/A')}/2.0)

### Market Analysis Summary
- Signal: {market_analysis.get('signal', 'N/A')}
- Confidence: {market_analysis.get('confidence', 'N/A')}%
- Summary: {market_analysis.get('summary', 'N/A')}

═══════════════════════════════════════════════════════════════════
## 🌍 GLOBAL MARKET CONTEXT
═══════════════════════════════════════════════════════════════════
- Market Cap: {market_cap_str}
- 24h Global Volume: {volume_24h_str}
- All-Time High: {ath_str} ({global_stats.get('ath_change_percentage', 'N/A')}% from ATH)

═══════════════════════════════════════════════════════════════════
## 🎯 YOUR ANALYSIS TASK
═══════════════════════════════════════════════════════════════════

Synthesize ALL the data above. Pay special attention to:
1. **Conflicting signals** - explain which you give more weight to and why
2. **Order flow** - orderbook imbalance and aggressor ratio show real-time buyer/seller pressure
3. **Technical vs Flow divergence** - when technicals say one thing but order flow says another
4. **Key levels** - use the calculated support/resistance for precise entries and stops

CRITICAL REQUIREMENT: All trade setups MUST have a MINIMUM Risk:Reward ratio of 1:3. This means Take Profit must be at least 3x the distance from Entry to Stop Loss. Adjust your entries, stops, and targets accordingly to achieve this.

Provide your analysis in this exact format:

### 📊 MARKET SYNTHESIS
(2-3 sentences explaining how you weigh the conflicting signals. Which data points are most significant right now and why?)

### ⚡ SHORT-TERM TRADE (Scalp/Day - 15min to 4hr)

| Parameter | Value |
|-----------|-------|
| Direction | LONG / SHORT / NO TRADE |
| Entry | $[exact price] |
| Stop Loss | $[exact price] ([X]% risk) |
| Take Profit 1 | $[exact price] |
| Take Profit 2 | $[exact price] |
| Risk:Reward | 1:[X] (MUST be ≥1:3) |
| Confidence | Low / Medium / High |

**Rationale**: [1 sentence why]

### 📈 SWING TRADE (1-5 days)

| Parameter | Value |
|-----------|-------|
| Direction | LONG / SHORT / NO TRADE |
| Entry | $[exact price] |
| Stop Loss | $[exact price] ([X]% risk) |
| Take Profit 1 | $[exact price] |
| Take Profit 2 | $[exact price] |
| Risk:Reward | 1:[X] (MUST be ≥1:3) |
| Confidence | Low / Medium / High |

**Rationale**: [1 sentence why]

### 🎯 LONG-TERM POSITION (1 week - 1 month)

| Parameter | Value |
|-----------|-------|
| Direction | LONG / SHORT / WAIT |
| Entry Zone | $[low] - $[high] |
| Stop Loss | $[exact price] |
| Target | $[exact price] |
| Risk:Reward | 1:[X] (MUST be ≥1:3) |
| Confidence | Low / Medium / High |

**Rationale**: [1 sentence why]

### ⚠️ KEY RISKS
| # | Risk | Impact |
|---|------|--------|
| 1 | [Bullish invalidation risk] | [What happens] |
| 2 | [Bearish invalidation risk] | [What happens] |
| 3 | [External/macro risk] | [What happens] |

### 💡 ACTIONABLE INSIGHT
(One clear, specific action the trader should take RIGHT NOW based on all this data)

Current price: ${current_price}"""

        # Try Gemini first (usually has free tier), then fall back to Claude
        response_text = None
        model_used = None

        # Try Gemini
        if GEMINI_AVAILABLE and gemini_key:
            try:
                genai.configure(api_key=gemini_key)
                # Use gemini-2.0-flash (fast and capable)
                model = genai.GenerativeModel('gemini-2.0-flash')
                response = model.generate_content(prompt)
                response_text = response.text
                model_used = "gemini-2.0-flash"
            except Exception as e:
                logger.warning(f"Gemini API error: {e}, trying Claude...")

        # Fall back to Claude if Gemini failed
        if not response_text and ANTHROPIC_AVAILABLE and anthropic_key:
            try:
                client = anthropic.Anthropic(api_key=anthropic_key)
                message = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1500,
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = message.content[0].text
                model_used = "claude-sonnet-4-20250514"
            except Exception as e:
                return {"error": f"Claude API error: {str(e)}"}

        if not response_text:
            return {"error": "All AI providers failed. Check your API keys and account status."}

        return {
            "success": True,
            "symbol": symbol,
            "analysis": response_text,
            "model": model_used,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        return {"error": str(e)}


# ============================================================
# TARS - AI Trading Assistant Endpoints
# ============================================================

class TARSChatRequest(BaseModel):
    """Request model for TARS chat."""
    message: str
    context: Optional[Dict] = None


@app.post("/api/tars/chat")
async def tars_chat(request: TARSChatRequest):
    """
    Chat with TARS - the AI trading assistant.

    Send a message and receive an AI-powered response with
    optional actions (draw on chart, place trades, etc.)
    """
    try:
        tars = get_tars()

        # Build context from current state
        context = request.context or {}

        # Add current market data to context if not provided
        if "current_price" not in context and state.data_fetcher:
            try:
                ticker = state.exchange.fetch_ticker("BTC/USD")
                context["current_price"] = ticker.get("last", 0)
                context["symbol"] = "BTC/USD"
            except:
                pass

        # Add trading state
        if state.is_trading:
            context["trading_mode"] = state.trading_mode

        # Process message
        response = await tars.process_message(request.message, context)

        return {
            "message": response.message,
            "actions": response.actions,
            "suggestions": response.suggestions,
            "data": response.data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"TARS chat error: {e}")
        return {
            "message": f"I encountered an error: {str(e)}. Please try again.",
            "actions": [],
            "suggestions": ["Try again", "Check connection"],
            "error": str(e)
        }


@app.post("/api/tars/clear")
async def tars_clear_history():
    """Clear TARS conversation history."""
    try:
        tars = get_tars()
        tars.clear_history()
        return {"status": "ok", "message": "Conversation history cleared"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/tars/status")
async def tars_status():
    """Get TARS status and capabilities."""
    try:
        tars = get_tars()
        return {
            "status": "online",
            "provider": tars.provider,
            "conversation_length": len(tars.conversation_history),
            "capabilities": [
                "market_data",
                "strategy_explanation",
                "ict_concepts",
                "trading_commands",
                "chart_drawing",
                "price_alerts"
            ],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/technical-analysis/{symbol:path}")
async def get_technical_analysis(symbol: str, timeframe: str = "1h"):
    """
    Get comprehensive technical analysis with moving averages and oscillators.
    Returns indicator values and trading signals similar to Kraken Pro.
    """
    try:
        symbol = symbol.replace("-", "/")

        # Fetch OHLCV data
        df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=200)

        if df.empty:
            return {"error": "No data available"}

        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        current_price = float(close[-1])

        # Import indicator functions
        from features.pine_script.functions import BuiltinFunctions as bf

        # Calculate Moving Averages
        sma_10 = bf.sma(close, 10)
        sma_20 = bf.sma(close, 20)
        sma_30 = bf.sma(close, 30)
        sma_50 = bf.sma(close, 50)
        sma_100 = bf.sma(close, 100)
        sma_200 = bf.sma(close, 200)

        ema_10 = bf.ema(close, 10)
        ema_20 = bf.ema(close, 20)
        ema_30 = bf.ema(close, 30)
        ema_50 = bf.ema(close, 50)
        ema_100 = bf.ema(close, 100)
        ema_200 = bf.ema(close, 200)

        # Calculate Oscillators
        rsi_14 = bf.rsi(close, 14)
        macd_line, macd_signal, macd_hist = bf.macd(close, 12, 26, 9)
        stoch_k = bf.stoch(high, low, close, 14)
        stoch_d = bf.sma(stoch_k, 3)
        atr_14 = bf.atr(high, low, close, 14)

        # Helper to get signal based on price vs MA
        def ma_signal(ma_value, price):
            if np.isnan(ma_value):
                return "NEUTRAL"
            return "BUY" if price > ma_value else "SELL"

        # Helper to count signals
        def count_signals(signals):
            buy = sum(1 for s in signals if s == "BUY")
            sell = sum(1 for s in signals if s == "SELL")
            neutral = sum(1 for s in signals if s == "NEUTRAL")
            return {"buy": buy, "sell": sell, "neutral": neutral}

        # Build moving averages with signals
        moving_averages = [
            {"name": "SMA (10)", "value": round(float(sma_10[-1]), 2) if not np.isnan(sma_10[-1]) else None, "signal": ma_signal(sma_10[-1], current_price)},
            {"name": "EMA (10)", "value": round(float(ema_10[-1]), 2) if not np.isnan(ema_10[-1]) else None, "signal": ma_signal(ema_10[-1], current_price)},
            {"name": "SMA (20)", "value": round(float(sma_20[-1]), 2) if not np.isnan(sma_20[-1]) else None, "signal": ma_signal(sma_20[-1], current_price)},
            {"name": "EMA (20)", "value": round(float(ema_20[-1]), 2) if not np.isnan(ema_20[-1]) else None, "signal": ma_signal(ema_20[-1], current_price)},
            {"name": "SMA (30)", "value": round(float(sma_30[-1]), 2) if not np.isnan(sma_30[-1]) else None, "signal": ma_signal(sma_30[-1], current_price)},
            {"name": "EMA (30)", "value": round(float(ema_30[-1]), 2) if not np.isnan(ema_30[-1]) else None, "signal": ma_signal(ema_30[-1], current_price)},
            {"name": "SMA (50)", "value": round(float(sma_50[-1]), 2) if not np.isnan(sma_50[-1]) else None, "signal": ma_signal(sma_50[-1], current_price)},
            {"name": "EMA (50)", "value": round(float(ema_50[-1]), 2) if not np.isnan(ema_50[-1]) else None, "signal": ma_signal(ema_50[-1], current_price)},
            {"name": "SMA (100)", "value": round(float(sma_100[-1]), 2) if not np.isnan(sma_100[-1]) else None, "signal": ma_signal(sma_100[-1], current_price)},
            {"name": "EMA (100)", "value": round(float(ema_100[-1]), 2) if not np.isnan(ema_100[-1]) else None, "signal": ma_signal(ema_100[-1], current_price)},
            {"name": "SMA (200)", "value": round(float(sma_200[-1]), 2) if not np.isnan(sma_200[-1]) else None, "signal": ma_signal(sma_200[-1], current_price)},
            {"name": "EMA (200)", "value": round(float(ema_200[-1]), 2) if not np.isnan(ema_200[-1]) else None, "signal": ma_signal(ema_200[-1], current_price)},
        ]

        # Oscillator signals
        rsi_val = float(rsi_14[-1]) if not np.isnan(rsi_14[-1]) else 50
        rsi_signal = "SELL" if rsi_val > 70 else ("BUY" if rsi_val < 30 else "NEUTRAL")

        macd_val = float(macd_hist[-1]) if not np.isnan(macd_hist[-1]) else 0
        macd_sig = "BUY" if macd_val > 0 else "SELL"

        stoch_val = float(stoch_k[-1]) if not np.isnan(stoch_k[-1]) else 50
        stoch_signal = "SELL" if stoch_val > 80 else ("BUY" if stoch_val < 20 else "NEUTRAL")

        oscillators = [
            {"name": "RSI (14)", "value": round(rsi_val, 2), "signal": rsi_signal},
            {"name": "MACD", "value": round(macd_val, 2), "signal": macd_sig},
            {"name": "MACD Signal", "value": round(float(macd_signal[-1]), 2) if not np.isnan(macd_signal[-1]) else None, "signal": macd_sig},
            {"name": "Stochastic %K", "value": round(stoch_val, 2), "signal": stoch_signal},
            {"name": "Stochastic %D", "value": round(float(stoch_d[-1]), 2) if not np.isnan(stoch_d[-1]) else None, "signal": stoch_signal},
        ]

        # Calculate overall strength
        ma_signals = [ma["signal"] for ma in moving_averages]
        osc_signals = [osc["signal"] for osc in oscillators]
        all_signals = ma_signals + osc_signals

        ma_summary = count_signals(ma_signals)
        osc_summary = count_signals(osc_signals)
        overall_summary = count_signals(all_signals)

        # Determine overall signal
        if overall_summary["buy"] > overall_summary["sell"] + 3:
            overall_signal = "STRONG BUY"
        elif overall_summary["buy"] > overall_summary["sell"]:
            overall_signal = "BUY"
        elif overall_summary["sell"] > overall_summary["buy"] + 3:
            overall_signal = "STRONG SELL"
        elif overall_summary["sell"] > overall_summary["buy"]:
            overall_signal = "SELL"
        else:
            overall_signal = "NEUTRAL"

        # Calculate key support/resistance levels
        atr_value = float(atr_14[-1]) if not np.isnan(atr_14[-1]) else current_price * 0.02

        # Key levels for trading
        key_levels = {
            "current_price": round(current_price, 2),
            "atr": round(atr_value, 2),
            "support_1": round(current_price - atr_value, 2),
            "support_2": round(current_price - (2 * atr_value), 2),
            "resistance_1": round(current_price + atr_value, 2),
            "resistance_2": round(current_price + (2 * atr_value), 2),
            "sma_20": round(float(sma_20[-1]), 2) if not np.isnan(sma_20[-1]) else None,
            "sma_50": round(float(sma_50[-1]), 2) if not np.isnan(sma_50[-1]) else None,
            "sma_200": round(float(sma_200[-1]), 2) if not np.isnan(sma_200[-1]) else None,
        }

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "current_price": round(current_price, 2),
            "overall_signal": overall_signal,
            "summary": {
                "moving_averages": ma_summary,
                "oscillators": osc_summary,
                "overall": overall_summary
            },
            "moving_averages": moving_averages,
            "oscillators": oscillators,
            "key_levels": key_levels,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Technical analysis error: {e}")
        return {"error": str(e)}


@app.get("/api/dr-idr/{symbol}")
async def get_dr_idr(symbol: str, timeframe: str = "5m"):
    """
    Get DR/IDR (Defining Range / Initial Defining Range) levels.

    These are key intraday levels based on the first hour of trading sessions:
    - RDR: Regular session (9:30-10:30 NY)
    - ADR: After hours (19:30-20:30 NY)
    - ODR: Overnight (3:00-4:00 NY)
    """
    try:
        symbol = symbol.replace("-", "/")

        # Fetch enough data to cover the session
        df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=500)

        if df.empty:
            return {"error": "No data available"}

        # Calculate DR/IDR levels
        result = calculate_dr_idr_for_chart(
            df,
            show_dr=True,
            show_idr=True,
            show_middle_dr=False,
            show_middle_idr=True,
            show_open=True,
            show_std=True,
            std_levels_count=5
        )

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            **result
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/indicators/symbol/{symbol}")
async def get_indicators(symbol: str):
    """Get technical indicators for a symbol."""
    try:
        symbol = symbol.replace("-", "/")
        timeframe = state.config.get("trading", {}).get("timeframe", "1h")
        df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=200)

        if df.empty:
            return {"error": "No data"}

        df_features = state.feature_engineer.generate_features(df)
        latest = df_features.iloc[-1]

        # Get the most recent candle snapshot from database for signal counts
        db_counts = {"bullish_count": None, "bearish_count": None, "neutral_count": None, "db_prediction": None, "explanation": None}
        try:
            from data.database import DatabaseManager
            db = DatabaseManager()
            result = db.execute_query(
                "SELECT bullish_count, bearish_count, neutral_count, prediction, explanation FROM candle_snapshots WHERE symbol = ? ORDER BY timestamp_ny DESC LIMIT 1",
                (symbol,)
            )
            if result:
                row = result[0]
                db_counts["bullish_count"] = row[0]
                db_counts["bearish_count"] = row[1]
                db_counts["neutral_count"] = row[2]
                db_counts["db_prediction"] = row[3]
                db_counts["explanation"] = row[4]
        except Exception as e:
            print(f"Error fetching DB counts: {e}")

        return {
            "symbol": symbol,
            "timestamp": df_features.index[-1].isoformat(),
            "price": latest["close"],
            # RSI
            "rsi_14": latest.get("rsi_14"),
            "rsi_7": latest.get("rsi_7"),
            # MACD
            "macd": latest.get("macd"),
            "macd_signal": latest.get("macd_signal"),
            "macd_hist": latest.get("macd_hist"),
            # Bollinger Bands
            "bb_upper": latest.get("bb_upper"),
            "bb_middle": latest.get("bb_middle"),
            "bb_lower": latest.get("bb_lower"),
            "bb_width": latest.get("bb_width"),
            "bb_pct": latest.get("bb_pct"),
            # Moving Averages
            "ema_9": latest.get("ema_9"),
            "ema_21": latest.get("ema_21"),
            "ema_50": latest.get("ema_50"),
            "sma_20": latest.get("sma_20"),
            "sma_50": latest.get("sma_50"),
            # Stochastic
            "stoch_k": latest.get("stoch_k"),
            "stoch_d": latest.get("stoch_d"),
            # ADX (Trend Strength)
            "adx": latest.get("adx"),
            "di_plus": latest.get("di_plus"),
            "di_minus": latest.get("di_minus"),
            # Volatility
            "atr_14": latest.get("atr_14"),
            "atr_pct": latest.get("atr_pct"),
            # CCI
            "cci": latest.get("cci"),
            # Volume
            "volume_ratio": latest.get("volume_ratio"),
            "obv": latest.get("obv"),
            # VWAP
            "vwap": latest.get("vwap"),
            # Momentum
            "roc_10": latest.get("roc_10"),
            "momentum_10": latest.get("momentum_10"),
            # Database signal counts (from latest candle snapshot)
            "db_bullish_count": db_counts["bullish_count"],
            "db_bearish_count": db_counts["bearish_count"],
            "db_neutral_count": db_counts["neutral_count"],
            "db_prediction": db_counts["db_prediction"],
            "db_explanation": db_counts["explanation"]
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/signal/{symbol:path}")
async def get_signal(symbol: str):
    """Get current trading signal for a symbol."""
    if not state.strategy:
        return {"error": "Model not loaded"}

    try:
        symbol = symbol.replace("-", "/")
        timeframe = state.config.get("trading", {}).get("timeframe", "1h")
        df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=200)

        if df.empty:
            return {"error": "No data"}

        signal, confidence = state.strategy.generate_signal(df)

        return {
            "symbol": symbol,
            "signal": signal.name,
            "confidence": float(confidence),  # Convert numpy float to Python float
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error generating signal: {e}")
        return {"error": str(e)}


@app.get("/api/snapshots/{symbol}")
async def get_candle_snapshots(
    symbol: str,
    limit: int = 100,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Get historical 5-minute candle snapshots with indicators and predictions.

    Args:
        symbol: Trading pair (e.g., BTC-USDT)
        limit: Maximum records to return (default 100)
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)
    """
    try:
        symbol = symbol.replace("-", "/")
        df = state.storage.get_candle_snapshots(
            symbol=symbol,
            limit=limit,
            start_date=start_date,
            end_date=end_date
        )

        if df.empty:
            return {"snapshots": [], "count": 0}

        # Convert to list of dicts
        snapshots = df.to_dict(orient='records')

        return {
            "symbol": symbol,
            "snapshots": snapshots,
            "count": len(snapshots)
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/snapshots/{symbol}/latest")
async def get_latest_snapshot(symbol: str):
    """Get the most recent 5-minute candle snapshot for a symbol."""
    try:
        symbol = symbol.replace("-", "/")
        snapshot = state.storage.get_latest_snapshot(symbol)

        if not snapshot:
            return {"error": "No snapshots found"}

        return snapshot
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/snapshots/{symbol}/collect")
async def trigger_snapshot_collection(symbol: str):
    """Manually trigger a snapshot collection for a symbol."""
    try:
        symbol = symbol.replace("-", "/")

        if state.candle_collector is None:
            return {"error": "Candle collector not initialized"}

        # Temporarily change symbol and collect
        original_symbol = state.candle_collector.symbol
        state.candle_collector.symbol = symbol
        result = state.candle_collector.collect_snapshot()
        state.candle_collector.symbol = original_symbol

        if result:
            return {
                "status": "collected",
                "snapshot": result
            }
        else:
            return {"status": "no_new_data"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/order-blocks/{symbol}")
async def get_order_blocks(symbol: str, lookback: int = 100):
    """
    Detect order blocks and key levels (support/resistance, SL/TP zones).

    Order blocks are supply/demand zones where institutional orders are placed.
    They are identified by:
    - Large candles (body > 1.5x ATR) followed by reversal
    - High volume relative to average
    - Price zones that act as support/resistance

    SL/TP levels are calculated based on:
    - Recent swing highs/lows
    - ATR-based distances
    - Round numbers
    - Previous support/resistance levels
    """
    try:
        symbol = symbol.replace("-", "/")
        timeframe = state.config.get("trading", {}).get("timeframe", "1h")
        df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=lookback)

        if df.empty or len(df) < 20:
            return {"error": "Insufficient data"}

        import numpy as np

        # Calculate ATR for volatility reference
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        tr = high_low.combine(high_close, max).combine(low_close, max)
        atr = tr.rolling(window=14).mean().iloc[-1]

        current_price = df['close'].iloc[-1]
        avg_volume = df['volume'].rolling(window=20).mean()

        order_blocks = []
        support_levels = []
        resistance_levels = []

        # Detect Order Blocks
        for i in range(5, len(df) - 1):
            candle_body = abs(df['close'].iloc[i] - df['open'].iloc[i])
            candle_range = df['high'].iloc[i] - df['low'].iloc[i]
            volume = df['volume'].iloc[i]
            avg_vol = avg_volume.iloc[i] if not np.isnan(avg_volume.iloc[i]) else volume

            # Order block criteria:
            # 1. Large body candle (> 1.5x ATR)
            # 2. High volume (> 1.5x average)
            # 3. Followed by reversal movement
            if candle_body > atr * 1.2 and volume > avg_vol * 1.3:
                is_bullish = df['close'].iloc[i] > df['open'].iloc[i]
                next_close = df['close'].iloc[i + 1] if i + 1 < len(df) else df['close'].iloc[i]

                # Check for reversal
                if is_bullish and next_close < df['close'].iloc[i]:
                    # Bullish order block (demand zone)
                    order_blocks.append({
                        "type": "demand",
                        "high": float(df['high'].iloc[i]),
                        "low": float(df['low'].iloc[i]),
                        "timestamp": df.index[i].isoformat(),
                        "strength": min(100, int((volume / avg_vol) * 50 + (candle_body / atr) * 25)),
                        "touched": bool(df['low'].iloc[i+1:].min() <= df['high'].iloc[i])
                    })
                elif not is_bullish and next_close > df['close'].iloc[i]:
                    # Bearish order block (supply zone)
                    order_blocks.append({
                        "type": "supply",
                        "high": float(df['high'].iloc[i]),
                        "low": float(df['low'].iloc[i]),
                        "timestamp": df.index[i].isoformat(),
                        "strength": min(100, int((volume / avg_vol) * 50 + (candle_body / atr) * 25)),
                        "touched": bool(df['high'].iloc[i+1:].max() >= df['low'].iloc[i])
                    })

        # Find swing highs and lows for support/resistance
        for i in range(3, len(df) - 3):
            # Swing high - local maximum
            if df['high'].iloc[i] >= df['high'].iloc[i-3:i].max() and \
               df['high'].iloc[i] >= df['high'].iloc[i+1:i+4].max():
                resistance_levels.append({
                    "price": float(df['high'].iloc[i]),
                    "timestamp": df.index[i].isoformat(),
                    "touches": int(((df['high'] >= df['high'].iloc[i] * 0.998) &
                                   (df['high'] <= df['high'].iloc[i] * 1.002)).sum())
                })

            # Swing low - local minimum
            if df['low'].iloc[i] <= df['low'].iloc[i-3:i].min() and \
               df['low'].iloc[i] <= df['low'].iloc[i+1:i+4].min():
                support_levels.append({
                    "price": float(df['low'].iloc[i]),
                    "timestamp": df.index[i].isoformat(),
                    "touches": int(((df['low'] >= df['low'].iloc[i] * 0.998) &
                                   (df['low'] <= df['low'].iloc[i] * 1.002)).sum())
                })

        # Consolidate nearby levels (within 0.5% of each other)
        def consolidate_levels(levels, key='price'):
            if not levels:
                return []
            sorted_levels = sorted(levels, key=lambda x: x[key])
            consolidated = []
            current_group = [sorted_levels[0]]

            for level in sorted_levels[1:]:
                if level[key] <= current_group[-1][key] * 1.005:
                    current_group.append(level)
                else:
                    # Take the level with most touches
                    best = max(current_group, key=lambda x: x.get('touches', 1))
                    best['touches'] = sum(l.get('touches', 1) for l in current_group)
                    consolidated.append(best)
                    current_group = [level]

            if current_group:
                best = max(current_group, key=lambda x: x.get('touches', 1))
                best['touches'] = sum(l.get('touches', 1) for l in current_group)
                consolidated.append(best)

            return consolidated

        support_levels = consolidate_levels(support_levels)
        resistance_levels = consolidate_levels(resistance_levels)

        # Filter to most relevant levels (near current price)
        relevant_support = [s for s in support_levels if s['price'] < current_price and s['price'] > current_price * 0.9]
        relevant_resistance = [r for r in resistance_levels if r['price'] > current_price and r['price'] < current_price * 1.1]

        # Calculate suggested SL/TP levels
        sl_tp_levels = {
            "long": {
                "entry": float(current_price),
                "stop_loss": [],
                "take_profit": []
            },
            "short": {
                "entry": float(current_price),
                "stop_loss": [],
                "take_profit": []
            }
        }

        # For long positions: SL below support, TP at resistance
        if relevant_support:
            for i, sup in enumerate(sorted(relevant_support, key=lambda x: x['price'], reverse=True)[:3]):
                sl_tp_levels["long"]["stop_loss"].append({
                    "price": float(sup['price'] * 0.998),  # Just below support
                    "risk_reward": round((current_price - sup['price'] * 0.998) / current_price * 100, 2),
                    "level_type": "support",
                    "touches": sup.get('touches', 1)
                })
        else:
            # ATR-based fallback
            sl_tp_levels["long"]["stop_loss"].append({
                "price": float(current_price - 2 * atr),
                "risk_reward": round(2 * atr / current_price * 100, 2),
                "level_type": "atr_based",
                "touches": 0
            })

        if relevant_resistance:
            for i, res in enumerate(sorted(relevant_resistance, key=lambda x: x['price'])[:3]):
                sl_tp_levels["long"]["take_profit"].append({
                    "price": float(res['price'] * 0.998),  # Just below resistance
                    "reward": round((res['price'] * 0.998 - current_price) / current_price * 100, 2),
                    "level_type": "resistance",
                    "touches": res.get('touches', 1)
                })
        else:
            # ATR-based fallback
            for mult in [2, 3, 5]:
                sl_tp_levels["long"]["take_profit"].append({
                    "price": float(current_price + mult * atr),
                    "reward": round(mult * atr / current_price * 100, 2),
                    "level_type": "atr_based",
                    "touches": 0
                })

        # For short positions: SL above resistance, TP at support
        if relevant_resistance:
            for i, res in enumerate(sorted(relevant_resistance, key=lambda x: x['price'])[:3]):
                sl_tp_levels["short"]["stop_loss"].append({
                    "price": float(res['price'] * 1.002),  # Just above resistance
                    "risk_reward": round((res['price'] * 1.002 - current_price) / current_price * 100, 2),
                    "level_type": "resistance",
                    "touches": res.get('touches', 1)
                })
        else:
            sl_tp_levels["short"]["stop_loss"].append({
                "price": float(current_price + 2 * atr),
                "risk_reward": round(2 * atr / current_price * 100, 2),
                "level_type": "atr_based",
                "touches": 0
            })

        if relevant_support:
            for i, sup in enumerate(sorted(relevant_support, key=lambda x: x['price'], reverse=True)[:3]):
                sl_tp_levels["short"]["take_profit"].append({
                    "price": float(sup['price'] * 1.002),  # Just above support
                    "reward": round((current_price - sup['price'] * 1.002) / current_price * 100, 2),
                    "level_type": "support",
                    "touches": sup.get('touches', 1)
                })
        else:
            for mult in [2, 3, 5]:
                sl_tp_levels["short"]["take_profit"].append({
                    "price": float(current_price - mult * atr),
                    "reward": round(mult * atr / current_price * 100, 2),
                    "level_type": "atr_based",
                    "touches": 0
                })

        # Keep only recent/strong order blocks
        recent_order_blocks = sorted(order_blocks, key=lambda x: x['strength'], reverse=True)[:10]

        return {
            "symbol": symbol,
            "current_price": float(current_price),
            "atr": float(atr),
            "order_blocks": recent_order_blocks,
            "support_levels": sorted(relevant_support, key=lambda x: x['price'], reverse=True)[:5],
            "resistance_levels": sorted(relevant_resistance, key=lambda x: x['price'])[:5],
            "sl_tp_levels": sl_tp_levels,
            "timestamp": df.index[-1].isoformat()
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


# ================== ICT INDICATORS API ENDPOINTS ==================

@app.get("/api/ict/{symbol}")
async def get_ict_indicators(symbol: str, timeframe: str = "5m", lookback: int = 200):
    """
    Get all ICT (Inner Circle Trader) indicators for a symbol.

    This endpoint detects ICT patterns in real-time and saves to database.
    Returns:
    - Fair Value Gaps (FVG)
    - Market Structure Shift (MSS)
    - Order Blocks
    - Breaker Blocks
    - OTE (Optimal Trade Entry) levels
    - Liquidity Zones
    - Premium/Discount Zones
    - Displacement candles
    - Trading Bias
    """
    try:
        symbol = symbol.replace("-", "/")
        df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=lookback)

        if df.empty or len(df) < 50:
            return {"error": "Insufficient data for ICT analysis"}

        # Initialize ICT indicators detector
        ict = ICTIndicators(df)

        # Detect all ICT patterns
        results = ict.detect_all()

        # Save to database for analysis
        if state.storage:
            try:
                state.storage.save_ict_indicators(results, symbol, timeframe)
            except Exception as e:
                print(f"Warning: Could not save ICT indicators to DB: {e}")

        # Convert DataFrames to lists for JSON response
        response = {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": datetime.now().isoformat(),
            "candle_count": len(df),
            "fvg": results["fvg"].to_dict(orient="records") if not results["fvg"].empty else [],
            "mss": results["mss"].to_dict(orient="records") if not results["mss"].empty else [],
            "order_blocks": results["order_blocks"].to_dict(orient="records") if not results["order_blocks"].empty else [],
            "breaker_blocks": results["breaker_blocks"].to_dict(orient="records") if not results["breaker_blocks"].empty else [],
            "ote_levels": results["ote_levels"],
            "liquidity_zones": results["liquidity_zones"].to_dict(orient="records") if not results["liquidity_zones"].empty else [],
            "premium_discount": results["premium_discount"],
            "displacement": results["displacement"].to_dict(orient="records") if not results["displacement"].empty else [],
            "swing_points": results["swing_points"].to_dict(orient="records") if not results["swing_points"].empty else [],
            "market_structure": results["market_structure"],
            "trading_bias": results["trading_bias"]
        }

        return response

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/ict/fvg/{symbol}")
async def get_ict_fvg(symbol: str, timeframe: str = "5m", limit: int = 50, unfilled_only: bool = False):
    """
    Get Fair Value Gaps from database.

    FVGs are 3-candle patterns where there's a gap between the first and third candles.
    They represent areas where price moved too quickly and may return to fill.
    """
    try:
        symbol = symbol.replace("-", "/")

        if state.storage:
            df = state.storage.get_ict_fvg(symbol, timeframe, limit, unfilled_only)
            if not df.empty:
                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "count": len(df),
                    "fvg": df.to_dict(orient="records")
                }

        return {"symbol": symbol, "timeframe": timeframe, "count": 0, "fvg": []}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/ict/order-blocks/{symbol}")
async def get_ict_order_blocks_db(symbol: str, timeframe: str = "5m", limit: int = 50, unmitigated_only: bool = False):
    """
    Get Order Blocks from database.

    Order Blocks are the last opposing candle before a strong move.
    They represent institutional entry zones that may act as support/resistance.
    """
    try:
        symbol = symbol.replace("-", "/")

        if state.storage:
            df = state.storage.get_ict_order_blocks(symbol, timeframe, limit, unmitigated_only)
            if not df.empty:
                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "count": len(df),
                    "order_blocks": df.to_dict(orient="records")
                }

        return {"symbol": symbol, "timeframe": timeframe, "count": 0, "order_blocks": []}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/ict/mss/{symbol}")
async def get_ict_mss(symbol: str, timeframe: str = "5m", limit: int = 50):
    """
    Get Market Structure Shifts from database.

    MSS occurs when price breaks a swing point and indicates potential trend reversal.
    - Bullish MSS: Price breaks above a swing high in a downtrend
    - Bearish MSS: Price breaks below a swing low in an uptrend
    """
    try:
        symbol = symbol.replace("-", "/")

        if state.storage:
            df = state.storage.get_ict_mss(symbol, timeframe, limit)
            if not df.empty:
                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "count": len(df),
                    "mss": df.to_dict(orient="records")
                }

        return {"symbol": symbol, "timeframe": timeframe, "count": 0, "mss": []}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/structure/{symbol}")
async def get_structure_breaks(symbol: str, timeframe: str = "5m", lookback: int = 5, limit: int = 200):
    """
    Get Break of Structure (BOS) and Market Structure Shift (MSS) data.

    BOS (Break of Structure): Price breaks a swing point IN the direction of the trend
    - Bullish BOS: In uptrend, price breaks above a swing high (trend continuation)
    - Bearish BOS: In downtrend, price breaks below a swing low (trend continuation)

    MSS (Market Structure Shift): Price breaks a swing point AGAINST the trend direction
    - Bullish MSS: In downtrend, price breaks above a swing high (potential reversal to uptrend)
    - Bearish MSS: In uptrend, price breaks below a swing low (potential reversal to downtrend)
    """
    try:
        symbol = symbol.replace("-", "/")
        df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=limit)

        if df.empty:
            return {"symbol": symbol, "timeframe": timeframe, "error": "No data available"}

        result = calculate_bos_mss(df, swing_lookback=lookback)

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "current_trend": result["current_trend"],
            "swing_highs": result["swing_highs"],
            "swing_lows": result["swing_lows"],
            "bos_events": result["bos_events"],
            "mss_events": result["mss_events"],
            "recent_bos": result["recent_bos"],
            "recent_mss": result["recent_mss"],
            "last_break": result["last_break"],
            "summary": result["summary"]
        }
    except Exception as e:
        logger.error(f"Error getting structure breaks for {symbol}: {e}")
        return {"error": str(e)}


@app.get("/api/structure/signal/{symbol}")
async def get_structure_trading_signal(symbol: str, timeframe: str = "5m", lookback: int = 5):
    """
    Get trading signal based on BOS/MSS analysis.

    Returns a signal (LONG, SHORT, NEUTRAL) with confidence level
    based on recent structure breaks.
    """
    try:
        symbol = symbol.replace("-", "/")
        df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=200)

        if df.empty:
            return {"symbol": symbol, "error": "No data available"}

        signal = get_structure_signal(df, swing_lookback=lookback)

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            **signal
        }
    except Exception as e:
        logger.error(f"Error getting structure signal for {symbol}: {e}")
        return {"error": str(e)}


@app.get("/api/ict/ote/{symbol}")
async def get_ict_ote(symbol: str, timeframe: str = "5m"):
    """
    Calculate current OTE (Optimal Trade Entry) levels.

    OTE levels are Fibonacci-based entry zones:
    - 50% (Equilibrium)
    - 62% (OTE - Best Entry)
    - 70.5%
    - 79%

    Also includes targets: -27%, -62%, -100%, -200%
    """
    try:
        symbol = symbol.replace("-", "/")
        df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=100)

        if df.empty or len(df) < 20:
            return {"error": "Insufficient data"}

        ict = ICTIndicators(df)
        ote_levels = ict.calculate_ote_levels()

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": datetime.now().isoformat(),
            "ote_levels": ote_levels
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/ict/bias/{symbol}")
async def get_ict_trading_bias(symbol: str, timeframe: str = "5m"):
    """
    Get ICT trading bias analysis.

    Combines multiple ICT signals to determine overall market bias:
    - FVG signals
    - MSS signals
    - Order Block positions
    - Premium/Discount zones
    - Market structure

    Returns confidence-weighted bias (BULLISH, BEARISH, or NEUTRAL).
    """
    try:
        symbol = symbol.replace("-", "/")
        df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=200)

        if df.empty or len(df) < 50:
            return {"error": "Insufficient data"}

        ict = ICTIndicators(df)
        results = ict.detect_all()
        bias = results["trading_bias"]

        # Save bias to database for tracking/validation
        if state.storage:
            try:
                state.storage.save_ict_trading_bias(
                    symbol=symbol,
                    timeframe=timeframe,
                    bias=bias["bias"],
                    confidence=bias["confidence"],
                    bullish_score=bias["bullish_score"],
                    bearish_score=bias["bearish_score"],
                    signals=bias["signals"]
                )
            except Exception as e:
                print(f"Warning: Could not save ICT bias: {e}")

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": datetime.now().isoformat(),
            "bias": bias["bias"],
            "confidence": bias["confidence"],
            "bullish_score": bias["bullish_score"],
            "bearish_score": bias["bearish_score"],
            "signals": bias["signals"]
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/ict/bias-accuracy/{symbol}")
async def get_ict_bias_accuracy(symbol: str, days: int = 7):
    """
    Get ICT bias prediction accuracy statistics.

    Tracks how well ICT signals predicted actual market movements.
    Returns:
    - Overall accuracy
    - Accuracy by bias type
    - Signal breakdown
    """
    try:
        symbol = symbol.replace("-", "/")

        if state.storage:
            accuracy = state.storage.get_ict_bias_accuracy(symbol, days)
            return {
                "symbol": symbol,
                "days": days,
                **accuracy
            }

        return {"error": "Storage not initialized"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/ict/history/{indicator_type}/{symbol}")
async def get_ict_history(
    indicator_type: str,
    symbol: str,
    timeframe: str = "5m",
    limit: int = 100,
    start_date: str = None,
    end_date: str = None
):
    """
    Get historical ICT indicator data from database.

    indicator_type can be:
    - fvg: Fair Value Gaps
    - mss: Market Structure Shifts
    - order_blocks: Order Blocks
    - breaker_blocks: Breaker Blocks
    - liquidity_zones: Liquidity Zones
    - displacement: Displacement candles
    - swing_points: Swing Points
    - market_structure: Market Structure analysis
    - premium_discount: Premium/Discount zones
    - trading_bias: Trading bias history
    """
    try:
        symbol = symbol.replace("-", "/")

        if not state.storage:
            return {"error": "Storage not initialized"}

        valid_types = [
            "fvg", "mss", "order_blocks", "breaker_blocks",
            "liquidity_zones", "displacement", "swing_points",
            "market_structure", "premium_discount", "trading_bias"
        ]

        if indicator_type not in valid_types:
            return {"error": f"Invalid indicator type. Valid types: {valid_types}"}

        # Map to storage methods
        if indicator_type == "fvg":
            df = state.storage.get_ict_fvg(symbol, timeframe, limit)
        elif indicator_type == "mss":
            df = state.storage.get_ict_mss(symbol, timeframe, limit)
        elif indicator_type == "order_blocks":
            df = state.storage.get_ict_order_blocks(symbol, timeframe, limit)
        elif indicator_type == "trading_bias":
            df = state.storage.get_ict_trading_bias_history(symbol, timeframe, limit)
        elif indicator_type == "market_structure":
            df = state.storage.get_ict_market_structure_history(symbol, timeframe, limit)
        elif indicator_type == "premium_discount":
            df = state.storage.get_ict_premium_discount_history(symbol, timeframe, limit)
        else:
            # Generic query for other types
            import sqlite3
            table_name = f"ict_{indicator_type}"
            conn = sqlite3.connect(state.storage.db_path)
            conn.row_factory = sqlite3.Row
            query = f"SELECT * FROM {table_name} WHERE symbol = ? AND timeframe = ? ORDER BY detected_at DESC LIMIT ?"
            df = pd.read_sql_query(query, conn, params=(symbol, timeframe, limit))
            conn.close()

        if df is not None and not df.empty:
            return {
                "indicator_type": indicator_type,
                "symbol": symbol,
                "timeframe": timeframe,
                "count": len(df),
                "data": df.to_dict(orient="records")
            }

        return {
            "indicator_type": indicator_type,
            "symbol": symbol,
            "timeframe": timeframe,
            "count": 0,
            "data": []
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


# ================== END ICT INDICATORS API ENDPOINTS ==================


# ================== ICT STRATEGY API ENDPOINTS ==================

@app.get("/api/ict-strategy/signal/{symbol:path}")
async def get_ict_strategy_signal(symbol: str, timeframe: str = "5m", include_ml: bool = True):
    """
    Get ICT strategy trading signal with confluence analysis.

    This endpoint provides a comprehensive ICT-based trading signal including:
    - Direction (LONG/SHORT/HOLD)
    - Confluence score and breakdown
    - Entry, Stop Loss, and Take Profit levels
    - Risk/Reward ratios
    - Session timing analysis
    - ML model confirmation (optional)

    Args:
        symbol: Trading pair (e.g., BTC-USDT)
        timeframe: Candle timeframe (default: 5m)
        include_ml: Whether to include ML model confirmation
    """
    try:
        from strategy.ict_strategy import ICTStrategy, ICTSignal

        symbol = symbol.replace("-", "/")
        df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=200)

        if df.empty or len(df) < 50:
            return {"error": "Insufficient data for ICT analysis"}

        # Initialize ICT strategy
        ict_config = state.config.get('ict_strategy', {})
        ict_strategy = ICTStrategy(
            config=ict_config,
            ml_model=state.model if include_ml else None,
            feature_engineer=state.feature_engineer if include_ml else None
        )

        # Generate signal
        signal, confidence, details = ict_strategy.generate_signal(df, include_ml=include_ml)

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": datetime.now().isoformat(),
            "signal": signal.name,
            "signal_value": signal.value,
            "confidence": confidence,
            "direction": details.get('direction', 'none'),
            "confluence": details.get('confluence', {}),
            "entry_targets": details.get('entry_targets', {}),
            "ict_bias": details.get('ict_bias', 'neutral'),
            "ict_confidence": details.get('ict_confidence', 0),
            "ml_signal": details.get('ml_signal'),
            "ml_confidence": details.get('ml_confidence', 0),
            "session": details.get('session', 'unknown'),
            "is_optimal_session": details.get('is_optimal_session', False),
            "current_price": details.get('current_price', 0),
            "atr": details.get('atr', 0),
            "ict_summary": details.get('ict_data_summary', {}),
            "explanation": ict_strategy.get_signal_explanation(details) if hasattr(ict_strategy, 'get_signal_explanation') else ""
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/ict-strategy/confluence/{symbol}")
async def get_ict_confluence(symbol: str, timeframe: str = "5m", direction: str = "auto"):
    """
    Get detailed ICT confluence analysis.

    Returns a comprehensive breakdown of all confluence factors
    and their contribution to the overall score.

    Args:
        symbol: Trading pair
        timeframe: Candle timeframe
        direction: 'long', 'short', or 'auto' (determine from data)
    """
    try:
        from strategy.confluence import ConfluenceDetector
        from features.ict_indicators import ICTIndicators

        symbol = symbol.replace("-", "/")
        df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=200)

        if df.empty or len(df) < 50:
            return {"error": "Insufficient data"}

        # Detect ICT patterns
        ict = ICTIndicators()
        ict_data = ict.detect_all(df)

        current_price = float(df['close'].iloc[-1])

        # Calculate ATR
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        tr = pd.concat([high - low, abs(high - close), abs(low - close)], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1])

        # Get ML signal if available
        ml_signal = None
        ml_confidence = 0.0
        if state.strategy and state.model:
            try:
                from strategy.ml_strategy import Signal
                sig, conf = state.strategy.generate_signal(df)
                ml_signal = sig.name
                ml_confidence = conf
            except:
                pass

        # Analyze confluence
        detector = ConfluenceDetector()
        result = detector.analyze(
            ict_data=ict_data,
            current_price=current_price,
            atr=atr,
            direction=direction,
            ml_signal=ml_signal,
            ml_confidence=ml_confidence,
            timestamp=datetime.now()
        )

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            **result.to_dict()
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/ict-strategy/session")
async def get_session_info():
    """
    Get current trading session information.

    Returns:
    - Current session (Asia, London, NY AM, NY PM, etc.)
    - Whether it's an optimal trading time
    - Next optimal session and time until
    - Silver Bullet window status
    """
    try:
        from features.sessions import SessionFilter, format_session_time, get_ny_time

        sf = SessionFilter()
        now = datetime.now()
        ny_time = get_ny_time(now)

        current_session = sf.get_session(now)
        is_optimal, session, reason = sf.is_optimal_time(now)
        is_silver_bullet, sb_info = sf.is_silver_bullet_window(now)
        is_killzone, kz_info = sf.is_killzone(now)
        next_optimal = sf.get_next_optimal_session(now)

        return {
            "current_time_utc": now.isoformat(),
            "current_time_ny": ny_time.isoformat(),
            "current_session": current_session.value,
            "session_time_range": format_session_time(current_session),
            "is_optimal": is_optimal,
            "optimal_reason": reason,
            "is_silver_bullet": is_silver_bullet,
            "silver_bullet_info": sb_info,
            "is_killzone": is_killzone,
            "killzone_info": kz_info,
            "next_optimal_session": {
                "session": next_optimal['session'].value,
                "name": next_optimal['name'],
                "starts_at": next_optimal['starts_at'],
                "minutes_until": next_optimal['minutes_until']
            }
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/ict-strategy/features/{symbol}")
async def get_ict_ml_features(symbol: str, timeframe: str = "5m"):
    """
    Get ICT features formatted for ML model input.

    Returns 50+ ICT-derived features that can be used
    to enhance ML model predictions.
    """
    try:
        from features.ict_features import ICTFeatureGenerator

        symbol = symbol.replace("-", "/")
        df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=200)

        if df.empty or len(df) < 50:
            return {"error": "Insufficient data"}

        # Generate ICT features
        feature_gen = ICTFeatureGenerator()
        features = feature_gen.generate_features_for_row(df)

        # Categorize features for display
        categories = {
            'fvg': {k: v for k, v in features.items() if 'fvg' in k},
            'mss': {k: v for k, v in features.items() if 'mss' in k},
            'order_block': {k: v for k, v in features.items() if '_ob_' in k},
            'ote': {k: v for k, v in features.items() if 'ote' in k},
            'zone': {k: v for k, v in features.items() if 'zone' in k},
            'liquidity': {k: v for k, v in features.items() if 'liq' in k},
            'structure': {k: v for k, v in features.items() if 'trend' in k or 'hh_' in k or 'hl_' in k or 'lh_' in k or 'll_' in k or 'structure' in k or 'bullish_score' in k or 'bearish_score' in k},
            'displacement': {k: v for k, v in features.items() if 'disp' in k},
            'session': {k: v for k, v in features.items() if 'session' in k},
            'bias': {k: v for k, v in features.items() if 'bias' in k and 'zone' not in k},
        }

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": datetime.now().isoformat(),
            "feature_count": len(features),
            "features": features,
            "categories": categories
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


class BacktestRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    timeframe: str = "5m"
    initial_capital: float = 10000
    risk_per_trade: float = 0.01
    min_confluence: int = 15


@app.post("/api/ict-strategy/backtest")
async def run_ict_backtest(request: BacktestRequest):
    """
    Run backtest using ICT strategy.

    Args:
        symbol: Trading pair
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        timeframe: Candle timeframe
        initial_capital: Starting capital
        risk_per_trade: Risk per trade (0.01 = 1%)
        min_confluence: Minimum confluence score to enter trade
    """
    try:
        from strategy.ict_strategy import ICTStrategy, ICTSignal
        from dataclasses import dataclass
        from typing import List

        # Extract request params
        symbol = request.symbol.replace("-", "/")
        timeframe = request.timeframe
        start_date = request.start_date
        end_date = request.end_date
        min_confluence = request.min_confluence
        risk_per_trade = request.risk_per_trade
        initial_capital = request.initial_capital

        # Fetch historical data
        df = await run_in_executor(
            state.data_fetcher.fetch_historical_data,
            symbol,
            timeframe,
            start_date,
            end_date
        )

        if df is None or df.empty or len(df) < 100:
            return {"error": f"Insufficient historical data. Got {len(df) if df is not None else 0} candles, need at least 100."}

        # Initialize strategy
        ict_config = {
            'min_confluence_score': min_confluence,
            'risk': {'risk_per_trade': risk_per_trade}
        }
        strategy = ICTStrategy(config=ict_config)

        # Backtest variables
        capital = initial_capital
        position = 0  # 0 = flat, 1 = long, -1 = short
        entry_price = 0
        stop_loss = 0
        take_profit = 0

        trades = []
        equity_curve = [initial_capital]

        # Run backtest
        lookback = 100  # Candles needed for ICT analysis

        for i in range(lookback, len(df)):
            df_slice = df.iloc[:i+1].copy()
            current_price = float(df_slice['close'].iloc[-1])
            current_time = df_slice.index[-1]

            # Check for exit if in position
            if position != 0:
                exit_reason = None

                if position == 1:  # Long
                    if current_price <= stop_loss:
                        exit_reason = 'stop_loss'
                    elif current_price >= take_profit:
                        exit_reason = 'take_profit'
                else:  # Short
                    if current_price >= stop_loss:
                        exit_reason = 'stop_loss'
                    elif current_price <= take_profit:
                        exit_reason = 'take_profit'

                if exit_reason:
                    # Close position
                    if position == 1:
                        pnl = (current_price - entry_price) / entry_price * 100
                    else:
                        pnl = (entry_price - current_price) / entry_price * 100

                    trade_return = capital * (pnl / 100)
                    capital += trade_return

                    trades.append({
                        'entry_time': entry_time.isoformat(),
                        'exit_time': current_time.isoformat(),
                        'direction': 'long' if position == 1 else 'short',
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'pnl_pct': round(pnl, 2),
                        'pnl_usd': round(trade_return, 2),
                        'exit_reason': exit_reason
                    })

                    position = 0
                    entry_price = 0

            # Check for entry if flat
            if position == 0:
                try:
                    signal, confidence, details = strategy.generate_signal(df_slice, include_ml=False)

                    if signal in [ICTSignal.STRONG_BUY, ICTSignal.BUY]:
                        position = 1
                        entry_price = current_price
                        entry_time = current_time
                        et = details.get('entry_targets', {})
                        stop_loss = et.get('stop_loss', current_price * 0.98)
                        take_profit = et.get('take_profit_1', current_price * 1.03)

                    elif signal in [ICTSignal.STRONG_SELL, ICTSignal.SELL]:
                        position = -1
                        entry_price = current_price
                        entry_time = current_time
                        et = details.get('entry_targets', {})
                        stop_loss = et.get('stop_loss', current_price * 1.02)
                        take_profit = et.get('take_profit_1', current_price * 0.97)

                except Exception as e:
                    pass  # Skip this candle on error

            equity_curve.append(capital)

        # Calculate statistics
        if trades:
            winning_trades = [t for t in trades if t['pnl_pct'] > 0]
            losing_trades = [t for t in trades if t['pnl_pct'] <= 0]

            total_return = (capital - initial_capital) / initial_capital * 100
            win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
            avg_win = sum(t['pnl_pct'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
            avg_loss = sum(t['pnl_pct'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
            profit_factor = abs(sum(t['pnl_pct'] for t in winning_trades) / sum(t['pnl_pct'] for t in losing_trades)) if losing_trades and sum(t['pnl_pct'] for t in losing_trades) != 0 else 0

            # Max drawdown
            peak = initial_capital
            max_dd = 0
            for eq in equity_curve:
                if eq > peak:
                    peak = eq
                dd = (peak - eq) / peak * 100
                if dd > max_dd:
                    max_dd = dd

            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "period": f"{start_date} to {end_date}",
                "initial_capital": initial_capital,
                "final_capital": round(capital, 2),
                "total_return_pct": round(total_return, 2),
                "total_trades": len(trades),
                "winning_trades": len(winning_trades),
                "losing_trades": len(losing_trades),
                "win_rate_pct": round(win_rate, 2),
                "avg_win_pct": round(avg_win, 2),
                "avg_loss_pct": round(avg_loss, 2),
                "profit_factor": round(profit_factor, 2),
                "max_drawdown_pct": round(max_dd, 2),
                "trades": trades[-20:],  # Last 20 trades
                "equity_curve_sample": equity_curve[::max(1, len(equity_curve)//100)]  # Sample 100 points
            }
        else:
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "period": f"{start_date} to {end_date}",
                "total_trades": 0,
                "message": "No trades generated during backtest period"
            }

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


# ================== END ICT STRATEGY API ENDPOINTS ==================


@app.get("/api/ict-strategy/mtf/{symbol}")
async def get_mtf_analysis(symbol: str, timeframes: Optional[str] = None):
    """
    Get Multi-Timeframe ICT Analysis.

    Performs top-down analysis across multiple timeframes following ICT methodology:
    - Daily: Overall bias and key levels (PDH/PDL/PWH/PWL)
    - 4H: Intermediate structure and order blocks
    - 1H: Key swing points and FVGs
    - 15m: Setup identification and entry zones
    - 5m: Precision entries

    Args:
        symbol: Trading pair (e.g., BTC-USDT)
        timeframes: Comma-separated list of timeframes to analyze (default: all)
                    Example: "1d,4h,1h" or "4h,15m,5m"

    Returns:
        Complete multi-timeframe analysis with:
        - Overall bias and confidence
        - Alignment score (how well timeframes agree)
        - Recommended direction (long/short/wait)
        - Per-timeframe breakdown with structure and key levels
        - Aggregated key levels for trading
    """
    try:
        symbol = symbol.replace("-", "/")

        # Parse timeframes
        if timeframes:
            tf_list = [tf.strip() for tf in timeframes.split(',')]
            # Validate timeframes
            valid_tfs = ['1d', '4h', '1h', '15m', '5m']
            tf_list = [tf for tf in tf_list if tf in valid_tfs]
        else:
            tf_list = None  # Use all timeframes

        # Initialize MTF analyzer
        mtf_analyzer = MTFICTAnalyzer(data_fetcher=state.data_fetcher)

        # Perform analysis
        result = mtf_analyzer.analyze(symbol, timeframes=tf_list)

        # Convert to dict for JSON response
        response = mtf_analyzer.to_dict(result)
        response['symbol'] = symbol

        return response

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/ict-strategy/mtf-bias/{symbol}")
async def get_mtf_htf_bias(symbol: str):
    """
    Get quick Higher Timeframe bias (Daily + 4H only).

    Useful for quickly checking HTF direction before looking for entries
    on lower timeframes.

    Args:
        symbol: Trading pair (e.g., BTC-USDT)

    Returns:
        Quick HTF bias with daily and 4H analysis
    """
    try:
        symbol = symbol.replace("-", "/")

        mtf_analyzer = MTFICTAnalyzer(data_fetcher=state.data_fetcher)
        bias = mtf_analyzer.get_htf_bias(symbol)

        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            **bias
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/ict-strategy/daily-bias/{symbol}")
async def get_daily_bias(symbol: str, timeframe: str = "5m"):
    """
    Get ICT daily directional bias.

    Analyzes multiple factors to determine the most probable
    direction for the trading day:
    - Previous Day High/Low (PDH/PDL)
    - Previous Week High/Low (PWH/PWL)
    - Higher Timeframe Structure
    - Asian Session Range
    - London Open Direction
    - Gap Analysis

    Args:
        symbol: Trading pair (e.g., BTC-USDT)
        timeframe: Base timeframe for analysis
    """
    try:
        from strategy.daily_bias import DailyBiasCalculator

        symbol = symbol.replace("-", "/")

        # Fetch multiple timeframes
        df_5m = state.data_fetcher.fetch_ohlcv(symbol, "5m", limit=500)

        df_1h = None
        df_daily = None

        try:
            df_1h = state.data_fetcher.fetch_ohlcv(symbol, "1h", limit=200)
        except:
            pass

        try:
            df_daily = state.data_fetcher.fetch_ohlcv(symbol, "1d", limit=30)
        except:
            pass

        if df_5m.empty or len(df_5m) < 100:
            return {"error": "Insufficient 5-minute data"}

        # Calculate daily bias
        calculator = DailyBiasCalculator()
        result = calculator.calculate_bias(
            df_5m=df_5m,
            df_1h=df_1h,
            df_daily=df_daily
        )

        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            **result.to_dict()
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/ict-strategy/silver-bullet/status")
async def get_silver_bullet_status():
    """
    Get current Silver Bullet window status.

    Returns:
    - Current window (AM, PM, or NONE)
    - Time until next window
    - Whether currently in a valid trading window
    """
    try:
        from strategy.silver_bullet import SilverBulletStrategy, SilverBulletWindow

        strategy = SilverBulletStrategy()
        current_window = strategy.get_current_window()
        next_window, time_until = strategy.get_time_until_next_window()

        return {
            "current_window": current_window.value,
            "is_active": current_window != SilverBulletWindow.NONE,
            "next_window": next_window.value,
            "time_until_next": str(time_until),
            "time_until_seconds": int(time_until.total_seconds()),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/ict-strategy/silver-bullet/{symbol}")
async def get_silver_bullet_setup(symbol: str, timeframe: str = "5m"):
    """
    Get Silver Bullet strategy setup.

    The Silver Bullet strategy looks for high-probability setups during:
    - AM Window: 10:00 AM - 11:00 AM EST
    - PM Window: 2:00 PM - 3:00 PM EST

    Entry conditions:
    1. Within Silver Bullet time window
    2. Liquidity has been swept (PDH/PDL, Asian High/Low)
    3. Market Structure Shift confirmed
    4. Price returns to FVG or Order Block
    5. Minimum 3:1 Risk/Reward

    Args:
        symbol: Trading pair (e.g., BTC-USDT)
        timeframe: Timeframe for analysis (default 5m)
    """
    try:
        from strategy.silver_bullet import SilverBulletStrategy

        symbol = symbol.replace("-", "/")

        # Fetch data (need enough for liquidity level identification)
        df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=500)

        if df.empty or len(df) < 100:
            return {"error": "Insufficient data for Silver Bullet analysis"}

        # Analyze for Silver Bullet setup
        strategy = SilverBulletStrategy()
        setup = strategy.analyze(df)

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            **strategy.to_dict(setup)
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/ict-strategy/smt-divergence/multi/{symbol}")
async def get_smt_divergence_multi(symbol: str, timeframe: str = "5m"):
    """
    Detect SMT divergence against multiple correlated assets.

    Analyzes the primary symbol against all commonly correlated assets
    and returns the strongest divergence signal.

    Args:
        symbol: Primary trading pair (e.g., BTC-USDT)
        timeframe: Timeframe for analysis (default 5m)
    """
    try:
        from features.smt_divergence import SMTDivergenceDetector

        symbol = symbol.replace("-", "/")

        # Define comparison assets based on primary
        if 'BTC' in symbol:
            comparisons = ['ETH/USD', 'SOL/USD']
        elif 'ETH' in symbol:
            comparisons = ['BTC/USD', 'SOL/USD']
        else:
            comparisons = ['BTC/USD', 'ETH/USD']

        # Fetch primary data
        df_primary = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=200)

        if df_primary.empty:
            return {"error": f"Could not fetch data for {symbol}"}

        detector = SMTDivergenceDetector()
        results = {
            'symbol': symbol,
            'timeframe': timeframe,
            'analyses': [],
            'strongest_divergence': None,
            'timestamp': datetime.now().isoformat()
        }

        strongest_confidence = 0

        for comp_symbol in comparisons:
            try:
                df_comparison = state.data_fetcher.fetch_ohlcv(comp_symbol, timeframe, limit=200)

                if df_comparison.empty:
                    continue

                analysis = detector.analyze(
                    df_primary, df_comparison,
                    symbol, comp_symbol
                )

                results['analyses'].append(analysis)

                if analysis['divergence']:
                    div_confidence = analysis['divergence']['confidence']
                    if div_confidence > strongest_confidence:
                        strongest_confidence = div_confidence
                        results['strongest_divergence'] = analysis['divergence']

            except Exception as e:
                results['analyses'].append({
                    'comparison_symbol': comp_symbol,
                    'error': str(e)
                })

        return results

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/ict-strategy/smt-divergence/{symbol}")
async def get_smt_divergence(
    symbol: str,
    comparison_symbol: Optional[str] = None,
    timeframe: str = "5m"
):
    """
    Detect SMT (Smart Money Tool) divergence.

    SMT divergence identifies when correlated assets fail to confirm
    each other's swing points, indicating potential smart money activity.

    - Bullish SMT: Asset A makes lower low, Asset B makes higher low
    - Bearish SMT: Asset A makes higher high, Asset B makes lower high

    Args:
        symbol: Primary trading pair (e.g., BTC-USDT)
        comparison_symbol: Comparison asset (optional, defaults to ETH for BTC)
        timeframe: Timeframe for analysis (default 5m)
    """
    try:
        from features.smt_divergence import SMTDivergenceDetector

        symbol = symbol.replace("-", "/")

        # Default comparison symbols
        if comparison_symbol:
            comparison_symbol = comparison_symbol.replace("-", "/")
        else:
            # Default comparisons
            if 'BTC' in symbol:
                comparison_symbol = 'ETH/USD'
            elif 'ETH' in symbol:
                comparison_symbol = 'BTC/USD'
            else:
                comparison_symbol = 'BTC/USD'

        # Fetch data for both assets
        df_primary = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=200)
        df_comparison = state.data_fetcher.fetch_ohlcv(comparison_symbol, timeframe, limit=200)

        if df_primary.empty:
            return {"error": f"Could not fetch data for {symbol}"}

        if df_comparison.empty:
            return {"error": f"Could not fetch data for {comparison_symbol}"}

        # Analyze for divergence
        detector = SMTDivergenceDetector()
        result = detector.analyze(
            df_primary, df_comparison,
            symbol, comparison_symbol
        )

        result['timeframe'] = timeframe

        return result

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/database/query")
async def query_database(
    table: str = "candle_snapshots",
    limit: int = 100,
    offset: int = 0,
    symbol: str = None,
    prediction: str = None,
    start_date: str = None,
    end_date: str = None
):
    """Query database tables with optional filters."""
    import sqlite3

    # Validate table name to prevent SQL injection
    allowed_tables = ['candle_snapshots', 'trades', 'ohlcv', 'model_performance']
    if table not in allowed_tables:
        return {"error": f"Invalid table name. Allowed: {allowed_tables}"}

    try:
        conn = sqlite3.connect(state.storage.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query
        query = f"SELECT * FROM {table} WHERE 1=1"
        count_query = f"SELECT COUNT(*) FROM {table} WHERE 1=1"
        params = []

        # Add filters based on table
        if symbol:
            query += " AND symbol = ?"
            count_query += " AND symbol = ?"
            params.append(symbol)

        if prediction and table == 'candle_snapshots':
            query += " AND prediction = ?"
            count_query += " AND prediction = ?"
            params.append(prediction)

        if start_date:
            if table == 'candle_snapshots':
                query += " AND timestamp_utc >= ?"
                count_query += " AND timestamp_utc >= ?"
            elif table in ['trades', 'ohlcv', 'model_performance']:
                query += " AND timestamp >= ?"
                count_query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            if table == 'candle_snapshots':
                query += " AND timestamp_utc <= ?"
                count_query += " AND timestamp_utc <= ?"
            elif table in ['trades', 'ohlcv', 'model_performance']:
                query += " AND timestamp <= ?"
                count_query += " AND timestamp <= ?"
            params.append(end_date + " 23:59:59")

        # Get total count
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        # Add ordering and pagination
        if table == 'candle_snapshots':
            query += " ORDER BY timestamp_utc DESC"
        elif table in ['trades', 'ohlcv', 'model_performance']:
            query += " ORDER BY timestamp DESC"
        else:
            query += " ORDER BY id DESC"

        query += f" LIMIT {limit} OFFSET {offset}"

        # Execute query
        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Get column names
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        # Convert rows to dicts
        data = [dict(row) for row in rows]

        conn.close()

        return {
            "table": table,
            "columns": columns,
            "rows": data,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        return {"error": str(e)}


@app.get("/api/prediction-accuracy/{symbol}")
async def get_prediction_accuracy(symbol: str, days: int = 7):
    """
    Get prediction accuracy statistics for a symbol.

    Args:
        symbol: Trading pair (e.g., BTC-USDT)
        days: Number of days to analyze (default 7)

    Returns:
        Dictionary with accuracy metrics including:
        - Overall accuracy
        - Accuracy by prediction type (BUY/SELL/HOLD)
        - Last 24h performance
    """
    try:
        symbol = symbol.replace("-", "/")
        accuracy = state.storage.get_prediction_accuracy(symbol, days)
        return {
            "symbol": symbol,
            **accuracy
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/validate-predictions/{symbol}")
async def validate_pending_predictions(symbol: str):
    """
    Manually trigger validation of pending predictions.

    This will validate any predictions that haven't been validated yet
    using the current price as the next close.
    """
    try:
        symbol = symbol.replace("-", "/")

        # Get current price
        ticker = await run_in_executor(state.exchange.fetch_ticker, symbol)
        current_close = ticker.get("last", 0)

        if not current_close:
            return {"error": "Could not fetch current price"}

        # Get unvalidated predictions
        unvalidated = state.storage.get_unvalidated_predictions(symbol)

        if not unvalidated:
            return {"status": "no_pending_validations", "validated_count": 0}

        # Validate all except the most recent
        validated_count = 0
        for snapshot in unvalidated[:-1]:  # Skip the last one (current)
            state.storage.validate_prediction(
                snapshot_id=snapshot['id'],
                next_close=current_close,
                flat_threshold=0.1
            )
            validated_count += 1

        return {
            "status": "validated",
            "validated_count": validated_count,
            "current_price": current_close
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/start")
async def start_trading(config: TradeConfig, background_tasks: BackgroundTasks):
    """Start paper or live trading."""
    if state.is_trading:
        raise HTTPException(status_code=400, detail="Trading already running")

    if not state.strategy:
        raise HTTPException(status_code=400, detail="Model not loaded. Train first.")

    state.active_symbols = config.symbols
    state.trading_mode = config.mode
    state.is_trading = True

    # Initialize paper trader
    state.paper_trader = PaperTrader(
        state.strategy,
        state.data_fetcher,
        state.storage,
        state.config
    )

    # Start trading in background
    background_tasks.add_task(run_trading_loop)

    await broadcast({"type": "status", "is_trading": True, "mode": config.mode})

    return {"status": "started", "mode": config.mode, "symbols": config.symbols}


async def run_trading_loop():
    """Background trading loop."""
    interval = 60  # seconds

    while state.is_trading:
        try:
            for symbol in state.active_symbols:
                # Process symbol
                timeframe = state.config.get("trading", {}).get("timeframe", "1h")
                df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=200)

                if df.empty:
                    continue

                current_price = df["close"].iloc[-1]

                # Get signal
                signal, confidence = state.strategy.generate_signal(df)

                # Broadcast update
                await broadcast({
                    "type": "update",
                    "symbol": symbol,
                    "price": current_price,
                    "signal": signal.name,
                    "confidence": confidence,
                    "timestamp": datetime.now().isoformat()
                })

                # Process trading logic in paper trader
                if state.paper_trader:
                    state.paper_trader._process_symbol(symbol)

            # Broadcast account update
            if state.paper_trader:
                await broadcast({
                    "type": "account",
                    "cash": state.paper_trader.account.cash,
                    "equity": state.paper_trader.account.equity,
                    "pnl": state.paper_trader.account.total_pnl
                })

            await asyncio.sleep(interval)

        except Exception as e:
            print(f"Trading loop error: {e}")
            await asyncio.sleep(10)


@app.post("/api/stop")
async def stop_trading():
    """Stop trading."""
    state.is_trading = False
    state.trading_mode = None

    if state.paper_trader:
        state.paper_trader.stop()

    await broadcast({"type": "status", "is_trading": False})

    return {"status": "stopped"}


@app.post("/api/train")
async def train_model(config: TrainConfig, background_tasks: BackgroundTasks):
    """Train the ML model."""
    background_tasks.add_task(run_training, config)
    return {"status": "training_started"}


async def run_training(config: TrainConfig):
    """Background training task."""
    try:
        model_type = config.model_type
        await broadcast({"type": "training", "status": "fetching_data", "model_type": model_type})

        timeframe = state.config.get("trading", {}).get("timeframe", "1h")
        df = state.data_fetcher.fetch_historical_data(
            config.symbol, timeframe, config.start_date, config.end_date
        )

        if df.empty:
            await broadcast({"type": "training", "status": "error", "message": "No data"})
            return

        await broadcast({"type": "training", "status": "generating_features", "model_type": model_type})
        df_features = state.feature_engineer.generate_features(df)

        await broadcast({"type": "training", "status": "training_model", "model_type": model_type})
        X, y = state.feature_engineer.prepare_ml_data(df_features)

        # Create model with specified type
        from models.ml_models import (
            XGBoostModel, LightGBMModel, RandomForestModel,
            ProphetModel, TransformerModel, PPOModel
        )

        model_classes = {
            "xgboost": XGBoostModel,
            "lightgbm": LightGBMModel,
            "random_forest": RandomForestModel,
            "prophet": ProphetModel,
            "transformer": TransformerModel,
            "ppo": PPOModel,
        }

        model_class = model_classes.get(model_type)
        if not model_class:
            await broadcast({"type": "training", "status": "error", "message": f"Unknown model type: {model_type}"})
            return

        model = model_class(state.config)

        # Train model (Prophet and PPO need different data format)
        if model_type == "prophet":
            model.train(df_features, y)
        elif model_type == "ppo":
            model.train(df_features, y)
        else:
            model.train(X, y)

        # Evaluate
        metrics = model.evaluate(X, y)

        # Save model with specific filename for predictions page
        models_dir = Path(__file__).parent.parent / "models"
        models_dir.mkdir(parents=True, exist_ok=True)

        # Save with model-specific name
        if model_type == "transformer":
            model_filename = f"transformer_model.pt"
        elif model_type == "ppo":
            model_filename = f"ppo_model.zip"
        else:
            model_filename = f"{model_type}_model.joblib"

        model_path = models_dir / model_filename
        model.save(str(model_path))

        # Also save as trained_model.joblib if it's the primary model type
        if model_type == state.config.get("model", {}).get("type", "xgboost"):
            generic_path = models_dir / "trained_model.joblib"
            model.save(str(generic_path))
            state.model = model
            state.strategy = MLStrategy(state.model, state.feature_engineer, state.config)

        await broadcast({
            "type": "training",
            "status": "completed",
            "model_type": model_type,
            "metrics": metrics,
            "model_path": str(model_path)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        await broadcast({"type": "training", "status": "error", "message": str(e)})


@app.post("/api/backtest")
async def run_backtest(config: BacktestConfig):
    """Run backtest."""
    if not state.strategy:
        raise HTTPException(status_code=400, detail="Model not loaded")

    try:
        timeframe = state.config.get("trading", {}).get("timeframe", "1h")
        df = state.data_fetcher.fetch_historical_data(
            config.symbol, timeframe, config.start_date, config.end_date
        )

        if df.empty:
            raise HTTPException(status_code=400, detail="No data available")

        df_features = state.feature_engineer.generate_features(df)

        backtester = Backtester(state.config)
        result = backtester.run(state.strategy, df_features, config.symbol)

        return {
            "total_return": result.total_return,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
            "win_rate": result.win_rate,
            "profit_factor": result.profit_factor,
            "total_trades": result.total_trades,
            "winning_trades": result.winning_trades,
            "losing_trades": result.losing_trades
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates."""
    await websocket.accept()
    state.websocket_clients.append(websocket)

    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        state.websocket_clients.remove(websocket)


# ================== SCALPING BOT API ENDPOINTS ==================

class ScalpingConfig(BaseModel):
    mode: str = "paper"  # "paper" or "live"
    symbol: str = "BTC/USD"
    initial_capital: float = 1000
    risk_per_trade: float = 0.01
    trading_mode: str = "medium"  # "safe", "medium", "fast", or "custom"
    # Enabled confluence signals
    enabled_confluences: Optional[List[str]] = None
    # Custom mode parameters (only used when trading_mode="custom")
    take_profit_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    max_trades_per_hour: Optional[int] = None
    min_confidence: Optional[int] = None
    min_confluence_score: Optional[int] = None
    min_aligned_signals: Optional[int] = None
    cooldown_seconds: Optional[int] = None


class TradingModeConfig(BaseModel):
    trading_mode: str  # "safe", "medium", "fast", or "custom"
    custom_config: Optional[dict] = None  # Custom parameters for custom mode


@app.get("/api/scalping/status")
async def get_scalping_status():
    """Get scalping bot status and statistics."""
    if state.scalping_bot is None:
        return {
            "status": "not_initialized",
            "message": "Scalping bot has not been started yet"
        }

    return convert_numpy_types(state.scalping_bot.get_status())


@app.post("/api/scalping/start")
async def start_scalping_bot(config: Optional[ScalpingConfig] = None):
    """Start the scalping bot."""
    from engine.scalping_bot import ScalpingBot, create_scalping_bot

    # Check if already running
    if state.scalping_bot is not None and state.scalping_bot.status.value == "running":
        return {"error": "Scalping bot is already running"}

    # Get config from request or file
    if config:
        # Build kwargs for custom parameters
        custom_kwargs = {}
        if config.take_profit_pct is not None:
            custom_kwargs["take_profit_pct"] = config.take_profit_pct
        if config.stop_loss_pct is not None:
            custom_kwargs["stop_loss_pct"] = config.stop_loss_pct
        if config.max_trades_per_hour is not None:
            custom_kwargs["max_trades_per_hour"] = config.max_trades_per_hour
        if config.min_confidence is not None:
            custom_kwargs["min_confidence"] = config.min_confidence
        if config.min_confluence_score is not None:
            custom_kwargs["min_confluence_score"] = config.min_confluence_score
        if config.min_aligned_signals is not None:
            custom_kwargs["min_aligned_signals"] = config.min_aligned_signals
        if config.cooldown_seconds is not None:
            custom_kwargs["cooldown_seconds"] = config.cooldown_seconds
        if config.enabled_confluences is not None:
            custom_kwargs["enabled_confluences"] = config.enabled_confluences

        state.scalping_bot = create_scalping_bot(
            exchange=state.exchange,
            fetcher=state.data_fetcher,
            storage=state.storage,
            mode=config.mode,
            symbol=config.symbol,
            capital=config.initial_capital,
            trading_mode=config.trading_mode,
            risk_per_trade=config.risk_per_trade,
            ml_strategy=state.strategy,  # Pass ML strategy for predictions
            **custom_kwargs
        )
    else:
        # Use config from file
        bot_config = state.config.get("scalping", {})
        state.scalping_bot = create_scalping_bot(
            exchange=state.exchange,
            fetcher=state.data_fetcher,
            storage=state.storage,
            mode=bot_config.get("mode", "paper"),
            symbol=bot_config.get("symbol", "BTC/USD"),
            capital=bot_config.get("initial_capital", 1000),
            trading_mode=bot_config.get("trading_mode", "medium"),
            risk_per_trade=bot_config.get("risk_per_trade", 0.01),
            ml_strategy=state.strategy,  # Pass ML strategy for predictions
        )

    # Start bot in background task
    state.scalping_task = asyncio.create_task(state.scalping_bot.start())

    return {
        "status": "started",
        "mode": state.scalping_bot.mode.value,
        "trading_mode": state.scalping_bot.get_trading_mode_info(),
        "symbol": state.scalping_bot.symbol,
        "capital": state.scalping_bot.capital
    }


@app.post("/api/scalping/stop")
async def stop_scalping_bot():
    """Stop the scalping bot."""
    if state.scalping_bot is None:
        return {"error": "Scalping bot is not running"}

    await state.scalping_bot.stop()

    # Cancel the task
    if state.scalping_task:
        state.scalping_task.cancel()
        state.scalping_task = None

    return {
        "status": "stopped",
        "final_stats": state.scalping_bot.get_status()
    }


@app.post("/api/scalping/pause")
async def pause_scalping_bot():
    """Pause the scalping bot (keeps positions)."""
    if state.scalping_bot is None:
        return {"error": "Scalping bot is not running"}

    await state.scalping_bot.pause()
    return {"status": "paused"}


@app.post("/api/scalping/resume")
async def resume_scalping_bot():
    """Resume a paused scalping bot."""
    if state.scalping_bot is None:
        return {"error": "Scalping bot is not running"}

    await state.scalping_bot.resume()
    return {"status": "resumed"}


@app.get("/api/scalping/signal")
async def get_scalping_signal(symbol: str = "BTC-USD", timeframe: str = "1m"):
    """Get current scalping signal without executing."""
    from strategy.scalping import ScalpingStrategy

    symbol = symbol.replace("-", "/")
    df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=200)

    if df.empty:
        return {"error": "Could not fetch data"}

    strategy = ScalpingStrategy()
    signal, confidence, details = strategy.generate_signal(df)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "signal": signal.value,
        "confidence": confidence,
        "details": details
    }


@app.get("/api/scalping/modes")
async def get_trading_modes():
    """Get all available trading modes and their settings."""
    from engine.scalping_bot import ScalpingBot
    return {
        "modes": ScalpingBot.get_available_trading_modes(),
        "current_mode": state.scalping_bot.get_trading_mode_info() if state.scalping_bot else None
    }


@app.post("/api/scalping/mode")
async def set_trading_mode(config: TradingModeConfig):
    """Change trading mode at runtime (while bot is running)."""
    if state.scalping_bot is None:
        return {"error": "Scalping bot is not initialized"}

    success = state.scalping_bot.set_trading_mode(
        config.trading_mode,
        config.custom_config
    )

    if success:
        return {
            "status": "success",
            "message": f"Trading mode changed to {config.trading_mode}",
            "mode_info": state.scalping_bot.get_trading_mode_info()
        }
    else:
        return {"error": f"Invalid trading mode: {config.trading_mode}"}


# ================== END SCALPING BOT API ENDPOINTS ==================


# ================== SHORT TERM BOT API ENDPOINTS ==================

class BotConfig(BaseModel):
    mode: str = "paper"
    capital: float = 1000
    symbol: str = "BTC/USD"
    trading_mode: str = "medium"  # conservative, medium, aggressive
    risk_per_trade: float = 0.02


@app.get("/api/short-term/status")
async def get_short_term_status():
    """Get short-term bot status and statistics."""
    if state.short_term_bot is None:
        return {"status": "not_initialized", "mode": None}
    return state.short_term_bot.get_status()


@app.post("/api/short-term/start")
async def start_short_term_bot(config: Optional[BotConfig] = None):
    """Start the short-term trading bot."""
    if state.short_term_bot and state.short_term_bot.status.value == "running":
        return {"error": "Short-term bot is already running"}

    bot_config = {
        "mode": config.mode if config else "paper",
        "initial_capital": config.capital if config else 1000,
        "symbol": config.symbol if config else "BTC/USD",
        "trading_mode": config.trading_mode if config else "medium",
        "risk_per_trade": config.risk_per_trade if config else 0.02
    }

    state.short_term_bot = ShortTermBot(
        exchange=state.exchange,
        fetcher=state.data_fetcher,
        storage=state.storage,
        config=bot_config,
        ml_strategy=state.strategy
    )

    async def run_bot():
        try:
            await state.short_term_bot.start()
        except Exception as e:
            print(f"Short-term bot error: {e}")

    state.short_term_task = asyncio.create_task(run_bot())

    return {
        "status": "started",
        "mode": bot_config["mode"],
        "symbol": bot_config["symbol"],
        "capital": bot_config["initial_capital"]
    }


@app.post("/api/short-term/stop")
async def stop_short_term_bot():
    """Stop the short-term trading bot."""
    if state.short_term_bot is None:
        return {"error": "Short-term bot is not running"}

    await state.short_term_bot.stop()
    if state.short_term_task:
        state.short_term_task.cancel()

    return {"status": "stopped", "final_stats": state.short_term_bot.get_status()}


@app.post("/api/short-term/pause")
async def pause_short_term_bot():
    """Pause the short-term bot."""
    if state.short_term_bot is None:
        return {"error": "Short-term bot is not running"}
    await state.short_term_bot.pause()
    return {"status": "paused"}


@app.post("/api/short-term/resume")
async def resume_short_term_bot():
    """Resume the short-term bot."""
    if state.short_term_bot is None:
        return {"error": "Short-term bot is not running"}
    await state.short_term_bot.resume()
    return {"status": "resumed"}


# ================== SWING TRADING BOT API ENDPOINTS ==================

@app.get("/api/swing/status")
async def get_swing_status():
    """Get swing trading bot status and statistics."""
    if state.swing_bot is None:
        return {"status": "not_initialized", "mode": None}
    return state.swing_bot.get_status()


@app.post("/api/swing/start")
async def start_swing_bot(config: Optional[BotConfig] = None):
    """Start the swing trading bot."""
    if state.swing_bot and state.swing_bot.status.value == "running":
        return {"error": "Swing trading bot is already running"}

    bot_config = {
        "mode": config.mode if config else "paper",
        "initial_capital": config.capital if config else 1000,
        "symbol": config.symbol if config else "BTC/USD",
        "trading_mode": config.trading_mode if config else "medium",
        "risk_per_trade": config.risk_per_trade if config else 0.03
    }

    state.swing_bot = SwingTradingBot(
        exchange=state.exchange,
        fetcher=state.data_fetcher,
        storage=state.storage,
        config=bot_config,
        ml_strategy=state.strategy
    )

    async def run_bot():
        try:
            await state.swing_bot.start()
        except Exception as e:
            print(f"Swing bot error: {e}")

    state.swing_task = asyncio.create_task(run_bot())

    return {
        "status": "started",
        "mode": bot_config["mode"],
        "symbol": bot_config["symbol"],
        "capital": bot_config["initial_capital"]
    }


@app.post("/api/swing/stop")
async def stop_swing_bot():
    """Stop the swing trading bot."""
    if state.swing_bot is None:
        return {"error": "Swing trading bot is not running"}

    await state.swing_bot.stop()
    if state.swing_task:
        state.swing_task.cancel()

    return {"status": "stopped", "final_stats": state.swing_bot.get_status()}


@app.post("/api/swing/pause")
async def pause_swing_bot():
    """Pause the swing trading bot."""
    if state.swing_bot is None:
        return {"error": "Swing trading bot is not running"}
    await state.swing_bot.pause()
    return {"status": "paused"}


@app.post("/api/swing/resume")
async def resume_swing_bot():
    """Resume the swing trading bot."""
    if state.swing_bot is None:
        return {"error": "Swing trading bot is not running"}
    await state.swing_bot.resume()
    return {"status": "resumed"}


# ================== LONG TERM BOT API ENDPOINTS ==================

@app.get("/api/long-term/status")
async def get_long_term_status():
    """Get long-term bot status and statistics."""
    if state.long_term_bot is None:
        return {"status": "not_initialized", "mode": None}
    return state.long_term_bot.get_status()


@app.post("/api/long-term/start")
async def start_long_term_bot(config: Optional[BotConfig] = None):
    """Start the long-term investment bot."""
    if state.long_term_bot and state.long_term_bot.status.value == "running":
        return {"error": "Long-term bot is already running"}

    bot_config = {
        "mode": config.mode if config else "paper",
        "initial_capital": config.capital if config else 1000,
        "symbol": config.symbol if config else "BTC/USD",
        "trading_mode": config.trading_mode if config else "medium",
        "risk_per_trade": config.risk_per_trade if config else 0.05
    }

    state.long_term_bot = LongTermBot(
        exchange=state.exchange,
        fetcher=state.data_fetcher,
        storage=state.storage,
        config=bot_config,
        ml_strategy=state.strategy
    )

    async def run_bot():
        try:
            await state.long_term_bot.start()
        except Exception as e:
            print(f"Long-term bot error: {e}")

    state.long_term_task = asyncio.create_task(run_bot())

    return {
        "status": "started",
        "mode": bot_config["mode"],
        "symbol": bot_config["symbol"],
        "capital": bot_config["initial_capital"]
    }


@app.post("/api/long-term/stop")
async def stop_long_term_bot():
    """Stop the long-term investment bot."""
    if state.long_term_bot is None:
        return {"error": "Long-term bot is not running"}

    await state.long_term_bot.stop()
    if state.long_term_task:
        state.long_term_task.cancel()

    return {"status": "stopped", "final_stats": state.long_term_bot.get_status()}


@app.post("/api/long-term/pause")
async def pause_long_term_bot():
    """Pause the long-term bot."""
    if state.long_term_bot is None:
        return {"error": "Long-term bot is not running"}
    await state.long_term_bot.pause()
    return {"status": "paused"}


@app.post("/api/long-term/resume")
async def resume_long_term_bot():
    """Resume the long-term bot."""
    if state.long_term_bot is None:
        return {"error": "Long-term bot is not running"}
    await state.long_term_bot.resume()
    return {"status": "resumed"}


# ================== ALL BOTS STATUS ENDPOINT ==================

@app.get("/api/bots/status")
async def get_all_bots_status():
    """Get status of all trading bots."""
    return convert_numpy_types({
        "scalping": state.scalping_bot.get_status() if state.scalping_bot else {"status": "not_initialized"},
        "short_term": state.short_term_bot.get_status() if state.short_term_bot else {"status": "not_initialized"},
        "swing": state.swing_bot.get_status() if state.swing_bot else {"status": "not_initialized"},
        "long_term": state.long_term_bot.get_status() if state.long_term_bot else {"status": "not_initialized"}
    })


# ================== MULTI-MODEL API ENDPOINTS ==================

# Store multi-model configuration
multi_model_config = {
    "enabled": False,
    "models": ["xgboost", "lightgbm"],
    "weights": {"xgboost": 0.5, "lightgbm": 0.5}
}


class MultiModelConfig(BaseModel):
    models: list[str]
    weights: dict[str, float]


@app.get("/api/multi-model/config")
async def get_multi_model_config():
    """Get current multi-model configuration."""
    from models.ml_models import MultiModel
    return {
        "enabled": multi_model_config["enabled"],
        "models": multi_model_config["models"],
        "weights": multi_model_config["weights"],
        "available_models": MultiModel.AVAILABLE_MODELS
    }


@app.post("/api/multi-model/config")
async def set_multi_model_config(config: MultiModelConfig):
    """Set multi-model configuration."""
    from models.ml_models import MultiModel

    # Validate models
    invalid_models = [m for m in config.models if m not in MultiModel.AVAILABLE_MODELS]
    if invalid_models:
        return {"error": f"Invalid models: {invalid_models}"}

    if len(config.models) < 2:
        return {"error": "At least 2 models are required for multi-model configuration"}

    # Validate weights sum to approximately 1
    weight_sum = sum(config.weights.values())
    if abs(weight_sum - 1.0) > 0.01:
        # Normalize weights
        for model in config.weights:
            config.weights[model] = config.weights[model] / weight_sum

    # Update configuration
    multi_model_config["enabled"] = True
    multi_model_config["models"] = config.models
    multi_model_config["weights"] = config.weights

    print(f"Multi-model configuration updated: {config.models} with weights {config.weights}")

    return {
        "status": "success",
        "message": f"Multi-model configuration applied with {len(config.models)} models",
        "config": multi_model_config
    }


@app.post("/api/multi-model/disable")
async def disable_multi_model():
    """Disable multi-model and revert to single model."""
    multi_model_config["enabled"] = False
    print("Multi-model configuration disabled")
    return {"status": "success", "message": "Multi-model disabled"}


@app.get("/api/multi-model/info")
async def get_multi_model_info():
    """Get information about multi-model system."""
    from models.ml_models import MultiModel
    return {
        "description": "Multi-model system allows running multiple ML models simultaneously with custom weights",
        "available_models": MultiModel.AVAILABLE_MODELS,
        "model_info": {
            "xgboost": {
                "name": "XGBoost",
                "type": "Gradient Boosting",
                "description": "High-performance gradient boosting"
            },
            "lightgbm": {
                "name": "LightGBM",
                "type": "Gradient Boosting",
                "description": "Fast and efficient gradient boosting"
            },
            "random_forest": {
                "name": "Random Forest",
                "type": "Ensemble",
                "description": "Ensemble of decision trees"
            },
            "prophet": {
                "name": "Prophet",
                "type": "Forecasting",
                "description": "Time series forecasting by Meta"
            }
        },
        "current_config": multi_model_config
    }


@app.get("/api/multi-model/predictions/{symbol}")
async def get_multi_model_predictions(symbol: str):
    """Get predictions from all available trained models for comparison."""
    from models.ml_models import (
        XGBoostModel, LightGBMModel, RandomForestModel,
        ProphetModel, TransformerModel, PPOModel, create_model
    )

    try:
        symbol = symbol.replace("-", "/")
        timeframe = state.config.get("trading", {}).get("timeframe", "1h")
        df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=200)

        if df.empty:
            return {"error": "No data available"}

        # Prepare features
        features_df = state.feature_engineer.generate_features(df)
        if features_df.empty:
            return {"error": "Could not create features"}

        # Get the latest row for prediction
        X = features_df.iloc[[-1]]

        # Model definitions with metadata
        model_info = {
            "xgboost": {"name": "XGBoost", "icon": "🚀", "type": "Gradient Boosting", "class": XGBoostModel},
            "lightgbm": {"name": "LightGBM", "icon": "⚡", "type": "Gradient Boosting", "class": LightGBMModel},
            "random_forest": {"name": "Random Forest", "icon": "🌲", "type": "Ensemble", "class": RandomForestModel},
            "prophet": {"name": "Prophet", "icon": "📈", "type": "Forecasting", "class": ProphetModel},
            "transformer": {"name": "Transformer", "icon": "🤖", "type": "Deep Learning", "class": TransformerModel},
            "ppo": {"name": "PPO", "icon": "🎯", "type": "Reinforcement Learning", "class": PPOModel},
        }

        predictions = {}
        models_dir = Path("models")

        # Also check for the generic trained_model.joblib and use currently loaded model
        generic_model_path = models_dir / "trained_model.joblib"
        current_model_type = state.config.get("model", {}).get("type", "xgboost")

        for model_key, info in model_info.items():
            try:
                # Check for trained model file
                model_path = models_dir / f"{model_key}_model.joblib"
                alt_model_path = models_dir / f"trained_{model_key}.joblib"

                # For transformer and ppo, check their specific file patterns
                if model_key == "transformer":
                    model_path = models_dir / "transformer_model.pt"
                    alt_model_path = models_dir / "transformer_model.joblib"
                elif model_key == "ppo":
                    model_path = models_dir / "ppo_model.zip"
                    alt_model_path = models_dir / "ppo_model.joblib"

                # Also check if this model type matches the generic trained_model.joblib
                use_generic = (model_key == current_model_type and
                              generic_model_path.exists() and
                              not model_path.exists() and
                              not alt_model_path.exists())

                # Try to load and predict
                if model_path.exists() or alt_model_path.exists() or use_generic:
                    if use_generic:
                        actual_path = generic_model_path
                    else:
                        actual_path = model_path if model_path.exists() else alt_model_path

                    try:
                        # Use currently loaded model if it matches the type
                        if (use_generic and state.model and
                            state.model.name == model_key and
                            state.model.is_trained):
                            model = state.model
                        else:
                            # Create and load model instance
                            model_config = state.config.copy()
                            model_config["model"] = {"type": model_key}
                            model = info["class"](model_config)
                            model.load(str(actual_path))

                        # Get prediction
                        if model_key == "prophet":
                            # Prophet needs the full dataframe
                            proba = model.predict_proba(df)
                        else:
                            proba = model.predict_proba(X)

                        # Handle different output formats
                        if isinstance(proba, np.ndarray):
                            if len(proba.shape) > 1:
                                prob_up = float(proba[-1, 1]) if proba.shape[1] > 1 else float(proba[-1, 0])
                            else:
                                prob_up = float(proba[-1])
                        else:
                            prob_up = float(proba)

                        # Determine signal
                        if prob_up >= 0.6:
                            signal = "BUY"
                        elif prob_up <= 0.4:
                            signal = "SELL"
                        else:
                            signal = "HOLD"

                        predictions[model_key] = {
                            "name": info["name"],
                            "icon": info["icon"],
                            "type": info["type"],
                            "signal": signal,
                            "confidence": round(abs(prob_up - 0.5) * 200, 1),  # 0-100%
                            "probability": round(prob_up * 100, 1),
                            "status": "active",
                            "weight": multi_model_config["weights"].get(model_key, 0)
                        }
                    except Exception as e:
                        predictions[model_key] = {
                            "name": info["name"],
                            "icon": info["icon"],
                            "type": info["type"],
                            "signal": "N/A",
                            "confidence": 0,
                            "probability": 50,
                            "status": "error",
                            "error": str(e)
                        }
                else:
                    predictions[model_key] = {
                        "name": info["name"],
                        "icon": info["icon"],
                        "type": info["type"],
                        "signal": "N/A",
                        "confidence": 0,
                        "probability": 50,
                        "status": "not_trained",
                        "error": "Model not trained"
                    }
            except Exception as e:
                predictions[model_key] = {
                    "name": info["name"],
                    "icon": info["icon"],
                    "type": info["type"],
                    "signal": "N/A",
                    "confidence": 0,
                    "probability": 50,
                    "status": "error",
                    "error": str(e)
                }

        # Calculate ensemble prediction (weighted average of active models)
        active_predictions = {k: v for k, v in predictions.items() if v["status"] == "active"}
        ensemble_signal = "N/A"
        ensemble_confidence = 0

        if active_predictions:
            total_weight = sum(p.get("weight", 1) for p in active_predictions.values())
            if total_weight == 0:
                total_weight = len(active_predictions)  # Equal weights if none set
                for k in active_predictions:
                    active_predictions[k]["weight"] = 1 / total_weight

            weighted_prob = sum(
                p["probability"] * (p.get("weight", 1) / total_weight)
                for p in active_predictions.values()
            )

            if weighted_prob >= 60:
                ensemble_signal = "BUY"
            elif weighted_prob <= 40:
                ensemble_signal = "SELL"
            else:
                ensemble_signal = "HOLD"

            ensemble_confidence = round(abs(weighted_prob - 50) * 2, 1)

        # Count agreements
        signals = [p["signal"] for p in predictions.values() if p["status"] == "active"]
        buy_count = signals.count("BUY")
        sell_count = signals.count("SELL")
        hold_count = signals.count("HOLD")

        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "predictions": predictions,
            "ensemble": {
                "signal": ensemble_signal,
                "confidence": ensemble_confidence,
                "active_models": len(active_predictions)
            },
            "agreement": {
                "buy": buy_count,
                "sell": sell_count,
                "hold": hold_count,
                "total_active": len(signals)
            },
            "current_price": float(df['close'].iloc[-1]) if not df.empty else None
        }

    except Exception as e:
        print(f"Error getting multi-model predictions: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


# ================== END MULTI-MODEL API ENDPOINTS ==================


# ================== CUSTOM INDICATOR API ENDPOINTS ==================

@app.post("/api/indicators/custom")
async def create_custom_indicator(indicator: CustomIndicatorCreate):
    """Create a new custom indicator from Pine Script."""
    try:
        storage = get_postgres_storage()

        # Validate Pine Script first
        validation = validate_script(indicator.pine_script)
        if not validation['valid']:
            raise HTTPException(status_code=400, detail=f"Invalid Pine Script: {validation['errors']}")

        # Create the indicator
        indicator_id = storage.create_indicator(
            name=indicator.name,
            short_name=indicator.short_name,
            pine_script=indicator.pine_script,
            description=indicator.description,
            is_overlay=indicator.is_overlay,
            category=indicator.category,
            default_settings=indicator.default_settings
        )

        return {
            "id": indicator_id,
            "name": indicator.name,
            "short_name": indicator.short_name,
            "message": "Custom indicator created successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating custom indicator: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/indicators/custom")
async def list_custom_indicators(
    enabled_only: bool = False,
    category: Optional[str] = None
):
    """List all custom indicators."""
    try:
        storage = get_postgres_storage()
        indicators = storage.list_indicators(enabled_only=enabled_only, category=category)
        return {"indicators": indicators}
    except Exception as e:
        logger.error(f"Error listing custom indicators: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/indicators/custom/{indicator_id}")
async def get_custom_indicator(indicator_id: int):
    """Get a specific custom indicator."""
    try:
        storage = get_postgres_storage()
        indicator = storage.get_indicator(indicator_id)
        if not indicator:
            raise HTTPException(status_code=404, detail="Indicator not found")
        return indicator
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting custom indicator: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/indicators/custom/{indicator_id}")
async def update_custom_indicator(indicator_id: int, update: CustomIndicatorUpdate):
    """Update a custom indicator."""
    try:
        storage = get_postgres_storage()

        # If Pine Script is being updated, validate it
        if update.pine_script:
            validation = validate_script(update.pine_script)
            if not validation['valid']:
                raise HTTPException(status_code=400, detail=f"Invalid Pine Script: {validation['errors']}")

        # Build update dict from non-None values
        update_data = {k: v for k, v in update.dict().items() if v is not None}

        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")

        success = storage.update_indicator(indicator_id, **update_data)
        if not success:
            raise HTTPException(status_code=404, detail="Indicator not found")

        return {"message": "Indicator updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating custom indicator: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/indicators/custom/{indicator_id}")
async def delete_custom_indicator(indicator_id: int):
    """Delete a custom indicator."""
    try:
        storage = get_postgres_storage()
        success = storage.delete_indicator(indicator_id)
        if not success:
            raise HTTPException(status_code=404, detail="Indicator not found")
        return {"message": "Indicator deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting custom indicator: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/indicators/custom/validate")
async def validate_pine_script(request: PineScriptValidate):
    """Validate Pine Script without saving."""
    try:
        result = validate_script(request.pine_script)
        return result
    except Exception as e:
        logger.error(f"Error validating Pine Script: {e}")
        return {
            "valid": False,
            "errors": [str(e)]
        }


@app.post("/api/indicators/custom/{indicator_id}/calculate/{symbol}")
async def calculate_custom_indicator(
    indicator_id: int,
    symbol: str,
    timeframe: str = "1h",
    limit: int = 500
):
    """Calculate custom indicator values for a symbol."""
    try:
        storage = get_postgres_storage()

        # Get the indicator
        indicator = storage.get_indicator(indicator_id)
        if not indicator:
            raise HTTPException(status_code=404, detail="Indicator not found")

        # Fetch OHLCV data
        symbol = symbol.replace("-", "/")
        df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=limit)

        if df.empty:
            raise HTTPException(status_code=404, detail="No data available for symbol")

        # Prepare OHLCV data for Pine Script interpreter
        ohlcv_data = {
            'open': df['open'].values,
            'high': df['high'].values,
            'low': df['low'].values,
            'close': df['close'].values,
            'volume': df['volume'].values,
            'time': (df.index.astype(np.int64) // 10**9).tolist()  # Unix timestamps
        }

        # Execute Pine Script
        result = parse_and_execute(indicator['pine_script'], ohlcv_data)

        if result.get('errors'):
            raise HTTPException(status_code=400, detail=f"Execution error: {result['errors']}")

        # Convert numpy arrays to lists for JSON serialization
        plots = []
        for plot in result.get('plots', []):
            plot_data = {
                'title': plot.get('title', 'Unnamed'),
                'color': plot.get('color', '#2962FF'),
                'linewidth': plot.get('linewidth', 2),
                'style': plot.get('style', 'line'),
                'values': convert_numpy_types(plot.get('data', []))
            }
            plots.append(plot_data)

        return {
            "indicator_id": indicator_id,
            "name": indicator['name'],
            "symbol": symbol,
            "timeframe": timeframe,
            "is_overlay": indicator['is_overlay'],
            "plots": plots,
            "hlines": result.get('hlines', []),
            "timestamps": ohlcv_data['time']
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating custom indicator: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/indicators/templates")
async def get_indicator_templates(
    category: Optional[str] = None,
    featured_only: bool = False
):
    """Get pre-built indicator templates."""
    try:
        storage = get_postgres_storage()
        templates = storage.get_templates(category=category, featured_only=featured_only)
        return {"templates": templates}
    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/indicators/templates/seed")
async def seed_indicator_templates():
    """Seed default indicator templates (admin function)."""
    try:
        storage = get_postgres_storage()
        storage.seed_default_templates()
        return {"message": "Default templates seeded successfully"}
    except Exception as e:
        logger.error(f"Error seeding templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/indicators/active")
async def get_active_indicators(chart_id: str = "default"):
    """Get all active indicators for a chart."""
    try:
        storage = get_postgres_storage()
        indicators = storage.get_active_indicators(chart_id=chart_id)
        return {"indicators": indicators}
    except Exception as e:
        logger.error(f"Error getting active indicators: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/indicators/custom/{indicator_id}/settings")
async def save_indicator_settings(indicator_id: int, settings: IndicatorSettingsUpdate):
    """Save indicator settings for a chart."""
    try:
        storage = get_postgres_storage()
        storage.save_indicator_settings(
            indicator_id=indicator_id,
            settings=settings.settings,
            chart_id=settings.chart_id
        )
        return {"message": "Settings saved successfully"}
    except Exception as e:
        logger.error(f"Error saving indicator settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/indicators/custom/{indicator_id}/toggle")
async def toggle_indicator(indicator_id: int, chart_id: str = "default", active: bool = True):
    """Toggle indicator active state for a chart."""
    try:
        storage = get_postgres_storage()
        storage.toggle_indicator_active(indicator_id, chart_id, active)
        return {"message": f"Indicator {'activated' if active else 'deactivated'} successfully"}
    except Exception as e:
        logger.error(f"Error toggling indicator: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/indicators/custom/from-template/{template_id}")
async def create_from_template(template_id: int, name: Optional[str] = None):
    """Create a custom indicator from a template."""
    try:
        storage = get_postgres_storage()

        # Get the template
        templates = storage.get_templates()
        template = next((t for t in templates if t['id'] == template_id), None)

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Create indicator from template
        indicator_id = storage.create_indicator(
            name=name or template['name'],
            short_name=template.get('short_name', template['name'][:10]),
            pine_script=template['pine_script'],
            description=template.get('description'),
            is_overlay=template.get('is_overlay', True),
            category=template.get('category')
        )

        return {
            "id": indicator_id,
            "name": name or template['name'],
            "message": "Indicator created from template successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating from template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== PYTHON INDICATOR API ENDPOINTS ==================

@app.get("/api/indicators/python")
async def list_python_indicators_api():
    """List all available Python indicators."""
    try:
        from features.python_indicators import list_python_indicators
        indicators = list_python_indicators()
        return {"indicators": indicators}
    except Exception as e:
        logger.error(f"Error listing Python indicators: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/indicators/python/builtin/{indicator_id}")
async def get_python_indicator_info(indicator_id: str):
    """Get information about a built-in Python indicator."""
    try:
        from features.python_indicators import get_python_indicator
        indicator = get_python_indicator(indicator_id)
        if not indicator:
            raise HTTPException(status_code=404, detail="Python indicator not found")
        return {
            "id": indicator_id,
            "name": indicator.name,
            "short_name": indicator.short_name,
            "description": indicator.description,
            "is_overlay": indicator.is_overlay,
            "type": "python",
            "default_settings": indicator.get_default_settings()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Python indicator: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/indicators/python/builtin/{indicator_id}/calculate/{symbol}")
async def calculate_python_indicator(
    indicator_id: str,
    symbol: str,
    timeframe: str = "5m",
    limit: int = 500,
    settings: Optional[dict] = None
):
    """
    Calculate built-in Python indicator values for a symbol.

    Returns drawing primitives (lines, boxes, labels) for the frontend to render.
    """
    try:
        from features.python_indicators import get_python_indicator

        # Get indicator instance with settings
        indicator = get_python_indicator(indicator_id, **(settings or {}))
        if not indicator:
            raise HTTPException(status_code=404, detail=f"Python indicator '{indicator_id}' not found")

        # Fetch OHLCV data
        symbol = symbol.replace("-", "/")
        df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=limit)

        if df.empty:
            raise HTTPException(status_code=404, detail="No data available for symbol")

        # Calculate the indicator
        output = indicator.calculate(df)

        # Convert timestamps in index to list for reference
        timestamps = (df.index.astype(np.int64) // 10**9).tolist()

        return {
            "indicator_id": indicator_id,
            "name": indicator.name,
            "short_name": indicator.short_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "is_overlay": indicator.is_overlay,
            "type": "python",
            "drawings": output.to_dict(),
            "timestamps": timestamps
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating Python indicator: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ================== CUSTOM PYTHON INDICATOR API ENDPOINTS ==================

@app.post("/api/indicators/python/custom")
async def create_custom_python_indicator(indicator: CustomPythonIndicatorCreate):
    """Create a new custom Python indicator."""
    try:
        storage = get_postgres_storage()
        indicator_id = storage.create_python_indicator(
            name=indicator.name,
            short_name=indicator.short_name,
            python_code=indicator.python_code,
            description=indicator.description,
            is_overlay=indicator.is_overlay,
            default_settings=indicator.default_settings
        )
        return {
            "id": indicator_id,
            "name": indicator.name,
            "message": "Custom Python indicator created successfully"
        }
    except Exception as e:
        logger.error(f"Error creating custom Python indicator: {e}")
        if "duplicate key" in str(e).lower():
            raise HTTPException(status_code=400, detail="Indicator with this name already exists")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/indicators/python/custom")
async def list_custom_python_indicators(enabled_only: bool = False):
    """List all custom Python indicators."""
    try:
        storage = get_postgres_storage()
        indicators = storage.list_python_indicators(enabled_only=enabled_only)
        return {"indicators": indicators}
    except Exception as e:
        logger.error(f"Error listing custom Python indicators: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/indicators/python/custom/{indicator_id}")
async def get_custom_python_indicator(indicator_id: int):
    """Get a specific custom Python indicator."""
    try:
        storage = get_postgres_storage()
        indicator = storage.get_python_indicator(indicator_id)
        if not indicator:
            raise HTTPException(status_code=404, detail="Python indicator not found")
        return indicator
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting custom Python indicator: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/indicators/python/custom/{indicator_id}")
async def update_custom_python_indicator(indicator_id: int, update: CustomPythonIndicatorUpdate):
    """Update a custom Python indicator."""
    try:
        storage = get_postgres_storage()
        update_dict = {k: v for k, v in update.dict().items() if v is not None}
        if not update_dict:
            raise HTTPException(status_code=400, detail="No fields to update")

        success = storage.update_python_indicator(indicator_id, **update_dict)
        if not success:
            raise HTTPException(status_code=404, detail="Python indicator not found")
        return {"message": "Python indicator updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating custom Python indicator: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/indicators/python/custom/{indicator_id}")
async def delete_custom_python_indicator(indicator_id: int):
    """Delete a custom Python indicator."""
    try:
        storage = get_postgres_storage()
        success = storage.delete_python_indicator(indicator_id)
        if not success:
            raise HTTPException(status_code=404, detail="Python indicator not found")
        return {"message": "Python indicator deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting custom Python indicator: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/indicators/python/custom/{indicator_id}/calculate/{symbol}")
async def calculate_custom_python_indicator(
    indicator_id: int,
    symbol: str,
    timeframe: str = "5m",
    limit: int = 500,
    settings: Optional[dict] = None
):
    """Calculate a custom Python indicator."""
    try:
        storage = get_postgres_storage()
        indicator = storage.get_python_indicator(indicator_id)
        if not indicator:
            raise HTTPException(status_code=404, detail="Python indicator not found")

        # Execute the Python code
        result = execute_custom_python_indicator(
            indicator['python_code'],
            symbol,
            timeframe,
            limit,
            settings or indicator.get('default_settings', {})
        )

        return {
            "indicator_id": indicator_id,
            "name": indicator['name'],
            "short_name": indicator['short_name'],
            "symbol": symbol,
            "timeframe": timeframe,
            "is_overlay": indicator['is_overlay'],
            "type": "custom_python",
            "drawings": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating custom Python indicator: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/indicators/python/execute/{symbol}")
async def execute_python_code(
    symbol: str,
    request: PythonCodeExecute,
    timeframe: str = "5m",
    limit: int = 500
):
    """Execute arbitrary Python code for indicator preview."""
    try:
        result = execute_custom_python_indicator(
            request.python_code,
            symbol,
            timeframe,
            limit,
            request.settings or {}
        )
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "type": "python_preview",
            "drawings": result
        }
    except Exception as e:
        logger.error(f"Error executing Python code: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def execute_custom_python_indicator(
    python_code: str,
    symbol: str,
    timeframe: str,
    limit: int,
    settings: dict
) -> dict:
    """Execute custom Python indicator code and return drawings."""
    import pandas as pd
    import numpy as np
    from datetime import datetime, timedelta, time
    import pytz
    from features.python_indicators import IndicatorOutput, Line, Box, Label, HLine, Plot

    # Fetch OHLCV data
    symbol = symbol.replace("-", "/")
    df = state.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=limit)

    if df.empty:
        raise ValueError("No data available for symbol")

    # Create output object for drawings
    output = IndicatorOutput()
    ny_tz = pytz.timezone('America/New_York')

    # Helper function to convert datetime to unix timestamp
    def ts(dt):
        if hasattr(dt, 'timestamp'):
            if dt.tzinfo is None:
                dt = ny_tz.localize(dt)
            return int(dt.timestamp())
        return int(dt)

    # Get today's date in NY timezone
    now_ny = datetime.now(ny_tz)
    today = now_ny.date()

    # ==================== SESSION HELPERS ====================
    # Session times (in NY timezone)
    # New York: 9:30 AM - 4:00 PM (DR period: 9:30-10:30)
    # London: 3:00 AM - 11:00 AM (DR period: 3:00-4:00)
    # Tokyo: 7:30 PM - 2:00 AM next day (DR period: 7:30-8:30)

    def make_session_time(date, hour, minute):
        """Create a timezone-aware datetime for a session time."""
        dt = datetime.combine(date, time(hour, minute))
        return ny_tz.localize(dt)

    # New York Session (today)
    StartOfSessionNewYork = ts(make_session_time(today, 9, 30))
    EndOfSessionNewYork = ts(make_session_time(today, 16, 0))
    OneHourFromStartOfSessionNewYork = ts(make_session_time(today, 10, 30))
    NYOpen = StartOfSessionNewYork
    NYClose = EndOfSessionNewYork

    # London Session (today - early morning NY time)
    StartOfSessionLondon = ts(make_session_time(today, 3, 0))
    EndOfSessionLondon = ts(make_session_time(today, 11, 0))
    OneHourFromStartOfSessionLondon = ts(make_session_time(today, 4, 0))
    LondonOpen = StartOfSessionLondon
    LondonClose = EndOfSessionLondon

    # Tokyo Session (starts previous evening NY time)
    yesterday = today - timedelta(days=1)
    StartOfSessionTokyo = ts(make_session_time(yesterday, 19, 30))
    EndOfSessionTokyo = ts(make_session_time(today, 2, 0))
    OneHourFromStartOfSessionTokyo = ts(make_session_time(yesterday, 20, 30))
    TokyoOpen = StartOfSessionTokyo
    TokyoClose = EndOfSessionTokyo

    # Price helpers from data
    high = df['high'].max()
    low = df['low'].min()
    latest_close = df['close'].iloc[-1]
    latest_open = df['open'].iloc[-1]
    latest_high = df['high'].iloc[-1]
    latest_low = df['low'].iloc[-1]

    # ==================== SESSION BOX VALUES ====================
    # Calculate DR (Defining Range) values for each session
    # DR = first hour of each session

    # Ensure df index is timezone-aware
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert(ny_tz)
    else:
        df.index = df.index.tz_convert(ny_tz)

    def get_session_box_values(start_ts, end_ts):
        """Get OHLC values for a session's DR period."""
        start_dt = pd.Timestamp(start_ts, unit='s', tz='America/New_York')
        end_dt = pd.Timestamp(end_ts, unit='s', tz='America/New_York')
        session_data = df[(df.index >= start_dt) & (df.index <= end_dt)]
        if session_data.empty:
            return None, None, None, None
        return (
            float(session_data['high'].max()),      # Box High
            float(session_data['open'].iloc[0]),    # Box Open
            float(session_data['low'].min()),       # Box Low
            float(session_data['close'].iloc[-1])   # Box Close
        )

    # NY DR Box (9:30-10:30)
    NYBoxHigh, NYBoxOpen, NYBoxLow, NYBoxClose = get_session_box_values(
        StartOfSessionNewYork, OneHourFromStartOfSessionNewYork
    )

    # London DR Box (3:00-4:00)
    LondonBoxHigh, LondonBoxOpen, LondonBoxLow, LondonBoxClose = get_session_box_values(
        StartOfSessionLondon, OneHourFromStartOfSessionLondon
    )

    # Tokyo DR Box (7:30-8:30 PM previous day)
    TokyoBoxHigh, TokyoBoxOpen, TokyoBoxLow, TokyoBoxClose = get_session_box_values(
        StartOfSessionTokyo, OneHourFromStartOfSessionTokyo
    )

    # IDR (Initial Defining Range) = body range (open/close extremes)
    def get_idr_values(box_high, box_open, box_low, box_close):
        """Get IDR (body range) from box values."""
        if box_high is None:
            return None, None
        return max(box_open, box_close), min(box_open, box_close)

    NYIDRHigh, NYIDRLow = get_idr_values(NYBoxHigh, NYBoxOpen, NYBoxLow, NYBoxClose)
    LondonIDRHigh, LondonIDRLow = get_idr_values(LondonBoxHigh, LondonBoxOpen, LondonBoxLow, LondonBoxClose)
    TokyoIDRHigh, TokyoIDRLow = get_idr_values(TokyoBoxHigh, TokyoBoxOpen, TokyoBoxLow, TokyoBoxClose)

    # Prepare execution context
    exec_globals = {
        # Libraries
        'pd': pd,
        'np': np,
        'datetime': datetime,
        'timedelta': timedelta,
        'time': time,
        # Data
        'df': df,
        'output': output,
        'settings': settings,
        # Helpers
        'ts': ts,
        # Drawing primitives
        'Line': Line,
        'Box': Box,
        'Label': Label,
        'HLine': HLine,
        'Plot': Plot,
        # Session times (unix timestamps)
        'StartOfSessionNewYork': StartOfSessionNewYork,
        'EndOfSessionNewYork': EndOfSessionNewYork,
        'OneHourFromStartOfSessionNewYork': OneHourFromStartOfSessionNewYork,
        'NYOpen': NYOpen,
        'NYClose': NYClose,
        'StartOfSessionLondon': StartOfSessionLondon,
        'EndOfSessionLondon': EndOfSessionLondon,
        'OneHourFromStartOfSessionLondon': OneHourFromStartOfSessionLondon,
        'LondonOpen': LondonOpen,
        'LondonClose': LondonClose,
        'StartOfSessionTokyo': StartOfSessionTokyo,
        'EndOfSessionTokyo': EndOfSessionTokyo,
        'OneHourFromStartOfSessionTokyo': OneHourFromStartOfSessionTokyo,
        'TokyoOpen': TokyoOpen,
        'TokyoClose': TokyoClose,
        # Price helpers
        'high': high,
        'low': low,
        'latest_close': latest_close,
        'latest_open': latest_open,
        'latest_high': latest_high,
        'latest_low': latest_low,
        # NY DR Box values
        'NYBoxHigh': NYBoxHigh,
        'NYBoxOpen': NYBoxOpen,
        'NYBoxLow': NYBoxLow,
        'NYBoxClose': NYBoxClose,
        'NYIDRHigh': NYIDRHigh,
        'NYIDRLow': NYIDRLow,
        # London DR Box values
        'LondonBoxHigh': LondonBoxHigh,
        'LondonBoxOpen': LondonBoxOpen,
        'LondonBoxLow': LondonBoxLow,
        'LondonBoxClose': LondonBoxClose,
        'LondonIDRHigh': LondonIDRHigh,
        'LondonIDRLow': LondonIDRLow,
        # Tokyo DR Box values
        'TokyoBoxHigh': TokyoBoxHigh,
        'TokyoBoxOpen': TokyoBoxOpen,
        'TokyoBoxLow': TokyoBoxLow,
        'TokyoBoxClose': TokyoBoxClose,
        'TokyoIDRHigh': TokyoIDRHigh,
        'TokyoIDRLow': TokyoIDRLow,
    }

    # Execute the user's Python code
    exec(python_code, exec_globals)

    # Get output and filter out any drawings with None/null values
    result = output.to_dict()

    # Filter lines - remove any with None values
    result['lines'] = [
        line for line in result['lines']
        if line.get('x1') is not None and line.get('y1') is not None
        and line.get('x2') is not None and line.get('y2') is not None
    ]

    # Filter boxes - remove any with None values
    result['boxes'] = [
        box for box in result['boxes']
        if box.get('x1') is not None and box.get('y1') is not None
        and box.get('x2') is not None and box.get('y2') is not None
    ]

    # Filter hlines - remove any with None values
    result['hlines'] = [
        hline for hline in result['hlines']
        if hline.get('y') is not None
    ]

    # Filter labels - remove any with None values
    result['labels'] = [
        label for label in result['labels']
        if label.get('x') is not None and label.get('y') is not None
    ]

    return result


# ================== END CUSTOM INDICATOR API ENDPOINTS ==================


# ================== SBC + DR COMBINED STRATEGY DASHBOARD ==================

@app.get("/sbc-dr-dashboard", response_class=HTMLResponse)
async def sbc_dr_dashboard_page(request: Request):
    """Serve the SBC + DR Combined Strategy Dashboard."""
    return templates.TemplateResponse("sbc_dr_dashboard.html", {"request": request})


@app.get("/api/sbc-dr/history")
async def get_sbc_dr_history():
    """Get full SBC + DR combined historical data from database."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host='localhost',
            database='robo_trader',
            user='utpalraina',
            password=''
        )
        cursor = conn.cursor()

        cursor.execute("""
            SELECT date, v5_signal, v6_signal, v6_reason, moon_nakshatra, tithi,
                   nakshatra_net, tithi_net, rashi_net, akshara_net, swara_net,
                   ny_session_change_pct, actual_direction, v5_correct, v6_correct, pnl_v6,
                   dr_high, dr_low, breakout_direction, retracement_back_to_dr,
                   session_high, session_low, dr_signal, sbc_dir, signals_agree,
                   combined_signal, dr_correct, combined_correct, pnl_combined,
                   ny_open, first_hour_high, first_hour_low, ny_close_1030,
                   post_1hr_high, post_1hr_low,
                   session_high_full, session_low_full, time_close_above_1hr_high, time_close_below_1hr_low
            FROM sbc_dr_combined
            ORDER BY date DESC
        """)

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        history = []
        for row in rows:
            record = dict(zip(columns, row))
            if record.get('date'):
                record['date'] = str(record['date'])
            history.append(convert_numpy_types(record))

        return {"history": history, "total": len(history)}
    except Exception as e:
        logger.error(f"Error fetching SBC-DR history: {e}")
        return {"error": str(e), "history": []}


@app.get("/api/sbc-dr/today")
async def get_sbc_dr_today():
    """Get today's SBC + DR combined signal with decision basis."""
    try:
        import pytz
        import requests
        from datetime import datetime, time
        from web.sbc_analysis import calculate_custom_sbc_analysis
        from web.sbc_market_rules import decide_neutral_signal

        ny_tz = pytz.timezone('America/New_York')
        now_ny = datetime.now(ny_tz)
        today_str = now_ny.strftime('%Y-%m-%d')
        day_of_week = now_ny.strftime('%A')

        # Get SBC analysis for today at NY open
        sbc = calculate_custom_sbc_analysis(
            name="Bitcoin",
            birth_date="2009-01-03",
            birth_time="18:15",
            latitude=0.0,
            longitude=0.0,
            analysis_date=today_str,
            analysis_time="09:30",
            timezone="America/New_York"
        )

        if not sbc or 'error' in sbc:
            return {"error": "Failed to calculate SBC analysis", "date": today_str}

        # Extract SBC data
        vw = sbc.get('vedha_weights', {})
        net_weight = vw.get('net_score', 0)

        vedhas_by_factor = sbc.get('vedhas_by_factor', {})
        nakshatra_net = vedhas_by_factor.get('nakshatra', {}).get('net', 0)
        tithi_net = vedhas_by_factor.get('tithi', {}).get('net', 0)
        rashi_net = vedhas_by_factor.get('rashi', {}).get('net', 0)
        akshara_net = vedhas_by_factor.get('akshara', {}).get('net', 0)
        swara_net = vedhas_by_factor.get('swara', {}).get('net', 0)

        tp = sbc.get('transit_positions', {})
        moon_nakshatra = tp.get('Moon', {}).get('nakshatra', '')
        current_tithi = sbc.get('current_tithi', '')

        # Calculate V5 signal (crypto inverted)
        if net_weight > 2.0:
            v5_signal = 'STRONGLY_BEARISH'
        elif net_weight > 0.5:
            v5_signal = 'MODERATELY_BEARISH'
        elif net_weight > -0.5:
            v5_signal = 'NEUTRAL'
        elif net_weight > -2.0:
            v5_signal = 'MODERATELY_BULLISH'
        else:
            v5_signal = 'STRONGLY_BULLISH'

        # Apply V6 rules if NEUTRAL
        if v5_signal == 'NEUTRAL':
            v6_signal, v6_reason = decide_neutral_signal(
                v5_signal, moon_nakshatra,
                nakshatra_net, tithi_net, rashi_net, akshara_net, swara_net,
                current_tithi
            )
        else:
            v6_signal = v5_signal
            v6_reason = 'Already directional'

        # Get DR signal from database for today
        dr_signal = None
        dr_high = None
        dr_low = None
        breakout_direction = None

        import psycopg2
        conn = psycopg2.connect(
            host='localhost',
            database='robo_trader',
            user='utpalraina',
            password=''
        )
        cursor = conn.cursor()
        cursor.execute("""
            SELECT dr_signal, dr_high, dr_low, breakout_direction
            FROM sbc_dr_combined
            WHERE date = %s
        """, (today_str,))
        dr_row = cursor.fetchone()

        if dr_row and dr_row[0]:
            dr_signal, dr_high, dr_low, breakout_direction = dr_row
        else:
            # Database doesn't have DR data for today - fetch real-time from Binance
            # Check if first hour has completed (after 10:30 AM NY)
            first_hour_complete = now_ny.time() >= time(10, 30)

            if first_hour_complete:
                # Calculate first hour time range
                first_hour_start = ny_tz.localize(datetime(now_ny.year, now_ny.month, now_ny.day, 9, 30))
                first_hour_end = ny_tz.localize(datetime(now_ny.year, now_ny.month, now_ny.day, 10, 30))

                # Convert to UTC timestamps for Binance
                start_ms = int(first_hour_start.astimezone(pytz.UTC).timestamp() * 1000)
                end_ms = int(first_hour_end.astimezone(pytz.UTC).timestamp() * 1000)

                # Fetch first hour candles from Binance
                url = "https://api.binance.com/api/v3/klines"
                params = {
                    'symbol': 'BTCUSDT',
                    'interval': '5m',
                    'startTime': start_ms,
                    'endTime': end_ms,
                    'limit': 15
                }

                try:
                    resp = requests.get(url, params=params, timeout=10)
                    if resp.status_code == 200:
                        klines = resp.json()
                        if klines and len(klines) > 0:
                            # Calculate first hour high and low
                            dr_high = max(float(k[2]) for k in klines)
                            dr_low = min(float(k[3]) for k in klines)

                            # Now check for breakout - fetch candles after first hour to current time
                            post_hour_start = end_ms
                            now_ms = int(now_ny.astimezone(pytz.UTC).timestamp() * 1000)

                            params2 = {
                                'symbol': 'BTCUSDT',
                                'interval': '5m',
                                'startTime': post_hour_start,
                                'endTime': now_ms,
                                'limit': 100
                            }
                            resp2 = requests.get(url, params=params2, timeout=10)
                            if resp2.status_code == 200:
                                post_klines = resp2.json()
                                if post_klines and len(post_klines) > 0:
                                    # Check for breakout (close above/below DR levels)
                                    for k in post_klines:
                                        close = float(k[4])
                                        if close > dr_high:
                                            breakout_direction = 'BULLISH'
                                            dr_signal = 'BULLISH'
                                            break
                                        elif close < dr_low:
                                            breakout_direction = 'BEARISH'
                                            dr_signal = 'BEARISH'
                                            break

                except Exception as e:
                    logger.warning(f"Failed to fetch real-time DR data: {e}")

        # Determine combined signal
        sbc_dir = 'BULLISH' if 'BULLISH' in v6_signal else ('BEARISH' if 'BEARISH' in v6_signal else None)

        if sbc_dir and dr_signal:
            signals_agree = (sbc_dir == dr_signal)
            if signals_agree:
                combined_signal = sbc_dir
                decision_reason = "SBC and DR both agree - HIGH CONFIDENCE"
            else:
                combined_signal = "CONFLICT"
                decision_reason = f"SBC says {sbc_dir}, DR says {dr_signal} - Follow DR (60.4% win rate in conflicts)"
        elif dr_signal:
            signals_agree = None
            combined_signal = dr_signal
            decision_reason = "SBC is neutral, following DR signal"
        elif sbc_dir:
            signals_agree = None
            combined_signal = sbc_dir
            decision_reason = "No DR signal yet, following SBC"
        else:
            signals_agree = None
            combined_signal = "NEUTRAL"
            decision_reason = "Both SBC and DR are neutral - NO TRADE"

        # Get historical accuracy for this nakshatra
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN combined_correct THEN 1 ELSE 0 END) as correct
            FROM sbc_dr_combined
            WHERE moon_nakshatra = %s AND signals_agree = true
        """, (moon_nakshatra,))
        nak_stats = cursor.fetchone()
        nakshatra_accuracy = None
        if nak_stats and nak_stats[0] and nak_stats[0] > 5:
            nakshatra_accuracy = f"{nak_stats[1]}/{nak_stats[0]} ({nak_stats[1]/nak_stats[0]*100:.1f}%)"

        return {
            "date": today_str,
            "day_of_week": day_of_week,
            "v5_signal": v5_signal,
            "v6_signal": v6_signal,
            "v6_reason": v6_reason,
            "moon_nakshatra": moon_nakshatra,
            "tithi": current_tithi,
            "nakshatra_net": nakshatra_net,
            "tithi_net": tithi_net,
            "rashi_net": rashi_net,
            "akshara_net": akshara_net,
            "swara_net": swara_net,
            "net_weight": net_weight,
            "dr_signal": dr_signal,
            "dr_high": dr_high,
            "dr_low": dr_low,
            "breakout_direction": breakout_direction,
            "signals_agree": signals_agree,
            "combined_signal": combined_signal,
            "decision_reason": decision_reason,
            "nakshatra_accuracy": nakshatra_accuracy
        }
    except Exception as e:
        logger.error(f"Error getting today's SBC-DR signal: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


@app.get("/api/sbc-dr/similar-cases")
async def get_similar_cases():
    """Get similar historical cases based on today's Moon nakshatra."""
    try:
        import pytz
        from datetime import datetime
        from web.sbc_analysis import calculate_custom_sbc_analysis

        ny_tz = pytz.timezone('America/New_York')
        now_ny = datetime.now(ny_tz)
        today_str = now_ny.strftime('%Y-%m-%d')

        # Get today's SBC
        sbc = calculate_custom_sbc_analysis(
            name="Bitcoin",
            birth_date="2009-01-03",
            birth_time="18:15",
            latitude=0.0,
            longitude=0.0,
            analysis_date=today_str,
            analysis_time="09:30",
            timezone="America/New_York"
        )

        if not sbc or 'error' in sbc:
            return {"error": "Failed to calculate SBC", "cases": []}

        tp = sbc.get('transit_positions', {})
        moon_nakshatra = tp.get('Moon', {}).get('nakshatra', '')
        current_tithi = sbc.get('current_tithi', '')

        import psycopg2
        conn = psycopg2.connect(
            host='localhost',
            database='robo_trader',
            user='utpalraina',
            password=''
        )
        cursor = conn.cursor()

        # Find similar cases: same nakshatra
        cursor.execute("""
            SELECT date, moon_nakshatra, tithi, v6_signal, dr_signal,
                   combined_signal, actual_direction, combined_correct, pnl_combined,
                   signals_agree, ny_open, first_hour_high, first_hour_low, ny_close_1030,
                   session_high_full, session_low_full, time_close_above_1hr_high, time_close_below_1hr_low
            FROM sbc_dr_combined
            WHERE moon_nakshatra = %s
              AND signals_agree IS NOT NULL
              AND date < %s
            ORDER BY date DESC
            LIMIT 20
        """, (moon_nakshatra, today_str))

        columns = ['date', 'moon_nakshatra', 'tithi', 'v6_signal', 'dr_signal',
                   'combined_signal', 'actual_direction', 'combined_correct', 'pnl_combined',
                   'signals_agree', 'ny_open', 'first_hour_high', 'first_hour_low', 'ny_close_1030',
                   'session_high_full', 'session_low_full', 'time_close_above_1hr_high', 'time_close_below_1hr_low']
        rows = cursor.fetchall()

        cases = []
        for row in rows:
            record = dict(zip(columns, row))
            if record.get('date'):
                record['date'] = str(record['date'])
            cases.append(convert_numpy_types(record))

        return {
            "today_nakshatra": moon_nakshatra,
            "today_tithi": current_tithi,
            "cases": cases
        }
    except Exception as e:
        logger.error(f"Error getting similar cases: {e}")
        return {"error": str(e), "cases": []}


@app.get("/trade-detail", response_class=HTMLResponse)
async def trade_detail_page(request: Request):
    """Serve the trade detail page."""
    return templates.TemplateResponse("trade_detail.html", {"request": request})


@app.get("/api/sbc-dr/trade/{date}")
async def get_trade_detail(date: str):
    """Get detailed trade data for a specific date."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host='localhost',
            database='robo_trader',
            user='utpalraina',
            password=''
        )
        cursor = conn.cursor()

        cursor.execute("""
            SELECT date, v5_signal, v6_signal, v6_reason, moon_nakshatra, tithi,
                   nakshatra_net, tithi_net, rashi_net, akshara_net, swara_net,
                   ny_session_change_pct, actual_direction, v5_correct, v6_correct, pnl_v6,
                   dr_high, dr_low, breakout_direction, retracement_back_to_dr,
                   session_high, session_low, dr_signal, sbc_dir, signals_agree,
                   combined_signal, dr_correct, combined_correct, pnl_combined
            FROM sbc_dr_combined
            WHERE date = %s
        """, (date,))

        row = cursor.fetchone()
        if not row:
            return {"error": "Trade not found"}

        columns = [desc[0] for desc in cursor.description]
        record = dict(zip(columns, row))
        if record.get('date'):
            record['date'] = str(record['date'])

        conn.close()
        return convert_numpy_types(record)
    except Exception as e:
        logger.error(f"Error getting trade detail: {e}")
        return {"error": str(e)}


@app.get("/api/sbc-dr/chart/{date}")
async def get_trade_chart(date: str, timeframe: str = "15m"):
    """Get OHLC chart data for a specific trade date."""
    try:
        from datetime import datetime, timedelta
        import pytz

        ny_tz = pytz.timezone('America/New_York')

        # Parse date
        trade_date = datetime.strptime(date, '%Y-%m-%d')

        # Map timeframe to Binance format
        tf_map = {
            '5m': '5m',
            '15m': '15m',
            '1h': '1h',
            '1d': '1d'
        }
        binance_tf = tf_map.get(timeframe, '15m')

        # Calculate time range for NY session (9:30 AM - 4:00 PM ET)
        # We want data from 8:00 AM to 5:00 PM to see before/after session
        start_dt = ny_tz.localize(datetime.combine(trade_date.date(), datetime.strptime('08:00', '%H:%M').time()))
        end_dt = ny_tz.localize(datetime.combine(trade_date.date(), datetime.strptime('17:00', '%H:%M').time()))

        # For daily timeframe, get surrounding days
        if timeframe == '1d':
            start_dt = trade_date - timedelta(days=30)
            end_dt = trade_date + timedelta(days=5)

        # Convert to timestamps
        start_ts = int(start_dt.timestamp() * 1000)
        end_ts = int(end_dt.timestamp() * 1000)

        # Fetch from Binance
        import requests
        url = 'https://api.binance.com/api/v3/klines'
        params = {
            'symbol': 'BTCUSDT',
            'interval': binance_tf,
            'startTime': start_ts,
            'endTime': end_ts,
            'limit': 1000
        }

        response = requests.get(url, params=params, timeout=30)
        if response.status_code != 200:
            return {"error": "Failed to fetch data from Binance", "candles": []}

        data = response.json()
        if not data:
            return {"error": "No data available", "candles": []}

        # Convert to lightweight-charts format
        candles = []
        for kline in data:
            candle_time = int(kline[0] / 1000)  # Convert to seconds
            candles.append({
                'time': candle_time,
                'open': float(kline[1]),
                'high': float(kline[2]),
                'low': float(kline[3]),
                'close': float(kline[4])
            })

        # Get DR range from database
        import psycopg2
        conn = psycopg2.connect(
            host='localhost',
            database='robo_trader',
            user='utpalraina',
            password=''
        )
        cursor = conn.cursor()
        cursor.execute("""
            SELECT dr_high, dr_low, session_high, session_low
            FROM sbc_dr_combined
            WHERE date = %s
        """, (date,))
        dr_row = cursor.fetchone()
        conn.close()

        dr_high = dr_row[0] if dr_row else None
        dr_low = dr_row[1] if dr_row else None
        session_high = dr_row[2] if dr_row else None
        session_low = dr_row[3] if dr_row else None

        # Calculate DR time range (9:30-10:00 AM ET)
        dr_start = ny_tz.localize(datetime.combine(trade_date.date(), datetime.strptime('09:30', '%H:%M').time()))
        dr_end = ny_tz.localize(datetime.combine(trade_date.date(), datetime.strptime('10:00', '%H:%M').time()))
        idr_end = ny_tz.localize(datetime.combine(trade_date.date(), datetime.strptime('10:30', '%H:%M').time()))

        return {
            "candles": candles,
            "dr_high": dr_high,
            "dr_low": dr_low,
            "dr_start": int(dr_start.timestamp()),
            "dr_end": int(dr_end.timestamp()),
            "idr_high": session_high,  # Using session high/low as proxy for IDR
            "idr_low": session_low,
            "idr_end": int(idr_end.timestamp()),
            "session_high": session_high,
            "session_low": session_low
        }

    except Exception as e:
        logger.error(f"Error getting chart data: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "candles": []}


@app.get("/api/sbc-dr/trades-list")
async def get_trades_list(
    start_date: str = None,
    end_date: str = None,
    signal_type: str = None,
    nakshatra: str = None,
    page: int = 1,
    per_page: int = 50
):
    """Get paginated list of trades with optional filters."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host='localhost',
            database='robo_trader',
            user='utpalraina',
            password=''
        )
        cursor = conn.cursor()

        # Build query
        where_clauses = []
        params = []

        if start_date:
            where_clauses.append("date >= %s")
            params.append(start_date)
        if end_date:
            where_clauses.append("date <= %s")
            params.append(end_date)
        if nakshatra:
            where_clauses.append("moon_nakshatra = %s")
            params.append(nakshatra)
        if signal_type == 'AGREE':
            where_clauses.append("signals_agree = true")
        elif signal_type == 'CONFLICT':
            where_clauses.append("signals_agree = false")
        elif signal_type in ['BULLISH', 'BEARISH']:
            where_clauses.append("combined_signal LIKE %s")
            params.append(f'%{signal_type}%')

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Get total count
        cursor.execute(f"SELECT COUNT(*) FROM sbc_dr_combined WHERE {where_sql}", params)
        total = cursor.fetchone()[0]

        # Get paginated results
        offset = (page - 1) * per_page
        cursor.execute(f"""
            SELECT date, moon_nakshatra, tithi, v6_signal, dr_signal,
                   combined_signal, actual_direction, combined_correct, pnl_combined,
                   signals_agree, ny_session_change_pct
            FROM sbc_dr_combined
            WHERE {where_sql}
            ORDER BY date DESC
            LIMIT %s OFFSET %s
        """, params + [per_page, offset])

        columns = ['date', 'moon_nakshatra', 'tithi', 'v6_signal', 'dr_signal',
                   'combined_signal', 'actual_direction', 'combined_correct', 'pnl_combined',
                   'signals_agree', 'ny_session_change_pct']
        rows = cursor.fetchall()

        trades = []
        for row in rows:
            record = dict(zip(columns, row))
            if record.get('date'):
                record['date'] = str(record['date'])
            trades.append(convert_numpy_types(record))

        conn.close()

        return {
            "trades": trades,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page
        }
    except Exception as e:
        logger.error(f"Error getting trades list: {e}")
        return {"error": str(e), "trades": []}


@app.get("/sbc-dr-history", response_class=HTMLResponse)
async def sbc_dr_history_page(request: Request):
    """SBC + DR Historical Data page."""
    return templates.TemplateResponse("sbc_dr_history.html", {"request": request})


@app.get("/api/sbc-dr-history")
async def get_sbc_dr_history():
    """Get all historical SBC + DR data since 5-minute candles available (Sept 2017)."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host='localhost',
            database='robo_trader',
            user='utpalraina',
            password=''
        )
        cursor = conn.cursor()

        cursor.execute("""
            SELECT date, moon_nakshatra, tithi, v6_signal, dr_signal,
                   combined_signal, actual_direction, combined_correct, pnl_combined,
                   signals_agree, ny_open, first_hour_high, first_hour_low, ny_close_1030,
                   session_high_full, session_low_full, time_close_above_1hr_high, time_close_below_1hr_low
            FROM sbc_dr_combined
            WHERE date >= '2017-09-01'
            ORDER BY date DESC
        """)

        columns = ['date', 'moon_nakshatra', 'tithi', 'v6_signal', 'dr_signal',
                   'combined_signal', 'actual_direction', 'combined_correct', 'pnl_combined',
                   'signals_agree', 'ny_open', 'first_hour_high', 'first_hour_low', 'ny_close_1030',
                   'session_high_full', 'session_low_full', 'time_close_above_1hr_high', 'time_close_below_1hr_low']
        rows_data = cursor.fetchall()

        rows = []
        for row in rows_data:
            record = dict(zip(columns, row))
            if record.get('date'):
                record['date'] = str(record['date'])
            rows.append(convert_numpy_types(record))

        conn.close()

        return {"rows": rows, "total": len(rows)}
    except Exception as e:
        logger.error(f"Error getting SBC DR history: {e}")
        return {"error": str(e), "rows": []}


# ================== END SBC + DR COMBINED STRATEGY ==================


# ================== JENKINS TRADING METHODS ==================

from web.jenkins_analysis import (
    full_jenkins_analysis,
    calculate_square_root_levels,
    calculate_time_conversion_bar,
    calculate_overlap_zones,
    calculate_gann_angles,
    calculate_measured_moves,
    # Planetary methods
    get_planetary_positions,
    calculate_planetary_square_outs,
    calculate_planetary_aspects,
    calculate_mars_jupiter_cycle,
    calculate_jupiter_saturn_cycle,
    get_retrograde_status,
    # Asset profiles
    get_asset_profile,
    get_all_asset_profiles,
    get_assets_by_type,
    calculate_birth_cycles,
    calculate_daily_square_outs,
    backtest_jenkins_square_outs,
    ASSET_PROFILES
)


class JenkinsAnalyzeRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"
    bars: int = 100


@app.get("/jenkins", response_class=HTMLResponse)
async def jenkins_page(request: Request):
    """Jenkins Trading Methods page."""
    return templates.TemplateResponse("jenkins.html", {"request": request})


@app.post("/api/jenkins/analyze")
async def jenkins_analyze(req: JenkinsAnalyzeRequest):
    """Run full Jenkins analysis on a symbol."""
    try:
        # Map timeframe to exchange format
        tf_map = {
            '5m': '5m', '15m': '15m', '1h': '1h', '4h': '4h',
            '1d': '1d', '1w': '1w'
        }
        timeframe = tf_map.get(req.timeframe, '1h')

        # Fetch candle data
        if state.data_fetcher is None:
            # Initialize data fetcher if not available
            config = load_config()
            exchange = get_exchange(config)
            data_fetcher = DataFetcher(exchange, config)
        else:
            data_fetcher = state.data_fetcher

        # Fetch OHLCV data (signature: symbol, timeframe, since=None, limit=1000)
        df = await run_in_executor(
            data_fetcher.fetch_ohlcv,
            req.symbol,
            timeframe,
            None,  # since - not needed
            req.bars  # limit
        )

        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {req.symbol}")

        # Convert to list of candle dicts
        candles = []
        for idx, row in df.iterrows():
            # Handle various timestamp formats
            if hasattr(idx, 'timestamp'):
                ts = int(idx.timestamp())
            elif 'timestamp' in row:
                ts = int(row['timestamp'])
            elif isinstance(idx, (int, float)):
                ts = int(idx)
            else:
                ts = 0
            candles.append({
                'timestamp': ts,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row.get('volume', 0))
            })

        # Detect asset type from symbol
        symbol_upper = req.symbol.upper()
        if any(x in symbol_upper for x in ['BTC', 'ETH', 'SOL', 'XRP', 'ADA', 'DOGE', 'AVAX', 'DOT']):
            asset_type = 'crypto'
        elif any(x in symbol_upper for x in ['SPY', 'QQQ', 'DJI', 'IWM', 'ES', 'NQ', 'YM', 'RTY']):
            asset_type = 'index'
        elif any(x in symbol_upper for x in ['GOLD', 'XAU', 'SILVER', 'XAG', 'GC', 'SI', 'HG', 'PL']):
            asset_type = 'metal'
        elif any(x in symbol_upper for x in ['CL', 'CRUDE', 'OIL', 'NG', 'RB', 'HO']):
            asset_type = 'commodity'
        else:
            asset_type = 'stock'

        # Run Jenkins analysis with asset type
        analysis = full_jenkins_analysis(candles, asset_type=asset_type)

        return convert_numpy_types({
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "bars": len(candles),
            "candles": candles,
            "analysis": analysis
        })

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Jenkins analysis error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/sqrt-levels")
async def get_sqrt_levels(price: float):
    """Calculate square root support/resistance levels for a price."""
    try:
        levels = calculate_square_root_levels(price)
        return convert_numpy_types(levels)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/tcb")
async def get_tcb(bar_height: float, scale: float = 1.0):
    """Calculate Time Conversion Bar projections."""
    try:
        tcb = calculate_time_conversion_bar(bar_height, scale)
        return convert_numpy_types(tcb)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/overlap")
async def get_overlap(prev_high: float, prev_low: float):
    """Calculate overlap zones for counter-trend entries."""
    try:
        zones = calculate_overlap_zones(prev_high, prev_low)
        return convert_numpy_types(zones)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/gann-angles")
async def get_gann_angles(price: float, time_units: int = 20, scale: float = 1.0):
    """Calculate Gann angle projections from a pivot."""
    try:
        angles = calculate_gann_angles(price, time_units, scale)
        return convert_numpy_types(angles)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Planetary Methods (Jenkins Astro) ----

@app.get("/api/jenkins/planetary/positions")
async def get_planetary_positions_api(lat: float = 40.7128, lon: float = -74.0060):
    """Get current geocentric and heliocentric planetary positions."""
    try:
        positions = get_planetary_positions(location=(lat, lon))
        return convert_numpy_types(positions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/planetary/square-outs")
async def get_planetary_square_outs_api(price: float):
    """Find planetary square outs for a given price."""
    try:
        square_outs = calculate_planetary_square_outs(price)
        return convert_numpy_types(square_outs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/planetary/aspects")
async def get_planetary_aspects_api():
    """Get current planetary aspects."""
    try:
        aspects = calculate_planetary_aspects()
        return convert_numpy_types(aspects)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/planetary/mars-jupiter")
async def get_mars_jupiter_cycle_api():
    """Get Mars/Jupiter synodic cycle information."""
    try:
        cycle = calculate_mars_jupiter_cycle()
        return convert_numpy_types(cycle)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/planetary/jupiter-saturn")
async def get_jupiter_saturn_cycle_api():
    """Get Jupiter/Saturn 20-year cycle information."""
    try:
        cycle = calculate_jupiter_saturn_cycle()
        return convert_numpy_types(cycle)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/planetary/retrogrades")
async def get_retrogrades_api():
    """Get current retrograde status of all planets."""
    try:
        status = get_retrograde_status()
        return convert_numpy_types(status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Asset Profile Endpoints
@app.get("/api/jenkins/assets")
async def get_all_assets():
    """Get all predefined asset profiles."""
    try:
        return convert_numpy_types(get_all_asset_profiles())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/assets/{symbol}")
async def get_asset(symbol: str):
    """Get asset profile by symbol."""
    try:
        profile = get_asset_profile(symbol)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")
        return convert_numpy_types(profile)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/assets/type/{asset_type}")
async def get_assets_by_type_api(asset_type: str):
    """Get all assets of a specific type (crypto, stock, index, metal)."""
    try:
        assets = get_assets_by_type(asset_type)
        return convert_numpy_types(assets)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/birth-cycles/{symbol}")
async def get_birth_cycles(symbol: str):
    """Get Jenkins birth-based cycles for an asset."""
    try:
        profile = get_asset_profile(symbol)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")
        cycles = calculate_birth_cycles(profile)
        return convert_numpy_types(cycles)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class JenkinsBacktestRequest(BaseModel):
    symbol: str
    timeframe: str = "1d"
    bars: int = 365


@app.post("/api/jenkins/backtest")
async def jenkins_backtest(req: JenkinsBacktestRequest):
    """
    Backtest Jenkins Time = Price methodology on historical data.
    Returns accuracy stats and individual swing predictions.
    """
    try:
        # Map timeframe
        timeframe_map = {
            '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '1h', '4h': '4h', '1d': '1d', '1w': '1w'
        }
        timeframe = timeframe_map.get(req.timeframe, '1d')

        # Get data fetcher
        if state.data_fetcher is None:
            config = load_config()
            exchange = get_exchange(config)
            data_fetcher = DataFetcher(exchange, config)
        else:
            data_fetcher = state.data_fetcher

        # Fetch historical data
        df = await run_in_executor(
            data_fetcher.fetch_ohlcv,
            req.symbol,
            timeframe,
            None,
            req.bars
        )

        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {req.symbol}")

        # Convert to candle dicts
        candles = []
        for idx, row in df.iterrows():
            if hasattr(idx, 'timestamp'):
                ts = int(idx.timestamp())
            elif 'timestamp' in row:
                ts = int(row['timestamp'])
            elif isinstance(idx, (int, float)):
                ts = int(idx)
            else:
                ts = 0
            candles.append({
                'timestamp': ts,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close'])
            })

        # Detect asset type
        symbol_upper = req.symbol.upper()
        if any(x in symbol_upper for x in ['BTC', 'ETH', 'SOL', 'XRP', 'ADA']):
            asset_type = 'crypto'
        elif any(x in symbol_upper for x in ['SPY', 'QQQ', 'ES', 'NQ']):
            asset_type = 'index'
        elif any(x in symbol_upper for x in ['GOLD', 'XAU', 'SILVER']):
            asset_type = 'metal'
        elif any(x in symbol_upper for x in ['CL', 'NG']):
            asset_type = 'commodity'
        else:
            asset_type = 'stock'

        # Run backtest
        results = backtest_jenkins_square_outs(candles, asset_type)

        return convert_numpy_types({
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "bars": len(candles),
            "backtest": results
        })

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Jenkins backtest error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== END JENKINS TRADING METHODS ==================


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the web server."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
