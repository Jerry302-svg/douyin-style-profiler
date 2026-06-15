from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class DiagnosticCheck:
    name: str
    status: str
    message: str


CommandRunner = Callable[[Sequence[str]], tuple[int, str, str]]
ExecutableFinder = Callable[[str], str | None]
ModuleImporter = Callable[[str], object]


def run_diagnostics(
    storage_state_path: str | Path = "runtime/douyin_storage_state.json",
    *,
    env: Mapping[str, str] | None = None,
    python_version: tuple[int, ...] | None = None,
    which: ExecutableFinder | None = None,
    run_command: CommandRunner | None = None,
    import_module: ModuleImporter | None = None,
    include_transcription: bool = True,
) -> list[DiagnosticCheck]:
    source_env = env or os.environ
    version = python_version or sys.version_info[:3]
    finder = which or shutil.which
    runner = run_command or _run_command
    importer = import_module or importlib.import_module

    checks = [
        _check_python(version),
        _check_ffmpeg(source_env, finder, runner),
        _check_storage_state(storage_state_path),
        _check_llm(source_env),
    ]
    if include_transcription:
        checks.append(_check_funasr(importer))
    else:
        checks.append(DiagnosticCheck("funasr", "ok", "已跳过 FunASR 转写依赖检查"))
    return checks


def diagnostics_has_errors(checks: list[DiagnosticCheck]) -> bool:
    return any(check.status == "error" for check in checks)


def format_diagnostics(checks: list[DiagnosticCheck]) -> str:
    labels = {"ok": "OK", "warn": "WARN", "error": "ERROR"}
    return "\n".join(f"[{labels.get(check.status, check.status.upper())}] {check.name}: {check.message}" for check in checks)


def _check_python(version: tuple[int, ...]) -> DiagnosticCheck:
    major = version[0] if len(version) > 0 else 0
    minor = version[1] if len(version) > 1 else 0
    patch = version[2] if len(version) > 2 else 0
    if (major, minor) < (3, 10):
        return DiagnosticCheck("python", "error", f"当前 Python {major}.{minor}.{patch} 过低，需要 Python 3.10+")
    return DiagnosticCheck("python", "ok", f"当前 Python {major}.{minor}.{patch} 可用")


def _check_ffmpeg(env: Mapping[str, str], which: ExecutableFinder, run_command: CommandRunner) -> DiagnosticCheck:
    configured = str(env.get("FFMPEG_BINARY") or "").strip()
    binary = configured or which("ffmpeg")
    if not binary:
        return DiagnosticCheck("ffmpeg", "error", "未找到 ffmpeg，请先安装并确保命令行可执行")
    if configured and not Path(configured).exists():
        return DiagnosticCheck("ffmpeg", "error", f"FFMPEG_BINARY 指向的文件不存在：{configured}")
    code, stdout, stderr = run_command([binary, "-version"])
    if code != 0:
        detail = (stderr or stdout or "未知错误").strip()
        return DiagnosticCheck("ffmpeg", "error", f"ffmpeg 无法运行：{detail[:160]}")
    first_line = (stdout or "").splitlines()[0] if stdout else binary
    return DiagnosticCheck("ffmpeg", "ok", f"ffmpeg 可用：{first_line[:120]}")


def _check_storage_state(path: str | Path) -> DiagnosticCheck:
    target = Path(path)
    if target.exists():
        return DiagnosticCheck("storage_state", "ok", f"已找到 Cookie 文件：{target}")
    return DiagnosticCheck("storage_state", "warn", f"未找到 Cookie 文件：{target}；需要采集时请先运行 login")


def _check_llm(env: Mapping[str, str]) -> DiagnosticCheck:
    provider = str(env.get("LLM_PROVIDER") or "").strip()
    model = str(env.get("LLM_MODEL") or "").strip()
    api_key = str(env.get("LLM_API_KEY") or "").strip()
    filled = [bool(provider), bool(model), bool(api_key)]
    if all(filled):
        return DiagnosticCheck("llm", "ok", f"LLM 已配置：{provider}/{model}")
    if any(filled):
        return DiagnosticCheck("llm", "warn", "LLM 配置不完整；使用 --llm 前请补齐 LLM_PROVIDER、LLM_MODEL、LLM_API_KEY")
    return DiagnosticCheck("llm", "ok", "未配置 LLM；不传 --llm 时会使用规则版 fallback")


def _check_funasr(import_module: ModuleImporter) -> DiagnosticCheck:
    try:
        import_module("funasr")
    except ImportError:
        return DiagnosticCheck("funasr", "warn", "未检测到 FunASR；需要自动转写音频时请安装完整依赖")
    return DiagnosticCheck("funasr", "ok", "FunASR Python 包可导入")


def _run_command(command: Sequence[str]) -> tuple[int, str, str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
    except OSError as exc:
        return 1, "", str(exc)
    except subprocess.TimeoutExpired:
        return 1, "", "命令执行超时"
    return result.returncode, result.stdout, result.stderr
