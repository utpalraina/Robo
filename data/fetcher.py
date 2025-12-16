"""Data fetching module for historical and real-time market data."""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from loguru import logger
import asyncio
import time


class DataFetcher:
    """Fetch historical and real-time market data from exchanges."""

    def __init__(self, exchange: ccxt.Exchange):
        """
        Initialize DataFetcher.

        Args:
            exchange: Configured ccxt exchange instance
        """
        self.exchange = exchange
        self.exchange.load_markets()

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: Optional[datetime] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Fetch OHLCV (candlestick) data.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (1m, 5m, 15m, 1h, 4h, 1d)
            since: Start datetime (None for most recent)
            limit: Maximum number of candles to fetch

        Returns:
            DataFrame with OHLCV data
        """
        since_ts = None
        if since:
            since_ts = int(since.timestamp() * 1000)

        try:
            ohlcv = self.exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                since=since_ts,
                limit=limit
            )

            df = pd.DataFrame(
                ohlcv,
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            df["symbol"] = symbol

            logger.debug(f"Fetched {len(df)} candles for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            raise

    def fetch_ohlcv_binance(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: Optional[datetime] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from Binance (for deeper historical data).

        Binance has much more historical data than Kraken, so this is used
        as a fallback when Kraken runs out of historical candles.

        Args:
            symbol: Trading pair (e.g., "BTC/USD") - will be converted to USDT pair
            timeframe: Candle timeframe (1m, 2m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M)
            since: Start datetime (None for most recent)
            limit: Maximum number of candles to fetch

        Returns:
            DataFrame with OHLCV data
        """
        since_ts = None
        if since:
            since_ts = int(since.timestamp() * 1000)

        try:
            # Create Binance instance for historical data
            binance = ccxt.binance({'enableRateLimit': True})
            binance.load_markets()

            # Map symbol to Binance format
            binance_symbol = self._convert_symbol_for_binance(symbol)

            # Map timeframe to Binance format (Binance uses different names for some)
            binance_timeframe = self._convert_timeframe_for_binance(timeframe)

            if binance_symbol not in binance.markets:
                logger.warning(f"Symbol {binance_symbol} not found on Binance, cannot fetch historical data")
                return pd.DataFrame()

            logger.info(f"Fetching historical data from Binance: {binance_symbol} (timeframe={binance_timeframe}, since={since})")

            ohlcv = binance.fetch_ohlcv(
                binance_symbol,
                timeframe=binance_timeframe,
                since=since_ts,
                limit=limit
            )

            if not ohlcv:
                return pd.DataFrame()

            df = pd.DataFrame(
                ohlcv,
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            df["symbol"] = symbol  # Keep original symbol (e.g., BTC/USD)

            logger.info(f"Fetched {len(df)} candles from Binance for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching OHLCV from Binance for {symbol}: {e}")
            return pd.DataFrame()

    def _convert_symbol_for_binance(self, symbol: str) -> str:
        """Convert symbol to Binance format."""
        # Map USD pairs to USDT for Binance
        if symbol.endswith('/USD'):
            return symbol.replace('/USD', '/USDT')
        # Map EUR pairs to USDT (Binance has limited EUR pairs)
        if symbol.endswith('/EUR'):
            return symbol.replace('/EUR', '/USDT')
        # BTC pairs stay the same
        return symbol

    def _convert_timeframe_for_binance(self, timeframe: str) -> str:
        """Convert timeframe to Binance format."""
        # Binance timeframe mappings
        tf_map = {
            '1m': '1m',
            '2m': '1m',  # Binance doesn't have 2m, use 1m and aggregate if needed
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '1h': '1h',
            '4h': '4h',
            '1d': '1d',
            '1w': '1w',
            '1M': '1M',
            '1y': '1M',  # Binance doesn't have 1y, use 1M
        }
        return tf_map.get(timeframe, '1h')

    def fetch_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Fetch historical data over a date range.

        Uses Binance for historical data (supports full history) while
        the main exchange (e.g., Kraken) is used for live trading.

        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with all historical data
        """
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        all_data = []
        current = start

        # Map timeframe to timedelta
        tf_map = {
            "1m": timedelta(minutes=1),
            "2m": timedelta(minutes=2),
            "5m": timedelta(minutes=5),
            "15m": timedelta(minutes=15),
            "30m": timedelta(minutes=30),
            "1h": timedelta(hours=1),
            "4h": timedelta(hours=4),
            "1d": timedelta(days=1),
            "1w": timedelta(weeks=1),
            "1M": timedelta(days=30),
            "1y": timedelta(days=365),
        }

        tf_delta = tf_map.get(timeframe, timedelta(hours=1))
        batch_size = 1000

        logger.info(f"Fetching historical data for {symbol} from {start_date} to {end_date}")

        # Use Binance for historical data (Kraken doesn't support historical OHLCV)
        binance = ccxt.binance({'enableRateLimit': True})
        binance.load_markets()

        # Convert symbol and timeframe for Binance
        binance_symbol = self._convert_symbol_for_binance(symbol)
        binance_timeframe = self._convert_timeframe_for_binance(timeframe)

        if binance_symbol not in binance.markets:
            logger.error(f"Symbol {binance_symbol} not found on Binance")
            raise ValueError(f"Symbol '{binance_symbol}' not available on Binance for historical data")

        logger.info(f"Using Binance for historical data: {binance_symbol} (timeframe={binance_timeframe})")

        while current < end:
            since_ts = int(current.timestamp() * 1000)

            try:
                ohlcv = binance.fetch_ohlcv(
                    binance_symbol,
                    timeframe=binance_timeframe,
                    since=since_ts,
                    limit=batch_size
                )

                if not ohlcv:
                    break

                df = pd.DataFrame(
                    ohlcv,
                    columns=["timestamp", "open", "high", "low", "close", "volume"]
                )
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df.set_index("timestamp", inplace=True)
                df["symbol"] = symbol  # Use original symbol (e.g., BTC/USD)

                all_data.append(df)
                current = df.index[-1].to_pydatetime() + tf_delta

                # Respect rate limits
                time.sleep(binance.rateLimit / 1000)

            except Exception as e:
                logger.error(f"Error fetching from Binance: {e}")
                break

        if not all_data:
            logger.warning(f"No data returned for {symbol} in range {start_date} to {end_date}")
            return pd.DataFrame()

        result = pd.concat(all_data)
        result = result[~result.index.duplicated(keep="first")]
        result = result[result.index <= pd.Timestamp(end)]

        logger.info(f"Fetched {len(result)} total candles for {symbol} from Binance")
        return result

    def fetch_ticker(self, symbol: str) -> Dict:
        """
        Fetch current ticker data.

        Args:
            symbol: Trading pair

        Returns:
            Ticker dictionary with bid, ask, last price, etc.
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                "symbol": symbol,
                "bid": ticker["bid"],
                "ask": ticker["ask"],
                "last": ticker["last"],
                "high": ticker.get("high"),      # 24h high
                "low": ticker.get("low"),        # 24h low
                "change": ticker.get("percentage"),  # 24h change %
                "volume": ticker["baseVolume"],
                "timestamp": datetime.now()
            }
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
            raise

    def fetch_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """
        Fetch order book data.

        Args:
            symbol: Trading pair
            limit: Depth of order book

        Returns:
            Dictionary with bids and asks
        """
        try:
            order_book = self.exchange.fetch_order_book(symbol, limit)
            return {
                "symbol": symbol,
                "bids": order_book["bids"][:limit],
                "asks": order_book["asks"][:limit],
                "timestamp": datetime.now()
            }
        except Exception as e:
            logger.error(f"Error fetching order book for {symbol}: {e}")
            raise

    def fetch_market_trades(self, symbol: str, limit: int = 500) -> List[Dict]:
        """
        Fetch recent market trades (trade tape) from the exchange.

        Args:
            symbol: Trading pair (e.g., BTC/USD)
            limit: Number of recent trades to fetch

        Returns:
            List of trade dictionaries with price, amount, side, timestamp
        """
        try:
            trades = self.exchange.fetch_trades(symbol, limit=limit)
            return [
                {
                    "id": trade.get("id"),
                    "timestamp": trade.get("timestamp"),
                    "datetime": trade.get("datetime"),
                    "symbol": trade.get("symbol"),
                    "side": trade.get("side"),  # 'buy' or 'sell' (taker side)
                    "price": trade.get("price"),
                    "amount": trade.get("amount"),
                    "cost": trade.get("cost"),  # price * amount
                }
                for trade in trades
            ]
        except Exception as e:
            logger.error(f"Error fetching market trades for {symbol}: {e}")
            raise

    def fetch_multiple_symbols(
        self,
        symbols: List[str],
        timeframe: str,
        limit: int = 100
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch OHLCV data for multiple symbols.

        Args:
            symbols: List of trading pairs
            timeframe: Candle timeframe
            limit: Number of candles per symbol

        Returns:
            Dictionary mapping symbols to their OHLCV DataFrames
        """
        data = {}
        for symbol in symbols:
            try:
                data[symbol] = self.fetch_ohlcv(symbol, timeframe, limit=limit)
                time.sleep(self.exchange.rateLimit / 1000)
            except Exception as e:
                logger.warning(f"Failed to fetch {symbol}: {e}")

        return data
