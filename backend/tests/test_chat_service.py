import pytest

from app.core.errors import ProviderCallError
from app.core.security import AuthContext
from app.db.models import ApiKey, Client, Model, ModelAlias, Provider, RouteRule
from app.schemas.chat import ChatCompletionRequest, ChatMessage, GatewayChatChunk, GatewayChatResponse
from app.services.cache_service import CacheService
from app.services.chat_service import ChatService


class MemoryCache(CacheService):
    def __init__(self):
        super().__init__(redis=None)
        self.values = {}

    async def get_json(self, cache_key):
        return self.values.get(cache_key)

    async def set_json(self, cache_key, value, ttl_seconds):
        self.values[cache_key] = value


class FakeRouting:
    def __init__(self):
        self.alias = ModelAlias(id=1, alias="default-chat", status="active")
        self.rule = RouteRule(
            id=1,
            model_alias_id=1,
            primary_model_id=1,
            fallback_model_ids=[2],
            failover_enabled=True,
            failover_on_status_codes=[500],
            failover_on_error_types=["timeout", "provider_error"],
            max_failover_attempts=1,
            cache_enabled=True,
            cache_ttl_seconds=60,
        )
        self.primary = Model(id=1, provider_id=1, name="primary-model", status="active")
        self.fallback = Model(id=2, provider_id=2, name="fallback-model", status="active")
        self.primary_provider = Provider(
            id=1,
            name="p1",
            provider_type="openai_compatible",
            base_url="https://p1.test",
            status="active",
        )
        self.fallback_provider = Provider(
            id=2,
            name="p2",
            provider_type="openai_compatible",
            base_url="https://p2.test",
            status="active",
        )

    async def resolve(self, model_alias):
        class Target:
            pass

        target = Target()
        target.alias = self.alias
        target.rule = self.rule
        target.model = self.primary
        target.provider = self.primary_provider
        return target

    async def resolve_model(self, model_id):
        assert model_id == 2
        return self.fallback, self.fallback_provider


class FakeProviderService:
    def __init__(self):
        self.calls = []

    async def chat_completion(self, provider, model, request):
        self.calls.append((provider.id, model.id))
        if model.id == 1:
            raise ProviderCallError("bad upstream", status_code=500, error_type="provider_error")
        return GatewayChatResponse(
            body={"id": "ok", "choices": [{"message": {"role": "assistant", "content": "done"}}]},
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
            raw_usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            usage_status="parsed",
        )


class FakeStreamProviderService:
    def __init__(self):
        self.calls = []

    async def stream_chat_completion(self, provider, model, request):
        self.calls.append((provider.id, model.id))
        if model.id == 1:
            raise ProviderCallError("stream failed before first token", status_code=500, error_type="provider_error")
        yield GatewayChatChunk(data=b"data: ok\n\n", first_token=True)


class FakeUsage:
    def __init__(self):
        self.records = []

    async def record(self, **data):
        self.records.append(data)


@pytest.mark.asyncio
async def test_chat_service_failover_then_cache_hit():
    service = ChatService(session=None, cache=MemoryCache())  # type: ignore[arg-type]
    service.routing = FakeRouting()
    provider_service = FakeProviderService()
    service.provider_service = provider_service
    usage = FakeUsage()
    service.usage = usage
    auth = AuthContext(
        client=Client(id=1, name="client", status="active"),
        api_key=ApiKey(id=1, client_id=1, name="key", key_prefix="p", key_hash="h", status="active"),
    )
    payload = ChatCompletionRequest(
        model="default-chat",
        messages=[ChatMessage(role="user", content="hello")],
        stream=False,
    )

    first = await service.complete(auth, "req-1", payload)
    second = await service.complete(auth, "req-2", payload)

    assert first["id"] == "ok"
    assert second["id"] == "ok"
    assert provider_service.calls == [(1, 1), (2, 2)]
    assert any(record["status"] == "failed" for record in usage.records)
    assert any(record["failover_triggered"] for record in usage.records if record["status"] == "success")
    assert usage.records[-1]["cache_hit"] is True


@pytest.mark.asyncio
async def test_chat_service_stream_failover_before_first_token():
    service = ChatService(session=None, cache=MemoryCache())  # type: ignore[arg-type]
    service.routing = FakeRouting()
    stream_provider = FakeStreamProviderService()
    service.provider_service = stream_provider
    usage = FakeUsage()
    service.usage = usage
    auth = AuthContext(
        client=Client(id=1, name="client", status="active"),
        api_key=ApiKey(id=1, client_id=1, name="key", key_prefix="p", key_hash="h", status="active"),
    )
    payload = ChatCompletionRequest(
        model="default-chat",
        messages=[ChatMessage(role="user", content="hello")],
        stream=True,
    )

    chunks = [chunk async for chunk in service.complete_stream(auth, "req-stream", payload)]

    assert chunks == [b"data: ok\n\n"]
    assert stream_provider.calls == [(1, 1), (2, 2)]
    assert any(record["status"] == "failed" for record in usage.records)
    assert usage.records[-1]["status"] == "success"
    assert usage.records[-1]["failover_triggered"] is True
