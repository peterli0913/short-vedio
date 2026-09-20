from __future__ import annotations

from dataclasses import dataclass

from auto_resume_bot.currency import parse_salary_to_rmb_min
from auto_resume_bot.models import Job


@dataclass
class HardFilterResult:
    passed: bool
    reason: str
    gray: bool = False


def hard_filter(job: Job, profile: dict, hkd_to_cny: float) -> HardFilterResult:
    cities = [str(c) for c in (profile.get("city_allowlist") or [])]
    location = (job.location or "").casefold()
    if cities and not any(city.casefold() in location for city in cities):
        return HardFilterResult(False, "city_not_hk")

    blocked = [str(c) for c in (profile.get("company_blocklist") or [])]
    company = (job.company or "").casefold()
    if any(bad and bad.casefold() in company for bad in blocked):
        return HardFilterResult(False, "company_blocklist")

    keywords = [str(k) for k in (profile.get("role_keywords") or [])]
    blob = f"{job.title}\n{job.description}".casefold()
    if keywords and not any(key.casefold() in blob for key in keywords if key.strip()):
        return HardFilterResult(False, "role_keyword_miss")

    salary = job.salary_rmb_min
    if salary is None:
        salary = parse_salary_to_rmb_min(job.salary_raw or "", hkd_to_cny)
        job.salary_rmb_min = salary
    if salary is None:
        return HardFilterResult(False, "salary_unparsed", gray=True)

    floor = int(profile.get("salary_rmb_min") or 0)
    if floor and salary < floor:
        return HardFilterResult(False, "salary_below_floor")
    return HardFilterResult(True, "ok")
