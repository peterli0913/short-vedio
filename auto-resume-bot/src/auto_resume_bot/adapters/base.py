from __future__ import annotations

from typing import Protocol

from auto_resume_bot.models import Job


class SourceAdapter(Protocol):
    name: str

    def fetch_jobs(self) -> list[Job]:
        ...
