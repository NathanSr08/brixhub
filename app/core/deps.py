from fastapi import Header, HTTPException, Request
from app.core.security import hash_key
from app.core.config import get_settings
from app.core.rate_limit import QuotaLimiter, enforce_rps
from app.core import pricing
from app.services.key_service import KeyService
from app.db.clickhouse import get_redis

async def require_api_key(request: Request, authorization: str | None = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        request.state.audit_error = "MISSING_KEY"
        raise HTTPException(status_code=401, detail="Header Authorization requis")
    
    raw = authorization.removeprefix("Bearer ").strip()
    rec = await KeyService().resolve(hash_key(raw))
    if not rec:
        request.state.audit_error = "BAD_KEY"
        raise HTTPException(status_code=401, detail="Cle API invalide")
    
    val = rec.get("is_active")
    if val in (0, "0", False, None) or str(val).lower() in ("false", "0"):
        request.state.audit_error = "REVOKED_KEY"
        raise HTTPException(status_code=401, detail="Cle API revoquee")

    plan = rec.get("plan", "free")
    quota = pricing.plan_daily_quota(plan)
    request.state.key_id = rec["key_id"]
    request.state.key_label = rec.get("label", "")
    request.state.key_plan = plan
    try:
        await enforce_rps(get_redis(), "api", rec["key_id"], pricing.plan_rps(plan))
    except HTTPException as exc:
        request.state.audit_error = "RPS_EXCEEDED"
        raise exc
    try:
        info = await QuotaLimiter(get_redis()).consume(rec["key_id"], quota)
    except HTTPException as exc:
        request.state.audit_error = "QUOTA_EXCEEDED"
        request.state.audit_meta = {"quota_limit": quota, "quota_used": quota}
        raise exc
    request.state.audit_meta = {"quota_limit": info["limit"], "quota_used": info["used"]}
    request.state.quota_headers = {
        "X-RateLimit-Limit": str(info["limit"]),
        "X-RateLimit-Remaining": str(info["remaining"]),
    }
    return rec
