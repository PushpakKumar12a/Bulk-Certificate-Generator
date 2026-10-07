import logging

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.observability import JsonFormatter
from app.main import app


def test_logs_are_json() -> None:
    record = logging.LogRecord(
        "test",
        logging.INFO,
        __file__,
        1,
        "request %s",
        ("abc",),
        None,
    )

    assert JsonFormatter().format(record) == (
        '{"level": "INFO", "logger": "test", "message": "request abc"}'
    )


@pytest.mark.asyncio
async def test_health_has_request_id_and_readiness_is_explicit() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        health = await client.get("/health", headers={"X-Request-ID": "test-request"})
        ready = await client.get("/ready")

    assert health.headers["X-Request-ID"] == "test-request"
    assert ready.json()["status"] in {"ready", "degraded"}
