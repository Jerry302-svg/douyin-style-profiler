from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .analyzer import analyze_video_items
from .collector import collect_profile_topn, load_video_items, save_douyin_login_state, save_video_items
from .llm import LLMClient, load_dotenv
from .reports import write_outputs


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="douyin-style-profiler", description="对标账号风格分析工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login = subparsers.add_parser("login", help="用 Playwright 登录抖音并保存 Cookie")
    login.add_argument("--state", default="runtime/douyin_storage_state.json", help="Cookie 保存路径")
    login.add_argument("--headless", action="store_true", help="无头浏览器模式，不建议首次登录使用")

    collect = subparsers.add_parser("collect", help="采集对标账号主页 TopN 视频卡片")
    collect.add_argument("--profile-url", required=True, help="抖音博主主页分享链接")
    collect.add_argument("--top-n", type=int, default=10, help="采集数量")
    collect.add_argument("--state", default="runtime/douyin_storage_state.json", help="Cookie 路径")
    collect.add_argument("--output", default="outputs/profile_videos.json", help="采集结果保存路径")
    collect.add_argument("--headed", action="store_true", help="显示浏览器，方便排查")

    analyze = subparsers.add_parser("analyze", help="根据采集结果或转写稿生成风格档案")
    analyze.add_argument("--input", required=True, help="JSON 文件：可以是 video item 列表，也可以是转写字符串列表")
    analyze.add_argument("--nickname", default="对标账号", help="账号昵称")
    analyze.add_argument("--source-url", default="", help="账号主页链接")
    analyze.add_argument("--output-dir", default="outputs/style_profile", help="输出目录")
    analyze.add_argument("--llm", action="store_true", help="使用 OpenAI/MiniMax 生成精细风格档案")

    run = subparsers.add_parser("run", help="从主页链接采集并生成风格档案")
    run.add_argument("--profile-url", required=True, help="抖音博主主页分享链接")
    run.add_argument("--nickname", default="对标账号", help="账号昵称")
    run.add_argument("--top-n", type=int, default=10, help="采集数量")
    run.add_argument("--state", default="runtime/douyin_storage_state.json", help="Cookie 路径")
    run.add_argument("--output-dir", default="outputs/style_profile", help="输出目录")
    run.add_argument("--headed", action="store_true", help="显示浏览器，方便排查")
    run.add_argument("--llm", action="store_true", help="使用 OpenAI/MiniMax 生成精细风格档案")

    args = parser.parse_args()
    if args.command == "login":
        path = asyncio.run(save_douyin_login_state(args.state, headless=args.headless))
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
    if args.command == "analyze":
        items = load_video_items(args.input)
        llm_client = LLMClient() if args.llm else None
        profile = analyze_video_items(items, nickname=args.nickname, source_url=args.source_url, llm_client=llm_client)
        outputs = write_outputs(profile, args.output_dir)
        _print_outputs(outputs)
        return
    if args.command == "run":
        items = asyncio.run(
            collect_profile_topn(
                args.profile_url,
                top_n=args.top_n,
                storage_state_path=args.state,
                headless=not args.headed,
            )
        )
        output_dir = Path(args.output_dir)
        save_video_items(items, output_dir / "profile_videos.json")
        llm_client = LLMClient() if args.llm else None
        profile = analyze_video_items(items, nickname=args.nickname, source_url=args.profile_url, llm_client=llm_client)
        outputs = write_outputs(profile, output_dir)
        _print_outputs(outputs)
        return


def _print_outputs(outputs: dict) -> None:
    print("风格档案已生成：")
    for label, path in outputs.items():
        print(f"- {label}: {path}")


if __name__ == "__main__":
    main()

