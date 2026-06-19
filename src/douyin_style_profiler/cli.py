from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .analyzer import analyze_video_items
from .collector import collect_profile_topn, load_video_items, save_douyin_login_state, save_video_items
from .diagnostics import diagnostics_has_errors, format_diagnostics, run_diagnostics
from .llm import LLMClient, load_dotenv
from .media import collect_and_download_profile, transcribe_video_items
from .pipeline import run_profile_pipeline, write_transcripts
from .reports import write_outputs


def _add_llm_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--llm", action="store_true", help="使用用户配置的 LLM 生成精细风格档案")
    parser.add_argument("--llm-provider", default="", help="LLM Provider，例如 openai/deepseek/qwen/kimi/zhipu/minimax/anthropic/gemini/openai-compatible")
    parser.add_argument("--llm-model", default="", help="模型名称，由用户按自己的账号填写")
    parser.add_argument("--llm-api-key", default="", help="API Key；更推荐写入 .env 的 LLM_API_KEY")
    parser.add_argument("--llm-base-url", default="", help="自定义 API 地址；openai-compatible 或私有网关需要填写")


def _build_llm_client(args: argparse.Namespace) -> LLMClient | None:
    if not getattr(args, "llm", False):
        return None
    return LLMClient(
        provider=getattr(args, "llm_provider", "") or "",
        model=getattr(args, "llm_model", "") or "",
        api_key=getattr(args, "llm_api_key", "") or "",
        base_url=getattr(args, "llm_base_url", "") or "",
    )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="douyin-style-profiler", description="对标账号风格分析工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="检查本机运行环境和常见配置")
    doctor.add_argument("--state", default="runtime/douyin_storage_state.json", help="Cookie 路径")
    doctor.add_argument("--skip-transcription", action="store_true", help="跳过 FunASR 转写依赖检查")

    login = subparsers.add_parser("login", help="用 Playwright 登录抖音并保存 Cookie")
    login.add_argument("--state", default="runtime/douyin_storage_state.json", help="Cookie 保存路径")
    login.add_argument("--headless", action="store_true", help="无头浏览器模式，不建议首次登录使用")
    login.add_argument("--wait-seconds", type=int, default=0, help="不等待回车，打开浏览器后等待指定秒数再自动保存 Cookie")

    collect = subparsers.add_parser("collect", help="采集对标账号主页 TopN 视频卡片")
    collect.add_argument("--profile-url", required=True, help="抖音博主主页分享链接")
    collect.add_argument("--top-n", type=int, default=10, help="采集数量")
    collect.add_argument("--state", default="runtime/douyin_storage_state.json", help="Cookie 路径")
    collect.add_argument("--output", default="outputs/profile_videos.json", help="采集结果保存路径")
    collect.add_argument("--headed", action="store_true", help="显示浏览器，方便排查")

    download = subparsers.add_parser("download", help="复用楼大壮下载层下载 TopN 视频并抽取音频")
    download.add_argument("--profile-url", required=True, help="抖音博主主页分享链接")
    download.add_argument("--top-n", type=int, default=10, help="下载数量，默认 Top10")
    download.add_argument("--state", default="runtime/douyin_storage_state.json", help="Cookie 路径")
    download.add_argument("--output-dir", default="outputs/profile_media", help="输出目录")
    download.add_argument("--keep-video", action="store_true", help="保留下载的视频文件；默认只保证音频用于转写")
    download.add_argument("--max-concurrency", type=int, default=3, help="下载并发数，最多 5")

    transcribe = subparsers.add_parser("transcribe", help="自动转写已下载的音频")
    transcribe.add_argument("--input", required=True, help="download/collect 产生的 JSON")
    transcribe.add_argument("--output", default="outputs/transcripts.json", help="转写结果保存路径")

    analyze = subparsers.add_parser("analyze", help="根据采集结果或转写稿生成风格档案")
    analyze.add_argument("--input", required=True, help="JSON 文件：可以是 video item 列表，也可以是转写字符串列表")
    analyze.add_argument("--nickname", default="对标账号", help="账号昵称")
    analyze.add_argument("--source-url", default="", help="账号主页链接")
    analyze.add_argument("--output-dir", default="outputs/style_profile", help="输出目录")
    analyze.add_argument("--sample-limit", type=int, default=0, help="最多使用多少条样本参与分析，0 表示不限制")
    analyze.add_argument("--min-transcript-chars", type=int, default=0, help="只使用转写/标题长度不低于该值的样本")
    _add_llm_args(analyze)

    run = subparsers.add_parser("run", help="从主页链接采集并生成风格档案")
    run.add_argument("--profile-url", required=True, help="抖音博主主页分享链接")
    run.add_argument("--nickname", default="对标账号", help="账号昵称")
    run.add_argument("--top-n", type=int, default=10, help="采集数量")
    run.add_argument("--state", default="runtime/douyin_storage_state.json", help="Cookie 路径")
    run.add_argument("--output-dir", default="outputs/style_profile", help="输出目录")
    run.add_argument("--headed", action="store_true", help="显示浏览器，方便排查")
    _add_llm_args(run)
    run.add_argument("--metadata-only", action="store_true", help="只采集主页卡片文本，不下载视频、不转写")
    run.add_argument("--keep-video", action="store_true", help="完整流程中保留下载的视频文件")
    run.add_argument("--max-concurrency", type=int, default=3, help="下载并发数，最多 5")
    run.add_argument("--resume", action="store_true", help="优先复用输出目录中已有 profile_videos.json/transcripts.json")
    run.add_argument("--sample-limit", type=int, default=0, help="最多使用多少条样本参与分析，0 表示不限制")
    run.add_argument("--min-transcript-chars", type=int, default=0, help="只使用转写/标题长度不低于该值的样本")

    args = parser.parse_args()
    if args.command == "doctor":
        checks = run_diagnostics(args.state, include_transcription=not args.skip_transcription)
        print(format_diagnostics(checks))
        if diagnostics_has_errors(checks):
            raise SystemExit(1)
        return
    if args.command == "login":
        path = asyncio.run(save_douyin_login_state(args.state, headless=args.headless, wait_seconds=args.wait_seconds))
        print(f"Cookie 已保存：{path}")
        return
    if args.command == "collect":
        items = asyncio.run(
            collect_profile_topn(
                args.profile_url,
                top_n=args.top_n,
                storage_state_path=args.state,
                headless=not args.headed,
            )
        )
        path = save_video_items(items, args.output)
        print(f"已保存 {len(items)} 条视频卡片：{path}")
        return
    if args.command == "download":
        result = asyncio.run(
            collect_and_download_profile(
                profile_url=args.profile_url,
                output_dir=args.output_dir,
                top_n=args.top_n,
                storage_state_path=args.state,
                keep_video=args.keep_video,
                max_concurrency=args.max_concurrency,
            )
        )
        if result.get("error"):
            raise SystemExit(f"下载失败：{result['error']}")
        items = result.get("items") or []
        path = save_video_items(items, Path(args.output_dir) / "profile_videos.json")
        ok_count = len([item for item in items if not item.metadata.get("error")])
        print(f"已下载/抽音频 {ok_count}/{len(items)} 条：{path}")
        return
    if args.command == "transcribe":
        items = load_video_items(args.input)
        items = transcribe_video_items(items)
        path = write_transcripts(items, args.output)
        ok_count = len([item for item in items if item.metadata.get("transcribe_status") == "success"])
        print(f"已转写 {ok_count}/{len(items)} 条：{path}")
        return
    if args.command == "analyze":
        items = load_video_items(args.input)
        llm_client = _build_llm_client(args)
        profile = analyze_video_items(
            items,
            nickname=args.nickname,
            source_url=args.source_url,
            llm_client=llm_client,
            sample_limit=args.sample_limit,
            min_transcript_chars=args.min_transcript_chars,
        )
        outputs = write_outputs(profile, args.output_dir)
        _print_outputs(outputs)
        return
    if args.command == "run":
        llm_client = _build_llm_client(args)
        outputs = asyncio.run(
            run_profile_pipeline(
                profile_url=args.profile_url,
                nickname=args.nickname,
                top_n=args.top_n,
                storage_state_path=args.state,
                output_dir=args.output_dir,
                llm_client=llm_client,
                headless=not args.headed,
                download=not args.metadata_only,
                transcribe=not args.metadata_only,
                keep_video=args.keep_video,
                max_concurrency=args.max_concurrency,
                resume=args.resume,
                sample_limit=args.sample_limit,
                min_transcript_chars=args.min_transcript_chars,
            )
        )
        _print_outputs(outputs)
        return


def _print_outputs(outputs: dict) -> None:
    print("风格档案已生成：")
    for label, path in outputs.items():
        print(f"- {label}: {path}")


if __name__ == "__main__":
    main()
