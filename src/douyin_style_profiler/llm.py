from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional
from urllib import request
from urllib.error import HTTPError, URLError


OPENAI_HOST = "https://api.openai.com"
MINIMAX_HOST = "https://api.minimaxi.com"
OPENAI_MODEL = "gpt-5.5"
MINIMAX_MODEL = "MiniMax-M2.7-highspeed"


class LLMClient:
    """Small Chat Completions client. OpenAI is preferred, MiniMax is fallback."""

    def __init__(self, openai_key: str = "", minimax_key: str = "", timeout: int = 180):
        self.openai_key = openai_key or os.getenv("OPENAI_API_KEY", "")
        self.minimax_key = minimax_key or os.getenv("MINIMAX_API_KEY", "")
        self.timeout = timeout

    def complete(self, messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 4000) -> str:
        providers = [
            ("openai", self.openai_key, OPENAI_HOST, OPENAI_MODEL),
            ("minimax", self.minimax_key, MINIMAX_HOST, MINIMAX_MODEL),
        ]
        last_error = "no provider key configured"
        for provider, key, host, model in providers:
            if not key:
                continue
            payload = self._payload(provider, model, messages, temperature, max_tokens)
            for attempt in range(3):
                try:
                    return self._post_chat_completion(host, key, payload)
                except Exception as exc:
                    last_error = f"{provider}: {exc}"
                    time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"LLM 调用失败：{last_error}")

    def _payload(
        self,
        provider: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> Dict:
        payload: Dict = {"model": model, "messages": messages}
        if model.startswith("gpt-5"):
            payload["max_completion_tokens"] = max_tokens
        else:
            payload["max_tokens"] = max_tokens
            payload["temperature"] = temperature
        if provider == "minimax":
            payload["thinking"] = {"type": "off"}
        return payload

    def _post_chat_completion(self, host: str, key: str, payload: Dict) -> str:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"{host}/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:300]
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(str(exc)) from exc
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if "</think>" in content:
            content = content.split("</think>")[-1].strip()
        if not content:
            raise RuntimeError("empty LLM content")
        return content


def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

