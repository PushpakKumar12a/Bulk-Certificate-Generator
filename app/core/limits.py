from collections import defaultdict, deque
from time import monotonic

from fastapi import HTTPException, Request

from app.core.config import get_settings

requests: dict[str, deque[float]] = defaultdict(deque)

def check_rate(request: Request) -> None:
    now = monotonic()
    window = now - 60

    if request.client is not None:
        client = request.client.host

    else:
        client = "unknown"

    bucket = requests[f"{client}:{request.url.path}"]

    while bucket and bucket[0] <= window:
        bucket.popleft()

    if len(bucket) >= get_settings().rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="rate limit exceeded")

    bucket.append(now)
