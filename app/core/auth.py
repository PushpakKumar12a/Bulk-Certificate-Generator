import time
from collections import defaultdict
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from app.core.config import get_settings

api_key_scheme = APIKeyHeader(name="X-Api-Key", auto_error=False)

def parse_keys(raw: str) -> dict[str, str]:
    return {
        key.strip(): user_id.strip()
        for pair in raw.split(",")
        if ":" in pair
        for key, user_id in [pair.split(":", 1)]
    }

rate_counters: dict[str, list[float]] = defaultdict(list)

def check_rate(key: str, limit: int) -> None:
    now = time.monotonic()
    rate_counters[key] = [t for t in rate_counters[key] if now - t < 60]
    if len(rate_counters[key]) >= limit:
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    rate_counters[key].append(now)

def require_api_key(
    x_api_key: Annotated[str | None, Depends(api_key_scheme)],
) -> str:
    settings = get_settings()
    keys = parse_keys(settings.api_keys)

    if not x_api_key or x_api_key not in keys:
        raise HTTPException(status_code=401, detail="invalid or missing API key")

    check_rate(x_api_key, settings.rate_limit_per_minute)
    return keys[x_api_key]

CurrentUser = Annotated[str, Depends(require_api_key)]
