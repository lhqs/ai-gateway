from datetime import datetime, timedelta, timezone
from typing import Any

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
from app.repositories.model_price_configs import ModelPriceConfigRepository
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
    ModelAliasPage,
    ModelAliasPatch,
    ModelAliasRead,
    ModelAliasWrite,
    ModelPriceConfigPage,
    ModelPriceConfigPatch,
    ModelPriceConfigRead,
    ModelPriceConfigWrite,
    ModelPage,
    ModelPatch,
    ModelRead,
    ModelWrite,
    ProviderPage,
    ProviderPatch,
    ProviderConfigSchema,
    ProviderRead,
    ProviderWrite,
    RouteRulePatch,
    RouteRulePage,
    RouteRuleRead,
    RouteRuleValidateRequest,
    RouteRuleValidationModel,
    RouteRuleValidationResult,
    RouteRuleWrite,
)
from app.schemas.usage import UsageLogPage, UsageSummaryPage
from app.services.provider_health_service import ProviderHealthService

router = APIRouter(dependencies=[Depends(require_admin)])


def _usage_filters(
    *,
    call_mode: str | None = None,
    client_id: int | None = None,
    api_key_id: int | None = None,
    model_alias: str | None = None,
    provider_id: int | None = None,
    model_id: int | None = None,
    native_path: str | None = None,
    status_filter: str | None = None,
    usage_status: str | None = None,
    pricing_status: str | None = None,
    cost_currency: str | None = None,
    cache_hit: bool | None = None,
    failover_triggered: bool | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> dict[str, Any]:
    return {
        "call_mode": call_mode,
        "client_id": client_id,
        "api_key_id": api_key_id,
        "model_alias": model_alias,
        "provider_id": provider_id,
        "model_id": model_id,
        "native_path": native_path,
        "status": status_filter,
        "usage_status": usage_status,
        "pricing_status": pricing_status,
        "cost_currency": cost_currency.upper() if cost_currency else None,
        "cache_hit": cache_hit,
        "failover_triggered": failover_triggered,
        "created_from": created_from,
        "created_to": created_to,
    }


async def _patch(repo: Repository, item_id: int, data: dict[str, Any]):
    item = await repo.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    for key, value in data.items():
        setattr(item, key, value)
    await repo.session.flush()
    await repo.session.refresh(item)
    return item


async def _ensure_price_model_provider(
    session: AsyncSession, provider_id: int, model_id: int
) -> Model:
    provider = await ProviderRepository(session).get(provider_id)
    model = await ModelRepository(session).get(model_id)
    if not provider or not model or model.provider_id != provider.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Price config provider_id and model_id must reference the same model provider",
        )
    return model


def _normalize_price_payload(data: dict[str, Any], model: Model | None = None) -> dict[str, Any]:
    if data.get("currency_code"):
        data["currency_code"] = str(data["currency_code"]).upper()
    if data.get("currency_code") and data["currency_code"] not in {"USD", "CNY"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="currency_code must be USD or CNY",
        )
    if model and not data.get("model_name"):
        data["model_name"] = model.name
    return data


PROVIDER_CONFIG_SCHEMAS: dict[str, ProviderConfigSchema] = {
    "claude": ProviderConfigSchema(
        provider_type="claude",
        defaults={"health_path": "v1/models", "default_max_tokens": 4096},
        fields=[
            {
                "name": "health_path",
                "label": "Health Path",
                "default": "v1/models",
                "help_text": "Relative path used by provider health checks.",
            },
            {
                "name": "default_max_tokens",
                "label": "Default Max Tokens",
                "field_type": "number",
                "default": 4096,
                "help_text": "Fallback max_tokens for Claude requests that omit it.",
            },
        ],
    ),
    "gemini": ProviderConfigSchema(
        provider_type="gemini",
        defaults={"health_path": "v1beta/models"},
        fields=[
            {
                "name": "health_path",
                "label": "Health Path",
                "default": "v1beta/models",
                "help_text": "Relative path used by provider health checks.",
            },
            {
                "name": "forward_headers_allowlist",
                "label": "Forward Headers Allowlist",
                "field_type": "tags",
                "default": [],
                "help_text": "Optional native proxy headers allowed to pass upstream.",
            },
        ],
    ),
    "openai_compatible": ProviderConfigSchema(
        provider_type="openai_compatible",
        defaults={"health_path": "v1/models"},
        fields=[
            {
                "name": "health_path",
                "label": "Health Path",
                "default": "v1/models",
                "help_text": "Relative path used by provider health checks.",
            },
            {
                "name": "request_body_remove_fields",
                "label": "Remove Body Fields",
                "field_type": "tags",
                "default": [],
                "help_text": "Request body fields stripped before forwarding.",
            },
        ],
    ),
}


