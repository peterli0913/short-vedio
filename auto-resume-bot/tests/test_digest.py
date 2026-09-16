from datetime import date, datetime, timezone

from auto_resume_bot.db import Database
from auto_resume_bot.digest import build_digest
from auto_resume_bot.models import Job, JobStatus, MailCategory, MailEvent


def test_digest_sections(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    db.upsert_job(
        Job(
            job_key="jobsdb:1",
            title="AI Application",
            company="Acme",
            location="Hong Kong",
            url="u",
            source="jobsdb",
            status=JobStatus.applied,
            score=80,
            applied_at=datetime.now(timezone.utc),
        )
    )
    db.upsert_job(
        Job(
            job_key="jobsdb:2",
            title="Ops",
            company="GrayCo",
            location="Hong Kong",
            url="u",
            source="jobsdb",
            status=JobStatus.needs_human,
        )
    )
    db.add_mail_event(
        MailEvent(
            id="m1",
            account="a",
            subject="Interview invitation",
            from_addr="hr@acme.hk",
            received_at=datetime.now(timezone.utc),
            category=MailCategory.interview,
            job_key="jobsdb:1",
        )
    )
    text = build_digest(db, date.today())
    assert "Auto-resume digest" in text
    assert "Acme" in text
    assert "GrayCo" in text
    assert "Interview invitation" in text
