from typing import Any, Protocol

from app.schemas.proxy import NativeUsageResult


class UsageParser(Protocol):
    def parse(self, payload: dict[str, Any] | None) -> NativeUsageResult:
        ...


class NoopUsageParser:
    def parse(self, payload: dict[str, Any] | None) -> NativeUsageResult:
        return NativeUsageResult(raw_usage=payload, usage_status="unknown")
