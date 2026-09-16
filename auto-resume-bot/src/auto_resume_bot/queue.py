from auto_resume_bot.models import JobStatus


def decide_queue(score: int, auto_min: int = 70, gray_min: int = 60) -> JobStatus:
    if score >= auto_min:
        return JobStatus.queued
    if score >= gray_min:
        return JobStatus.needs_human
    return JobStatus.skipped
