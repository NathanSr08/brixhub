import json
from datetime import datetime, timedelta
from starlette.concurrency import run_in_threadpool
from app.core.config import get_settings
from app.core.security import generate_key
from app.db.clickhouse import get_redis
from app.repositories import keys_repo, usage_repo

CACHE_TTL = 3600

class KeyService:
    async def resolve(self, key_hash: str) -> dict | None:
        r = get_redis()
        cached = await r.get(f"apikey:{key_hash}")
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass
        rec = await run_in_threadpool(keys_repo.get_by_hash, key_hash)
        if rec:
            await r.setex(f"apikey:{key_hash}", CACHE_TTL, json.dumps(rec, default=str))
        return rec

    async def create(self, label: str, email: str, plan: str) -> dict:
        s = get_settings()
        if plan not in s.plans:
            plan = "free"
        raw, key_hash, preview = generate_key()
        key_id = keys_repo.new_id()
        rec = {
            "key_id": key_id, "key_hash": key_hash, "preview": preview,
            "label": label, "owner_email": email, "plan": plan,
            "is_active": 1, "created_at": datetime.utcnow(),
        }
        await run_in_threadpool(keys_repo.insert, rec)
        r = get_redis()
        await r.setex(f"apikey:{key_hash}", CACHE_TTL, json.dumps(rec, default=str))
        return {**rec, "is_active": True, "key": raw, "quota_per_day": s.plans[plan]}

    async def revoke(self, key_id: str) -> bool:
        rec = await run_in_threadpool(keys_repo.get_by_id, key_id)
        if not rec:
            return False
        kh = rec["key_hash"]
        rec["is_active"] = 0
        # Timestamp strictement supérieur pour devancer ReplacingMergeTree(created_at)
        orig_dt = rec.get("created_at")
        if isinstance(orig_dt, datetime):
            rec["created_at"] = orig_dt + timedelta(seconds=2)
        else:
            rec["created_at"] = datetime.utcnow() + timedelta(seconds=2)
        
        await run_in_threadpool(keys_repo.insert, rec)
        r = get_redis()
        # Écrasement direct dans Redis pour effet immédiat
        await r.setex(f"apikey:{kh}", CACHE_TTL, json.dumps(rec, default=str))
        return True

    async def usage(self, key_id: str) -> dict:
        today = await run_in_threadpool(usage_repo.usage_today, key_id)
        hist = await run_in_threadpool(usage_repo.usage_summary, key_id, 30)
        return {"requetes_aujourdhui": today, "historique_30j": hist}
