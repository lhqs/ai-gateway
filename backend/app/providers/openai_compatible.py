import json
from collections.abc import AsyncIterator

import httpx

from app.core.errors import ProviderCallError
from app.db.models import Model, Provider
from app.schemas.chat import GatewayChatChunk, GatewayChatRequest, GatewayChatResponse
from app.usage.parsers.openai import OpenAIUsageParser


class OpenAICompatibleAdapter:
    provider_type = "openai_compatible"

    def _headers(self, provider: Provider) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        api_key = provider.encrypted_api_key or provider.auth_config.get("api_key")
        if provider.auth_type == "bearer_token" and api_key:
            headers["authorization"] = f"Bearer {api_key}"
        elif provider.auth_type == "api_key_header" and api_key:
            header_name = provider.auth_config.get("header", "Authorization")
            prefix = provider.auth_config.get("prefix", "Bearer")
            headers[header_name] = f"{prefix} {api_key}" if prefix else api_key
        headers.update(provider.config.get("headers") or {})
        return headers

    def _body(self, model: Model, request: GatewayChatRequest) -> dict:
        body = dict(request.body)
        body["model"] = model.name
        return body

    def _url(self, provider: Provider) -> str:
        return f"{provider.base_url.rstrip('/')}/v1/chat/completions"

    async def chat_completion(
        self, provider: Provider, model: Model, request: GatewayChatRequest
    ) -> GatewayChatResponse:
        timeout = (provider.timeout_ms or 60000) / 1000
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self._url(provider), headers=self._headers(provider), json=self._body(model, request)
                )
        except httpx.TimeoutException as exc:
            raise ProviderCallError("Provider request timed out", error_type="timeout") from exc
        except httpx.ConnectError as exc:
            raise ProviderCallError("Provider connection failed", error_type="connection_error") from exc
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

        payload = response.json()
        usage = OpenAIUsageParser().parse(payload)
        return GatewayChatResponse(
            body=payload,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            raw_usage=usage.raw_usage,
            usage_status=usage.usage_status,
        )

    async def stream_chat_completion(
        self, provider: Provider, model: Model, request: GatewayChatRequest
    ) -> AsyncIterator[GatewayChatChunk]:
        timeout = (provider.timeout_ms or 60000) / 1000
        first = True
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    self._url(provider),
                    headers=self._headers(provider),
                    json=self._body(model, request),
                ) as response:
                    if response.status_code >= 400:
                        text = await response.aread()
                        error_type = "rate_limit" if response.status_code == 429 else "provider_error"
                        raise ProviderCallError(
                            f"Provider returned HTTP {response.status_code}",
                            status_code=response.status_code,
                            error_type=error_type,
                            response_body=text.decode("utf-8", errors="ignore")[:4000],
                        )
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = line if line.startswith("data:") else f"data: {line}"
                        payload = f"{data}\n\n".encode("utf-8")
                        yield GatewayChatChunk(data=payload, first_token=first)
                        first = False
        except httpx.TimeoutException as exc:
            raise ProviderCallError("Provider stream timed out", error_type="timeout") from exc
        except httpx.ConnectError as exc:
            raise ProviderCallError("Provider stream connection failed", error_type="connection_error") from exc
        except json.JSONDecodeError as exc:
            raise ProviderCallError("Provider stream returned invalid JSON", error_type="provider_error") from exc
