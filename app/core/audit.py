"""
BrixHub - Audit Trail global.
Journalise TOUTES les requetes HTTP (guest, user, admin, cle API, bot) dans
auth_db.api_logs. Bufferise (200 lignes ou 2 s) : aucun impact sur la latence.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.db.clickhouse import get_ch, get_redis
from app.repositories import usage_repo, users_repo

AUDIT_TABLE = "auth_db.api_logs"

MAX_UA, MAX_Q, MAX_PATH, MAX_ERR, MAX_ENDPOINT = 280, 700, 300, 300, 400

_buffer: list[list] = []
_lock = asyncio.Lock()
_flush_lock = asyncio.Lock()   # serialise les INSERT ClickHouse
MAX_BUFFER = 200
FLUSH_INTERVAL = 2.0

COLUMNS = [
    "timestamp", "actor_type", "actor_id", "actor_label", "session_ref",
    "ip", "user_id", "user_email", "endpoint", "path", "route", "method",
    "query_params", "status_code", "execution_time_ms", "latency_ms",
    "user_agent", "ua_hash", "referer", "request_id", "error", "tag", "meta",
]

BOT_RE = re.compile(
    r"(bot|crawler|spider|curl|wget|python-requests|python-httpx|httpx|"
    r"axios|postman|insomnia|scrapy|go-http|headless|phantom)", re.I)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sha16(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "ignore")).hexdigest()[:16]


def _clip(value, size: int) -> str:
    if value is None:
        return ""
    return str(value).strip()[:size]


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return (request.headers.get("x-real-ip")
            or (request.client.host if request.client else "?"))


def _tag_for(path: str) -> str:
    if path.startswith("/admin/api/logs"):
        return "panel"
    if path.startswith("/admin"):
        return "admin"
    if path.startswith("/auth") or path.startswith("/api/auth"):
        return "auth"
    if path.startswith("/v1"):
        return "api"
    if path.startswith("/api/search"):
        return "search"
    if path.startswith("/api/correlations"):
        return "correlation"
    if path.startswith("/api"):
        return "web"
    if path.startswith("/ws"):
        return "realtime"
    return "page"


def _flush_sync(rows: list[list]) -> None:
    if rows:
        get_ch().insert(AUDIT_TABLE, data=rows, column_names=COLUMNS)


async def _push(row: list) -> None:
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
            await asyncio.to_thread(_flush_sync, rows)


async def flush_loop(interval: float = FLUSH_INTERVAL) -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            await flush_now()
        except Exception:
            pass


def ensure_audit_table() -> None:
    try:
        get_ch().query(f"SELECT 1 FROM {AUDIT_TABLE} LIMIT 1")
    except Exception as e:
        print(f"[AUDIT] table indisponible: {e}", flush=True)


async def _user_ctx(uid: str) -> tuple[str, str]:
    r = get_redis()
    try:
        cached = await r.get(f"audit:uctx:{uid}")
        if cached:
            d = json.loads(cached)
            return d.get("email", ""), d.get("plan", "free")
    except Exception:
        pass

    user = None
    try:
        user = await run_in_threadpool(users_repo.get_by_id, uid)
    except Exception:
        user = None

    email = (user or {}).get("email", "")
    plan = (user or {}).get("plan", "free")
    try:
        await r.setex(f"audit:uctx:{uid}", 300, json.dumps({"email": email, "plan": plan}))
    except Exception:
        pass
    return email, plan


async def _resolve_actor(request: Request) -> dict:
    ip = client_ip(request)
    ua = request.headers.get("user-agent", "")

    key_id = getattr(request.state, "key_id", None)
    if key_id:
        return {"type": "api", "id": str(key_id),
                "label": getattr(request.state, "key_label", "") or "Cle API",
                "plan": getattr(request.state, "key_plan", ""), "session_ref": ""}

    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        h = hashlib.sha256(auth[7:].strip().encode()).hexdigest()
        rec = None
        try:
            cached = await get_redis().get(f"apikey:{h}")
            rec = json.loads(cached) if cached else None
        except Exception:
            rec = None
        if rec:
            return {"type": "api", "id": str(rec.get("key_id", h[:16])),
                    "label": f"{rec.get('label', '')} / {rec.get('owner_email', '')}".strip(" /"),
                    "plan": rec.get("plan", ""), "session_ref": ""}
        return {"type": "api", "id": h[:16], "label": "Cle inconnue",
                "plan": "", "session_ref": ""}

    admin_cookie = request.cookies.get("admin_session")
    admin_header = request.headers.get("x-admin-token")
    if admin_cookie or admin_header:
        return {"type": "admin", "id": "admin", "label": "Administrateur",
                "plan": "root",
                "session_ref": _sha16(admin_cookie or admin_header or "")}

    session_id = request.headers.get("x-auth-session") or request.cookies.get("auth_session")
    if session_id:
        uid = None
        try:
            raw = await get_redis().get(f"auth_session:{session_id}")
            if raw:
                uid = raw.decode() if isinstance(raw, bytes) else str(raw)
        except Exception:
            uid = None
        ref = _sha16(str(session_id))
        if uid:
            email, plan = await _user_ctx(uid)
            return {"type": "user", "id": uid, "label": email or uid[:8],
                    "plan": plan, "session_ref": ref}
        return {"type": "user", "id": f"anon_{ref}", "label": "session expiree",
                "plan": "", "session_ref": ref}

    if BOT_RE.search(ua):
        return {"type": "bot", "id": ip, "label": ua[:48], "plan": "", "session_ref": ""}

    return {"type": "guest", "id": ip, "label": "Visiteur", "plan": "guest",
            "session_ref": _sha16(ua + ip)}


async def _emit(request: Request, request_id: str, path: str,
                status: int, latency: int, err: str) -> None:
    ip = client_ip(request)
    ua = _clip(request.headers.get("user-agent"), MAX_UA)
    actor = await _resolve_actor(request)
    is_user = actor["type"] == "user"

    key_id = getattr(request.state, "key_id", None)
    if key_id and path.startswith("/v1/"):
        full = path + (f"?{request.url.query}" if request.url.query else "")
        try:
            await usage_repo.add_usage(key_id, full, status, latency, ip)
        except Exception:
            pass

    meta = dict(getattr(request.state, "audit_meta", {}) or {})
    if actor.get("plan"):
        meta.setdefault("plan", actor["plan"])
    quota = getattr(request.state, "quota_headers", None)
    if quota:
        meta["quota"] = quota
    if request.url.query and any(s in path for s in ("/search", "/correlations")):
        meta.setdefault("criteria", dict(request.query_params))

    route = ""
    r = request.scope.get("route")
    if r is not None:
        route = getattr(r, "path", "") or ""

    full_path = path + (f"?{request.url.query}" if request.url.query else "")

    await _push([
        _now(),
        actor["type"],
        _clip(actor.get("id"), 120),
        _clip(actor.get("label"), 160),
        _clip(actor.get("session_ref"), 32),
        ip,
        _clip(actor.get("id") if is_user else "guest", 120),
        _clip(actor.get("label") if is_user else "anonymous", 160),
        _clip(full_path, MAX_ENDPOINT),
        _clip(path, MAX_PATH),
        route,
        request.method,
        _clip(str(request.url.query), MAX_Q),
        int(status),
        float(latency),
        int(latency),
        ua,
        _sha16(ua) if ua else "",
        _clip(request.headers.get("referer"), 300),
        request_id,
        _clip(err or getattr(request.state, "audit_error", ""), MAX_ERR),
        getattr(request.state, "audit_tag", None) or _tag_for(path),
        json.dumps(meta, ensure_ascii=False, default=str)[:2000],
    ])


SKIP_PREFIXES = ("/static/", "/favicon.ico", "/admin/api/logs/stream")


async def audit_middleware(request: Request, call_next):
    if _is_excluded(request.url.path):
        return await call_next(request)
    path = request.url.path
    if path.startswith(SKIP_PREFIXES):
        return await call_next(request)

    start = time.perf_counter()
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    request.state.request_id = request_id

    exc_caught, err, status = None, "", 200
    try:
        try:
            from app.core import access
            await access.check(request)
            response = await call_next(request)
        except HTTPException as _exc:
            request.state.audit_error = _exc.detail
            response = JSONResponse({"detail": _exc.detail}, status_code=_exc.status_code)
        status = response.status_code
    except Exception as e:
        exc_caught = e
        status = 500
        err = f"{type(e).__name__}: {e}"

    latency = int((time.perf_counter() - start) * 1000)
    try:
        await _emit(request, request_id, path, status, latency, err)
    except Exception as e:
        print(f"[AUDIT] emit KO: {e}", flush=True)

    if exc_caught is not None:
        raise exc_caught

    response.headers["X-Request-ID"] = request_id
    for k, v in (getattr(request.state, "quota_headers", None) or {}).items():
        response.headers[k] = v
    return response


async def resolve_actor(request: Request) -> dict:
    """Alias public : identifie l'acteur (guest/user/api/admin/bot) d'une requete."""
    return await _resolve_actor(request)


EXCLUDE_DEFAULT = "/api/config,/api/track/click,/api/pricing/detect,/health,/healthz,/favicon.ico,/robots.txt,/metrics,/static/"


def _is_excluded(path: str) -> bool:
    try:
        from app.core import pricing
        raw = pricing.setting("audit_exclude_paths", EXCLUDE_DEFAULT)
    except Exception:
        raw = EXCLUDE_DEFAULT
    for part in str(raw or "").split(","):
        pfx = part.strip()
        if pfx and (path == pfx or path.startswith(pfx)):
            return True
    return False
