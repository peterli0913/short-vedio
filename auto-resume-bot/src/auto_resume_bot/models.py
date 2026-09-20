from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    discovered = "discovered"
    scored = "scored"
    queued = "queued"
    applying = "applying"
    applied = "applied"
    failed = "failed"
    needs_human = "needs_human"
    skipped = "skipped"


class Job(BaseModel):
    job_key: str
    title: str
    company: str
    location: str
    salary_raw: str | None = None
    salary_rmb_min: int | None = None
    url: str
    source: str
    description: str = ""
    score: int | None = None
    score_reason: str | None = None
    status: JobStatus = JobStatus.discovered
    applied_at: datetime | None = None
    mail_event_ids: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None


class Application(BaseModel):
    job_key: str
    applied_at: datetime
    mail_event_ids: list[str] = Field(default_factory=list)


class MailCategory(str, Enum):
    interview = "interview"
    reject = "reject"
    docs_needed = "docs_needed"
    system = "system"
    other = "other"


class MailEvent(BaseModel):
    id: str
    account: str
    subject: str
    from_addr: str
    received_at: datetime
    category: MailCategory
    job_key: str | None = None
    snippet: str = ""
