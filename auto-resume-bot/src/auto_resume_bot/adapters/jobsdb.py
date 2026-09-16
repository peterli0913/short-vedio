from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from auto_resume_bot.currency import parse_salary_to_rmb_min
from auto_resume_bot.models import Job, JobStatus

SEARCH_JSON = "https://hk.jobsdb.com/api/jobsearch/v5/search"
JOB_URL = "https://hk.jobsdb.com/job/{job_id}"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
JOB_ID_RE = re.compile(r"/job/(\d+)")


class JobsDbAdapter:
    """Week-1 HK adapter.

    HTML job/search pages are behind Cloudflare. Unit tests parse a static
    fixture. Live `fetch_jobs` uses the public search JSON (same payload the
    site uses). Playwright is only a fallback and must stop on a CF/captcha wall.
    """

    name = "jobsdb"

    def __init__(
        self,
        keywords: str = "AI application manufacturing",
        pages: int = 1,
        page_size: int = 20,
        hkd_to_cny: float = 0.92,
        client: httpx.Client | None = None,
    ):
        self.keywords = keywords
        self.pages = pages
        self.page_size = page_size
        self.hkd_to_cny = hkd_to_cny
        self.client = client

    def parse_listing_html(self, html: str) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[Job] = []
        for card in soup.select("[data-job-id], article.job-card, div.job-card"):
            job_id = card.get("data-job-id") or ""
            link = card.select_one("a[href]")
            href = (link.get("href") if link else "") or ""
            if not job_id:
                match = JOB_ID_RE.search(href)
                job_id = match.group(1) if match else ""
            title = (link.get_text(" ", strip=True) if link else "") or (
                card.select_one(".job-title") or card
            ).get_text(" ", strip=True)
            company = _text(card, ".company", "company")
            location = _text(card, ".location", "location") or "Hong Kong"
            salary = _text(card, ".salary", "salary")
            desc = _text(card, ".description", "teaser")
            if not href and job_id:
                href = JOB_URL.format(job_id=job_id)
            if href.startswith("/"):
                href = "https://hk.jobsdb.com" + href
            key = f"jobsdb:{job_id}" if job_id else f"jobsdb:{_hash(href or title)}"
            jobs.append(
                Job(
                    job_key=key,
                    title=title,
                    company=company,
                    location=location,
                    salary_raw=salary or None,
                    salary_rmb_min=parse_salary_to_rmb_min(salary, self.hkd_to_cny) if salary else None,
                    url=href or JOB_URL.format(job_id=job_id or "unknown"),
                    source=self.name,
                    description=desc,
                    status=JobStatus.discovered,
                )
            )
        return jobs

    def fetch_jobs(self) -> list[Job]:
        jobs: list[Job] = []
        close = False
        client = self.client
        if client is None:
            client = httpx.Client(timeout=20.0, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            close = True
        try:
            for page in range(1, max(1, self.pages) + 1):
                params = {
                    "siteKey": "HK-Main",
                    "keywords": self.keywords,
                    "page": str(page),
                    "pageSize": str(self.page_size),
                }
                resp = client.get(f"{SEARCH_JSON}?{urlencode(params)}")
                resp.raise_for_status()
                payload = resp.json()
                for item in payload.get("data") or []:
                    if isinstance(item, dict) and item.get("id"):
                        jobs.append(job_from_payload(item, self.hkd_to_cny))
        finally:
            if close:
                client.close()
        return jobs


def job_from_payload(item: dict[str, Any], hkd_to_cny: float = 0.92) -> Job:
    advertiser = item.get("advertiser") or {}
    employer = item.get("employer") or {}
    company = item.get("companyName") or employer.get("name") or advertiser.get("description") or ""
    locations = item.get("locations") or []
    location = ", ".join(
        loc.get("label") for loc in locations if isinstance(loc, dict) and loc.get("label")
    )
    job_id = str(item.get("id") or "")
    salary = item.get("salaryLabel") or ""
    bullets = [str(x) for x in (item.get("bulletPoints") or []) if x]
    teaser = item.get("teaser") or ""
    return Job(
        job_key=f"jobsdb:{job_id}",
        title=item.get("title") or "",
        company=company,
        location=location or "Hong Kong",
        salary_raw=salary or None,
        salary_rmb_min=parse_salary_to_rmb_min(salary, hkd_to_cny) if salary else None,
        url=JOB_URL.format(job_id=job_id),
        source="jobsdb",
        description=" ".join([teaser] + bullets),
        status=JobStatus.discovered,
    )


def _text(card, *selectors: str) -> str:
    for sel in selectors:
        node = card.select_one(sel)
        if node:
            return node.get_text(" ", strip=True)
    return ""


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
