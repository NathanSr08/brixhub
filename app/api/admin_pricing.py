import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.api.admin import require_admin_auth
from app.core import pricing
from app.repositories import audit_repo, pricing_repo

router = APIRouter(prefix="/admin", tags=["admin-pricing"])
public_router = APIRouter(prefix="/api", tags=["config"])


class PlanPayload(BaseModel):
    plan_id: str
    label: str = ""
    price_eur: float = 0
    price_usd: float = 0
    daily_quota: int = 0
    rate_limit_rps: int = 0
    web_unlimited: int = 0
    web_daily_quota: int = 0
    features: str = "[]"
    is_public: int = 1
    sort_order: int = 0
    is_deleted: int = 0
    ui_match: str = ""


class DeletionPlanPayload(BaseModel):
    plan_id: str
    label: str = ""
    price_eur: float = 0
    description: str = ""
    delay_hours: int = 24
    is_active: int = 1
    sort_order: int = 0
    is_deleted: int = 0
    ui_match: str = ""


class SettingsPayload(BaseModel):
    values: dict = {}


# ================================ PUBLIC ================================ #
@public_router.get("/config")
async def api_config():
    return await run_in_threadpool(pricing.public_config)


@public_router.get("/plans")
async def api_public_plans():
    return await run_in_threadpool(lambda: pricing.get_plans(public_only=True))


@public_router.get("/deletion-plans")
async def api_public_deletion_plans():
    return await run_in_threadpool(lambda: pricing.get_deletion_plans(public_only=True))


# ================================ PLANS API ================================ #
@router.get("/api/plans", dependencies=[Depends(require_admin_auth)])
async def admin_list_plans():
    return await run_in_threadpool(pricing_repo.list_plans)


@router.post("/api/plans", dependencies=[Depends(require_admin_auth)])
async def admin_create_plan(payload: PlanPayload, request: Request):
    existing = {p["plan_id"] for p in await run_in_threadpool(pricing_repo.list_plans)}
    if payload.plan_id in existing:
        raise HTTPException(status_code=400, detail="Ce plan_id existe deja")
    await run_in_threadpool(pricing_repo.upsert_plan, payload.model_dump())
    await pricing.invalidate()
    audit_repo.log_admin_action("admin", "plan_create", "plan", payload.plan_id,
                                _ip(request))
    return {"status": "ok", "plan_id": payload.plan_id}


@router.patch("/api/plans/{plan_id}", dependencies=[Depends(require_admin_auth)])
async def admin_update_plan(plan_id: str, payload: PlanPayload, request: Request):
    data = payload.model_dump()
    data["plan_id"] = plan_id
    await run_in_threadpool(pricing_repo.upsert_plan, data)
    await pricing.invalidate()
    audit_repo.log_admin_action("admin", "plan_update", "plan", plan_id, _ip(request))
    return {"status": "ok", "plan_id": plan_id}


