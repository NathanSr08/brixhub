import json
from datetime import datetime
from fastapi import Request, HTTPException
from app.core import pricing
from app.core.rate_limit import enforce_rps
from app.db.clickhouse import get_redis
from app.repositories import users_repo

async def check_search_quota(request: Request) -> dict:
    r = get_redis()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    # 1. Récupération de l utilisateur connecté via le cookie auth_session
    session_id = request.headers.get("x-auth-session") or request.cookies.get("auth_session")
    user = None
    if session_id:
        raw_uid = await r.get(f"auth_session:{session_id}")
        if raw_uid:
            user_id = raw_uid.decode() if isinstance(raw_uid, bytes) else str(raw_uid)
            user = users_repo.get_by_id(user_id)

    # Attacher l utilisateur à request.state pour les logs
    request.state.user = user

    # CAS A : UTILISATEUR CONNECTÉ
    if user:
        # Si compte banni
        if user.get("is_active") == 0:
            raise HTTPException(status_code=403, detail="Votre compte a été suspendu.")

        plan = user.get("plan", "free")
        
        # Plan payant lié -> Accès illimité
        if pricing.resolve_web_access(user)[0]:
            return {"user": user, "quota": "unlimited", "remaining": 999999}

        # Compte gratuit -> 5 requêtes / jour strict
        await enforce_rps(r, "web", str(user["user_id"]), pricing.setting_int("global_rps_user", 5))
        rkey = f"quota:user:{user['user_id']}:{today}"
        used = await r.incr(rkey)
        if used == 1:
            await r.expire(rkey, 86400)

        limit = pricing.resolve_web_access(user)[1]
        if used > limit:
            request.state.audit_error = "QUOTA_EXCEEDED_USER"
            request.state.audit_error = "QUOTA_EXCEEDED_GUEST"
            raise HTTPException(
                status_code=429,
                detail=f"Limite atteinte ({used - 1}/{limit} requêtes aujourd'hui). Liez une clé API pour débloquer l'illimité."
            )
        return {"user": user, "quota": limit, "remaining": max(0, limit - used)}

    # CAS B : VISITEUR NON CONNECTÉ (IP)
    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    
    await enforce_rps(r, "web", client_ip, pricing.setting_int("global_rps_guest", 3))
    rkey = f"quota:ip:{client_ip}:{today}"
    used = await r.incr(rkey)
    if used == 1:
        await r.expire(rkey, 86400)

    limit = pricing.guest_daily_quota()
    if used > limit:
        raise HTTPException(
            status_code=429,
            detail=f"Limite visiteur atteinte ({used - 1}/{limit} requêtes/jour par IP). Connectez-vous pour obtenir 5 requêtes gratuites."
        )
    return {"user": None, "quota": limit, "remaining": max(0, limit - used)}
