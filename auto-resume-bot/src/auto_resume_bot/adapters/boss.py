from auto_resume_bot.models import Job


class BossAdapter:
    name = "boss"

    def fetch_jobs(self) -> list[Job]:
        return []

    def apply(self, *args, **kwargs):
        raise NotImplementedError("Boss apply is read-only in week-1")
