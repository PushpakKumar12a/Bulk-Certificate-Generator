from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.certificates.storage import LocalCertificateStorage
from app.core.auth import Identity, require_scope
from app.core.config import get_settings
from app.db.repo import get_certificate
from app.db.session import get_db

router = APIRouter(prefix="/jobs", tags=["certificates"])


@router.get("/{job_id}/certificates/{certificate_id}")
async def download(
    job_id: UUID,
    certificate_id: UUID,
    identity: Identity = Depends(require_scope("certificates:read")),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    certificate = await get_certificate(db, job_id, certificate_id, identity.user_id)
    if certificate is None:
        raise HTTPException(status_code=404, detail="certificate not found")


    storage = LocalCertificateStorage(Path(get_settings().storage_path))
    try:
        file_path = storage.path_for(certificate.file_path)
        file_path.stat()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="certificate file not found") from exc


    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"{certificate.id}.pdf",
    )
