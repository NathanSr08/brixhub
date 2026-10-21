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

    async def list_all(self) -> list[dict]:
        keys = await run_in_threadpool(keys_repo.list_all)
        s = get_settings()
        r = get_redis()
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        
        for k in keys:
            plan = k.get("plan", "free")
            quota_max = s.plans.get(plan, 0)
            k["quota_per_day"] = quota_max
            
            # Compteur du jour (Redis en priorité, fallback ClickHouse)
            kid = k["key_id"]
            used = 0
            try:
                # Clé Redis typique
                val = await r.get(f"usage:{kid}:{today_str}") or await r.get(f"rate:{kid}")
                if val:
                    used = int(val)
                else:
                    used = await run_in_threadpool(usage_repo.usage_today, kid)
            except Exception:
                used = await run_in_threadpool(usage_repo.usage_today, kid)
                
            k["used_today"] = used
            k["remaining_today"] = max(0, quota_max - used) if quota_max > 0 else 99999999
        return keys

    async def get_logs(self, key_id: str, limit: int = 100) -> list[dict]:
        return await run_in_threadpool(usage_repo.get_key_logs, key_id, limit)

    async def reset_daily_quota(self, key_id: str) -> bool:
        r = get_redis()
        # Supprime toutes les clés quota liées à ce key_id
        keys = await r.keys(f"quota:{key_id}:*")
        if keys:
            await r.delete(*keys)
        # Supprime aussi les éventuelles clés secondaires
        await r.delete(f"rate:{key_id}")
        return True

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
        orig_dt = rec.get("created_at")
        if isinstance(orig_dt, datetime):
            rec["created_at"] = orig_dt + timedelta(seconds=2)
        else:
            rec["created_at"] = datetime.utcnow() + timedelta(seconds=2)

        await run_in_threadpool(keys_repo.insert, rec)
        r = get_redis()
        await r.setex(f"apikey:{kh}", CACHE_TTL, json.dumps(rec, default=str))
        return True

    async def reactivate(self, key_id: str) -> bool:
        rec = await run_in_threadpool(keys_repo.get_by_id, key_id)
        if not rec:
            return False
        kh = rec["key_hash"]
        rec["is_active"] = 1
        orig_dt = rec.get("created_at")
        if isinstance(orig_dt, datetime):
            rec["created_at"] = orig_dt + timedelta(seconds=2)
        else:
            rec["created_at"] = datetime.utcnow() + timedelta(seconds=2)

        await run_in_threadpool(keys_repo.insert, rec)
        r = get_redis()
        await r.setex(f"apikey:{kh}", CACHE_TTL, json.dumps(rec, default=str))
        return True

    async def update_plan(self, key_id: str, new_plan: str) -> bool:
        s = get_settings()
        if new_plan not in s.plans:
            return False
        rec = await run_in_threadpool(keys_repo.get_by_id, key_id)
        if not rec:
            return False
        kh = rec["key_hash"]
        rec["plan"] = new_plan
        orig_dt = rec.get("created_at")
        if isinstance(orig_dt, datetime):
            rec["created_at"] = orig_dt + timedelta(seconds=2)
        else:
            rec["created_at"] = datetime.utcnow() + timedelta(seconds=2)

        await run_in_threadpool(keys_repo.insert, rec)
        r = get_redis()
        await r.setex(f"apikey:{kh}", CACHE_TTL, json.dumps(rec, default=str))
        return True

    async def usage(self, key_id: str) -> dict:
        today = await run_in_threadpool(usage_repo.usage_today, key_id)
        hist = await run_in_threadpool(usage_repo.usage_summary, key_id, 30)
        return {"requetes_aujourdhui": today, "historique_30j": hist}
