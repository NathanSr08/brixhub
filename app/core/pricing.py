"""Acces cache aux plans, tarifs et reglages globaux (pilotables depuis l'admin).

Cache process 10 s + invalidation immediate a chaque ecriture admin.
"""
from __future__ import annotations

import json
import time

from app.db.clickhouse import get_redis

CACHE_TTL = 10

_cache = {"plans": None, "deletion": None, "settings": None, "overrides": None, "ts": 0.0}


def invalidate_local() -> None:
    _cache["ts"] = 0.0
    _cache["plans"] = None
    _cache["deletion"] = None
    _cache["settings"] = None
    _cache["overrides"] = None


async def invalidate() -> None:
    invalidate_local()
    try:
        r = get_redis()
        keys = await r.keys("cfg:*")
        if keys:
            await r.delete(*keys)
    except Exception:
        pass


def _refresh() -> None:
    from app.repositories import pricing_repo
    _cache["plans"] = pricing_repo.list_plans()
    _cache["deletion"] = pricing_repo.list_deletion_plans()
    _cache["settings"] = pricing_repo.get_settings()
    try:
        from app.repositories import web_access_repo
        _cache["overrides"] = web_access_repo.list_overrides()
    except Exception:
        _cache["overrides"] = {}
    _cache["ts"] = time.monotonic()


def _ensure() -> None:
    if (_cache["plans"] is None or _cache["settings"] is None
            or _cache.get("overrides") is None
            or (time.monotonic() - _cache["ts"]) > CACHE_TTL):
        try:
            _refresh()
        except Exception:
            if _cache["settings"] is None:
                from app.repositories import pricing_repo
                _cache["settings"] = dict(pricing_repo.DEFAULT_SETTINGS)
                _cache["plans"] = []
                _cache["deletion"] = []
                _cache["overrides"] = {}


# ------------------------------- lectures ------------------------------- #
def get_settings() -> dict:
    _ensure()
    return dict(_cache["settings"] or {})


def get_plans(public_only: bool = False) -> list[dict]:
    _ensure()
    plans = [p for p in (_cache["plans"] or []) if not p.get("is_deleted")]
    return [p for p in plans if p.get("is_public")] if public_only else plans


def get_deletion_plans(public_only: bool = False) -> list[dict]:
    _ensure()
    plans = [p for p in (_cache["deletion"] or []) if not p.get("is_deleted")]
    return [p for p in plans if p.get("is_active")] if public_only else plans


def get_plan(plan_id: str) -> dict | None:
    for p in get_plans():
        if p["plan_id"] == plan_id:
            return p
    return None


def setting(key: str, default=None):
    return get_settings().get(key, default)


def setting_int(key: str, default: int = 0) -> int:
    try:
        return int(str(setting(key, default)).strip())
    except Exception:
        return default


def setting_bool(key: str, default: bool = False) -> bool:
    return str(setting(key, "1" if default else "0")).strip().lower() in ("1", "true", "yes", "on")


# ------------------------------- quotas ------------------------------- #
def guest_daily_quota() -> int:
    return max(0, setting_int("guest_daily_quota", 2))


def user_daily_quota() -> int:
    return max(0, setting_int("user_daily_quota", 5))


def plan_daily_quota(plan_id: str) -> int:
    p = get_plan(plan_id) or {}
    q = int(p.get("daily_quota") or 0)
    return q if q > 0 else setting_int("default_plan_daily_quota", 500)


def plan_rps(plan_id: str) -> int:
    p = get_plan(plan_id) or {}
    r = int(p.get("rate_limit_rps") or 0)
    return r if r > 0 else setting_int("default_plan_rps", 2)


def plan_web_unlimited(plan_id: str) -> bool:
    p = get_plan(plan_id)
    if p:
        return bool(p.get("web_unlimited")) or int(p.get("web_daily_quota") or 0) >= 999999
    return False


def plan_web_quota(plan_id: str) -> int:
    p = get_plan(plan_id) or {}
    q = int(p.get("web_daily_quota") or 0)
    return q if q > 0 else user_daily_quota()


def ui_rules() -> list:
    try:
        return json.loads(setting("ui_rules", "[]") or "[]")
    except Exception:
        return []


def public_config() -> dict:
    s = get_settings()
    return {
        "guest_daily_quota": guest_daily_quota(),
        "user_daily_quota": user_daily_quota(),
        "global_rps_guest": setting_int("global_rps_guest", 3),
        "global_rps_user": setting_int("global_rps_user", 5),
        "registration_open": setting_bool("registration_open", True),
        "maintenance_mode": setting_bool("maintenance_mode", False),
        "maintenance_text": s.get("maintenance_text", ""),
        "banner": {
            "enabled": setting_bool("banner_enabled", False),
            "type": s.get("banner_type", "info"),
            "text": s.get("banner_text", ""),
            "until": s.get("banner_until", ""),
        },
        "pricing_title": s.get("pricing_title", ""),
        "pricing_subtitle": s.get("pricing_subtitle", ""),
        "recommended_plan": s.get("recommended_plan", "pro"),
        "cta_url": s.get("cta_url", "/"),
        "cta_label": s.get("cta_label", "Prendre {plan} ({price})"),
        "contact_url": s.get("contact_url", "mailto:contact@brixhub.uned.live"),
        "contact_label": s.get("contact_label", "Contacter l'equipe"),
        "telegram_handle": s.get("telegram_handle", "leackfrench"),
        "price_format_eur": s.get("price_format_eur", "{value} EUR"),
        "price_format_usd": s.get("price_format_usd", "${value}"),
        "plans": get_plans(public_only=True),
        "deletion_plans": get_deletion_plans(public_only=True),
        "ui_rules": ui_rules(),
    }


# ------------------------- acces web par utilisateur ------------------------- #
def get_override(user_id: str) -> dict:
    _ensure()
    return (_cache.get("overrides") or {}).get(str(user_id), {})


def api_key_grants_web_unlimited() -> bool:
    return setting_bool("api_plan_grants_web_unlimited", True)


def resolve_web_access(user: dict) -> tuple:
    """(illimite, quota_journalier). Priorite : override illimite > cle API
    > quota specifique > plan. Un quota specifique a 0 vaut illimite."""
    ov = get_override(str(user.get("user_id") or ""))

    if int(ov.get("web_unlimited") or 0) == 1:
        return True, 999999

    has_key = bool(user.get("api_key_id"))
    allow = ov.get("api_key_unlimited")
    if allow is None:
        allow = api_key_grants_web_unlimited()
    if has_key and int(allow) == 1:
        return True, 999999

    q = ov.get("web_daily_quota")
    if q is not None:
        q = int(q)
        return (True, 999999) if (q <= 0 or q >= 999999) else (False, q)

    plan = user.get("plan", "free")
    if plan_web_unlimited(plan):
        return True, 999999
    return False, plan_web_quota(plan)
