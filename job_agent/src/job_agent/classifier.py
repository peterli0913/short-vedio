from __future__ import annotations

import re

from .models import InboxItem, Job

INTERVIEW = (
    "interview",
    "available for a call",
    "schedule a call",
    "phone screen",
    "first round",
    "meet with",
    "invitation to interview",
    "面试",
    "面試",
    "电面",
    "視訊",
    "视讯",
)
ASSESSMENT = (
    "assessment",
    "online test",
    "coding test",
    "case study",
    "assignment",
    "hackerrank",
    "测评",
    "笔试",
    "筆試",
)
REQUEST = (
    "could you send",
    "please provide",
    "more information",
    "availability",
    "right to work",
    "expected salary",
    "kindly share",
    "补充",
    "请提供",
)
REJECT = (
    "unfortunately",
    "not moving forward",
    "other candidates",
    "will not be progressing",
    "unsuccessful",
    "we regret",
    "not selected",
    "抱歉",
    "未能通过",
    "未能通過",
    "不获录用",
    "不獲錄用",
)
AUTO = ("do not reply", "noreply", "no-reply", "out of office", "automatic reply")


def _blob(subject: str, snippet: str, sender: str) -> str:
    return f"{subject}\n{snippet}\n{sender}".lower()


def _contains(blob: str, phrases: tuple[str, ...]) -> list[str]:
    return [p for p in phrases if p in blob]


def classify_email(subject: str, snippet: str, sender: str = "") -> tuple[str, str]:
    blob = _blob(subject, snippet, sender)
    if _contains(blob, REJECT):
        return "reject", "high"
    if _contains(blob, INTERVIEW):
        return "interview", "high"
    if _contains(blob, ASSESSMENT):
        return "assessment", "high"
    if _contains(blob, REQUEST):
        return "info_request", "medium"
    if _contains(blob, AUTO) and "thank you for applying" in blob:
        return "ack", "medium"
    if "thank you for applying" in blob or "we have received your application" in blob:
        return "ack", "medium"
    return "other", "low"


def hint_job(subject: str, snippet: str, jobs: list[Job]) -> str:
    blob = _blob(subject, snippet, "")
    for job in jobs:
        if job.company and job.company.lower() in blob:
            return f"{job.job_id} {job.company}"
        if job.title and job.title.lower() in blob:
            return f"{job.job_id} {job.title}"
    return ""


def to_inbox_item(
    uid: str,
    subject: str,
    sender: str,
    date: str,
    snippet: str,
    jobs: list[Job] | None = None,
) -> InboxItem:
    label, confidence = classify_email(subject, snippet, sender)
    return InboxItem(
        uid=uid,
        subject=subject,
        sender=sender,
        date=date,
        snippet=snippet[:500],
        label=label,
        confidence=confidence,
        job_hint=hint_job(subject, snippet, jobs or []),
    )


def parse_mbox_like(text: str) -> list[dict[str, str]]:
    """Parse a pasted dump. Blocks split by a --- line, or a new From: header."""
    text = (text or "").strip()
    if not text:
        return []
    chunks = re.split(r"\n(?:-{3,}|={3,})\s*\n", text)
    if len(chunks) == 1:
        chunks = re.split(r"\n(?=From:\s)", text)
    items = []
    for i, chunk in enumerate(chunks, start=1):
        chunk = chunk.strip()
        if not chunk or set(chunk) <= {"-", "="}:
            continue
        subject = _field(chunk, "Subject") or chunk.splitlines()[0][:120]
        sender = _field(chunk, "From") or ""
        date = _field(chunk, "Date") or ""
        items.append(
            {
                "uid": f"paste-{i}-{abs(hash(chunk)) % 10_000_000}",
                "subject": subject,
                "sender": sender,
                "date": date,
                "snippet": chunk[:800],
            }
        )
    return items


def _field(chunk: str, name: str) -> str:
    match = re.search(rf"^{name}:\s*(.+)$", chunk, re.I | re.M)
    return match.group(1).strip() if match else ""
