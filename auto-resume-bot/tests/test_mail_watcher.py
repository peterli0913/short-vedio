from datetime import datetime, timezone
from types import SimpleNamespace

from auto_resume_bot.db import Database
from auto_resume_bot.mail_watcher import classify_subject, match_job_key, poll_account
from auto_resume_bot.models import Job, JobStatus, MailCategory


def test_classify_subject():
    assert classify_subject("Interview invitation", "") == MailCategory.interview
    assert classify_subject("感谢您的应聘", "很遗憾") == MailCategory.reject
    assert classify_subject("请补充材料", "") == MailCategory.docs_needed


def test_poll_attaches_company_match(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    db.upsert_job(
        Job(
            job_key="jobsdb:1",
            title="AI Application",
            company="Acme HK",
            location="Hong Kong",
            url="u",
            source="jobsdb",
            status=JobStatus.applied,
            applied_at=datetime.now(timezone.utc),
        )
    )

    class FakeImap:
        def fetch_messages(self):
            return [
                SimpleNamespace(
                    uid="17",
                    subject="Interview invitation from Acme HK",
                    from_addr="hr@acme.hk",
                    body="Can we schedule a call?",
                    received_at=datetime.now(timezone.utc),
                )
            ]

    events = poll_account(FakeImap(), "peterdqs@163.com", db)
    assert events[0].category == MailCategory.interview
    assert events[0].job_key == "jobsdb:1"
    stored = db.get_job("jobsdb:1")
    assert events[0].id in stored.mail_event_ids
    assert match_job_key(db, "hello Acme HK", "") == "jobsdb:1"
