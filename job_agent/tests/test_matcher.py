import unittest

import tests._path  # noqa: F401
from job_agent.matcher import score_job
from job_agent.models import Job, Profile


def _job(**kwargs):
    base = dict(
        job_id="1",
        title="AI Engineer",
        company="Acme",
        url="https://hk.jobsdb.com/job/1",
        teaser="Python and LLM work in Hong Kong",
    )
    base.update(kwargs)
    return Job(**base)


class MatcherTests(unittest.TestCase):
    def test_role_and_skill_boost(self):
        profile = Profile(
            target_roles=["AI engineer"],
            skills=["python", "llm"],
            locations=["Hong Kong"],
        )
        job = score_job(_job(), profile)
        self.assertGreaterEqual(job.score, 40)
        self.assertTrue(any("role" in r for r in job.reasons))

    def test_avoid_penalty(self):
        profile = Profile(avoid=["unpaid intern"])
        job = score_job(_job(teaser="This is an unpaid intern role"), profile)
        self.assertLess(job.score, 20)


if __name__ == "__main__":
    unittest.main()
