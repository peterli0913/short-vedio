import tempfile
import unittest
from pathlib import Path

import tests._path  # noqa: F401
from job_agent.cli import main
from job_agent.config import set_home
from job_agent.drafts import build_reply_draft, suggested_action, write_drafts
from job_agent.models import InboxItem, Job, Profile
from job_agent.web import render_index


class DraftTests(unittest.TestCase):
    def test_interview_draft_is_bilingual(self):
        item = InboxItem(
            uid="1",
            subject="Invitation to interview",
            sender="hr@acme.com",
            date="",
            snippet="",
            label="interview",
            confidence="high",
        )
        text = build_reply_draft(item, Profile(full_name="Pat", email="p@e.com"))
        self.assertIn("Thank you for the interview invitation", text)
        self.assertIn("感谢邀请面试", text)
        self.assertEqual(suggested_action("interview"), "draft + calendar")

    def test_write_skips_ack(self):
        with tempfile.TemporaryDirectory() as raw:
            set_home(raw)
            paths = write_drafts(
                [
                    InboxItem(
                        uid="a",
                        subject="got it",
                        sender="n@e.com",
                        date="",
                        snippet="",
                        label="ack",
                        confidence="medium",
                    ),
                    InboxItem(
                        uid="b",
                        subject="call?",
                        sender="h@e.com",
                        date="",
                        snippet="",
                        label="interview",
                        confidence="high",
                    ),
                ],
                Profile(full_name="Pat"),
            )
            self.assertEqual(len(paths), 1)
            self.assertTrue(paths[0].exists())


class SetupCliTests(unittest.TestCase):
    def test_setup_copies_examples(self):
        with tempfile.TemporaryDirectory() as raw:
            self.assertEqual(main(["--home", raw, "setup"]), 0)
            self.assertTrue((Path(raw) / "profile.json").exists())
            self.assertTrue((Path(raw) / "resume.md").exists())
            example = Path(__file__).resolve().parents[1] / "data" / "emails.example.txt"
            self.assertEqual(main(["--home", raw, "classify", "--file", str(example)]), 0)
            self.assertEqual(main(["--home", raw, "drafts"]), 0)
            self.assertTrue(any((Path(raw) / "replies").glob("*.md")))


class WebTests(unittest.TestCase):
    def test_index_renders(self):
        from job_agent import store

        with tempfile.TemporaryDirectory() as raw:
            set_home(raw)
            store.upsert_jobs(
                [
                    Job(
                        job_id="94663084",
                        title="AI Engineer",
                        company="Acme",
                        url="https://hk.jobsdb.com/job/94663084",
                        score=80,
                    )
                ]
            )
            page = render_index()
            self.assertIn("求职工作台", page)
            self.assertIn("94663084", page)
            self.assertIn("Acme", page)


if __name__ == "__main__":
    unittest.main()
