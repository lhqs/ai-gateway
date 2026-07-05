from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, session_dep
from app.core.security import generate_api_key, hash_api_key
from app.db.models import ApiKey, Client, Model, ModelAlias, Provider, RouteRule, UsageLog
from app.repositories.api_keys import ApiKeyRepository
from app.repositories.base import Repository
from app.repositories.clients import ClientRepository
from app.repositories.models import ModelRepository
from app.repositories.providers import ProviderRepository
from app.repositories.route_rules import RouteRuleRepository
from app.repositories.usage_logs import UsageLogRepository
from app.schemas.admin import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyPage,
    ApiKeyRead,
    ClientCreate,
    ClientPage,
    ClientPatch,
    ClientRead,
    ModelAliasRead,
    ModelAliasPage,
    ModelAliasPatch,
    ModelAliasWrite,
    ModelPage,
    ModelPatch,
    ModelRead,
    ModelWrite,
    ProviderPage,
    ProviderPatch,
    ProviderRead,
    ProviderWrite,
    RouteRulePatch,
    RouteRulePage,
    RouteRuleRead,
    RouteRuleWrite,
)
from app.schemas.usage import UsageLogPage

router = APIRouter(dependencies=[Depends(require_admin)])


def _usage_filters(
    *,
    call_mode: str | None = None,
    native_path: str | None = None,
    status_filter: str | None = None,
    usage_status: str | None = None,
    cache_hit: bool | None = None,
    failover_triggered: bool | None = None,
) -> dict[str, Any]:
    return {
        "call_mode": call_mode,
        "native_path": native_path,
        "status": status_filter,
        "usage_status": usage_status,
        "cache_hit": cache_hit,
        "failover_triggered": failover_triggered,
    }


async def _patch(repo: Repository, item_id: int, data: dict[str, Any]):
    item = await repo.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    for key, value in data.items():
        if value is not None:
            setattr(item, key, value)
    await repo.session.flush()
    return item


@router.get("/clients", response_model=ClientPage)
async def list_clients(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(session_dep),
):
    repo = ClientRepository(session)
    return {
        "items": await repo.list(limit=limit, offset=offset),
        "total": await repo.count(),
        "limit": limit,
        "offset": offset,
    }


@router.post("/clients", response_model=ClientRead)
async def create_client(payload: ClientCreate, session: AsyncSession = Depends(session_dep)):
    return await ClientRepository(session).create(payload.model_dump())


@router.patch("/clients/{item_id}", response_model=ClientRead)
async def update_client(item_id: int, payload: ClientPatch, session: AsyncSession = Depends(session_dep)):
    return await _patch(ClientRepository(session), item_id, payload.model_dump(exclude_unset=True))


