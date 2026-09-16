from __future__ import annotations

from collections import defaultdict
from datetime import date

from auto_resume_bot.db import Database
from auto_resume_bot.models import JobStatus, MailCategory


def build_digest(db: Database, day: date) -> str:
    jobs = db.list_jobs(limit=500)
    mails = db.list_mail_events(limit=200)
    by_status: dict[str, list] = defaultdict(list)
    for job in jobs:
        by_status[job.status.value].append(job)

    def _lines(items, empty="(none)"):
        if not items:
            return [f"- {empty}"]
        out = []
        for job in items[:20]:
            extra = f" score={job.score}" if job.score is not None else ""
            out.append(f"- {job.company} — {job.title} ({job.job_key}{extra})")
        return out

    day_mails = [m for m in mails if m.received_at.date() == day] or mails
    mail_by = defaultdict(list)
    for item in day_mails:
        mail_by[item.category].append(item)

    def _mail(cat: MailCategory):
        rows = mail_by.get(cat) or []
        if not rows:
            return ["- (none)"]
        return [f"- {m.subject} ({m.from_addr})" for m in rows[:15]]

    parts = [
        f"# Auto-resume digest {day.isoformat()}",
        "",
        "## New discovered",
        *_lines(by_status.get(JobStatus.discovered.value)),
        "",
        "## Hard-filter passes / scored / queued",
        *_lines(by_status[JobStatus.queued.value] + by_status[JobStatus.scored.value]),
        "",
        "## Auto-applied",
        *_lines(by_status.get(JobStatus.applied.value)),
        "",
        "## Needs human",
        *_lines(by_status.get(JobStatus.needs_human.value)),
        "",
        "## Failed",
        *_lines(by_status.get(JobStatus.failed.value)),
        "",
        "## Skipped",
        *_lines(by_status.get(JobStatus.skipped.value)),
        "",
        "## Mail — interview",
        *_mail(MailCategory.interview),
        "",
        "## Mail — reject",
        *_mail(MailCategory.reject),
        "",
        "## Mail — docs needed",
        *_mail(MailCategory.docs_needed),
        "",
    ]
    return "\n".join(parts) + "\n"
