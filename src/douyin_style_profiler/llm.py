from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping
from urllib import parse, request
from urllib.error import HTTPError, URLError


OPENAI_COMPATIBLE_PROVIDERS = {
    "openai": "https://api.openai.com",
    "openai-compatible": "",
    "deepseek": "https://api.deepseek.com",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode",
    "kimi": "https://api.moonshot.cn",
    "moonshot": "https://api.moonshot.cn",
    "zhipu": "https://open.bigmodel.cn/api/paas",
    "minimax": "https://api.minimaxi.com",
}

NATIVE_PROVIDERS = {
    "anthropic": "https://api.anthropic.com",
    "gemini": "https://generativelanguage.googleapis.com",
}


def provider_presets() -> Dict[str, Dict[str, str]]:
    """Return built-in provider presets for docs, tests and CLI help."""
    presets = {
        key: {"type": "openai-compatible", "base_url": value}
        for key, value in OPENAI_COMPATIBLE_PROVIDERS.items()
        if key != "openai-compatible"
    }
    presets["openai-compatible"] = {"type": "openai-compatible", "base_url": "用户自填"}
    presets["anthropic"] = {"type": "anthropic", "base_url": NATIVE_PROVIDERS["anthropic"]}
    presets["gemini"] = {"type": "gemini", "base_url": NATIVE_PROVIDERS["gemini"]}
    return presets


@dataclass
class LLMConfig:
    provider: str = ""
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    timeout: int = 180

    @property
    def normalized_provider(self) -> str:
        return (self.provider or "").strip().lower().replace("_", "-")

    @property
    def is_configured(self) -> bool:
        return bool(self.normalized_provider and self.model.strip() and self.api_key.strip())

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "LLMConfig":
        source = env or os.environ
        timeout_raw = source.get("LLM_TIMEOUT", "180")
        try:
            timeout = int(timeout_raw)
        except (TypeError, ValueError):
            timeout = 180
        return cls(
            provider=source.get("LLM_PROVIDER", ""),
            model=source.get("LLM_MODEL", ""),
            api_key=source.get("LLM_API_KEY", ""),
            base_url=source.get("LLM_BASE_URL", ""),
            timeout=timeout,
        )


@dataclass
class LLMRequest:
    provider: str
    url: str
    headers: Dict[str, str]
    payload: Dict[str, Any]


