from typing import Optional
import clickhouse_connect
from redis.asyncio import Redis
from app.core.config import get_settings

_client = None
_redis: Optional[Redis] = None

def _init_ch_sync():
    global _client
    if _client is None:
        s = get_settings()
        _client = clickhouse_connect.get_client(
            host=s.clickhouse_host,
            port=s.clickhouse_port,
            username=s.clickhouse_user,
            password=s.clickhouse_password,
            compress=True,
        )
    return _client

async def init_clients() -> None:
    global _client, _redis
    _init_ch_sync()
    s = get_settings()
    _redis = Redis.from_url(s.redis_url, decode_responses=True)
    await _redis.ping()

async def close_clients() -> None:
    global _client, _redis
    if _client:
        _client.close()
        _client = None
    if _redis:
        await _redis.aclose()
        _redis = None

def get_ch():
    global _client
    if _client is None:
        _init_ch_sync()
    return _client

def get_redis() -> Redis:
    if _redis is None:
        raise RuntimeError("Client Redis non initialisé")
    return _redis

get_ch_client = get_ch
