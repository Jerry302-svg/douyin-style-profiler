import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from douyin_style_profiler.schemas import VideoItem


class MediaPipelineTest(unittest.TestCase):
    def test_build_media_paths_sanitizes_title_and_partitions_outputs(self):
        from douyin_style_profiler.media import build_media_paths

        with tempfile.TemporaryDirectory() as tmp:
            paths = build_media_paths(
                output_dir=tmp,
                video=VideoItem(url="https://www.douyin.com/video/123456789", title='这/个:"标题"? 很长很长很长'),
                index=1,
            )

            self.assertTrue(str(paths.video_path).startswith(str(Path(tmp) / "videos")))
            self.assertTrue(str(paths.audio_path).startswith(str(Path(tmp) / "audio")))
            self.assertIn("123456789", paths.video_path.name)
            self.assertNotIn("/", paths.video_path.name)
            self.assertEqual(paths.video_path.suffix, ".mp4")
            self.assertEqual(paths.audio_path.suffix, ".mp3")

    def test_write_netscape_cookie_file_converts_playwright_storage_state(self):
        from douyin_style_profiler.cookies import write_netscape_cookie_file

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "storage_state.json"
            cookie_path = Path(tmp) / "cookies.txt"
            state_path.write_text(
                json.dumps(
                    {
                        "cookies": [
                            {
                                "name": "sessionid",
                                "value": "abc",
                                "domain": ".douyin.com",
                                "path": "/",
                                "expires": 1999999999,
                                "httpOnly": True,
                                "secure": True,
                            },
                            {
                                "name": "ignore",
                                "value": "x",
                                "domain": ".example.com",
                                "path": "/",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            written = write_netscape_cookie_file(state_path, cookie_path)
            content = Path(written).read_text(encoding="utf-8")

            self.assertIn("# Netscape HTTP Cookie File", content)
            self.assertIn(".douyin.com", content)
            self.assertIn("sessionid", content)
            self.assertNotIn("example.com", content)

    def test_transcribe_video_items_updates_transcript_and_keeps_metadata(self):
        from douyin_style_profiler.media import transcribe_video_items

        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "sample.mp3"
            audio_path.write_bytes(b"fake-audio")
            items = [
                VideoItem(
                    url="https://www.douyin.com/video/1",
                    title="样本",
                    metadata={"audio_path": str(audio_path), "video_path": str(Path(tmp) / "sample.mp4")},
                )
            ]

            def fake_transcribe(path):
                self.assertEqual(path, audio_path)
                return "这是一段自动转写出来的口播内容。"

            result = transcribe_video_items(items, transcribe_fn=fake_transcribe)

            self.assertEqual(result[0].transcript, "这是一段自动转写出来的口播内容。")
            self.assertEqual(result[0].metadata["transcribe_status"], "success")
            self.assertEqual(result[0].metadata["audio_path"], str(audio_path))

    def test_postprocess_transcript_removes_spaces_adds_model_punctuation_and_simplifies(self):
        from douyin_style_profiler.media import postprocess_transcript

        result = postprocess_transcript(
            "這 是 一 段 轉 寫",
            punctuator=lambda text: f"{text}。",
        )

        self.assertEqual(result, "这是一段转写。")

    def test_postprocess_transcript_keeps_simplified_text_when_punctuation_model_fails(self):
        from douyin_style_profiler.media import postprocess_transcript

        def broken_punctuator(text):
            raise RuntimeError("model missing")

        result = postprocess_transcript("這 是 一 段 轉 寫", punctuator=broken_punctuator)

        self.assertEqual(result, "这是一段转写")

    def test_run_profile_pipeline_collects_downloads_transcribes_and_writes_outputs(self):
        from douyin_style_profiler.pipeline import run_profile_pipeline

        async def fake_collector(profile_url, top_n, storage_state_path, headless):
            self.assertEqual(profile_url, "https://v.douyin.com/example/")
            self.assertEqual(top_n, 2)
            return [
                VideoItem(url="https://www.douyin.com/video/1", title="第一条"),
                VideoItem(url="https://www.douyin.com/video/2", title="第二条"),
            ]

        def fake_downloader(items, output_dir, storage_state_path, keep_video=True):
            for index, item in enumerate(items, 1):
                item.metadata["video_path"] = str(Path(output_dir) / "videos" / f"{index}.mp4")
                item.metadata["audio_path"] = str(Path(output_dir) / "audio" / f"{index}.mp3")
                item.metadata["download_status"] = "success"
            return items

        def fake_transcriber(items):
            for item in items:
                item.transcript = f"{item.title} 的完整转写。"
                item.metadata["transcribe_status"] = "success"
            return items

        with tempfile.TemporaryDirectory() as tmp:
            outputs = asyncio.run(
                run_profile_pipeline(
                    profile_url="https://v.douyin.com/example/",
                    nickname="测试账号",
                    top_n=2,
                    storage_state_path=Path(tmp) / "state.json",
                    output_dir=tmp,
                    llm_client=None,
                    headless=True,
                    collector=fake_collector,
                    downloader=fake_downloader,
                    transcriber=fake_transcriber,
                )
            )

            self.assertTrue(Path(outputs["profile_videos"]).exists())
            self.assertTrue(Path(outputs["transcripts"]).exists())
            self.assertTrue(Path(outputs["json"]).exists())
            transcripts = json.loads(Path(outputs["transcripts"]).read_text(encoding="utf-8"))
            self.assertEqual(len(transcripts), 2)
            self.assertEqual(transcripts[0]["transcript"], "第一条 的完整转写。")

    def test_run_profile_pipeline_resume_reuses_existing_transcripts_and_filters_samples(self):
        from douyin_style_profiler.pipeline import run_profile_pipeline

        async def forbidden_collector(*args, **kwargs):
            raise AssertionError("resume should not collect again when transcripts exist")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            transcripts_path = root / "transcripts.json"
            transcripts_path.write_text(
                json.dumps(
                    [
                        {
                            "url": "https://www.douyin.com/video/1",
                            "title": "短样本",
                            "transcript": "太短",
                            "metadata": {"transcribe_status": "success"},
                        },
                        {
                            "url": "https://www.douyin.com/video/2",
                            "title": "有效样本一",
                            "transcript": "这是第一条足够长的转写内容，用于分析账号表达节奏。",
                            "metadata": {"transcribe_status": "success"},
                        },
                        {
                            "url": "https://www.douyin.com/video/3",
                            "title": "有效样本二",
                            "transcript": "这是第二条足够长的转写内容，用于补充分析样本。",
                            "metadata": {"transcribe_status": "success"},
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            outputs = asyncio.run(
                run_profile_pipeline(
                    profile_url="https://v.douyin.com/example/",
                    nickname="测试账号",
                    top_n=3,
                    storage_state_path=root / "state.json",
                    output_dir=root,
                    llm_client=None,
                    resume=True,
                    collector=forbidden_collector,
                    sample_limit=1,
                    min_transcript_chars=10,
                )
            )

            profile = json.loads(Path(outputs["json"]).read_text(encoding="utf-8"))

            self.assertEqual(profile["sample_count"], 1)
            self.assertEqual(profile["samples"][0]["title"], "有效样本一")
            self.assertEqual(profile["samples"][0]["transcript_chars"], len("这是第一条足够长的转写内容，用于分析账号表达节奏。"))

    def test_run_profile_pipeline_resume_transcribes_only_missing_items_and_writes_manifest(self):
        from douyin_style_profiler.pipeline import run_profile_pipeline

        async def forbidden_collector(*args, **kwargs):
            raise AssertionError("resume should reuse existing files")

        def fake_transcriber(items):
            items = list(items)
            self.assertEqual([item.title for item in items], ["失败样本"])
            for item in items:
                item.transcript = "失败样本重新转写成功，这是一段足够长的转写内容。"
                item.metadata["transcribe_status"] = "success"
                item.metadata.pop("transcribe_error", None)
            return items

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "profile_videos.json").write_text(
                json.dumps(
                    [
                        {
                            "url": "https://www.douyin.com/video/1",
                            "title": "成功样本",
                            "transcript": "",
                            "metadata": {"audio_path": str(root / "1.mp3")},
                        },
                        {
                            "url": "https://www.douyin.com/video/2",
                            "title": "失败样本",
                            "transcript": "",
                            "metadata": {"audio_path": str(root / "2.mp3")},
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "transcripts.json").write_text(
                json.dumps(
                    [
                        {
                            "url": "https://www.douyin.com/video/1",
                            "title": "成功样本",
                            "transcript": "成功样本已有足够长的转写内容，可以直接复用。",
                            "metadata": {"transcribe_status": "success", "audio_path": str(root / "1.mp3")},
                        },
                        {
                            "url": "https://www.douyin.com/video/2",
                            "title": "失败样本",
                            "transcript": "",
                            "metadata": {
                                "transcribe_status": "failed",
                                "transcribe_error": "previous failure",
                                "audio_path": str(root / "2.mp3"),
                            },
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            outputs = asyncio.run(
                run_profile_pipeline(
                    profile_url="https://v.douyin.com/example/",
                    nickname="测试账号",
                    top_n=2,
                    storage_state_path=root / "state.json",
                    output_dir=root,
                    llm_client=None,
                    resume=True,
                    collector=forbidden_collector,
                    transcriber=fake_transcriber,
                    min_transcript_chars=10,
                )
            )

            transcripts = json.loads(Path(outputs["transcripts"]).read_text(encoding="utf-8"))
            manifest = json.loads(Path(outputs["manifest"]).read_text(encoding="utf-8"))

            self.assertEqual(transcripts[0]["transcript"], "成功样本已有足够长的转写内容，可以直接复用。")
            self.assertEqual(transcripts[1]["metadata"]["transcribe_status"], "success")
            self.assertEqual(manifest["stages"]["transcribe"]["reused"], 1)
            self.assertEqual(manifest["stages"]["transcribe"]["retried"], 1)
            self.assertEqual(manifest["items"][1]["transcribe_status"], "success")


if __name__ == "__main__":
    unittest.main()
