from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional

from .llm import LLMClient
from .schemas import STYLE_MODULE_KEYS, StyleProfile, VideoItem


def analyze_style(
    transcripts: Iterable[str],
    nickname: str = "对标账号",
    source_url: str = "",
    llm_client: Optional[LLMClient] = None,
) -> StyleProfile:
    clean_transcripts = [text.strip() for text in transcripts if text and text.strip()]
    if not clean_transcripts:
        raise ValueError("至少需要一条转写文本才能生成风格分析")
    if llm_client:
        prompt = build_style_prompt(clean_transcripts, nickname=nickname, source_url=source_url)
        raw = llm_client.complete(prompt, temperature=0.2, max_tokens=5000)
        return parse_llm_style_profile(raw, nickname=nickname, source_url=source_url, sample_count=len(clean_transcripts))
    return deterministic_style_profile(clean_transcripts, nickname=nickname, source_url=source_url)


def analyze_video_items(
    videos: Iterable[VideoItem],
    nickname: str = "对标账号",
    source_url: str = "",
    llm_client: Optional[LLMClient] = None,
) -> StyleProfile:
    return analyze_style(
        transcripts=[video.transcript or video.title for video in videos],
        nickname=nickname,
        source_url=source_url,
        llm_client=llm_client,
    )


def build_style_prompt(transcripts: List[str], nickname: str, source_url: str = "") -> List[Dict[str, str]]:
    samples = "\n\n".join([f"【样本 {index + 1}】\n{text[:1800]}" for index, text in enumerate(transcripts[:20])])
    system = (
        "你是短视频对标账号风格分析专家。你只分析表达风格、结构、选题方式和用户心理，"
        "不要评价账号本人，不要复刻具体事实，不要输出营销废话。"
        "输出必须是严格 JSON object，不要 markdown。"
    )
    user = f"""
请基于以下对标账号视频转写，生成结构化风格档案。

账号昵称：{nickname}
账号链接：{source_url or "未提供"}

必须包含这些顶层字段：
summary, hook, content_structure, expression_style, cta, topic_selection, overall_tone,
emotion_analysis, user_psychology, signature_mark, generation_tips

字段要求：
- summary: 一句话概括这个账号的可学习风格。
- hook: 开头钩子的常见方式、句式、禁忌。
- content_structure: 内容推进结构。
- expression_style: 句长、口语密度、停顿、转折、真实口播感。
- cta: 常见互动引导方式。
- topic_selection: 这个账号如何选题、如何放大用户痛点。
- overall_tone: 整体语气。
- emotion_analysis: 情绪曲线。
- user_psychology: 目标用户心理。
- signature_mark: 标志性表达、常用句式、节奏标记。
- generation_tips: 8-12 条可执行生成建议。

转写样本：
{samples}
""".strip()
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_llm_style_profile(raw_text: str, nickname: str = "对标账号", source_url: str = "", sample_count: int = 0) -> StyleProfile:
    data = _extract_json(raw_text)
    if "style_report" in data and isinstance(data["style_report"], dict):
        nested = data["style_report"]
        for key in ["hook", "content_structure", "expression_style", "cta", "topic_selection", "overall_tone"]:
            data.setdefault(key, nested.get(key))
    missing = [key for key in STYLE_MODULE_KEYS if not _has_value(data.get(key))]
    if missing:
        raise ValueError(f"缺少必要模块：{', '.join(missing)}")
    tips = data.get("generation_tips") or []
    if isinstance(tips, str):
        tips = [line.strip("- ").strip() for line in tips.splitlines() if line.strip()]
    profile = StyleProfile(
        nickname=nickname,
        source_url=source_url,
        summary=str(data.get("summary") or "").strip(),
        hook=_as_dict(data["hook"]),
        content_structure=_as_dict(data["content_structure"]),
        expression_style=_as_dict(data["expression_style"]),
        cta=_as_dict(data["cta"]),
        topic_selection=_as_dict(data["topic_selection"]),
        overall_tone=_as_dict(data["overall_tone"]),
        emotion_analysis=_as_dict(data["emotion_analysis"]),
        user_psychology=_as_dict(data["user_psychology"]),
        signature_mark=_as_dict(data["signature_mark"]),
        generation_tips=[str(item).strip() for item in tips if str(item).strip()],
        sample_count=sample_count,
    )
    profile.style_report = profile.to_dict()["style_report"]
    return profile


