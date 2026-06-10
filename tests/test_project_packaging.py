from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProjectPackagingTest(unittest.TestCase):
    def test_requirements_contains_full_runtime_dependencies(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        required_packages = [
            "playwright",
            "aiohttp",
            "requests",
            "PyYAML",
            "funasr",
            "modelscope",
            "opencc-python-reimplemented",
        ]

        for package in required_packages:
            self.assertIn(package, requirements)

    def test_readme_uses_standard_github_python_install_flow(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("pip install -r requirements.txt", readme)
        self.assertIn("python -m playwright install chromium", readme)
        self.assertNotIn("python -m venv", readme)
        self.assertNotIn("source .venv/bin/activate", readme)
        self.assertNotIn("Windows 无 Python 环境", readme)
        self.assertNotIn("runtime/", readme)
        self.assertNotIn("requirements-transcribe.txt", readme)

    def test_readme_does_not_claim_builtin_llm_priority_or_keys(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("LLM_PROVIDER", readme)
        self.assertIn("LLM_MODEL", readme)
        self.assertIn("LLM_API_KEY", readme)
        self.assertIn("openai-compatible", readme)
        self.assertNotIn("OpenAI 优先", readme)
        self.assertNotIn("MiniMax 作为备用", readme)
        self.assertNotIn("gpt-5.5", readme)

    def test_login_confirmation_can_wait_without_interactive_stdin(self):
        from douyin_style_profiler.collector import wait_for_login_confirmation

        calls = []

        async def fake_sleep(seconds):
            calls.append(seconds)

        import asyncio

        asyncio.run(
            wait_for_login_confirmation(
                wait_seconds=12,
                input_fn=lambda: (_ for _ in ()).throw(EOFError()),
                sleep_fn=fake_sleep,
            )
        )

        self.assertEqual(calls, [12])


if __name__ == "__main__":
    unittest.main()
