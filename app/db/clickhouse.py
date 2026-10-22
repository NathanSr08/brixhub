"""
Clients ClickHouse / Redis.

Le client HTTP de clickhouse_connect n'est pas thread-safe : on en instancie
un par thread appelant (thread-local) et on desactive la session cote serveur
pour eviter "Attempt to execute concurrent queries within the same session".
"""
from __future__ import annotations

import threading
from typing import Optional

import clickhouse_connect
from redis.asyncio import Redis

from app.core.config import get_settings

_local = threading.local()
_all_clients: list = []
_registry_lock = threading.Lock()
_redis: Optional[Redis] = None


def _make_client():
    s = get_settings()
    client = clickhouse_connect.get_client(
        host=s.clickhouse_host,
        port=s.clickhouse_port,
        username=s.clickhouse_user,
        password=s.clickhouse_password,
        compress=True,
        autogenerate_session_id=False,
        connect_timeout=10,
        send_receive_timeout=120,
    )
    with _registry_lock:
        _all_clients.append(client)
    return client


def get_ch():
    """Client ClickHouse dedie au thread appelant (thread-safe)."""
    client = getattr(_local, "client", None)
    if client is None:
        client = _make_client()
        _local.client = client
    return client


def get_ch_client():
    return get_ch()


def _init_ch_sync():
    return get_ch()


async def init_clients() -> None:
    global _redis
    get_ch()                       # client du thread principal
    s = get_settings()
    _redis = Redis.from_url(s.redis_url, decode_responses=True)
    await _redis.ping()


async def close_clients() -> None:
    global _redis
    with _registry_lock:
        clients, _all_clients[:] = _all_clients[:], []
    for c in clients:
        try:
            c.close()
        except Exception:
            pass
    _local.client = None
    if _redis:
        try:
            await _redis.aclose()
        except Exception:
            pass
        _redis = None


def get_redis() -> Redis:
    if _redis is None:
        raise RuntimeError("Client Redis non initialise")
    return _redis
