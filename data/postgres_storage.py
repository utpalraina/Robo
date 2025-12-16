"""PostgreSQL storage for custom indicators."""

import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from loguru import logger
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from contextlib import contextmanager


class PostgresStorage:
    """PostgreSQL storage for custom Pine Script indicators."""

    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize PostgreSQL storage.

        Args:
            connection_string: PostgreSQL connection string.
                             Defaults to DATABASE_URL env var or localhost.
        """
        self.connection_string = connection_string or os.getenv(
            'DATABASE_URL',
            'postgresql://localhost:5432/robo_trader'
        )
        self._init_db()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = psycopg2.connect(self.connection_string)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _init_db(self):
        """Initialize database tables for custom indicators."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Custom indicators table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS custom_indicators (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    short_name VARCHAR(20) NOT NULL,
                    description TEXT,
                    category VARCHAR(50) DEFAULT 'custom',
                    pine_script TEXT NOT NULL,
                    compiled_ast JSONB,
                    is_overlay BOOLEAN DEFAULT TRUE,
                    is_enabled BOOLEAN DEFAULT TRUE,
                    default_settings JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name)
                )
            """)

            # Indicator user settings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS indicator_settings (
                    id SERIAL PRIMARY KEY,
                    indicator_id INTEGER REFERENCES custom_indicators(id) ON DELETE CASCADE,
                    chart_id VARCHAR(50),
                    settings JSONB NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    display_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(indicator_id, chart_id)
                )
            """)

            # Pine Script templates
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pine_templates (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    category VARCHAR(50) NOT NULL,
                    description TEXT,
                    pine_script TEXT NOT NULL,
                    difficulty VARCHAR(20) DEFAULT 'beginner',
                    is_featured BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indicator calculation cache
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS indicator_cache (
                    id SERIAL PRIMARY KEY,
                    indicator_id INTEGER REFERENCES custom_indicators(id) ON DELETE CASCADE,
                    symbol VARCHAR(20) NOT NULL,
                    timeframe VARCHAR(10) NOT NULL,
                    cache_key VARCHAR(100) NOT NULL,
                    calculated_data JSONB NOT NULL,
                    last_candle_time TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(indicator_id, symbol, timeframe, cache_key)
                )
            """)

            # Custom Python indicators table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS custom_python_indicators (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    short_name VARCHAR(20) NOT NULL,
                    description TEXT,
                    python_code TEXT NOT NULL,
                    is_overlay BOOLEAN DEFAULT TRUE,
                    is_enabled BOOLEAN DEFAULT TRUE,
                    default_settings JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name)
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_indicators_enabled
                ON custom_indicators(is_enabled) WHERE is_enabled = TRUE
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_settings_indicator
                ON indicator_settings(indicator_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_templates_category
                ON pine_templates(category)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_lookup
                ON indicator_cache(indicator_id, symbol, timeframe)
            """)

            logger.info("PostgreSQL custom indicators tables initialized")

    # =====================================================
    # Custom Indicators CRUD
    # =====================================================

    def create_indicator(
        self,
        name: str,
        short_name: str,
        pine_script: str,
        description: Optional[str] = None,
        category: str = 'custom',
        is_overlay: bool = True,
        default_settings: Optional[Dict] = None,
        compiled_ast: Optional[Dict] = None
    ) -> int:
        """
        Create a new custom indicator.

        Returns:
            The ID of the created indicator.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO custom_indicators
                (name, short_name, description, category, pine_script,
                 compiled_ast, is_overlay, default_settings)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                name, short_name, description, category, pine_script,
                Json(compiled_ast) if compiled_ast else None,
                is_overlay,
                Json(default_settings or {})
            ))
            indicator_id = cursor.fetchone()[0]
            logger.info(f"Created custom indicator: {name} (ID: {indicator_id})")
            return indicator_id

    def get_indicator(self, indicator_id: int) -> Optional[Dict]:
        """Get a custom indicator by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT * FROM custom_indicators WHERE id = %s
            """, (indicator_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_indicator_by_name(self, name: str) -> Optional[Dict]:
        """Get a custom indicator by name."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT * FROM custom_indicators WHERE name = %s
            """, (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_indicators(
        self,
        enabled_only: bool = False,
        category: Optional[str] = None
    ) -> List[Dict]:
        """List all custom indicators."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = "SELECT * FROM custom_indicators WHERE 1=1"
            params = []

            if enabled_only:
                query += " AND is_enabled = TRUE"
            if category:
                query += " AND category = %s"
                params.append(category)

            query += " ORDER BY name"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def update_indicator(
        self,
        indicator_id: int,
        **kwargs
    ) -> bool:
        """
        Update a custom indicator.

        Args:
            indicator_id: ID of the indicator to update
            **kwargs: Fields to update (name, short_name, description,
                     category, pine_script, compiled_ast, is_overlay,
                     is_enabled, default_settings)
        """
        allowed_fields = {
            'name', 'short_name', 'description', 'category', 'pine_script',
            'compiled_ast', 'is_overlay', 'is_enabled', 'default_settings'
        }

        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False

        # Handle JSON fields
        if 'compiled_ast' in updates:
            updates['compiled_ast'] = Json(updates['compiled_ast'])
        if 'default_settings' in updates:
            updates['default_settings'] = Json(updates['default_settings'])

        updates['updated_at'] = datetime.now()

        set_clause = ', '.join(f"{k} = %s" for k in updates.keys())
        values = list(updates.values()) + [indicator_id]

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE custom_indicators
                SET {set_clause}
                WHERE id = %s
            """, values)

            # Invalidate cache for this indicator
            cursor.execute("""
                DELETE FROM indicator_cache WHERE indicator_id = %s
            """, (indicator_id,))

            return cursor.rowcount > 0

    def delete_indicator(self, indicator_id: int) -> bool:
        """Delete a custom indicator."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM custom_indicators WHERE id = %s
            """, (indicator_id,))
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted custom indicator ID: {indicator_id}")
            return deleted

    # =====================================================
    # Indicator Settings
    # =====================================================

    def save_indicator_settings(
        self,
        indicator_id: int,
        settings: Dict,
        chart_id: str = 'default',
        is_active: bool = True
    ):
        """Save or update indicator settings for a chart."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO indicator_settings
                (indicator_id, chart_id, settings, is_active, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (indicator_id, chart_id)
                DO UPDATE SET
                    settings = EXCLUDED.settings,
                    is_active = EXCLUDED.is_active,
                    updated_at = EXCLUDED.updated_at
            """, (indicator_id, chart_id, Json(settings), is_active, datetime.now()))

    def get_indicator_settings(
        self,
        indicator_id: int,
        chart_id: str = 'default'
    ) -> Optional[Dict]:
        """Get indicator settings for a chart."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT * FROM indicator_settings
                WHERE indicator_id = %s AND chart_id = %s
            """, (indicator_id, chart_id))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_active_indicators(self, chart_id: str = 'default') -> List[Dict]:
        """Get all active indicators for a chart with their settings."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT ci.*, ics.settings as user_settings, ics.is_active
                FROM custom_indicators ci
                JOIN indicator_settings ics ON ci.id = ics.indicator_id
                WHERE ics.chart_id = %s AND ics.is_active = TRUE AND ci.is_enabled = TRUE
                ORDER BY ics.display_order
            """, (chart_id,))
            return [dict(row) for row in cursor.fetchall()]

    # =====================================================
    # Pine Script Templates
    # =====================================================

    def create_template(
        self,
        name: str,
        category: str,
        pine_script: str,
        description: Optional[str] = None,
        difficulty: str = 'beginner',
        is_featured: bool = False
    ) -> int:
        """Create a Pine Script template."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO pine_templates
                (name, category, description, pine_script, difficulty, is_featured)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (name, category, description, pine_script, difficulty, is_featured))
            return cursor.fetchone()[0]

    def get_templates(
        self,
        category: Optional[str] = None,
        featured_only: bool = False
    ) -> List[Dict]:
        """Get Pine Script templates."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = "SELECT * FROM pine_templates WHERE 1=1"
            params = []

            if category:
                query += " AND category = %s"
                params.append(category)
            if featured_only:
                query += " AND is_featured = TRUE"

            query += " ORDER BY category, name"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_template(self, template_id: int) -> Optional[Dict]:
        """Get a specific template."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM pine_templates WHERE id = %s", (template_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # =====================================================
    # Indicator Cache
    # =====================================================

    def get_cached_calculation(
        self,
        indicator_id: int,
        symbol: str,
        timeframe: str,
        cache_key: str
    ) -> Optional[Dict]:
        """Get cached indicator calculation if valid."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT calculated_data, last_candle_time FROM indicator_cache
                WHERE indicator_id = %s AND symbol = %s AND timeframe = %s
                AND cache_key = %s AND expires_at > NOW()
            """, (indicator_id, symbol, timeframe, cache_key))
            row = cursor.fetchone()
            if row:
                return {
                    'data': row['calculated_data'],
                    'last_candle_time': row['last_candle_time']
                }
            return None

    def save_cached_calculation(
        self,
        indicator_id: int,
        symbol: str,
        timeframe: str,
        cache_key: str,
        data: Dict,
        last_candle_time: datetime,
        ttl_seconds: int = 300
    ):
        """Save indicator calculation to cache."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO indicator_cache
                (indicator_id, symbol, timeframe, cache_key, calculated_data,
                 last_candle_time, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW() + INTERVAL '%s seconds')
                ON CONFLICT (indicator_id, symbol, timeframe, cache_key)
                DO UPDATE SET
                    calculated_data = EXCLUDED.calculated_data,
                    last_candle_time = EXCLUDED.last_candle_time,
                    expires_at = EXCLUDED.expires_at
            """, (indicator_id, symbol, timeframe, cache_key, Json(data),
                  last_candle_time, ttl_seconds))

    def invalidate_cache(
        self,
        indicator_id: Optional[int] = None,
        symbol: Optional[str] = None
    ):
        """Invalidate indicator cache."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if indicator_id and symbol:
                cursor.execute("""
                    DELETE FROM indicator_cache
                    WHERE indicator_id = %s AND symbol = %s
                """, (indicator_id, symbol))
            elif indicator_id:
                cursor.execute("""
                    DELETE FROM indicator_cache WHERE indicator_id = %s
                """, (indicator_id,))
            elif symbol:
                cursor.execute("""
                    DELETE FROM indicator_cache WHERE symbol = %s
                """, (symbol,))
            else:
                cursor.execute("DELETE FROM indicator_cache")

    # =====================================================
    # Custom Python Indicators CRUD
    # =====================================================

    def create_python_indicator(
        self,
        name: str,
        short_name: str,
        python_code: str,
        description: Optional[str] = None,
        is_overlay: bool = True,
        default_settings: Optional[Dict] = None
    ) -> int:
        """Create a new custom Python indicator."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO custom_python_indicators
                (name, short_name, description, python_code, is_overlay, default_settings)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                name, short_name, description, python_code,
                is_overlay, Json(default_settings or {})
            ))
            indicator_id = cursor.fetchone()[0]
            logger.info(f"Created custom Python indicator: {name} (ID: {indicator_id})")
            return indicator_id

    def get_python_indicator(self, indicator_id: int) -> Optional[Dict]:
        """Get a custom Python indicator by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT * FROM custom_python_indicators WHERE id = %s
            """, (indicator_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_python_indicators(self, enabled_only: bool = False) -> List[Dict]:
        """List all custom Python indicators."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            query = "SELECT * FROM custom_python_indicators WHERE 1=1"
            if enabled_only:
                query += " AND is_enabled = TRUE"
            query += " ORDER BY name"
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]

    def update_python_indicator(self, indicator_id: int, **kwargs) -> bool:
        """Update a custom Python indicator."""
        allowed_fields = {
            'name', 'short_name', 'description', 'python_code',
            'is_overlay', 'is_enabled', 'default_settings'
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False

        if 'default_settings' in updates:
            updates['default_settings'] = Json(updates['default_settings'])
        updates['updated_at'] = datetime.now()

        set_clause = ', '.join(f"{k} = %s" for k in updates.keys())
        values = list(updates.values()) + [indicator_id]

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE custom_python_indicators
                SET {set_clause}
                WHERE id = %s
            """, values)
            return cursor.rowcount > 0

    def delete_python_indicator(self, indicator_id: int) -> bool:
        """Delete a custom Python indicator."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM custom_python_indicators WHERE id = %s
            """, (indicator_id,))
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted custom Python indicator ID: {indicator_id}")
            return deleted

    # =====================================================
    # Utility Methods
    # =====================================================

    def seed_default_templates(self):
        """Seed default Pine Script templates."""
        templates = [
            {
                'name': 'Simple Moving Average',
                'category': 'trend',
                'difficulty': 'beginner',
                'description': 'Basic SMA indicator with customizable period',
                'pine_script': '''//@version=5
indicator("Simple Moving Average", overlay=true)
length = input.int(20, "Length", minval=1)
src = input.source(close, "Source")
smaValue = ta.sma(src, length)
plot(smaValue, "SMA", color=color.blue, linewidth=2)'''
            },
            {
                'name': 'RSI',
                'category': 'momentum',
                'difficulty': 'beginner',
                'description': 'Relative Strength Index with overbought/oversold levels',
                'pine_script': '''//@version=5
indicator("RSI", overlay=false)
length = input.int(14, "Length", minval=1)
src = input.source(close, "Source")
rsiValue = ta.rsi(src, length)
plot(rsiValue, "RSI", color=color.purple, linewidth=2)
hline(70, "Overbought", color=color.red)
hline(30, "Oversold", color=color.green)
hline(50, "Middle", color=color.gray)'''
            },
            {
                'name': 'MACD',
                'category': 'momentum',
                'difficulty': 'intermediate',
                'description': 'Moving Average Convergence Divergence',
                'pine_script': '''//@version=5
indicator("MACD", overlay=false)
fast = input.int(12, "Fast Length")
slow = input.int(26, "Slow Length")
signal_length = input.int(9, "Signal Length")
[macdLine, signalLine, histLine] = ta.macd(close, fast, slow, signal_length)
plot(macdLine, "MACD", color=color.blue)
plot(signalLine, "Signal", color=color.orange)
plot(histLine, "Histogram", color=histLine >= 0 ? color.green : color.red, style=plot.style_histogram)'''
            },
            {
                'name': 'Bollinger Bands',
                'category': 'volatility',
                'difficulty': 'beginner',
                'description': 'Bollinger Bands with customizable period and deviation',
                'pine_script': '''//@version=5
indicator("Bollinger Bands", overlay=true)
length = input.int(20, "Length")
mult = input.float(2.0, "Multiplier")
[middle, upper, lower] = ta.bb(close, length, mult)
plot(middle, "Middle", color=color.blue)
plot(upper, "Upper", color=color.red)
plot(lower, "Lower", color=color.green)
fill(plot(upper), plot(lower), color=color.new(color.blue, 90))'''
            },
            {
                'name': 'EMA Crossover',
                'category': 'trend',
                'difficulty': 'intermediate',
                'description': 'EMA crossover signals with two moving averages',
                'pine_script': '''//@version=5
indicator("EMA Crossover", overlay=true)
fast_length = input.int(9, "Fast EMA")
slow_length = input.int(21, "Slow EMA")
fast_ema = ta.ema(close, fast_length)
slow_ema = ta.ema(close, slow_length)
plot(fast_ema, "Fast EMA", color=color.blue, linewidth=2)
plot(slow_ema, "Slow EMA", color=color.red, linewidth=2)
bullish = ta.crossover(fast_ema, slow_ema)
bearish = ta.crossunder(fast_ema, slow_ema)
plotshape(bullish, "Buy", shape.triangleup, location.belowbar, color.green, size=size.small)
plotshape(bearish, "Sell", shape.triangledown, location.abovebar, color.red, size=size.small)'''
            },
            {
                'name': 'ATR',
                'category': 'volatility',
                'difficulty': 'beginner',
                'description': 'Average True Range volatility indicator',
                'pine_script': '''//@version=5
indicator("ATR", overlay=false)
length = input.int(14, "Length")
atrValue = ta.atr(length)
plot(atrValue, "ATR", color=color.orange, linewidth=2)'''
            },
            {
                'name': 'Stochastic RSI',
                'category': 'momentum',
                'difficulty': 'intermediate',
                'description': 'Stochastic RSI oscillator',
                'pine_script': '''//@version=5
indicator("Stochastic RSI", overlay=false)
rsi_length = input.int(14, "RSI Length")
stoch_length = input.int(14, "Stochastic Length")
k_smooth = input.int(3, "K Smoothing")
d_smooth = input.int(3, "D Smoothing")
rsi = ta.rsi(close, rsi_length)
k = ta.sma(ta.stoch(rsi, rsi, rsi, stoch_length), k_smooth)
d = ta.sma(k, d_smooth)
plot(k, "K", color=color.blue)
plot(d, "D", color=color.orange)
hline(80, "Overbought")
hline(20, "Oversold")'''
            },
            {
                'name': 'Volume Profile',
                'category': 'volume',
                'difficulty': 'beginner',
                'description': 'Volume with moving average',
                'pine_script': '''//@version=5
indicator("Volume Profile", overlay=false)
length = input.int(20, "MA Length")
vol_ma = ta.sma(volume, length)
plot(volume, "Volume", color=close > open ? color.green : color.red, style=plot.style_histogram)
plot(vol_ma, "Volume MA", color=color.orange, linewidth=2)'''
            }
        ]

        for template in templates:
            try:
                self.create_template(**template)
                logger.debug(f"Created template: {template['name']}")
            except Exception as e:
                # Template might already exist
                if 'duplicate key' not in str(e).lower():
                    logger.warning(f"Error creating template {template['name']}: {e}")
