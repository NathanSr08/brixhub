import hashlib
import secrets
from fastapi import HTTPException

# Fournisseurs officiels autorisés
ALLOWED_DOMAINS = {
    "gmail.com",
    "hotmail.com",
    "hotmail.fr",
    "yahoo.com",
    "yahoo.fr",
    "outlook.com",
    "outlook.fr",
    "icloud.com"
}

def validate_official_email(email: str) -> str:
    cleaned = email.strip().lower()
    if "@" not in cleaned:
        raise HTTPException(status_code=400, detail="Format d'adresse email invalide.")
    
    parts = cleaned.split("@")
    if len(parts) != 2 or not parts[0]:
        raise HTTPException(status_code=400, detail="Format d'adresse email invalide.")
        
    domain = parts[1]
    if domain not in ALLOWED_DOMAINS:
        raise HTTPException(
            status_code=400,
            detail=f"Seuls les fournisseurs officiels sont acceptés (@gmail, @hotmail, @yahoo, @outlook, @icloud)."
        )
    return cleaned

def hash_password(password: str) -> str:
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Le mot de passe doit comporter au moins 6 caractères.")
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${key.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt, key_hex = hashed_password.split("$", 1)
        check_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return secrets.compare_digest(check_key.hex(), key_hex)
    except Exception:
        return False

def generate_session_token() -> str:
    return secrets.token_urlsafe(32)
