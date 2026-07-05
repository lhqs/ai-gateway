import asyncio

import pytest
from fastapi import HTTPException

from app.core.errors import ProviderCallError
from app.core.security import AuthContext
from app.db.models import ApiKey, Client, Model, ModelAlias, Provider, RouteRule
from app.schemas.proxy import NativeProxyChunk, NativeProxyResponse, NativeUsageResult
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


class FakeRouteRules:
    def __init__(self, alias=None, rule=None):
        self.alias = alias
        self.rule = rule

    async def get_for_alias(self, alias):
        if self.alias and self.rule and alias == self.alias.alias:
            return self.alias, self.rule
        return None


class FakeModels:
    def __init__(self, model=None):
        self.model = model

    async def get_active(self, model_id):
        return self.model if self.model and model_id == self.model.id else None


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
        api_key=ApiKey(
            id=1,
            client_id=1,
            name="key",
            key_prefix="p",
            key_hash="h",
            status="active",
        ),
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
    service.route_rules = FakeRouteRules()
    service.models = FakeModels()
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

    monkeypatch.setattr(
        native_proxy_service.registry, "get_native", lambda provider_type: Adapter()
    )
    service = NativeProxyService(session=None, redis=None)  # type: ignore[arg-type]
    service.providers = FakeProviders(provider())
    service.route_rules = FakeRouteRules()
    service.models = FakeModels()
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
async def test_native_proxy_rewrites_model_alias_in_gemini_path(monkeypatch):
    class Adapter:
        async def forward(self, provider, request):
            assert request.native_path == "v1beta/models/gemini-1.5-pro:generateContent"
            return NativeProxyResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                body=b'{"ok":true}',
                usage=NativeUsageResult(usage_status="unknown"),
            )

    from app.services import native_proxy_service

    monkeypatch.setattr(
        native_proxy_service.registry, "get_native", lambda provider_type: Adapter()
    )

    model = Model(id=10, provider_id=1, name="gemini-1.5-pro", status="active")
    alias = ModelAlias(id=20, alias="gemini-chat", status="active")
    rule = RouteRule(
        id=30,
        model_alias_id=alias.id,
        primary_model_id=model.id,
        fallback_model_ids=[],
        status="active",
    )
    service = NativeProxyService(session=None, redis=None)  # type: ignore[arg-type]
    service.providers = FakeProviders(provider())
    service.route_rules = FakeRouteRules(alias, rule)
    service.models = FakeModels(model)
    service.usage = FakeUsage()
    service.rate_limiter = FakeRateLimiter()

    response = await service.forward(
        auth({"model_aliases": ["gemini-chat"], "model_ids": [10]}),
        "req-alias",
        "gemini",
        "v1beta/models/gemini-chat:generateContent",
        "POST",
        FakeRequest(),
    )

    assert response.status_code == 200
    assert service.usage.records[0]["model_alias"] == "gemini-chat"
    assert service.usage.records[0]["model_id"] == 10
    assert service.usage.records[0]["native_path"] == "v1beta/models/gemini-chat:generateContent"


@pytest.mark.asyncio
async def test_native_proxy_stream_records_usage(monkeypatch):
    class Adapter:
        async def stream_forward(self, provider, request):
            yield NativeProxyChunk(
                data=(
                    b'data: {"usageMetadata":{"promptTokenCount":2,'
                    b'"candidatesTokenCount":3,"totalTokenCount":5}}\n\n'
                ),
                usage=NativeUsageResult(
                    prompt_tokens=2,
                    completion_tokens=3,
                    total_tokens=5,
                    raw_usage={"totalTokenCount": 5},
                    usage_status="parsed",
                ),
            )

    from app.services import native_proxy_service

    monkeypatch.setattr(
        native_proxy_service.registry, "get_native", lambda provider_type: Adapter()
    )
    service = NativeProxyService(session=None, redis=None)  # type: ignore[arg-type]
    service.providers = FakeProviders(provider())
    service.route_rules = FakeRouteRules()
    service.models = FakeModels()
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

    monkeypatch.setattr(
        native_proxy_service.registry, "get_native", lambda provider_type: Adapter()
    )
    service = NativeProxyService(session=None, redis=None)  # type: ignore[arg-type]
    service.settings.native_stream_max_seconds = 0.01
    service.providers = FakeProviders(provider())
    service.route_rules = FakeRouteRules()
    service.models = FakeModels()
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
