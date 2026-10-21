import time
from fastapi import HTTPException

DAY = 86_400

class QuotaLimiter:
    def __init__(self, redis):
        self.redis = redis

    async def consume(self, key_id: str, quota: int) -> dict:
        bucket = int(time.time()) // DAY
        rkey = f"quota:{key_id}:{bucket}"
        async with self.redis.pipeline(transaction=True) as p:
            p.incr(rkey)
            p.expire(rkey, DAY + 120)
            used, _ = await p.execute()
        if used > quota:
            raise HTTPException(
                status_code=429,
                detail="Quota journalier dépassé. Passe à un plan supérieur.",
                headers={
                    "X-RateLimit-Limit": str(quota),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str((bucket + 1) * DAY - int(time.time())),
                },
            )
        return {"limit": quota, "remaining": quota - used, "used": used}
