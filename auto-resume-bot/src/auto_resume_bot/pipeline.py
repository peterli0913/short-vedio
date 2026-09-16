from __future__ import annotations

from auto_resume_bot.db import Database
from auto_resume_bot.filters import hard_filter
from auto_resume_bot.models import Job, JobStatus
from auto_resume_bot.queue import decide_queue

SKIP_REPROCESS = {JobStatus.applied, JobStatus.queued, JobStatus.applying}


def process_new_job(db: Database, job: Job, profile: dict, scorer, cfg: dict) -> Job:
    existing = db.get_job(job.job_key)
    if existing and existing.status in SKIP_REPROCESS:
        return existing

    fx = float((cfg.get("currency") or {}).get("hkd_to_cny") or 0.92)
    result = hard_filter(job, profile, fx)
    if result.gray:
        job.status = JobStatus.needs_human
        job.score_reason = result.reason
        db.upsert_job(job)
        return job
    if not result.passed:
        job.status = JobStatus.skipped
        job.score_reason = result.reason
        db.upsert_job(job)
        return job

    resume = cfg.get("resume_summary") or ""
    scored = scorer.score(job, resume)
    job.score = scored.score
    job.score_reason = scored.reason
    scoring = cfg.get("scoring") or {}
    job.status = decide_queue(
        scored.score,
        int(scoring.get("auto_min", 70)),
        int(scoring.get("gray_min", 60)),
    )
    db.upsert_job(job)
    return job


def run_discover(db: Database, jobs: list[Job], profile: dict, scorer, cfg: dict) -> list[Job]:
    return [process_new_job(db, job, profile, scorer, cfg) for job in jobs]
