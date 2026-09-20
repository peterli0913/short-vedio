from datetime import datetime, timezone

from auto_resume_bot.applier import apply_job, run_apply_batch
from auto_resume_bot.db import Database
from auto_resume_bot.models import Job, JobStatus


class FakeLocator:
    def __init__(self, visible: bool):
        self._visible = visible

    def count(self) -> int:
        return 1 if self._visible else 0

    def is_visible(self) -> bool:
        return self._visible


class FakePage:
    def __init__(self, html: str):
        self.html = html
        self.clicked: list[str] = []

    def content(self) -> str:
        return self.html

    def goto(self, url: str) -> None:
        self.last_url = url

    def click(self, sel: str) -> None:
        self.clicked.append(sel)

    def locator(self, sel: str) -> FakeLocator:
        return FakeLocator(sel.lower() in self.html.lower())


def _job(**kw):
    base = dict(
        job_key="jobsdb:1",
        title="AI Application",
        company="Acme",
        location="Hong Kong",
        url="https://hk.jobsdb.com/job/1",
        source="jobsdb",
        status=JobStatus.queued,
    )
    base.update(kw)
    return Job(**base)


def test_captcha_stops():
    page = FakePage("<html>请完成验证码 captcha</html>")
    result = apply_job(page, _job())
    assert result.status == JobStatus.needs_human
    assert result.ok is False


def test_happy_path_updates_db(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    job = _job()
    db.upsert_job(job)
    page = FakePage("<html><button>Apply</button></html>")
    results = run_apply_batch(db, "jobsdb", cap=5, page=page)
    assert results[0].status == JobStatus.applied
    stored = db.get_job("jobsdb:1")
    assert stored.status == JobStatus.applied
    assert stored.applied_at is not None
    assert page.clicked
