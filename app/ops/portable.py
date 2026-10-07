import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from app.certificates.storage import LocalCertificateStorage

def export_records(
    jobs: list[dict[str, Any]],
    recipients: list[dict[str, Any]],
    certificates: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = {
        "format": "bulk-certificate-generator-v1",
        "jobs": jobs,
        "recipients": recipients,
        "certificates": certificates,
    }

    validate_records(payload)

    return payload

def validate_records(payload: dict[str, Any]) -> None:
    if payload.get("format") != "bulk-certificate-generator-v1":
        raise ValueError("unsupported export format")

    jobs: set[str] = set()

    for job in payload.get("jobs", []):
        jobs.add(str(job["id"]))

    recipients: dict[str, dict[str, Any]] = {}

    for item in payload.get("recipients", []):
        recipients[str(item["id"])] = item

    for item in payload.get("recipients", []):
        if str(item["job_id"]) not in jobs:
            raise ValueError(f"recipient {item['id']} references a missing job")

    for certificate in payload.get("certificates", []):
        recipient_id = str(certificate["recipient_id"])
        if recipient_id not in recipients:
            raise ValueError(
                f"certificate {certificate['id']} references a missing recipient"
            )
        LocalCertificateStorage(".").path_for(certificate["file_path"])

def write_export(path: str | Path, payload: dict[str, Any]) -> None:
    validate_records(payload)

    Path(path).write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )

def read_export(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_records(payload)

    return payload

def backup_storage(source: str | Path, archive: str | Path) -> Path:
    source_path = Path(source).resolve()

    if not source_path.is_dir():
        raise FileNotFoundError(f"storage directory not found: {source_path}")

    archive_path = Path(archive).resolve()
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    
    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary) / "storage"
        shutil.copytree(source_path, staging)
        manifest = storage_manifest(staging)

        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
        created = shutil.make_archive(
            str(archive_path.with_suffix("")), "zip", temporary, "storage"
        )

    return Path(created)

def storage_manifest(root: str | Path) -> dict[str, str]:
    root_path = Path(root)
    manifest: dict[str, str] = {}
    for path in sorted(root_path.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue

        key = path.relative_to(root_path).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest[key] = digest

    return manifest

def restore_storage(archive: str | Path, target: str | Path) -> None:
    target_path = Path(target)
    target_path.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temporary:
        unpacked = Path(temporary)
        shutil.unpack_archive(str(archive), str(unpacked))
        source = unpacked / "storage"
        expected = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
        actual = storage_manifest(source)

        if expected != actual:
            raise ValueError("storage backup checksum verification failed")

        for path in source.rglob("*"):
            if path.is_file() and path.name != "manifest.json":
                destination = target_path / path.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
