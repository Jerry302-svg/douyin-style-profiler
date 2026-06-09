from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable


DOUYIN_DOMAINS = ("douyin.com", "iesdouyin.com", "amemv.com")


def load_cookies_from_storage_state(
    storage_state_path: str | Path = "runtime/douyin_storage_state.json",
    domains: Iterable[str] = DOUYIN_DOMAINS,
) -> Dict[str, str]:
    """Load Playwright storage_state cookies as the dict used by the downloader."""
    path = Path(storage_state_path)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    allowed = tuple(domains)
    cookies: Dict[str, str] = {}
    for cookie in data.get("cookies") or []:
        domain = str(cookie.get("domain") or "")
        name = str(cookie.get("name") or "").strip()
        value = str(cookie.get("value") or "")
        if not name:
            continue
        if allowed and not any(domain.endswith(item) for item in allowed):
            continue
        cookies[name] = value
    return cookies


def write_netscape_cookie_file(
    storage_state_path: str | Path,
    cookie_file_path: str | Path,
    domains: Iterable[str] = DOUYIN_DOMAINS,
) -> str:
    """Convert Playwright storage_state to a Netscape cookie file for tools like yt-dlp."""
    source = Path(storage_state_path)
    target = Path(cookie_file_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(source.read_text(encoding="utf-8"))
    allowed = tuple(domains)
    lines = ["# Netscape HTTP Cookie File"]
    for cookie in data.get("cookies") or []:
        domain = str(cookie.get("domain") or "")
        if allowed and not any(domain.endswith(item) for item in allowed):
            continue
        include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
        path = str(cookie.get("path") or "/")
        secure = "TRUE" if cookie.get("secure") else "FALSE"
        expires = str(int(cookie.get("expires") or 0))
        name = str(cookie.get("name") or "")
        value = str(cookie.get("value") or "")
        if not domain or not name:
            continue
        lines.append("\t".join([domain, include_subdomains, path, secure, expires, name, value]))
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(target)
