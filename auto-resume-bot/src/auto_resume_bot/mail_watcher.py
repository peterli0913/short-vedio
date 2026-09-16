from __future__ import annotations

import imaplib
import os
from datetime import datetime, timezone
from email import message_from_bytes
from email.header import decode_header
from email.message import Message

from auto_resume_bot.db import Database
from auto_resume_bot.models import JobStatus, MailCategory, MailEvent

INTERVIEW = ("interview", "面试", "面試", "schedule a call", "phone screen")
REJECT = ("很遗憾", "遗憾", "unfortunately", "not moving forward", "unsuccessful", "未能")
DOCS = ("请补充", "补充材料", "please provide", "kindly send", "more information")
SYSTEM = ("do not reply", "noreply", "no-reply", "out of office")


def classify_subject(subject: str, body: str) -> MailCategory:
    blob = f"{subject}\n{body}".lower()
    if any(p.lower() in blob for p in REJECT):
        return MailCategory.reject
    if any(p.lower() in blob for p in INTERVIEW):
        return MailCategory.interview
    if any(p.lower() in blob for p in DOCS):
        return MailCategory.docs_needed
    if any(p.lower() in blob for p in SYSTEM):
        return MailCategory.system
    return MailCategory.other


def match_job_key(db: Database, subject: str, body: str, company_hints: list[str] | None = None) -> str | None:
    blob = f"{subject}\n{body}".lower()
    hints = [h for h in (company_hints or []) if h]
    hits: list[str] = []
    for job in db.list_jobs(limit=300):
        if job.status not in {JobStatus.applied, JobStatus.queued, JobStatus.applying}:
            if not hints:
                continue
        company = (job.company or "").strip()
        if company and company.lower() in blob:
            hits.append(job.job_key)
            continue
        if any(h.lower() in blob and h.lower() in company.lower() for h in hints):
            hits.append(job.job_key)
    if len(hits) == 1:
        return hits[0]
    return None


def poll_account(client, account_id: str, db: Database) -> list[MailEvent]:
    events: list[MailEvent] = []
    messages = client.fetch_messages()
    for raw in messages:
        subject = getattr(raw, "subject", "") or ""
        body = getattr(raw, "body", "") or getattr(raw, "snippet", "") or ""
        from_addr = getattr(raw, "from_addr", "") or getattr(raw, "sender", "") or ""
        received = getattr(raw, "received_at", None) or datetime.now(timezone.utc)
        uid = str(getattr(raw, "uid", "") or getattr(raw, "id", "") or f"{account_id}-{subject}")
        event = MailEvent(
            id=f"{account_id}:{uid}",
            account=account_id,
            subject=subject,
            from_addr=from_addr,
            received_at=received,
            category=classify_subject(subject, body),
            job_key=match_job_key(db, subject, body),
            snippet=body[:500],
        )
        db.add_mail_event(event)
        if event.job_key:
            db.attach_mail_to_job(event.id, event.job_key)
        events.append(event)
    return events


def _decode(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for data, enc in parts:
        if isinstance(data, bytes):
            out.append(data.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(data)
    return "".join(out)


def _snippet(msg: Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True) or b""
                return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    payload = msg.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    return str(msg.get_payload() or "")


class StdlibImapClient:
    """Read-only IMAP. Never deletes or sends."""

    def __init__(self, host: str, user: str, password: str, folder: str = "INBOX", limit: int = 30):
        self.host = host
        self.user = user
        self.password = password
        self.folder = folder
        self.limit = limit

    def fetch_messages(self) -> list[object]:
        client = imaplib.IMAP4_SSL(self.host)
        try:
            client.login(self.user, self.password)
            client.select(self.folder, readonly=True)
            _, data = client.search(None, "ALL")
            ids = (data[0] or b"").split()[-self.limit :]
            out = []
            for raw_id in reversed(ids):
                _, fetched = client.fetch(raw_id, "(RFC822)")
                if not fetched or not fetched[0]:
                    continue
                body = fetched[0][1]
                if not isinstance(body, (bytes, bytearray)):
                    continue
                msg = message_from_bytes(body)

                class _Msg:
                    pass

                item = _Msg()
                item.uid = raw_id.decode()
                item.subject = _decode(msg.get("Subject"))
                item.from_addr = _decode(msg.get("From"))
                item.body = _snippet(msg)
                item.received_at = datetime.now(timezone.utc)
                out.append(item)
            return out
        finally:
            try:
                client.logout()
            except Exception:
                pass


def client_from_account(account: dict) -> StdlibImapClient:
    password = os.environ.get(account.get("password_env") or "", "")
    if not password:
        raise RuntimeError(f"Missing env {account.get('password_env')} for IMAP (do not put the password in yaml)")
    return StdlibImapClient(
        host=account["host"],
        user=account["user"],
        password=password,
    )
