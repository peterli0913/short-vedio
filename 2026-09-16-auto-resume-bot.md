# Auto-Resume Bot (Week 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal week-1 auto job-application bot that discovers Hong Kong roles, hard-filters + AI-scores them, auto-applies when score ≥70 (user session / Playwright), escalates captchas and gray scores, watches resume inboxes read-only, and writes a daily digest.

**Architecture:** Local Python package with SQLite as the system of record. Source adapters normalize jobs into one `Job` model; a matcher (hard filter + scorer) feeds a queue; a Playwright applier uses the user’s logged-in browser context and stops on captcha/login walls; an IMAP mail watcher attaches replies to applications; a digest job summarizes the day. No captcha bypass, no plaintext platform passwords.

**Tech Stack:** Python 3.11+, Playwright, SQLite, pydantic v2, PyYAML, httpx (for AI scoring API), IMAPClient (or stdlib imaplib), pytest, pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-09-16-auto-resume-bot-design.md`

## Global Constraints

- City hard filter: Hong Kong only (Hong Kong / HK / 香港特别行政区 / 香港)
- Salary floor: **CNY ≥ 50,000 / month**; HKD converted via config rate; unparseable salary → gray zone (no auto-apply)
- Target roles: 智能制造, AI运筹, 海外站点运营, AI应用 (CDMO alone does not pass)
- Score gates: ≥70 auto-apply; 60–69 ask user; &lt;60 skip
- Mail: read-only on resume inboxes; never auto-reply
- Browser: user session only; captcha / 2FA / risk page → `needs_human`, stop that job
- Per-source daily apply cap default: 20–40 (config)
- Week-1 closed loop priority: **JobsDB (or CTGoodJobs)**; Boss / company careers may be read-only + queue if apply is blocked
- Project root for code: `/workspace/auto-resume-bot/` (init git on first commit)
- Do not store platform passwords in plaintext; secrets only in `.env`

---

## File Structure (create under `/workspace/auto-resume-bot/`)

| Path | Responsibility |
|------|----------------|
| `pyproject.toml` | Package metadata, deps, pytest entry |
| `config.example.yaml` | Thresholds, sources, FX rate, caps |
| `.env.example` | `OPENAI_API_KEY` / scoring endpoint, IMAP secrets |
| `README.md` | Runbook: install, login, cron digest |
| `src/auto_resume_bot/models.py` | Pydantic models: Profile, Job, Application, MailEvent |
| `src/auto_resume_bot/db.py` | SQLite schema + repository helpers |
| `src/auto_resume_bot/currency.py` | Parse salary strings → RMB min |
| `src/auto_resume_bot/profile.py` | Load profile + resume summary from config/files |
| `src/auto_resume_bot/filters.py` | Hard filter |
| `src/auto_resume_bot/scorer.py` | AI score client (injectable) |
| `src/auto_resume_bot/queue.py` | Status transitions |
| `src/auto_resume_bot/adapters/base.py` | `SourceAdapter` protocol + normalize helpers |
| `src/auto_resume_bot/adapters/jobsdb.py` | Week-1 HK adapter |
| `src/auto_resume_bot/adapters/boss.py` | Stub / read-only search skeleton |
| `src/auto_resume_bot/adapters/careers.py` | Company careers URL list skeleton |
| `src/auto_resume_bot/applier.py` | Playwright apply + captcha stop |
| `src/auto_resume_bot/mail_watcher.py` | IMAP fetch + classify + attach |
| `src/auto_resume_bot/digest.py` | Daily markdown digest |
| `src/auto_resume_bot/pipeline.py` | discover → filter → score → enqueue |
| `src/auto_resume_bot/cli.py` | `discover`, `apply-once`, `watch-mail`, `digest` |
| `tests/...` | Mirror package layout |

---

### Task 1: Scaffold package, config, and git

**Files:**
- Create: `pyproject.toml`
- Create: `config.example.yaml`
- Create: `.env.example`
- Create: `src/auto_resume_bot/__init__.py`
- Create: `tests/test_scaffold.py`
- Create: `README.md` (minimal)

**Interfaces:**
- Consumes: none
- Produces: installable package `auto_resume_bot`; config keys used by later tasks

- [ ] **Step 1: Write failing scaffold test**

```python
# tests/test_scaffold.py
from pathlib import Path

