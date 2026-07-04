import json
from collections.abc import AsyncIterator
from fnmatch import fnmatch
from urllib.parse import urlencode

import httpx

from app.core.errors import ProviderCallError
from app.db.models import Provider
from app.schemas.proxy import NativeProxyChunk, NativeProxyRequest, NativeProxyResponse, NativeUsageResult
from app.usage.parsers.registry import get_usage_parser


DEFAULT_BLOCKED_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "host",
    "content-length",
    "connection",
    "x-forwarded-for",
    "x-real-ip",
}


class GeminiNativeProxyAdapter:
    provider_type = "gemini"

    def _is_allowed_path(self, provider: Provider, path: str) -> bool:
        allowed = provider.allowed_paths or []
        return any(fnmatch(path, pattern) for pattern in allowed)

    def _filtered_headers(self, provider: Provider, incoming: dict[str, str]) -> dict[str, str]:
        blocked = DEFAULT_BLOCKED_HEADERS | {h.lower() for h in (provider.blocked_headers or [])}
        headers = {k: v for k, v in incoming.items() if k.lower() not in blocked}
        headers.setdefault("content-type", "application/json")
        return headers

    def _url(self, provider: Provider, request: NativeProxyRequest) -> str:
        path = request.native_path.lstrip("/")
        url = f"{provider.base_url.rstrip('/')}/{path}"
        query = list(request.query_params)
        api_key = provider.encrypted_api_key or provider.auth_config.get("api_key")
        if provider.auth_type == "api_key_query" and api_key:
            query.append((provider.auth_config.get("query_name", "key"), api_key))
        if query:
            return f"{url}?{urlencode(query)}"
        return url

    def _headers(self, provider: Provider, request: NativeProxyRequest) -> dict[str, str]:
        headers = self._filtered_headers(provider, request.headers)
        api_key = provider.encrypted_api_key or provider.auth_config.get("api_key")
        if provider.auth_type == "api_key_header" and api_key:
            headers[provider.auth_config.get("header", "x-goog-api-key")] = api_key
        elif provider.auth_type == "bearer_token" and api_key:
            headers["authorization"] = f"Bearer {api_key}"
        return headers

    async def parse_usage(self, provider: Provider, payload: dict | None) -> NativeUsageResult:
        return get_usage_parser(provider.usage_parser_type).parse(payload)

    async def forward(self, provider: Provider, request: NativeProxyRequest) -> NativeProxyResponse:
        if not self._is_allowed_path(provider, request.native_path):
            raise ProviderCallError("Native path is not allowed", status_code=403, error_type="policy_error")
        timeout = (provider.timeout_ms or 60000) / 1000
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    request.method,
                    self._url(provider, request),
                    headers=self._headers(provider, request),
                    content=request.body if request.method == "POST" else None,
                )
        except httpx.TimeoutException as exc:
            raise ProviderCallError("Native provider request timed out", error_type="timeout") from exc
        except httpx.ConnectError as exc:
            raise ProviderCallError("Native provider connection failed", error_type="connection_error") from exc
        except httpx.HTTPError as exc:
            raise ProviderCallError(str(exc), error_type="provider_error") from exc

        payload: dict | None = None
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            try:
                payload = response.json()
            except json.JSONDecodeError:
                payload = None
        usage = await self.parse_usage(provider, payload)
        headers = {
            key: value
            for key, value in response.headers.items()
            if key.lower() not in {"content-length", "transfer-encoding", "connection"}
        }
        return NativeProxyResponse(
            status_code=response.status_code,
            headers=headers,
            body=response.content,
            usage=usage,
        )

    def _extract_stream_usage(self, chunk: bytes, provider: Provider) -> NativeUsageResult | None:
        text = chunk.decode("utf-8", errors="ignore")
        candidates: list[str] = []
        if text.strip().startswith("data:"):
            for line in text.splitlines():
                if line.startswith("data:"):
                    candidates.append(line.removeprefix("data:").strip())
        else:
            candidates.append(text.strip())
        for candidate in candidates:
            if not candidate or candidate == "[DONE]":
                continue
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            usage = get_usage_parser(provider.usage_parser_type).parse(payload)
            if usage.usage_status == "parsed":
                return usage
        return None

    async def stream_forward(self, provider: Provider, request: NativeProxyRequest) -> AsyncIterator[NativeProxyChunk]:
        if not provider.allow_streaming:
            raise ProviderCallError("Streaming is disabled for provider", status_code=403, error_type="policy_error")
        if not self._is_allowed_path(provider, request.native_path):
            raise ProviderCallError("Native path is not allowed", status_code=403, error_type="policy_error")
        timeout = (provider.timeout_ms or 60000) / 1000
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    request.method,
                    self._url(provider, request),
                    headers=self._headers(provider, request),
                    content=request.body if request.method == "POST" else None,
                ) as response:
                    if response.status_code >= 400:
                        text = await response.aread()
                        headers = {
                            key: value
                            for key, value in response.headers.items()
                            if key.lower() not in {"content-length", "transfer-encoding", "connection"}
                        }
                        raise ProviderCallError(
                            f"Native provider returned HTTP {response.status_code}",
                            status_code=response.status_code,
                            response_body=text.decode("utf-8", errors="ignore")[:4000],
                            response_headers=headers,
                        )
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            yield NativeProxyChunk(data=chunk, usage=self._extract_stream_usage(chunk, provider))
        except httpx.TimeoutException as exc:
            raise ProviderCallError("Native provider stream timed out", error_type="timeout") from exc
        except httpx.ConnectError as exc:
            raise ProviderCallError("Native provider stream connection failed", error_type="connection_error") from exc
