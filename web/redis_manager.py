"""
Redis Manager for Production Deployment
Handles caching, pub/sub for real-time updates, and session management
"""

import json
import asyncio
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime, timedelta
import redis.asyncio as redis
from loguru import logger


class RedisManager:
    """Production-grade Redis manager for the trading application."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        prefix: str = "robo_trader:"
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.prefix = prefix
        self.redis: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self._subscribers: Dict[str, List[Callable]] = {}

    async def connect(self):
        """Connect to Redis server."""
        try:
            self.redis = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30
            )
            await self.redis.ping()
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis = None

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.pubsub:
            await self.pubsub.close()
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis")

    def _key(self, key: str) -> str:
        """Generate prefixed key."""
        return f"{self.prefix}{key}"

    # ==================== Caching ====================

    async def cache_set(
        self,
        key: str,
        value: Any,
        expire_seconds: int = 300
    ) -> bool:
        """Set a cached value with expiration."""
        if not self.redis:
            return False

        try:
            serialized = json.dumps(value, default=str)
            await self.redis.setex(self._key(key), expire_seconds, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    async def cache_get(self, key: str) -> Optional[Any]:
        """Get a cached value."""
        if not self.redis:
            return None

        try:
            value = await self.redis.get(self._key(key))
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    async def cache_delete(self, key: str) -> bool:
        """Delete a cached value."""
        if not self.redis:
            return False

        try:
            await self.redis.delete(self._key(key))
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    async def cache_exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        if not self.redis:
            return False

        try:
            return await self.redis.exists(self._key(key)) > 0
        except Exception as e:
            logger.error(f"Cache exists error: {e}")
            return False

    # ==================== Price Data Caching ====================

    async def cache_price(self, symbol: str, price_data: Dict):
        """Cache latest price data for a symbol."""
        key = f"price:{symbol.replace('/', '_')}"
        await self.cache_set(key, price_data, expire_seconds=60)

    async def get_cached_price(self, symbol: str) -> Optional[Dict]:
        """Get cached price data."""
        key = f"price:{symbol.replace('/', '_')}"
        return await self.cache_get(key)

    async def cache_ohlcv(self, symbol: str, timeframe: str, data: List[Dict]):
        """Cache OHLCV data."""
        key = f"ohlcv:{symbol.replace('/', '_')}:{timeframe}"
        await self.cache_set(key, data, expire_seconds=300)

    async def get_cached_ohlcv(self, symbol: str, timeframe: str) -> Optional[List[Dict]]:
        """Get cached OHLCV data."""
        key = f"ohlcv:{symbol.replace('/', '_')}:{timeframe}"
        return await self.cache_get(key)

    # ==================== Session Management ====================

    async def set_session(self, session_id: str, data: Dict, expire_hours: int = 24):
        """Store session data."""
        key = f"session:{session_id}"
        await self.cache_set(key, data, expire_seconds=expire_hours * 3600)

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session data."""
        key = f"session:{session_id}"
        return await self.cache_get(key)

    async def delete_session(self, session_id: str):
        """Delete session."""
        key = f"session:{session_id}"
        await self.cache_delete(key)

    # ==================== Pub/Sub for Real-time Updates ====================

    async def publish(self, channel: str, message: Dict):
        """Publish message to a channel."""
        if not self.redis:
            return

        try:
            serialized = json.dumps(message, default=str)
            await self.redis.publish(self._key(channel), serialized)
        except Exception as e:
            logger.error(f"Publish error: {e}")

    async def subscribe(self, channel: str, callback: Callable):
        """Subscribe to a channel with a callback."""
        if not self.redis:
            return

        if channel not in self._subscribers:
            self._subscribers[channel] = []
        self._subscribers[channel].append(callback)

        if not self.pubsub:
            self.pubsub = self.redis.pubsub()

        await self.pubsub.subscribe(self._key(channel))
        logger.info(f"Subscribed to channel: {channel}")

    async def start_listener(self):
        """Start listening for pub/sub messages."""
        if not self.pubsub:
            return

        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"].replace(self.prefix, "")
                    data = json.loads(message["data"])

                    if channel in self._subscribers:
                        for callback in self._subscribers[channel]:
                            try:
                                if asyncio.iscoroutinefunction(callback):
                                    await callback(data)
                                else:
                                    callback(data)
                            except Exception as e:
                                logger.error(f"Subscriber callback error: {e}")
        except Exception as e:
            logger.error(f"Listener error: {e}")

    # ==================== Rate Limiting ====================

    async def check_rate_limit(
        self,
        identifier: str,
        max_requests: int = 100,
        window_seconds: int = 60
    ) -> bool:
        """
        Check if request is within rate limit.
        Returns True if allowed, False if rate limited.
        """
        if not self.redis:
            return True

        key = f"rate_limit:{identifier}"
        full_key = self._key(key)

        try:
            current = await self.redis.incr(full_key)
            if current == 1:
                await self.redis.expire(full_key, window_seconds)

            return current <= max_requests
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            return True

    # ==================== Trading State ====================

    async def set_trading_state(self, state: Dict):
        """Store current trading state."""
        await self.cache_set("trading_state", state, expire_seconds=3600)

    async def get_trading_state(self) -> Optional[Dict]:
        """Get current trading state."""
        return await self.cache_get("trading_state")

    async def add_trade_to_history(self, trade: Dict):
        """Add trade to Redis list for fast retrieval."""
        if not self.redis:
            return

        try:
            key = self._key("trade_history")
            serialized = json.dumps(trade, default=str)
            await self.redis.lpush(key, serialized)
            await self.redis.ltrim(key, 0, 999)  # Keep last 1000 trades
        except Exception as e:
            logger.error(f"Add trade error: {e}")

    async def get_recent_trades(self, limit: int = 50) -> List[Dict]:
        """Get recent trades from Redis."""
        if not self.redis:
            return []

        try:
            key = self._key("trade_history")
            trades = await self.redis.lrange(key, 0, limit - 1)
            return [json.loads(t) for t in trades]
        except Exception as e:
            logger.error(f"Get trades error: {e}")
            return []

    # ==================== Health Check ====================

    async def health_check(self) -> Dict:
        """Check Redis connection health."""
        if not self.redis:
            return {"status": "disconnected", "latency_ms": None}

        try:
            start = datetime.now()
            await self.redis.ping()
            latency = (datetime.now() - start).total_seconds() * 1000

            info = await self.redis.info("memory")

            return {
                "status": "connected",
                "latency_ms": round(latency, 2),
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients")
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


# Global Redis manager instance
redis_manager = RedisManager()
