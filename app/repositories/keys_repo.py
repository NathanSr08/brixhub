import uuid
from typing import Optional
from app.db.clickhouse import get_ch

TABLE = "sports_db.api_keys"
COLS = "key_id, key_hash, preview, label, owner_email, plan, is_active, created_at"

def _row(r) -> dict:
    d = dict(zip(["key_id", "key_hash", "preview", "label", "owner_email", "plan", "is_active", "created_at"], r))
    if isinstance(d["key_hash"], bytes):
        d["key_hash"] = d["key_hash"].decode("utf-8")
    d["is_active"] = int(d["is_active"])
    return d

def get_by_hash(key_hash: str) -> Optional[dict]:
    res = get_ch().query(
        f"SELECT {COLS} FROM {TABLE} FINAL WHERE key_hash = %(h)s LIMIT 1",
        parameters={"h": key_hash},
    )
    return _row(res.result_rows[0]) if res.result_rows else None

def get_by_id(key_id: str) -> Optional[dict]:
    res = get_ch().query(
        f"SELECT {COLS} FROM {TABLE} FINAL WHERE key_id = %(i)s LIMIT 1",
        parameters={"i": key_id},
    )
    return _row(res.result_rows[0]) if res.result_rows else None

def insert(rec: dict) -> None:
    kh = rec["key_hash"]
    if isinstance(kh, bytes):
        kh = kh.decode("utf-8")
    get_ch().insert(
        TABLE,
        data=[[rec["key_id"], kh, rec["preview"], rec["label"],
               rec["owner_email"], rec["plan"], int(rec["is_active"]), rec["created_at"]]],
        column_names=["key_id", "key_hash", "preview", "label",
                      "owner_email", "plan", "is_active", "created_at"],
    )

def list_all() -> list[dict]:
    res = get_ch().query(f"SELECT {COLS} FROM {TABLE} FINAL ORDER BY created_at DESC")
    return [_row(r) for r in res.result_rows]

def new_id() -> str:
    return uuid.uuid4().hex[:16]
