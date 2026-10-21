import uuid
import json
from datetime import datetime
from app.db.clickhouse import get_ch

USERS_TABLE = "sports_db.users"
SEARCH_LOG_TABLE = "sports_db.search_log"

def _query(sql: str, parameters: dict = None):
    # Utilise l instance client du pool
    return get_ch().query(sql, parameters=parameters)

def _command(sql: str):
    return get_ch().command(sql)

def _insert(table: str, data: list, column_names: list):
    return get_ch().insert(table, data, column_names=column_names)

def list_all_users() -> list[dict]:
    res = _query(f"""
        SELECT user_id, email, is_active, plan, api_key_id, created_at
        FROM {USERS_TABLE} FINAL
        ORDER BY created_at DESC
    """)
    return [
        {
            "user_id": str(r[0]),
            "email": r[1],
            "is_active": int(r[2]),
            "plan": r[3],
            "api_key_id": r[4] or "",
            "created_at": str(r[5])
        }
        for r in res.result_rows
    ]

def get_by_email(email: str) -> dict | None:
    res = _query(f"""
        SELECT user_id, email, password_hash, is_active, plan, api_key_id, created_at
        FROM {USERS_TABLE} FINAL
        WHERE lower(email) = lower(%(email)s)
        LIMIT 1
    """, parameters={"email": email.strip()})
    
    if not res.result_rows:
        return None
    r = res.result_rows[0]
    return {
        "user_id": str(r[0]),
        "email": r[1],
        "password_hash": r[2],
        "is_active": int(r[3]),
        "plan": r[4],
        "api_key_id": r[5],
        "created_at": str(r[6])
    }

def get_by_id(user_id: str) -> dict | None:
    res = _query(f"""
        SELECT user_id, email, password_hash, is_active, plan, api_key_id, created_at
        FROM {USERS_TABLE} FINAL
        WHERE toString(user_id) = %(uid)s
        LIMIT 1
    """, parameters={"uid": user_id})
    
    if not res.result_rows:
        return None
    r = res.result_rows[0]
    return {
        "user_id": str(r[0]),
        "email": r[1],
        "password_hash": r[2],
        "is_active": int(r[3]),
        "plan": r[4],
        "api_key_id": r[5],
        "created_at": str(r[6])
    }

def create_user(email: str, password_hash: str) -> str:
    user_id = str(uuid.uuid4())
    row = [[uuid.UUID(user_id), email.lower().strip(), password_hash, 1, "free", None, datetime.utcnow()]]
    _insert(USERS_TABLE, row, column_names=["user_id", "email", "password_hash", "is_active", "plan", "api_key_id", "created_at"])
    return user_id

def update_password(user_id: str, new_password_hash: str) -> None:
    user = get_by_id(user_id)
    if not user:
        return
    row = [[uuid.UUID(user_id), user["email"], new_password_hash, user["is_active"], user["plan"], user["api_key_id"], datetime.utcnow()]]
    _insert(USERS_TABLE, row, column_names=["user_id", "email", "password_hash", "is_active", "plan", "api_key_id", "created_at"])

def link_api_key(user_id: str, key_id: str, new_plan: str) -> None:
    user = get_by_id(user_id)
    if not user:
        return
    row = [[uuid.UUID(user_id), user["email"], user["password_hash"], user["is_active"], new_plan, key_id, datetime.utcnow()]]
    _insert(USERS_TABLE, row, column_names=["user_id", "email", "password_hash", "is_active", "plan", "api_key_id", "created_at"])

def toggle_user_status(user_id: str, is_active: int) -> None:
    user = get_by_id(user_id)
    if not user:
        return
    row = [[uuid.UUID(user_id), user["email"], user["password_hash"], is_active, user["plan"], user["api_key_id"], datetime.utcnow()]]
    _insert(USERS_TABLE, row, column_names=["user_id", "email", "password_hash", "is_active", "plan", "api_key_id", "created_at"])

def update_user_plan(user_id: str, plan: str) -> None:
    user = get_by_id(user_id)
    if not user:
        return
    row = [[uuid.UUID(user_id), user["email"], user["password_hash"], user["is_active"], plan, user["api_key_id"], datetime.utcnow()]]
    _insert(USERS_TABLE, row, column_names=["user_id", "email", "password_hash", "is_active", "plan", "api_key_id", "created_at"])

def get_user_search_logs(user_id: str, key_id: str = None, limit: int = 100) -> list[dict]:
    ch = get_ch()
    # Récupérer par user_id exact, ou par son api_key_id
    uid_str = str(user_id).strip()
    kid_str = str(key_id).strip() if key_id else ""

    res = ch.query(f"""
        SELECT ts, client_ip, criteria, nb_results
        FROM sports_db.search_log
        WHERE toString(key_id) = %(uid)s OR (%(kid)s != '' AND toString(key_id) = %(kid)s)
        ORDER BY ts DESC
        LIMIT %(lim)s
    """, parameters={"uid": uid_str, "kid": kid_str, "lim": limit})

    logs = []
    for r in res.result_rows:
        logs.append({
            "ts": str(r[0]),
            "client_ip": str(r[1]),
            "criteria": str(r[2]),
            "nb_results": int(r[3])
        })
    return logs