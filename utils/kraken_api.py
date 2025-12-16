"""
Kraken API utility module for direct API access.

This module provides direct Kraken REST API access without going through CCXT,
useful for advanced features and debugging.
"""

import os
import time
import base64
import hmac
import hashlib
import urllib.parse
from typing import Optional, Literal, Dict, Any, List
from dotenv import load_dotenv
import requests
from loguru import logger


# Load environment variables
load_dotenv()

# API endpoints
KRAKEN_BASE = "https://api.kraken.com"

# Public endpoints
TIME_PATH = "/0/public/Time"
SYSTEM_STATUS_PATH = "/0/public/SystemStatus"
ASSETS_PATH = "/0/public/Assets"
ASSET_PAIRS_PATH = "/0/public/AssetPairs"
TICKER_PATH = "/0/public/Ticker"
OHLC_PATH = "/0/public/OHLC"
DEPTH_PATH = "/0/public/Depth"
TRADES_PATH = "/0/public/Trades"
SPREAD_PATH = "/0/public/Spread"

# Private endpoints
ADD_ORDER_PATH = "/0/private/AddOrder"
CANCEL_ORDER_PATH = "/0/private/CancelOrder"
OPEN_ORDERS_PATH = "/0/private/OpenOrders"
AMEND_ORDER_PATH = "/0/private/AmendOrder"
CANCEL_ALL_AFTER_PATH = "/0/private/CancelAllOrdersAfter"
BALANCE_PATH = "/0/private/Balance"
CLOSED_ORDERS_PATH = "/0/private/ClosedOrders"
TRADES_HISTORY_PATH = "/0/private/TradesHistory"


class KrakenAPIError(Exception):
    """Kraken API error."""
    pass


