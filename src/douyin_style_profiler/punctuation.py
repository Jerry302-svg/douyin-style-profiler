from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Tuple

import yaml


_DEFAULT_MODEL_DIR = Path.home() / ".cache/modelscope/hub/models/iic/punc_ct-transformer_cn-en-common-vocab471067-large"
_model_instance: Tuple[Any, list[str]] | None = None


def _model_dir() -> Path:
    return Path(os.environ.get("FUNASR_PUNC_MODEL_DIR") or _DEFAULT_MODEL_DIR)


def _load_model() -> Tuple[Any, list[str]]:
    global _model_instance
    if _model_instance is not None:
        return _model_instance

    import torch
    from funasr.models.ct_transformer.model import CTTransformer

    model_dir = _model_dir()
    config_path = model_dir / "config.yaml"
    tokens_path = model_dir / "tokens.json"
    model_path = model_dir / "model.pt"
    missing = [str(path) for path in (config_path, tokens_path, model_path) if not path.exists()]
    if missing:
        raise FileNotFoundError("标点模型文件不存在: " + ", ".join(missing))

    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    with tokens_path.open("r", encoding="utf-8") as handle:
        tokens = json.load(handle)

    model = CTTransformer(
        vocab_size=len(tokens),
        **config.get("model_conf", {}),
        encoder=config.get("encoder"),
        encoder_conf=config.get("encoder_conf"),
    )
    state_dict = torch.load(model_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict, strict=False)
    model.eval()
    _model_instance = (model, tokens)
    return _model_instance


def to_simplified_chinese(text: str) -> str:
    if not text:
        return text
    try:
        from opencc import OpenCC

        return OpenCC("t2s").convert(text)
    except Exception:
        return text


def add_punctuation(text: str) -> str:
    """Use the local FunASR CT-Transformer punctuation model, then normalize to Simplified Chinese."""
    clean_text = (text or "").strip()
    if not clean_text:
        return clean_text

    import torch

    model, tokens = _load_model()
    unknown_index = tokens.index("<unk>") if "<unk>" in tokens else 0
    token_index = {token: index for index, token in enumerate(tokens)}
    char_ids = [token_index.get(char, unknown_index) for char in clean_text]
    input_tensor = torch.LongTensor(char_ids).unsqueeze(0)
    input_lengths = torch.LongTensor([len(char_ids)])

    with torch.no_grad():
        logits, _ = model.punc_forward(input_tensor, input_lengths)
        preds = logits.argmax(dim=-1).squeeze(0).tolist()

    punc_list = getattr(model, "punc_list", [])
    result: list[str] = []
    for index, char in enumerate(clean_text):
        result.append(char)
        if index >= len(preds):
            continue
        pred = preds[index]
        if pred > 1 and pred < len(punc_list):
            result.append(str(punc_list[pred]))

    return to_simplified_chinese("".join(result))
