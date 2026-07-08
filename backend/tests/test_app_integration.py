import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx
from fastapi import Depends, Header, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.deps import get_auth_context, get_redis, require_admin, session_dep
from app.core.config import get_settings
from app.core.security import authenticate_api_key
from app.db.models import AdminUser, Base
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


@pytest.fixture
async def auth_app_client(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-bootstrap-token")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-with-at-least-32-bytes")
    get_settings.cache_clear()
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

    app = create_app()
    app.dependency_overrides[session_dep] = override_session
    app.dependency_overrides[get_auth_context] = override_auth
    app.dependency_overrides[get_redis] = lambda: None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, session_factory

    get_settings.cache_clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_auth_register_login_and_access_admin_api(auth_app_client):
    client, _ = auth_app_client

    register_response = await client.post(
        "/auth/register",
        json={
            "email": "admin@example.com",
            "username": "admin",
            "password": "Password123",
            "display_name": "Admin",
        },
    )
    assert register_response.status_code == 201
    assert register_response.json()["status"] == "active"
    assert "role" not in register_response.json()

    login_response = await client.post(
        "/auth/login", json={"account": "admin@example.com", "password": "Password123"}
    )
    payload = login_response.json()
    assert login_response.status_code == 200
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["refresh_token"]

    dashboard_response = await client.get(
        "/admin/dashboard", headers={"Authorization": f"Bearer {payload['access_token']}"}
    )
    assert dashboard_response.status_code == 200

    legacy_token_response = await client.get(
        "/admin/dashboard", headers={"Authorization": "Bearer test-bootstrap-token"}
    )
    assert legacy_token_response.status_code == 401


@pytest.mark.asyncio
async def test_admin_auth_register_requires_bootstrap_after_first_user(auth_app_client):
    client, _ = auth_app_client

    await client.post(
        "/auth/register",
        json={
            "email": "admin@example.com",
            "username": "admin",
            "password": "Password123",
            "display_name": "Admin",
        },
    )

    blocked_response = await client.post(
        "/auth/register",
        json={
            "email": "ops@example.com",
            "username": "ops",
            "password": "Password123",
            "display_name": "Ops",
        },
    )
    assert blocked_response.status_code == 401

    created_response = await client.post(
        "/auth/register",
        headers={"Authorization": "Bearer test-bootstrap-token"},
        json={
            "email": "ops@example.com",
            "username": "ops",
            "password": "Password123",
            "display_name": "Ops",
        },
    )
    assert created_response.status_code == 201


@pytest.mark.asyncio
async def test_admin_auth_refresh_rotation_and_logout(auth_app_client):
    client, _ = auth_app_client
    await client.post(
        "/auth/register",
        json={
            "email": "admin@example.com",
            "username": "admin",
            "password": "Password123",
            "display_name": "Admin",
        },
    )
    login_payload = (
        await client.post(
            "/auth/login", json={"account": "admin", "password": "Password123"}
        )
    ).json()

    refresh_response = await client.post(
        "/auth/refresh", json={"refresh_token": login_payload["refresh_token"]}
    )
    refresh_payload = refresh_response.json()
    assert refresh_response.status_code == 200
    assert refresh_payload["refresh_token"] != login_payload["refresh_token"]

    reused_response = await client.post(
        "/auth/refresh", json={"refresh_token": login_payload["refresh_token"]}
    )
    assert reused_response.status_code == 401

    logout_response = await client.post(
        "/auth/logout", json={"refresh_token": refresh_payload["refresh_token"]}
    )
    assert logout_response.status_code == 204

    after_logout_response = await client.post(
        "/auth/refresh", json={"refresh_token": refresh_payload["refresh_token"]}
    )
    assert after_logout_response.status_code == 401


