# Auto-resume bot (Week 1)

Hong Kong job desk from `2026-09-16-auto-resume-bot.md` on `main`.

Discovers JobsDB roles, hard-filters (HK + salary + keywords), scores, queues
≥70 for apply, escalates 60–69 and captcha/Cloudflare walls, watches IMAP
read-only, writes a daily digest.

It does **not** solve captchas, does **not** bypass Cloudflare, and does
**not** auto-reply to email. Platform passwords stay in `.env`.

JobsDB **HTML** pages are a Cloudflare wall. Discover uses the public search
JSON (`/api/jobsearch/v5/search`). Apply uses your logged-in Playwright
profile and stops if a challenge appears.

## Install

```bash
cd auto-resume-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
cp config.example.yaml config.yaml
cp .env.example .env
# edit .env — never commit it
```

Grok Bot / no venv:

```bash
pip install -e ".[dev]"
python3 run.py discover --source jobsdb
```

## First-time JobsDB login (human)

```bash
python3 run.py login
```

Log in yourself in the opened browser. Do not paste passwords into chat.

## Daily loop

```bash
python3 run.py discover --source jobsdb
python3 run.py apply --source jobsdb
python3 run.py watch-mail
python3 run.py digest
```

Without `SCORING_API_KEY`, discover uses a local heuristic scorer. Set
`AUTO_RESUME_FAKE_SCORE=80` only in tests.

Apply dry-run (no browser): `python3 run.py apply --dry-run`

## Safety

- City: Hong Kong only
- Salary floor: CNY ≥ 50,000 / month (HKD × 0.92); 面议 → needs_human
- Roles: 智能制造 / AI运筹 / 海外站点运营 / AI应用 (CDMO alone does not pass)
- Score: ≥70 queue; 60–69 ask; <60 skip
- Daily apply cap: 30 on JobsDB (config)
- Mail: IMAP read-only, no SMTP
- Captcha / 2FA / CF / login wall → `needs_human`, that job stops

## Week-1 acceptance
- [ ] `pytest` all green
- [ ] JobsDB discover inserts ≥1 real HK job into SQLite (manual)
- [ ] Hard filter drops non-HK
- [ ] FakeScorer path can enqueue; live HttpScorer optional
- [ ] Apply stops cleanly on captcha page (manual screenshot)
- [ ] IMAP poll on one mailbox inserts MailEvent
- [ ] Digest file written under data/digests/

## Tests

```bash
cd auto-resume-bot
python -m pytest -q
```
