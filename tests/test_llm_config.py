import os
import unittest
from unittest import mock

from douyin_style_profiler.llm import LLMClient, LLMConfig, provider_presets


class LLMConfigTest(unittest.TestCase):
    def test_from_env_requires_user_selected_model_and_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            config = LLMConfig.from_env()

        self.assertEqual(config.provider, "")
        self.assertEqual(config.model, "")
        self.assertEqual(config.api_key, "")
        self.assertFalse(config.is_configured)

    def test_deepseek_uses_openai_compatible_chat_completion(self):
        client = LLMClient(provider="deepseek", model="deepseek-chat", api_key="key")

        req = client._build_request([{"role": "user", "content": "hi"}], temperature=0.1, max_tokens=100)

        self.assertEqual(req.url, "https://api.deepseek.com/v1/chat/completions")
        self.assertEqual(req.provider, "deepseek")
        self.assertEqual(req.payload["model"], "deepseek-chat")
        self.assertEqual(req.payload["messages"][0]["content"], "hi")
        self.assertEqual(req.headers["Authorization"], "Bearer key")

    def test_custom_openai_compatible_base_url_is_supported(self):
        client = LLMClient(
            provider="openai-compatible",
            model="custom-model",
            api_key="key",
            base_url="https://llm.example.com/api",
        )

        req = client._build_request([{"role": "user", "content": "hi"}], temperature=0.1, max_tokens=100)

        self.assertEqual(req.url, "https://llm.example.com/api/v1/chat/completions")
        self.assertEqual(req.payload["model"], "custom-model")

    def test_anthropic_request_uses_messages_api(self):
        client = LLMClient(provider="anthropic", model="claude-3-5-sonnet-latest", api_key="key")

        req = client._build_request(
            [
                {"role": "system", "content": "你是分析师"},
                {"role": "user", "content": "分析这个账号"},
            ],
            temperature=0.2,
            max_tokens=200,
        )

        self.assertEqual(req.url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(req.headers["x-api-key"], "key")
        self.assertEqual(req.payload["system"], "你是分析师")
        self.assertEqual(req.payload["messages"][0]["role"], "user")
        self.assertEqual(req.payload["max_tokens"], 200)

    def test_gemini_request_uses_generate_content_api(self):
        client = LLMClient(provider="gemini", model="gemini-1.5-pro", api_key="key")

        req = client._build_request([{"role": "user", "content": "hi"}], temperature=0.2, max_tokens=200)

        self.assertEqual(
            req.url,
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key=key",
        )
        self.assertEqual(req.payload["contents"][0]["parts"][0]["text"], "hi")
        self.assertEqual(req.payload["generationConfig"]["maxOutputTokens"], 200)

    def test_minimax_uses_current_openai_compatible_endpoint_and_disables_thinking(self):
        client = LLMClient(provider="minimax", model="MiniMax-M3", api_key="key")

        req = client._build_request([{"role": "user", "content": "hi"}], temperature=0.1, max_tokens=100)

        self.assertEqual(req.url, "https://api.minimax.io/v1/chat/completions")
        self.assertEqual(req.payload["thinking"], {"type": "disabled"})

    def test_minimax_cn_uses_mainland_endpoint_and_disables_thinking(self):
        client = LLMClient(provider="minimax-cn", model="MiniMax-M3", api_key="key")

        req = client._build_request([{"role": "user", "content": "hi"}], temperature=0.1, max_tokens=100)

        self.assertEqual(req.url, "https://api.minimaxi.com/v1/chat/completions")
        self.assertEqual(req.payload["thinking"], {"type": "disabled"})

    def test_provider_presets_include_mainstream_models(self):
        presets = provider_presets()

        for provider in ["openai", "deepseek", "qwen", "kimi", "zhipu", "minimax", "minimax-cn", "anthropic", "gemini"]:
            self.assertIn(provider, presets)


if __name__ == "__main__":
    unittest.main()