@pytest.mark.asyncio
async def test_admin_auth_change_password_invalidates_existing_tokens(auth_app_client):
    client, _ = auth_app_client
    await client.post(
        "/auth/register",
        json={
            "email": "admin@example.com",
            "username": "admin",
            "password": "Password123",
            "display_name": "Admin",
        },
    )
    login_payload = (
        await client.post(
            "/auth/login", json={"account": "admin", "password": "Password123"}
        )
    ).json()
    headers = {"Authorization": f"Bearer {login_payload['access_token']}"}

    change_response = await client.post(
        "/auth/change-password",
        headers=headers,
        json={"old_password": "Password123", "new_password": "NewPassword123"},
    )
    assert change_response.status_code == 204

    me_response = await client.get("/auth/me", headers=headers)
    assert me_response.status_code == 401

    old_login_response = await client.post(
        "/auth/login", json={"account": "admin", "password": "Password123"}
    )
    assert old_login_response.status_code == 401

    new_login_response = await client.post(
        "/auth/login", json={"account": "admin", "password": "NewPassword123"}
    )
    assert new_login_response.status_code == 200


@pytest.mark.asyncio
async def test_admin_auth_disabled_user_cannot_keep_using_access_token(auth_app_client):
    client, session_factory = auth_app_client
    await client.post(
        "/auth/register",
        json={
            "email": "admin@example.com",
            "username": "admin",
            "password": "Password123",
            "display_name": "Admin",
        },
    )
    login_payload = (
        await client.post(
            "/auth/login", json={"account": "admin", "password": "Password123"}
        )
    ).json()

    async with session_factory() as session:
        await session.execute(update(AdminUser).values(status="disabled"))
        await session.commit()

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {login_payload['access_token']}"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_access_token_does_not_authenticate_gateway_calls(auth_app_client):
    client, _ = auth_app_client
    await client.post(
        "/auth/register",
        json={
            "email": "admin@example.com",
            "username": "admin",
            "password": "Password123",
            "display_name": "Admin",
        },
    )
    login_payload = (
        await client.post(
            "/auth/login", json={"account": "admin", "password": "Password123"}
        )
    ).json()

    response = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
        json={"model": "default-chat", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


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
async def test_admin_providers_pagination_and_delete_cleanup(app_client):
    client = app_client
    provider_one = (
        await client.post(
            "/admin/providers",
            json={
                "name": "openai",
                "provider_type": "openai_compatible",
                "base_url": "https://openai.test",
                "protocol_modes": ["openai_compatible"],
                "status": "active",
            },
        )
    ).json()
    provider_two = (
        await client.post(
            "/admin/providers",
            json={
                "name": "gemini",
                "provider_type": "gemini",
                "base_url": "https://gemini.test",
                "protocol_modes": ["native_proxy"],
                "status": "active",
            },
        )
    ).json()
    model_one = (
        await client.post(
            "/admin/models",
            json={"provider_id": provider_one["id"], "name": "gpt-test", "status": "active"},
        )
    ).json()
    model_two = (
        await client.post(
            "/admin/models",
            json={"provider_id": provider_two["id"], "name": "gemini-test", "status": "active"},
        )
    ).json()
    alias = (
        await client.post("/admin/model-aliases", json={"alias": "default-chat", "status": "active"})
    ).json()
    await client.post(
        "/admin/route-rules",
        json={
            "model_alias_id": alias["id"],
            "primary_model_id": model_two["id"],
            "fallback_model_ids": [model_one["id"]],
            "status": "active",
        },
    )

    provider_page = await client.get("/admin/providers?limit=1&offset=0")
    assert provider_page.json()["total"] == 2
    assert len(provider_page.json()["items"]) == 1

    assert (await client.delete(f"/admin/providers/{provider_one['id']}")).status_code == 204
    providers_after_delete = (await client.get("/admin/providers")).json()
    models_after_delete = (await client.get("/admin/models")).json()
    routes_after_delete = (await client.get("/admin/route-rules")).json()

    assert providers_after_delete["total"] == 1
    assert [item["id"] for item in providers_after_delete["items"]] == [provider_two["id"]]
    assert [item["id"] for item in models_after_delete["items"]] == [model_two["id"]]
    assert routes_after_delete["items"][0]["fallback_model_ids"] == []


@pytest.mark.asyncio
async def test_admin_provider_patch_config_returns_refreshed_timestamps(app_client):
    client = app_client
    provider = (
        await client.post(
            "/admin/providers",
            json={
                "name": "deepseek",
                "provider_type": "openai_compatible",
                "base_url": "https://api.deepseek.test",
                "protocol_modes": ["openai_compatible"],
                "status": "active",
            },
        )
    ).json()

    response = await client.patch(
        f"/admin/providers/{provider['id']}",
        json={
            "config": {
                "request_body_remove_fields": ["reasoning_effort"],
                "request_body_overrides": {"thinking": {"type": "disabled"}},
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["config"]["request_body_remove_fields"] == ["reasoning_effort"]
    assert response.json()["config"]["request_body_overrides"]["thinking"] == {"type": "disabled"}
    assert response.json()["updated_at"]


@pytest.mark.asyncio
async def test_admin_models_aliases_and_routes_pagination_and_delete(app_client):
    client = app_client
    provider = (
        await client.post(
            "/admin/providers",
            json={
                "name": "openai",
                "provider_type": "openai_compatible",
                "base_url": "https://openai.test",
                "protocol_modes": ["openai_compatible"],
                "status": "active",
            },
        )
    ).json()
    primary_model = (
        await client.post(
            "/admin/models",
            json={"provider_id": provider["id"], "name": "primary-model", "status": "active"},
        )
    ).json()
    fallback_model = (
        await client.post(
            "/admin/models",
            json={"provider_id": provider["id"], "name": "fallback-model", "status": "active"},
        )
    ).json()
    alias = (
        await client.post("/admin/model-aliases", json={"alias": "default-chat", "status": "active"})
    ).json()
    route_rule = (
        await client.post(
            "/admin/route-rules",
            json={
                "model_alias_id": alias["id"],
                "primary_model_id": primary_model["id"],
                "fallback_model_ids": [fallback_model["id"]],
                "status": "active",
            },
        )
    ).json()

    model_page = await client.get("/admin/models?limit=1&offset=0")
    alias_page = await client.get("/admin/model-aliases?limit=1&offset=0")
    route_page = await client.get("/admin/route-rules?limit=1&offset=0")

    assert model_page.json()["total"] == 2
    assert len(model_page.json()["items"]) == 1
    assert alias_page.json()["total"] == 1
    assert route_page.json()["total"] == 1

    assert (await client.delete(f"/admin/models/{fallback_model['id']}")).status_code == 204
    routes_after_fallback_delete = (await client.get("/admin/route-rules")).json()["items"]
    assert routes_after_fallback_delete[0]["fallback_model_ids"] == []

    assert (await client.delete(f"/admin/route-rules/{route_rule['id']}")).status_code == 204
    assert (await client.get("/admin/route-rules")).json()["total"] == 0

    replacement_route = (
        await client.post(
            "/admin/route-rules",
            json={
                "model_alias_id": alias["id"],
                "primary_model_id": primary_model["id"],
                "fallback_model_ids": [],
                "status": "active",
            },
        )
    ).json()
    assert replacement_route["id"]

    assert (await client.delete(f"/admin/model-aliases/{alias['id']}")).status_code == 204
    assert (await client.get("/admin/model-aliases")).json()["total"] == 0
    assert (await client.get("/admin/route-rules")).json()["total"] == 0


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
    price = (
        await client.post(
            "/admin/model-price-configs",
            json={
                "provider_id": provider["id"],
                "model_id": model["id"],
                "model_name": model["name"],
                "currency_code": "USD",
                "unit_quantity": 1000,
                "input_unit_price": "2.00",
                "cached_input_unit_price": "0.50",
                "output_unit_price": "8.00",
                "status": "active",
            },
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
    logs = (await client.get("/admin/usage-logs")).json()["items"]
    filtered = (
        await client.get(
            "/admin/usage-logs",
            params={
                "usage_status": "parsed",
            },
        )
    ).json()

    assert response.status_code == 200
    assert response.json()["id"] == "chatcmpl-test"
    assert logs[0]["call_mode"] == "unified_chat"
    assert logs[0]["api_key_id"] == key_payload["id"]
    assert logs[0]["prompt_content"]["messages"][0]["content"] == "hi"
    assert logs[0]["pricing_config_id"] == price["id"]
    assert logs[0]["pricing_status"] == "calculated"
    assert logs[0]["cost_currency"] == "USD"
    assert logs[0]["total_cost"] is not None
    assert filtered["total"] == 1
    assert filtered["items"][0]["usage_status"] == "parsed"

    key_filtered = (
        await client.get("/admin/usage-logs", params={"api_key_id": key_payload["id"]})
    ).json()
    summary = (
        await client.get("/admin/usage-summary", params={"group_by": "total", "api_key_id": key_payload["id"]})
    ).json()

    assert key_filtered["total"] == 1
    assert summary["items"][0]["request_count"] == 1
    assert summary["items"][0]["total_tokens"] == 2


@pytest.mark.asyncio
async def test_chat_skips_unhealthy_primary_and_uses_fallback(app_client, monkeypatch):
    calls = []

    class Adapter:
        async def chat_completion(self, provider, model, request):
            calls.append((provider.name, model.name))
            return GatewayChatResponse(
                body={
                    "id": "chatcmpl-fallback",
                    "object": "chat.completion",
                    "choices": [{"message": {"role": "assistant", "content": "fallback"}}],
                },
                prompt_tokens=1,
                completion_tokens=2,
                total_tokens=3,
                raw_usage={"total_tokens": 3},
                usage_status="parsed",
            )

    from app.services import provider_service

    monkeypatch.setattr(provider_service.registry, "get_chat", lambda provider_type: Adapter())

    client = app_client
    created_client = (await client.post("/admin/clients", json={"name": "fallback-client"})).json()
    key_payload = (
        await client.post(
            "/admin/api-keys",
            json={
                "client_id": created_client["id"],
                "name": "fallback-key",
                "access_config": {"model_aliases": ["default-chat"], "provider_names": ["primary", "fallback"]},
            },
        )
    ).json()
    primary_provider = (
        await client.post(
            "/admin/providers",
            json={
                "name": "primary",
                "provider_type": "openai_compatible",
                "base_url": "https://primary.test",
                "protocol_modes": ["openai_compatible"],
                "status": "active",
                "health_status": "unhealthy",
                "failure_count": 5,
                "failure_threshold": 5,
                "cooldown_until": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            },
        )
    ).json()
    fallback_provider = (
        await client.post(
            "/admin/providers",
            json={
                "name": "fallback",
                "provider_type": "openai_compatible",
                "base_url": "https://fallback.test",
                "protocol_modes": ["openai_compatible"],
                "status": "active",
            },
        )
    ).json()
    primary_model = (
        await client.post(
            "/admin/models",
            json={"provider_id": primary_provider["id"], "name": "primary-model", "status": "active"},
        )
    ).json()
    fallback_model = (
        await client.post(
            "/admin/models",
            json={"provider_id": fallback_provider["id"], "name": "fallback-model", "status": "active"},
        )
    ).json()
    alias = (
        await client.post("/admin/model-aliases", json={"alias": "default-chat", "status": "active"})
    ).json()
    await client.post(
        "/admin/route-rules",
        json={
            "model_alias_id": alias["id"],
            "primary_model_id": primary_model["id"],
            "fallback_model_ids": [fallback_model["id"]],
            "max_failover_attempts": 1,
            "status": "active",
        },
    )

    response = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key_payload['key']}"},
        json={"model": "default-chat", "messages": [{"role": "user", "content": "hi"}]},
    )
    logs = (await client.get("/admin/usage-logs")).json()["items"]

    assert response.status_code == 200
    assert calls == [("fallback", "fallback-model")]
    assert logs[0]["failover_triggered"] is True
    assert logs[0]["final_provider_id"] == fallback_provider["id"]


@pytest.mark.asyncio
async def test_admin_workbench_chat_test_uses_api_key_context(app_client, monkeypatch):
    class Adapter:
        async def chat_completion(self, provider, model, request):
            assert request.model_alias == "workbench-chat"
            assert request.provider_model == "gpt-workbench"
            return GatewayChatResponse(
                body={
                    "id": "chatcmpl-workbench",
                    "object": "chat.completion",
                    "choices": [{"message": {"role": "assistant", "content": "tested"}}],
                },
                prompt_tokens=2,
                completion_tokens=3,
                total_tokens=5,
                raw_usage={"total_tokens": 5},
                usage_status="parsed",
            )

    from app.services import provider_service

    monkeypatch.setattr(provider_service.registry, "get_chat", lambda provider_type: Adapter())

    client = app_client
    created_client = (await client.post("/admin/clients", json={"name": "workbench-client"})).json()
    key_payload = (
        await client.post(
            "/admin/api-keys",
            json={
                "client_id": created_client["id"],
                "name": "workbench-key",
                "access_config": {"model_aliases": ["workbench-chat"], "provider_names": ["openai"]},
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
    model = (
        await client.post(
            "/admin/models",
            json={"provider_id": provider["id"], "name": "gpt-workbench", "status": "active"},
        )
    ).json()
    alias = (
        await client.post(
            "/admin/model-aliases",
            json={"alias": "workbench-chat", "status": "active"},
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
        "/admin/workbench/chat-test",
        json={
            "api_key_id": key_payload["id"],
            "model": "workbench-chat",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["body"]["id"] == "chatcmpl-workbench"
    assert payload["meta"]["status"] == "success"
    assert payload["meta"]["usage_status"] == "parsed"
    assert payload["meta"]["total_tokens"] == 5
    assert payload["meta"]["final_model_id"] == model["id"]


@pytest.mark.asyncio
async def test_admin_workbench_chat_test_supports_gemini_alias(app_client):
    client = app_client
    created_client = (
        await client.post("/admin/clients", json={"name": "gemini-client"})
    ).json()
    key_payload = (
        await client.post(
            "/admin/api-keys",
            json={
                "client_id": created_client["id"],
                "name": "gemini-key",
                "access_config": {
                    "model_aliases": ["gemini-chat"],
                    "provider_names": ["gemini"],
                },
            },
        )
    ).json()
    provider = (
        await client.post(
            "/admin/providers",
            json={
                "name": "gemini",
                "provider_type": "gemini",
                "base_url": "https://gemini.test",
                "encrypted_api_key": "secret",
                "protocol_modes": ["native_proxy"],
                "auth_type": "api_key_query",
                "auth_config": {"query_name": "key"},
                "usage_parser_type": "gemini",
                "status": "active",
            },
        )
    ).json()
    model = (
        await client.post(
            "/admin/models",
            json={
                "provider_id": provider["id"],
                "name": "gemini-1.5-pro",
                "status": "active",
            },
        )
    ).json()
    alias = (
        await client.post(
            "/admin/model-aliases",
            json={"alias": "gemini-chat", "status": "active"},
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

    with respx.mock(assert_all_called=True) as router:
        gemini_route = router.post(
            "https://gemini.test/v1beta/models/gemini-1.5-pro:generateContent?key=secret"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {"parts": [{"text": "你好，我是 Gemini。"}]},
                            "finishReason": "STOP",
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 4,
                        "candidatesTokenCount": 6,
                        "totalTokenCount": 10,
                    },
                },
            )
        )

        response = await client.post(
            "/admin/workbench/chat-test",
            json={
                "api_key_id": key_payload["id"],
                "model": "gemini-chat",
                "messages": [
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "hi"},
                ],
                "temperature": 0.7,
                "max_tokens": 64,
            },
        )

    payload = response.json()
    upstream_body = json.loads(gemini_route.calls[0].request.content)

    assert response.status_code == 200
    assert upstream_body["systemInstruction"]["parts"][0]["text"] == "You are helpful."
    assert upstream_body["contents"][0]["role"] == "user"
    assert upstream_body["generationConfig"]["maxOutputTokens"] == 64
    assert payload["body"]["choices"][0]["message"]["content"] == "你好，我是 Gemini。"
    assert payload["meta"]["status"] == "success"
    assert payload["meta"]["usage_status"] == "parsed"
    assert payload["meta"]["total_tokens"] == 10
    assert payload["meta"]["final_model_id"] == model["id"]


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
    logs = (await client.get("/admin/usage-logs")).json()["items"]

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
    logs = (await client.get("/admin/usage-logs")).json()["items"]

    assert response.status_code == 200
    assert response.json()["id"] == "chatcmpl-direct-model"
    assert logs[0]["model_alias"] == "deepseek-v4-flash"
    assert logs[0]["final_model_id"] is not None
