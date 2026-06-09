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


if __name__ == "__main__":
    unittest.main()
