from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ProviderCallError
from app.db.models import Provider


HEALTH_FAILURE_STATUSES = {401, 403, 408, 429, 500, 502, 503, 504}
HEALTH_FAILURE_TYPES = {"timeout", "connection_error", "rate_limit"}


@dataclass(slots=True)
class ProviderHealthProbeResult:
    status: str
    status_code: int | None = None
    latency_ms: int | None = None
    probe_url: str | None = None
    error_summary: str | None = None
    checked_at: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "status_code": self.status_code,
            "latency_ms": self.latency_ms,
            "probe_url": self.probe_url,
            "error_summary": self.error_summary,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
        }


class ProviderHealthService:
    def __init__(self, session: AsyncSession | None) -> None:
        self.session = session

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)

    def is_available(self, provider: Provider) -> bool:
        if provider.status != "active":
            return False
        cooldown_until = provider.cooldown_until
        if cooldown_until and cooldown_until.tzinfo is None:
            cooldown_until = cooldown_until.replace(tzinfo=timezone.utc)
        if provider.health_status == "unhealthy" and cooldown_until:
            return cooldown_until <= self.now()
        return provider.health_status != "unhealthy"

    def unavailable_reason(self, provider: Provider) -> str:
        cooldown_until = provider.cooldown_until
        if provider.status != "active":
            return "provider_disabled"
        if provider.health_status == "unhealthy" and cooldown_until:
            return f"provider_cooling_down_until:{cooldown_until.isoformat()}"
        return f"provider_health_status:{provider.health_status}"

    async def record_success(self, provider: Provider, status_code: int | None = None) -> None:
        provider.health_status = "healthy"
        provider.failure_count = 0
        provider.last_success_at = self.now()
        provider.cooldown_until = None
        provider.last_health_error = None
        provider.last_health_status_code = status_code
        if self.session:
            await self.session.flush()

    async def record_failure(
        self,
        provider: Provider,
        *,
        error_summary: str,
        status_code: int | None = None,
    ) -> None:
        now = self.now()
        provider.failure_count = int(provider.failure_count or 0) + 1
        provider.last_failure_at = now
        provider.last_health_error = error_summary[:2000]
        provider.last_health_status_code = status_code
        if provider.failure_count >= max(int(provider.failure_threshold or 1), 1):
            provider.health_status = "unhealthy"
            provider.cooldown_until = now + timedelta(
                seconds=max(int(provider.cooldown_seconds or 0), 0)
            )
        else:
            provider.health_status = "degraded"
        if self.session:
            await self.session.flush()

    async def record_call_success(self, provider: Provider) -> None:
        if provider.health_status != "healthy" or provider.failure_count:
            await self.record_success(provider)

    async def record_call_failure(self, provider: Provider, error: ProviderCallError) -> None:
        if not self.is_health_failure(error):
            return
        await self.record_failure(
            provider,
            error_summary=error.message or error.error_type,
            status_code=error.status_code,
        )

    @staticmethod
    def is_health_failure(error: ProviderCallError) -> bool:
        if error.error_type in HEALTH_FAILURE_TYPES:
            return True
        if error.status_code in HEALTH_FAILURE_STATUSES:
            return True
        return bool(error.status_code and error.status_code >= 500)

    async def record_response_status(
        self, provider: Provider, status_code: int | None, error_summary: str | None = None
    ) -> None:
        if status_code is None:
            return
        if status_code < 400:
            await self.record_success(provider, status_code=status_code)
        elif status_code in HEALTH_FAILURE_STATUSES or status_code >= 500:
            await self.record_failure(
                provider,
                error_summary=error_summary or f"Provider returned HTTP {status_code}",
                status_code=status_code,
            )

    async def probe(self, provider: Provider) -> ProviderHealthProbeResult:
        checked_at = self.now()
        probe_url, params = self._probe_target(provider)
        if not probe_url:
            provider.health_status = "degraded"
            provider.last_health_error = "No health path configured"
            provider.last_health_status_code = None
            provider.last_failure_at = checked_at
            if self.session:
                await self.session.flush()
            return ProviderHealthProbeResult(
                status="degraded",
                error_summary="No health path configured",
                checked_at=checked_at,
            )

        started = checked_at.timestamp()
        try:
            timeout = min((provider.timeout_ms or 60000) / 1000, 10)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    probe_url,
                    params=params,
                    headers=self._headers(provider),
                )
            latency_ms = int((self.now().timestamp() - started) * 1000)
            status = self._status_from_code(response.status_code)
            if status == "healthy":
                await self.record_success(provider, status_code=response.status_code)
            else:
                await self.record_failure(
                    provider,
                    error_summary=f"Health probe returned HTTP {response.status_code}",
                    status_code=response.status_code,
                )
            return ProviderHealthProbeResult(
                status=status,
                status_code=response.status_code,
                latency_ms=latency_ms,
                probe_url=self._redacted_url(probe_url),
                error_summary=None if status == "healthy" else provider.last_health_error,
                checked_at=checked_at,
            )
        except httpx.TimeoutException as exc:
            return await self._probe_error(
                provider,
                checked_at,
                probe_url,
                "Health probe timed out",
                exc,
            )
        except httpx.HTTPError as exc:
            return await self._probe_error(provider, checked_at, probe_url, str(exc), exc)

    async def _probe_error(
        self,
        provider: Provider,
        checked_at: datetime,
        probe_url: str,
        message: str,
        exc: Exception,
    ) -> ProviderHealthProbeResult:
        await self.record_failure(provider, error_summary=message)
        return ProviderHealthProbeResult(
            status=provider.health_status,
            probe_url=self._redacted_url(probe_url),
            error_summary=str(exc)[:2000],
            checked_at=checked_at,
        )

    def _probe_target(self, provider: Provider) -> tuple[str | None, dict[str, str]]:
        health_path = (provider.config or {}).get("health_path")
        if not isinstance(health_path, str) or not health_path.strip():
            health_path = self._default_health_path(provider.provider_type)
        if not health_path:
            return None, {}

        base = provider.base_url.rstrip("/") + "/"
        if provider.base_url.rstrip("/").endswith("/v1") and health_path == "v1/models":
            health_path = "models"
        url = (
            health_path
            if health_path.startswith("http")
            else urljoin(base, health_path.lstrip("/"))
        )
        params: dict[str, str] = {}
        api_key = provider.encrypted_api_key or (provider.auth_config or {}).get("api_key")
        if provider.auth_type == "api_key_query" and api_key:
            params[str((provider.auth_config or {}).get("query_name", "key"))] = str(api_key)
        return url, params

    @staticmethod
    def _default_health_path(provider_type: str) -> str | None:
        if provider_type in {"openai_compatible", "claude"}:
            return "v1/models"
        if provider_type == "gemini":
            return "v1beta/models"
        return None

    @staticmethod
    def _status_from_code(status_code: int) -> str:
        if status_code < 400:
            return "healthy"
        if status_code < 500:
            return "degraded"
        return "unhealthy"

    def _headers(self, provider: Provider) -> dict[str, str]:
        headers = {"accept": "application/json"}
        api_key = provider.encrypted_api_key or (provider.auth_config or {}).get("api_key")
        if provider.auth_type == "bearer_token" and api_key:
            headers["authorization"] = f"Bearer {api_key}"
        elif provider.auth_type == "api_key_header" and api_key:
            header_name = str((provider.auth_config or {}).get("header", "Authorization"))
            prefix = (provider.auth_config or {}).get("prefix", "Bearer")
            headers[header_name] = f"{prefix} {api_key}" if prefix else str(api_key)
        headers.update((provider.config or {}).get("health_headers") or {})
        return headers

    @staticmethod
    def _redacted_url(url: str) -> str:
        return url.split("?", 1)[0]
