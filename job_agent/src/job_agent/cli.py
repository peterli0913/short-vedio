from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, config
from .classifier import parse_mbox_like, to_inbox_item
from .config import ensure_dirs, load_profile, set_home
from .drafts import suggested_action, write_drafts
from .jobsdb import JobsDBError, jobs_from_urls, search_jobs
from .mailer import fetch_imap
from .matcher import rank_jobs
from .store import (
    counts,
    email_counts,
    get_job,
    list_emails,
    list_jobs,
    set_status,
    upsert_emails,
    upsert_jobs,
)
from .writer import write_packet

STATUSES = ("new", "packet_ready", "applied", "skipped", "interview", "rejected")
SKIP_BATCH = {"applied", "skipped", "rejected"}

MENU = """
求职工作台  (v{version})
workspace: {home}

1) 搜索 JobsDB（公开 JSON，不打开 Cloudflare 网页）
2) 从文件导入职位 URL / ID
3) 查看短名单
4) 一键生成投递包（求职信 + 官方链接）
5) 批量为短名单生成投递包
6) 标记 已投 / 跳过 / 面试
7) 拉取 IMAP 收件箱并分类
8) 分类粘贴的邮件（emails.txt）
9) 查看已分类回复
10) 一键生成回复草稿
d) 今日摘要
s) 初始化工作区
w) 打开本机网页工作台
0) 退出
""".strip()


def _data_dir() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parents[2] / "data", here.parents[1] / "data"):
        if candidate.exists():
            return candidate
    return here.parents[2] / "data"


def default_keywords() -> str:
    profile = load_profile()
    return " ".join(profile.target_roles[:4]) or "AI engineer"


def _print_jobs(jobs: list) -> None:
    if not jobs:
        print("No jobs.")
        return
    print(f"{'score':>5}  {'id':<10} {'st':<12} company / title")
    for job in jobs:
        print(
            f"{job.score:>5}  {job.job_id:<10} {job.status:<12} "
            f"{job.company} — {job.title}"
        )
        if job.reasons:
            print("       " + "; ".join(job.reasons))
        print(f"       {job.url}")


def cmd_setup() -> int:
    ensure_dirs()
    data = _data_dir()
    mapping = [
        (data / "profile.example.json", config.PROFILE_PATH),
        (data / "resume.example.md", config.RESUME_PATH),
        (data / "emails.example.txt", config.IMPORT_DIR / "emails.txt"),
    ]
    for src, dest in mapping:
        if dest.exists():
            print(f"keep {dest}")
            continue
        if not src.exists():
            print(f"missing example {src}")
            return 2
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"wrote {dest}")
    print("Edit profile.json, then: python3 run.py search")
    return 0


def cmd_search(keywords: str, pages: int, page_size: int, min_score: int, where: str = "") -> int:
    profile = load_profile()
    if not profile.full_name and not profile.skills and not profile.target_roles:
        print(f"Fill {config.PROFILE_PATH} first. Run: python3 run.py setup")
        return 2
    keywords = (keywords or "").strip() or default_keywords()
    try:
        jobs, total = search_jobs(keywords, pages=pages, page_size=page_size, where=where)
    except JobsDBError as exc:
        print(exc)
        return 1
    ranked = rank_jobs(jobs, profile)
    upsert_jobs(ranked)
    keep = [job for job in ranked if job.score >= min_score]
    print(f"Fetched {len(ranked)} / {total} listings for {keywords!r}. Showing score >= {min_score}:")
    _print_jobs(keep[:30])
    return 0


def cmd_import(path: str, min_score: int) -> int:
    profile = load_profile()
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    jobs = rank_jobs(jobs_from_urls(lines), profile)
    upsert_jobs(jobs)
    _print_jobs([job for job in jobs if job.score >= min_score])
    print("Imported IDs only. Re-run search to fill title/company when possible.")
    return 0


def cmd_shortlist(limit: int, status: str | None) -> int:
    jobs = list_jobs(status=status, limit=limit)
    print("Tracker:", counts())
    _print_jobs(jobs)
    return 0


def cmd_packet(job_id: str) -> int:
    profile = load_profile()
    job = get_job(job_id)
    if not job:
        print(f"Unknown job {job_id}. Search or import first.")
        return 2
    path = write_packet(job, profile)
    if job.status == "new":
        set_status(job.job_id, "packet_ready")
    print(f"Wrote {path}")
    print(f"Open this yourself: {job.url}")
    return 0


