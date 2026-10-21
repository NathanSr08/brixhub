import hashlib, secrets
from app.core.config import get_settings

def generate_key() -> tuple[str, str, str]:
    raw = f"{get_settings().key_prefix}{secrets.token_urlsafe(32)}"
    return raw, hash_key(raw), f"{raw[:14]}...{raw[-4:]}"

def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

def hash_api_key(raw: str) -> str:
    return hash_key(raw)
