# job_agent

- Stdlib only. Do not add pip dependencies.
- Never implement Cloudflare, CAPTCHA, or login bypass.
- Never POST an application form. Packets + official URLs only.
- Keep IMAP secrets in environment variables.
- Grok Bot entry: `python3 run.py` / `bash scripts/daily.sh`. Local UI: `python3 run.py serve` (localhost only).
- Run tests with `python3 -m unittest discover -s tests -v` from `job_agent/`.