@router.delete("/api/plans/{plan_id}", dependencies=[Depends(require_admin_auth)])
async def admin_delete_plan(plan_id: str, request: Request):
    ok = await run_in_threadpool(pricing_repo.delete_plan, plan_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Plan introuvable")
    await pricing.invalidate()
    audit_repo.log_admin_action("admin", "plan_delete", "plan", plan_id, _ip(request))
    return {"status": "ok", "plan_id": plan_id}


# ============================ PLANS DE SUPPRESSION ============================ #
@router.get("/api/deletion-plans", dependencies=[Depends(require_admin_auth)])
async def admin_list_deletion():
    return await run_in_threadpool(pricing_repo.list_deletion_plans)


@router.post("/api/deletion-plans", dependencies=[Depends(require_admin_auth)])
async def admin_create_deletion(payload: DeletionPlanPayload, request: Request):
    existing = {p["plan_id"] for p in await run_in_threadpool(pricing_repo.list_deletion_plans)}
    if payload.plan_id in existing:
        raise HTTPException(status_code=400, detail="Ce plan_id existe deja")
    await run_in_threadpool(pricing_repo.upsert_deletion_plan, payload.model_dump())
    await pricing.invalidate()
    audit_repo.log_admin_action("admin", "deletion_create", "deletion_plan",
                                payload.plan_id, _ip(request))
    return {"status": "ok"}


@router.patch("/api/deletion-plans/{plan_id}", dependencies=[Depends(require_admin_auth)])
async def admin_update_deletion(plan_id: str, payload: DeletionPlanPayload, request: Request):
    data = payload.model_dump()
    data["plan_id"] = plan_id
    await run_in_threadpool(pricing_repo.upsert_deletion_plan, data)
    await pricing.invalidate()
    audit_repo.log_admin_action("admin", "deletion_update", "deletion_plan", plan_id, _ip(request))
    return {"status": "ok"}


@router.delete("/api/deletion-plans/{plan_id}", dependencies=[Depends(require_admin_auth)])
async def admin_delete_deletion(plan_id: str, request: Request):
    ok = await run_in_threadpool(pricing_repo.delete_deletion_plan, plan_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Plan introuvable")
    await pricing.invalidate()
    audit_repo.log_admin_action("admin", "deletion_delete", "deletion_plan", plan_id, _ip(request))
    return {"status": "ok"}


# ================================ REGLAGES ================================ #
@router.get("/api/settings", dependencies=[Depends(require_admin_auth)])
async def admin_get_settings():
    values = await run_in_threadpool(pricing_repo.get_settings)
    return {"values": values, "defaults": pricing_repo.DEFAULT_SETTINGS}


@router.patch("/api/settings", dependencies=[Depends(require_admin_auth)])
async def admin_set_settings(payload: SettingsPayload, request: Request):
    n = await run_in_threadpool(pricing_repo.set_settings, payload.values)
    await pricing.invalidate()
    audit_repo.log_admin_action("admin", "settings_update", "settings", str(n),
                                _ip(request), json.dumps(payload.values)[:500])
    return {"status": "ok", "updated": n}


@router.post("/api/settings/reset", dependencies=[Depends(require_admin_auth)])
async def admin_reset_settings(request: Request):
    await run_in_threadpool(pricing_repo.reset_settings)
    await pricing.invalidate()
    audit_repo.log_admin_action("admin", "settings_reset", "settings", "", _ip(request))
    return {"status": "ok"}


# ================================ ETAT / CACHE ================================ #
@router.get("/api/pricing/state", dependencies=[Depends(require_admin_auth)])
async def admin_pricing_state():
    def _build():
        s = pricing.get_settings()
        return {
            "guest_daily_quota": pricing.guest_daily_quota(),
            "user_daily_quota": pricing.user_daily_quota(),
            "global_rps_guest": pricing.setting_int("global_rps_guest", 3),
            "global_rps_user": pricing.setting_int("global_rps_user", 5),
            "plans": [{"plan_id": p["plan_id"], "daily_quota": p["daily_quota"],
                       "rate_limit_rps": p["rate_limit_rps"],
                       "web_unlimited": p["web_unlimited"],
                       "web_daily_quota": p["web_daily_quota"]}
                      for p in pricing.get_plans()],
            "banner_enabled": pricing.setting_bool("banner_enabled", False),
            "maintenance_mode": pricing.setting_bool("maintenance_mode", False),
            "registration_open": pricing.setting_bool("registration_open", True),
            "price_format_eur": s.get("price_format_eur"),
        }
    return await run_in_threadpool(_build)


@router.post("/api/pricing/flush", dependencies=[Depends(require_admin_auth)])
async def admin_flush_cache(request: Request):
    await pricing.invalidate()
    await run_in_threadpool(pricing_repo.ensure_defaults)
    await pricing.invalidate()
    audit_repo.log_admin_action("admin", "pricing_flush", "", "", _ip(request))
    return {"status": "ok"}


@router.post("/api/pricing/detect", dependencies=[Depends(require_admin_auth)])
async def admin_detect_ui_matches(request: Request):
    """Scanne les pages publiques et remplit automatiquement les champs
    'texte a remplacer' des plans, en associant chaque libelle a son prix."""
    import html as htmlmod
    import re
    import urllib.request

    base = str(request.base_url).rstrip("/")

    def _plain(path: str) -> str:
        try:
            raw = urllib.request.urlopen(base + path, timeout=10).read().decode("utf-8", "ignore")
        except Exception:
            return ""
        raw = re.sub(r"<script.*?</script>", " ", raw, flags=re.S | re.I)
        raw = re.sub(r"<style.*?</style>", " ", raw, flags=re.S | re.I)
        txt = htmlmod.unescape(re.sub(r"<[^>]+>", " ", raw))
        return re.sub(r"\s+", " ", txt)

    pages = {}
    for path in ("/", "/api-docs", "/cgu"):
        p = _plain(path)
        if p:
            pages[path] = p

    def _work():
        found = {}
        plans = pricing_repo.list_plans() + pricing_repo.list_deletion_plans()
        price_re = re.compile(r"\d+(?:[.,]\d{1,2})?\s*(?:€|EUR|\$|USD)", re.I)
        for pl in plans:
            label = (pl.get("label") or pl["plan_id"]).strip()
            if not label:
                continue
            for path, txt in pages.items():
                idx = txt.lower().find(label.lower())
                if idx == -1:
                    continue
                window = txt[max(0, idx - 150): idx + 450]
                m = price_re.search(window)
                if m:
                    found[pl["plan_id"]] = {"ui_match": m.group(0).strip(), "page": path}
                break

        applied = []
        for pid, info in found.items():
            target = next((x for x in pricing_repo.list_plans() if x["plan_id"] == pid), None)
            kind = "plan"
            if target is None:
                target = next((x for x in pricing_repo.list_deletion_plans()
                               if x["plan_id"] == pid), None)
                kind = "deletion"
            if target is None:
                continue
            target["ui_match"] = info["ui_match"]
            if kind == "plan":
                pricing_repo.upsert_plan(target)
            else:
                pricing_repo.upsert_deletion_plan(target)
            applied.append({"plan_id": pid, "ui_match": info["ui_match"], "page": info["page"]})

        return {"pages_scannees": list(pages.keys()), "appliques": applied}

    result = await run_in_threadpool(_work)
    await pricing.invalidate()
    audit_repo.log_admin_action("admin", "pricing_detect", "ui_match",
                                str(len(result.get("appliques", []))), _ip(request))
    return result


def _ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"
