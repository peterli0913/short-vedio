from auto_resume_bot.filters import hard_filter
from auto_resume_bot.models import Job, JobStatus

PROFILE = {
    "city_allowlist": ["Hong Kong", "HK", "香港"],
    "salary_rmb_min": 50000,
    "role_keywords": ["智能制造", "AI", "运筹", "smart manufacturing"],
    "company_blocklist": ["BadCo"],
}


def _job(**kw):
    base = dict(
        job_key="x",
        title="AI Application",
        company="Good",
        location="Hong Kong",
        salary_raw="CNY 60000",
        salary_rmb_min=60000,
        url="u",
        source="jobsdb",
        description="AI应用 智能制造",
        status=JobStatus.discovered,
    )
    base.update(kw)
    return Job(**base)


def test_pass():
    r = hard_filter(_job(), PROFILE, 0.92)
    assert r.passed and not r.gray


def test_wrong_city():
    r = hard_filter(_job(location="Shanghai"), PROFILE, 0.92)
    assert not r.passed and not r.gray


def test_salary_gray():
    r = hard_filter(_job(salary_raw="面议", salary_rmb_min=None), PROFILE, 0.92)
    assert r.gray and not r.passed


def test_blocklist():
    r = hard_filter(_job(company="BadCo"), PROFILE, 0.92)
    assert not r.passed
