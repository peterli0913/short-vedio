import unittest

import tests._path  # noqa: F401
from job_agent.classifier import classify_email, parse_mbox_like


class ClassifierTests(unittest.TestCase):
    def test_interview(self):
        self.assertEqual(
            classify_email("Invitation to interview", "can we schedule a call")[0],
            "interview",
        )

    def test_reject(self):
        self.assertEqual(
            classify_email("Update", "Unfortunately we will not be progressing")[0],
            "reject",
        )

    def test_request(self):
        self.assertEqual(
            classify_email("Application", "Please provide your expected salary")[0],
            "info_request",
        )

    def test_parse_example(self):
        text = (
            "From: a@b.com\nSubject: Invitation to interview — AI Engineer\n\nHi\n"
            "\n---\n"
            "From: c@d.com\nSubject: Update\n\nUnfortunately we will not be progressing\n"
        )
        rows = parse_mbox_like(text)
        self.assertEqual(len(rows), 2)
        self.assertIn("interview", rows[0]["subject"].lower())

    def test_parse_bundled_example_file(self):
        from pathlib import Path

        from job_agent.classifier import to_inbox_item

        text = (Path(__file__).resolve().parents[1] / "data" / "emails.example.txt").read_text(
            encoding="utf-8"
        )
        rows = parse_mbox_like(text)
        self.assertEqual(len(rows), 3)
        labels = [to_inbox_item(r["uid"], r["subject"], r["sender"], r["date"], r["snippet"]).label for r in rows]
        self.assertEqual(labels, ["interview", "reject", "info_request"])


if __name__ == "__main__":
    unittest.main()
