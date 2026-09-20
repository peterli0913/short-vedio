import tempfile
import unittest

import tests._path  # noqa: F401
from job_agent.cli import cmd_digest, cmd_shortlist
from job_agent.config import set_home
from job_agent.models import Job


class DigestTests(unittest.TestCase):
    def test_digest_lists_ready_packets(self):
        from job_agent import store

        with tempfile.TemporaryDirectory() as raw:
            set_home(raw)
            store.upsert_jobs(
                [
                    Job(
                        job_id="1",
                        title="AI",
                        company="Z",
                        url="u",
                        score=90,
                        status="packet_ready",
                    )
                ]
            )
            self.assertEqual(cmd_digest(), 0)
            self.assertEqual(cmd_shortlist(10, "packet_ready"), 0)


if __name__ == "__main__":
    unittest.main()