@router.delete("/clients/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(item_id: int, session: AsyncSession = Depends(session_dep)):
    repo = ClientRepository(session)
    item = await repo.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    await ApiKeyRepository(session).delete_for_client(item_id)
    await repo.delete(item)


@router.post("/api-keys", response_model=ApiKeyCreated)
async def create_api_key(payload: ApiKeyCreate, session: AsyncSession = Depends(session_dep)):
    raw_key, prefix = generate_api_key()
    item = await ApiKeyRepository(session).create(
        {
            "client_id": payload.client_id,
            "name": payload.name,
            "key_prefix": prefix,
            "key_hash": hash_api_key(raw_key),
            "key_value": raw_key,
            "expires_at": payload.expires_at,
            "access_config": payload.access_config,
            "status": "active",
        }
    )
    return ApiKeyCreated(id=item.id, key=raw_key, key_prefix=prefix)


@router.get("/api-keys", response_model=ApiKeyPage)
async def list_api_keys(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(session_dep),
):
    repo = ApiKeyRepository(session)
    return {
        "items": await repo.list_public(limit=limit, offset=offset),
        "total": await repo.count(),
        "limit": limit,
        "offset": offset,
    }


@router.patch("/api-keys/{item_id}")
async def update_api_key(item_id: int, payload: dict[str, Any], session: AsyncSession = Depends(session_dep)):
    return await _patch(ApiKeyRepository(session), item_id, payload)


@router.delete("/api-keys/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(item_id: int, session: AsyncSession = Depends(session_dep)):
    repo = ApiKeyRepository(session)
    item = await repo.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    await repo.delete(item)


@router.get("/providers", response_model=ProviderPage)
async def list_providers(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(session_dep),
):
    repo = ProviderRepository(session)
    return {
        "items": await repo.list(limit=limit, offset=offset),
        "total": await repo.count(),
        "limit": limit,
        "offset": offset,
    }


@router.post("/providers", response_model=ProviderRead)
async def create_provider(payload: ProviderWrite, session: AsyncSession = Depends(session_dep)):
    return await ProviderRepository(session).create(payload.model_dump())


@router.patch("/providers/{item_id}", response_model=ProviderRead)
async def update_provider(item_id: int, payload: ProviderPatch, session: AsyncSession = Depends(session_dep)):
    return await _patch(ProviderRepository(session), item_id, payload.model_dump(exclude_unset=True))


@router.delete("/providers/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(item_id: int, session: AsyncSession = Depends(session_dep)):
    repo = ProviderRepository(session)
    item = await repo.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    model_repo = ModelRepository(session)
    model_ids = await model_repo.list_ids_for_provider(item_id)
    await RouteRuleRepository(session).remove_model_references(model_ids)
    await model_repo.delete_for_provider(item_id)
    await repo.delete(item)


@router.post("/providers/{item_id}/test")
async def test_provider(item_id: int, session: AsyncSession = Depends(session_dep)):
    provider = await ProviderRepository(session).get(item_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    try:
        async with httpx.AsyncClient(timeout=min((provider.timeout_ms or 60000) / 1000, 10)) as client:
            response = await client.get(provider.base_url.rstrip("/"))
        provider.health_status = "healthy" if response.status_code < 500 else "degraded"
        return {"status": provider.health_status, "status_code": response.status_code}
    except httpx.HTTPError as exc:
        provider.health_status = "unhealthy"
        return {"status": "unhealthy", "error": str(exc)}


@router.get("/models", response_model=ModelPage)
async def list_models(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(session_dep),
):
    repo = ModelRepository(session)
    return {
        "items": await repo.list(limit=limit, offset=offset),
        "total": await repo.count(),
        "limit": limit,
        "offset": offset,
    }


@router.post("/models", response_model=ModelRead)
async def create_model(payload: ModelWrite, session: AsyncSession = Depends(session_dep)):
    return await ModelRepository(session).create(payload.model_dump())


@router.patch("/models/{item_id}", response_model=ModelRead)
async def update_model(item_id: int, payload: ModelPatch, session: AsyncSession = Depends(session_dep)):
    return await _patch(ModelRepository(session), item_id, payload.model_dump(exclude_unset=True))


@router.delete("/models/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(item_id: int, session: AsyncSession = Depends(session_dep)):
    repo = ModelRepository(session)
    item = await repo.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    await RouteRuleRepository(session).remove_model_references([item_id])
    await repo.delete(item)


class ModelAliasRepository(Repository[ModelAlias]):
    model = ModelAlias


@router.get("/model-aliases", response_model=ModelAliasPage)
async def list_aliases(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(session_dep),
):
    repo = ModelAliasRepository(session)
    return {
        "items": await repo.list(limit=limit, offset=offset),
        "total": await repo.count(),
        "limit": limit,
        "offset": offset,
    }


@router.post("/model-aliases", response_model=ModelAliasRead)
async def create_alias(payload: ModelAliasWrite, session: AsyncSession = Depends(session_dep)):
    return await ModelAliasRepository(session).create(payload.model_dump())


@router.patch("/model-aliases/{item_id}", response_model=ModelAliasRead)
async def update_alias(item_id: int, payload: ModelAliasPatch, session: AsyncSession = Depends(session_dep)):
    return await _patch(ModelAliasRepository(session), item_id, payload.model_dump(exclude_unset=True))


@router.delete("/model-aliases/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alias(item_id: int, session: AsyncSession = Depends(session_dep)):
    repo = ModelAliasRepository(session)
    item = await repo.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    await RouteRuleRepository(session).delete_for_alias(item_id)
    await repo.delete(item)


@router.get("/route-rules", response_model=RouteRulePage)
async def list_route_rules(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(session_dep),
):
    repo = RouteRuleRepository(session)
    return {
        "items": await repo.list(limit=limit, offset=offset),
        "total": await repo.count(),
        "limit": limit,
        "offset": offset,
    }


@router.post("/route-rules", response_model=RouteRuleRead)
async def create_route_rule(payload: RouteRuleWrite, session: AsyncSession = Depends(session_dep)):
    return await RouteRuleRepository(session).create(payload.model_dump())


@router.patch("/route-rules/{item_id}", response_model=RouteRuleRead)
async def update_route_rule(item_id: int, payload: RouteRulePatch, session: AsyncSession = Depends(session_dep)):
    return await _patch(RouteRuleRepository(session), item_id, payload.model_dump(exclude_unset=True))


@router.delete("/route-rules/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route_rule(item_id: int, session: AsyncSession = Depends(session_dep)):
    repo = RouteRuleRepository(session)
    item = await repo.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    await repo.delete(item)


@router.get("/usage-logs", response_model=UsageLogPage)
async def list_usage_logs(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    call_mode: str | None = None,
    native_path: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    usage_status: str | None = None,
    cache_hit: bool | None = None,
    failover_triggered: bool | None = None,
    session: AsyncSession = Depends(session_dep),
):
    filters = _usage_filters(
        call_mode=call_mode,
        native_path=native_path,
        status_filter=status_filter,
        usage_status=usage_status,
        cache_hit=cache_hit,
        failover_triggered=failover_triggered,
    )
    repo = UsageLogRepository(session)
    return {
        "items": await repo.list_recent(limit=limit, offset=offset, filters=filters),
        "total": await repo.count_recent(filters=filters),
        "limit": limit,
        "offset": offset,
    }


@router.get("/dashboard")
async def dashboard(session: AsyncSession = Depends(session_dep)):
    total = await session.scalar(select(func.count()).select_from(UsageLog))
    success = await session.scalar(select(func.count()).select_from(UsageLog).where(UsageLog.status == "success"))
    tokens = await session.scalar(select(func.coalesce(func.sum(UsageLog.total_tokens), 0)))
    avg_latency = await session.scalar(select(func.avg(UsageLog.latency_ms)))
    return {
        "total_requests": total or 0,
        "success_rate": float((success or 0) / total) if total else 0,
        "total_tokens": int(tokens or 0),
        "avg_latency_ms": float(avg_latency or 0),
    }
