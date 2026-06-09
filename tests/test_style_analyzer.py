import json
import unittest

from douyin_style_profiler.analyzer import analyze_style, parse_llm_style_profile
from douyin_style_profiler.reports import render_markdown_report
from douyin_style_profiler.schemas import STYLE_MODULE_KEYS


SAMPLE_TRANSCRIPTS = [
    "你先别急着下结论。很多问题不是不能解决，是第一步就问错了。先把场景、时间和对方怎么说的整理出来，再判断下一步。",
    "说白了，普通人最怕的不是问题本身，是不知道先做哪一步。你先留证据，再看规则，最后再决定怎么沟通。",
    "如果你也遇到这种情况，别先情绪化硬刚。第一，把材料备份。第二，把对方原话保存。第三，只问一个最关键的问题。",
]


class StyleAnalyzerTest(unittest.TestCase):
    def test_analyze_style_returns_ten_core_modules_without_llm(self):
        profile = analyze_style(
            transcripts=SAMPLE_TRANSCRIPTS,
            nickname="测试对标账号",
            llm_client=None,
        )

        self.assertEqual(profile.nickname, "测试对标账号")
        self.assertTrue(profile.style_report)
        for key in STYLE_MODULE_KEYS:
            self.assertIn(key, profile.to_dict())
            self.assertTrue(profile.to_dict()[key])

    def test_render_markdown_report_contains_core_sections(self):
        profile = analyze_style(SAMPLE_TRANSCRIPTS, nickname="测试账号", llm_client=None)
        markdown = render_markdown_report(profile)

        self.assertIn("# 测试账号 风格分析报告", markdown)
        self.assertIn("## 1. 开头钩子", markdown)
        self.assertIn("## 10. 生成建议", markdown)
        self.assertIn("## 可复制风格提示词", markdown)

    def test_parse_llm_style_profile_requires_all_modules(self):
        bad_json = json.dumps(
            {
                "summary": "只返回了摘要",
                "hook": {"pattern": "提问开头"},
            },
            ensure_ascii=False,
        )

        with self.assertRaisesRegex(ValueError, "缺少必要模块"):
            parse_llm_style_profile(bad_json, nickname="坏输出")

    def test_parse_llm_style_profile_accepts_complete_json(self):
        payload = {
            "summary": "短句、直接、先给动作",
            "hook": {"pattern": "先提醒不要急"},
            "content_structure": {"pattern": "误区 -> 场景 -> 步骤 -> CTA"},
            "expression_style": {"sentence": "短句，口语化"},
            "cta": {"pattern": "评论区留下具体情况"},
            "topic_selection": {"pattern": "选择真实高频痛点"},
            "overall_tone": {"tone": "稳、直接、有陪伴感"},
            "emotion_analysis": {"primary_emotion": "降低焦虑"},
            "user_psychology": {"surface_need": "想知道下一步"},
            "signature_mark": {"phrases": ["先别急", "说白了"]},
            "generation_tips": ["先讲误区", "给一个动作"],
        }

        profile = parse_llm_style_profile(json.dumps(payload, ensure_ascii=False), nickname="完整输出")

        self.assertEqual(profile.summary, "短句、直接、先给动作")
        self.assertEqual(profile.hook["pattern"], "先提醒不要急")
        self.assertEqual(profile.generation_tips, ["先讲误区", "给一个动作"])


if __name__ == "__main__":
    unittest.main()
