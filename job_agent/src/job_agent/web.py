from __future__ import annotations

import html
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from . import config
from .config import load_profile
from .drafts import suggested_action, write_drafts
from .jobsdb import search_jobs
from .matcher import rank_jobs
from .store import counts, email_counts, get_job, list_emails, list_jobs, set_status, upsert_emails, upsert_jobs
from .writer import write_packet

STATUSES = ("new", "packet_ready", "applied", "skipped", "interview", "rejected")


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def render_index(notice: str = "") -> str:
    profile = load_profile()
    jobs = list_jobs(limit=40)
    mails = list_emails(limit=30)
    job_stat = counts()
    mail_stat = email_counts()
    job_rows = []
    for job in jobs:
        job_rows.append(
            f"<tr><td>{job.score}</td><td>{_e(job.job_id)}</td><td>{_e(job.status)}</td>"
            f"<td>{_e(job.company)}<br><small>{_e(job.title)}</small></td>"
            f"<td><a href=\"{_e(job.url)}\" target=\"_blank\" rel=\"noreferrer\">open</a></td>"
            f"<td><form method=\"post\" action=\"/packet\" class=\"inline\">"
            f"<input type=\"hidden\" name=\"job_id\" value=\"{_e(job.job_id)}\">"
            f"<button type=\"submit\">packet</button></form> "
            f"<form method=\"post\" action=\"/mark\" class=\"inline\">"
            f"<input type=\"hidden\" name=\"job_id\" value=\"{_e(job.job_id)}\">"
            f"<select name=\"status\">{_status_options(job.status)}</select>"
            f"<button type=\"submit\">mark</button></form></td></tr>"
        )
    mail_rows = []
    for item in mails:
        mail_rows.append(
            f"<tr><td>{_e(item.label)}</td><td>{_e(item.confidence)}</td>"
            f"<td>{_e(suggested_action(item.label))}</td>"
            f"<td>{_e(item.subject)}<br><small>{_e(item.sender)}</small></td>"
            f"<td>{_e(item.job_hint)}</td></tr>"
        )
    banner = f"<p class=\"notice\">{_e(notice)}</p>" if notice else ""
    keywords = " ".join(profile.target_roles[:4]) or "AI engineer"
    return f"""<!doctype html>
<html lang="zh-HK">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>求职工作台</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 24px; color: #1a1a1a; }}
    h1, h2 {{ margin: 0 0 12px; }}
    form.inline {{ display: inline; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 28px; }}
    th, td {{ border-bottom: 1px solid #ddd; text-align: left; padding: 8px; vertical-align: top; }}
    .notice {{ background: #eef6ff; padding: 10px 12px; border-radius: 8px; }}
    .bar {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 16px 0; }}
    input[type=text] {{ min-width: 220px; padding: 6px 8px; }}
    button, select {{ padding: 6px 8px; }}
    small {{ color: #555; }}
    .hint {{ color: #555; max-width: 720px; }}
  </style>
</head>
<body>
  <h1>求职工作台</h1>
  <p class="hint">JobsDB HTML 有 Cloudflare，这里只走公开 JSON。投递包给你官方链接和求职信，Apply 请自己点。邮箱密码只用环境变量。</p>
  {banner}
  <p>workspace: <code>{_e(config.APP_DIR)}</code> · jobs { _e(job_stat) } · mail { _e(mail_stat) }</p>
  <div class="bar">
    <form method="post" action="/search">
      <input type="text" name="keywords" value="{_e(keywords)}" placeholder="keywords">
      <input type="text" name="where" placeholder="Hong Kong (optional)" size="16">
      <button type="submit">搜索 JobsDB</button>
    </form>
    <form method="post" action="/batch">
      <input type="text" name="min_score" value="40" size="4">
      <button type="submit">批量生成投递包</button>
    </form>
    <form method="post" action="/drafts">
      <button type="submit">一键回复草稿</button>
    </form>
  </div>
  <h2>短名单</h2>
  <table>
    <tr><th>score</th><th>id</th><th>status</th><th>company / title</th><th>url</th><th>action</th></tr>
    {''.join(job_rows) or '<tr><td colspan="6">还没有职位。先搜索，或 python3 run.py setup</td></tr>'}
  </table>
  <h2>邮件分类</h2>
  <table>
    <tr><th>label</th><th>conf</th><th>next</th><th>subject</th><th>job</th></tr>
    {''.join(mail_rows) or '<tr><td colspan="5">还没有邮件。粘贴到 workspace/imports/emails.txt 后运行 classify。</td></tr>'}
  </table>
</body>
</html>
"""


def _status_options(current: str) -> str:
    bits = []
    for status in STATUSES:
        selected = " selected" if status == current else ""
        bits.append(f"<option value=\"{_e(status)}\"{selected}>{_e(status)}</option>")
    return "".join(bits)


class DeskHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] != "/":
            self.send_error(404)
            return
        self._html(render_index())

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8")
        form = {k: v[0] if v else "" for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()}
        path = self.path.split("?", 1)[0]
        notice = "unknown action"
        try:
            if path == "/search":
                notice = self._search(form)
            elif path == "/packet":
                notice = self._packet(form)
            elif path == "/batch":
                notice = self._batch(form)
            elif path == "/mark":
                notice = self._mark(form)
            elif path == "/drafts":
                notice = self._drafts()
        except Exception as exc:
            notice = str(exc)
        self._html(render_index(notice))

    def _search(self, form: dict[str, str]) -> str:
        profile = load_profile()
        keywords = (form.get("keywords") or "").strip() or " ".join(profile.target_roles[:4]) or "AI engineer"
        where = (form.get("where") or "").strip()
        jobs, total = search_jobs(keywords, pages=1, page_size=20, where=where)
        ranked = rank_jobs(jobs, profile)
        upsert_jobs(ranked)
        return f"Fetched {len(ranked)} / {total} for {keywords}"

    def _packet(self, form: dict[str, str]) -> str:
        job = get_job(form.get("job_id") or "")
        if not job:
            return "Unknown job."
        path = write_packet(job, load_profile())
        if job.status == "new":
            set_status(job.job_id, "packet_ready")
        return f"Wrote {path}"

    def _batch(self, form: dict[str, str]) -> str:
        try:
            min_score = int(form.get("min_score") or 40)
        except ValueError:
            min_score = 40
        profile = load_profile()
        jobs = [
            job
            for job in list_jobs(limit=200)
            if job.score >= min_score and job.status not in {"applied", "skipped", "rejected"}
        ][:8]
        paths = []
        for job in jobs:
            paths.append(str(write_packet(job, profile)))
            if job.status == "new":
                set_status(job.job_id, "packet_ready")
        return f"Wrote {len(paths)} packets"

    def _mark(self, form: dict[str, str]) -> str:
        job_id = form.get("job_id") or ""
        status = form.get("status") or ""
        if not get_job(job_id):
            return "Unknown job."
        if status not in STATUSES:
            return f"Bad status {status}"
        set_status(job_id, status)
        return f"{job_id} -> {status}"

    def _drafts(self) -> str:
        items = list_emails(limit=80)
        paths = write_drafts(items, load_profile())
        return f"Wrote {len(paths)} reply drafts in {config.REPLIES_DIR}"

    def _html(self, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Desk binds to localhost only.")
    httpd = ThreadingHTTPServer((host, port), DeskHandler)
    print(f"Open http://{host}:{port}  (Ctrl+C to stop)")
    httpd.serve_forever()
