#!/usr/bin/env python3
"""Cable les plans/quotas/rate-limits dynamiques."""
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "app" / "main.py").exists():
    print("!!! Lance depuis la racine du repo"); sys.exit(2)

DONE, SKIPPED, FAILED = [], [], []


def load(p): return (ROOT / p).read_text(encoding="utf-8")


def save(p, s):
    f = ROOT / p
    bak = f.with_suffix(f.suffix + ".bakpricing")
    if not bak.exists():
        shutil.copy2(f, bak)
    f.write_text(s, encoding="utf-8")


def replace(path, old, new, marker, label, count=1):
    s = load(path)
    if marker in s:
        SKIPPED.append(label); return
    if old not in s:
        FAILED.append(f"{label} : ancre introuvable dans {path}"); return
    save(path, s.replace(old, new, count))
    DONE.append(label)


# ------------------------------ main.py ------------------------------ #
P = "app/main.py"
replace(P,
    "from app.api.admin_logs import router as admin_logs_router",
    "from app.api.admin_logs import router as admin_logs_router\n"
    "from app.api.admin_pricing import router as pricing_router, public_router as config_router",
    "from app.api.admin_pricing import", "main.py : import")

replace(P,
    "    app.include_router(admin_logs_router)",
    "    app.include_router(admin_logs_router)\n"
    "    app.include_router(pricing_router)\n"
    "    app.include_router(config_router)",
    "app.include_router(pricing_router)", "main.py : routers")

replace(P,
    "    await run_in_threadpool(bootstrap.ensure_schema)",
    "    await run_in_threadpool(bootstrap.ensure_schema)\n"
    "    await run_in_threadpool(bootstrap.ensure_pricing_defaults)",
    "bootstrap.ensure_pricing_defaults", "main.py : defaults pricing")

# ------------------------------ deps.py ------------------------------ #
P = "app/core/deps.py"
replace(P,
    "from app.core.rate_limit import QuotaLimiter",
    "from app.core.rate_limit import QuotaLimiter, enforce_rps\nfrom app.core import pricing",
    "from app.core import pricing", "deps.py : imports")

replace(P,
    '''    quota = get_settings().plans.get(rec.get("plan", "free"), 500)
    request.state.key_id = rec["key_id"]
    request.state.key_label = rec.get("label", "")
    request.state.key_plan = rec.get("plan", "")
    try:
        info = await QuotaLimiter(get_redis()).consume(rec["key_id"], quota)''',
    '''    plan = rec.get("plan", "free")
    quota = pricing.plan_daily_quota(plan)
    request.state.key_id = rec["key_id"]
    request.state.key_label = rec.get("label", "")
    request.state.key_plan = plan
    try:
        await enforce_rps(get_redis(), "api", rec["key_id"], pricing.plan_rps(plan))
    except HTTPException as exc:
        request.state.audit_error = "RPS_EXCEEDED"
        raise exc
    try:
        info = await QuotaLimiter(get_redis()).consume(rec["key_id"], quota)''',
    "pricing.plan_daily_quota(plan)", "deps.py : quota + rps dynamiques")

# ------------------------------ quotas.py ------------------------------ #
P = "app/core/quotas.py"
replace(P,
    "from app.db.clickhouse import get_redis",
    "from app.core import pricing\nfrom app.core.rate_limit import enforce_rps\nfrom app.db.clickhouse import get_redis",
    "from app.core import pricing", "quotas.py : imports")

replace(P,
    '''        if plan in ["starter", "pro", "enterprise", "paid"]:
            return {"user": user, "quota": "unlimited", "remaining": 999999}''',
    '''        if pricing.plan_web_unlimited(plan):
            return {"user": user, "quota": "unlimited", "remaining": 999999}''',
    "pricing.plan_web_unlimited(plan)", "quotas.py : plan illimite")

