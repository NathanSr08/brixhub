"""Rate limiting : quota journalier + limite par seconde (valeurs pilotables)."""
import time

from fastapi import HTTPException

DAY = 86_400


class QuotaLimiter:
    def __init__(self, redis):
        self.redis = redis

    async def consume(self, key_id: str, quota: int) -> dict:
        if quota <= 0:
            return {"limit": 0, "remaining": 999999, "used": 0}
        bucket = int(time.time()) // DAY
        rkey = f"quota:{key_id}:{bucket}"
        async with self.redis.pipeline(transaction=True) as p:
            p.incr(rkey)
            p.expire(rkey, DAY + 120)
            used, _ = await p.execute()
        if used > quota:
            raise HTTPException(
                status_code=429,
                detail="QUOTA_DAILY_EXCEEDED",
                headers={
                    "X-RateLimit-Limit": str(quota),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str((bucket + 1) * DAY - int(time.time())),
                },
            )
        return {"limit": quota, "remaining": quota - used, "used": used}

    async def per_second(self, scope: str, ident: str, limit: int) -> dict:
        """Fenetre fixe d'une seconde. limit <= 0 => illimite."""
        if limit <= 0:
            return {"limit": 0, "used": 0}
        bucket = int(time.time())
        rkey = f"rps:{scope}:{ident}:{bucket}"
        async with self.redis.pipeline(transaction=True) as p:
            p.incr(rkey)
            p.expire(rkey, 2)
            used, _ = await p.execute()
        if used > limit:
            raise HTTPException(
                status_code=429,
                detail="RATE_LIMIT_PER_SECOND",
                headers={"Retry-After": "1", "X-RateLimit-RPS": str(limit)},
            )
        return {"limit": limit, "used": used}


async def enforce_rps(redis, scope: str, ident: str, limit: int) -> dict:
    return await QuotaLimiter(redis).per_second(scope, ident, limit)
