import asyncio

import pytest
from fastapi import HTTPException

from app.core.errors import ProviderCallError
from app.core.security import AuthContext
from app.db.models import ApiKey, Client, Provider
from app.schemas.proxy import NativeProxyChunk, NativeUsageResult
from app.services.native_proxy_service import NativeProxyService


class FakeProviders:
    def __init__(self, provider):
        self.provider = provider

    async def get_active_by_name(self, name):
        return self.provider if name == self.provider.name else None


class FakeUsage:
    def __init__(self):
        self.records = []

    async def record(self, **data):
        self.records.append(data)


class FakeRateLimiter:
    async def check(self, key, limit=None, window_seconds=60):
        return None


class FakeRequest:
    def __init__(self, body=b"{}", headers=None, query=None):
        self._body = body
        self.headers = headers or {"content-type": "application/json"}
        class Query(dict):
            def multi_items(self):
                return list(self.items())

        self.query_params = Query(query or {})

    async def body(self):
        return self._body


def auth(access=None):
    return AuthContext(
        client=Client(id=1, name="client", status="active", access_config=access or {}),
        api_key=ApiKey(id=1, client_id=1, name="key", key_prefix="p", key_hash="h", status="active"),
    )


def provider():
    return Provider(
        id=1,
        name="gemini",
        provider_type="gemini",
        base_url="https://example.test",
        protocol_modes=["native_proxy"],
        allowed_paths=["v1beta/models/*"],
        status="active",
        native_rate_limit_per_minute=0,
    )


@pytest.mark.asyncio
async def test_native_proxy_access_denied_is_logged():
    service = NativeProxyService(session=None, redis=None)  # type: ignore[arg-type]
    service.providers = FakeProviders(provider())
    service.usage = FakeUsage()
    service.rate_limiter = FakeRateLimiter()

    with pytest.raises(HTTPException) as exc:
        await service.forward(
            auth({"provider_names": ["other"]}),
            "req-native",
            "gemini",
            "v1beta/models/gemini",
            "GET",
            FakeRequest(body=b""),
        )

    assert exc.value.status_code == 403
    assert service.usage.records[0]["error_code"] == "access_denied"


@pytest.mark.asyncio
async def test_native_proxy_provider_error_body_is_passthrough(monkeypatch):
    class Adapter:
        async def forward(self, provider, request):
            raise ProviderCallError(
                "bad request",
                status_code=400,
                error_type="provider_error",
                response_body='{"error":{"message":"native"}}',
                response_headers={"content-type": "application/json"},
            )

    from app.services import native_proxy_service

    monkeypatch.setattr(native_proxy_service.registry, "get_native", lambda provider_type: Adapter())
    service = NativeProxyService(session=None, redis=None)  # type: ignore[arg-type]
    service.providers = FakeProviders(provider())
    service.usage = FakeUsage()
    service.rate_limiter = FakeRateLimiter()

    response = await service.forward(
        auth(),
        "req-native",
        "gemini",
        "v1beta/models/gemini",
        "GET",
        FakeRequest(body=b""),
    )

    assert response.status_code == 400
    assert response.body == b'{"error":{"message":"native"}}'
    assert service.usage.records[0]["raw_response_body"] == '{"error":{"message":"native"}}'


@pytest.mark.asyncio
async def test_native_proxy_stream_records_usage(monkeypatch):
    class Adapter:
        async def stream_forward(self, provider, request):
            yield NativeProxyChunk(
                data=b'data: {"usageMetadata":{"promptTokenCount":2,"candidatesTokenCount":3,"totalTokenCount":5}}\n\n',
                usage=NativeUsageResult(
                    prompt_tokens=2,
                    completion_tokens=3,
                    total_tokens=5,
                    raw_usage={"totalTokenCount": 5},
                    usage_status="parsed",
                ),
            )

    from app.services import native_proxy_service

    monkeypatch.setattr(native_proxy_service.registry, "get_native", lambda provider_type: Adapter())
    service = NativeProxyService(session=None, redis=None)  # type: ignore[arg-type]
    service.providers = FakeProviders(provider())
    service.usage = FakeUsage()
    service.rate_limiter = FakeRateLimiter()

    response = await service.stream(
        auth(),
        "req-stream",
        "gemini",
        "v1beta/models/gemini:streamGenerateContent",
        "POST",
        FakeRequest(),
    )
    chunks = [chunk async for chunk in response.body_iterator]

    assert chunks
    assert service.usage.records[0]["usage_status"] == "parsed"
    assert service.usage.records[0]["total_tokens"] == 5


@pytest.mark.asyncio
async def test_native_proxy_stream_timeout_is_logged(monkeypatch):
    class Adapter:
        async def stream_forward(self, provider, request):
            await asyncio.sleep(0.05)
            yield NativeProxyChunk(data=b"late")

    from app.services import native_proxy_service

    monkeypatch.setattr(native_proxy_service.registry, "get_native", lambda provider_type: Adapter())
    service = NativeProxyService(session=None, redis=None)  # type: ignore[arg-type]
    service.settings.native_stream_max_seconds = 0.01
    service.providers = FakeProviders(provider())
    service.usage = FakeUsage()
    service.rate_limiter = FakeRateLimiter()

    response = await service.stream(
        auth(),
        "req-timeout",
        "gemini",
        "v1beta/models/gemini:streamGenerateContent",
        "POST",
        FakeRequest(),
    )
    with pytest.raises(TimeoutError):
        _ = [chunk async for chunk in response.body_iterator]

    assert service.usage.records[0]["error_code"] == "stream_timeout"
