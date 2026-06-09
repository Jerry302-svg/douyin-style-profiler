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


if __name__ == "__main__":
    unittest.main()
