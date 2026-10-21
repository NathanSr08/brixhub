from datetime import datetime
from app.db.clickhouse import get_redis
from starlette.concurrency import run_in_threadpool
import hmac
from pathlib import Path
from fastapi import APIRouter, Request, Response, HTTPException, Depends, Header
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from app.core.config import get_settings
from app.services.key_service import KeyService

router = APIRouter(prefix="/admin", tags=["admin"])
key_svc = KeyService()

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static" if (BASE_DIR / "static").exists() else BASE_DIR.parent / "static"

class LoginPayload(BaseModel):
    token: str

class KeyCreateAdmin(BaseModel):
    label: str
    owner_email: str
    plan: str

class KeyUpdatePlan(BaseModel):
    plan: str

def check_admin(request: Request) -> bool:
    settings = get_settings()
    expected = settings.admin_token
    if not expected:
        return False
    # 1. Cookie
    cookie_token = request.cookies.get("admin_session")
    if cookie_token and hmac.compare_digest(cookie_token, expected):
        return True
    # 2. Header x-admin-token ou Authorization Bearer
    header_token = request.headers.get("x-admin-token")
    if header_token and hmac.compare_digest(header_token, expected):
        return True
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        bearer_token = auth[7:].strip()
        if hmac.compare_digest(bearer_token, expected):
            return True
    return False

def require_admin_auth(request: Request):
    if not check_admin(request):
        raise HTTPException(status_code=401, detail="Non autorisé")

@router.get("")
async def serve_admin_dashboard(request: Request):
    if not check_admin(request):
        return RedirectResponse(url="/admin/login")
    return FileResponse(str(STATIC_DIR / "admin.html"))

@router.get("/login")
async def serve_admin_login(request: Request):
    if check_admin(request):
        return RedirectResponse(url="/admin")
    return FileResponse(str(STATIC_DIR / "admin-login.html"))

@router.post("/api/login")
async def api_login(payload: LoginPayload, response: Response):
    settings = get_settings()
    if not hmac.compare_digest(payload.token.strip(), settings.admin_token):
        raise HTTPException(status_code=403, detail="Clé secrète invalide")
    response = JSONResponse({"status": "ok"})
    response.set_cookie(
        key="admin_session",
        value=settings.admin_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=86400 * 7
    )
    return response

@router.post("/api/logout")
async def api_logout(response: Response):
    res = JSONResponse({"status": "logged_out"})
    res.delete_cookie("admin_session")
    return res

@router.get("/api/keys", dependencies=[Depends(require_admin_auth)])
async def api_list_keys():
    return await key_svc.list_all()

@router.post("/api/keys", dependencies=[Depends(require_admin_auth)])
async def api_create_key(payload: KeyCreateAdmin):
    return await key_svc.create(payload.label, payload.owner_email, payload.plan)

@router.patch("/api/keys/{key_id}/plan", dependencies=[Depends(require_admin_auth)])
async def api_update_plan(key_id: str, payload: KeyUpdatePlan):
    ok = await key_svc.update_plan(key_id, payload.plan)
    if not ok:
        raise HTTPException(status_code=400, detail="Plan invalide ou clé introuvable")
    return {"status": "updated", "key_id": key_id, "plan": payload.plan}

@router.post("/api/keys/{key_id}/reactivate", dependencies=[Depends(require_admin_auth)])
async def api_reactivate_key(key_id: str):
    ok = await key_svc.reactivate(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Clé introuvable")
    return {"status": "reactivated", "key_id": key_id}

@router.delete("/api/keys/{key_id}", dependencies=[Depends(require_admin_auth)])
async def api_revoke_key(key_id: str):
    ok = await key_svc.revoke(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Clé introuvable")
    return {"status": "revoked", "key_id": key_id}


@router.get("/api/keys/{key_id}/logs", dependencies=[Depends(require_admin_auth)])
async def api_get_key_logs(key_id: str, limit: int = 100):
    return await key_svc.get_logs(key_id, limit=limit)

@router.post("/api/keys/{key_id}/reset-quota", dependencies=[Depends(require_admin_auth)])
async def api_reset_key_quota(key_id: str):
    await key_svc.reset_daily_quota(key_id)
    return {"status": "reset", "key_id": key_id}


from app.repositories import users_repo
from app.core.auth_service import hash_password

class AdminUserPasswordReset(BaseModel):
    new_password: str

class AdminUserLinkKey(BaseModel):
    key_id: str
    plan: str = "pro"

class AdminUserPlan(BaseModel):
    plan: str

@router.get("/api/users", dependencies=[Depends(require_admin_auth)])
async def api_get_users():
    users = await run_in_threadpool(users_repo.list_all_users)
    r = get_redis()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    for u in users:
        uid = u["user_id"]
        used = 0
        try:
            val = await r.get(f"quota:user:{uid}:{today}")
            used = int(val) if val else 0
        except Exception:
            used = 0
        u["used_today"] = used
        u["is_unlimited"] = u["plan"] in ["starter", "pro", "enterprise", "paid"]
    return users

@router.patch("/api/users/{user_id}/status", dependencies=[Depends(require_admin_auth)])
async def api_toggle_user_status(user_id: str):
    u = await run_in_threadpool(users_repo.get_by_id, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    new_status = 0 if u["is_active"] == 1 else 1
    await run_in_threadpool(users_repo.toggle_user_status, user_id, new_status)
    # Si banni, purger ses sessions Redis actives immédiatement
    if new_status == 0:
        r = get_redis()
        # Supprimer sessions associées si présentes
        pass
    return {"status": "ok", "is_active": new_status}

@router.post("/api/users/{user_id}/reset-password", dependencies=[Depends(require_admin_auth)])
async def api_admin_reset_password(user_id: str, payload: AdminUserPasswordReset):
    new_hash = hash_password(payload.new_password)
    await run_in_threadpool(users_repo.update_password, user_id, new_hash)
    return {"status": "ok", "message": "Mot de passe mis à jour"}

@router.post("/api/users/{user_id}/link-key", dependencies=[Depends(require_admin_auth)])
async def api_admin_link_key(user_id: str, payload: AdminUserLinkKey):
    await run_in_threadpool(users_repo.link_api_key, user_id, payload.key_id, payload.plan)
    return {"status": "ok", "message": "Clé liée et plan mis à jour"}

@router.patch("/api/users/{user_id}/plan", dependencies=[Depends(require_admin_auth)])
async def api_admin_update_plan(user_id: str, payload: AdminUserPlan):
    await run_in_threadpool(users_repo.update_user_plan, user_id, payload.plan)
    return {"status": "ok", "plan": payload.plan}

@router.post("/api/users/{user_id}/reset-quota", dependencies=[Depends(require_admin_auth)])
async def api_admin_reset_user_quota(user_id: str):
    r = get_redis()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    await r.delete(f"quota:user:{user_id}:{today}")
    return {"status": "ok"}

@router.get("/api/users/{user_id}/search-logs", dependencies=[Depends(require_admin_auth)])
async def api_admin_user_logs(user_id: str, limit: int = 100):
    u = await run_in_threadpool(users_repo.get_by_id, user_id)
    key_id = u.get("api_key_id") if u else None
    return await run_in_threadpool(users_repo.get_user_search_logs, user_id, key_id, limit)
