from pathlib import Path

import pytest

from app.ops.portable import (
    backup_storage,
    export_records,
    read_export,
    restore_storage,
    write_export,
)


def records() -> dict:
    return export_records(
        jobs=[{"id": "job-1"}],
        recipients=[{"id": "recipient-1", "job_id": "job-1"}],
        certificates=[
            {"id": "certificate-1", "recipient_id": "recipient-1", "file_path": "a.pdf"}
        ],
    )


def test_export_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "export.json"
    write_export(path, records())

    assert read_export(path)["format"] == "bulk-certificate-generator-v1"


def test_invalid_reference_is_rejected() -> None:
    payload = records()
    payload["certificates"][0]["recipient_id"] = "missing"

    with pytest.raises(ValueError, match="missing recipient"):
        write_export("unused.json", payload)


def test_storage_backup_restores_keys(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.joinpath("certificates/job").mkdir(parents=True)
    source.joinpath("certificates/job/cert.pdf").write_bytes(b"%PDF-test")
    archive = backup_storage(source, tmp_path / "backup.zip")

    restore_storage(archive, target)

    assert target.joinpath("certificates/job/cert.pdf").read_bytes() == b"%PDF-test"
