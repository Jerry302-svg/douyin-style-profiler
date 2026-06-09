from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List


STYLE_MODULE_KEYS = [
    "hook",
    "content_structure",
    "expression_style",
    "cta",
    "topic_selection",
    "overall_tone",
    "emotion_analysis",
    "user_psychology",
    "signature_mark",
    "generation_tips",
]


@dataclass
class VideoItem:
    url: str
    title: str = ""
    transcript: str = ""
    like_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StyleProfile:
    nickname: str
    source_url: str = ""
    summary: str = ""
    hook: Dict[str, Any] = field(default_factory=dict)
    content_structure: Dict[str, Any] = field(default_factory=dict)
    expression_style: Dict[str, Any] = field(default_factory=dict)
    cta: Dict[str, Any] = field(default_factory=dict)
    topic_selection: Dict[str, Any] = field(default_factory=dict)
    overall_tone: Dict[str, Any] = field(default_factory=dict)
    emotion_analysis: Dict[str, Any] = field(default_factory=dict)
    user_psychology: Dict[str, Any] = field(default_factory=dict)
    signature_mark: Dict[str, Any] = field(default_factory=dict)
    generation_tips: List[str] = field(default_factory=list)
    style_report: Dict[str, Any] = field(default_factory=dict)
    sample_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["style_report"] = {
            "hook": self.hook,
            "content_structure": self.content_structure,
            "expression_style": self.expression_style,
            "cta": self.cta,
            "topic_selection": self.topic_selection,
            "overall_tone": self.overall_tone,
        }
        return data

