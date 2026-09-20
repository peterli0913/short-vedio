from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .models import Job

SEARCH_URL = "https://hk.jobsdb.com/api/jobsearch/v5/search"
JOB_URL = "https://hk.jobsdb.com/job/{job_id}"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
JOB_ID_RE = re.compile(r"(?:jobsdb\.com/job/|/job/)(\d+)", re.I)


class JobsDBError(RuntimeError):
    pass


def parse_job_id(text: str) -> str | None:
    text = text.strip()
    if text.isdigit():
        return text
    match = JOB_ID_RE.search(text)
    return match.group(1) if match else None


def _arrangements(raw: Any) -> str:
    if isinstance(raw, dict):
        labels = []
        for item in raw.get("data") or []:
            label = (item or {}).get("label") or {}
            text = label.get("text") if isinstance(label, dict) else None
            if text:
                labels.append(text)
        return ", ".join(labels)
    if isinstance(raw, list):
        return ", ".join(str(x) for x in raw)
    return ""


def _work_types(raw: Any) -> str:
    if isinstance(raw, list):
        return ", ".join(str(x) for x in raw)
    return str(raw or "")


def job_from_payload(item: dict[str, Any]) -> Job:
    advertiser = item.get("advertiser") or {}
    employer = item.get("employer") or {}
    company = (
        item.get("companyName")
        or employer.get("name")
        or advertiser.get("description")
        or ""
    )
    locations = item.get("locations") or []
    location = ", ".join(
        loc.get("label") for loc in locations if isinstance(loc, dict) and loc.get("label")
    )
    classifications = item.get("classifications") or []
    class_bits = []
    for row in classifications:
        top = ((row or {}).get("classification") or {}).get("description")
        sub = ((row or {}).get("subclassification") or {}).get("description")
        class_bits.append(" / ".join(part for part in (top, sub) if part))
    job_id = str(item.get("id") or "")
    return Job(
        job_id=job_id,
        title=item.get("title") or "",
        company=company,
        url=JOB_URL.format(job_id=job_id),
        location=location,
        salary=item.get("salaryLabel") or "",
        work_type=_work_types(item.get("workTypes")),
        arrangement=_arrangements(item.get("workArrangements")),
        classification="; ".join(class_bits),
        teaser=item.get("teaser") or "",
        bullets=[str(x) for x in (item.get("bulletPoints") or []) if x],
        listed_at=item.get("listingDate") or "",
    )


def search_jobs(
    keywords: str,
    pages: int = 1,
    page_size: int = 20,
    timeout: int = 20,
    where: str = "",
) -> tuple[list[Job], int]:
    """Search via JobsDB public JSON (same payload the site uses).

    HTML job pages are behind Cloudflare; this JSON search is not.
    """
    jobs: list[Job] = []
    total = 0
    for page in range(1, max(1, pages) + 1):
        query = {
            "siteKey": "HK-Main",
            "keywords": keywords,
            "page": str(page),
            "pageSize": str(page_size),
        }
        if where:
            query["where"] = where
        params = urllib.parse.urlencode(query)
        req = urllib.request.Request(
            f"{SEARCH_URL}?{params}",
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Accept-Language": "en-HK,en;q=0.9,zh-HK;q=0.8",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise JobsDBError(
                f"JobsDB search HTTP {exc.code}. If this is 403, the JSON endpoint "
                "is blocked in this network — import job URLs instead."
            ) from exc
        except urllib.error.URLError as exc:
            raise JobsDBError(f"JobsDB search failed: {exc.reason}") from exc
        total = int(payload.get("totalCount") or 0)
        for item in payload.get("data") or []:
            if isinstance(item, dict) and item.get("id"):
                jobs.append(job_from_payload(item))
        if page < pages:
            time.sleep(0.3)
    return jobs, total


def jobs_from_urls(lines: list[str]) -> list[Job]:
    jobs = []
    for line in lines:
        job_id = parse_job_id(line)
        if not job_id:
            continue
        jobs.append(
            Job(
                job_id=job_id,
                title=f"JobsDB {job_id}",
                company="(open listing to fill)",
                url=JOB_URL.format(job_id=job_id),
                teaser=line.strip(),
            )
        )
    return jobs
