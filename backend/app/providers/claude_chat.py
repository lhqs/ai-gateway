import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.errors import ProviderCallError
from app.db.models import Model, Provider
from app.schemas.chat import ChatMessage, GatewayChatChunk, GatewayChatRequest, GatewayChatResponse
from app.schemas.proxy import NativeUsageResult
from app.usage.parsers.anthropic import AnthropicUsageParser


ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_CONTENT_BLOCK_TYPES = {
    "text",
    "image",
    "document",
    "search_result",
    "thinking",
    "redacted_thinking",
    "tool_use",
    "tool_result",
    "server_tool_use",
    "web_search_tool_result",
}


class ClaudeChatAdapter:
    provider_type = "claude"

    def _url(self, provider: Provider) -> str:
        base_url = provider.base_url.rstrip("/")
        if base_url.endswith("/v1"):
            return f"{base_url}/messages"
        return f"{base_url}/v1/messages"

    def _headers(self, provider: Provider) -> dict[str, str]:
        config = provider.config or {}
        auth_config = provider.auth_config or {}
        headers = {
            "content-type": "application/json",
            "anthropic-version": str(config.get("anthropic_version") or ANTHROPIC_VERSION),
        }
        beta = config.get("anthropic_beta") or config.get("anthropic_betas")
        if isinstance(beta, str) and beta:
            headers["anthropic-beta"] = beta
        elif isinstance(beta, list) and beta:
            headers["anthropic-beta"] = ",".join(str(item) for item in beta if item)

        api_key = provider.encrypted_api_key or auth_config.get("api_key")
        if provider.auth_type == "bearer_token" and api_key:
            headers["authorization"] = f"Bearer {api_key}"
        elif provider.auth_type == "api_key_header" and api_key:
            header_name = auth_config.get("header", "x-api-key")
            prefix = auth_config.get("prefix", "")
            headers[header_name] = f"{prefix} {api_key}" if prefix else api_key

        headers.update(config.get("headers") or {})
        return headers

    def _text_from_content(self, content: str | list[dict[str, Any]]) -> str:
        if isinstance(content, str):
            return content
        parts: list[str] = []
        for item in content:
            if item.get("type") in {"text", "input_text"} and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif item:
                parts.append(json.dumps(item, ensure_ascii=False))
        return "\n".join(parts)

    def _system(self, messages: list[ChatMessage]) -> str | None:
        text = "\n\n".join(
            self._text_from_content(message.content)
            for message in messages
            if message.role == "system"
        ).strip()
        return text or None

    def _content_blocks(self, content: str | list[dict[str, Any]]) -> str | list[dict[str, Any]]:
        if isinstance(content, str):
            return content

        blocks: list[dict[str, Any]] = []
        for item in content:
            block_type = item.get("type")
            if block_type in ANTHROPIC_CONTENT_BLOCK_TYPES:
                blocks.append(dict(item))
            elif block_type in {"text", "input_text"} and isinstance(item.get("text"), str):
                blocks.append({"type": "text", "text": item["text"]})
            elif block_type in {"image_url", "input_image"}:
                block = self._image_block(item)
                if block:
                    blocks.append(block)
            elif isinstance(item.get("text"), str):
                blocks.append({"type": "text", "text": item["text"]})
            else:
                blocks.append({"type": "text", "text": json.dumps(item, ensure_ascii=False)})
        return blocks or ""

    def _image_block(self, item: dict[str, Any]) -> dict[str, Any] | None:
        image = item.get("image_url") or item
        url = image.get("url") if isinstance(image, dict) else None
        if not isinstance(url, str) or not url:
            return None
        if url.startswith("data:") and ";base64," in url:
            media_type = url[5 : url.index(";base64,")]
            data = url.split(";base64,", 1)[1]
            return {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": data},
            }
        return {"type": "image", "source": {"type": "url", "url": url}}

    def _tool_result_content(
        self, content: str | list[dict[str, Any]]
    ) -> str | list[dict[str, Any]]:
        if isinstance(content, str):
            return content
        return self._content_blocks(content)

    def _messages(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for message in messages:
            if message.role == "system":
                continue
            if message.role == "tool":
                if not message.tool_call_id:
                    continue
                result.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": message.tool_call_id,
                                "content": self._tool_result_content(message.content),
                            }
                        ],
                    }
                )
                continue
            role = "assistant" if message.role == "assistant" else "user"
            result.append({"role": role, "content": self._content_blocks(message.content)})
        return result or [{"role": "user", "content": ""}]

    def _tools(self, tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        if not tools:
            return None
        result: list[dict[str, Any]] = []
        for tool in tools:
            if "name" in tool and "input_schema" in tool:
                result.append(tool)
                continue
            function = tool.get("function") if tool.get("type") == "function" else None
            if not isinstance(function, dict) or not function.get("name"):
                continue
            anthropic_tool = {
                "name": function["name"],
                "input_schema": function.get("parameters") or {"type": "object", "properties": {}},
            }
            if function.get("description"):
                anthropic_tool["description"] = function["description"]
            result.append(anthropic_tool)
        return result or None

    def _tool_choice(self, choice: str | dict[str, Any] | None) -> dict[str, Any] | None:
        if choice is None:
            return None
        if choice == "auto":
            return {"type": "auto"}
        if choice == "required":
            return {"type": "any"}
        if choice == "none":
            return {"type": "none"}
        if isinstance(choice, dict):
            if choice.get("type") in {"auto", "any", "tool", "none"}:
                return choice
            function = choice.get("function")
            if (
                choice.get("type") == "function"
                and isinstance(function, dict)
                and function.get("name")
            ):
                return {"type": "tool", "name": function["name"]}
        return None

    def _body(
        self, provider: Provider, model: Model, request: GatewayChatRequest
    ) -> dict[str, Any]:
        source = request.body
        provider_config = provider.config or {}
        body: dict[str, Any] = {
            "model": model.name,
            "messages": self._messages(request.messages),
            "max_tokens": int(
                source.get("max_tokens")
                or source.get("max_completion_tokens")
                or provider_config.get("default_max_tokens")
                or 1024
            ),
        }
        system = self._system(request.messages)
        if system:
            body["system"] = system

        field_map = {
            "temperature": "temperature",
            "top_p": "top_p",
            "top_k": "top_k",
            "metadata": "metadata",
            "thinking": "thinking",
            "service_tier": "service_tier",
        }
        for source_field, target_field in field_map.items():
            if source.get(source_field) is not None:
                body[target_field] = source[source_field]

        if source.get("user") and "metadata" not in body:
            body["metadata"] = {"user_id": source["user"]}
        if source.get("stop") is not None:
            stop = source["stop"]
            body["stop_sequences"] = stop if isinstance(stop, list) else [stop]
        if request.stream:
            body["stream"] = True

        tools = self._tools(source.get("tools"))
        if tools:
            body["tools"] = tools
            tool_choice = self._tool_choice(source.get("tool_choice"))
            if tool_choice:
                body["tool_choice"] = tool_choice

        for field in provider_config.get("request_body_passthrough_fields") or []:
            if isinstance(field, str) and source.get(field) is not None:
                body[field] = source[field]

        return self._apply_provider_body_config(body, provider_config)

    def _apply_provider_body_config(
        self, body: dict[str, Any], provider_config: dict[str, Any]
    ) -> dict[str, Any]:
        remove_fields = provider_config.get("request_body_remove_fields") or []
        if isinstance(remove_fields, list):
            for field in remove_fields:
                if isinstance(field, str):
                    body.pop(field, None)

        overrides = provider_config.get("request_body_overrides") or {}
        if isinstance(overrides, dict):
            body.update(overrides)
        return body

    def _assistant_text(self, payload: dict[str, Any]) -> str:
        parts: list[str] = []
        for block in payload.get("content") or []:
            if (
                isinstance(block, dict)
                and block.get("type") == "text"
                and isinstance(block.get("text"), str)
            ):
                parts.append(block["text"])
        return "".join(parts)

    def _tool_calls(self, payload: dict[str, Any]) -> list[dict[str, Any]] | None:
        calls: list[dict[str, Any]] = []
        for block in payload.get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            calls.append(
                {
                    "id": block.get("id"),
                    "type": "function",
                    "function": {
                        "name": block.get("name"),
                        "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
                    },
                }
            )
        return calls or None

    def _finish_reason(self, reason: str | None) -> str | None:
        return {
            "end_turn": "stop",
            "stop_sequence": "stop",
            "max_tokens": "length",
            "model_context_window_exceeded": "length",
            "tool_use": "tool_calls",
            "refusal": "content_filter",
            "pause_turn": "stop",
        }.get(reason or "", reason)

    def _openai_usage(self, usage: NativeUsageResult) -> dict[str, Any]:
        result = {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
        }
        if usage.cached_input_tokens:
            result["prompt_tokens_details"] = {"cached_tokens": usage.cached_input_tokens}
        return result

    def _openai_body(
        self, request: GatewayChatRequest, model: Model, payload: dict[str, Any]
    ) -> dict[str, Any]:
        usage = AnthropicUsageParser().parse(payload)
        message: dict[str, Any] = {"role": "assistant", "content": self._assistant_text(payload)}
        tool_calls = self._tool_calls(payload)
        if tool_calls:
            message["tool_calls"] = tool_calls

        return {
            "id": payload.get("id") or f"claude-{request.request_id}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": payload.get("model") or model.name,
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": self._finish_reason(payload.get("stop_reason")),
                }
            ],
            "usage": self._openai_usage(usage),
            "claude": payload,
        }

    async def chat_completion(
        self, provider: Provider, model: Model, request: GatewayChatRequest
    ) -> GatewayChatResponse:
        timeout = (provider.timeout_ms or 60000) / 1000
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self._url(provider),
                    headers=self._headers(provider),
                    json=self._body(provider, model, request),
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
            error_type = (
                "rate_limit" if response.status_code in {429, 529} else "provider_error"
            )
            raise ProviderCallError(
                f"Provider returned HTTP {response.status_code}",
                status_code=response.status_code,
                error_type=error_type,
                response_body=response.text[:4000],
                response_headers=dict(response.headers),
                retryable=response.status_code in {429, 500, 502, 503, 504, 529},
            )

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ProviderCallError(
                "Provider returned invalid JSON", error_type="provider_error"
            ) from exc

        usage = AnthropicUsageParser().parse(payload)
        return GatewayChatResponse(
            body=self._openai_body(request, model, payload),
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            cached_input_tokens=usage.cached_input_tokens,
            raw_usage=usage.raw_usage,
            usage_status=usage.usage_status,
        )

    def _openai_stream_chunk(
        self,
        message_id: str,
        model_name: str,
        choices: list[dict[str, Any]],
        usage: NativeUsageResult | None = None,
    ) -> bytes:
        payload: dict[str, Any] = {
            "id": message_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model_name,
            "choices": choices,
        }
        if usage:
            payload["usage"] = self._openai_usage(usage)
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

    async def stream_chat_completion(
        self, provider: Provider, model: Model, request: GatewayChatRequest
    ) -> AsyncIterator[GatewayChatChunk]:
        timeout = (provider.timeout_ms or 60000) / 1000
        message_id = f"claude-{request.request_id}"
        stream_model_name = model.name
        raw_usage: dict[str, Any] = {}
        first_content = True
        emitted_usage = False
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    self._url(provider),
                    headers=self._headers(provider),
                    json=self._body(provider, model, request),
                ) as response:
                    if response.status_code >= 400:
                        text = await response.aread()
                        error_type = (
                            "rate_limit"
                            if response.status_code in {429, 529}
                            else "provider_error"
                        )
                        raise ProviderCallError(
                            f"Provider returned HTTP {response.status_code}",
                            status_code=response.status_code,
                            error_type=error_type,
                            response_body=text.decode("utf-8", errors="ignore")[:4000],
                            response_headers=dict(response.headers),
                            retryable=response.status_code in {429, 500, 502, 503, 504, 529},
                        )

                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        raw = line.removeprefix("data:").strip()
                        if not raw:
                            continue
                        payload = json.loads(raw)
                        event_type = payload.get("type")
                        if event_type == "error":
                            error = payload.get("error") or {}
                            raise ProviderCallError(
                                error.get("message") or "Provider stream returned an error",
                                error_type=error.get("type") or "provider_error",
                                response_body=raw[:4000],
                            )
                        if event_type == "message_start":
                            message = payload.get("message") or {}
                            message_id = message.get("id") or message_id
                            stream_model_name = message.get("model") or stream_model_name
                            if isinstance(message.get("usage"), dict):
                                raw_usage.update(message["usage"])
                            yield GatewayChatChunk(
                                data=self._openai_stream_chunk(
                                    message_id,
                                    stream_model_name,
                                    [
                                        {
                                            "index": 0,
                                            "delta": {"role": "assistant"},
                                            "finish_reason": None,
                                        }
                                    ],
                                )
                            )
                        elif event_type == "content_block_delta":
                            delta = payload.get("delta") or {}
                            if delta.get("type") != "text_delta" or not isinstance(
                                delta.get("text"), str
                            ):
                                continue
                            text = delta["text"]
                            yield GatewayChatChunk(
                                data=self._openai_stream_chunk(
                                    message_id,
                                    stream_model_name,
                                    [
                                        {
                                            "index": 0,
                                            "delta": {"content": text},
                                            "finish_reason": None,
                                        }
                                    ],
                                ),
                                first_token=first_content,
                                completion_delta=text,
                            )
                            first_content = False
                        elif event_type == "message_delta":
                            delta = payload.get("delta") or {}
                            if isinstance(payload.get("usage"), dict):
                                raw_usage.update(payload["usage"])
                            usage = AnthropicUsageParser().parse(raw_usage) if raw_usage else None
                            finish_reason = self._finish_reason(delta.get("stop_reason"))
                            choices = []
                            if finish_reason:
                                choices.append(
                                    {"index": 0, "delta": {}, "finish_reason": finish_reason}
                                )
                            emitted_usage = usage is not None
                            yield GatewayChatChunk(
                                data=self._openai_stream_chunk(
                                    message_id, stream_model_name, choices, usage
                                ),
                                prompt_tokens=usage.prompt_tokens if usage else 0,
                                completion_tokens=usage.completion_tokens if usage else 0,
                                total_tokens=usage.total_tokens if usage else 0,
                                cached_input_tokens=usage.cached_input_tokens if usage else 0,
                                raw_usage=usage.raw_usage if usage else None,
                                usage_status=usage.usage_status if usage else "unknown",
                            )
                        elif event_type == "message_stop":
                            if raw_usage and not emitted_usage:
                                usage = AnthropicUsageParser().parse(raw_usage)
                                yield GatewayChatChunk(
                                    data=self._openai_stream_chunk(
                                        message_id, stream_model_name, [], usage
                                    ),
                                    prompt_tokens=usage.prompt_tokens,
                                    completion_tokens=usage.completion_tokens,
                                    total_tokens=usage.total_tokens,
                                    cached_input_tokens=usage.cached_input_tokens,
                                    raw_usage=usage.raw_usage,
                                    usage_status=usage.usage_status,
                                )
                            yield GatewayChatChunk(data=b"data: [DONE]\n\n")
        except httpx.TimeoutException as exc:
            raise ProviderCallError("Provider stream timed out", error_type="timeout") from exc
        except httpx.ConnectError as exc:
            raise ProviderCallError(
                "Provider stream connection failed", error_type="connection_error"
            ) from exc
        except json.JSONDecodeError as exc:
            raise ProviderCallError(
                "Provider stream returned invalid JSON", error_type="provider_error"
            ) from exc
