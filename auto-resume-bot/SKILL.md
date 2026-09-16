# Skill: Auto-resume bot (JobsDB week-1)

## When to use
User wants HK job discover / score / apply queue / inbox watch / daily digest.

## Do not
- Do not bypass Cloudflare, CAPTCHA, 2FA, or login walls.
- Do not store platform passwords in files or chat.
- Do not send email. IMAP is read-only.
- Do not scrape JobsDB HTML job pages. Use `python3 run.py discover`.

## Sequence
1. `cd auto-resume-bot && python3 run.py discover --source jobsdb`
2. Show queued (`>=70`) and `needs_human` (60–69 or 面议 or wall).
3. Apply only with the user’s persistent browser profile:
   `python3 run.py apply --source jobsdb`
   If captcha/CF appears, leave the job as `needs_human` and stop that job.
4. `python3 run.py watch-mail` if IMAP env vars exist.
5. `python3 run.py digest` and paste the markdown.

## Validate
- Jobs have keys `jobsdb:<id>` and official URLs.
- Non-HK roles are `skipped`.
- Digest file appears under `data/digests/`.

## Approval
Sending mail, paying JobsDB, or solving a challenge requires the user.
