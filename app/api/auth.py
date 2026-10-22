import secrets

def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"

from app.services.email_service import send_otp_email_sync
from fastapi import BackgroundTasks
import json
import hashlib
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel
from app.core.auth_service import (
    validate_official_email, hash_password, verify_password, generate_session_token
)
from app.core.quotas import check_search_quota
from app.core import pricing
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
        return {"logged_in": False, "plan": "guest", "limit": pricing.guest_daily_quota()}
    
    r = get_redis()
    user_id = await r.get(f"auth_session:{token}")
    if not user_id:
        return {"logged_in": False, "plan": "guest", "limit": pricing.guest_daily_quota()}
    
    user = users_repo.get_by_id(user_id)
    if not user:
        return {"logged_in": False, "plan": "guest", "limit": pricing.guest_daily_quota()}

    return {
        "logged_in": True,
        "email": user["email"],
        "plan": user["plan"],
        "has_api_key": bool(user["api_key_id"]),
        "limit": pricing.plan_web_quota(user["plan"]),
        "unlimited": pricing.plan_web_unlimited(user["plan"]),
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


class SendOtpResetPayload(BaseModel):
    email: str

class VerifyOtpResetPayload(BaseModel):
    email: str
    otp: str
    new_password: str

@router.post("/forgot-password")
@router.post("/forgot-password/send-otp")
async def forgot_send_otp(payload: SendOtpResetPayload, background: BackgroundTasks):
    email = payload.email.strip().lower()
    user = users_repo.get_by_email(email)

    # Réponse générique pour bloquer l'énumération des comptes
    generic_msg = {"status": "ok", "message": "Si cette adresse est enregistrée, un code de validation vient de lui être envoyé."}

    if not user:
        return generic_msg

    otp = _generate_otp()
    r = get_redis()
    await r.setex(f"otp_reset:{email}", 600, otp)

    # Envoi strict par email en tâche de fond (aucun code n'est renvoyé au navigateur)
    background.add_task(
        send_otp_email_sync,
        to_email=email,
        code=otp,
        title="Réinitialisation de votre mot de passe",
        subtitle="Entrez ce code sur la plateforme pour définir votre nouveau mot de passe."
    )

    print(f"[OTP RESET SÉCURISÉ] Code envoyé par email à {email}", flush=True)
    return generic_msg

@router.post("/forgot-password/verify-otp")
async def forgot_verify_otp(payload: VerifyOtpResetPayload):
    email = payload.email.strip().lower()
    r = get_redis()
    raw = await r.get(f"otp_reset:{email}")
    if not raw:
        raise HTTPException(status_code=400, detail="Code expiré ou aucune demande en cours.")

    stored_otp = raw.decode() if isinstance(raw, bytes) else str(raw)
    if stored_otp != payload.otp.strip():
        raise HTTPException(status_code=400, detail="Code OTP incorrect.")

    user = users_repo.get_by_email(email)
    if not user:
        raise HTTPException(status_code=400, detail="Compte introuvable.")

    new_hash = hash_password(payload.new_password)
    users_repo.update_password(user["user_id"], new_hash)
    await r.delete(f"otp_reset:{email}")

    return {"status": "ok", "message": "Votre mot de passe a été réinitialisé avec succès."}


# ==========================================
# ROUTES OTP INSCRIPTION
# ==========================================
class SendOtpSignupPayload(BaseModel):
    email: str
    password: str

class VerifyOtpSignupPayload(BaseModel):
    email: str
    otp: str




# === START SIGNUP OTP ===
class SendOtpSignupPayload(BaseModel):
    email: str
    password: str

class VerifyOtpSignupPayload(BaseModel):
    email: str
    otp: str

@router.post("/signup/send-otp")
async def signup_send_otp(payload: SendOtpSignupPayload, background: BackgroundTasks):
    try:
        email = validate_official_email(payload.email)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    existing = users_repo.get_by_email(email)
    if existing:
        raise HTTPException(status_code=400, detail="Cette adresse email possède déjà un compte.")

    otp = _generate_otp()
    pwd_hash = hash_password(payload.password)
    r = get_redis()

    cache_data = {"otp": otp, "password_hash": pwd_hash}
    await r.setex(f"otp_signup:{email}", 600, json.dumps(cache_data))

    background.add_task(
        send_otp_email_sync,
        to_email=email,
        code=otp,
        title="Création de votre compte BrixHub",
        subtitle="Confirmez votre adresse email pour débloquer vos 5 requêtes quotidiennes."
    )

    print(f"[OTP SIGNUP] Code envoyé à {email}", flush=True)
    return {"status": "ok", "message": "Code de confirmation envoyé par email."}

@router.post("/signup/verify-otp")
async def signup_verify_otp(payload: VerifyOtpSignupPayload):
    email = payload.email.strip().lower()
    r = get_redis()
    raw = await r.get(f"otp_signup:{email}")
    if not raw:
        raise HTTPException(status_code=400, detail="Code expiré ou aucune inscription en cours.")

    stored = json.loads(raw if isinstance(raw, str) else raw.decode())
    if stored.get("otp") != payload.otp.strip():
        raise HTTPException(status_code=400, detail="Code OTP incorrect.")

    users_repo.create_user(email=email, password_hash=stored["password_hash"])
    await r.delete(f"otp_signup:{email}")

    return {"status": "ok", "message": "Compte créé et validé avec succès !"}
# === END SIGNUP OTP ===
