from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Job:
    job_id: str
    title: str
    company: str
    url: str
    location: str = ""
    salary: str = ""
    work_type: str = ""
    arrangement: str = ""
    classification: str = ""
    teaser: str = ""
    bullets: list[str] = field(default_factory=list)
    listed_at: str = ""
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    status: str = "new"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Profile:
    full_name: str = ""
    email: str = ""
    phone: str = ""
    target_roles: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    years_experience: int = 0
    locations: list[str] = field(default_factory=list)
    must_have: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)
    salary_min_hkd: int = 0
    languages: list[str] = field(default_factory=list)
    summary: str = ""
    highlights: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class InboxItem:
    uid: str
    subject: str
    sender: str
    date: str
    snippet: str
    label: str
    confidence: str
    job_hint: str = ""
