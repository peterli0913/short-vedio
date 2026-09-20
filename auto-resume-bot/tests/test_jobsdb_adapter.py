from pathlib import Path

from auto_resume_bot.adapters.jobsdb import JobsDbAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "jobsdb_sample.html"


def test_parse_listing_html():
    html = FIXTURE.read_text(encoding="utf-8")
    jobs = JobsDbAdapter(hkd_to_cny=0.92).parse_listing_html(html)
    assert len(jobs) == 2
    assert jobs[0].job_key == "jobsdb:111"
    assert jobs[0].title == "AI Application Engineer"
    assert jobs[0].company == "Acme HK"
    assert jobs[0].location == "Hong Kong"
    assert jobs[0].salary_rmb_min == 55200
    assert jobs[1].job_key == "jobsdb:222"
    assert "Harbor" in jobs[1].company


def test_fetch_jobs_searches_each_keyword():
    calls: list[str] = []

    class FakeResp:
        def __init__(self, job_id: str):
            self._job_id = job_id

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {
                        "id": self._job_id,
                        "title": "AI Application",
                        "companyName": "Acme",
                        "locations": [{"label": "Hong Kong"}],
                        "teaser": "smart manufacturing",
                    }
                ]
            }

    class FakeClient:
        def get(self, url: str):
            if "MES" in url:
                calls.append("MES")
                return FakeResp("1")
            calls.append("other")
            return FakeResp("2")

        def close(self):
            return None

    jobs = JobsDbAdapter(keywords=["MES", "AI application"], client=FakeClient()).fetch_jobs()
    assert {j.job_key for j in jobs} == {"jobsdb:1", "jobsdb:2"}
    assert calls == ["MES", "other"]
