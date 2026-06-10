from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import aiohttp

from .cookies import load_cookies_from_storage_state
from .schemas import VideoItem


MOBILE_SHARE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

_url_sign_lock = asyncio.Lock()
_funasr_model = None


@dataclass
class MediaPaths:
    video_path: Path
    audio_path: Path


def safe_filename(value: str, fallback: str = "video", limit: int = 42) -> str:
    text = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", (value or "").strip())
    text = re.sub(r"\s+", " ", text).strip(" ._")
    return (text or fallback)[:limit]


def extract_aweme_id(url: str) -> str:
    match = re.search(r"/video/(\d+)", url or "")
    return match.group(1) if match else ""


def build_media_paths(output_dir: str | Path, video: VideoItem, index: int) -> MediaPaths:
    root = Path(output_dir)
    aweme_id = extract_aweme_id(video.url) or str(video.metadata.get("aweme_id") or index)
    title = safe_filename(video.title or video.metadata.get("desc") or f"video_{index}")
    stem = f"{index:02d}_{title}_{aweme_id}"
    return MediaPaths(
        video_path=root / "videos" / f"{stem}.mp4",
        audio_path=root / "audio" / f"{stem}.mp3",
    )


def _resolve_ffmpeg_binary() -> str:
    candidates = [
        os.environ.get("FFMPEG_BINARY", "").strip(),
        shutil.which("ffmpeg") or "",
        str(Path.cwd() / "runtime" / "ms-playwright" / "ffmpeg-1011" / "ffmpeg-linux"),
        str(Path.home() / ".local" / "bin" / "ffmpeg"),
        "/usr/local/bin/ffmpeg",
        "/usr/bin/ffmpeg",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return "ffmpeg"


def extract_audio(video_path: str | Path, audio_path: str | Path | None = None) -> Path:
    source = Path(video_path)
    if not source.exists():
        raise FileNotFoundError(f"视频文件不存在: {source}")
    target = Path(audio_path) if audio_path else source.with_name(f"{source.stem}_audio.mp3")
    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            _resolve_ffmpeg_binary(),
            "-y",
            "-i",
            str(source),
            "-vn",
            "-acodec",
            "libmp3lame",
            "-q:a",
            "2",
            str(target),
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 提取音频失败: {result.stderr[:300] if result.stderr else '未知错误'}")
    if not target.exists() or target.stat().st_size < 1024:
        raise RuntimeError(f"ffmpeg 未生成有效音频: {target}")
    return target


async def extract_audio_async(video_path: str | Path, audio_path: str | Path | None = None) -> Path:
    return await asyncio.to_thread(extract_audio, video_path, audio_path)


def postprocess_transcript(
    raw_text: Any,
    punctuator: Optional[Callable[[str], str]] = None,
) -> str:
    text = str(raw_text or "").replace(" ", "").strip()
    if not text:
        return ""
    if punctuator is None:
        from .punctuation import add_punctuation

        punctuator = add_punctuation
    try:
        text = punctuator(text)
    except Exception:
        pass
    try:
        from .punctuation import to_simplified_chinese

        text = to_simplified_chinese(text)
    except Exception:
        pass
    return text.strip()


def parse_douyin_url(url: str) -> Optional[Dict[str, Any]]:
    text = (url or "").strip()
    video_match = re.search(r"/video/(\d+)", text)
    if video_match:
        return {"type": "video", "aweme_id": video_match.group(1)}
    user_match = re.search(r"/user/([A-Za-z0-9_-]+)", text)
    if user_match:
        return {"type": "user", "sec_uid": user_match.group(1)}
    return None


def expand_share_url(url: str, timeout: int = 12) -> str:
    if "v.douyin.com" not in (url or ""):
        return url
    try:
        import requests

        response = requests.get(
            url,
            headers=MOBILE_SHARE_HEADERS,
            allow_redirects=True,
            timeout=timeout,
        )
        return response.url or url
    except Exception:
        return url


def _pick_first_aweme_item(obj: Any) -> Optional[Dict[str, Any]]:
    if isinstance(obj, dict):
        item_list = obj.get("item_list")
        if isinstance(item_list, list):
            for item in item_list:
                if isinstance(item, dict) and item.get("aweme_id") and isinstance(item.get("video"), dict):
                    return item
        for value in obj.values():
            found = _pick_first_aweme_item(value)
            if found:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _pick_first_aweme_item(value)
            if found:
                return found
    return None


def extract_aweme_data_from_share_html(html_text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*</script>", html_text or "", re.DOTALL)
    if not match:
        return None
    try:
        router_data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return _pick_first_aweme_item(router_data)


def fetch_aweme_data_from_share_page(
    share_url: str,
    cookies: Optional[Dict[str, str]] = None,
    timeout: int = 20,
) -> Dict[str, Any]:
    import requests

    response = requests.get(
        share_url,
        headers=MOBILE_SHARE_HEADERS,
        cookies=cookies or None,
        allow_redirects=True,
        timeout=timeout,
    )
    if response.status_code >= 400:
        return {"aweme_data": None, "resolved_url": response.url, "error": f"分享页请求失败: HTTP {response.status_code}"}
    aweme_data = extract_aweme_data_from_share_html(response.text)
    if not aweme_data:
        return {"aweme_data": None, "resolved_url": response.url, "error": "分享页未找到视频数据"}
    return {"aweme_data": aweme_data, "resolved_url": response.url, "error": None}


def _build_download_headers(client: Any, user_agent: Optional[str] = None) -> Dict[str, str]:
    return {
        "Referer": f"{client.BASE_URL}/",
        "Origin": client.BASE_URL,
        "Accept": "*/*",
        "User-Agent": user_agent or client.headers.get("User-Agent", ""),
    }


def _pick_highest_quality_play_addr(video: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    bit_rates = video.get("bit_rate") if isinstance(video, dict) else None
    if not isinstance(bit_rates, list) or not bit_rates:
        return None
    best: Optional[Dict[str, Any]] = None
    best_score = -1
    for entry in bit_rates:
        if not isinstance(entry, dict):
            continue
        play_addr = entry.get("play_addr")
        if not isinstance(play_addr, dict):
            continue
        bit_rate = int(entry.get("bit_rate") or 0)
        width = int(play_addr.get("width") or entry.get("width") or 0)
        score = bit_rate * 10_000 + width
        if score > best_score:
            best_score = score
            best = play_addr
    return best


async def build_video_url(aweme_data: Dict[str, Any], client: Any) -> Optional[Tuple[str, Dict[str, str]]]:
    from urllib.parse import urlparse

    video = aweme_data.get("video", {}) if isinstance(aweme_data, dict) else {}
    play_addr = _pick_highest_quality_play_addr(video) or video.get("play_addr", {})
    candidates = [item for item in (play_addr.get("url_list") or []) if item]
    candidates.sort(key=lambda value: 0 if "watermark=0" in value else 1)
    fallback: Optional[Tuple[str, Dict[str, str]]] = None
    for candidate in candidates:
        parsed = urlparse(candidate)
        if parsed.netloc.endswith("douyin.com"):
            if "X-Bogus=" in candidate:
                return candidate, _build_download_headers(client)
            async with _url_sign_lock:
                signed_url, ua = await asyncio.to_thread(client.sign_url, candidate)
            return signed_url, _build_download_headers(client, user_agent=ua)
        fallback = (candidate, _build_download_headers(client))
    if fallback:
        return fallback
    uri = play_addr.get("uri") or video.get("vid") or video.get("download_addr", {}).get("uri")
    if uri:
        params = {
            "video_id": uri,
            "ratio": "1080p",
            "line": "0",
            "is_play_url": "1",
            "watermark": "0",
            "source": "PackSourceEnum_PUBLISH",
        }
        async with _url_sign_lock:
            signed_url, ua = await asyncio.to_thread(client.build_signed_path, "/aweme/v1/play/", params)
        return signed_url, _build_download_headers(client, user_agent=ua)
    return None


async def download_video_file(
    url: str,
    save_path: str | Path,
    session: aiohttp.ClientSession,
    headers: Optional[Dict[str, str]] = None,
    chunk_size: int = 1024 * 1024,
    max_retries: int = 3,
) -> bool:
    target = Path(save_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(max_retries):
        target.unlink(missing_ok=True)
        try:
            async with session.get(url, headers=headers or {}) as response:
                if response.status not in (200, 206):
                    continue
                with target.open("wb") as handle:
                    async for chunk in response.content.iter_chunked(chunk_size):
                        handle.write(chunk)
            if target.exists() and target.stat().st_size > 1024:
                return True
        except Exception:
            target.unlink(missing_ok=True)
        if attempt < max_retries - 1:
            await asyncio.sleep(1 * (attempt + 1))
    return False


async def fetch_user_posts_top10(profile_url: str, cookies: Dict[str, str], limit: int = 10) -> Dict[str, Any]:
    from douyin.core.api_client import DouyinAPIClient

    expanded_url = expand_share_url(profile_url)
    parsed = parse_douyin_url(expanded_url)
    if not parsed or parsed.get("type") != "user":
        return {"videos": [], "blogger": {}, "error": "无法解析博主主页链接，请确认分享链接指向账号主页"}
    sec_uid = parsed.get("sec_uid")
    if not sec_uid:
        return {"videos": [], "blogger": {}, "error": "无法提取 sec_uid"}
    if not cookies:
        return {"videos": [], "blogger": {}, "error": "未找到抖音 Cookie，请先运行 login"}

    async with DouyinAPIClient(cookies=cookies) as client:
        user_info = await client.get_user_info(sec_uid)
        if not user_info:
            return {"videos": [], "blogger": {}, "error": "获取博主信息失败，Cookie 可能已过期"}
        blogger = {
            "sec_uid": sec_uid,
            "nickname": user_info.get("nickname", ""),
            "avatar_url": user_info.get("avatar_url", ""),
            "follower_count": user_info.get("follower_count", 0),
            "total_favorite": user_info.get("total_favorite", 0),
        }
        all_items: List[Dict[str, Any]] = []
        max_cursor = 0
        has_more = True
        page_count = 0
        while has_more and page_count < 10:
            page = await client.get_user_post(sec_uid, max_cursor=max_cursor, count=20)
            aweme_list = page.get("aweme_list") or []
            if not aweme_list:
                break
            all_items.extend(aweme_list)
            has_more = bool(page.get("has_more", False))
            max_cursor = page.get("max_cursor", 0)
            page_count += 1
        if not all_items:
            return {"videos": [], "blogger": blogger, "error": "未获取到视频列表，Cookie 可能已过期或账号不可访问"}
        all_items.sort(key=lambda item: item.get("statistics", {}).get("digg_count", 0) or 0, reverse=True)
        videos = []
        for item in all_items[: max(1, min(limit, 20))]:
            aweme_id = str(item.get("aweme_id") or "")
            if not aweme_id:
                continue
            desc = (item.get("desc") or "").strip()
            stats = item.get("statistics") or {}
            videos.append(
                {
                    "aweme_id": aweme_id,
                    "url": f"https://www.douyin.com/video/{aweme_id}",
                    "title": desc or f"视频{aweme_id}",
                    "desc": desc,
                    "digg_count": int(stats.get("digg_count", 0) or 0),
                    "collect_count": int(stats.get("collect_count", 0) or 0),
                    "comment_count": int(stats.get("comment_count", 0) or 0),
                    "share_count": int(stats.get("share_count", 0) or 0),
                    "nickname": blogger["nickname"],
                    "sec_uid": sec_uid,
                    "raw_aweme_data": item,
                }
            )
        return {"videos": videos, "blogger": blogger, "error": None}


async def download_single_video(
    aweme_id: str,
    output_dir: str | Path,
    cookies: Dict[str, str],
    raw_aweme_data: Optional[Dict[str, Any]] = None,
    title: str = "",
    index: int = 1,
) -> Dict[str, Any]:
    from douyin.core.api_client import DouyinAPIClient

    video_item = VideoItem(url=f"https://www.douyin.com/video/{aweme_id}", title=title, metadata={"aweme_id": aweme_id})
    paths = build_media_paths(output_dir, video_item, index)
    async with DouyinAPIClient(cookies=cookies) as client:
        aweme_data = raw_aweme_data or await client.get_video_detail(aweme_id)
        if not aweme_data:
            return {"aweme_id": aweme_id, "video_path": "", "audio_path": "", "error": "获取视频详情失败"}
        video_info = await build_video_url(aweme_data, client)
        if not video_info:
            return {"aweme_id": aweme_id, "video_path": "", "audio_path": "", "error": "无法获取视频直链"}
        video_url, headers = video_info
        async with aiohttp.ClientSession() as session:
            ok = await download_video_file(video_url, paths.video_path, session, headers=headers)
        if not ok:
            paths.video_path.unlink(missing_ok=True)
            return {"aweme_id": aweme_id, "video_path": "", "audio_path": "", "error": "下载视频失败"}
        try:
            audio_path = await extract_audio_async(paths.video_path, paths.audio_path)
        except Exception as exc:
            paths.video_path.unlink(missing_ok=True)
            paths.audio_path.unlink(missing_ok=True)
            return {"aweme_id": aweme_id, "video_path": str(paths.video_path), "audio_path": "", "error": f"提取音频失败: {exc}"}
        return {
            "aweme_id": aweme_id,
            "video_path": str(paths.video_path),
            "audio_path": str(audio_path),
            "desc": aweme_data.get("desc") or title,
            "error": None,
        }


async def download_single_video_by_share_page(
    share_url: str,
    output_dir: str | Path,
    cookies: Dict[str, str],
    index: int = 1,
) -> Dict[str, Any]:
    try:
        fetch_result = await asyncio.to_thread(fetch_aweme_data_from_share_page, share_url, cookies)
    except Exception as exc:
        return {"aweme_id": "", "video_path": "", "audio_path": "", "error": f"分享页解析失败: {exc}"}
    if fetch_result.get("error"):
        return {"aweme_id": "", "video_path": "", "audio_path": "", "error": fetch_result["error"]}
    aweme_data = fetch_result.get("aweme_data") or {}
    aweme_id = str(aweme_data.get("aweme_id") or "")
    if not aweme_id:
        return {"aweme_id": "", "video_path": "", "audio_path": "", "error": "分享页未返回 aweme_id"}
    result = await download_single_video(
        aweme_id=aweme_id,
        output_dir=output_dir,
        cookies=cookies,
        raw_aweme_data=aweme_data,
        title=aweme_data.get("desc") or "",
        index=index,
    )
    result["resolved_url"] = fetch_result.get("resolved_url", "")
    return result


async def download_video_items(
    items: Iterable[VideoItem],
    output_dir: str | Path,
    storage_state_path: str | Path = "runtime/douyin_storage_state.json",
    keep_video: bool = True,
    max_concurrency: int = 3,
) -> List[VideoItem]:
    cookies = load_cookies_from_storage_state(storage_state_path)
    semaphore = asyncio.Semaphore(max(1, min(max_concurrency, 5)))
    item_list = list(items)

    async def _one(index: int, item: VideoItem) -> VideoItem:
        aweme_id = item.metadata.get("aweme_id") or extract_aweme_id(item.url)
        async with semaphore:
            if aweme_id:
                result = await download_single_video(
                    aweme_id=str(aweme_id),
                    output_dir=output_dir,
                    cookies=cookies,
                    raw_aweme_data=item.metadata.get("raw_aweme_data"),
                    title=item.title,
                    index=index,
                )
            else:
                result = await download_single_video_by_share_page(item.url, output_dir, cookies, index=index)
        item.metadata.update(result)
        item.metadata["download_status"] = "failed" if result.get("error") else "success"
        if result.get("desc") and not item.title:
            item.title = result["desc"]
        if not keep_video and result.get("video_path"):
            try:
                Path(result["video_path"]).unlink(missing_ok=True)
            except OSError:
                pass
        return item

    return await asyncio.gather(*[_one(index, item) for index, item in enumerate(item_list, 1)])


async def collect_and_download_profile(
    profile_url: str,
    output_dir: str | Path,
    top_n: int = 10,
    storage_state_path: str | Path = "runtime/douyin_storage_state.json",
    keep_video: bool = True,
    max_concurrency: int = 3,
) -> Dict[str, Any]:
    cookies = load_cookies_from_storage_state(storage_state_path)
    collect_result = await fetch_user_posts_top10(profile_url, cookies=cookies, limit=top_n)
    if collect_result.get("error"):
        return {"items": [], "blogger": collect_result.get("blogger") or {}, "error": collect_result["error"]}
    items = []
    for video in collect_result.get("videos") or []:
        items.append(
            VideoItem(
                url=video.get("url") or f"https://www.douyin.com/video/{video.get('aweme_id')}",
                title=video.get("title") or video.get("desc") or "",
                like_count=int(video.get("digg_count") or 0),
                metadata={
                    "aweme_id": video.get("aweme_id") or "",
                    "raw_aweme_data": video.get("raw_aweme_data"),
                    "digg_count": video.get("digg_count", 0),
                    "collect_count": video.get("collect_count", 0),
                    "comment_count": video.get("comment_count", 0),
                    "share_count": video.get("share_count", 0),
                    "sec_uid": video.get("sec_uid", ""),
                    "nickname": video.get("nickname", ""),
                },
            )
        )
    downloaded = await download_video_items(
        items,
        output_dir=output_dir,
        storage_state_path=storage_state_path,
        keep_video=keep_video,
        max_concurrency=max_concurrency,
    )
    return {"items": downloaded, "blogger": collect_result.get("blogger") or {}, "error": None}


def transcribe_audio(audio_path: str | Path) -> str:
    global _funasr_model
    source = Path(audio_path)
    if not source.exists():
        raise FileNotFoundError(f"音频文件不存在: {source}")
    if source.stat().st_size < 1024:
        raise ValueError(f"音频文件过小，可能损坏: {source}")
    try:
        from funasr import AutoModel
    except ImportError as exc:
        raise RuntimeError("未安装 FunASR，请先安装 requirements-transcribe.txt 或运行 bootstrap 脚本") from exc
    if _funasr_model is None:
        modelscope_cache = Path(os.environ.get("MODELSCOPE_CACHE") or Path.cwd() / "models" / "modelscope")
        modelscope_cache.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("MODELSCOPE_CACHE", str(modelscope_cache))
        _funasr_model = AutoModel(
            model=os.environ.get("FUNASR_MODEL", "paraformer-zh"),
            model_revision=os.environ.get("FUNASR_MODEL_REVISION", "v2.0.4"),
            vad_model=os.environ.get("FUNASR_VAD_MODEL", "fsmn-vad"),
            disable_update=True,
        )
    result = _funasr_model.generate(str(source), batch_size_s=300)
    if not isinstance(result, list) or not result:
        raise RuntimeError("FunASR 未返回有效转写结果")
    raw_text = result[0].get("text", result[0]) if isinstance(result[0], dict) else result[0]
    return postprocess_transcript(raw_text)


def transcribe_video_items(
    items: Iterable[VideoItem],
    transcribe_fn: Optional[Callable[[Path], str]] = None,
) -> List[VideoItem]:
    transcriber = transcribe_fn or transcribe_audio
    result: List[VideoItem] = []
    for item in items:
        audio_path = Path(str(item.metadata.get("audio_path") or ""))
        try:
            if not audio_path.exists():
                raise FileNotFoundError(f"音频文件不存在: {audio_path}")
            item.transcript = transcriber(audio_path)
            item.metadata["transcribe_status"] = "success"
            item.metadata.pop("transcribe_error", None)
        except Exception as exc:
            item.metadata["transcribe_status"] = "failed"
            item.metadata["transcribe_error"] = str(exc)
        result.append(item)
    return result
