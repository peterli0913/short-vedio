from __future__ import annotations

from pathlib import Path

from . import config
from .models import InboxItem, Profile

ACTIONS = {
    "interview": "draft + calendar",
    "assessment": "open test link",
    "info_request": "draft reply",
    "reject": "close tracker",
    "ack": "no reply",
    "other": "read manually",
}


def suggested_action(label: str) -> str:
    return ACTIONS.get(label, "read manually")


def build_reply_draft(item: InboxItem, profile: Profile) -> str:
    name = profile.full_name or "[Your name]"
    contact = "\n".join(part for part in (name, profile.email, profile.phone) if part)
    locations = ", ".join(profile.locations) or "Hong Kong"
    header = (
        f"To: {item.sender}\n"
        f"Subject: Re: {item.subject}\n"
        f"Label: {item.label} ({item.confidence})\n"
        f"Job hint: {item.job_hint or '—'}\n"
    )
    if item.label == "interview":
        body = f"""您好，

感谢邀请面试。本周我都可以安排通话（香港时区），请告知方便的时间。

{contact}

---
Hi,

Thank you for the interview invitation. I am available for a call this week (Hong Kong time). Please share a time that works.

Best regards,
{name}
"""
    elif item.label == "info_request":
        body = f"""您好，

感谢来信。补充信息如下：

- 到岗：可协商
- 期望薪资：按职位范围面议
- 工作地点：{locations}

如需更新简历或作品，我可以立刻补发。

{contact}

---
Hi,

Thank you for reaching out. Happy to share:

- Start date: flexible
- Salary: happy to discuss against the posted range
- Location: {locations}

I can send an updated resume if useful.

Best regards,
{name}
"""
    elif item.label == "assessment":
        body = f"""您好，

已收到测评 / 作业通知，我会在截止日期前完成。如有登录问题我会再联系。

{contact}

---
Hi,

Thanks for the assessment details. I will complete it before the deadline and follow up if I hit any access issues.

Best regards,
{name}
"""
    elif item.label == "reject":
        body = f"""您好，

感谢告知。祝团队招聘顺利；如后续有更匹配的职位，欢迎再联系。

{contact}

---
Hi,

Thank you for the update. Wishing the team a successful search — please keep me in mind if a closer match opens up.

Best regards,
{name}
"""
    elif item.label == "ack":
        body = "_No reply needed (application received)._\n"
    else:
        body = "_Read this one manually. No auto draft._\n"
    return header + "\n" + body


def write_drafts(items: list[InboxItem], profile: Profile) -> list[Path]:
    config.ensure_dirs()
    config.REPLIES_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for item in items:
        if item.label in {"other", "ack"}:
            continue
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in item.uid)[:40]
        path = config.REPLIES_DIR / f"{item.label}_{safe}.md"
        path.write_text(build_reply_draft(item, profile), encoding="utf-8")
        paths.append(path)
    return paths
