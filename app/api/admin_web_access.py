"""Pilotage admin de l'acces web : illimite / quota par utilisateur."""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.api.admin import require_admin_auth
from app.core import pricing
from app.db.clickhouse import get_redis
from app.repositories import audit_repo, users_repo, web_access_repo

router = APIRouter(prefix="/admin", tags=["admin-web-access"])


class OverridePayload(BaseModel):
    web_unlimited: int | None = None
    web_daily_quota: int | None = None   # -1 => null (suit le plan)
    api_key_unlimited: int | None = None  # -1 => null (suit le reglage global)
    note: str | None = None


class GlobalPayload(BaseModel):
    enabled: int = 1


def _ip(request: Request) -> str:
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "")


async def _used_today(user_id: str) -> int:
    try:
        r = get_redis()
        return int(await r.get("quota:user:%s:%s" % (user_id, datetime.utcnow().strftime("%Y-%m-%d"))) or 0)
    except Exception:
        return 0


@router.get("/api/web-users", dependencies=[Depends(require_admin_auth)])
async def list_web_users(q: str = "", limit: int = 200, offset: int = 0):
    users = await run_in_threadpool(users_repo.list_all_users)
    overrides = await run_in_threadpool(web_access_repo.list_overrides)
    items = []
    needle = (q or "").strip().lower()
    for u in users:
        uid = str(u.get("user_id") or "")
        email = (u.get("email") or "")
        if needle and needle not in email.lower() and needle not in uid.lower():
            continue
        ov = overrides.get(uid, {})
        unl, quota = pricing.resolve_web_access(u)
        items.append({
            "user_id": uid,
            "email": email,
            "plan": u.get("plan", "free"),
            "is_active": int(u.get("is_active", 1) or 0),
            "has_api_key": bool(u.get("api_key_id")),
            "api_key_id": u.get("api_key_id") or "",
            "used_today": await _used_today(uid),
            "unlimited": unl,
            "effective_quota": quota,
            "override": {
                "web_unlimited": int(ov.get("web_unlimited") or 0),
                "web_daily_quota": ov.get("web_daily_quota"),
                "api_key_unlimited": ov.get("api_key_unlimited"),
                "note": ov.get("note") or "",
            },
        })
    items.sort(key=lambda x: x["email"].lower())
    return {
        "total": len(items),
        "items": items[offset:offset + limit],
        "global_api_key_unlimited": pricing.api_key_grants_web_unlimited(),
    }


@router.patch("/api/web-access/global", dependencies=[Depends(require_admin_auth)])
async def set_global(payload: GlobalPayload, request: Request):
    from app.repositories import pricing_repo
    await run_in_threadpool(
        pricing_repo.set_settings, {"api_plan_grants_web_unlimited": "1" if payload.enabled else "0"})
    await pricing.invalidate()
    audit_repo.log_admin_action("admin", "web_access_global", "settings",
                                str(payload.enabled), _ip(request))
    return {"status": "ok", "enabled": bool(payload.enabled)}


@router.patch("/api/web-users/{user_id}", dependencies=[Depends(require_admin_auth)])
async def set_web_user(user_id: str, payload: OverridePayload, request: Request):
    u = await run_in_threadpool(users_repo.get_by_id, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")

    fields = {}
    if payload.web_unlimited is not None:
        fields["web_unlimited"] = int(payload.web_unlimited)
    if payload.web_daily_quota is not None:
        fields["web_daily_quota"] = None if payload.web_daily_quota == -1 else int(payload.web_daily_quota)
    if payload.api_key_unlimited is not None:
        fields["api_key_unlimited"] = None if payload.api_key_unlimited == -1 else int(payload.api_key_unlimited)
    if payload.note is not None:
        fields["note"] = payload.note

    await run_in_threadpool(web_access_repo.upsert, user_id, **fields)
    await pricing.invalidate()
    audit_repo.log_admin_action("admin", "web_access_update", "user", user_id,
                                _ip(request), json.dumps(fields, default=str)[:500])
    unl, quota = pricing.resolve_web_access(u)
    return {"status": "ok", "unlimited": unl, "quota": quota}


@router.post("/api/web-users/{user_id}/clear", dependencies=[Depends(require_admin_auth)])
async def clear_web_user(user_id: str, request: Request):
    await run_in_threadpool(web_access_repo.clear_override, user_id)
    await pricing.invalidate()
    audit_repo.log_admin_action("admin", "web_access_clear", "user", user_id, _ip(request))
    return {"status": "ok"}
