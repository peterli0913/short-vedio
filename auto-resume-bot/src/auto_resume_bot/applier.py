from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from auto_resume_bot.db import Database
from auto_resume_bot.models import Job, JobStatus

WALL_HINTS = (
    "验证码",
    "captcha",
    "滑动",
    "unusual activity",
    "just a moment",
    "cf-challenge",
    "cf-browser-verification",
    "attention required",
    "challenge-platform",
)
LOGIN_HINTS = ("sign in to continue", "please log in", "请登录", "login wall")
APPLY_SELECTORS = ("apply", "申请", "立即申请", "quick apply", "easy apply")


@dataclass
class ApplyResult:
    ok: bool
    status: JobStatus
    detail: str


def _blocked(html: str) -> str | None:
    blob = (html or "").lower()
    for hint in WALL_HINTS:
        if hint.lower() in blob:
            return f"wall:{hint}"
    for hint in LOGIN_HINTS:
        if hint.lower() in blob:
            return f"login:{hint}"
    return None


def apply_job(page, job: Job) -> ApplyResult:
    page.goto(job.url)
    html = page.content()
    reason = _blocked(html)
    if reason:
        return ApplyResult(False, JobStatus.needs_human, reason)
    clicked = None
    for sel in APPLY_SELECTORS:
        loc = page.locator(sel)
        if loc.count() and loc.is_visible():
            page.click(sel)
            clicked = sel
            break
    after = page.content()
    reason = _blocked(after)
    if reason:
        return ApplyResult(False, JobStatus.needs_human, reason)
    if not clicked:
        return ApplyResult(False, JobStatus.failed, "no_apply_button")
    return ApplyResult(True, JobStatus.applied, f"clicked:{clicked}")


def run_apply_batch(db: Database, source: str, cap: int, page=None, page_factory=None) -> list[ApplyResult]:
    results: list[ApplyResult] = []
    queued = db.list_jobs_by_status(JobStatus.queued)
    queued = [job for job in queued if job.source == source]
    for job in queued:
        if db.count_applied_today(source) >= cap:
            break
        current = page or (page_factory() if page_factory else None)
        if current is None:
            results.append(ApplyResult(False, JobStatus.needs_human, "no_browser_page"))
            job.status = JobStatus.needs_human
            job.score_reason = (job.score_reason or "") + " | no_browser_page"
            db.upsert_job(job)
            continue
        job.status = JobStatus.applying
        db.upsert_job(job)
        result = apply_job(current, job)
        job.status = result.status
        if result.ok:
            job.applied_at = datetime.now(timezone.utc).replace(microsecond=0)
        job.score_reason = (job.score_reason or "") + f" | apply:{result.detail}"
        db.upsert_job(job)
        results.append(result)
    return results


def open_persistent_page(user_data_dir: str, headless: bool = False):
    """Launch the user's Chromium profile. Never stores passwords."""
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    context = pw.chromium.launch_persistent_context(user_data_dir, headless=headless)
    page = context.pages[0] if context.pages else context.new_page()
    return pw, context, page
