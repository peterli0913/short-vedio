from auto_resume_bot.db import Database
from auto_resume_bot.models import Job, JobStatus
from auto_resume_bot.pipeline import process_new_job
from auto_resume_bot.queue import decide_queue
from auto_resume_bot.scorer import FakeScorer


def test_decide_queue():
    assert decide_queue(80) == JobStatus.queued
    assert decide_queue(65) == JobStatus.needs_human
    assert decide_queue(40) == JobStatus.skipped


PROFILE = {
    "city_allowlist": ["Hong Kong", "HK", "香港"],
    "salary_rmb_min": 50000,
    "role_keywords": ["智能制造", "AI", "运筹", "smart manufacturing"],
    "company_blocklist": [],
}

CFG = {
    "currency": {"hkd_to_cny": 0.92},
    "scoring": {"auto_min": 70, "gray_min": 60},
    "resume_summary": "AI manufacturing",
}


def _job(**kw):
    base = dict(
        job_key="jobsdb:9",
        title="AI Application Manager",
        company="Acme",
        location="Hong Kong",
        salary_raw="HKD 60,000 - 80,000",
        salary_rmb_min=55200,
        url="https://example.com/9",
        source="jobsdb",
        description="smart manufacturing AI",
        status=JobStatus.discovered,
    )
    base.update(kw)
    return Job(**base)


def test_process_queued(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    job = process_new_job(db, _job(), PROFILE, FakeScorer(80), CFG)
    assert db.get_job(job.job_key).status == JobStatus.queued


def test_process_gray_score(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    job = process_new_job(db, _job(job_key="jobsdb:65"), PROFILE, FakeScorer(65), CFG)
    assert db.get_job(job.job_key).status == JobStatus.needs_human


def test_salary_gray_skips_scorer(tmp_path):
    db = Database(tmp_path / "t.sqlite")

    class Boom:
        def score(self, *args, **kwargs):
            raise AssertionError("should not score")

    job = process_new_job(
        db,
        _job(job_key="jobsdb:gray", salary_raw="面议", salary_rmb_min=None),
        PROFILE,
        Boom(),
        CFG,
    )
    stored = db.get_job(job.job_key)
    assert stored.status == JobStatus.needs_human
    assert stored.score is None
