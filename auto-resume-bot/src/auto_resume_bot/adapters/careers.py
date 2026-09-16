from auto_resume_bot.models import Job, JobStatus


class CareersAdapter:
    name = "careers"

    def __init__(self, urls: list[str] | None = None):
        self.urls = urls or []

    def fetch_jobs(self) -> list[Job]:
        jobs: list[Job] = []
        for i, url in enumerate(self.urls):
            jobs.append(
                Job(
                    job_key=f"careers:{i}:{url}",
                    title=f"Careers page {i+1}",
                    company="(open listing)",
                    location="Hong Kong",
                    url=url,
                    source=self.name,
                    description=url,
                    status=JobStatus.discovered,
                )
            )
        return jobs
