from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Awaitable, Callable, List

from .schemas import VideoItem


DOUYIN_HOME = "https://www.douyin.com"


async def save_douyin_login_state(
    storage_state_path: str | Path = "runtime/douyin_storage_state.json",
    headless: bool = False,
    wait_seconds: int = 0,
) -> str:
    """Open Douyin with Playwright and save cookies after the user logs in."""
    from playwright.async_api import async_playwright

    target = Path(storage_state_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        context = await browser.new_context(locale="zh-CN")
        page = await context.new_page()
        await page.goto(DOUYIN_HOME, wait_until="domcontentloaded", timeout=60000)
        await wait_for_login_confirmation(wait_seconds=wait_seconds)
        await context.storage_state(path=str(target))
        await browser.close()
    return str(target)


async def wait_for_login_confirmation(
    wait_seconds: int = 0,
    input_fn: Callable[[], str] = input,
    sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    if wait_seconds > 0:
        print(f"请在打开的浏览器里登录抖音。程序会在 {wait_seconds} 秒后自动保存 Cookie。")
        await sleep_fn(wait_seconds)
        return
    print("请在打开的浏览器里登录抖音。登录完成后回到终端按 Enter。")
    try:
        await asyncio.to_thread(input_fn)
    except EOFError:
        print("当前终端不能读取回车。请改用 --wait-seconds 60 这类参数自动等待后保存 Cookie。")
        raise


async def collect_profile_topn(
    profile_url: str,
    top_n: int = 10,
    storage_state_path: str | Path = "runtime/douyin_storage_state.json",
    headless: bool = True,
    scroll_rounds: int = 4,
) -> List[VideoItem]:
    """Collect visible TopN video links and card text from a Douyin profile page."""
    from playwright.async_api import async_playwright

    storage_path = Path(storage_state_path)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        context_kwargs = {"locale": "zh-CN"}
        if storage_path.exists():
            context_kwargs["storage_state"] = str(storage_path)
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(3000)
        for _ in range(max(1, scroll_rounds)):
            await page.mouse.wheel(0, 1600)
            await page.wait_for_timeout(1200)
        raw_items = await page.evaluate(
            """
            () => {
              const anchors = Array.from(document.querySelectorAll('a[href*="/video/"]'));
              const seen = new Set();
              return anchors.map((a) => {
                const href = a.href || '';
                if (!href || seen.has(href)) return null;
                seen.add(href);
                const card = a.closest('div') || a;
                const text = (card.innerText || a.innerText || a.getAttribute('aria-label') || '').trim();
                return {url: href, title: text.replace(/\\s+/g, ' ').slice(0, 240)};
              }).filter(Boolean);
            }
            """
        )
        await context.storage_state(path=str(storage_path))
        await browser.close()
    items = []
    for item in raw_items[:top_n]:
        items.append(VideoItem(url=item.get("url", ""), title=item.get("title", ""), transcript=item.get("title", "")))
    return items


def save_video_items(items: List[VideoItem], path: str | Path) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps([item.to_dict() for item in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(target)


def load_video_items(path: str | Path) -> List[VideoItem]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = []
    for item in data:
        if isinstance(item, str):
            items.append(VideoItem(url="", title="", transcript=item))
        elif isinstance(item, dict):
            items.append(VideoItem(**{key: item.get(key) for key in ["url", "title", "transcript", "like_count", "metadata"] if key in item}))
    return items
