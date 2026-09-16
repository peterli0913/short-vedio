# Run this on Grok Bot

Grok Bot's browser will keep failing JobsDB HTML because of Cloudflare.
This project does **not** fight that. It uses the public search JSON, then
hands you a one-click packet so *you* open the official apply page.

## One-time setup on the Bot computer

1. Copy the `job_agent/` folder onto the Bot computer (or clone this repo).
2. In a Bot chat:

```
Create folder job_agent/workspace.
Run: cd job_agent && python3 run.py setup
Then edit workspace/profile.json with my real target roles and skills,
and paste a short resume into workspace/resume.md.
```

3. Tell the Bot its standing rules: paste `SKILL.md`, then

```
Save this as a skill called “JobsDB apply desk”.
Never bypass Cloudflare. Never click Apply for me.
```

## Daily commands the Bot should run

One shot:

```bash
cd job_agent
export JOB_AGENT_HOME="$PWD/workspace"
bash scripts/daily.sh "AI engineer machine learning"
```

Or step by step:

```bash
cd job_agent
export JOB_AGENT_HOME="$PWD/workspace"
python3 run.py search --keywords "AI engineer machine learning" --pages 2
python3 run.py batch --min-score 40 --limit 8
python3 run.py digest
```

Then the Bot posts the digest in chat and waits. You open each URL, apply,
and reply `mark 94663084 applied`.

## Inbox without IMAP

Export or paste recruiter mail into `workspace/imports/emails.txt`
(see `data/emails.example.txt`), then:

```bash
python3 run.py classify --file workspace/imports/emails.txt
python3 run.py replies --label interview
python3 run.py drafts
```

## Inbox with Gmail IMAP (optional)

On the Bot computer set (do not put these in the skill or a shared Bot):

```bash
export JOB_AGENT_IMAP_USER="you@gmail.com"
export JOB_AGENT_IMAP_PASSWORD="app-password"
```

```bash
python3 run.py inbox --limit 30
python3 run.py drafts
```

## Routine (after the skill works once)

```
Every weekday at 09:00 Asia/Hong_Kong, run the JobsDB apply desk skill:
search my profile target roles, write packets for score >= 40,
classify new mail if emails.txt or IMAP is available,
write reply drafts, post digest in this chat.
Do not open JobsDB in the browser. Do not apply.
If search JSON fails, say so and stop.
```

## Interactive menu / local page

If you are sitting with the Bot terminal:

```bash
cd job_agent
export JOB_AGENT_HOME="$PWD/workspace"
python3 run.py menu
```

On your own machine (not required for the Bot):

```bash
python3 run.py serve
```

opens http://127.0.0.1:8765 . For unattended routines, use `scripts/daily.sh`.
