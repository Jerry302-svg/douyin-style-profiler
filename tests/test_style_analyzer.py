import json
import unittest

from douyin_style_profiler.analyzer import analyze_style, analyze_video_items, parse_llm_style_profile
from douyin_style_profiler.reports import render_markdown_report
from douyin_style_profiler.schemas import STYLE_MODULE_KEYS, VideoItem


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
        self.assertIn("## 快速复刻清单", markdown)
        self.assertLess(markdown.index("## 快速复刻清单"), markdown.index("## 1. 开头钩子"))
        self.assertIn("- **钩子**：", markdown)
        self.assertIn("- **先做**：", markdown)
        self.assertIn("## 1. 开头钩子", markdown)
        self.assertIn("## 10. 生成建议", markdown)
        self.assertIn("## 可复制风格提示词", markdown)

    def test_analyze_video_items_filters_and_limits_samples(self):
        profile = analyze_video_items(
            [
                VideoItem(url="https://example.com/1", title="短", transcript="太短"),
                VideoItem(url="https://example.com/2", title="长样本一", transcript="第一条足够长的转写内容，适合进入分析。"),
                VideoItem(url="https://example.com/3", title="长样本二", transcript="第二条足够长的转写内容，也适合进入分析。"),
            ],
            nickname="样本号",
            sample_limit=1,
            min_transcript_chars=10,
        )

        self.assertEqual(profile.sample_count, 1)
        self.assertEqual(profile.samples[0]["title"], "长样本一")

    def test_render_markdown_report_contains_sample_details(self):
        profile = analyze_video_items(
            [VideoItem(url="https://example.com/1", title="长样本一", transcript="第一条足够长的转写内容，适合进入分析。")],
            nickname="样本号",
            min_transcript_chars=10,
        )
        markdown = render_markdown_report(profile)

        self.assertIn("## 样本明细", markdown)
        self.assertIn("长样本一", markdown)
        self.assertIn("[打开原视频](https://example.com/1)", markdown)
        self.assertNotIn("：https://example.com/1", markdown)

    def test_render_markdown_report_formats_nested_values_and_sample_preview(self):
        raw = json.dumps(
            {
                "summary": "冷静拆步骤",
                "hook": {"common_patterns": ["先别急", "先留证据"]},
                "content_structure": {"stages": [{"stage": "钩子", "function": "打断情绪"}]},
                "generation_tips": ["先给动作"],
            },
            ensure_ascii=False,
        )
        profile = parse_llm_style_profile(
            raw,
            nickname="格式测试",
            sample_count=1,
            samples=[
                {
                    "index": 1,
                    "title": "样本 1",
                    "url": "",
                    "transcript_chars": 18,
                    "has_transcript": True,
                    "preview": "先别急，先把证据留好。",
                }
            ],
        )

        markdown = render_markdown_report(profile)

        self.assertIn("  - 先别急", markdown)
        self.assertIn("    - stage：钩子", markdown)
        self.assertIn("预览：先别急，先把证据留好。", markdown)
        self.assertNotIn("{'stage'", markdown)

    def test_render_markdown_report_hides_single_text_wrapper(self):
        profile = parse_llm_style_profile(
            json.dumps({"summary": "冷静", "hook": "先别急，先做第一步。"}, ensure_ascii=False),
            nickname="文本包装",
        )

        markdown = render_markdown_report(profile)

        self.assertIn("- 先别急，先做第一步。", markdown)
        self.assertNotIn("**text**", markdown)

    def test_parse_llm_style_profile_allows_missing_modules(self):
        partial_json = json.dumps(
            {
                "summary": "只返回了摘要",
                "hook": {"pattern": "提问开头"},
            },
            ensure_ascii=False,
        )

        profile = parse_llm_style_profile(partial_json, nickname="部分输出")

        self.assertEqual(profile.summary, "只返回了摘要")
        self.assertEqual(profile.hook["pattern"], "提问开头")
        self.assertEqual(profile.signature_mark, {})
        self.assertEqual(profile.generation_tips, [])

    def test_parse_llm_style_profile_ignores_text_after_first_json_object(self):
        payload = {
            "summary": "短句、直接、先给动作",
            "hook": {"pattern": "先提醒不要急"},
        }
        raw = (
            json.dumps(payload, ensure_ascii=False)
            + "\n\n补充说明：这段不应该进入报告。\n"
            + json.dumps({"debug": "第二个 JSON 也不应该进入报告"}, ensure_ascii=False)
        )

        profile = parse_llm_style_profile(raw, nickname="带杂音输出")

        self.assertEqual(profile.summary, "短句、直接、先给动作")
        self.assertEqual(profile.hook["pattern"], "先提醒不要急")

    def test_parse_llm_style_profile_ignores_thinking_json_and_uses_report_json(self):
        raw = """
<think>
我先想一下结构。这里可能会写一个草稿：{"summary": "思考过程里的草稿", "debug": true}
</think>

```json
{
  "summary": "真正的风格总结",
  "hook": {"pattern": "先用冲突钩子开头"},
  "content_structure": {"pattern": "痛点 -> 判断 -> 方法"},
  "generation_tips": ["先抛矛盾", "再给动作"]
}
```
""".strip()

        profile = parse_llm_style_profile(raw, nickname="带思考输出")

        self.assertEqual(profile.summary, "真正的风格总结")
        self.assertEqual(profile.hook["pattern"], "先用冲突钩子开头")
        self.assertEqual(profile.content_structure["pattern"], "痛点 -> 判断 -> 方法")

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
