from fastapi import Header, HTTPException, Request
from app.core.security import hash_key
from app.core.config import get_settings
from app.core.rate_limit import QuotaLimiter
from app.services.key_service import KeyService
from app.db.clickhouse import get_redis

async def require_api_key(request: Request, authorization: str | None = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Header Authorization requis")
    
    raw = authorization.removeprefix("Bearer ").strip()
    rec = await KeyService().resolve(hash_key(raw))
    if not rec:
        raise HTTPException(status_code=401, detail="Cle API invalide")
    
    val = rec.get("is_active")
    if val in (0, "0", False, None) or str(val).lower() in ("false", "0"):
        raise HTTPException(status_code=401, detail="Cle API revoquee")

    quota = get_settings().plans.get(rec.get("plan", "free"), 500)
    info = await QuotaLimiter(get_redis()).consume(rec["key_id"], quota)
    request.state.key_id = rec["key_id"]
    request.state.quota_headers = {
        "X-RateLimit-Limit": str(info["limit"]),
        "X-RateLimit-Remaining": str(info["remaining"]),
    }
    return rec