class LLMClient:
    """Small multi-provider LLM client.

    The project does not ship any API key or hard-code any model. Users must
    configure provider, model and key in `.env` or pass them through CLI flags.
    """

    def __init__(
        self,
        provider: str = "",
        model: str = "",
        api_key: str = "",
        base_url: str = "",
        timeout: int | None = None,
    ):
        env_config = LLMConfig.from_env()
        self.config = LLMConfig(
            provider=provider or env_config.provider,
            model=model or env_config.model,
            api_key=api_key or env_config.api_key,
            base_url=base_url or env_config.base_url,
            timeout=timeout if timeout is not None else env_config.timeout,
        )

    def complete(self, messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 4000) -> str:
        if not self.config.is_configured:
            raise RuntimeError("LLM 未配置，请设置 LLM_PROVIDER、LLM_MODEL、LLM_API_KEY")
        last_error = ""
        for attempt in range(3):
            try:
                req = self._build_request(messages, temperature=temperature, max_tokens=max_tokens)
                return self._post(req)
            except Exception as exc:
                last_error = str(exc)
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"LLM 调用失败：{last_error}")

    def _build_request(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> LLMRequest:
        provider = self.config.normalized_provider
        if provider in OPENAI_COMPATIBLE_PROVIDERS:
            return self._build_openai_compatible_request(provider, messages, temperature, max_tokens)
        if provider == "anthropic":
            return self._build_anthropic_request(messages, temperature, max_tokens)
        if provider == "gemini":
            return self._build_gemini_request(messages, temperature, max_tokens)
        raise ValueError(
            f"不支持的 LLM_PROVIDER: {self.config.provider}。"
            "可用值：openai, openai-compatible, deepseek, qwen, kimi, zhipu, minimax, anthropic, gemini"
        )

    def _build_openai_compatible_request(
        self,
        provider: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> LLMRequest:
        host = self._resolve_base_url(provider)
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
        }
        if self.config.model.startswith("gpt-5"):
            payload.pop("temperature", None)
            payload["max_completion_tokens"] = max_tokens
        else:
            payload["max_tokens"] = max_tokens
        if provider == "minimax":
            payload["thinking"] = {"type": "off"}
        return LLMRequest(
            provider=provider,
            url=f"{host}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            payload=payload,
        )

    def _build_anthropic_request(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> LLMRequest:
        system_parts: List[str] = []
        chat_messages: List[Dict[str, str]] = []
        for item in messages:
            role = item.get("role", "user")
            content = item.get("content", "")
            if role == "system":
                system_parts.append(content)
                continue
            if role not in {"user", "assistant"}:
                role = "user"
            chat_messages.append({"role": role, "content": content})
        if not chat_messages:
            chat_messages = [{"role": "user", "content": "\n".join(system_parts)}]
            system_parts = []
        payload = {
            "model": self.config.model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_parts:
            payload["system"] = "\n".join(system_parts)
        return LLMRequest(
            provider="anthropic",
            url=f"{self._resolve_base_url('anthropic')}/v1/messages",
            headers={
                "x-api-key": self.config.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            payload=payload,
        )

    def _build_gemini_request(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> LLMRequest:
        contents = []
        system_parts: List[str] = []
        for item in messages:
            role = item.get("role", "user")
            content = item.get("content", "")
            if role == "system":
                system_parts.append(content)
                continue
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": content}]})
        if system_parts:
            contents.insert(0, {"role": "user", "parts": [{"text": "\n".join(system_parts)}]})
        if not contents:
            contents = [{"role": "user", "parts": [{"text": ""}]}]
        model = parse.quote(self.config.model, safe="")
        key = parse.quote(self.config.api_key, safe="")
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        return LLMRequest(
            provider="gemini",
            url=f"{self._resolve_base_url('gemini')}/v1beta/models/{model}:generateContent?key={key}",
            headers={"Content-Type": "application/json"},
            payload=payload,
        )

    def _resolve_base_url(self, provider: str) -> str:
        base_url = (self.config.base_url or "").strip()
        if not base_url:
            if provider in OPENAI_COMPATIBLE_PROVIDERS:
                base_url = OPENAI_COMPATIBLE_PROVIDERS[provider]
            else:
                base_url = NATIVE_PROVIDERS.get(provider, "")
        if not base_url:
            raise ValueError(f"{provider} 需要配置 LLM_BASE_URL")
        return base_url.rstrip("/")

    def _post(self, req: LLMRequest) -> str:
        body = json.dumps(req.payload, ensure_ascii=False).encode("utf-8")
        http_req = request.Request(req.url, data=body, headers=req.headers, method="POST")
        try:
            with request.urlopen(http_req, timeout=self.config.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:300]
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(str(exc)) from exc
        content = self._extract_content(req.provider, data)
        if "</think>" in content:
            content = content.split("</think>")[-1].strip()
        if not content:
            raise RuntimeError("empty LLM content")
        return content

    def _extract_content(self, provider: str, data: Dict[str, Any]) -> str:
        if provider == "anthropic":
            parts = data.get("content") or []
            return "".join(str(item.get("text") or "") for item in parts if isinstance(item, dict)).strip()
        if provider == "gemini":
            candidates = data.get("candidates") or []
            content = ((candidates[0] if candidates else {}).get("content") or {}).get("parts") or []
            return "".join(str(item.get("text") or "") for item in content if isinstance(item, dict)).strip()
        return str(data.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()


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