class KrakenAPI:
    """Direct Kraken REST API client."""

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize Kraken API client.

        Args:
            api_key: Kraken API key (defaults to KRAKEN_API_KEY env var)
            api_secret: Kraken API secret (defaults to KRAKEN_API_SECRET env var)
        """
        self.api_key = api_key or os.getenv("KRAKEN_API_KEY")
        self.api_secret = api_secret or os.getenv("KRAKEN_API_SECRET")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "robo-trader/1.0"
        })

    def _nonce(self) -> str:
        """Generate unique nonce for request signing."""
        return str(int(time.time() * 1000))

    def _normalize_payload(self, d: dict) -> dict:
        """Normalize payload values for API."""
        out = {}
        for k, v in d.items():
            if v is True:
                out[k] = "true"
            elif v is False:
                out[k] = "false"
            elif v is None:
                continue
            else:
                out[k] = v
        return out

    def _sign(self, url_path: str, payload: dict) -> tuple:
        """
        Sign request for Kraken API authentication.

        Returns:
            Tuple of (signature, encoded_postdata)
        """
        postdata = urllib.parse.urlencode(payload)
        encoded = (str(payload["nonce"]) + postdata).encode()
        sha256 = hashlib.sha256(encoded).digest()
        message = url_path.encode() + sha256
        mac = hmac.new(base64.b64decode(self.api_secret), message, hashlib.sha512)
        return base64.b64encode(mac.digest()).decode(), postdata

    def _public_get(self, url_path: str, params: Optional[dict] = None, timeout: float = 15.0) -> dict:
        """Make public (unauthenticated) GET request."""
        url = KRAKEN_BASE + url_path
        r = self.session.get(url, params=params or {}, timeout=timeout)
        r.raise_for_status()
        j = r.json()
        if j.get("error"):
            raise KrakenAPIError("; ".join(j["error"]))
        if "result" not in j:
            raise KrakenAPIError("Kraken API response missing 'result' key.")
        return j["result"]

    def _private_post(self, url_path: str, data: dict, timeout: float = 15.0) -> dict:
        """Make private (authenticated) POST request."""
        if not self.api_key or not self.api_secret:
            raise KrakenAPIError("Missing KRAKEN_API_KEY / KRAKEN_API_SECRET")

        url = KRAKEN_BASE + url_path
        data = self._normalize_payload(data)
        sig, postdata = self._sign(url_path, data)

        headers = {
            "API-Key": self.api_key,
            "API-Sign": sig,
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        }

        r = self.session.post(url, headers=headers, data=postdata, timeout=timeout)
        r.raise_for_status()
        j = r.json()
        if j.get("error"):
            raise KrakenAPIError("; ".join(j["error"]))
        if "result" not in j:
            raise KrakenAPIError("Kraken API response missing 'result' key.")
        return j["result"]

    # ==================== Public Market Data ====================

    def get_server_time(self) -> dict:
        """Get Kraken server time (UTC)."""
        return self._public_get(TIME_PATH)

    def get_system_status(self) -> dict:
        """Get current system status / trading mode."""
        return self._public_get(SYSTEM_STATUS_PATH)

    def get_asset_info(self, assets: Optional[str] = None) -> dict:
        """
        Get asset metadata.

        Args:
            assets: Comma-separated asset list, e.g. 'XBT,ETH,USDT'
        """
        params = {}
        if assets:
            params["asset"] = assets
        return self._public_get(ASSETS_PATH, params)

    def get_tradable_pairs(self, pairs: Optional[str] = None) -> dict:
        """
        Get tradable asset pairs info.

        Args:
            pairs: Comma-separated pair list, e.g. 'XBTUSD,ETHUSD'
        """
        params = {}
        if pairs:
            params["pair"] = pairs
        return self._public_get(ASSET_PAIRS_PATH, params)

    def get_ticker(self, pairs: Optional[str] = None) -> dict:
        """
        Get ticker information.

        Args:
            pairs: Comma-separated pair list. None for all pairs.
        """
        params = {}
        if pairs:
            params["pair"] = pairs
        return self._public_get(TICKER_PATH, params)

    def get_ohlc(self, pair: str, interval: int = 1, since: Optional[int] = None) -> dict:
        """
        Get OHLC candlestick data.

        Args:
            pair: Trading pair (e.g. 'XBTUSD')
            interval: Candle interval in minutes (1, 5, 15, 30, 60, 240, 1440, 10080, 21600)
            since: Unix timestamp to start from
        """
        params = {"pair": pair, "interval": int(interval)}
        if since is not None:
            params["since"] = int(since)
        return self._public_get(OHLC_PATH, params)

    def get_order_book(self, pair: str, count: Optional[int] = None) -> dict:
        """
        Get order book depth.

        Args:
            pair: Trading pair
            count: Max levels per side
        """
        params = {"pair": pair}
        if count is not None:
            params["count"] = int(count)
        return self._public_get(DEPTH_PATH, params)

    def get_recent_trades(self, pair: str, since: Optional[int] = None) -> dict:
        """
        Get recent trades.

        Args:
            pair: Trading pair
            since: Return trades since this ID
        """
        params = {"pair": pair}
        if since is not None:
            params["since"] = int(since)
        return self._public_get(TRADES_PATH, params)

    def get_recent_spreads(self, pair: str, since: Optional[int] = None) -> dict:
        """Get recent spreads (bid/ask)."""
        params = {"pair": pair}
        if since is not None:
            params["since"] = int(since)
        return self._public_get(SPREAD_PATH, params)

    # ==================== Private Account Data ====================

    def get_balance(self) -> dict:
        """Get account balance."""
        return self._private_post(BALANCE_PATH, {"nonce": self._nonce()})

    def get_open_orders(self, userref: Optional[int] = None) -> dict:
        """
        Get open orders.

        Args:
            userref: Filter by user reference ID
        """
        data = {"nonce": self._nonce()}
        if userref is not None:
            data["userref"] = int(userref)
        return self._private_post(OPEN_ORDERS_PATH, data)

    def get_closed_orders(
        self,
        start: Optional[int] = None,
        end: Optional[int] = None,
        offset: Optional[int] = None
    ) -> dict:
        """
        Get closed orders.

        Args:
            start: Starting timestamp
            end: Ending timestamp
            offset: Pagination offset
        """
        data = {"nonce": self._nonce()}
        if start is not None:
            data["start"] = str(start)
        if end is not None:
            data["end"] = str(end)
        if offset is not None:
            data["ofs"] = int(offset)
        return self._private_post(CLOSED_ORDERS_PATH, data)

    def get_trades_history(
        self,
        start: Optional[int] = None,
        end: Optional[int] = None,
        offset: Optional[int] = None
    ) -> dict:
        """
        Get trade history (fills).

        Args:
            start: Starting timestamp
            end: Ending timestamp
            offset: Pagination offset (50 per page)
        """
        data = {"nonce": self._nonce(), "type": "all"}
        if start is not None:
            data["start"] = str(start)
        if end is not None:
            data["end"] = str(end)
        if offset is not None:
            data["ofs"] = int(offset)
        return self._private_post(TRADES_HISTORY_PATH, data)

    # ==================== Trading ====================

    def add_order(
        self,
        pair: str,
        side: Literal["buy", "sell"],
        ordertype: Literal["market", "limit", "stop-loss", "take-profit",
                          "stop-loss-limit", "take-profit-limit"] = "limit",
        volume: float = 0.0,
        price: Optional[str] = None,
        price2: Optional[str] = None,
        timeinforce: Optional[Literal["GTC", "IOC", "GTD"]] = None,
        userref: Optional[int] = None,
        validate: bool = True
    ) -> dict:
        """
        Place a new order.

        Args:
            pair: Trading pair (e.g. 'XBTUSD')
            side: 'buy' or 'sell'
            ordertype: Order type
            volume: Order volume
            price: Price for limit orders
            price2: Secondary price (for stop-loss-limit, etc.)
            timeinforce: Time in force (GTC, IOC, GTD)
            userref: User reference ID
            validate: If True, validate only (don't execute)

        Returns:
            Order result dict with txid
        """
        data = {
            "nonce": self._nonce(),
            "pair": pair,
            "type": side,
            "ordertype": ordertype,
            "volume": str(volume),
        }
        if price is not None:
            data["price"] = str(price)
        if price2 is not None:
            data["price2"] = str(price2)
        if timeinforce is not None:
            data["timeinforce"] = timeinforce
        if userref is not None:
            data["userref"] = int(userref)
        if validate:
            data["validate"] = True

        return self._private_post(ADD_ORDER_PATH, data)

    def cancel_order(self, txid: str) -> dict:
        """
        Cancel an open order.

        Args:
            txid: Order transaction ID or userref
        """
        data = {
            "nonce": self._nonce(),
            "txid": txid,
        }
        return self._private_post(CANCEL_ORDER_PATH, data)

    def cancel_all_orders_after(self, timeout_seconds: int) -> dict:
        """
        Dead man's switch: cancel all orders after timeout.

        Args:
            timeout_seconds: Seconds until all orders are cancelled. 0 to disable.
        """
        data = {
            "nonce": self._nonce(),
            "timeout": int(timeout_seconds),
        }
        return self._private_post(CANCEL_ALL_AFTER_PATH, data)

    def amend_order(
        self,
        order_id: Optional[str] = None,
        order_qty: Optional[str] = None,
        limit_price: Optional[str] = None,
        trigger_price: Optional[str] = None
    ) -> dict:
        """
        Amend an existing order.

        Args:
            order_id: Order ID to amend
            order_qty: New quantity
            limit_price: New limit price
            trigger_price: New trigger price (for stop orders)
        """
        if not order_id:
            raise KrakenAPIError("order_id is required")
        if not any([order_qty, limit_price, trigger_price]):
            raise KrakenAPIError("Provide at least one field to amend")

        data = {"nonce": self._nonce(), "order_id": order_id}
        if order_qty is not None:
            data["order_qty"] = str(order_qty)
        if limit_price is not None:
            data["limit_price"] = str(limit_price)
        if trigger_price is not None:
            data["trigger_price"] = str(trigger_price)

        return self._private_post(AMEND_ORDER_PATH, data)


# Convenience functions for quick access
_default_client: Optional[KrakenAPI] = None

def get_client() -> KrakenAPI:
    """Get or create default Kraken API client."""
    global _default_client
    if _default_client is None:
        _default_client = KrakenAPI()
    return _default_client


def get_btc_price() -> float:
    """Quick helper to get current BTC/USD price."""
    client = get_client()
    ticker = client.get_ticker("XBTUSD")
    return float(ticker["XXBTZUSD"]["c"][0])


def get_eth_price() -> float:
    """Quick helper to get current ETH/USD price."""
    client = get_client()
    ticker = client.get_ticker("ETHUSD")
    return float(ticker["XETHZUSD"]["c"][0])


def get_account_summary() -> dict:
    """Get a summary of account balances."""
    client = get_client()
    balances = client.get_balance()

    # Filter out zero balances
    non_zero = {k: float(v) for k, v in balances.items() if float(v) > 0}

    return {
        "balances": non_zero,
        "system_status": client.get_system_status()
    }


if __name__ == "__main__":
    # Test the API
    print("Testing Kraken API...")

    client = KrakenAPI()

    print("\n--- System Status ---")
    print(client.get_system_status())

    print("\n--- BTC/USD Price ---")
    print(f"${get_btc_price():,.2f}")

    print("\n--- ETH/USD Price ---")
    print(f"${get_eth_price():,.2f}")

    print("\n--- Account Summary ---")
    print(get_account_summary())
