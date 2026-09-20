import tempfile
import unittest

import tests._path  # noqa: F401
from job_agent.config import set_home
from job_agent.models import Job, Profile
from job_agent.writer import build_cover_letter


class StoreTests(unittest.TestCase):
    def test_roundtrip(self):
        from job_agent import store

        with tempfile.TemporaryDirectory() as raw:
            set_home(raw)
            job = Job(
                job_id="9",
                title="X",
                company="Y",
                url="https://hk.jobsdb.com/job/9",
                score=70,
            )
            store.upsert_jobs([job])
            loaded = store.get_job("9")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.company, "Y")
            store.set_status("9", "applied")
            self.assertEqual(store.get_job("9").status, "applied")


class PacketTests(unittest.TestCase):
    def test_cover_letter(self):
        job = Job(job_id="1", title="AI Engineer", company="Acme", url="u")
        letter = build_cover_letter(job, Profile(full_name="Pat", email="p@e.com"))
        self.assertIn("AI Engineer", letter)
        self.assertIn("Acme", letter)

    def test_write_packet(self):
        from job_agent import writer

        job = Job(
            job_id="1",
            title="AI Engineer",
            company="Acme",
            url="https://hk.jobsdb.com/job/1",
        )
        with tempfile.TemporaryDirectory() as raw:
            set_home(raw)
            path = writer.write_packet(job, Profile(full_name="Pat"))
            text = path.read_text(encoding="utf-8")
            self.assertIn("Cloudflare", text)
            self.assertIn("https://hk.jobsdb.com/job/1", text)
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
