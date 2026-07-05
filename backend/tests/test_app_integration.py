import pytest
from fastapi import Depends, Header, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.deps import get_auth_context, get_redis, require_admin, session_dep
from app.core.security import authenticate_api_key
from app.db.models import Base
from app.main import create_app
from app.schemas.chat import GatewayChatResponse


@pytest.fixture
async def app_client(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except HTTPException:
                await session.commit()
                raise
            except Exception:
                await session.rollback()
                raise

    async def override_auth(
        session=Depends(override_session), authorization: str | None = Header(default=None)
    ):
        return await authenticate_api_key(session, authorization)

    async def override_admin():
        return None

    app = create_app()
    app.dependency_overrides[session_dep] = override_session
    app.dependency_overrides[get_auth_context] = override_auth
    app.dependency_overrides[require_admin] = override_admin
    app.dependency_overrides[get_redis] = lambda: None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_clients_and_keys_pagination_and_delete(app_client):
    client = app_client
    client_one = (await client.post("/admin/clients", json={"name": "client-one"})).json()
    client_two = (await client.post("/admin/clients", json={"name": "client-two"})).json()
    key_one = (
        await client.post("/admin/api-keys", json={"client_id": client_one["id"], "name": "key-one"})
    ).json()
    key_two = (
        await client.post("/admin/api-keys", json={"client_id": client_two["id"], "name": "key-two"})
    ).json()

    client_page = await client.get("/admin/clients?limit=1&offset=0")
    key_page = await client.get("/admin/api-keys?limit=1&offset=0")

    assert client_page.json()["total"] == 2
    assert len(client_page.json()["items"]) == 1
    assert key_page.json()["total"] == 2
    assert len(key_page.json()["items"]) == 1

    assert (await client.delete(f"/admin/api-keys/{key_two['id']}")).status_code == 204
    keys_after_key_delete = (await client.get("/admin/api-keys")).json()["items"]
    assert [item["id"] for item in keys_after_key_delete] == [key_one["id"]]

    assert (await client.delete(f"/admin/clients/{client_one['id']}")).status_code == 204
    clients_after_client_delete = await client.get("/admin/clients")
    keys_after_client_delete = await client.get("/admin/api-keys")

    assert clients_after_client_delete.json()["total"] == 1
    assert [item["id"] for item in clients_after_client_delete.json()["items"]] == [client_two["id"]]
    assert keys_after_client_delete.json()["total"] == 0
    assert keys_after_client_delete.json()["items"] == []


@pytest.mark.asyncio
async def test_admin_config_to_chat_usage_log(app_client, monkeypatch):
    class Adapter:
        async def chat_completion(self, provider, model, request):
            return GatewayChatResponse(
                body={
                    "id": "chatcmpl-test",
                    "object": "chat.completion",
                    "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                },
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
                raw_usage={"total_tokens": 2},
                usage_status="parsed",
            )

    from app.services import provider_service

    monkeypatch.setattr(provider_service.registry, "get_chat", lambda provider_type: Adapter())

    client = app_client
    created_client = (await client.post("/admin/clients", json={"name": "client"})).json()
    key_payload = (
        await client.post(
            "/admin/api-keys",
            json={
                "client_id": created_client["id"],
                "name": "key",
                "access_config": {"model_aliases": ["default-chat"], "provider_names": ["openai"]},
            },
        )
    ).json()
    api_keys = (await client.get("/admin/api-keys")).json()["items"]
    assert api_keys[0]["key"] == key_payload["key"]
    assert "key_hash" not in api_keys[0]
    provider = (
        await client.post(
            "/admin/providers",
            json={
                "name": "openai",
                "provider_type": "openai_compatible",
                "base_url": "https://example.test",
                "protocol_modes": ["openai_compatible"],
                "status": "active",
            },
        )
    ).json()
    model = (
        await client.post(
            "/admin/models",
            json={"provider_id": provider["id"], "name": "gpt-test", "capabilities": ["chat"], "status": "active"},
        )
    ).json()
    alias = (
        await client.post(
            "/admin/model-aliases",
            json={"alias": "default-chat", "description": "default", "status": "active"},
        )
    ).json()
    await client.post(
        "/admin/route-rules",
        json={
            "model_alias_id": alias["id"],
            "primary_model_id": model["id"],
            "fallback_model_ids": [],
            "cache_enabled": False,
            "status": "active",
        },
    )

    response = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key_payload['key']}"},
        json={"model": "default-chat", "messages": [{"role": "user", "content": "hi"}]},
    )
    logs = (await client.get("/admin/usage-logs")).json()

    assert response.status_code == 200
    assert response.json()["id"] == "chatcmpl-test"
    assert logs[0]["call_mode"] == "unified_chat"
    assert logs[0]["prompt_content"]["messages"][0]["content"] == "hi"


@pytest.mark.asyncio
async def test_native_proxy_access_denied_through_app(app_client):
    client = app_client
    created_client = (await client.post("/admin/clients", json={"name": "native-client"})).json()
    key_payload = (
        await client.post(
            "/admin/api-keys",
            json={
                "client_id": created_client["id"],
                "name": "key",
                "access_config": {"provider_names": ["other"]},
            },
        )
    ).json()
    await client.post(
        "/admin/providers",
        json={
            "name": "gemini",
            "provider_type": "gemini",
            "base_url": "https://example.test",
            "protocol_modes": ["native_proxy"],
            "allowed_paths": ["v1beta/models/*"],
            "status": "active",
        },
    )

    response = await client.get(
        "/proxy/gemini/v1beta/models/gemini",
        headers={"Authorization": f"Bearer {key_payload['key']}"},
    )
    logs = (await client.get("/admin/usage-logs")).json()

    assert response.status_code == 403
    assert logs[0]["call_mode"] == "native_proxy"
    assert logs[0]["error_code"] == "access_denied"


@pytest.mark.asyncio
async def test_chat_can_call_active_provider_model_without_alias(app_client, monkeypatch):
    class Adapter:
        async def chat_completion(self, provider, model, request):
            assert request.model_alias == "deepseek-v4-flash"
            assert request.provider_model == "deepseek-v4-flash"
            return GatewayChatResponse(
                body={
                    "id": "chatcmpl-direct-model",
                    "object": "chat.completion",
                    "model": model.name,
                    "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                },
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
                usage_status="parsed",
            )

    from app.services import provider_service

    monkeypatch.setattr(provider_service.registry, "get_chat", lambda provider_type: Adapter())

    client = app_client
    created_client = (await client.post("/admin/clients", json={"name": "direct-client"})).json()
    key_payload = (
        await client.post(
            "/admin/api-keys",
            json={
                "client_id": created_client["id"],
                "name": "direct-key",
                "access_config": {"model_aliases": ["*"], "provider_names": ["openai"]},
            },
        )
    ).json()
    provider = (
        await client.post(
            "/admin/providers",
            json={
                "name": "openai",
                "provider_type": "openai_compatible",
                "base_url": "https://example.test",
                "protocol_modes": ["openai_compatible"],
                "status": "active",
            },
        )
    ).json()
    await client.post(
        "/admin/models",
        json={
            "provider_id": provider["id"],
            "name": "deepseek-v4-flash",
            "capabilities": ["chat"],
            "status": "active",
        },
    )

    response = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key_payload['key']}"},
        json={"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": "hi"}]},
    )
    logs = (await client.get("/admin/usage-logs")).json()

    assert response.status_code == 200
    assert response.json()["id"] == "chatcmpl-direct-model"
    assert logs[0]["model_alias"] == "deepseek-v4-flash"
    assert logs[0]["final_model_id"] is not None
