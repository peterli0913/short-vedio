# Run this on Grok Bot

Paste `SKILL.md` as a skill. Then:

```
cd auto-resume-bot
pip install -e ".[dev]"   # once
python3 run.py discover --source jobsdb
python3 run.py digest
```

Rules for the Bot:

- Do not open `hk.jobsdb.com/job/...` in a headless browser to “solve” Cloudflare.
- `discover` uses public JSON. If it 403s, stop and say so.
- `apply` needs the user’s logged-in Chromium profile (`run.py login` on their machine).
  On a shared Bot computer, skip apply or run `apply --dry-run` and list queued URLs.
- Never type or print IMAP / scoring keys. They live in `.env`.
- Never send email.

Routine:

```
Weekdays 09:00 Asia/Hong_Kong:
python3 run.py discover --source jobsdb
python3 run.py digest
Post the digest. Wait for me to apply or reply mark needs_human.
```
