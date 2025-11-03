"""Redis client utilities."""
import json
import os
import redis
from typing import Optional, Any


REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))


def create_redis_client() -> redis.Redis:
    """Create a Redis client."""
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True
    )


def set_session_data(client: redis.Redis, session_id: str, data: dict, ttl: Optional[int] = None):
    """Store session data in Redis."""
    key = f"session:{session_id}"
    client.set(key, json.dumps(data), ex=ttl)


def get_session_data(client: redis.Redis, session_id: str) -> Optional[dict]:
    """Retrieve session data from Redis."""
    key = f"session:{session_id}"
    data = client.get(key)
    return json.loads(data) if data else None


def publish_realtime_update(client: redis.Redis, channel: str, message: dict):
    """Publish a real-time update to a Redis channel."""
    client.publish(channel, json.dumps(message))

