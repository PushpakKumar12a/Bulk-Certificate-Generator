import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.core.auth import Identity, require_scope
from app.main import app

def test_identity_scope() -> None:
    dependency = require_scope("jobs:read")

    assert dependency.__name__ == "dependency"

def test_missing_scope_is_rejected() -> None:
    dependency = require_scope("jobs:write")

    with pytest.raises(HTTPException, match="insufficient scope"):
        dependency(Identity("team-a", frozenset({"jobs:read"})))

@pytest.mark.asyncio
async def test_jobs_require_authentication() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/jobs/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 401
