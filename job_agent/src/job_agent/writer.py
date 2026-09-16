from __future__ import annotations

from datetime import date
from pathlib import Path

from . import config
from .models import Job, Profile


def _safe_name(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in text)
    return cleaned.strip("_")[:80] or "job"


def build_cover_letter(job: Job, profile: Profile) -> str:
    highlights = profile.highlights[:4] or [
        f"{profile.years_experience}+ years in {', '.join(profile.target_roles[:2]) or 'the target field'}"
    ]
    bullet_block = "\n".join(f"- {item}" for item in highlights)
    skills = ", ".join(profile.skills[:8]) or "the listed requirements"
    return f"""{date.today().isoformat()}

Hiring Manager
{job.company}

Re: {job.title}

Dear Hiring Team,

I am writing to apply for the {job.title} role at {job.company}. {profile.summary or "I would like to contribute the experience below."}

{bullet_block}

This listing stands out because it matches my target work ({", ".join(profile.target_roles[:3]) or "see resume"}) and skills such as {skills}. I am available in {", ".join(profile.locations) or "the posted location"} and can start a conversation this week.

Thank you for your time. I have attached my resume and would welcome a short call.

Sincerely,
{profile.full_name or "[Your name]"}
{profile.email}
{profile.phone}
"""


def build_packet_markdown(job: Job, profile: Profile) -> str:
    resume = config.load_resume().strip()
    why = "\n".join(f"- {reason}" for reason in job.reasons) or "- scored from title/teaser overlap"
    bullets = "\n".join(f"- {item}" for item in job.bullets) or "- (no bullets in search payload)"
    return f"""# Apply packet — {job.title}

- Company: {job.company}
- Job ID: {job.job_id}
- Score: {job.score}
- Official page (open in *your* browser; do not ask a bot to bypass Cloudflare): {job.url}
- Location: {job.location or "—"}
- Type: {job.work_type or "—"} / {job.arrangement or "—"}
- Salary: {job.salary or "—"}
- Classification: {job.classification or "—"}
- Listed: {job.listed_at or "—"}

## Why this was shortlisted
{why}

## Listing teaser
{job.teaser or "—"}

## Listing bullets
{bullets}

## One-click apply steps
1. Open the official URL above in your own browser (complete any Cloudflare / login yourself).
2. Paste the cover letter below into the message / cover-letter box.
3. Attach your resume PDF.
4. Come back here and mark the job as `applied`.

## Cover letter
{build_cover_letter(job, profile)}

## Resume notes (from resume.md)
{resume or "_Add resume.md in the workspace folder._"}
"""


def write_packet(job: Job, profile: Profile) -> Path:
    config.ensure_dirs()
    config.PACKETS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.PACKETS_DIR / f"{job.job_id}_{_safe_name(job.company)}_{_safe_name(job.title)}.md"
    path.write_text(build_packet_markdown(job, profile), encoding="utf-8")
    return path
