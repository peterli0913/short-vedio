from __future__ import annotations

import re

from .models import Job, Profile

TOKEN_RE = re.compile(r"[a-z0-9+#./-]{2,}")


def _norm(text: str) -> str:
    return (text or "").lower()


def _tokens(text: str) -> set[str]:
    return set(TOKEN_RE.findall(_norm(text)))


def _haystack(job: Job) -> str:
    return " ".join(
        [
            job.title,
            job.company,
            job.location,
            job.salary,
            job.work_type,
            job.arrangement,
            job.classification,
            job.teaser,
            " ".join(job.bullets),
        ]
    )


def score_job(job: Job, profile: Profile) -> Job:
    text = _haystack(job)
    blob = _norm(text)
    tokens = _tokens(text)
    reasons: list[str] = []
    score = 10

    role_hits = [role for role in profile.target_roles if _norm(role) and _norm(role) in blob]
    if role_hits:
        score += min(30, 12 * len(role_hits))
        reasons.append("role: " + ", ".join(role_hits[:3]))

    skill_hits = [skill for skill in profile.skills if _norm(skill) and _norm(skill) in blob]
    if skill_hits:
        score += min(35, 5 * len(skill_hits))
        reasons.append("skills: " + ", ".join(skill_hits[:6]))

    loc_hits = [loc for loc in profile.locations if _norm(loc) and _norm(loc) in blob]
    if loc_hits:
        score += 8
        reasons.append("location: " + ", ".join(loc_hits[:2]))
    elif profile.locations and tokens:
        # No explicit match is fine for HK-wide searches.
        pass

    must_miss = [need for need in profile.must_have if _norm(need) and _norm(need) not in blob]
    if must_miss:
        score -= 15 * len(must_miss)
        reasons.append("missing: " + ", ".join(must_miss[:4]))

    avoid_hits = [bad for bad in profile.avoid if _norm(bad) and _norm(bad) in blob]
    if avoid_hits:
        score -= 20 * len(avoid_hits)
        reasons.append("avoid: " + ", ".join(avoid_hits[:3]))

    if profile.salary_min_hkd and job.salary:
        numbers = [int(x.replace(",", "")) for x in re.findall(r"(\d[\d,]{2,})", job.salary)]
        if numbers and max(numbers) < profile.salary_min_hkd:
            score -= 15
            reasons.append(f"salary below {profile.salary_min_hkd}")

    job.score = max(0, min(100, score))
    job.reasons = reasons
    return job


def rank_jobs(jobs: list[Job], profile: Profile) -> list[Job]:
    scored = [score_job(job, profile) for job in jobs]
    scored.sort(key=lambda item: (-item.score, item.listed_at), reverse=False)
    scored.sort(key=lambda item: item.score, reverse=True)
    return scored
