import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ProviderCallError
from app.core.security import AuthContext
from app.db.models import Model, Provider
from app.policies.rate_limit import RateLimiter
from app.providers.registry import registry
from app.repositories.models import ModelRepository
from app.repositories.providers import ProviderRepository
from app.repositories.route_rules import RouteRuleRepository
from app.schemas.proxy import NativeProxyRequest
from app.services.access_policy_service import AccessPolicyService
from app.services.usage_service import UsageService


NATIVE_MODEL_PATH_PATTERN = re.compile(
    r"(?P<prefix>(?:^|/)models/)(?P<model>[^/:]+)(?P<suffix>(?::[^/]+)?(?:/.*)?)$"
)


@dataclass(slots=True)
class NativePathTarget:
    upstream_path: str
    model_alias: str | None = None
    model: Model | None = None


class NativeProxyService:
    def __init__(self, session: AsyncSession, redis: Redis | None) -> None:
        self.session = session
        self.redis = redis
        self.settings = get_settings()
        self.providers = ProviderRepository(session)
        self.route_rules = RouteRuleRepository(session)
        self.models = ModelRepository(session)
        self.usage = UsageService(session)
        self.rate_limiter = RateLimiter(redis)
        self.access_policy = AccessPolicyService()

    async def _build_request(
        self,
        request_id: str,
        provider_name: str,
        native_path: str,
        method: str,
        request: Request,
    ) -> NativeProxyRequest:
        body = await request.body()
        if len(body) > self.settings.request_body_limit_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Request body too large",
            )
        return NativeProxyRequest(
            request_id=request_id,
            method=method,  # type: ignore[arg-type]
            provider_name=provider_name,
            native_path=native_path,
            query_params=list(request.query_params.multi_items()),
            headers={k: v for k, v in request.headers.items()},
            body=body,
        )

    def _json_or_text(self, content: bytes, content_type: str | None) -> Any:
        if content_type and "json" in content_type:
            try:
                return json.loads(content.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return content.decode("utf-8", errors="replace")
        return content.decode("utf-8", errors="replace")[:20000]

    async def _resolve_native_model_alias(
        self, provider: Provider, native_path: str
    ) -> NativePathTarget:
        match = NATIVE_MODEL_PATH_PATTERN.search(native_path)
        if not match:
            return NativePathTarget(upstream_path=native_path)

        requested_model = match.group("model")
        found = await self.route_rules.get_for_alias(requested_model)
        if not found:
            return NativePathTarget(upstream_path=native_path)

        alias, rule = found
        model = await self.models.get_active(rule.primary_model_id)
        if not model or model.provider_id != provider.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model alias is unavailable for native provider",
            )

        upstream_path = (
            f"{native_path[:match.start('model')]}"
            f"{model.name}"
            f"{native_path[match.end('model'):]}"
        )
        return NativePathTarget(upstream_path=upstream_path, model_alias=alias.alias, model=model)

    async def forward(
        self,
        auth: AuthContext,
        request_id: str,
        provider_name: str,
        native_path: str,
        method: str,
        request: Request,
    ) -> Response:
        provider = await self.providers.get_active_by_name(provider_name)
        if not provider or "native_proxy" not in (provider.protocol_modes or []):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Native provider is unavailable",
            )
        started = time.perf_counter()
        path_target = NativePathTarget(upstream_path=native_path)
        try:
            self.access_policy.ensure_native_allowed(auth, provider, native_path)
            path_target = await self._resolve_native_model_alias(provider, native_path)
            if path_target.model_alias and path_target.model:
                self.access_policy.ensure_chat_allowed(
                    auth, path_target.model_alias, provider, path_target.model
                )
        except HTTPException as exc:
            await self.usage.record(
                request_id=request_id,
                client_id=auth.client.id,
                model_alias=path_target.model_alias,
                provider_id=provider.id,
                model_id=path_target.model.id if path_target.model else None,
                stream=False,
                status="failed",
                latency_ms=int((time.perf_counter() - started) * 1000),
                error_code="access_denied",
                error_message=str(exc.detail),
                call_mode="native_proxy",
                native_method=method,
                native_path=native_path,
                native_status_code=exc.status_code,
                usage_status="failed",
            )
            raise
        await self.rate_limiter.check(
            f"native-rate:{auth.client.id}:{provider.id}", provider.native_rate_limit_per_minute
        )
        native_request = await self._build_request(
            request_id, provider_name, path_target.upstream_path, method, request
        )
        adapter = registry.get_native(provider.provider_type)
        try:
            response = await adapter.forward(provider, native_request)
            content_type = response.headers.get("content-type")
            raw_response_body = self._json_or_text(response.body, content_type)
            await self.usage.record(
                request_id=request_id,
                client_id=auth.client.id,
                model_alias=path_target.model_alias,
                provider_id=provider.id,
                model_id=path_target.model.id if path_target.model else None,
                stream=False,
                status="success" if response.status_code < 400 else "failed",
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                latency_ms=int((time.perf_counter() - started) * 1000),
                call_mode="native_proxy",
                native_method=method,
                native_path=native_path,
                native_status_code=response.status_code,
                usage_status=response.usage.usage_status,
                raw_usage=response.usage.raw_usage,
                raw_request_body=self._json_or_text(
                    native_request.body, request.headers.get("content-type")
                )
                if native_request.body
                else None,
                raw_response_body=raw_response_body,
            )
            return Response(
                content=response.body,
                status_code=response.status_code,
                media_type=content_type,
                headers={k: v for k, v in response.headers.items() if k.lower() != "content-type"},
            )
        except ProviderCallError as exc:
            await self.usage.record(
                request_id=request_id,
                client_id=auth.client.id,
                model_alias=path_target.model_alias,
                provider_id=provider.id,
                model_id=path_target.model.id if path_target.model else None,
                stream=False,
                status="failed",
                latency_ms=int((time.perf_counter() - started) * 1000),
                error_code=exc.error_type,
                error_message=exc.message,
                call_mode="native_proxy",
                native_method=method,
                native_path=native_path,
                native_status_code=exc.status_code,
                usage_status="failed",
                raw_request_body=self._json_or_text(
                    native_request.body, request.headers.get("content-type")
                )
                if native_request.body
                else None,
                raw_response_body=exc.response_body,
            )
            if exc.response_body and exc.status_code:
                return Response(
                    content=exc.response_body,
                    status_code=exc.status_code,
                    headers=exc.response_headers or {},
                    media_type=(exc.response_headers or {}).get("content-type"),
                )
            raise HTTPException(status_code=exc.status_code or 502, detail=exc.message)

    async def stream(
        self,
        auth: AuthContext,
        request_id: str,
        provider_name: str,
        native_path: str,
        method: str,
        request: Request,
    ) -> StreamingResponse:
        provider = await self.providers.get_active_by_name(provider_name)
        if not provider or "native_proxy" not in (provider.protocol_modes or []):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Native provider is unavailable",
            )
        started = time.perf_counter()
        path_target = NativePathTarget(upstream_path=native_path)
        try:
            self.access_policy.ensure_native_allowed(auth, provider, native_path)
            path_target = await self._resolve_native_model_alias(provider, native_path)
            if path_target.model_alias and path_target.model:
                self.access_policy.ensure_chat_allowed(
                    auth, path_target.model_alias, provider, path_target.model
                )
        except HTTPException as exc:
            await self.usage.record(
                request_id=request_id,
                client_id=auth.client.id,
                model_alias=path_target.model_alias,
                provider_id=provider.id,
                model_id=path_target.model.id if path_target.model else None,
                stream=True,
                status="failed",
                latency_ms=int((time.perf_counter() - started) * 1000),
                error_code="access_denied",
                error_message=str(exc.detail),
                call_mode="native_proxy",
                native_method=method,
                native_path=native_path,
                native_status_code=exc.status_code,
                usage_status="failed",
            )
            raise
        await self.rate_limiter.check(
            f"native-rate:{auth.client.id}:{provider.id}", provider.native_rate_limit_per_minute
        )
        native_request = await self._build_request(
            request_id, provider_name, path_target.upstream_path, method, request
        )
        adapter = registry.get_native(provider.provider_type)

        async def iterator():
            chunks: list[str] = []
            usage = None
            stream_started = time.perf_counter()
            try:
                async with asyncio.timeout(self.settings.native_stream_max_seconds):
                    async for chunk in adapter.stream_forward(provider, native_request):
                        if (
                            time.perf_counter() - stream_started
                            > self.settings.native_stream_max_seconds
                        ):
                            raise ProviderCallError(
                                "Native provider stream exceeded maximum duration",
                                error_type="stream_timeout",
                                status_code=504,
                                retryable=False,
                            )
                        if chunk.usage:
                            usage = chunk.usage
                        data = chunk.data
                        if len("".join(chunks)) < 20000:
                            chunks.append(data.decode("utf-8", errors="replace"))
                        yield data
                await self.usage.record(
                    request_id=request_id,
                    client_id=auth.client.id,
                    model_alias=path_target.model_alias,
                    provider_id=provider.id,
                    model_id=path_target.model.id if path_target.model else None,
                    stream=True,
                    status="success",
                    prompt_tokens=usage.prompt_tokens if usage else 0,
                    completion_tokens=usage.completion_tokens if usage else 0,
                    total_tokens=usage.total_tokens if usage else 0,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    call_mode="native_proxy",
                    native_method=method,
                    native_path=native_path,
                    usage_status=usage.usage_status if usage else "unknown",
                    raw_usage=usage.raw_usage if usage else None,
                    raw_request_body=self._json_or_text(
                        native_request.body, request.headers.get("content-type")
                    )
                    if native_request.body
                    else None,
                    raw_response_body="".join(chunks),
                )
            except ProviderCallError as exc:
                await self.usage.record(
                    request_id=request_id,
                    client_id=auth.client.id,
                    model_alias=path_target.model_alias,
                    provider_id=provider.id,
                    model_id=path_target.model.id if path_target.model else None,
                    stream=True,
                    status="failed",
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    error_code=exc.error_type,
                    error_message=exc.message,
                    call_mode="native_proxy",
                    native_method=method,
                    native_path=native_path,
                    native_status_code=exc.status_code,
                    usage_status="failed",
                    raw_response_body=exc.response_body,
                )
                raise
            except TimeoutError:
                await self.usage.record(
                    request_id=request_id,
                    client_id=auth.client.id,
                    model_alias=path_target.model_alias,
                    provider_id=provider.id,
                    model_id=path_target.model.id if path_target.model else None,
                    stream=True,
                    status="failed",
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    error_code="stream_timeout",
                    error_message="Native provider stream exceeded maximum duration",
                    call_mode="native_proxy",
                    native_method=method,
                    native_path=native_path,
                    native_status_code=504,
                    usage_status="failed",
                    raw_response_body="".join(chunks),
                )
                raise

        return StreamingResponse(iterator(), media_type="text/event-stream")
