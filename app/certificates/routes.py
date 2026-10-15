from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.certificates.schemas import CertificateVerifyOut
from app.certificates.storage import get_storage
from app.db.models import Job, Recipient
from app.db.repo import get_certificate_by_id
from app.db.session import get_db

router = APIRouter(prefix="/certificates", tags=["certificates"])

def parse_cert_uuid(raw_id: str) -> UUID:
    clean = raw_id.strip().strip("'\"{}")
    if clean.lower().endswith(".pdf"):
        clean = clean[:-4]
    try:
        return UUID(clean)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Certificate ID format is invalid")

@router.get("/{certificate_id}", summary="Download Certificate PDF")
async def download_certificate(
    certificate_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    cert_uuid = parse_cert_uuid(certificate_id)
    certificate = await get_certificate_by_id(db, cert_uuid)
    if certificate is None:
        recipient = await db.scalar(
            select(Recipient).options(selectinload(Recipient.certificate)).where(Recipient.id == cert_uuid)
        )
        if recipient and recipient.certificate:
            certificate = recipient.certificate
        else:
            raise HTTPException(status_code=404, detail="certificate not found")

    storage = get_storage()
    try:
        content = storage.read(certificate.file_path)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{certificate.id}.pdf"'},
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="certificate file not found") from exc

@router.get(
    "/{certificate_id}/verify",
    response_model=CertificateVerifyOut,
    summary="Verify Certificate Authenticity",
)
async def verify_certificate(
    certificate_id: str,
    db: AsyncSession = Depends(get_db),
) -> CertificateVerifyOut:
    cert_uuid = parse_cert_uuid(certificate_id)
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
            if await db.get(Job, cert_uuid):
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