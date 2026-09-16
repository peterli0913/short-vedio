from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from auto_resume_bot.adapters.boss import BossAdapter
from auto_resume_bot.adapters.careers import CareersAdapter
from auto_resume_bot.adapters.jobsdb import JobsDbAdapter
from auto_resume_bot.applier import run_apply_batch
from auto_resume_bot.db import Database
from auto_resume_bot.digest import build_digest
from auto_resume_bot.mail_watcher import client_from_account, poll_account
from auto_resume_bot.pipeline import run_discover
from auto_resume_bot.profile import load_config, load_env, load_profile, project_root
from auto_resume_bot.scorer import FakeScorer, HeuristicScorer, HttpScorer


def _db(cfg: dict) -> Database:
    root = Path(cfg.get("_root") or project_root())
    return Database(root / "data" / "auto_resume.sqlite")


def _scorer(cfg: dict):
    load_env()
    key = os.environ.get("SCORING_API_KEY") or os.environ.get("OPENAI_API_KEY")
    scoring = cfg.get("scoring") or {}
    if os.environ.get("AUTO_RESUME_FAKE_SCORE"):
        return FakeScorer(int(os.environ["AUTO_RESUME_FAKE_SCORE"]), "env-fake")
    if key:
        return HttpScorer(
            scoring.get("api_url") or "https://api.openai.com/v1/chat/completions",
            key,
            scoring.get("model") or "gpt-4o-mini",
        )
    return HeuristicScorer()


def _adapter(name: str, cfg: dict, profile: dict):
    keywords = " ".join((profile.get("role_keywords") or [])[:8]) or "AI application"
    fx = float((cfg.get("currency") or {}).get("hkd_to_cny") or 0.92)
    if name == "jobsdb":
        return JobsDbAdapter(keywords=keywords, pages=2, hkd_to_cny=fx)
    if name == "boss":
        return BossAdapter()
    if name == "careers":
        urls = ((cfg.get("sources") or {}).get("careers") or {}).get("urls") or []
        return CareersAdapter(urls)
    raise SystemExit(f"unknown source {name}")


def cmd_discover(args) -> int:
    cfg = load_config(args.config)
    profile, summary = load_profile(args.config)
    cfg["resume_summary"] = summary
    db = _db(cfg)
    adapter = _adapter(args.source, cfg, profile)
    jobs = adapter.fetch_jobs()
    processed = run_discover(db, jobs, profile, _scorer(cfg), cfg)
    counts: dict[str, int] = {}
    for job in processed:
        counts[job.status.value] = counts.get(job.status.value, 0) + 1
    print(f"discovered {len(jobs)} from {args.source}: {counts}")
    for job in processed[:15]:
        print(f"  {job.status.value:12} {job.score or '-':>3} {job.company} — {job.title} {job.url}")
    return 0


def cmd_apply(args) -> int:
    cfg = load_config(args.config)
    db = _db(cfg)
    cap = int(((cfg.get("sources") or {}).get(args.source) or {}).get("daily_apply_cap") or 30)
    page = None
    pw = context = None
    if args.dry_run:
        print("dry-run: not opening a browser")
    else:
        try:
            from auto_resume_bot.applier import open_persistent_page

            root = Path(cfg.get("_root") or project_root())
            user_dir = root / ((cfg.get("browser") or {}).get("user_data_dir") or "data/browser-profile")
            user_dir.mkdir(parents=True, exist_ok=True)
            headless = bool((cfg.get("browser") or {}).get("headless"))
            pw, context, page = open_persistent_page(str(user_dir), headless=headless)
        except Exception as exc:
            print(f"browser unavailable ({exc}). Jobs stay needs_human. Log into JobsDB yourself first.")
            page = None
    try:
        results = run_apply_batch(db, args.source, cap, page=page)
    finally:
        if context:
            context.close()
        if pw:
            pw.stop()
    for result in results:
        print(f"{result.status.value}: {result.detail}")
    if not results:
        print("nothing queued")
    return 0


def cmd_watch_mail(args) -> int:
    cfg = load_config(args.config)
    db = _db(cfg)
    accounts = (cfg.get("mail") or {}).get("accounts") or []
    if not accounts:
        print("No mail.accounts in config. Add IMAP host/user/password_env (password stays in .env).")
        return 2
    load_env()
    total = 0
    for account in accounts:
        client = client_from_account(account)
        events = poll_account(client, account.get("user") or account.get("host"), db)
        total += len(events)
        for event in events:
            print(f"{event.category.value:12} {event.subject} job={event.job_key or '-'}")
    print(f"stored {total} messages (read-only, no replies sent)")
    return 0


def cmd_digest(args) -> int:
    cfg = load_config(args.config)
    db = _db(cfg)
    day = date.fromisoformat(args.date) if args.date else date.today()
    text = build_digest(db, day)
    out_dir = Path(cfg.get("_root") or project_root()) / ((cfg.get("digest") or {}).get("output_path") or "data/digests")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{day.isoformat()}.md"
    path.write_text(text, encoding="utf-8")
    print(text)
    print(f"wrote {path}")
    return 0


def cmd_login(args) -> int:
    cfg = load_config(args.config)
    from auto_resume_bot.applier import open_persistent_page

    root = Path(cfg.get("_root") or project_root())
    user_dir = root / ((cfg.get("browser") or {}).get("user_data_dir") or "data/browser-profile")
    user_dir.mkdir(parents=True, exist_ok=True)
    print(f"Opening persistent profile at {user_dir}. Log into JobsDB yourself, then close the window.")
    pw, context, page = open_persistent_page(str(user_dir), headless=False)
    try:
        page.goto("https://hk.jobsdb.com/")
        input("Press Enter after you have logged in (do not paste passwords here)...")
    finally:
        context.close()
        pw.stop()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Week-1 auto resume bot (HK / JobsDB)")
    parser.add_argument("--config", help="Path to config.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    discover = sub.add_parser("discover")
    discover.add_argument("--source", default="jobsdb")

    apply_p = sub.add_parser("apply")
    apply_p.add_argument("--source", default="jobsdb")
    apply_p.add_argument("--dry-run", action="store_true")

    once = sub.add_parser("apply-once")
    once.add_argument("--source", default="jobsdb")
    once.add_argument("--dry-run", action="store_true")

    sub.add_parser("watch-mail")
    digest = sub.add_parser("digest")
    digest.add_argument("--date")
    sub.add_parser("login")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "discover":
        return cmd_discover(args)
    if args.cmd in {"apply", "apply-once"}:
        return cmd_apply(args)
    if args.cmd == "watch-mail":
        return cmd_watch_mail(args)
    if args.cmd == "digest":
        return cmd_digest(args)
    if args.cmd == "login":
        return cmd_login(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
