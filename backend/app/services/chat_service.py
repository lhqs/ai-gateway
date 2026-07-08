import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ProviderCallError
from app.core.security import AuthContext
from app.db.models import Model, Provider
from app.repositories.cache_entries import CacheEntryRepository
from app.schemas.chat import ChatCompletionRequest, GatewayChatRequest, GatewayChatResponse
from app.services.cache_service import CacheService
from app.services.access_policy_service import AccessPolicyService
from app.services.failover_service import FailoverService
from app.services.provider_health_service import ProviderHealthService
from app.services.provider_service import ProviderService
from app.services.routing_service import RoutingService
from app.services.usage_service import UsageService


class ChatService:
    def __init__(self, session: AsyncSession, cache: CacheService) -> None:
        self.session = session
        self.cache = cache
        self.routing = RoutingService(session)
        self.provider_service = ProviderService()
        self.failover = FailoverService()
        self.health = ProviderHealthService(session)
        self.usage = UsageService(session)
        self.access_policy = AccessPolicyService()
        self.settings = get_settings()

    def _cost_currency(self, auth: AuthContext) -> str:
        api_key_currency = (auth.api_key.access_config or {}).get("cost_currency")
        client_currency = (auth.client.access_config or {}).get("cost_currency")
        return str(api_key_currency or client_currency or self.settings.default_cost_currency).upper()

    async def _record_usage(self, auth: AuthContext, **data: Any) -> None:
        data.setdefault("api_key_id", auth.api_key.id)
        data.setdefault("cost_currency", self._cost_currency(auth))
        await self.usage.record(**data)

    async def _build_attempts(
        self, auth: AuthContext, payload: ChatCompletionRequest, route
    ) -> tuple[list[tuple[Model, Provider]], list[str]]:
        candidates: list[tuple[Model, Provider]] = [(route.model, route.provider)]
        for fallback_id in route.rule.fallback_model_ids or []:
            if len(candidates) >= max(route.rule.max_failover_attempts + 1, 1):
                break
            fallback_model, fallback_provider = await self.routing.resolve_model(int(fallback_id))
            candidates.append((fallback_model, fallback_provider))

        attempts: list[tuple[Model, Provider]] = []
        skipped: list[str] = []
        for model, provider in candidates:
            self.access_policy.ensure_chat_allowed(auth, payload.model, provider, model)
            if self.health.is_available(provider):
                attempts.append((model, provider))
            else:
                skipped.append(f"{provider.name}:{self.health.unavailable_reason(provider)}")
        return attempts, skipped

    async def complete(
        self, auth: AuthContext, request_id: str, payload: ChatCompletionRequest
    ) -> dict[str, Any]:
        started = time.perf_counter()
        route = await self.routing.resolve(payload.model)
        self.access_policy.ensure_chat_allowed(auth, payload.model, route.provider, route.model)
        body = payload.model_dump(exclude_none=True)
        cache_key = None
        request_hash = None
        if route.rule.cache_enabled and not payload.stream:
            request_hash = self.cache.build_request_hash(auth.client.id, payload.model, body)
            cache_key = self.cache.build_cache_key(request_hash)
            cached = await self.cache.get_json(cache_key)
            if cached:
                await self._record_usage(
                    auth,
                    request_id=request_id,
                    client_id=auth.client.id,
                    model_alias=payload.model,
                    provider_id=cached.get("provider_id"),
                    model_id=cached.get("model_id"),
                    stream=False,
                    status="success",
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    call_mode="unified_chat",
                    usage_status="parsed",
                    raw_usage=cached.get("raw_usage"),
                    prompt_content={"messages": [m.model_dump() for m in payload.messages]},
                    completion_content=cached.get("completion_content"),
                    cache_hit=True,
                    cache_key=cache_key,
                    final_provider_id=cached.get("provider_id"),
                    final_model_id=cached.get("model_id"),
                )
                return cached["body"]

        attempts, skipped = await self._build_attempts(auth, payload, route)
        if not attempts:
            failure_reason = "; ".join(skipped) or "no_available_provider"
            await self._record_usage(
                auth,
                request_id=request_id,
                client_id=auth.client.id,
                model_alias=payload.model,
                provider_id=route.provider.id,
                model_id=route.model.id,
                stream=False,
                status="failed",
                latency_ms=int((time.perf_counter() - started) * 1000),
                error_code="provider_unavailable",
                error_message="No healthy provider is available for this route",
                call_mode="unified_chat",
                usage_status="failed",
                prompt_content={"messages": [m.model_dump() for m in payload.messages]},
                failover_triggered=bool(skipped),
                initial_provider_id=route.provider.id,
                initial_model_id=route.model.id,
                final_provider_id=route.provider.id,
                final_model_id=route.model.id,
                failure_reason=failure_reason,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No healthy provider is available for this route",
            )

        last_error: ProviderCallError | None = None
        failure_reason = None
        for attempt_index, (model, provider) in enumerate(attempts):
            gw_request = GatewayChatRequest(
                request_id=request_id,
                model_alias=payload.model,
                provider_model=model.name,
                messages=payload.messages,
                stream=False,
                body=body,
            )
            try:
                response = await self.provider_service.chat_completion(provider, model, gw_request)
                latency_ms = int((time.perf_counter() - started) * 1000)
                await self.health.record_call_success(provider)
                failover_triggered = attempt_index > 0 or bool(skipped)
                await self._record_usage(
                    auth,
                    request_id=request_id,
                    client_id=auth.client.id,
                    model_alias=payload.model,
                    provider_id=provider.id,
                    model_id=model.id,
                    stream=False,
                    status="success",
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    total_tokens=response.total_tokens,
                    cached_input_tokens=response.cached_input_tokens,
                    latency_ms=latency_ms,
                    call_mode="unified_chat",
                    usage_status=response.usage_status,
                    raw_usage=response.raw_usage,
                    prompt_content={"messages": [m.model_dump() for m in payload.messages]},
                    completion_content=response.body,
                    cache_hit=False,
                    cache_key=cache_key,
                    failover_triggered=failover_triggered,
                    failover_attempts=attempt_index + len(skipped),
                    initial_provider_id=route.provider.id,
                    initial_model_id=route.model.id,
                    final_provider_id=provider.id,
                    final_model_id=model.id,
                    failure_reason=failure_reason,
                )
                if cache_key and request_hash:
                    cache_written = await self.cache.set_json(
                        cache_key,
                        {
                            "body": response.body,
                            "provider_id": provider.id,
                            "model_id": model.id,
                            "raw_usage": response.raw_usage,
                            "completion_content": response.body,
                        },
                        route.rule.cache_ttl_seconds,
                    )
                    if cache_written and self.session:
                        await CacheEntryRepository(self.session).upsert_metadata(
                            cache_key=cache_key,
                            client_id=auth.client.id,
                            model_alias=payload.model,
                            request_hash=request_hash,
                            response_body=response.body,
                            prompt_tokens=response.prompt_tokens,
                            completion_tokens=response.completion_tokens,
                            total_tokens=response.total_tokens,
                            expires_at=datetime.now(timezone.utc)
                            + timedelta(seconds=route.rule.cache_ttl_seconds),
                        )
                return response.body
            except ProviderCallError as exc:
                last_error = exc
                await self.health.record_call_failure(provider, exc)
                decision = self.failover.should_failover(exc, route.rule, attempt_index)
                failure_reason = decision.reason or exc.error_type
                await self._record_usage(
                    auth,
                    request_id=request_id,
                    client_id=auth.client.id,
                    model_alias=payload.model,
                    provider_id=provider.id,
                    model_id=model.id,
                    stream=False,
                    status="failed",
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    error_code=exc.error_type,
                    error_message=exc.message,
                    call_mode="unified_chat",
                    usage_status="failed",
                    prompt_content={"messages": [m.model_dump() for m in payload.messages]},
                    raw_response_body=exc.response_body,
                    cache_hit=False,
                    cache_key=cache_key,
                    failover_triggered=decision.should_failover,
                    failover_attempts=attempt_index + len(skipped),
                    initial_provider_id=route.provider.id,
                    initial_model_id=route.model.id,
                    final_provider_id=provider.id,
                    final_model_id=model.id,
                    failure_reason=failure_reason,
                )
                if not decision.should_failover:
                    break

        if last_error and last_error.status_code:
            raise HTTPException(status_code=last_error.status_code, detail=last_error.message)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=last_error.message if last_error else "Provider request failed",
        )

    async def complete_stream(
        self, auth: AuthContext, request_id: str, payload: ChatCompletionRequest
    ):
        route = await self.routing.resolve(payload.model)
        self.access_policy.ensure_chat_allowed(auth, payload.model, route.provider, route.model)
        body = payload.model_dump(exclude_none=True)
        body["stream"] = True
        started = time.perf_counter()
        first_token_ms: int | None = None
        attempts, skipped = await self._build_attempts(auth, payload, route)
        if not attempts:
            failure_reason = "; ".join(skipped) or "no_available_provider"
            await self._record_usage(
                auth,
                request_id=request_id,
                client_id=auth.client.id,
                model_alias=payload.model,
                provider_id=route.provider.id,
                model_id=route.model.id,
                stream=True,
                status="failed",
                latency_ms=int((time.perf_counter() - started) * 1000),
                error_code="provider_unavailable",
                error_message="No healthy provider is available for this route",
                call_mode="unified_chat",
                usage_status="failed",
                prompt_content={"messages": [m.model_dump() for m in payload.messages]},
                failover_triggered=bool(skipped),
                initial_provider_id=route.provider.id,
                initial_model_id=route.model.id,
                final_provider_id=route.provider.id,
                final_model_id=route.model.id,
                failure_reason=failure_reason,
            )
            raise ProviderCallError(
                "No healthy provider is available for this route",
                error_type="provider_unavailable",
                status_code=503,
                retryable=False,
            )
        last_error: ProviderCallError | None = None
        emitted = False
        failure_reason = None
        for attempt_index, (model, provider) in enumerate(attempts):
            completion_parts: list[str] = []
            raw_usage: dict[str, Any] | None = None
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            cached_input_tokens = 0
            usage_status = "unknown"
            gw_request = GatewayChatRequest(
                request_id=request_id,
                model_alias=payload.model,
                provider_model=model.name,
                messages=payload.messages,
                stream=True,
                body=body,
            )
            try:
                async for chunk in self.provider_service.stream_chat_completion(provider, model, gw_request):
                    emitted = True
                    if chunk.first_token and first_token_ms is None:
                        first_token_ms = int((time.perf_counter() - started) * 1000)
                    if chunk.completion_delta and len("".join(completion_parts)) < 20000:
                        completion_parts.append(chunk.completion_delta)
                    if chunk.usage_status == "parsed":
                        prompt_tokens = chunk.prompt_tokens
                        completion_tokens = chunk.completion_tokens
                        total_tokens = chunk.total_tokens
                        cached_input_tokens = chunk.cached_input_tokens
                        raw_usage = chunk.raw_usage
                        usage_status = chunk.usage_status
                    yield chunk.data
                await self._record_usage(
                    auth,
                    request_id=request_id,
                    client_id=auth.client.id,
                    model_alias=payload.model,
                    provider_id=provider.id,
                    model_id=model.id,
                    stream=True,
                    status="success",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cached_input_tokens=cached_input_tokens,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    first_token_latency_ms=first_token_ms,
                    call_mode="unified_chat",
                    usage_status=usage_status,
                    raw_usage=raw_usage,
                    prompt_content={"messages": [m.model_dump() for m in payload.messages]},
                    completion_content={"content": "".join(completion_parts)} if completion_parts else None,
                    failover_triggered=attempt_index > 0 or bool(skipped),
                    failover_attempts=attempt_index + len(skipped),
                    initial_provider_id=route.provider.id,
                    initial_model_id=route.model.id,
                    final_provider_id=provider.id,
                    final_model_id=model.id,
                    failure_reason=failure_reason,
                )
                await self.health.record_call_success(provider)
                return
            except ProviderCallError as exc:
                last_error = exc
                await self.health.record_call_failure(provider, exc)
                decision = self.failover.should_failover(exc, route.rule, attempt_index)
                failure_reason = decision.reason or exc.error_type
                await self._record_usage(
                    auth,
                    request_id=request_id,
                    client_id=auth.client.id,
                    model_alias=payload.model,
                    provider_id=provider.id,
                    model_id=model.id,
                    stream=True,
                    status="failed",
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    first_token_latency_ms=first_token_ms,
                    error_code=exc.error_type,
                    error_message=exc.message,
                    call_mode="unified_chat",
                    usage_status="failed",
                    raw_response_body=exc.response_body,
                    prompt_content={"messages": [m.model_dump() for m in payload.messages]},
                    failover_triggered=decision.should_failover and not emitted,
                    failover_attempts=attempt_index + len(skipped),
                    initial_provider_id=route.provider.id,
                    initial_model_id=route.model.id,
                    final_provider_id=provider.id,
                    final_model_id=model.id,
                    failure_reason=failure_reason,
                )
                if emitted or not decision.should_failover:
                    raise
                continue
        if last_error:
            raise last_error
