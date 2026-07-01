from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional

from .analyzer import analyze_video_items
from .collector import collect_profile_topn, load_video_items, save_video_items
from .llm import LLMClient
from .media import collect_and_download_profile, download_video_items, transcribe_video_items
from .reports import write_outputs
from .schemas import VideoItem


Collector = Callable[[str, int, str | Path, bool], Awaitable[List[VideoItem]]]
Downloader = Callable[[Iterable[VideoItem], str | Path, str | Path, bool], List[VideoItem]]
Transcriber = Callable[[Iterable[VideoItem]], List[VideoItem]]


def write_transcripts(items: Iterable[VideoItem], path: str | Path) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps([item.to_dict() for item in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(target)


def write_run_manifest(
    *,
    root: str | Path,
    profile_url: str,
    nickname: str,
    top_n: int,
    stages: Dict[str, Dict[str, Any]],
    items: Iterable[VideoItem],
) -> str:
    target = Path(root) / "run_manifest.json"
    payload = {
        "profile_url": profile_url,
        "nickname": nickname,
        "top_n": top_n,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "stages": stages,
        "items": [_manifest_item(item) for item in items],
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(target)


def _manifest_item(item: VideoItem) -> Dict[str, Any]:
    metadata = item.metadata or {}
    return {
        "url": item.url,
        "title": item.title,
        "has_transcript": bool((item.transcript or "").strip()),
        "download_status": metadata.get("download_status", "unknown"),
        "transcribe_status": metadata.get("transcribe_status", "unknown"),
        "audio_path": metadata.get("audio_path", ""),
        "error": metadata.get("transcribe_error") or metadata.get("download_error") or metadata.get("error") or "",
    }


def _item_key(item: VideoItem) -> str:
    return (item.url or item.title or "").strip()


def _merge_resume_items(base_items: List[VideoItem], transcript_items: List[VideoItem]) -> List[VideoItem]:
    if not base_items:
        return transcript_items
    transcript_by_key = {_item_key(item): item for item in transcript_items if _item_key(item)}
    merged: List[VideoItem] = []
    for base in base_items:
        existing = transcript_by_key.get(_item_key(base))
        if not existing:
            merged.append(base)
            continue
        metadata = {**(base.metadata or {}), **(existing.metadata or {})}
        existing.metadata = metadata
        if not existing.title:
            existing.title = base.title
        if not existing.url:
            existing.url = base.url
        merged.append(existing)
    return merged


def _needs_transcribe_retry(item: VideoItem) -> bool:
    metadata = item.metadata or {}
    if (item.transcript or "").strip() and metadata.get("transcribe_status") == "success":
        return False
    return bool(metadata.get("audio_path"))


def _replace_items(items: List[VideoItem], replacements: Iterable[VideoItem]) -> List[VideoItem]:
    by_key = {_item_key(item): item for item in replacements if _item_key(item)}
    return [by_key.get(_item_key(item), item) for item in items]


async def _default_full_collector(
    profile_url: str,
    top_n: int,
    storage_state_path: str | Path,
    output_dir: str | Path,
    keep_video: bool,
    max_concurrency: int,
) -> Dict[str, object]:
    return await collect_and_download_profile(
        profile_url=profile_url,
        output_dir=output_dir,
        top_n=top_n,
        storage_state_path=storage_state_path,
        keep_video=keep_video,
        max_concurrency=max_concurrency,
    )


async def run_profile_pipeline(
    profile_url: str,
    nickname: str,
    top_n: int,
    storage_state_path: str | Path,
    output_dir: str | Path,
    llm_client: Optional[LLMClient],
    headless: bool = True,
    download: bool = True,
    transcribe: bool = True,
    keep_video: bool = True,
    max_concurrency: int = 3,
    resume: bool = False,
    sample_limit: int = 0,
    min_transcript_chars: int = 0,
    collector: Optional[Collector] = None,
    downloader: Optional[Downloader] = None,
    transcriber: Optional[Transcriber] = None,
) -> Dict[str, str]:
    """Run the full benchmark profile workflow and write all artifacts."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    profile_videos_path = str(root / "profile_videos.json")
    transcripts_path = str(root / "transcripts.json")
    stages: Dict[str, Dict[str, Any]] = {}

    if resume and Path(transcripts_path).exists():
        transcript_items = load_video_items(transcripts_path)
        base_items = load_video_items(profile_videos_path) if Path(profile_videos_path).exists() else []
        items = _merge_resume_items(base_items, transcript_items)
        if not Path(profile_videos_path).exists():
            profile_videos_path = save_video_items(items, root / "profile_videos.json")
        retry_items = [item for item in items if transcribe and _needs_transcribe_retry(item)]
        reused = len(items) - len(retry_items)
        if retry_items:
            active_transcriber = transcriber or transcribe_video_items
            retried = active_transcriber(retry_items)
            items = _replace_items(items, retried)
            transcripts_path = write_transcripts(items, root / "transcripts.json")
        stages["collect"] = {"status": "reused", "items": len(items)}
        stages["download"] = {"status": "reused", "items": len(items)}
        stages["transcribe"] = {
            "status": "resumed",
            "items": len(items),
            "reused": reused,
            "retried": len(retry_items),
            "success": len([item for item in items if item.metadata.get("transcribe_status") == "success"]),
        }
    elif resume and Path(profile_videos_path).exists():
        items = load_video_items(profile_videos_path)
        stages["collect"] = {"status": "reused", "items": len(items)}
        if transcribe:
            active_transcriber = transcriber or transcribe_video_items
            items = active_transcriber(items)
        stages["transcribe"] = {
            "status": "completed" if transcribe else "skipped",
            "items": len(items),
            "success": len([item for item in items if item.metadata.get("transcribe_status") == "success"]),
            "reused": 0,
            "retried": len(items) if transcribe else 0,
        }
        transcripts_path = write_transcripts(items, root / "transcripts.json")
    elif download and collector is None and downloader is None:
        full_result = await _default_full_collector(
            profile_url,
            top_n,
            storage_state_path,
            root,
            keep_video,
            max_concurrency,
        )
        if full_result.get("error"):
            raise RuntimeError(str(full_result["error"]))
        items = list(full_result.get("items") or [])
        blogger = full_result.get("blogger") or {}
        if isinstance(blogger, dict) and blogger.get("nickname") and nickname == "对标账号":
            nickname = str(blogger["nickname"])
        profile_videos_path = save_video_items(items, root / "profile_videos.json")
        stages["collect"] = {"status": "completed", "items": len(items)}
        stages["download"] = {
            "status": "completed",
            "items": len(items),
            "success": len([item for item in items if item.metadata.get("download_status") == "success"]),
        }
        if transcribe:
            active_transcriber = transcriber or transcribe_video_items
            items = active_transcriber(items)
        stages["transcribe"] = {
            "status": "completed" if transcribe else "skipped",
            "items": len(items),
            "success": len([item for item in items if item.metadata.get("transcribe_status") == "success"]),
            "reused": 0,
            "retried": len(items) if transcribe else 0,
        }
        transcripts_path = write_transcripts(items, root / "transcripts.json")
    else:
        active_collector = collector or collect_profile_topn
        items = await active_collector(profile_url, top_n, storage_state_path, headless)
        stages["collect"] = {"status": "completed", "items": len(items)}
        if download:
            if downloader:
                items = downloader(items, root, storage_state_path, keep_video=keep_video)
            else:
                items = await download_video_items(
                    items,
                    output_dir=root,
                    storage_state_path=storage_state_path,
                    keep_video=keep_video,
                    max_concurrency=max_concurrency,
                )
        stages["download"] = {
            "status": "completed" if download else "skipped",
            "items": len(items),
            "success": len([item for item in items if item.metadata.get("download_status") == "success"]),
        }

        profile_videos_path = save_video_items(items, root / "profile_videos.json")
        if transcribe:
            active_transcriber = transcriber or transcribe_video_items
            items = active_transcriber(items)
        stages["transcribe"] = {
            "status": "completed" if transcribe else "skipped",
            "items": len(items),
            "success": len([item for item in items if item.metadata.get("transcribe_status") == "success"]),
            "reused": 0,
            "retried": len(items) if transcribe else 0,
        }
        transcripts_path = write_transcripts(items, root / "transcripts.json")

    usable_items = [item for item in items if (item.transcript or "").strip()]
    if not usable_items:
        usable_items = items
    profile = analyze_video_items(
        usable_items,
        nickname=nickname,
        source_url=profile_url,
        llm_client=llm_client,
        sample_limit=sample_limit,
        min_transcript_chars=min_transcript_chars,
    )
    outputs = write_outputs(profile, root)
    manifest_path = write_run_manifest(
        root=root,
        profile_url=profile_url,
        nickname=nickname,
        top_n=top_n,
        stages=stages,
        items=items,
    )
    return {
        "profile_videos": profile_videos_path,
        "transcripts": transcripts_path,
        "manifest": manifest_path,
        "json": outputs["style_profile"],
        "report": outputs["style_report"],
        "prompt": outputs["style_prompt"],
        **outputs,
    }
