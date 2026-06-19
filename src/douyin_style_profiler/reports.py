from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .schemas import StyleProfile


SECTION_TITLES = [
    ("hook", "1. 开头钩子"),
    ("content_structure", "2. 内容结构"),
    ("expression_style", "3. 表达方式"),
    ("cta", "4. 互动引导"),
    ("topic_selection", "5. 选题方式"),
    ("overall_tone", "6. 整体语气"),
    ("emotion_analysis", "7. 情绪曲线"),
    ("user_psychology", "8. 用户心理"),
    ("signature_mark", "9. 标志性表达"),
    ("generation_tips", "10. 生成建议"),
]


def render_markdown_report(profile: StyleProfile) -> str:
    lines = [
        f"# {profile.nickname} 风格分析报告",
        "",
        f"- 来源链接：{profile.source_url or '未提供'}",
        f"- 样本数量：{profile.sample_count}",
        f"- 生成时间：{profile.created_at}",
        f"- 一句话总结：{profile.summary}",
        "",
    ]
    data = profile.to_dict()
    for key, title in SECTION_TITLES:
        lines.extend([f"## {title}", ""])
        value = data.get(key)
        lines.extend(_render_value(value))
        lines.append("")
    if profile.samples:
        lines.extend(["## 样本明细", ""])
        for sample in profile.samples:
            title = _short_text(sample.get("title") or f"样本 {sample.get('index', '')}".strip(), limit=72)
            url = _link("打开原视频", sample.get("url") or "")
            chars = sample.get("transcript_chars", 0)
            source = "转写稿" if sample.get("has_transcript") else "标题/描述"
            lines.append(f"- {title}（{source}，{chars} 字）：{url}")
            preview = sample.get("preview") or sample.get("transcript_preview") or ""
            if preview:
                lines.append(f"  - 预览：{preview}")
        lines.append("")
    lines.extend([
        "## 可复制风格提示词",
        "",
        render_style_prompt(profile),
        "",
    ])
    return "\n".join(lines).strip() + "\n"


def render_style_prompt(profile: StyleProfile) -> str:
    return (
        f"请参考“{profile.nickname}”的表达风格：{profile.summary}\n"
        "只学习结构、节奏、钩子、口语密度和互动方式，不复制原文、事实、身份或具体案例。\n"
        f"开头方式：{_compact(profile.hook)}\n"
        f"内容结构：{_compact(profile.content_structure)}\n"
        f"表达方式：{_compact(profile.expression_style)}\n"
        f"互动引导：{_compact(profile.cta)}\n"
        f"生成建议：{'；'.join(profile.generation_tips[:8])}"
    )


def write_outputs(profile: StyleProfile, output_dir: str | Path) -> Dict[str, str]:
    import json

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    profile_json = target / "style_profile.json"
    report_md = target / "style_report.md"
    prompt_txt = target / "style_prompt.txt"
    profile_json.write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(render_markdown_report(profile), encoding="utf-8")
    prompt_txt.write_text(render_style_prompt(profile), encoding="utf-8")
    return {
        "style_profile": str(profile_json),
        "style_report": str(report_md),
        "style_prompt": str(prompt_txt),
    }


def _render_value(value: Any) -> list[str]:
    if isinstance(value, dict):
        if set(value.keys()) == {"text"}:
            return [f"- {_compact(value.get('text'))}"]
        lines: list[str] = []
        for key, item in value.items():
            if _is_complex(item):
                lines.append(f"- **{key}**：")
                lines.extend(_render_nested(item, indent=2))
            else:
                lines.append(f"- **{key}**：{_compact(item)}")
        return lines
    if isinstance(value, list):
        return _render_nested(value, indent=0)
    return [str(value)]


def _render_nested(value: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, list):
        lines: list[str] = []
        for item in value:
            if isinstance(item, dict):
                lines.extend(_render_nested(item, indent=indent + 2))
            elif isinstance(item, list):
                lines.extend(_render_nested(item, indent=indent + 2))
            else:
                lines.append(f"{prefix}- {_compact(item)}")
        return lines
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if _is_complex(item):
                lines.append(f"{prefix}- {key}：")
                lines.extend(_render_nested(item, indent=indent + 2))
            else:
                lines.append(f"{prefix}- {key}：{_compact(item)}")
        return lines
    return [f"{prefix}- {_compact(value)}"]


def _compact(value: Any) -> str:
    if isinstance(value, dict):
        if set(value.keys()) == {"text"}:
            return _compact(value.get("text"))
        return "；".join(f"{key}: {_compact(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "、".join(_compact(item) for item in value)
    return str(value)


def _is_complex(value: Any) -> bool:
    return isinstance(value, (dict, list))


def _link(label: str, url: str) -> str:
    value = (url or "").strip()
    if not value:
        return "未提供"
    return f"[{label}]({value})"


def _short_text(value: Any, limit: int = 72) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."
