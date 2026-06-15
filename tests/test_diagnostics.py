from pathlib import Path
import tempfile
import unittest


class DiagnosticsTest(unittest.TestCase):
    def test_run_diagnostics_reports_ready_environment(self):
        from douyin_style_profiler.diagnostics import run_diagnostics

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "douyin_storage_state.json"
            state_path.write_text('{"cookies":[]}', encoding="utf-8")

            checks = run_diagnostics(
                storage_state_path=state_path,
                env={
                    "LLM_PROVIDER": "deepseek",
                    "LLM_MODEL": "deepseek-chat",
                    "LLM_API_KEY": "key",
                },
                python_version=(3, 10, 12),
                which=lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None,
                run_command=lambda command: (0, "ffmpeg version 6", ""),
                import_module=lambda name: object(),
            )

        statuses = {check.name: check.status for check in checks}

        self.assertEqual(statuses["python"], "ok")
        self.assertEqual(statuses["ffmpeg"], "ok")
        self.assertEqual(statuses["storage_state"], "ok")
        self.assertEqual(statuses["llm"], "ok")
        self.assertEqual(statuses["funasr"], "ok")

    def test_run_diagnostics_warns_for_partial_optional_setup(self):
        from douyin_style_profiler.diagnostics import run_diagnostics

        def missing_module(name):
            raise ImportError(name)

        checks = run_diagnostics(
            storage_state_path="runtime/missing.json",
            env={"LLM_PROVIDER": "deepseek", "LLM_MODEL": "", "LLM_API_KEY": ""},
            python_version=(3, 12, 0),
            which=lambda name: None,
            run_command=lambda command: (1, "", "not found"),
            import_module=missing_module,
        )

        by_name = {check.name: check for check in checks}

        self.assertEqual(by_name["ffmpeg"].status, "error")
        self.assertEqual(by_name["storage_state"].status, "warn")
        self.assertEqual(by_name["llm"].status, "warn")
        self.assertEqual(by_name["funasr"].status, "warn")

    def test_format_diagnostics_shows_human_readable_statuses(self):
        from douyin_style_profiler.diagnostics import DiagnosticCheck, format_diagnostics

        text = format_diagnostics(
            [
                DiagnosticCheck("python", "ok", "Python 版本可用"),
                DiagnosticCheck("ffmpeg", "error", "未找到 ffmpeg"),
            ]
        )

        self.assertIn("[OK] python: Python 版本可用", text)
        self.assertIn("[ERROR] ffmpeg: 未找到 ffmpeg", text)


if __name__ == "__main__":
    unittest.main()
