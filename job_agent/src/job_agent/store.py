from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from . import config
from .models import InboxItem, Job


def connect() -> sqlite3.Connection:
    config.ensure_dirs()
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    _init(conn)
    return conn


def _init(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            url TEXT,
            location TEXT,
            salary TEXT,
            work_type TEXT,
            arrangement TEXT,
            classification TEXT,
            teaser TEXT,
            bullets_json TEXT,
            listed_at TEXT,
            score INTEGER,
            reasons_json TEXT,
            status TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS emails (
            uid TEXT PRIMARY KEY,
            subject TEXT,
            sender TEXT,
            date TEXT,
            snippet TEXT,
            label TEXT,
            confidence TEXT,
            job_hint TEXT
        );
        """
    )
    conn.commit()


def upsert_jobs(jobs: list[Job]) -> int:
    conn = connect()
    count = 0
    for job in jobs:
        existing = conn.execute(
            "SELECT status FROM jobs WHERE job_id = ?", (job.job_id,)
        ).fetchone()
        status = existing["status"] if existing else job.status
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, title, company, url, location, salary, work_type,
                arrangement, classification, teaser, bullets_json, listed_at,
                score, reasons_json, status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(job_id) DO UPDATE SET
                title=excluded.title,
                company=excluded.company,
                url=excluded.url,
                location=excluded.location,
                salary=excluded.salary,
                work_type=excluded.work_type,
                arrangement=excluded.arrangement,
                classification=excluded.classification,
                teaser=excluded.teaser,
                bullets_json=excluded.bullets_json,
                listed_at=excluded.listed_at,
                score=excluded.score,
                reasons_json=excluded.reasons_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                job.job_id,
                job.title,
                job.company,
                job.url,
                job.location,
                job.salary,
                job.work_type,
                job.arrangement,
                job.classification,
                job.teaser,
                json.dumps(job.bullets, ensure_ascii=False),
                job.listed_at,
                job.score,
                json.dumps(job.reasons, ensure_ascii=False),
                status,
            ),
        )
        count += 1
    conn.commit()
    conn.close()
    return count


def set_status(job_id: str, status: str) -> None:
    conn = connect()
    conn.execute(
        "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
        (status, job_id),
    )
    conn.commit()
    conn.close()


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        job_id=row["job_id"],
        title=row["title"] or "",
        company=row["company"] or "",
        url=row["url"] or "",
        location=row["location"] or "",
        salary=row["salary"] or "",
        work_type=row["work_type"] or "",
        arrangement=row["arrangement"] or "",
        classification=row["classification"] or "",
        teaser=row["teaser"] or "",
        bullets=json.loads(row["bullets_json"] or "[]"),
        listed_at=row["listed_at"] or "",
        score=int(row["score"] or 0),
        reasons=json.loads(row["reasons_json"] or "[]"),
        status=row["status"] or "new",
    )


def list_jobs(status: str | None = None, limit: int = 50) -> list[Job]:
    conn = connect()
    if status:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY score DESC, listed_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY score DESC, listed_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [_row_to_job(row) for row in rows]


def get_job(job_id: str) -> Job | None:
    conn = connect()
    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    conn.close()
    return _row_to_job(row) if row else None


def counts() -> dict[str, int]:
    conn = connect()
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status").fetchall()
    conn.close()
    return {row["status"]: row["n"] for row in rows}


def upsert_emails(items: list[InboxItem]) -> int:
    conn = connect()
    for item in items:
        conn.execute(
            """
            INSERT INTO emails (uid, subject, sender, date, snippet, label, confidence, job_hint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
                subject=excluded.subject,
                sender=excluded.sender,
                date=excluded.date,
                snippet=excluded.snippet,
                label=excluded.label,
                confidence=excluded.confidence,
                job_hint=excluded.job_hint
            """,
            (
                item.uid,
                item.subject,
                item.sender,
                item.date,
                item.snippet,
                item.label,
                item.confidence,
                item.job_hint,
            ),
        )
    conn.commit()
    conn.close()
    return len(items)


def list_emails(label: str | None = None, limit: int = 50) -> list[InboxItem]:
    conn = connect()
    if label:
        rows = conn.execute(
            "SELECT * FROM emails WHERE label = ? ORDER BY date DESC LIMIT ?",
            (label, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM emails ORDER BY date DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [
        InboxItem(
            uid=row["uid"],
            subject=row["subject"],
            sender=row["sender"],
            date=row["date"],
            snippet=row["snippet"],
            label=row["label"],
            confidence=row["confidence"],
            job_hint=row["job_hint"],
        )
        for row in rows
    ]


def email_counts() -> dict[str, int]:
    conn = connect()
    rows = conn.execute("SELECT label, COUNT(*) AS n FROM emails GROUP BY label").fetchall()
    conn.close()
    return {row["label"]: row["n"] for row in rows}


def db_path() -> Path:
    return config.DB_PATH