async def _model_validation_row(
    session: AsyncSession, model_id: int
) -> RouteRuleValidationModel:
    row = (
        await session.execute(
            select(Model, Provider)
            .join(Provider, Provider.id == Model.provider_id)
            .where(Model.id == model_id)
        )
    ).first()
    if not row:
        return RouteRuleValidationModel(model_id=model_id, available=False)
    model, provider = row[0], row[1]
    available = (
        model.status == "active"
        and provider.status == "active"
        and provider.health_status != "unhealthy"
    )
    return RouteRuleValidationModel(
        model_id=model.id,
        model_name=model.name,
        provider_id=provider.id,
        provider_name=provider.name,
        model_status=model.status,
        provider_status=provider.status,
        provider_health_status=provider.health_status,
        available=available,
    )


async def _validate_route_rule_payload(
    session: AsyncSession, payload: RouteRuleValidateRequest
) -> RouteRuleValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    ids = [payload.primary_model_id, *payload.fallback_model_ids]
    duplicate_model_ids = sorted({model_id for model_id in ids if ids.count(model_id) > 1})
    if duplicate_model_ids:
        errors.append("Primary and fallback models must not contain duplicates.")

    alias = await session.get(ModelAlias, payload.model_alias_id)
    if not alias:
        errors.append("Model alias does not exist.")
    elif alias.status != "active" and payload.status == "active":
        warnings.append("Route is active but the selected alias is not active.")

    if payload.max_failover_attempts < 0:
        errors.append("max_failover_attempts must be greater than or equal to 0.")
    if payload.cache_ttl_seconds < 0:
        errors.append("cache_ttl_seconds must be greater than or equal to 0.")
    if payload.failover_enabled and payload.fallback_model_ids and payload.max_failover_attempts < 1:
        warnings.append("Failover is enabled but max_failover_attempts is lower than the fallback count.")

    primary = await _model_validation_row(session, payload.primary_model_id)
    fallbacks = [
        await _model_validation_row(session, model_id)
        for model_id in payload.fallback_model_ids
    ]
    for label, model in [("Primary", primary), *[(f"Fallback {index + 1}", item) for index, item in enumerate(fallbacks)]]:
        if not model.model_name:
            errors.append(f"{label} model does not exist.")
        elif not model.available and payload.status == "active":
            warnings.append(
                f"{label} model is not fully available "
                f"({model.provider_name or 'unknown provider'} / "
                f"{model.model_status or 'missing model'} / "
                f"{model.provider_status or 'missing provider'} / "
                f"{model.provider_health_status or 'unknown health'})."
            )

    provider_ids = {
        model.provider_id
        for model in [primary, *fallbacks]
        if model.provider_id is not None
    }
    cross_provider = len(provider_ids) > 1
    if cross_provider:
        warnings.append("Fallback chain crosses providers; verify cost, capability, and data policy.")

    existing = await session.scalar(
        select(RouteRule).where(
            RouteRule.model_alias_id == payload.model_alias_id,
            RouteRule.status == "active",
            RouteRule.id != payload.id,
        )
    )
    if existing and payload.status == "active":
        warnings.append("Another active route rule already uses this alias; priority decides the winner.")

    return RouteRuleValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        primary=primary,
        fallbacks=fallbacks,
        duplicate_model_ids=duplicate_model_ids,
        cross_provider=cross_provider,
    )


async def _ensure_valid_route_rule(
    session: AsyncSession, payload: RouteRuleValidateRequest
) -> None:
    result = await _validate_route_rule_payload(session, payload)
    if not result.valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.errors[0])


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


@router.get("/provider-config-schema/{provider_type}", response_model=ProviderConfigSchema)
async def provider_config_schema(provider_type: str):
    schema = PROVIDER_CONFIG_SCHEMAS.get(provider_type)
    if not schema:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider type is unsupported")
    return schema


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
    return (await ProviderHealthService(session).probe(provider)).as_dict()


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


@router.get("/model-price-configs", response_model=ModelPriceConfigPage)
async def list_model_price_configs(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    model_id: int | None = None,
    provider_id: int | None = None,
    currency_code: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = None,
    session: AsyncSession = Depends(session_dep),
):
    repo = ModelPriceConfigRepository(session)
    return {
        "items": await repo.list_filtered(
            limit=limit,
            offset=offset,
            model_id=model_id,
            provider_id=provider_id,
            currency_code=currency_code,
            status=status_filter,
            search=search,
        ),
        "total": await repo.count_filtered(
            model_id=model_id,
            provider_id=provider_id,
            currency_code=currency_code,
            status=status_filter,
            search=search,
        ),
        "limit": limit,
        "offset": offset,
    }


