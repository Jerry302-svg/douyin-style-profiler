from __future__ import annotations

import json
from pathlib import Path
from typing import Awaitable, Callable, Dict, Iterable, List, Optional

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

    if resume and Path(transcripts_path).exists():
        items = load_video_items(transcripts_path)
        if not Path(profile_videos_path).exists():
            profile_videos_path = save_video_items(items, root / "profile_videos.json")
    elif resume and Path(profile_videos_path).exists():
        items = load_video_items(profile_videos_path)
        if transcribe:
            active_transcriber = transcriber or transcribe_video_items
            items = active_transcriber(items)
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
        if transcribe:
            active_transcriber = transcriber or transcribe_video_items
            items = active_transcriber(items)
        transcripts_path = write_transcripts(items, root / "transcripts.json")
    else:
        active_collector = collector or collect_profile_topn
        items = await active_collector(profile_url, top_n, storage_state_path, headless)
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

        profile_videos_path = save_video_items(items, root / "profile_videos.json")
        if transcribe:
            active_transcriber = transcriber or transcribe_video_items
            items = active_transcriber(items)
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
    return {
        "profile_videos": profile_videos_path,
        "transcripts": transcripts_path,
        "json": outputs["style_profile"],
        "report": outputs["style_report"],
        "prompt": outputs["style_prompt"],
        **outputs,
    }