def cmd_batch(min_score: int, limit: int) -> int:
    profile = load_profile()
    jobs = [
        job
        for job in list_jobs(limit=200)
        if job.score >= min_score and job.status not in SKIP_BATCH
    ][:limit]
    if not jobs:
        print("Nothing to pack. Search first.")
        return 2
    for job in jobs:
        path = write_packet(job, profile)
        if job.status == "new":
            set_status(job.job_id, "packet_ready")
        print(path)
    return 0


def cmd_mark(job_id: str, status: str) -> int:
    if status not in STATUSES:
        print(f"Status must be one of: {', '.join(STATUSES)}")
        return 2
    if not get_job(job_id):
        print(f"Unknown job {job_id}.")
        return 2
    set_status(job_id, status)
    print(f"{job_id} -> {status}")
    return 0


def cmd_inbox(limit: int) -> int:
    jobs = list_jobs(limit=200)
    try:
        items = fetch_imap(limit=limit, jobs=jobs)
    except Exception as exc:
        print(exc)
        print("Or use: python3 run.py classify --file workspace/imports/emails.txt")
        return 1
    upsert_emails(items)
    cmd_replies(None, 40)
    return 0


def cmd_classify_file(path: str) -> int:
    jobs = list_jobs(limit=200)
    raw = Path(path).read_text(encoding="utf-8")
    items = [
        to_inbox_item(row["uid"], row["subject"], row["sender"], row["date"], row["snippet"], jobs)
        for row in parse_mbox_like(raw)
    ]
    upsert_emails(items)
    cmd_replies(None, 40)
    return 0


def cmd_replies(label: str | None, limit: int) -> int:
    items = list_emails(label=label, limit=limit)
    if not items:
        print("No classified mail yet.")
        return 0
    print(f"{'label':<13} {'conf':<7} {'next':<16} subject")
    for item in items:
        print(
            f"{item.label:<13} {item.confidence:<7} {suggested_action(item.label):<16} "
            f"{item.subject}"
        )
        print(f"             {item.sender}  {item.date}")
        if item.job_hint:
            print(f"             job: {item.job_hint}")
    return 0


def cmd_drafts(label: str | None) -> int:
    profile = load_profile()
    items = list_emails(label=label, limit=80)
    paths = write_drafts(items, profile)
    if not paths:
        print("No interview / assessment / info_request / reject drafts to write.")
        return 0
    for path in paths:
        print(path)
    return 0


def cmd_digest() -> int:
    stat = counts()
    ready = list_jobs(status="packet_ready", limit=10)
    interviews = list_emails(label="interview", limit=10)
    requests = list_emails(label="info_request", limit=10)
    print("# Daily job desk")
    print("jobs:", json.dumps(stat, ensure_ascii=False))
    print("mail:", json.dumps(email_counts(), ensure_ascii=False))
    print("\n## Packets waiting for you to click Apply")
    _print_jobs(ready)
    print("\n## Interviews")
    for item in interviews:
        print(f"- {item.subject} ({item.sender})")
    print("\n## Info requests")
    for item in requests:
        print(f"- {item.subject} ({item.sender})")
    return 0


def cmd_serve(host: str, port: int) -> int:
    from .web import serve

    serve(host, port)
    return 0


