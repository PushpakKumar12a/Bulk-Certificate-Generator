from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from app.certificates.storage import LocalCertificateStorage
from app.certificates.template import certificate_html, certificate_pdf

def test_template_escapes_data() -> None:
    content = certificate_html(
        name="<Asha>",
        course="Python & APIs",
        org="Example Org",
        issue_date=date(2026, 10, 7),
        number="CERT-1",
    )

    assert "&lt;Asha&gt;" in content
    assert "Python &amp; APIs" in content

def test_pdf_has_header() -> None:
    try:
        content = certificate_pdf(
            name="Asha",
            course="Python",
            org="Example Org",
            issue_date=date(2026, 10, 7),
            number="CERT-1",
        )
    except OSError as exc:
        pytest.skip(f"WeasyPrint native libraries unavailable: {exc}")

    assert content.startswith(b"%PDF")

def test_storage_read_write(tmp_path: Path) -> None:
    storage = LocalCertificateStorage(tmp_path)
    key = f"certificates/{uuid4()}/{uuid4()}.pdf"

    assert storage.save(key, b"%PDF-test") == key
    assert storage.read(key) == b"%PDF-test"

@pytest.mark.parametrize("key", ["../outside.pdf", r"..\outside.pdf", "C:/outside.pdf"])
def test_storage_rejects_unsafe_keys(tmp_path: Path, key: str) -> None:
    storage = LocalCertificateStorage(tmp_path)

    with pytest.raises(ValueError, match="invalid"):
        storage.save(key, b"unsafe")