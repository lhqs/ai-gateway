import json
import time
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.errors import ProviderCallError
from app.db.models import Model, Provider
from app.schemas.chat import ChatMessage, GatewayChatChunk, GatewayChatRequest, GatewayChatResponse
from app.usage.parsers.gemini import GeminiUsageParser


class GeminiChatAdapter:
    provider_type = "gemini"

    def _url(self, provider: Provider, model: Model, stream: bool = False) -> str:
        base_url = provider.base_url.rstrip("/")
        action = "streamGenerateContent" if stream else "generateContent"
        url = f"{base_url}/v1beta/models/{model.name}:{action}"
        query: list[tuple[str, str]] = []
        api_key = provider.encrypted_api_key or provider.auth_config.get("api_key")
        if provider.auth_type == "api_key_query" and api_key:
            query.append((provider.auth_config.get("query_name", "key"), api_key))
        if stream:
            query.append(("alt", "sse"))
        if query:
            return f"{url}?{urlencode(query)}"
        return url

    def _headers(self, provider: Provider) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        api_key = provider.encrypted_api_key or provider.auth_config.get("api_key")
        if provider.auth_type == "api_key_header" and api_key:
            headers[provider.auth_config.get("header", "x-goog-api-key")] = api_key
        elif provider.auth_type == "bearer_token" and api_key:
            headers["authorization"] = f"Bearer {api_key}"
        headers.update(provider.config.get("headers") or {})
        return headers

    def _text_from_content(self, content: str | list[dict[str, Any]]) -> str:
        if isinstance(content, str):
            return content
        parts: list[str] = []
        for item in content:
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif item:
                parts.append(json.dumps(item, ensure_ascii=False))
        return "\n".join(parts)

    def _system_instruction(self, messages: list[ChatMessage]) -> dict[str, Any] | None:
        texts = [
            self._text_from_content(message.content)
            for message in messages
            if message.role == "system"
        ]
        text = "\n\n".join(item for item in texts if item)
        if not text:
            return None
        return {"parts": [{"text": text}]}

    def _contents(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        contents: list[dict[str, Any]] = []
        for message in messages:
            if message.role == "system":
                continue
            text = self._text_from_content(message.content)
            if not text:
                continue
            role = "model" if message.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": text}]})
        return contents or [{"role": "user", "parts": [{"text": ""}]}]

    def _body(self, request: GatewayChatRequest) -> dict[str, Any]:
        body: dict[str, Any] = {"contents": self._contents(request.messages)}
        system_instruction = self._system_instruction(request.messages)
        if system_instruction:
            body["systemInstruction"] = system_instruction

        generation_config: dict[str, Any] = {}
        source = request.body
        if source.get("temperature") is not None:
            generation_config["temperature"] = source["temperature"]
        if source.get("top_p") is not None:
            generation_config["topP"] = source["top_p"]
        if source.get("max_tokens") is not None:
            generation_config["maxOutputTokens"] = source["max_tokens"]
        if source.get("stop") is not None:
            stop = source["stop"]
            generation_config["stopSequences"] = stop if isinstance(stop, list) else [stop]
        if generation_config:
            body["generationConfig"] = generation_config

        safety_settings = source.get("safety_settings") or source.get("safetySettings")
        if safety_settings is not None:
            body["safetySettings"] = safety_settings
        return body

    def _assistant_text(self, payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates") or []
        if not candidates:
            return ""
        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        return "".join(part.get("text", "") for part in parts if isinstance(part, dict))

    def _finish_reason(self, payload: dict[str, Any]) -> str | None:
        candidates = payload.get("candidates") or []
        if not candidates:
            return None
        reason = candidates[0].get("finishReason")
        if reason == "STOP":
            return "stop"
        if reason == "MAX_TOKENS":
            return "length"
        return reason.lower() if isinstance(reason, str) else None

    def _openai_body(
        self, request: GatewayChatRequest, model: Model, payload: dict[str, Any]
    ) -> dict[str, Any]:
        usage = GeminiUsageParser().parse(payload)
        return {
            "id": f"gemini-{request.request_id}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model.name,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": self._assistant_text(payload)},
                    "finish_reason": self._finish_reason(payload),
                }
            ],
            "usage": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            },
            "gemini": payload,
        }

    async def chat_completion(
        self, provider: Provider, model: Model, request: GatewayChatRequest
    ) -> GatewayChatResponse:
        timeout = (provider.timeout_ms or 60000) / 1000
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self._url(provider, model),
                    headers=self._headers(provider),
                    json=self._body(request),
                )
        except httpx.TimeoutException as exc:
            raise ProviderCallError("Provider request timed out", error_type="timeout") from exc
        except httpx.ConnectError as exc:
            raise ProviderCallError(
                "Provider connection failed", error_type="connection_error"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderCallError(str(exc), error_type="provider_error") from exc

        if response.status_code >= 400:
            error_type = "rate_limit" if response.status_code == 429 else "provider_error"
            raise ProviderCallError(
                f"Provider returned HTTP {response.status_code}",
                status_code=response.status_code,
                error_type=error_type,
                response_body=response.text[:4000],
                retryable=response.status_code in {429, 500, 502, 503, 504},
            )

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ProviderCallError(
                "Provider returned invalid JSON", error_type="provider_error"
            ) from exc

        usage = GeminiUsageParser().parse(payload)
        return GatewayChatResponse(
            body=self._openai_body(request, model, payload),
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            cached_input_tokens=usage.cached_input_tokens,
            raw_usage=usage.raw_usage,
            usage_status=usage.usage_status,
        )

    async def stream_chat_completion(
        self, provider: Provider, model: Model, request: GatewayChatRequest
    ) -> AsyncIterator[GatewayChatChunk]:
        raise ProviderCallError(
            "Gemini unified chat streaming is not implemented",
            status_code=400,
            error_type="unsupported_feature",
            retryable=False,
        )