def _prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def interactive() -> int:
    ensure_dirs()
    print(MENU.format(version=__version__, home=config.APP_DIR))
    if not config.PROFILE_PATH.exists():
        print(f"Missing profile. Copy data/profile.example.json -> {config.PROFILE_PATH}")
        if _prompt("Create starter files now? y/n", "y").lower().startswith("y"):
            cmd_setup()
    if not config.RESUME_PATH.exists():
        print(f"Optional: copy data/resume.example.md -> {config.RESUME_PATH}")
    while True:
        choice = input("\nSelect: ").strip()
        try:
            if choice == "1":
                cmd_search(
                    _prompt("Keywords", default_keywords()),
                    int(_prompt("Pages", "1")),
                    20,
                    int(_prompt("Min score", "25")),
                    _prompt("Where (optional)", ""),
                )
            elif choice == "2":
                cmd_import(_prompt("File path", str(config.IMPORT_DIR / "urls.txt")), 0)
            elif choice == "3":
                status = _prompt("Status filter empty=all", "")
                cmd_shortlist(30, status or None)
            elif choice == "4":
                cmd_packet(_prompt("Job ID"))
            elif choice == "5":
                cmd_batch(int(_prompt("Min score", "40")), int(_prompt("Limit", "8")))
            elif choice == "6":
                cmd_mark(_prompt("Job ID"), _prompt("Status", "applied"))
            elif choice == "7":
                cmd_inbox(int(_prompt("How many messages", "25")))
            elif choice == "8":
                cmd_classify_file(_prompt("Paste file", str(config.IMPORT_DIR / "emails.txt")))
            elif choice == "9":
                label = _prompt("Label empty=all", "")
                cmd_replies(label or None, 40)
            elif choice == "10":
                label = _prompt("Label empty=all actionable", "")
                cmd_drafts(label or None)
            elif choice in {"d", "D"}:
                cmd_digest()
            elif choice in {"s", "S"}:
                cmd_setup()
            elif choice in {"w", "W"}:
                cmd_serve("127.0.0.1", int(_prompt("Port", "8765")))
            elif choice in {"0", "q", "quit"}:
                return 0
            else:
                print("Unknown option.")
        except KeyboardInterrupt:
            print("\nBye.")
            return 0
        except Exception as exc:
            print(exc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JobsDB apply desk for Grok Bot / local CLI")
    parser.add_argument("--home", help="Workspace directory (or set JOB_AGENT_HOME)")
    sub = parser.add_subparsers(dest="cmd")

    search = sub.add_parser("search", help="Search JobsDB public JSON")
    search.add_argument("--keywords", default="", help="Defaults to profile target_roles")
    search.add_argument("--where", default="", help="Optional JobsDB where= location")
    search.add_argument("--pages", type=int, default=1)
    search.add_argument("--page-size", type=int, default=20)
    search.add_argument("--min-score", type=int, default=25)

    imp = sub.add_parser("import-urls", help="Import job URLs or IDs")
    imp.add_argument("--file", required=True)
    imp.add_argument("--min-score", type=int, default=0)

    short = sub.add_parser("shortlist")
    short.add_argument("--status")
    short.add_argument("--limit", type=int, default=30)

    pack = sub.add_parser("packet")
    pack.add_argument("--job-id", required=True)

    batch = sub.add_parser("batch")
    batch.add_argument("--min-score", type=int, default=40)
    batch.add_argument("--limit", type=int, default=8)

    mark = sub.add_parser("mark")
    mark.add_argument("--job-id", required=True)
    mark.add_argument("--status", required=True, choices=STATUSES)

    inbox = sub.add_parser("inbox")
    inbox.add_argument("--limit", type=int, default=25)

    classify = sub.add_parser("classify")
    classify.add_argument("--file", required=True)

    replies = sub.add_parser("replies")
    replies.add_argument("--label")
    replies.add_argument("--limit", type=int, default=40)

    drafts = sub.add_parser("drafts", help="Write bilingual reply drafts")
    drafts.add_argument("--label")

    serve = sub.add_parser("serve", help="Localhost web desk")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)

    sub.add_parser("setup", help="Copy example profile / resume / emails")
    sub.add_parser("digest")
    sub.add_parser("menu")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.home:
        set_home(args.home)
    ensure_dirs()
    if not args.cmd or args.cmd == "menu":
        return interactive()
    if args.cmd == "setup":
        return cmd_setup()
    if args.cmd == "search":
        return cmd_search(args.keywords, args.pages, args.page_size, args.min_score, args.where)
    if args.cmd == "import-urls":
        return cmd_import(args.file, args.min_score)
    if args.cmd == "shortlist":
        return cmd_shortlist(args.limit, args.status)
    if args.cmd == "packet":
        return cmd_packet(args.job_id)
    if args.cmd == "batch":
        return cmd_batch(args.min_score, args.limit)
    if args.cmd == "mark":
        return cmd_mark(args.job_id, args.status)
    if args.cmd == "inbox":
        return cmd_inbox(args.limit)
    if args.cmd == "classify":
        return cmd_classify_file(args.file)
    if args.cmd == "replies":
        return cmd_replies(args.label, args.limit)
    if args.cmd == "drafts":
        return cmd_drafts(args.label)
    if args.cmd == "digest":
        return cmd_digest()
    if args.cmd == "serve":
        return cmd_serve(args.host, args.port)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
