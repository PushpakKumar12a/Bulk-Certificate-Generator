import hmac
import logging
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class Identity:
    user_id: str
    scopes: frozenset[str]

def identities() -> dict[str, Identity]:
    result: dict[str, Identity] = {}
    for entry in get_settings().api_keys.split(","):
        parts = entry.strip().split(":", 2)
        if len(parts) != 3:
            continue
        key, user_id, scopes = parts
        if key and user_id:
            result[key] = Identity(user_id, frozenset(scopes.split("|")))
    return result

def authenticate(api_key: str | None = Header(default=None, alias="X-API-Key")) -> Identity:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    for configured_key, identity in identities().items():
        if hmac.compare_digest(api_key, configured_key):
            return identity
    logger.warning("Rejected invalid API key")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")

def require_scope(scope: str):
    def dependency(identity: Identity = Depends(authenticate)) -> Identity:
        if scope not in identity.scopes:
            raise HTTPException(status_code=403, detail="insufficient scope")
        return identity

    return dependency