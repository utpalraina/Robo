"""Data storage module for persisting market data."""

import pandas as pd
import sqlite3
from pathlib import Path
from typing import Optional, List
from loguru import logger
from datetime import datetime


class DataStorage:
    """SQLite-based storage for market data."""

    def __init__(self, db_path: str = "data/market_data.db"):
        """
        Initialize DataStorage.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # OHLCV data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                UNIQUE(symbol, timeframe, timestamp)
            )
        """)

        # Trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                amount REAL NOT NULL,
                cost REAL NOT NULL,
                timestamp DATETIME NOT NULL,
                order_id TEXT,
                is_paper BOOLEAN DEFAULT FALSE
            )
        """)

        # Model performance table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                accuracy REAL,
                precision_score REAL,
                recall REAL,
                f1_score REAL,
                profit_factor REAL,
                sharpe_ratio REAL,
                timestamp DATETIME NOT NULL
            )
        """)

        # Open positions table (for persistence across restarts)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS open_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                side TEXT NOT NULL,
                size REAL NOT NULL,
                entry_price REAL NOT NULL,
                entry_time DATETIME NOT NULL,
                stop_loss REAL,
                take_profit REAL,
                order_id TEXT,
                stop_loss_order_id TEXT,
                is_paper BOOLEAN DEFAULT FALSE,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_time
            ON ohlcv(symbol, timeframe, timestamp)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_symbol
            ON open_positions(symbol)
        """)

        # Candle snapshots table with indicators, predictions, and explanations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candle_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp_utc DATETIME NOT NULL,
                timestamp_ny TEXT NOT NULL,
                -- OHLCV data
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                -- Momentum Indicators
                rsi_14 REAL,
                rsi_7 REAL,
                stoch_k REAL,
                stoch_d REAL,
                cci REAL,
                roc_10 REAL,
                momentum_10 REAL,
                -- Trend Indicators
                macd REAL,
                macd_signal REAL,
                macd_hist REAL,
                adx REAL,
                di_plus REAL,
                di_minus REAL,
                ema_9 REAL,
                ema_21 REAL,
                ema_50 REAL,
                sma_20 REAL,
                sma_50 REAL,
                -- Volatility Indicators
                atr_14 REAL,
                atr_pct REAL,
                bb_upper REAL,
                bb_middle REAL,
                bb_lower REAL,
                bb_width REAL,
                bb_pct REAL,
                -- Volume Indicators
                volume_ratio REAL,
                obv REAL,
                vwap REAL,
                -- Prediction
                prediction TEXT,
                confidence REAL,
                -- Signal counts
                bullish_count INTEGER,
                bearish_count INTEGER,
                neutral_count INTEGER,
                -- Explanation (JSON)
                explanation TEXT,
                -- Validation fields (filled after next candle arrives)
                actual_outcome TEXT,          -- What actually happened: UP/DOWN/FLAT
                price_change_pct REAL,        -- Percentage change from close to next close
                next_close REAL,              -- Close price of next candle
                prediction_correct INTEGER,   -- 1=correct, 0=incorrect, NULL=not validated
                validated_at DATETIME,        -- When validation was performed
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timestamp_utc)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_symbol_time
            ON candle_snapshots(symbol, timestamp_utc)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_ny_time
            ON candle_snapshots(symbol, timestamp_ny)
        """)

        # =====================================================
        # ICT (Inner Circle Trader) Indicators Tables
        # =====================================================

        # Fair Value Gaps (FVG) table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ict_fvg (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                detected_at DATETIME NOT NULL,
                candle_timestamp DATETIME NOT NULL,
                type TEXT NOT NULL,  -- 'bullish' or 'bearish'
                top_price REAL NOT NULL,
                bottom_price REAL NOT NULL,
                gap_size REAL NOT NULL,
                gap_pct REAL NOT NULL,
                midpoint REAL NOT NULL,
                filled BOOLEAN DEFAULT FALSE,
                filled_pct REAL DEFAULT 0,
                filled_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timeframe, candle_timestamp, type)
            )
        """)

        # Market Structure Shift (MSS) table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ict_mss (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                detected_at DATETIME NOT NULL,
                trigger_timestamp DATETIME NOT NULL,
                type TEXT NOT NULL,  -- 'bullish' or 'bearish'
                broken_level REAL NOT NULL,
                break_price REAL NOT NULL,
                strength REAL,
                confirmed BOOLEAN DEFAULT FALSE,
                invalidated BOOLEAN DEFAULT FALSE,
                invalidated_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timeframe, trigger_timestamp, type)
            )
        """)

        # Order Blocks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ict_order_blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                detected_at DATETIME NOT NULL,
                candle_timestamp DATETIME NOT NULL,
                type TEXT NOT NULL,  -- 'bullish' or 'bearish'
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                open_price REAL NOT NULL,
                close_price REAL NOT NULL,
                volume REAL,
                is_high_volume BOOLEAN,
                displacement_size REAL,
                tested BOOLEAN DEFAULT FALSE,
                tested_at DATETIME,
                mitigated BOOLEAN DEFAULT FALSE,
                mitigated_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timeframe, candle_timestamp, type)
            )
        """)

        # Breaker Blocks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ict_breaker_blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                detected_at DATETIME NOT NULL,
                candle_timestamp DATETIME NOT NULL,
                type TEXT NOT NULL,  -- 'bullish' or 'bearish' (new direction)
                original_type TEXT NOT NULL,  -- original order block type
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                mitigated_at_timestamp DATETIME,
                tested BOOLEAN DEFAULT FALSE,
                tested_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timeframe, candle_timestamp, type)
            )
        """)

        # Liquidity Zones table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ict_liquidity_zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                detected_at DATETIME NOT NULL,
                first_touch_timestamp DATETIME NOT NULL,
                type TEXT NOT NULL,  -- 'buy_side' or 'sell_side'
                level_price REAL NOT NULL,
                touches INTEGER DEFAULT 1,
                swept BOOLEAN DEFAULT FALSE,
                swept_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timeframe, level_price, type)
            )
        """)

        # Displacement candles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ict_displacement (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                detected_at DATETIME NOT NULL,
                candle_timestamp DATETIME NOT NULL,
                type TEXT NOT NULL,  -- 'bullish' or 'bearish'
                open_price REAL NOT NULL,
                close_price REAL NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                body_size REAL NOT NULL,
                body_atr_ratio REAL,
                body_to_range_ratio REAL,
                is_high_volume BOOLEAN,
                volume REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timeframe, candle_timestamp)
            )
        """)

        # Swing Points table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ict_swing_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                detected_at DATETIME NOT NULL,
                candle_timestamp DATETIME NOT NULL,
                type TEXT NOT NULL,  -- 'high' or 'low'
                price REAL NOT NULL,
                broken BOOLEAN DEFAULT FALSE,
                broken_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timeframe, candle_timestamp, type)
            )
        """)

        # OTE (Optimal Trade Entry) Levels snapshot table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ict_ote_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                detected_at DATETIME NOT NULL,
                swing_high REAL NOT NULL,
                swing_low REAL NOT NULL,
                range_size REAL NOT NULL,
                equilibrium_50 REAL NOT NULL,
                ote_62 REAL NOT NULL,
                ote_705 REAL NOT NULL,
                ote_79 REAL NOT NULL,
                target_1 REAL,
                target_2 REAL,
                target_final REAL,
                current_zone TEXT,  -- 'premium', 'discount', 'deep_premium', 'deep_discount'
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Premium/Discount Zone snapshots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ict_premium_discount (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                detected_at DATETIME NOT NULL,
                range_high REAL NOT NULL,
                range_low REAL NOT NULL,
                equilibrium REAL NOT NULL,
                current_price REAL NOT NULL,
                position_pct REAL NOT NULL,
                zone TEXT NOT NULL,  -- 'premium', 'discount', 'deep_premium', 'deep_discount'
                bias TEXT NOT NULL,  -- 'bullish' or 'bearish'
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Market Structure Analysis snapshots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ict_market_structure (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                detected_at DATETIME NOT NULL,
                trend TEXT NOT NULL,  -- 'bullish', 'bearish', 'neutral'
                structure TEXT NOT NULL,  -- 'uptrend', 'downtrend', 'ranging'
                hh_count INTEGER DEFAULT 0,  -- Higher Highs
                hl_count INTEGER DEFAULT 0,  -- Higher Lows
                lh_count INTEGER DEFAULT 0,  -- Lower Highs
                ll_count INTEGER DEFAULT 0,  -- Lower Lows
                bullish_score INTEGER DEFAULT 0,
                bearish_score INTEGER DEFAULT 0,
                last_swing_high REAL,
                last_swing_low REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ICT Trading Bias - Combined analysis
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ict_trading_bias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                detected_at DATETIME NOT NULL,
                bias TEXT NOT NULL,  -- 'bullish', 'bearish', 'neutral'
                confidence REAL NOT NULL,
                bullish_score INTEGER DEFAULT 0,
                bearish_score INTEGER DEFAULT 0,
                -- Component signals
                fvg_signal TEXT,
                mss_signal TEXT,
                ob_signal TEXT,
                zone_signal TEXT,
                structure_signal TEXT,
                -- Validation
                actual_outcome TEXT,  -- What actually happened
                prediction_correct INTEGER,
                validated_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for ICT tables
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ict_fvg_symbol_time
            ON ict_fvg(symbol, timeframe, detected_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ict_mss_symbol_time
            ON ict_mss(symbol, timeframe, detected_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ict_ob_symbol_time
            ON ict_order_blocks(symbol, timeframe, detected_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ict_bias_symbol_time
            ON ict_trading_bias(symbol, timeframe, detected_at)
        """)

        conn.commit()
        conn.close()
        logger.debug("Database initialized")

    def save_ohlcv(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str
    ):
        """
        Save OHLCV data to database.

        Args:
            df: DataFrame with OHLCV data
            symbol: Trading pair
            timeframe: Candle timeframe
        """
        conn = sqlite3.connect(self.db_path)

        df_to_save = df.reset_index().copy()
        df_to_save["symbol"] = symbol
        df_to_save["timeframe"] = timeframe

        df_to_save.to_sql(
            "ohlcv",
            conn,
            if_exists="append",
            index=False,
            method="multi"
        )

        conn.close()
        logger.debug(f"Saved {len(df)} candles for {symbol}")

    def load_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Load OHLCV data from database.

        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            DataFrame with OHLCV data
        """
        conn = sqlite3.connect(self.db_path)

        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv
            WHERE symbol = ? AND timeframe = ?
        """
        params = [symbol, timeframe]

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        query += " ORDER BY timestamp"

        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)

        return df

    def save_trade(
        self,
        symbol: str,
        side: str,
        price: float,
        amount: float,
        cost: float,
        order_id: Optional[str] = None,
        is_paper: bool = False
    ):
        """
        Save a trade record.

        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            price: Execution price
            amount: Trade amount
            cost: Total cost
            order_id: Exchange order ID
            is_paper: Whether this is a paper trade
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO trades (symbol, side, price, amount, cost, timestamp, order_id, is_paper)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (symbol, side, price, amount, cost, datetime.now(), order_id, is_paper))

        conn.commit()
        conn.close()
        logger.info(f"Saved trade: {side} {amount} {symbol} @ {price}")

    def save_scalp_trade(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        amount: float,
        pnl: float,
        pnl_pct: float,
        exit_reason: str,
        duration_seconds: float,
        is_paper: bool = True
    ):
        """
        Save a complete scalp trade with P&L info.

        Args:
            symbol: Trading pair
            side: 'long' or 'short'
            entry_price: Entry price
            exit_price: Exit price
            amount: Trade size
            pnl: Profit/loss in dollars
            pnl_pct: Profit/loss percentage
            exit_reason: 'take_profit', 'stop_loss', 'signal', etc.
            duration_seconds: Trade duration
            is_paper: Whether paper trade
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Ensure scalp_trades table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scalp_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                amount REAL NOT NULL,
                pnl REAL NOT NULL,
                pnl_pct REAL NOT NULL,
                exit_reason TEXT,
                duration_seconds REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_paper INTEGER DEFAULT 1
            )
        """)

        cursor.execute("""
            INSERT INTO scalp_trades (symbol, side, entry_price, exit_price, amount, pnl, pnl_pct, exit_reason, duration_seconds, timestamp, is_paper)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (symbol, side, entry_price, exit_price, amount, pnl, pnl_pct, exit_reason, duration_seconds, datetime.now(), is_paper))

        conn.commit()
        conn.close()
        result = "+" if pnl >= 0 else ""
        logger.info(f"Saved scalp trade: {side} {symbol} | Entry: ${entry_price:,.2f} -> Exit: ${exit_price:,.2f} | P&L: {result}${pnl:.2f}")

    def get_scalp_trades(
        self,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> pd.DataFrame:
        """Get scalp trades with P&L info."""
        conn = sqlite3.connect(self.db_path)

        # Create table if not exists
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scalp_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                amount REAL NOT NULL,
                pnl REAL NOT NULL,
                pnl_pct REAL NOT NULL,
                exit_reason TEXT,
                duration_seconds REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_paper INTEGER DEFAULT 1
            )
        """)
        conn.commit()

        query = "SELECT * FROM scalp_trades WHERE 1=1"
        params = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

    def get_trades(
        self,
        symbol: Optional[str] = None,
        is_paper: Optional[bool] = None,
        limit: int = 100
    ) -> pd.DataFrame:
        """
        Retrieve trade history.

        Args:
            symbol: Filter by symbol (optional)
            is_paper: Filter by paper/live trades (optional)
            limit: Maximum records to return

        Returns:
            DataFrame with trade history
        """
        conn = sqlite3.connect(self.db_path)

        query = "SELECT * FROM trades WHERE 1=1"
        params = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        if is_paper is not None:
            query += " AND is_paper = ?"
            params.append(is_paper)

        query += f" ORDER BY timestamp DESC LIMIT {limit}"

        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        return df

    def save_model_performance(
        self,
        model_name: str,
        symbol: str,
        metrics: dict
    ):
        """
        Save model performance metrics.

        Args:
            model_name: Name of the ML model
            symbol: Trading pair
            metrics: Dictionary of performance metrics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO model_performance
            (model_name, symbol, accuracy, precision_score, recall, f1_score,
             profit_factor, sharpe_ratio, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            model_name,
            symbol,
            metrics.get("accuracy"),
            metrics.get("precision"),
            metrics.get("recall"),
            metrics.get("f1_score"),
            metrics.get("profit_factor"),
            metrics.get("sharpe_ratio"),
            datetime.now()
        ))

        conn.commit()
        conn.close()

    def save_candle_snapshot(
        self,
        symbol: str,
        timestamp_utc: datetime,
        timestamp_ny: str,
        ohlcv: dict,
        indicators: dict,
        prediction: str,
        confidence: float,
        signal_counts: dict,
        explanation: str
    ):
        """
        Save a 5-minute candle snapshot with all indicators and prediction.

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timestamp_utc: UTC timestamp of the candle
            timestamp_ny: New York time string
            ohlcv: Dict with open, high, low, close, volume
            indicators: Dict with all indicator values
            prediction: 'BUY', 'SELL', or 'HOLD'
            confidence: Prediction confidence (0-100)
            signal_counts: Dict with bullish_count, bearish_count, neutral_count
            explanation: JSON string with detailed explanation
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO candle_snapshots (
                    symbol, timestamp_utc, timestamp_ny,
                    open, high, low, close, volume,
                    rsi_14, rsi_7, stoch_k, stoch_d, cci, roc_10, momentum_10,
                    macd, macd_signal, macd_hist, adx, di_plus, di_minus,
                    ema_9, ema_21, ema_50, sma_20, sma_50,
                    atr_14, atr_pct, bb_upper, bb_middle, bb_lower, bb_width, bb_pct,
                    volume_ratio, obv, vwap,
                    prediction, confidence, bullish_count, bearish_count, neutral_count,
                    explanation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                timestamp_utc,
                timestamp_ny,
                ohlcv.get('open'),
                ohlcv.get('high'),
                ohlcv.get('low'),
                ohlcv.get('close'),
                ohlcv.get('volume'),
                indicators.get('rsi_14'),
                indicators.get('rsi_7'),
                indicators.get('stoch_k'),
                indicators.get('stoch_d'),
                indicators.get('cci'),
                indicators.get('roc_10'),
                indicators.get('momentum_10'),
                indicators.get('macd'),
                indicators.get('macd_signal'),
                indicators.get('macd_hist'),
                indicators.get('adx'),
                indicators.get('di_plus'),
                indicators.get('di_minus'),
                indicators.get('ema_9'),
                indicators.get('ema_21'),
                indicators.get('ema_50'),
                indicators.get('sma_20'),
                indicators.get('sma_50'),
                indicators.get('atr_14'),
                indicators.get('atr_pct'),
                indicators.get('bb_upper'),
                indicators.get('bb_middle'),
                indicators.get('bb_lower'),
                indicators.get('bb_width'),
                indicators.get('bb_pct'),
                indicators.get('volume_ratio'),
                indicators.get('obv'),
                indicators.get('vwap'),
                prediction,
                confidence,
                signal_counts.get('bullish', 0),
                signal_counts.get('bearish', 0),
                signal_counts.get('neutral', 0),
                explanation
            ))

            conn.commit()
            logger.debug(f"Saved candle snapshot for {symbol} at {timestamp_ny}")
        except Exception as e:
            logger.error(f"Error saving candle snapshot: {e}")
        finally:
            conn.close()

    def get_candle_snapshots(
        self,
        symbol: str,
        limit: int = 100,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Retrieve candle snapshots.

        Args:
            symbol: Trading pair
            limit: Maximum records to return
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            DataFrame with candle snapshots
        """
        conn = sqlite3.connect(self.db_path)

        query = """
            SELECT * FROM candle_snapshots
            WHERE symbol = ?
        """
        params = [symbol]

        if start_date:
            query += " AND timestamp_utc >= ?"
            params.append(start_date)

        if end_date:
            query += " AND timestamp_utc <= ?"
            params.append(end_date)

        query += f" ORDER BY timestamp_utc DESC LIMIT {limit}"

        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        return df

    def get_latest_snapshot(self, symbol: str) -> Optional[dict]:
        """
        Get the most recent candle snapshot for a symbol.

        Args:
            symbol: Trading pair

        Returns:
            Dictionary with snapshot data or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM candle_snapshots
            WHERE symbol = ?
            ORDER BY timestamp_utc DESC
            LIMIT 1
        """, (symbol,))

        row = cursor.fetchone()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        conn.close()

        if row:
            return dict(zip(columns, row))
        return None

    def get_unvalidated_predictions(self, symbol: str) -> List[dict]:
        """
        Get predictions that haven't been validated yet.

        Args:
            symbol: Trading pair

        Returns:
            List of unvalidated snapshot records
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, symbol, timestamp_utc, close, prediction
            FROM candle_snapshots
            WHERE symbol = ?
            AND prediction IS NOT NULL
            AND prediction_correct IS NULL
            ORDER BY timestamp_utc ASC
        """, (symbol,))

        rows = cursor.fetchall()
        columns = ['id', 'symbol', 'timestamp_utc', 'close', 'prediction']
        conn.close()

        return [dict(zip(columns, row)) for row in rows]

    def validate_prediction(
        self,
        snapshot_id: int,
        next_close: float,
        flat_threshold: float = 0.1
    ):
        """
        Validate a prediction by comparing with actual price movement.

        Args:
            snapshot_id: ID of the snapshot to validate
            next_close: Close price of the next candle
            flat_threshold: Percentage threshold for considering price as FLAT
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get the original snapshot
        cursor.execute("""
            SELECT close, prediction FROM candle_snapshots WHERE id = ?
        """, (snapshot_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return

        original_close, prediction = row

        # Calculate price change percentage
        price_change_pct = ((next_close - original_close) / original_close) * 100

        # Determine actual outcome
        if price_change_pct > flat_threshold:
            actual_outcome = "UP"
        elif price_change_pct < -flat_threshold:
            actual_outcome = "DOWN"
        else:
            actual_outcome = "FLAT"

        # Determine if prediction was correct
        prediction_correct = 0
        if prediction == "BUY" and actual_outcome == "UP":
            prediction_correct = 1
        elif prediction == "SELL" and actual_outcome == "DOWN":
            prediction_correct = 1
        elif prediction == "HOLD" and actual_outcome == "FLAT":
            prediction_correct = 1

        # Update the record
        cursor.execute("""
            UPDATE candle_snapshots
            SET actual_outcome = ?,
                price_change_pct = ?,
                next_close = ?,
                prediction_correct = ?,
                validated_at = ?
            WHERE id = ?
        """, (
            actual_outcome,
            round(price_change_pct, 4),
            next_close,
            prediction_correct,
            datetime.now(),
            snapshot_id
        ))

        conn.commit()
        conn.close()
        logger.debug(f"Validated prediction {snapshot_id}: {prediction} -> {actual_outcome} (correct: {prediction_correct})")

    def get_prediction_accuracy(self, symbol: str, days: int = 7) -> dict:
        """
        Get prediction accuracy statistics.

        Args:
            symbol: Trading pair
            days: Number of days to look back

        Returns:
            Dictionary with accuracy statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Overall accuracy
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN prediction_correct = 1 THEN 1 ELSE 0 END) as correct,
                AVG(CASE WHEN prediction_correct IS NOT NULL THEN prediction_correct ELSE NULL END) as accuracy
            FROM candle_snapshots
            WHERE symbol = ?
            AND prediction_correct IS NOT NULL
            AND timestamp_utc >= datetime('now', ?)
        """, (symbol, f'-{days} days'))
        overall = cursor.fetchone()

        # Accuracy by prediction type
        cursor.execute("""
            SELECT
                prediction,
                COUNT(*) as total,
                SUM(CASE WHEN prediction_correct = 1 THEN 1 ELSE 0 END) as correct,
                AVG(price_change_pct) as avg_price_change
            FROM candle_snapshots
            WHERE symbol = ?
            AND prediction_correct IS NOT NULL
            AND timestamp_utc >= datetime('now', ?)
            GROUP BY prediction
        """, (symbol, f'-{days} days'))
        by_type = cursor.fetchall()

        # Recent trend (last 24 hours)
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN prediction_correct = 1 THEN 1 ELSE 0 END) as correct
            FROM candle_snapshots
            WHERE symbol = ?
            AND prediction_correct IS NOT NULL
            AND timestamp_utc >= datetime('now', '-1 day')
        """, (symbol,))
        recent = cursor.fetchone()

        conn.close()

        return {
            'overall': {
                'total_predictions': overall[0] if overall else 0,
                'correct_predictions': overall[1] if overall else 0,
                'accuracy': round(overall[2] * 100, 2) if overall and overall[2] else 0
            },
            'by_prediction_type': {
                row[0]: {
                    'total': row[1],
                    'correct': row[2],
                    'accuracy': round(row[2] / row[1] * 100, 2) if row[1] > 0 else 0,
                    'avg_price_change': round(row[3], 4) if row[3] else 0
                } for row in by_type
            },
            'last_24h': {
                'total': recent[0] if recent else 0,
                'correct': recent[1] if recent else 0,
                'accuracy': round(recent[1] / recent[0] * 100, 2) if recent and recent[0] > 0 else 0
            },
            'period_days': days
        }

    # =====================================================
    # ICT (Inner Circle Trader) Indicators Methods
    # =====================================================

    def save_ict_indicators(
        self,
        symbol: str,
        timeframe: str,
        ict_data: dict
    ):
        """
        Save all ICT indicators data to database.

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Timeframe (e.g., '5m', '1h')
            ict_data: Dictionary containing all ICT indicator data
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        detected_at = datetime.now()

        try:
            # Save Fair Value Gaps
            for fvg in ict_data.get('fvg', []):
                cursor.execute("""
                    INSERT OR REPLACE INTO ict_fvg (
                        symbol, timeframe, detected_at, candle_timestamp, type,
                        top_price, bottom_price, gap_size, gap_pct, midpoint,
                        filled, filled_pct
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol, timeframe, detected_at, fvg.get('timestamp'),
                    fvg.get('type'), fvg.get('top'), fvg.get('bottom'),
                    fvg.get('gap_size'), fvg.get('gap_pct'), fvg.get('midpoint'),
                    fvg.get('filled', False), fvg.get('filled_pct', 0)
                ))

            # Save Market Structure Shifts
            for mss in ict_data.get('mss', []):
                cursor.execute("""
                    INSERT OR REPLACE INTO ict_mss (
                        symbol, timeframe, detected_at, trigger_timestamp, type,
                        broken_level, break_price, strength
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol, timeframe, detected_at, mss.get('timestamp'),
                    mss.get('type'), mss.get('broken_level'),
                    mss.get('break_price'), mss.get('strength')
                ))

            # Save Order Blocks
            for ob in ict_data.get('order_blocks', []):
                cursor.execute("""
                    INSERT OR REPLACE INTO ict_order_blocks (
                        symbol, timeframe, detected_at, candle_timestamp, type,
                        high_price, low_price, open_price, close_price, volume,
                        is_high_volume, displacement_size, tested, mitigated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol, timeframe, detected_at, ob.get('timestamp'),
                    ob.get('type'), ob.get('high'), ob.get('low'),
                    ob.get('open'), ob.get('close'), ob.get('volume'),
                    ob.get('is_high_volume'), ob.get('displacement_size'),
                    ob.get('tested', False), ob.get('mitigated', False)
                ))

            # Save Breaker Blocks
            for bb in ict_data.get('breaker_blocks', []):
                cursor.execute("""
                    INSERT OR REPLACE INTO ict_breaker_blocks (
                        symbol, timeframe, detected_at, candle_timestamp, type,
                        original_type, high_price, low_price
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol, timeframe, detected_at, bb.get('timestamp'),
                    bb.get('type'), bb.get('original_type'),
                    bb.get('high'), bb.get('low')
                ))

            # Save Liquidity Zones
            for lz in ict_data.get('liquidity_zones', []):
                cursor.execute("""
                    INSERT OR REPLACE INTO ict_liquidity_zones (
                        symbol, timeframe, detected_at, first_touch_timestamp, type,
                        level_price, touches, swept
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol, timeframe, detected_at, lz.get('timestamp'),
                    lz.get('type'), lz.get('level'),
                    lz.get('touches'), lz.get('swept', False)
                ))

            # Save Displacement
            for disp in ict_data.get('displacement', []):
                cursor.execute("""
                    INSERT OR REPLACE INTO ict_displacement (
                        symbol, timeframe, detected_at, candle_timestamp, type,
                        open_price, close_price, high_price, low_price,
                        body_size, body_atr_ratio, body_to_range_ratio,
                        is_high_volume, volume
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol, timeframe, detected_at, disp.get('timestamp'),
                    disp.get('type'), disp.get('open'), disp.get('close'),
                    disp.get('high'), disp.get('low'), disp.get('body_size'),
                    disp.get('body_atr_ratio'), disp.get('body_to_range_ratio'),
                    disp.get('is_high_volume'), disp.get('volume')
                ))

            # Save Swing Points
            for sp in ict_data.get('swing_points', []):
                cursor.execute("""
                    INSERT OR REPLACE INTO ict_swing_points (
                        symbol, timeframe, detected_at, candle_timestamp, type, price
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    symbol, timeframe, detected_at, sp.get('timestamp'),
                    sp.get('type'), sp.get('price')
                ))

            # Save OTE Levels
            ote = ict_data.get('ote_levels', {})
            if ote.get('bullish'):
                bullish_ote = ote['bullish']
                cursor.execute("""
                    INSERT INTO ict_ote_levels (
                        symbol, timeframe, detected_at, swing_high, swing_low,
                        range_size, equilibrium_50, ote_62, ote_705, ote_79,
                        target_1, target_2, target_final, current_zone
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol, timeframe, detected_at,
                    bullish_ote.get('swing_high'), bullish_ote.get('swing_low'),
                    bullish_ote.get('range'), bullish_ote['levels'].get('equilibrium_50'),
                    bullish_ote['levels'].get('ote_62'), bullish_ote['levels'].get('ote_705'),
                    bullish_ote['levels'].get('ote_79'), bullish_ote['targets'].get('target_1_neg27'),
                    bullish_ote['targets'].get('target_2_neg62'), bullish_ote['targets'].get('target_final'),
                    bullish_ote.get('zone')
                ))

            # Save Premium/Discount Zone
            pd_zone = ict_data.get('premium_discount')
            if pd_zone:
                cursor.execute("""
                    INSERT INTO ict_premium_discount (
                        symbol, timeframe, detected_at, range_high, range_low,
                        equilibrium, current_price, position_pct, zone, bias
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol, timeframe, detected_at, pd_zone.get('range_high'),
                    pd_zone.get('range_low'), pd_zone.get('equilibrium'),
                    pd_zone.get('current_price'), pd_zone.get('position_pct'),
                    pd_zone.get('zone'), pd_zone.get('bias')
                ))

            # Save Market Structure
            ms = ict_data.get('market_structure', {})
            if ms.get('trend'):
                cursor.execute("""
                    INSERT INTO ict_market_structure (
                        symbol, timeframe, detected_at, trend, structure,
                        hh_count, hl_count, lh_count, ll_count,
                        bullish_score, bearish_score, last_swing_high, last_swing_low
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol, timeframe, detected_at, ms.get('trend'),
                    ms.get('structure'), ms.get('hh_count', 0), ms.get('hl_count', 0),
                    ms.get('lh_count', 0), ms.get('ll_count', 0),
                    ms.get('bullish_score', 0), ms.get('bearish_score', 0),
                    ms.get('last_swing_high', {}).get('price') if ms.get('last_swing_high') else None,
                    ms.get('last_swing_low', {}).get('price') if ms.get('last_swing_low') else None
                ))

            conn.commit()
            logger.debug(f"Saved ICT indicators for {symbol} {timeframe}")
        except Exception as e:
            logger.error(f"Error saving ICT indicators: {e}")
            conn.rollback()
        finally:
            conn.close()

    def save_ict_trading_bias(
        self,
        symbol: str,
        timeframe: str,
        bias_data: dict,
        component_signals: dict = None
    ):
        """
        Save ICT trading bias for analysis and validation.

        Args:
            symbol: Trading pair
            timeframe: Timeframe
            bias_data: Dictionary with bias, confidence, scores
            component_signals: Optional breakdown of signals
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO ict_trading_bias (
                    symbol, timeframe, detected_at, bias, confidence,
                    bullish_score, bearish_score, fvg_signal, mss_signal,
                    ob_signal, zone_signal, structure_signal
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol, timeframe, datetime.now(),
                bias_data.get('bias'), bias_data.get('confidence'),
                bias_data.get('bullish_score', 0), bias_data.get('bearish_score', 0),
                component_signals.get('fvg') if component_signals else None,
                component_signals.get('mss') if component_signals else None,
                component_signals.get('ob') if component_signals else None,
                component_signals.get('zone') if component_signals else None,
                component_signals.get('structure') if component_signals else None
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving ICT trading bias: {e}")
        finally:
            conn.close()

    def get_ict_fvg(
        self,
        symbol: str,
        timeframe: str = '5m',
        limit: int = 50,
        unfilled_only: bool = False
    ) -> pd.DataFrame:
        """Get Fair Value Gaps from database."""
        conn = sqlite3.connect(self.db_path)

        query = """
            SELECT * FROM ict_fvg
            WHERE symbol = ? AND timeframe = ?
        """
        params = [symbol, timeframe]

        if unfilled_only:
            query += " AND filled = 0"

        query += f" ORDER BY detected_at DESC LIMIT {limit}"

        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

    def get_ict_order_blocks(
        self,
        symbol: str,
        timeframe: str = '5m',
        limit: int = 50,
        unmitigated_only: bool = False
    ) -> pd.DataFrame:
        """Get Order Blocks from database."""
        conn = sqlite3.connect(self.db_path)

        query = """
            SELECT * FROM ict_order_blocks
            WHERE symbol = ? AND timeframe = ?
        """
        params = [symbol, timeframe]

        if unmitigated_only:
            query += " AND mitigated = 0"

        query += f" ORDER BY detected_at DESC LIMIT {limit}"

        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

    def get_ict_mss(
        self,
        symbol: str,
        timeframe: str = '5m',
        limit: int = 20
    ) -> pd.DataFrame:
        """Get Market Structure Shifts from database."""
        conn = sqlite3.connect(self.db_path)

        query = """
            SELECT * FROM ict_mss
            WHERE symbol = ? AND timeframe = ?
            ORDER BY detected_at DESC LIMIT ?
        """

        df = pd.read_sql_query(query, conn, params=[symbol, timeframe, limit])
        conn.close()
        return df

    def get_ict_trading_bias_history(
        self,
        symbol: str,
        timeframe: str = '5m',
        days: int = 7
    ) -> pd.DataFrame:
        """Get ICT trading bias history."""
        conn = sqlite3.connect(self.db_path)

        query = """
            SELECT * FROM ict_trading_bias
            WHERE symbol = ? AND timeframe = ?
            AND detected_at >= datetime('now', ?)
            ORDER BY detected_at DESC
        """

        df = pd.read_sql_query(query, conn, params=[symbol, timeframe, f'-{days} days'])
        conn.close()
        return df

    def get_ict_market_structure_history(
        self,
        symbol: str,
        timeframe: str = '5m',
        limit: int = 100
    ) -> pd.DataFrame:
        """Get market structure analysis history."""
        conn = sqlite3.connect(self.db_path)

        query = """
            SELECT * FROM ict_market_structure
            WHERE symbol = ? AND timeframe = ?
            ORDER BY detected_at DESC LIMIT ?
        """

        df = pd.read_sql_query(query, conn, params=[symbol, timeframe, limit])
        conn.close()
        return df

    def get_ict_premium_discount_history(
        self,
        symbol: str,
        timeframe: str = '5m',
        limit: int = 100
    ) -> pd.DataFrame:
        """Get premium/discount zone history."""
        conn = sqlite3.connect(self.db_path)

        query = """
            SELECT * FROM ict_premium_discount
            WHERE symbol = ? AND timeframe = ?
            ORDER BY detected_at DESC LIMIT ?
        """

        df = pd.read_sql_query(query, conn, params=[symbol, timeframe, limit])
        conn.close()
        return df

    def get_ict_bias_accuracy(
        self,
        symbol: str,
        timeframe: str = '5m',
        days: int = 7
    ) -> dict:
        """
        Get ICT trading bias accuracy statistics.

        Returns accuracy of ICT-based predictions similar to prediction_accuracy.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Overall accuracy
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN prediction_correct = 1 THEN 1 ELSE 0 END) as correct,
                AVG(CASE WHEN prediction_correct IS NOT NULL THEN prediction_correct ELSE NULL END) as accuracy
            FROM ict_trading_bias
            WHERE symbol = ? AND timeframe = ?
            AND prediction_correct IS NOT NULL
            AND detected_at >= datetime('now', ?)
        """, (symbol, timeframe, f'-{days} days'))
        overall = cursor.fetchone()

        # Accuracy by bias type
        cursor.execute("""
            SELECT
                bias,
                COUNT(*) as total,
                SUM(CASE WHEN prediction_correct = 1 THEN 1 ELSE 0 END) as correct
            FROM ict_trading_bias
            WHERE symbol = ? AND timeframe = ?
            AND prediction_correct IS NOT NULL
            AND detected_at >= datetime('now', ?)
            GROUP BY bias
        """, (symbol, timeframe, f'-{days} days'))
        by_bias = cursor.fetchall()

        conn.close()

        return {
            'overall': {
                'total': overall[0] if overall else 0,
                'correct': overall[1] if overall else 0,
                'accuracy': round(overall[2] * 100, 2) if overall and overall[2] else 0
            },
            'by_bias': {
                row[0]: {
                    'total': row[1],
                    'correct': row[2],
                    'accuracy': round(row[2] / row[1] * 100, 2) if row[1] > 0 else 0
                } for row in by_bias
            },
            'period_days': days
        }

    # =====================================================
    # Position Persistence Methods
    # =====================================================

    def save_position(
        self,
        symbol: str,
        side: str,
        size: float,
        entry_price: float,
        entry_time: datetime,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_id: Optional[str] = None,
        stop_loss_order_id: Optional[str] = None,
        is_paper: bool = False
    ):
        """
        Save or update an open position for persistence across restarts.

        Args:
            symbol: Trading pair
            side: 'long' or 'short'
            size: Position size
            entry_price: Entry price
            entry_time: Entry timestamp
            stop_loss: Stop loss price
            take_profit: Take profit price
            order_id: Exchange order ID
            stop_loss_order_id: Stop loss order ID
            is_paper: Whether this is a paper trade
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO open_positions
            (symbol, side, size, entry_price, entry_time, stop_loss, take_profit,
             order_id, stop_loss_order_id, is_paper, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            symbol,
            side,
            size,
            entry_price,
            entry_time,
            stop_loss,
            take_profit,
            order_id,
            stop_loss_order_id,
            is_paper,
            datetime.now()
        ))

        conn.commit()
        conn.close()
        logger.debug(f"Saved position for {symbol}")

    def remove_position(self, symbol: str):
        """
        Remove a closed position from persistence.

        Args:
            symbol: Trading pair to remove
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM open_positions WHERE symbol = ?", (symbol,))

        conn.commit()
        conn.close()
        logger.debug(f"Removed position for {symbol}")

    def get_open_positions(self, is_paper: Optional[bool] = None) -> List[dict]:
        """
        Retrieve all open positions from database.

        Args:
            is_paper: Filter by paper/live positions (optional)

        Returns:
            List of position dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM open_positions WHERE 1=1"
        params = []

        if is_paper is not None:
            query += " AND is_paper = ?"
            params.append(is_paper)

        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        conn.close()

        positions = []
        for row in rows:
            position = dict(zip(columns, row))
            # Convert entry_time string back to datetime
            if position.get('entry_time'):
                position['entry_time'] = datetime.fromisoformat(str(position['entry_time']))
            positions.append(position)

        return positions

    def clear_all_positions(self, is_paper: Optional[bool] = None):
        """
        Clear all open positions (useful for resetting state).

        Args:
            is_paper: Only clear paper/live positions (optional, clears all if None)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if is_paper is not None:
            cursor.execute("DELETE FROM open_positions WHERE is_paper = ?", (is_paper,))
        else:
            cursor.execute("DELETE FROM open_positions")

        conn.commit()
        conn.close()
        logger.info("Cleared all open positions from database")
