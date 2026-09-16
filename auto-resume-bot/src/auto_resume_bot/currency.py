from __future__ import annotations

import re

_WAN_RE = re.compile(r"(\d+(?:\.\d+)?)\s*万")
_K_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[kK](?![a-zA-Z])")
_NUM_RE = re.compile(r"(\d[\d,]{2,}(?:\.\d+)?)")


def _amounts(salary_raw: str) -> list[float]:
    wan = [float(x) * 10_000 for x in _WAN_RE.findall(salary_raw)]
    if wan:
        return wan
    ks = [float(x) * 1_000 for x in _K_RE.findall(salary_raw)]
    if ks:
        return ks
    return [float(x.replace(",", "")) for x in _NUM_RE.findall(salary_raw)]


def parse_salary_to_rmb_min(salary_raw: str, hkd_to_cny: float) -> int | None:
    text = (salary_raw or "").strip()
    if not text:
        return None
    lower = text.lower()
    if ("面议" in text or "negotiable" in lower) and not re.search(r"\d", text):
        return None
    amounts = _amounts(text)
    if not amounts:
        return None
    low = min(amounts)
    is_hkd = any(token in lower for token in ("hkd", "hk$", "hk $")) or "港币" in text or "港元" in text
    is_cny = any(token in text for token in ("人民币", "CNY", "RMB", "元", "¥")) or "cny" in lower or "rmb" in lower
    if is_hkd and not is_cny:
        return int(round(low * hkd_to_cny))
    return int(round(low))
