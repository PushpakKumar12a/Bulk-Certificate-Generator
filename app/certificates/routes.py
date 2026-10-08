from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.certificates.schemas import CertificateVerifyOut
from app.certificates.storage import CertificateStorage
from app.core.auth import CurrentUser
from app.core.config import get_settings
from app.db.models import Certificate, Job, Recipient
from app.db.repo import get_certificate, get_certificate_by_id
from app.db.session import get_db

router = APIRouter()

@router.get(
    "/jobs/{job_id}/certificates/{certificate_id}",
    summary="Download Certificate PDF",
    tags=["jobs"],
)
async def download(
    job_id: UUID,
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = ...,
) -> FileResponse:
    certificate = await get_certificate(db, job_id, certificate_id)
    if certificate is None:
        raise HTTPException(status_code=404, detail="certificate not found")

    recipient = certificate.recipient
    if recipient is None or recipient.job is None or recipient.job.owner != current_user:
        raise HTTPException(status_code=404, detail="certificate not found")

    storage = CertificateStorage(Path(get_settings().storage_path))
    try:
        file_path = storage.path_for(certificate.file_path)
        file_path.stat()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="certificate file not found") from exc

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"{certificate.id}.pdf",
        headers={"Content-Disposition": f'attachment; filename="{certificate.id}.pdf"'},
    )

@router.get(
    "/verify/{certificate_id}",
    response_model=CertificateVerifyOut,
    summary="Verify Certificate Authenticity",
    tags=["verification"],
)
async def verify(certificate_id: str, db: AsyncSession = Depends(get_db)) -> CertificateVerifyOut:
    clean_id = certificate_id.strip().strip("'\"{}")
    if clean_id.lower().endswith(".pdf"):
        clean_id = clean_id[:-4]

    try:
        cert_uuid = UUID(clean_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Certificate ID format is invalid")

    certificate = await get_certificate_by_id(db, cert_uuid)
    if certificate is None:
        recipient = await db.scalar(
            select(Recipient)
            .options(selectinload(Recipient.certificate), selectinload(Recipient.job))
            .where(Recipient.id == cert_uuid)
        )
        if recipient and recipient.certificate:
            certificate = recipient.certificate
        else:
            job_match = await db.get(Job, cert_uuid)
            if job_match:
                raise HTTPException(
                    status_code=400,
                    detail="The provided ID is a Job ID, not a Certificate ID. Check /jobs/{job_id} for individual certificate IDs.",
                )
            raise HTTPException(status_code=404, detail="Certificate not found or not authentic")

    recipient = certificate.recipient
    job = recipient.job if recipient else None
    if recipient is None or job is None:
        raise HTTPException(status_code=404, detail="Certificate metadata not found")

    return CertificateVerifyOut(
        valid=True,
        certificate_id=certificate.id,
        recipient_name=recipient.name,
        course=job.course,
        org=job.org,
        issue_date=job.issue_date,
        issued_at=certificate.created_at,
    )

@router.get(
    "/certificates/{certificate_id}/verify",
    response_model=CertificateVerifyOut,
    summary="Verify Certificate by ID",
    tags=["verification"],
)
async def verify_alias(
    certificate_id: str,
    db: AsyncSession = Depends(get_db),
) -> CertificateVerifyOut:
    return await verify(certificate_id, db)

@router.get(
    "/certificates/{certificate_id}",
    summary="Download Certificate PDF by ID",
    tags=["certificates"],
)
async def download_by_id_alias(
    certificate_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    clean_id = certificate_id.strip().strip("'\"{}")
    if clean_id.lower().endswith(".pdf"):
        clean_id = clean_id[:-4]

    try:
        cert_uuid = UUID(clean_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Certificate ID format is invalid")

    certificate = await get_certificate_by_id(db, cert_uuid)
    if certificate is None:
        recipient = await db.scalar(
            select(Recipient)
            .options(selectinload(Recipient.certificate))
            .where(Recipient.id == cert_uuid)
        )
        if recipient and recipient.certificate:
            certificate = recipient.certificate
        else:
            raise HTTPException(status_code=404, detail="certificate not found")

    storage = CertificateStorage(Path(get_settings().storage_path))
    try:
        file_path = storage.path_for(certificate.file_path)
        file_path.stat()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="certificate file not found") from exc

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"{certificate.id}.pdf",
        headers={"Content-Disposition": f'attachment; filename="{certificate.id}.pdf"'},
    )
