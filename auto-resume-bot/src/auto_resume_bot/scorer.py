from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from auto_resume_bot.models import Job


@dataclass
class ScoreResult:
    score: int
    reason: str


class ScorerError(Exception):
    pass


class FakeScorer:
    def __init__(self, fixed_score: int, reason: str = "fake"):
        self.fixed_score = fixed_score
        self.reason = reason

    def score(self, job: Job, resume_summary: str) -> ScoreResult:
        return ScoreResult(self.fixed_score, self.reason)


class HeuristicScorer:
    """Used when SCORING_API_KEY is empty so discover still works on Grok Bot."""

    def score(self, job: Job, resume_summary: str) -> ScoreResult:
        blob = f"{job.title}\n{job.company}\n{job.description}\n{resume_summary}".lower()
        hits = []
        for word in (
            "ai",
            "manufacturing",
            "mes",
            "ebr",
            "operations research",
            "overseas",
            "site",
            "machine learning",
            "reinforcement",
            "智能制造",
            "运筹",
            "海外",
        ):
            if word in blob:
                hits.append(word)
        score = min(92, 48 + 6 * len(hits))
        reason = "heuristic: " + (", ".join(hits[:6]) or "weak overlap")
        return ScoreResult(score, reason)


class HttpScorer:
    def __init__(self, api_url: str, api_key: str, model: str):
        self.api_url = api_url
        self.api_key = api_key
        self.model = model

    def score(self, job: Job, resume_summary: str) -> ScoreResult:
        prompt = (
            "Score job fit 0-100 for this candidate. Reply JSON "
            '{"score": int, "reason": "short reason"}.\n'
            f"RESUME:\n{resume_summary}\n\nJOB:\n{job.title}\n{job.company}\n"
            f"{job.location}\n{job.description[:4000]}"
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Return only JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        try:
            resp = httpx.post(self.api_url, headers=headers, json=body, timeout=60.0)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            raise ScorerError(str(e)) from e
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            raise ScorerError(f"no JSON in model reply: {content[:200]}")
        data = json.loads(match.group(0))
        score = max(0, min(100, int(data["score"])))
        return ScoreResult(score=score, reason=str(data.get("reason", "")))
