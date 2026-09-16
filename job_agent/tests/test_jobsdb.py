import json
import unittest
from pathlib import Path

import tests._path  # noqa: F401
from job_agent.jobsdb import job_from_payload, jobs_from_urls, parse_job_id

FIXTURE = Path(__file__).parent / "fixtures" / "search.json"


class JobsDBTests(unittest.TestCase):
    def test_parse_job_id(self):
        self.assertEqual(parse_job_id("94663084"), "94663084")
        self.assertEqual(parse_job_id("https://hk.jobsdb.com/job/94663084"), "94663084")
        self.assertEqual(
            parse_job_id("see https://hk.jobsdb.com/job/94663084?type=standard"),
            "94663084",
        )
        self.assertIsNone(parse_job_id("not a job"))

    def test_job_from_fixture(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        job = job_from_payload(payload["data"][0])
        self.assertEqual(job.job_id, "94663084")
        self.assertTrue("AI" in job.title or "Engineer" in job.title)
        self.assertTrue(job.company)
        self.assertTrue(job.url.endswith("/job/94663084"))
        self.assertTrue(job.location)

    def test_jobs_from_urls(self):
        jobs = jobs_from_urls(["https://hk.jobsdb.com/job/111", "junk", "222"])
        self.assertEqual([j.job_id for j in jobs], ["111", "222"])


if __name__ == "__main__":
    unittest.main()