def test_package_importable():
    import auto_resume_bot
    assert auto_resume_bot.__version__ == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspace/auto-resume-bot && python -m pytest tests/test_scaffold.py -v`
Expected: FAIL (module not found or no `__version__`)

- [ ] **Step 3: Write minimal scaffold**

`pyproject.toml`:

```toml
[project]
name = "auto-resume-bot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "pydantic>=2.0",
  "pyyaml>=6.0",
  "httpx>=0.27",
  "playwright>=1.40",
  "imapclient>=3.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[project.scripts]
auto-resume = "auto_resume_bot.cli:main"

[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"
```

`src/auto_resume_bot/__init__.py`:

```python
__version__ = "0.1.0"
```

`config.example.yaml`:

```yaml
profile:
  name: "李涛"
  city_allowlist: ["Hong Kong", "HK", "香港", "香港特别行政区"]
  salary_rmb_min: 50000
  roles: ["智能制造", "AI运筹", "海外站点运营", "AI应用"]
  role_keywords:
    - "智能制造"
    - "smart manufacturing"
    - "运筹"
    - "operations research"
    - "overseas"
    - "site operations"
    - "AI应用"
    - "AI application"
    - "MES"
    - "EBR"
  company_blocklist: []
  resume_summary_path: "data/resume_summary.txt"

scoring:
  auto_min: 70
  gray_min: 60
  api_url: "https://api.openai.com/v1/chat/completions"
  model: "gpt-4o-mini"

currency:
  hkd_to_cny: 0.92

sources:
  jobsdb:
    enabled: true
    daily_apply_cap: 30
    search_url: "https://hk.jobsdb.com/jobs"
  boss:
    enabled: true
    daily_apply_cap: 20
    mode: "read_only"  # week-1 default
  careers:
    enabled: true
    daily_apply_cap: 20
    urls: []

browser:
  user_data_dir: "data/browser-profile"
  headless: false

mail:
  accounts: []
  # example:
  # - host: imap.163.com
  #   user: peterdqs@163.com
  #   password_env: IMAP_163_PASSWORD

digest:
  output_path: "data/digests"
```

`.env.example`:

```
SCORING_API_KEY=
IMAP_163_PASSWORD=
IMAP_GMAIL_PASSWORD=
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /workspace/auto-resume-bot && pip install -e ".[dev]" && python -m pytest tests/test_scaffold.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /workspace/auto-resume-bot
git init
git add pyproject.toml config.example.yaml .env.example src tests README.md
git commit -m "chore: scaffold auto-resume-bot package"
```

---

### Task 2: Domain models + SQLite repository

**Files:**
- Create: `src/auto_resume_bot/models.py`
- Create: `src/auto_resume_bot/db.py`
- Create: `tests/test_db.py`

**Interfaces:**
- Consumes: none
- Produces:
  - `JobStatus` enum: `discovered | scored | queued | applying | applied | failed | needs_human | skipped`
  - `Job` model fields: `job_key, title, company, location, salary_raw, salary_rmb_min, url, source, description, score, score_reason, status`
  - `Application` : `job_key, applied_at, mail_event_ids`
  - `MailEvent`: `id, account, subject, from_addr, received_at, category, job_key | None, snippet`
  - `Database` class: `upsert_job`, `get_job`, `list_jobs_by_status`, `count_applied_today`, `add_mail_event`, `attach_mail_to_job`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_db.py
from auto_resume_bot.db import Database
from auto_resume_bot.models import Job, JobStatus

def test_upsert_and_get_job(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    job = Job(
        job_key="jobsdb:1",
        title="AI Application Manager",
        company="Acme",
        location="Hong Kong",
        salary_raw="HKD 60k-80k",
        salary_rmb_min=55200,
        url="https://example.com/1",
        source="jobsdb",
        description="smart manufacturing AI",
        status=JobStatus.discovered,
    )
    db.upsert_job(job)
    got = db.get_job("jobsdb:1")
    assert got is not None
    assert got.title == "AI Application Manager"
    assert got.status == JobStatus.discovered

def test_count_applied_today(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    assert db.count_applied_today("jobsdb") == 0
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/test_db.py -v`
Expected: FAIL import / missing symbols

- [ ] **Step 3: Implement models + db**

```python
# src/auto_resume_bot/models.py
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class JobStatus(str, Enum):
    discovered = "discovered"
    scored = "scored"
    queued = "queued"
    applying = "applying"
    applied = "applied"
    failed = "failed"
    needs_human = "needs_human"
    skipped = "skipped"

class Job(BaseModel):
    job_key: str
    title: str
    company: str
    location: str
    salary_raw: str | None = None
    salary_rmb_min: int | None = None
    url: str
    source: str
    description: str = ""
    score: int | None = None
    score_reason: str | None = None
    status: JobStatus = JobStatus.discovered
    applied_at: datetime | None = None

class MailCategory(str, Enum):
    interview = "interview"
    reject = "reject"
    docs_needed = "docs_needed"
    system = "system"
    other = "other"

class MailEvent(BaseModel):
    id: str
    account: str
    subject: str
    from_addr: str
    received_at: datetime
    category: MailCategory
    job_key: str | None = None
    snippet: str = ""
```

Implement `Database` with SQLite tables `jobs` and `mail_events`, JSON-friendly row mapping, and the methods listed in Interfaces. Use `CREATE TABLE IF NOT EXISTS`. Store enums as text; datetimes as ISO UTC.

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/test_db.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/auto_resume_bot/models.py src/auto_resume_bot/db.py tests/test_db.py
git commit -m "feat: add Job models and SQLite repository"
```

---

### Task 3: Currency parse + hard filter

**Files:**
- Create: `src/auto_resume_bot/currency.py`
- Create: `src/auto_resume_bot/filters.py`
- Create: `tests/test_currency.py`
- Create: `tests/test_filters.py`

**Interfaces:**
- Consumes: `Job`, profile dict from config
- Produces:
  - `parse_salary_to_rmb_min(salary_raw: str, hkd_to_cny: float) -> int | None`
  - `HardFilterResult(passed: bool, reason: str, gray: bool = False)`
  - `hard_filter(job: Job, profile: dict, hkd_to_cny: float) -> HardFilterResult`
  - Gray cases: unparseable salary → `passed=False, gray=True, reason="salary_unparsed"`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_currency.py
from auto_resume_bot.currency import parse_salary_to_rmb_min

def test_parse_hkd_monthly():
    assert parse_salary_to_rmb_min("HKD 60,000 - 80,000", 0.92) == 55200

def test_parse_cny():
    assert parse_salary_to_rmb_min("人民币 5万-8万/月", 0.92) == 50000

def test_unparseable():
    assert parse_salary_to_rmb_min("面议", 0.92) is None
```

```python
# tests/test_filters.py
from auto_resume_bot.models import Job, JobStatus
from auto_resume_bot.filters import hard_filter

PROFILE = {
    "city_allowlist": ["Hong Kong", "HK", "香港"],
    "salary_rmb_min": 50000,
    "role_keywords": ["智能制造", "AI", "运筹", "smart manufacturing"],
    "company_blocklist": ["BadCo"],
}

def _job(**kw):
    base = dict(
        job_key="x", title="AI Application", company="Good",
        location="Hong Kong", salary_raw="CNY 60000", salary_rmb_min=60000,
        url="u", source="jobsdb", description="AI应用 智能制造",
        status=JobStatus.discovered,
    )
    base.update(kw)
    return Job(**base)

def test_pass():
    r = hard_filter(_job(), PROFILE, 0.92)
    assert r.passed and not r.gray

def test_wrong_city():
    r = hard_filter(_job(location="Shanghai"), PROFILE, 0.92)
    assert not r.passed and not r.gray

def test_salary_gray():
    r = hard_filter(_job(salary_raw="面议", salary_rmb_min=None), PROFILE, 0.92)
    assert r.gray and not r.passed

def test_blocklist():
    r = hard_filter(_job(company="BadCo"), PROFILE, 0.92)
    assert not r.passed
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

`currency.py`: regex for CNY/RMB/¥/`万`, HKD/HK$, take the **lower** bound of a range, convert HKD with `hkd_to_cny`, return int RMB or None.

`filters.py`: check city substring (casefold), salary (`job.salary_rmb_min` or parse), at least one role keyword in `title+description` (casefold), not blocklisted, return `HardFilterResult`.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat: salary parse and hard filter"
```

---

### Task 4: AI scorer (HTTP client + fake for tests)

**Files:**
- Create: `src/auto_resume_bot/scorer.py`
- Create: `tests/test_scorer.py`

**Interfaces:**
- Consumes: `Job`, resume summary `str`, scoring config
- Produces:
  - `ScoreResult(score: int, reason: str)`
  - `Scorer` protocol / class with `score(job, resume_summary) -> ScoreResult`
  - `HttpScorer` and `FakeScorer(fixed_score: int)`
  - Clamp score to 0–100

- [ ] **Step 1: Write failing tests**

```python
from auto_resume_bot.scorer import FakeScorer, ScoreResult
from auto_resume_bot.models import Job, JobStatus

def test_fake_scorer():
    job = Job(
        job_key="k", title="t", company="c", location="Hong Kong",
        url="u", source="jobsdb", status=JobStatus.discovered,
    )
    r = FakeScorer(75).score(job, "resume")
    assert r.score == 75
    assert isinstance(r.reason, str)
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

```python
# scorer.py — minimal shape
from dataclasses import dataclass
import httpx
from auto_resume_bot.models import Job

@dataclass
class ScoreResult:
    score: int
    reason: str

class FakeScorer:
    def __init__(self, fixed_score: int, reason: str = "fake"):
        self.fixed_score = fixed_score
        self.reason = reason
    def score(self, job: Job, resume_summary: str) -> ScoreResult:
        return ScoreResult(self.fixed_score, self.reason)

class ScorerError(Exception):
    pass

class HttpScorer:
    def __init__(self, api_url: str, api_key: str, model: str):
        self.api_url = api_url
        self.api_key = api_key
        self.model = model

    def score(self, job: Job, resume_summary: str) -> ScoreResult:
        import json
        import re
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
```

On API failure raise `ScorerError` (do not silently return 0).

- [ ] **Step 4: PASS + commit**

```bash
git commit -am "feat: add FakeScorer and HttpScorer"
```

---

### Task 5: Queue / status machine + pipeline (discover → filter → score → enqueue)

**Files:**
- Create: `src/auto_resume_bot/queue.py`
- Create: `src/auto_resume_bot/pipeline.py`
- Create: `src/auto_resume_bot/profile.py`
- Create: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `Database`, `hard_filter`, `Scorer`, config profile
- Produces:
  - `decide_queue(score: int, auto_min=70, gray_min=60) -> JobStatus` → `queued` | `needs_human` | `skipped`
  - `process_new_job(db, job, profile, scorer, cfg) -> Job` mutates status/score in DB
  - `load_profile(config_path) -> dict` + resume summary text
  - Dedup: if `db.get_job(job_key)` exists with status in applied/queued/applying, skip reprocess

- [ ] **Step 1: Write failing tests**

```python
from auto_resume_bot.queue import decide_queue
from auto_resume_bot.models import JobStatus

def test_decide_queue():
    assert decide_queue(80) == JobStatus.queued
    assert decide_queue(65) == JobStatus.needs_human
    assert decide_queue(40) == JobStatus.skipped
```

Also integration test: insert job with HK + salary + keywords, `FakeScorer(80)`, assert DB status `queued`; with `FakeScorer(65)` → `needs_human`; salary 面议 → `needs_human` without calling scorer (or score left None).

- [ ] **Step 2–4: Implement, pass, commit**

```bash
git commit -am "feat: scoring gates and discover pipeline"
```

---

### Task 6: JobsDB adapter (normalize + fetch seam)

**Files:**
- Create: `src/auto_resume_bot/adapters/__init__.py`
- Create: `src/auto_resume_bot/adapters/base.py`
- Create: `src/auto_resume_bot/adapters/jobsdb.py`
- Create: `tests/test_jobsdb_adapter.py`
- Create: `tests/fixtures/jobsdb_sample.html` (minimal HTML fixture)

**Interfaces:**
- Consumes: currency + Job model
- Produces:
  - `SourceAdapter` protocol: `name: str`, `fetch_jobs() -> list[Job]`
  - `JobsDbAdapter.parse_listing_html(html: str) -> list[Job]` (pure, tested)
  - `JobsDbAdapter.fetch_jobs()` uses Playwright or httpx; week-1 may use Playwright page content
  - `job_key` format: `jobsdb:<external_id_or_url_hash>`

- [ ] **Step 1: Write failing parse test against fixture HTML** containing 2 cards with title, company, location Hong Kong, salary, link.

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement parser** with BeautifulSoup **or** Playwright locators documented in comments. Prefer `beautifulsoup4` added to deps if parsing static HTML; if JobsDB is heavily JS, document that `fetch_jobs` must use Playwright and tests mock `parse_listing_html` only.

Add `beautifulsoup4` to `pyproject.toml` if used.

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat: JobsDB adapter with HTML fixture parse"
```

**Note:** Live network fetch is optional in unit tests. Add one manual script note in README: `auto-resume discover --source jobsdb`.

---

### Task 7: Playwright applier + daily cap + captcha stop

**Files:**
- Create: `src/auto_resume_bot/applier.py`
- Create: `tests/test_applier.py`

**Interfaces:**
- Consumes: `Database`, browser config, Job with status `queued`
- Produces:
  - `ApplyResult(ok: bool, status: JobStatus, detail: str)`
  - `apply_job(page, job) -> ApplyResult` — if captcha selectors match → `needs_human`
  - `run_apply_batch(db, source, cap) -> list[ApplyResult]` respects `count_applied_today`
  - Never stores passwords; launches persistent context from `user_data_dir`

- [ ] **Step 1: Write unit tests with a FakePage**

```python
class FakeLocator:
    def __init__(self, visible: bool):
        self._visible = visible
    def count(self) -> int:
        return 1 if self._visible else 0
    def is_visible(self) -> bool:
        return self._visible

class FakePage:
    def __init__(self, html: str):
        self.html = html
        self.clicked: list[str] = []
    def content(self) -> str:
        return self.html
    def goto(self, url: str) -> None:
        self.last_url = url
    def click(self, sel: str) -> None:
        self.clicked.append(sel)
    def locator(self, sel: str) -> FakeLocator:
        return FakeLocator(sel.lower() in self.html.lower())
```

Test: HTML containing “验证码” or “captcha” → status `needs_human`. Happy-path fake: apply button present → `applied` and `db` updated with `applied_at`.

- [ ] **Step 2–4: Implement, pass, commit**

Captcha heuristics (any match → stop): visible text/selectors for `验证码`, `captcha`, `滑动`, `unusual activity`, login wall URLs.

```bash
git commit -am "feat: Playwright applier with captcha escalation"
```

---

### Task 8: Mail watcher (IMAP) + classify + attach

**Files:**
- Create: `src/auto_resume_bot/mail_watcher.py`
- Create: `tests/test_mail_watcher.py`

**Interfaces:**
- Consumes: IMAP settings, `Database`
- Produces:
  - `classify_subject(subject: str, body: str) -> MailCategory`
  - `match_job_key(db, subject, body, company_hints) -> str | None` (low confidence → None)
  - `poll_account(client, account_id) -> list[MailEvent]`
  - Read-only: no SMTP send; do not delete messages

- [ ] **Step 1: Tests for classify**

```python
assert classify_subject("Interview invitation", "") == MailCategory.interview
assert classify_subject("感谢您的应聘", "很遗憾") == MailCategory.reject
assert classify_subject("请补充材料", "") == MailCategory.docs_needed
```

Fake IMAP client returns 1 message; `poll` inserts `mail_events` and attaches when company name matches a recent applied job.

- [ ] **Step 2–4: Implement with `imaplib` or IMAPClient, pass, commit**

```bash
git commit -am "feat: read-only mail watcher and classification"
```

---

### Task 9: Digest + CLI wiring

**Files:**
- Create: `src/auto_resume_bot/digest.py`
- Create: `src/auto_resume_bot/cli.py`
- Create: `src/auto_resume_bot/adapters/boss.py` (stub raising `NotImplementedError` for apply; optional `fetch_jobs` empty list)
- Create: `src/auto_resume_bot/adapters/careers.py` (iterate config URLs → Job stubs or skip)
- Create: `tests/test_digest.py`
- Modify: `README.md` full runbook

**Interfaces:**
- Consumes: `Database`
- Produces:
  - `build_digest(db, day: date) -> str` markdown
  - CLI subcommands: `discover`, `apply`, `watch-mail`, `digest`
  - Digest sections: new discovered, hard-filter passes, auto-applied, needs_human, failed, mail interview/reject/docs

- [ ] **Step 1: Digest test with seeded DB**

- [ ] **Step 2–4: Implement CLI with argparse, pass, commit**

```bash
git commit -am "feat: daily digest and CLI entrypoints"
```

README must document:
1. Copy `config.example.yaml` → `config.yaml`, `.env.example` → `.env`
2. `playwright install chromium`
3. First-time: open persistent profile and log into JobsDB manually
4. `auto-resume discover && auto-resume apply && auto-resume watch-mail && auto-resume digest`
5. Safety: captcha stops; no auto email reply

---

### Task 10: Week-1 smoke checklist (manual, recorded in README)

**Files:**
- Modify: `README.md` section “Week-1 acceptance”

- [ ] **Step 1: Add checklist**

```markdown
## Week-1 acceptance
- [ ] `pytest` all green
- [ ] JobsDB discover inserts ≥1 real HK job into SQLite (manual)
- [ ] Hard filter drops non-HK
- [ ] FakeScorer path can enqueue; live HttpScorer optional
- [ ] Apply stops cleanly on captcha page (manual screenshot)
- [ ] IMAP poll on one mailbox inserts MailEvent
- [ ] Digest file written under data/digests/
```

- [ ] **Step 2: Commit**

```bash
git commit -am "docs: week-1 acceptance checklist"
```

---

## Self-Review (author)

1. **Spec coverage:** Goals 1–5 → Tasks 5–9; HK closed loop → Task 6–7; Boss/官网 read-only → Task 9 stubs; mail read-only → Task 8; salary CNY / gray → Task 3; score gates → Task 5; no captcha bypass → Task 7; productize deferred → out of week-1 tasks (OK).
2. **Placeholders:** None; HttpScorer includes full httpx POST + JSON parse + ScorerError.
3. **Types:** `JobStatus`, `job_key`, `ScoreResult`, `HardFilterResult`, `ApplyResult`, `MailCategory` used consistently across tasks.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-16-auto-resume-bot.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks
2. **Inline Execution** — this session with executing-plans and checkpoints

Which approach?
