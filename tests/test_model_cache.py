import tempfile
import unittest
from pathlib import Path


class ModelCacheTest(unittest.TestCase):
    def test_resolve_modelscope_cache_reuses_existing_complete_user_cache(self):
        from douyin_style_profiler.model_cache import (
            FUNASR_ASR_MODEL_IDS,
            FUNASR_VAD_MODEL_IDS,
            resolve_modelscope_cache,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            user_cache = root / "user-modelscope"
            project_cache = root / "project" / "models" / "modelscope"
            for model_id in [FUNASR_ASR_MODEL_IDS[0], FUNASR_VAD_MODEL_IDS[0]]:
                (user_cache / "models" / "iic" / model_id).mkdir(parents=True)

            selected = resolve_modelscope_cache(
                env={},
                search_roots=[user_cache],
                project_cache=project_cache,
                create_fallback=False,
            )

            self.assertEqual(selected, user_cache)
            self.assertFalse(project_cache.exists())

    def test_resolve_modelscope_cache_uses_project_cache_only_when_no_existing_model(self):
        from douyin_style_profiler.model_cache import resolve_modelscope_cache

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            empty_user_cache = root / "empty-user-modelscope"
            empty_user_cache.mkdir()
            project_cache = root / "project" / "models" / "modelscope"

            selected = resolve_modelscope_cache(
                env={},
                search_roots=[empty_user_cache],
                project_cache=project_cache,
                create_fallback=True,
            )

            self.assertEqual(selected, project_cache)
            self.assertTrue(project_cache.exists())

    def test_resolve_punctuation_model_dir_reuses_existing_model_before_project_download(self):
        from douyin_style_profiler.model_cache import PUNCTUATION_MODEL_ID, resolve_punctuation_model_dir

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            user_cache = root / "user-modelscope"
            model_dir = user_cache / "hub" / "models" / "iic" / PUNCTUATION_MODEL_ID
            model_dir.mkdir(parents=True)
            for name in ["config.yaml", "tokens.json", "model.pt"]:
                (model_dir / name).write_text("x", encoding="utf-8")

            selected = resolve_punctuation_model_dir(env={}, search_roots=[user_cache])

            self.assertEqual(selected, model_dir)

    def test_resolve_punctuation_model_dir_supports_speech_prefixed_model_name(self):
        from douyin_style_profiler.model_cache import resolve_punctuation_model_dir

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_dir = (
                root
                / "hub"
                / "models"
                / "iic"
                / "speech_punc_ct-transformer_cn-en-common-vocab471067-large"
            )
            model_dir.mkdir(parents=True)
            for name in ["config.yaml", "tokens.json", "model.pt"]:
                (model_dir / name).write_text("x", encoding="utf-8")

            selected = resolve_punctuation_model_dir(env={}, search_roots=[root])

            self.assertEqual(selected, model_dir)


if __name__ == "__main__":
    unittest.main()