@router.post("/model-price-configs", response_model=ModelPriceConfigRead)
async def create_model_price_config(
    payload: ModelPriceConfigWrite, session: AsyncSession = Depends(session_dep)
):
    data = payload.model_dump(exclude_none=True)
    model = await _ensure_price_model_provider(session, payload.provider_id, payload.model_id)
    data = _normalize_price_payload(data, model)
    return await ModelPriceConfigRepository(session).create(data)


@router.patch("/model-price-configs/{item_id}", response_model=ModelPriceConfigRead)
async def update_model_price_config(
    item_id: int, payload: ModelPriceConfigPatch, session: AsyncSession = Depends(session_dep)
):
    repo = ModelPriceConfigRepository(session)
    item = await repo.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    data = payload.model_dump(exclude_unset=True)
    provider_id = int(data.get("provider_id") or item.provider_id)
    model_id = int(data.get("model_id") or item.model_id)
    model = await _ensure_price_model_provider(session, provider_id, model_id)
    data = _normalize_price_payload(data, model)
    for key, value in data.items():
        setattr(item, key, value)
    await session.flush()
    await session.refresh(item)
    return item


@router.delete("/model-price-configs/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model_price_config(item_id: int, session: AsyncSession = Depends(session_dep)):
    repo = ModelPriceConfigRepository(session)
    item = await repo.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
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


@router.post("/route-rules/validate", response_model=RouteRuleValidationResult)
async def validate_route_rule(
    payload: RouteRuleValidateRequest, session: AsyncSession = Depends(session_dep)
):
    return await _validate_route_rule_payload(session, payload)


@router.post("/route-rules", response_model=RouteRuleRead)
async def create_route_rule(payload: RouteRuleWrite, session: AsyncSession = Depends(session_dep)):
    await _ensure_valid_route_rule(session, RouteRuleValidateRequest(**payload.model_dump()))
    return await RouteRuleRepository(session).create(payload.model_dump())


@router.patch("/route-rules/{item_id}", response_model=RouteRuleRead)
async def update_route_rule(item_id: int, payload: RouteRulePatch, session: AsyncSession = Depends(session_dep)):
    repo = RouteRuleRepository(session)
    item = await repo.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    merged = RouteRuleValidateRequest(
        id=item.id,
        model_alias_id=payload.model_alias_id if payload.model_alias_id is not None else item.model_alias_id,
        primary_model_id=payload.primary_model_id
        if payload.primary_model_id is not None
        else item.primary_model_id,
        fallback_model_ids=payload.fallback_model_ids
        if payload.fallback_model_ids is not None
        else item.fallback_model_ids,
        strategy_type=payload.strategy_type if payload.strategy_type is not None else item.strategy_type,
        strategy_config=payload.strategy_config
        if payload.strategy_config is not None
        else item.strategy_config,
        priority=payload.priority if payload.priority is not None else item.priority,
        status=payload.status if payload.status is not None else item.status,
        failover_enabled=payload.failover_enabled
        if payload.failover_enabled is not None
        else item.failover_enabled,
        failover_on_status_codes=payload.failover_on_status_codes
        if payload.failover_on_status_codes is not None
        else item.failover_on_status_codes,
        failover_on_error_types=payload.failover_on_error_types
        if payload.failover_on_error_types is not None
        else item.failover_on_error_types,
        max_failover_attempts=payload.max_failover_attempts
        if payload.max_failover_attempts is not None
        else item.max_failover_attempts,
        cache_enabled=payload.cache_enabled if payload.cache_enabled is not None else item.cache_enabled,
        cache_ttl_seconds=payload.cache_ttl_seconds
        if payload.cache_ttl_seconds is not None
        else item.cache_ttl_seconds,
        cache_scope=payload.cache_scope if payload.cache_scope is not None else item.cache_scope,
    )
    await _ensure_valid_route_rule(session, merged)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await session.flush()
    await session.refresh(item)
    return item


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
    client_id: int | None = None,
    api_key_id: int | None = None,
    model_alias: str | None = None,
    provider_id: int | None = None,
    model_id: int | None = None,
    native_path: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    usage_status: str | None = None,
    pricing_status: str | None = None,
    cost_currency: str | None = None,
    cache_hit: bool | None = None,
    failover_triggered: bool | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    session: AsyncSession = Depends(session_dep),
):
    filters = _usage_filters(
        call_mode=call_mode,
        client_id=client_id,
        api_key_id=api_key_id,
        model_alias=model_alias,
        provider_id=provider_id,
        model_id=model_id,
        native_path=native_path,
        status_filter=status_filter,
        usage_status=usage_status,
        pricing_status=pricing_status,
        cost_currency=cost_currency,
        cache_hit=cache_hit,
        failover_triggered=failover_triggered,
        created_from=created_from,
        created_to=created_to,
    )
    repo = UsageLogRepository(session)
    return {
        "items": await repo.list_recent(limit=limit, offset=offset, filters=filters),
        "total": await repo.count_recent(filters=filters),
        "limit": limit,
        "offset": offset,
    }


