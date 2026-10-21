import json
import hashlib
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel
from app.core.auth_service import (
    validate_official_email, hash_password, verify_password, generate_session_token
)
from app.core.quotas import check_search_quota
from app.db.clickhouse import get_redis
from app.repositories import users_repo, keys_repo

router = APIRouter(prefix="/auth", tags=["auth"])

class AuthSignup(BaseModel):
    email: str
    password: str

class AuthSignin(BaseModel):
    email: str
    password: str

class LinkKeyPayload(BaseModel):
    api_key: str

class ForgotPasswordPayload(BaseModel):
    email: str

class ResetPasswordPayload(BaseModel):
    token: str
    new_password: str

@router.post("/signup")
async def signup(payload: AuthSignup):
    email = validate_official_email(payload.email)
    existing = users_repo.get_by_email(email)
    if existing:
        raise HTTPException(status_code=400, detail="Cet email possède déjà un compte.")

    pwd_hash = hash_password(payload.password)
    user_id = users_repo.create_user(email=email, password_hash=pwd_hash)
    return {"status": "ok", "message": "Compte créé ! Vous bénéficiez de 5 requêtes par jour."}

@router.post("/signin")
async def signin(payload: AuthSignin, response: Response):
    email = payload.email.strip().lower()
    user = users_repo.get_by_email(email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect.")
    
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Ce compte est désactivé.")

    token = generate_session_token()
    r = get_redis()
    await r.setex(f"auth_session:{token}", 86400 * 14, user["user_id"])

    response.set_cookie(
        key="auth_session",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=86400 * 14
    )
    return {"status": "ok", "token": token, "user": {"email": user["email"], "plan": user["plan"]}}

@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("auth_session")
    if token:
        r = get_redis()
        await r.delete(f"auth_session:{token}")
    response.delete_cookie("auth_session", path="/")
    return {"status": "ok"}

@router.get("/me")
async def get_me(request: Request):
    token = request.headers.get("x-auth-session") or request.cookies.get("auth_session")
    if not token:
        return {"logged_in": False, "plan": "guest", "limit": 2}
    
    r = get_redis()
    user_id = await r.get(f"auth_session:{token}")
    if not user_id:
        return {"logged_in": False, "plan": "guest", "limit": 2}
    
    user = users_repo.get_by_id(user_id)
    if not user:
        return {"logged_in": False, "plan": "guest", "limit": 2}

    return {
        "logged_in": True,
        "email": user["email"],
        "plan": user["plan"],
        "has_api_key": bool(user["api_key_id"])
    }

@router.post("/link-key")
async def link_key(payload: LinkKeyPayload, request: Request):
    token = request.cookies.get("auth_session")
    if not token:
        raise HTTPException(status_code=401, detail="Connectez-vous pour lier une clé API.")
    
    r = get_redis()
    user_id = await r.get(f"auth_session:{token}")
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expirée.")

    raw_key = payload.api_key.strip()
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    rec = keys_repo.get_by_hash(key_hash)
    if not rec or not rec.get("is_active"):
        raise HTTPException(status_code=400, detail="Clé API introuvable ou révoquée.")

    plan = rec.get("plan", "pro")
    users_repo.link_api_key(user_id, rec["key_id"], plan)
    return {"status": "ok", "message": f"Clé liée ! Votre compte bénéficie maintenant du plan {plan.upper()} en illimité."}

@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordPayload):
    email = payload.email.strip().lower()
    user = users_repo.get_by_email(email)
    if not user:
        return {"status": "ok", "message": "Si l'email existe, un lien de réinitialisation a été généré."}

    token = generate_session_token()
    r = get_redis()
    await r.setex(f"pwd_reset:{token}", 1800, user["user_id"])
    
    reset_link = f"/reset-password?token={token}"
    return {
        "status": "ok", 
        "message": "Lien de réinitialisation généré avec succès.",
        "reset_link": reset_link
    }

@router.post("/reset-password")
async def reset_password(payload: ResetPasswordPayload):
    r = get_redis()
    user_id = await r.get(f"pwd_reset:{payload.token}")
    if not user_id:
        raise HTTPException(status_code=400, detail="Ce lien de réinitialisation est invalide ou expiré.")

    new_hash = hash_password(payload.new_password)
    users_repo.update_password(user_id, new_hash)
    await r.delete(f"pwd_reset:{payload.token}")
    return {"status": "ok", "message": "Mot de passe mis à jour avec succès. Vous pouvez vous connecter."}
