from auto_resume_bot.db import Database
from auto_resume_bot.models import Job, JobStatus


def test_upsert_and_get_job(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    job = Job(
        job_key="jobsdb:1",
        title="AI Application Manager",
        company="Acme",
        location="Hong Kong",
        salary_raw="HKD 60k-80k",
        salary_rmb_min=55200,
        url="https://example.com/1",
        source="jobsdb",
        description="smart manufacturing AI",
        status=JobStatus.discovered,
    )
    db.upsert_job(job)
    got = db.get_job("jobsdb:1")
    assert got is not None
    assert got.title == "AI Application Manager"
    assert got.status == JobStatus.discovered


def test_count_applied_today(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    assert db.count_applied_today("jobsdb") == 0
