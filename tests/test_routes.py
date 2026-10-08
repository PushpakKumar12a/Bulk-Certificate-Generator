from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

@pytest.mark.asyncio
async def test_jobs_status_requires_authentication() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/jobs/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 401

@pytest.mark.asyncio
async def test_certificate_download_requires_authentication() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/jobs/00000000-0000-0000-0000-000000000000/certificates/00000000-0000-0000-0000-000000000000"
        )

    assert response.status_code == 401

@pytest.mark.asyncio
async def test_certificate_verify_not_found() -> None:
    with patch("app.certificates.routes.get_certificate_by_id", new_callable=AsyncMock, return_value=None):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/certificates/00000000-0000-0000-0000-000000000000/verify")
            assert response.status_code == 404

            response_shorthand = await client.get("/verify/00000000-0000-0000-0000-000000000000")
            assert response_shorthand.status_code == 404


@pytest.mark.asyncio
async def test_certificate_verify_invalid_uuid() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/certificates/not-a-valid-uuid/verify")
        assert response.status_code == 404

@pytest.mark.asyncio
async def test_certificate_verify_success() -> None:
    from datetime import date, datetime, UTC
    from uuid import uuid4
    from unittest.mock import MagicMock

    cert_id = uuid4()
    mock_cert = MagicMock()
    mock_cert.id = cert_id
    mock_cert.created_at = datetime(2026, 10, 7, 12, 0, 0, tzinfo=UTC)
    mock_cert.recipient.name = "Priya Sharma"
    mock_cert.recipient.job.course = "Cloud Architecture"
    mock_cert.recipient.job.org = "Google Cloud"
    mock_cert.recipient.job.issue_date = date(2026, 10, 7)

    with patch("app.certificates.routes.get_certificate_by_id", new_callable=AsyncMock, return_value=mock_cert):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/certificates/{cert_id}/verify")
            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is True
            assert data["certificate_id"] == str(cert_id)
            assert data["recipient_name"] == "Priya Sharma"
            assert data["course"] == "Cloud Architecture"
            assert data["org"] == "Google Cloud"
            assert data["issue_date"] == "2026-10-07"
