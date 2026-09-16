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