@router.get("/usage-summary", response_model=UsageSummaryPage)
async def usage_summary(
    group_by: str = Query(
        default="total",
        pattern="^(total|day|client|api_key|provider|model|model_alias|status|call_mode)$",
    ),
    limit: int = Query(default=100, ge=1, le=1000),
    call_mode: str | None = None,
    client_id: int | None = None,
    api_key_id: int | None = None,
    model_alias: str | None = None,
    provider_id: int | None = None,
    model_id: int | None = None,
    native_path: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    usage_status: str | None = None,
    pricing_status: str | None = None,
    cost_currency: str | None = None,
    cache_hit: bool | None = None,
    failover_triggered: bool | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    session: AsyncSession = Depends(session_dep),
):
    filters = _usage_filters(
        call_mode=call_mode,
        client_id=client_id,
        api_key_id=api_key_id,
        model_alias=model_alias,
        provider_id=provider_id,
        model_id=model_id,
        native_path=native_path,
        status_filter=status_filter,
        usage_status=usage_status,
        pricing_status=pricing_status,
        cost_currency=cost_currency,
        cache_hit=cache_hit,
        failover_triggered=failover_triggered,
        created_from=created_from,
        created_to=created_to,
    )
    rows = await UsageLogRepository(session).aggregate(
        filters=filters,
        group_by=group_by,
        limit=limit,
    )
    return {"items": rows, "total": len(rows)}


@router.get("/dashboard")
async def dashboard(session: AsyncSession = Depends(session_dep)):
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    total = await session.scalar(select(func.count()).select_from(UsageLog))
    success = await session.scalar(
        select(func.count()).select_from(UsageLog).where(UsageLog.status == "success")
    )
    tokens = await session.scalar(select(func.coalesce(func.sum(UsageLog.total_tokens), 0)))
    avg_latency = await session.scalar(select(func.avg(UsageLog.latency_ms)))
    errors = await session.scalar(
        select(func.count()).select_from(UsageLog).where(UsageLog.status != "success")
    )
    total_cost = await session.scalar(select(func.coalesce(func.sum(UsageLog.total_cost), 0)))
    cache_hits = await session.scalar(
        select(func.count()).select_from(UsageLog).where(UsageLog.cache_hit.is_(True))
    )
    failovers = await session.scalar(
        select(func.count()).select_from(UsageLog).where(UsageLog.failover_triggered.is_(True))
    )
    stream_calls = await session.scalar(
        select(func.count()).select_from(UsageLog).where(UsageLog.stream.is_(True))
    )
    parsed_usage = await session.scalar(
        select(func.count())
        .select_from(UsageLog)
        .where(UsageLog.usage_status.in_(["parsed", "estimated"]))
    )
    missing_prices = await session.scalar(
        select(func.count())
        .select_from(UsageLog)
        .where(UsageLog.pricing_status == "missing_price_config")
    )
    total_cost_24h = await session.scalar(
        select(func.coalesce(func.sum(UsageLog.total_cost), 0)).where(
            UsageLog.created_at >= day_ago
        )
    )
    total_cost_7d = await session.scalar(
        select(func.coalesce(func.sum(UsageLog.total_cost), 0)).where(
            UsageLog.created_at >= week_ago
        )
    )
    return {
        "total_requests": total or 0,
        "success_rate": float((success or 0) / total) if total else 0,
        "error_rate": float((errors or 0) / total) if total else 0,
        "total_tokens": int(tokens or 0),
        "avg_latency_ms": float(avg_latency or 0),
        "error_count": int(errors or 0),
        "total_cost": float(total_cost or 0),
        "total_cost_24h": float(total_cost_24h or 0),
        "total_cost_7d": float(total_cost_7d or 0),
        "cache_hit_rate": float((cache_hits or 0) / total) if total else 0,
        "failover_count": int(failovers or 0),
        "failover_rate": float((failovers or 0) / total) if total else 0,
        "stream_count": int(stream_calls or 0),
        "usage_parsed_rate": float((parsed_usage or 0) / total) if total else 0,
        "missing_price_count": int(missing_prices or 0),
    }
