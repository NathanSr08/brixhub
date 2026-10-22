#!/usr/bin/env python3
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
DONE, SKIPPED, FAILED = [], [], []


def load(p): return (ROOT / p).read_text(encoding="utf-8")


def save(p, s):
    f = ROOT / p
    bak = f.with_suffix(f.suffix + ".bakflush")
    if not bak.exists():
        shutil.copy2(f, bak)
    f.write_text(s, encoding="utf-8")


def replace(path, old, new, marker, label):
    s = load(path)
    if marker in s:
        SKIPPED.append(label); return
    if old not in s:
        FAILED.append(f"{label} : ancre introuvable dans {path}"); return
    save(path, s.replace(old, new, 1))
    DONE.append(label)


# ---------- audit.py : verrou de flush ----------
P = "app/core/audit.py"
replace(P,
    "_lock = asyncio.Lock()\nMAX_BUFFER = 200",
    "_lock = asyncio.Lock()\n_flush_lock = asyncio.Lock()   # serialise les INSERT ClickHouse\nMAX_BUFFER = 200",
    "_flush_lock = asyncio.Lock()", "audit.py : verrou de flush")

replace(P,
    '''async def _push(row: list) -> None:
    rows = None
    async with _lock:
        _buffer.append(row)
        if len(_buffer) >= MAX_BUFFER:
            rows, _buffer[:] = _buffer[:], []
    if rows:
        try:
            await asyncio.to_thread(_flush_sync, rows)
        except Exception as e:
            print(f"[AUDIT] flush KO: {e}", flush=True)


async def flush_now() -> None:
    async with _lock:
        rows, _buffer[:] = _buffer[:], []
    if rows:
        await asyncio.to_thread(_flush_sync, rows)''',
    '''async def _push(row: list) -> None:
    rows = None
    async with _lock:
        _buffer.append(row)
        if len(_buffer) >= MAX_BUFFER:
            rows, _buffer[:] = _buffer[:], []
    if rows:
        async with _flush_lock:
            try:
                await asyncio.to_thread(_flush_sync, rows)
            except Exception as e:
                print(f"[AUDIT] flush KO: {e}", flush=True)


async def flush_now() -> None:
    async with _lock:
        rows, _buffer[:] = _buffer[:], []
    if rows:
        async with _flush_lock:
            await asyncio.to_thread(_flush_sync, rows)''',
    "async with _flush_lock:", "audit.py : _push/flush_now")

# ---------- usage_repo.py : verrou threading + plus de clear sauvage ----------
P = "app/repositories/usage_repo.py"
replace(P,
    "import asyncio, json\nfrom app.db.clickhouse import get_ch",
    "import asyncio\nimport json\nimport threading\n\nfrom app.db.clickhouse import get_ch",
    "import threading", "usage_repo.py : import threading")

replace(P,
    "_buffer: list[list] = []\n_lock = asyncio.Lock()",
    "_buffer: list[list] = []\n_lock = threading.Lock()",
    "_lock = threading.Lock()", "usage_repo.py : verrou threading")

replace(P,
    """async def add_usage(key_id: str, endpoint: str, status: int,
                    latency_ms: int, client_ip: str) -> None:
    async with _lock:""",
    """async def add_usage(key_id: str, endpoint: str, status: int,
                    latency_ms: int, client_ip: str) -> None:
    with _lock:""",
    "latency_ms: int, client_ip: str) -> None:\n    with _lock:",
    "usage_repo.py : add_usage")

replace(P,
    """        await asyncio.sleep(interval)
        async with _lock:""",
    """        await asyncio.sleep(interval)
        with _lock:""",
    "await asyncio.sleep(interval)\n        with _lock:",
    "usage_repo.py : flush_loop")

replace(P,
    """def get_key_logs(key_id: str, limit: int = 100) -> list[dict]:
    global _buffer
    if _buffer:
        try:
            _flush_sync(_buffer[:])
            _buffer.clear()
        except Exception:
            pass

    res = get_ch().query(""",
    """def get_key_logs(key_id: str, limit: int = 100) -> list[dict]:
    with _lock:
        rows, _buffer[:] = _buffer[:], []
    if rows:
        try:
            _flush_sync(rows)
        except Exception:
            pass

    res = get_ch().query(""",
    "rows, _buffer[:] = _buffer[:], []\n    if rows:\n        try:\n            _flush_sync(rows)",
    "usage_repo.py : get_key_logs")

print("\n=== PATCH ===")
for d in DONE: print("  [OK]   ", d)
for s_ in SKIPPED: print("  [SKIP] ", s_)
for f in FAILED: print("  [ECHEC]", f)
print(f"\n{len(DONE)} applique(s), {len(SKIPPED)} deja en place, {len(FAILED)} echec(s).")
sys.exit(1 if FAILED else 0)
