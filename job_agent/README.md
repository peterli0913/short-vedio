# Job apply desk

Interactive helper for JobsDB search, apply packets, and recruiter-mail
triage. Built to run on **Grok Bot** or locally (`python3 run.py menu` /
`python3 run.py serve`).

It does **not** auto-submit applications and does **not** bypass Cloudflare
on `hk.jobsdb.com` HTML pages. Search uses the site's public JSON endpoint.
You click Apply yourself.

## Why this shape

A previous Grok Bot run died on JobsDB's Cloudflare challenge. The HTML job
page still returns 403 to automation. The search JSON used here returned 200
in testing, which is enough to shortlist and write a cover letter.

This repo's `main` only has wedding-photo uploads — the two plan files were
not in git — so the desk is built from that goal: search without the HTML
wall, one-click apply packets, one-click inbox filter / reply drafts.

## Quick start

```bash
cd job_agent
export JOB_AGENT_HOME="$PWD/workspace"
python3 run.py setup
# edit workspace/profile.json and workspace/resume.md
python3 run.py search --keywords "AI engineer" --pages 1
python3 run.py shortlist
python3 run.py packet --job-id <id>
```

Packets land in `workspace/packets/`. Open the official URL in your browser.

```bash
python3 run.py menu          # numbered one-click flow
python3 run.py serve         # localhost page at http://127.0.0.1:8765
python3 run.py digest        # morning summary
python3 run.py classify --file data/emails.example.txt
python3 run.py drafts        # bilingual reply drafts
bash scripts/daily.sh "AI engineer"
```

Grok Bot install: see [GROK_BOT.md](GROK_BOT.md) and [SKILL.md](SKILL.md).

## Tests

```bash
cd job_agent
python3 -m unittest discover -s tests -v
```

Stdlib only. No pip install.
