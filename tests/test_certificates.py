from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from app.certificates.storage import CertificateStorage
from app.certificates.template import certificate_pdf

def test_pdf_has_header() -> None:
    content = certificate_pdf(
        name="Sonu",
        course="Python",
        org="Example Org",
        issue_date=date(2026, 10, 7),
    )

    assert content.startswith(b"%PDF")
    assert len(content) > 500

def test_pdf_with_unique_certificate_id() -> None:
    cert_id = str(uuid4()).upper()
    content = certificate_pdf(
        name="Priya Sharma",
        course="Cloud Architecture",
        org="Google Cloud",
        issue_date=date(2026, 10, 7),
        certificate_id=cert_id,
    )

    assert content.startswith(b"%PDF")
    assert len(content) > 1000
    assert cert_id.encode() in content
    assert b"VERIFICATION ID" in content

def test_storage_read_write(tmp_path: Path) -> None:
    storage = CertificateStorage(tmp_path)
    key = f"certificates/{uuid4()}/{uuid4()}.pdf"

    assert storage.save(key, b"%PDF-test") == key
    assert storage.read(key) == b"%PDF-test"
    assert storage.path_for(key) == tmp_path / key

@pytest.mark.parametrize("key", ["../outside.pdf", r"..\outside.pdf", "C:/outside.pdf"])
def test_storage_rejects_unsafe_keys(tmp_path: Path, key: str) -> None:
    storage = CertificateStorage(tmp_path)

    with pytest.raises(ValueError, match="invalid"):
        storage.save(key, b"unsafe")
