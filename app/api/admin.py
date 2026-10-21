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
