from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from auto_resume_bot.models import Job, JobStatus, MailCategory, MailEvent


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        conn = self._connect()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_key TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                salary_raw TEXT,
                salary_rmb_min INTEGER,
                url TEXT,
                source TEXT,
                description TEXT,
                score INTEGER,
                score_reason TEXT,
                status TEXT,
                applied_at TEXT,
                mail_event_ids TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS mail_events (
                id TEXT PRIMARY KEY,
                account TEXT,
                subject TEXT,
                from_addr TEXT,
                received_at TEXT,
                category TEXT,
                job_key TEXT,
                snippet TEXT
            );
            """
        )
        conn.commit()
        conn.close()

    def upsert_job(self, job: Job) -> None:
        now = _now()
        job.updated_at = now
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO jobs (
                job_key, title, company, location, salary_raw, salary_rmb_min,
                url, source, description, score, score_reason, status,
                applied_at, mail_event_ids, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_key) DO UPDATE SET
                title=excluded.title,
                company=excluded.company,
                location=excluded.location,
                salary_raw=excluded.salary_raw,
                salary_rmb_min=excluded.salary_rmb_min,
                url=excluded.url,
                source=excluded.source,
                description=excluded.description,
                score=excluded.score,
                score_reason=excluded.score_reason,
                status=excluded.status,
                applied_at=excluded.applied_at,
                mail_event_ids=excluded.mail_event_ids,
                updated_at=excluded.updated_at
            """,
            (
                job.job_key,
                job.title,
                job.company,
                job.location,
                job.salary_raw,
                job.salary_rmb_min,
                job.url,
                job.source,
                job.description,
                job.score,
                job.score_reason,
                job.status.value,
                job.applied_at.isoformat() if job.applied_at else None,
                json.dumps(job.mail_event_ids, ensure_ascii=False),
                now.isoformat(),
            ),
        )
        conn.commit()
        conn.close()

    def get_job(self, job_key: str) -> Job | None:
        conn = self._connect()
        row = conn.execute("SELECT * FROM jobs WHERE job_key = ?", (job_key,)).fetchone()
        conn.close()
        return self._row_to_job(row) if row else None

    def list_jobs_by_status(self, status: JobStatus | str, limit: int = 200) -> list[Job]:
        value = status.value if isinstance(status, JobStatus) else status
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
            (value, limit),
        ).fetchall()
        conn.close()
        return [self._row_to_job(row) for row in rows]

    def list_jobs(self, limit: int = 500) -> list[Job]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [self._row_to_job(row) for row in rows]

    def count_applied_today(self, source: str) -> int:
        today = _now().date().isoformat()
        conn = self._connect()
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM jobs
            WHERE source = ? AND status = ? AND substr(applied_at, 1, 10) = ?
            """,
            (source, JobStatus.applied.value, today),
        ).fetchone()
        conn.close()
        return int(row["n"] if row else 0)

    def add_mail_event(self, event: MailEvent) -> None:
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO mail_events (
                id, account, subject, from_addr, received_at, category, job_key, snippet
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                subject=excluded.subject,
                from_addr=excluded.from_addr,
                received_at=excluded.received_at,
                category=excluded.category,
                job_key=excluded.job_key,
                snippet=excluded.snippet
            """,
            (
                event.id,
                event.account,
                event.subject,
                event.from_addr,
                event.received_at.isoformat(),
                event.category.value,
                event.job_key,
                event.snippet,
            ),
        )
        conn.commit()
        conn.close()

    def attach_mail_to_job(self, mail_id: str, job_key: str) -> None:
        conn = self._connect()
        conn.execute("UPDATE mail_events SET job_key = ? WHERE id = ?", (job_key, mail_id))
        row = conn.execute("SELECT mail_event_ids FROM jobs WHERE job_key = ?", (job_key,)).fetchone()
        if row:
            ids = json.loads(row["mail_event_ids"] or "[]")
            if mail_id not in ids:
                ids.append(mail_id)
            conn.execute(
                "UPDATE jobs SET mail_event_ids = ?, updated_at = ? WHERE job_key = ?",
                (json.dumps(ids, ensure_ascii=False), _now().isoformat(), job_key),
            )
        conn.commit()
        conn.close()

    def list_mail_events(self, limit: int = 200) -> list[MailEvent]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM mail_events ORDER BY received_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [self._row_to_mail(row) for row in rows]

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        return Job(
            job_key=row["job_key"],
            title=row["title"] or "",
            company=row["company"] or "",
            location=row["location"] or "",
            salary_raw=row["salary_raw"],
            salary_rmb_min=row["salary_rmb_min"],
            url=row["url"] or "",
            source=row["source"] or "",
            description=row["description"] or "",
            score=row["score"],
            score_reason=row["score_reason"],
            status=JobStatus(row["status"]),
            applied_at=_parse_dt(row["applied_at"]),
            mail_event_ids=json.loads(row["mail_event_ids"] or "[]"),
            updated_at=_parse_dt(row["updated_at"]),
        )

    def _row_to_mail(self, row: sqlite3.Row) -> MailEvent:
        received = _parse_dt(row["received_at"]) or _now()
        return MailEvent(
            id=row["id"],
            account=row["account"] or "",
            subject=row["subject"] or "",
            from_addr=row["from_addr"] or "",
            received_at=received,
            category=MailCategory(row["category"]),
            job_key=row["job_key"],
            snippet=row["snippet"] or "",
        )
