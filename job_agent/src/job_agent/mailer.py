from __future__ import annotations

import email
import imaplib
import os
from email.header import decode_header
from email.message import Message

from .classifier import to_inbox_item
from .models import InboxItem, Job


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
            if part.get_content_type() == "text/plain" and "attachment" not in str(
                part.get("Content-Disposition") or ""
            ):
                payload = part.get_payload(decode=True) or b""
                return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    payload = msg.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    return str(msg.get_payload() or "")


def fetch_imap(
    limit: int = 30,
    folder: str = "INBOX",
    jobs: list[Job] | None = None,
) -> list[InboxItem]:
    host = os.environ.get("JOB_AGENT_IMAP_HOST", "imap.gmail.com")
    user = os.environ.get("JOB_AGENT_IMAP_USER") or os.environ.get("JOB_AGENT_EMAIL")
    password = os.environ.get("JOB_AGENT_IMAP_PASSWORD")
    if not user or not password:
        raise RuntimeError(
            "Set JOB_AGENT_IMAP_USER and JOB_AGENT_IMAP_PASSWORD "
            "(Gmail: use an App Password, never your login password)."
        )
    client = imaplib.IMAP4_SSL(host)
    try:
        client.login(user, password)
        client.select(folder, readonly=True)
        _, data = client.search(None, "ALL")
        ids = (data[0] or b"").split()[-limit:]
        items: list[InboxItem] = []
        for raw_id in reversed(ids):
            _, fetched = client.fetch(raw_id, "(RFC822)")
            if not fetched or not fetched[0]:
                continue
            body = fetched[0][1]
            if not isinstance(body, (bytes, bytearray)):
                continue
            msg = email.message_from_bytes(body)
            items.append(
                to_inbox_item(
                    uid=raw_id.decode(),
                    subject=_decode(msg.get("Subject")),
                    sender=_decode(msg.get("From")),
                    date=_decode(msg.get("Date")),
                    snippet=_snippet(msg),
                    jobs=jobs,
                )
            )
        return items
    finally:
        try:
            client.logout()
        except Exception:
            pass