def deterministic_style_profile(transcripts: List[str], nickname: str, source_url: str = "") -> StyleProfile:
    joined = "\n".join(transcripts)
    first_sentences = _top_sentences(joined, limit=5)
    question_ratio = joined.count("？") + joined.count("?")
    cta_terms = [term for term in ["评论区", "私信", "留言", "收藏", "转发", "关注"] if term in joined]
    filler_terms = [term for term in ["嗯", "其实", "说白了", "你看", "换个说法", "先别急"] if term in joined]
    profile = StyleProfile(
        nickname=nickname,
        source_url=source_url,
        sample_count=len(transcripts),
        summary="短句推进、先降低焦虑，再给目标用户一个可执行动作。",
        hook={
            "pattern": "常用提醒、反问或具体场景开头。",
            "examples": first_sentences,
            "question_density": question_ratio,
        },
        content_structure={
            "pattern": "痛点/误区 -> 解释判断 -> 具体步骤 -> 互动引导",
            "pace": "每段只推进一个小判断，避免长篇理论。",
        },
        expression_style={
            "sentence": "偏短句、口语化、动作导向。",
            "fillers": filler_terms or ["其实", "你看", "说白了"],
            "natural_speech": "允许轻微停顿和换个说法，避免书面报告腔。",
        },
        cta={
            "pattern": "把用户当前卡点留到评论区或私信。",
            "observed_terms": cta_terms or ["评论区"],
        },
        topic_selection={
            "pattern": "优先选择用户容易焦虑、误判或不知道下一步的具体问题。",
            "source": "来自视频转写中的高频场景和问题表达。",
        },
        overall_tone={
            "tone": "稳、直接、有陪伴感",
            "boundary": "可以有冲突感，但不辱骂，不夸大结果。",
        },
        emotion_analysis={
            "opening": "先接住焦虑",
            "middle": "把问题拆小",
            "ending": "给一个低门槛行动",
        },
        user_psychology={
            "surface_need": "想知道这件事该怎么办",
            "deep_fear": "怕走错第一步、浪费时间或被对方拿捏",
            "trust_trigger": "具体场景、明确步骤、保守边界",
        },
        signature_mark={
            "phrases": filler_terms or ["先别急", "说白了", "你看"],
            "rhythm": "先提醒，再解释，再给动作",
        },
        generation_tips=[
            "开头先用一个具体问题或提醒，不要自我介绍。",
            "每 1-2 句推进一个判断，避免长句堆概念。",
            "中段必须给用户一个能马上执行的小动作。",
            "不要复制对标账号的事实、案例和身份，只学习结构和表达。",
            "结尾用评论区/私信引导用户留下具体场景。",
            "语气可以直接，但不要辱骂、恐吓或承诺结果。",
            "加入自然口语连接词，比如“其实”“你看”“说白了”。",
            "保持目标用户视角一致，正文里的“你”只指目标用户。",
        ],
    )
    profile.style_report = profile.to_dict()["style_report"]
    return profile


def _extract_json(text: str) -> Dict[str, Any]:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned).strip()
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    if cleaned and cleaned[0] != "{":
        start = cleaned.find("{")
        if start >= 0:
            cleaned = cleaned[start:]
    if cleaned.startswith("{") and "}" in cleaned:
        cleaned = cleaned[: cleaned.rfind("}") + 1]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM 没有返回合法 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("LLM JSON 必须是 object")
    return data


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set)):
        return any(_has_value(item) for item in value)
    if isinstance(value, dict):
        return any(_has_value(item) for item in value.values())
    return True


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {"items": value}
    return {"text": str(value)}


def _top_sentences(text: str, limit: int = 5) -> List[str]:
    parts = re.split(r"[。！？!?；;\n]+", text)
    return [part.strip() for part in parts if part.strip()][:limit]

