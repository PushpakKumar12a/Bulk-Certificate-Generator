from collections import defaultdict, deque
from time import monotonic

from fastapi import HTTPException, Request
from redis.asyncio import from_url

from app.core.config import get_settings

requests: dict[str, deque[float]] = defaultdict(deque)

async def check_rate(request: Request) -> None:
    now = monotonic()
    window = now - 60

    if request.client is not None:
        client = request.client.host

    else:
        client = "unknown"

    settings = get_settings()
    key = f"rate:{client}:{request.url.path}"

    if settings.redis_url:
        queue = from_url(settings.redis_url)
        try:
            count = await queue.incr(key)
            if count == 1:
                await queue.expire(key, 60)
            if count > settings.rate_limit_per_minute:
                raise HTTPException(status_code=429, detail="rate limit exceeded")
            return
        finally:
            await queue.aclose()

    bucket = requests[key]

    while bucket and bucket[0] <= window:
        bucket.popleft()

    if len(bucket) >= settings.rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="rate limit exceeded")

    bucket.append(now)

    if len(requests) > 1000:
        stale = []
        for path, values in requests.items():
            if not values or values[-1] <= window:
                stale.append(path)

        for path in stale:
            del requests[path]
