"""Overrides d'acces web par utilisateur (pilotage admin)."""
from __future__ import annotations

from datetime import datetime

from app.db.clickhouse import get_ch

TABLE = "sports_db.user_web_overrides"
_COLS = ["user_id", "web_unlimited", "web_daily_quota", "api_key_unlimited", "note", "updated_at"]


def _query(sql, parameters=None):
    return get_ch().query(sql, parameters=parameters or {}).result_rows


def _command(sql, parameters=None):
    return get_ch().command(sql, parameters=parameters or {})


def ensure_table() -> None:
    _command(
        "CREATE TABLE IF NOT EXISTS %s ("
        " user_id UUID,"
        " web_unlimited UInt8 DEFAULT 0,"
        " web_daily_quota Nullable(Int32),"
        " api_key_unlimited Nullable(UInt8),"
        " note String DEFAULT '',"
        " updated_at DateTime DEFAULT now()"
        ") ENGINE = ReplacingMergeTree(updated_at) ORDER BY user_id" % TABLE
    )


def list_overrides() -> dict:
    try:
        rows = _query("SELECT %s FROM %s FINAL" % (", ".join(_COLS), TABLE))
    except Exception:
        return {}
    out = {}
    for r in rows:
        d = dict(zip(_COLS, r))
        out[str(d["user_id"])] = d
    return out


def get_override(user_id: str) -> dict | None:
    rows = _query(
        "SELECT %s FROM %s FINAL WHERE user_id = %%(uid)s" % (", ".join(_COLS), TABLE),
        {"uid": user_id},
    )
    return dict(zip(_COLS, rows[0])) if rows else None


def upsert(user_id: str, **fields) -> None:
    cur = get_override(user_id) or {}
    row = {
        "user_id": user_id,
        "web_unlimited": int(cur.get("web_unlimited") or 0),
        "web_daily_quota": cur.get("web_daily_quota"),
        "api_key_unlimited": cur.get("api_key_unlimited"),
        "note": cur.get("note") or "",
    }
    for k, v in fields.items():
        if k in row:
            row[k] = v
    row["updated_at"] = datetime.utcnow()
    get_ch().insert(TABLE, [[row[c] for c in _COLS]], column_names=_COLS)


def clear_override(user_id: str) -> None:
    upsert(user_id, web_unlimited=0, web_daily_quota=None, api_key_unlimited=None, note="")
