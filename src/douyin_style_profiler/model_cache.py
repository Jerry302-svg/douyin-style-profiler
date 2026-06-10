from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Sequence


FUNASR_ASR_MODEL_IDS = (
    "speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
    "paraformer-zh",
)
FUNASR_VAD_MODEL_IDS = (
    "speech_fsmn_vad_zh-cn-16k-common-pytorch",
    "fsmn-vad",
)
PUNCTUATION_MODEL_ID = "punc_ct-transformer_cn-en-common-vocab471067-large"
PUNCTUATION_MODEL_IDS = (
    PUNCTUATION_MODEL_ID,
    "speech_punc_ct-transformer_cn-en-common-vocab471067-large",
)


def default_project_modelscope_cache() -> Path:
    return Path.cwd() / "models" / "modelscope"


def default_modelscope_search_roots(env: Mapping[str, str] | None = None) -> list[Path]:
    source = env or os.environ
    roots: list[Path] = []
    env_cache = (source.get("MODELSCOPE_CACHE") or "").strip()
    if env_cache:
        roots.append(Path(env_cache).expanduser())
    roots.extend(
        [
            Path.home() / ".cache" / "modelscope",
            Path.home() / ".modelscope",
            Path.cwd() / "models" / "modelscope",
        ]
    )
    unique: list[Path] = []
    seen = set()
    for root in roots:
        resolved = root.resolve() if root.exists() else root
        key = str(resolved)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def resolve_modelscope_cache(
    env: Mapping[str, str] | None = None,
    search_roots: Sequence[Path] | None = None,
    project_cache: Path | None = None,
    create_fallback: bool = True,
) -> Path:
    roots = list(search_roots) if search_roots is not None else default_modelscope_search_roots(env)
    for root in roots:
        if _has_any_model(root, FUNASR_ASR_MODEL_IDS) and _has_any_model(root, FUNASR_VAD_MODEL_IDS):
            return root

    fallback = project_cache or default_project_modelscope_cache()
    if create_fallback:
        fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def configure_modelscope_cache(env: Mapping[str, str] | None = None) -> Path:
    selected = resolve_modelscope_cache(env=env)
    os.environ["MODELSCOPE_CACHE"] = str(selected)
    return selected


def resolve_punctuation_model_dir(
    env: Mapping[str, str] | None = None,
    search_roots: Sequence[Path] | None = None,
) -> Path | None:
    source = env or os.environ
    explicit_dir = (source.get("FUNASR_PUNC_MODEL_DIR") or "").strip()
    if explicit_dir:
        explicit_path = Path(explicit_dir).expanduser()
        if _is_complete_punctuation_dir(explicit_path):
            return explicit_path

    roots = list(search_roots) if search_roots is not None else default_modelscope_search_roots(source)
    for root in roots:
        for model_dir in _candidate_model_dirs(root, PUNCTUATION_MODEL_IDS):
            if _is_complete_punctuation_dir(model_dir):
                return model_dir
    return None


def ensure_punctuation_model_dir() -> Path:
    found = resolve_punctuation_model_dir()
    if found:
        return found

    cache_root = default_project_modelscope_cache()
    cache_root.mkdir(parents=True, exist_ok=True)
    try:
        from modelscope import snapshot_download
    except ImportError as exc:
        raise RuntimeError("未安装 modelscope，无法下载标点模型") from exc

    downloaded = Path(snapshot_download(f"iic/{PUNCTUATION_MODEL_ID}", cache_dir=str(cache_root)))
    if _is_complete_punctuation_dir(downloaded):
        return downloaded
    found = resolve_punctuation_model_dir(search_roots=[cache_root])
    if found:
        return found
    raise FileNotFoundError(f"标点模型下载后仍未找到完整文件: {downloaded}")


def _has_any_model(root: Path, model_ids: Sequence[str]) -> bool:
    return any(path.exists() and path.is_dir() for path in _candidate_model_dirs(root, model_ids))


def _candidate_model_dirs(root: Path, model_ids: Sequence[str]) -> list[Path]:
    candidates: list[Path] = []
    for model_id in model_ids:
        candidates.extend(
            [
                root / "models" / "iic" / model_id,
                root / "hub" / "models" / "iic" / model_id,
                root / "iic" / model_id,
                root / model_id,
            ]
        )
    return candidates


def _is_complete_punctuation_dir(path: Path) -> bool:
    return all((path / name).exists() for name in ("config.yaml", "tokens.json", "model.pt"))
