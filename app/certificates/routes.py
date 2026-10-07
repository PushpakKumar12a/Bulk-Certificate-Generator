from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.certificates.storage import LocalCertificateStorage
from app.core.config import get_settings
from app.db.repo import get_certificate
from app.db.session import get_db

router = APIRouter(prefix="/jobs", tags=["certificates"])

@router.get("/{job_id}/certificates/{certificate_id}")
async def download(
    job_id: UUID,
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    certificate = await get_certificate(db, job_id, certificate_id)
    if certificate is None:
        raise HTTPException(status_code=404, detail="certificate not found")

    try:
        content = LocalCertificateStorage(
            Path(get_settings().storage_path)
        ).read(certificate.file_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="certificate file not found") from exc

    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{certificate.id}.pdf"'},
    )