replace(P,
    "        limit = 5\n        if used > limit:",
    "        limit = pricing.plan_web_quota(plan)\n        if used > limit:",
    "limit = pricing.plan_web_quota(plan)", "quotas.py : quota user")

replace(P,
    "    limit = 2\n    if used > limit:",
    "    limit = pricing.guest_daily_quota()\n    if used > limit:",
    "limit = pricing.guest_daily_quota()", "quotas.py : quota guest")

replace(P,
    '''    rkey = f"quota:user:{user['user_id']}:{today}"''',
    '''    await enforce_rps(r, "web", str(user["user_id"]), pricing.setting_int("global_rps_user", 5))
        rkey = f"quota:user:{user['user_id']}:{today}"''',
    'enforce_rps(r, "web", str(user["user_id"])', "quotas.py : rps user")

replace(P,
    '''    rkey = f"quota:ip:{client_ip}:{today}"''',
    '''    await enforce_rps(r, "web", client_ip, pricing.setting_int("global_rps_guest", 3))
    rkey = f"quota:ip:{client_ip}:{today}"''',
    'enforce_rps(r, "web", client_ip', "quotas.py : rps guest")

# ------------------------------ legacy.py ------------------------------ #
P = "app/api/legacy.py"
replace(P,
    "from app.repositories import clicks_repo",
    "from app.repositories import clicks_repo\nfrom app.core import pricing\nfrom app.core.rate_limit import enforce_rps",
    "from app.core import pricing", "legacy.py : imports")

replace(P,
    '        is_unlimited = plan in ["starter", "pro", "enterprise", "paid"]',
    '        is_unlimited = pricing.plan_web_unlimited(plan)\n'
    '        await enforce_rps(r, "web", user_id, pricing.setting_int("global_rps_user", 5))',
    "pricing.plan_web_unlimited(plan)", "legacy.py : plan illimite + rps")

replace(P,
    "            if used > 5:",
    "            if used > pricing.plan_web_quota(plan):",
    "if used > pricing.plan_web_quota(plan):", "legacy.py : quota user")

replace(P,
    "        ikey = f\"quota:ip:{client_ip}:{today_str}\"",
    "        await enforce_rps(r, \"web\", client_ip, pricing.setting_int(\"global_rps_guest\", 3))\n"
    "        ikey = f\"quota:ip:{client_ip}:{today_str}\"",
    'enforce_rps(r, "web", client_ip, pricing.setting_int("global_rps_guest"',
    "legacy.py : rps guest")

replace(P,
    "        if used > 2:",
    "        if used > pricing.guest_daily_quota():",
    "if used > pricing.guest_daily_quota():", "legacy.py : quota guest")

# ------------------------------ auth.py ------------------------------ #
P = "app/api/auth.py"
replace(P,
    "from app.core.quotas import check_search_quota",
    "from app.core.quotas import check_search_quota\nfrom app.core import pricing",
    "from app.core import pricing", "auth.py : import")

replace(P,
    'return {"logged_in": False, "plan": "guest", "limit": 2}',
    'return {"logged_in": False, "plan": "guest", "limit": pricing.guest_daily_quota()}',
    "limit\": pricing.guest_daily_quota()", "auth.py : limite guest", 3)

replace(P,
    '        "has_api_key": bool(user["api_key_id"])',
    '        "has_api_key": bool(user["api_key_id"]),\n'
    '        "limit": pricing.plan_web_quota(user["plan"]),\n'
    '        "unlimited": pricing.plan_web_unlimited(user["plan"]),',
    '"unlimited": pricing.plan_web_unlimited', "auth.py : limite user")

print("\n=== PATCH ===")
for d in DONE: print("  [OK]   ", d)
for s_ in SKIPPED: print("  [SKIP] ", s_)
for f in FAILED: print("  [ECHEC]", f)
print(f"\n{len(DONE)} applique(s), {len(SKIPPED)} deja en place, {len(FAILED)} echec(s).")
sys.exit(1 if FAILED else 0)
