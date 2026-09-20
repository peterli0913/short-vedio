from auto_resume_bot.models import Job, JobStatus
from auto_resume_bot.scorer import FakeScorer, ScoreResult


def test_fake_scorer():
    job = Job(
        job_key="k",
        title="t",
        company="c",
        location="Hong Kong",
        url="u",
        source="jobsdb",
        status=JobStatus.discovered,
    )
    r = FakeScorer(75).score(job, "resume")
    assert r.score == 75
    assert isinstance(r.reason, str)
    assert isinstance(r, ScoreResult)
