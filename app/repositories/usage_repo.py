import asyncio
import json
import threading

from app.db.clickhouse import get_ch

USAGE_TABLE = "sports_db.api_usage"
LOG_TABLE = "sports_db.search_log"

_buffer: list[list] = []
_lock = threading.Lock()
MAX_BUFFER = 200

def _flush_sync(rows: list[list]) -> None:
    if rows:
        get_ch().insert(
            USAGE_TABLE, data=rows,
            column_names=["key_id", "endpoint", "status", "latency_ms", "client_ip"],
        )

async def add_usage(key_id: str, endpoint: str, status: int,
                    latency_ms: int, client_ip: str) -> None:
    with _lock:
        _buffer.append([key_id, endpoint, status, latency_ms, client_ip])
        if len(_buffer) >= MAX_BUFFER:
            rows, _buffer[:] = _buffer[:], []
        else:
            rows = None
    if rows:
        await asyncio.to_thread(_flush_sync, rows)

async def flush_loop(interval: int = 15) -> None:
    while True:
        await asyncio.sleep(interval)
        with _lock:
            rows, _buffer[:] = _buffer[:], []
        if rows:
            await asyncio.to_thread(_flush_sync, rows)

def log_search(client_ip: str, key_id: str, criteria: dict, nb: int) -> None:
    get_ch().insert(
        LOG_TABLE,
        data=[[client_ip, key_id, json.dumps(criteria, ensure_ascii=False), nb]],
        column_names=["client_ip", "key_id", "criteria", "nb_results"],
    )

def usage_summary(key_id: str, days: int = 30) -> list[dict]:
    res = get_ch().query(f"""
        SELECT toDate(ts) AS jour, count() AS requetes,
               round(avg(latency_ms)) AS latence_moy,
               countIf(status >= 400) AS erreurs
        FROM {USAGE_TABLE}
        WHERE key_id = %(k)s AND ts >= now() - INTERVAL %(d)s DAY
        GROUP BY jour ORDER BY jour DESC
    """, parameters={"k": key_id, "d": days})
    return [{"jour": str(r[0]), "requetes": r[1], "latence_moy_ms": r[2], "erreurs": r[3]}
            for r in res.result_rows]

def usage_today(key_id: str) -> int:
    res = get_ch().query(
        f"SELECT count() FROM {USAGE_TABLE} WHERE key_id = %(k)s AND toDate(ts) = today()",
        parameters={"k": key_id})
    return res.result_rows[0][0] if res.result_rows else 0


def get_key_logs(key_id: str, limit: int = 100) -> list[dict]:
    with _lock:
        rows, _buffer[:] = _buffer[:], []
    if rows:
        try:
            _flush_sync(rows)
        except Exception:
            pass

    res = get_ch().query(f"""
        SELECT ts, endpoint, status, latency_ms, client_ip
        FROM {USAGE_TABLE}
        WHERE key_id = %(k)s
        ORDER BY ts DESC
        LIMIT %(lim)s
    """, parameters={"k": key_id, "lim": limit})
    
    return [
        {
            "ts": str(r[0]),
            "endpoint": r[1],
            "status": r[2],
            "latency_ms": r[3],
            "client_ip": r[4]
        }
        for r in res.result_rows
    ]
