"""
Kraken WebSocket Client for Real-Time Market Data

Connects directly to Kraken's WebSocket API for sub-100ms tick updates.
This provides much faster price updates compared to REST API polling.

Kraken WebSocket API: wss://ws.kraken.com
Documentation: https://docs.kraken.com/websockets/
"""

import asyncio
import json
import time
from typing import Callable, Optional, Dict, Any
from datetime import datetime
import websockets
from loguru import logger


class KrakenWebSocket:
    """
    Real-time WebSocket client for Kraken exchange.

    Subscribes to ticker channel for instant price updates.
    Much faster than REST API polling (50-100ms vs 1000ms+).
    """

    WS_URL = "wss://ws.kraken.com"

    # Kraken uses different symbol format in WebSocket
    # REST: BTC/USDT -> WebSocket: XBT/USDT
    SYMBOL_MAP = {
        "BTC/USDT": "XBT/USDT",
        "BTC/USD": "XBT/USD",
        "BTC/EUR": "XBT/EUR",
        "ETH/USDT": "ETH/USDT",
        "ETH/USD": "ETH/USD",
        "ETH/BTC": "ETH/XBT",
    }

    def __init__(self, on_ticker: Optional[Callable] = None):
        """
        Initialize Kraken WebSocket client.

        Args:
            on_ticker: Callback function called on each tick update.
                      Signature: on_ticker(symbol, price, bid, ask, volume, timestamp)
        """
        self.on_ticker = on_ticker
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.subscribed_symbols: set = set()
        self.running = False
        self.reconnect_delay = 1  # seconds
        self.max_reconnect_delay = 60
        self.last_tick: Dict[str, Dict[str, Any]] = {}

    def _convert_symbol(self, symbol: str) -> str:
        """Convert standard symbol to Kraken WebSocket format."""
        return self.SYMBOL_MAP.get(symbol, symbol)

    def _reverse_symbol(self, ws_symbol: str) -> str:
        """Convert Kraken WebSocket symbol back to standard format."""
        reverse_map = {v: k for k, v in self.SYMBOL_MAP.items()}
        return reverse_map.get(ws_symbol, ws_symbol)

    async def connect(self):
        """Establish WebSocket connection to Kraken."""
        try:
            self.ws = await websockets.connect(
                self.WS_URL,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5
            )
            self.running = True
            self.reconnect_delay = 1  # Reset on successful connect
            logger.info(f"Connected to Kraken WebSocket: {self.WS_URL}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Kraken WebSocket: {e}")
            return False

    async def subscribe_ticker(self, symbols: list):
        """
        Subscribe to ticker updates for given symbols.

        Args:
            symbols: List of symbols like ["BTC/USDT", "ETH/USDT"]
        """
        if not self.ws:
            logger.error("WebSocket not connected")
            return False

        # Convert symbols to Kraken format
        ws_symbols = [self._convert_symbol(s) for s in symbols]

        subscribe_msg = {
            "event": "subscribe",
            "pair": ws_symbols,
            "subscription": {
                "name": "ticker"
            }
        }

        try:
            await self.ws.send(json.dumps(subscribe_msg))
            self.subscribed_symbols.update(symbols)
            logger.info(f"Subscribed to ticker for: {symbols}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")
            return False

    async def subscribe_trades(self, symbols: list):
        """
        Subscribe to trade updates (individual trades, most granular).

        Args:
            symbols: List of symbols like ["BTC/USDT"]
        """
        if not self.ws:
            return False

        ws_symbols = [self._convert_symbol(s) for s in symbols]

        subscribe_msg = {
            "event": "subscribe",
            "pair": ws_symbols,
            "subscription": {
                "name": "trade"
            }
        }

        try:
            await self.ws.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to trades for: {symbols}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to trades: {e}")
            return False

    def _parse_ticker_message(self, data: list) -> Optional[Dict]:
        """
        Parse Kraken ticker message format.

        Ticker format: [channelID, tickerData, "ticker", "XBT/USDT"]
        tickerData contains: a (ask), b (bid), c (close/last), v (volume), etc.
        """
        if len(data) < 4:
            return None

        try:
            ticker_data = data[1]
            ws_symbol = data[3]
            symbol = self._reverse_symbol(ws_symbol)

            # Extract price data
            # c = close [price, lot volume]
            # b = bid [price, whole lot volume, lot volume]
            # a = ask [price, whole lot volume, lot volume]
            # v = volume [today, last 24h]
            # h = high [today, last 24h]
            # l = low [today, last 24h]
            # o = open [today, last 24h]

            last_price = float(ticker_data['c'][0])  # Close/last price
            bid = float(ticker_data['b'][0])
            ask = float(ticker_data['a'][0])
            volume_24h = float(ticker_data['v'][1])
            high_24h = float(ticker_data['h'][1])
            low_24h = float(ticker_data['l'][1])
            open_24h = float(ticker_data['o'][1]) if 'o' in ticker_data else None

            # Calculate 24h change percentage
            change_24h = 0
            if open_24h and open_24h > 0:
                change_24h = ((last_price - open_24h) / open_24h) * 100

            # Use current time as Kraken ticker doesn't include timestamp
            timestamp = int(time.time() * 1000)

            return {
                'symbol': symbol,
                'price': last_price,
                'bid': bid,
                'ask': ask,
                'volume': volume_24h,
                'high': high_24h,
                'low': low_24h,
                'change': change_24h,
                'timestamp': timestamp,
                'exchange_ts': timestamp
            }
        except (KeyError, IndexError, ValueError) as e:
            logger.debug(f"Failed to parse ticker: {e}")
            return None

    def _parse_trade_message(self, data: list) -> Optional[Dict]:
        """
        Parse Kraken trade message format.

        Trade format: [channelID, [[price, volume, time, side, orderType, misc], ...], "trade", "XBT/USDT"]
        """
        if len(data) < 4:
            return None

        try:
            trades = data[1]
            ws_symbol = data[3]
            symbol = self._reverse_symbol(ws_symbol)

            # Get the most recent trade
            if trades and len(trades) > 0:
                latest_trade = trades[-1]
                price = float(latest_trade[0])
                volume = float(latest_trade[1])
                trade_time = float(latest_trade[2])  # Unix timestamp with decimals
                side = latest_trade[3]  # 'b' for buy, 's' for sell

                return {
                    'symbol': symbol,
                    'price': price,
                    'volume': volume,
                    'side': 'buy' if side == 'b' else 'sell',
                    'timestamp': int(trade_time * 1000),
                    'exchange_ts': int(trade_time * 1000)
                }
        except (KeyError, IndexError, ValueError) as e:
            logger.debug(f"Failed to parse trade: {e}")
            return None

    async def _handle_message(self, message: str):
        """Process incoming WebSocket message."""
        try:
            data = json.loads(message)

            # Handle system events
            if isinstance(data, dict):
                event = data.get('event')
                if event == 'systemStatus':
                    logger.info(f"Kraken system status: {data.get('status')}")
                elif event == 'subscriptionStatus':
                    status = data.get('status')
                    pair = data.get('pair')
                    if status == 'subscribed':
                        logger.info(f"Successfully subscribed to {pair}")
                    elif status == 'error':
                        logger.error(f"Subscription error for {pair}: {data.get('errorMessage')}")
                elif event == 'heartbeat':
                    pass  # Ignore heartbeats
                return

            # Handle data messages (arrays)
            if isinstance(data, list) and len(data) >= 4:
                channel_name = data[-2] if len(data) >= 3 else None

                if channel_name == 'ticker':
                    ticker = self._parse_ticker_message(data)
                    if ticker and self.on_ticker:
                        self.last_tick[ticker['symbol']] = ticker
                        await self.on_ticker(ticker)

                elif channel_name == 'trade':
                    trade = self._parse_trade_message(data)
                    if trade and self.on_ticker:
                        # Update last tick with trade price
                        symbol = trade['symbol']
                        if symbol in self.last_tick:
                            self.last_tick[symbol]['price'] = trade['price']
                            self.last_tick[symbol]['timestamp'] = trade['timestamp']
                            self.last_tick[symbol]['exchange_ts'] = trade['exchange_ts']
                        else:
                            self.last_tick[symbol] = trade
                        await self.on_ticker(self.last_tick[symbol])

        except json.JSONDecodeError as e:
            logger.debug(f"Failed to decode message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def listen(self):
        """Main loop to receive and process messages."""
        if not self.ws:
            return

        try:
            async for message in self.ws:
                if not self.running:
                    break
                await self._handle_message(message)
        except websockets.ConnectionClosed as e:
            logger.warning(f"WebSocket connection closed: {e}")
        except Exception as e:
            logger.error(f"WebSocket listen error: {e}")
        finally:
            self.running = False

    async def run(self, symbols: list):
        """
        Connect and run the WebSocket client with auto-reconnect.

        Args:
            symbols: List of symbols to subscribe to
        """
        while True:
            try:
                if await self.connect():
                    # Subscribe to both ticker and trades for fastest updates
                    await self.subscribe_ticker(symbols)
                    await self.subscribe_trades(symbols)
                    await self.listen()

                if not self.running:
                    break

            except Exception as e:
                logger.error(f"WebSocket error: {e}")

            # Reconnect with exponential backoff
            logger.info(f"Reconnecting in {self.reconnect_delay}s...")
            await asyncio.sleep(self.reconnect_delay)
            self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)

    async def close(self):
        """Close the WebSocket connection."""
        self.running = False
        if self.ws:
            await self.ws.close()
            self.ws = None
            logger.info("Kraken WebSocket closed")

    def get_last_tick(self, symbol: str) -> Optional[Dict]:
        """Get the last received tick for a symbol."""
        return self.last_tick.get(symbol)


# Convenience function to create and run WebSocket client
async def create_kraken_ws(symbols: list, on_ticker: Callable) -> KrakenWebSocket:
    """
    Create and start a Kraken WebSocket client.

    Args:
        symbols: List of symbols to subscribe to
        on_ticker: Callback for tick updates

    Returns:
        KrakenWebSocket instance
    """
    client = KrakenWebSocket(on_ticker=on_ticker)
    asyncio.create_task(client.run(symbols))
    return client
