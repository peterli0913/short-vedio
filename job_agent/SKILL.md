# Skill: JobsDB apply desk

## When to use
User wants Hong Kong JobsDB search, tailored apply packets, or inbox triage for job replies.
Use this instead of driving the JobsDB website in the browser.

## Do not
- Do not solve or bypass Cloudflare, CAPTCHAs, or login walls.
- Do not auto-submit an application. The human clicks Apply in their own browser.
- Do not store or print IMAP passwords. Use environment variables.
- Do not scrape HTML job pages. Use `run.py search` (public JSON) or import URLs.

## Required inputs
- `job_agent/workspace/profile.json` (create with `python3 run.py setup`)
- Optional `job_agent/workspace/resume.md`
- Optional IMAP: `JOB_AGENT_IMAP_USER`, `JOB_AGENT_IMAP_PASSWORD` (Gmail App Password)

## Sequence
0. `cd job_agent && python3 run.py setup` (once)
1. `python3 run.py search --keywords "<roles>" --pages 1`
   (omit `--keywords` to use `profile.json` target_roles)
2. `python3 run.py shortlist --limit 20`
3. For each strong match: `python3 run.py packet --job-id <id>`
   or `python3 run.py batch --min-score 40 --limit 8`
4. Give the user the packet path and official URL. Wait for them to apply.
5. `python3 run.py mark --job-id <id> --status applied`
6. Inbox: `python3 run.py inbox` or `python3 run.py classify --file workspace/imports/emails.txt`
7. `python3 run.py drafts` then morning digest: `python3 run.py digest`
   Shortcut: `bash scripts/daily.sh "AI engineer"`

## Validate
- Search prints job IDs and official `hk.jobsdb.com/job/<id>` URLs.
- Packet markdown contains a cover letter and the Cloudflare warning.
- Inbox labels are one of: interview, assessment, info_request, reject, ack, other.

## Return
A short table: score, company, title, URL, next action.
For mail: label + subject + suggested next step + any job hint.

## Approval
Anything that sends email, submits a form, or purchases a JobsDB product requires the user.
