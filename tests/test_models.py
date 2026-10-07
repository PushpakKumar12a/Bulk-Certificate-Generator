from datetime import date

from sqlalchemy import Date, Enum, UniqueConstraint

from app.db.models import Certificate, Job, JobStatus, ItemStatus, Recipient

def test_tables() -> None:
    assert {Job.__tablename__, Recipient.__tablename__, Certificate.__tablename__} == {
        "jobs",
        "recipients",
        "certificates",
    }

def test_defaults() -> None:
    assert Job.__table__.c.status.default.arg == JobStatus.QUEUED
    assert Recipient.__table__.c.status.default.arg == ItemStatus.PENDING
    assert isinstance(Job.__table__.c.issue_date.type, Date)
    assert isinstance(Job.__table__.c.status.type, Enum)
    assert isinstance(Recipient.__table__.c.status.type, Enum)
    assert Certificate.__table__.c.file_path.name == "file_path"
    assert date(2026, 10, 7).isoformat() == "2026-10-07"

def test_unique_rows() -> None:
    names = {
        tuple(constraint.columns.keys())
        for constraint in Recipient.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("job_id", "row") in names