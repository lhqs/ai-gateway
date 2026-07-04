from typing import Any

from app.schemas.proxy import NativeUsageResult


class GeminiUsageParser:
    def parse(self, payload: dict[str, Any] | None) -> NativeUsageResult:
        if not payload:
            return NativeUsageResult(usage_status="unknown")
        usage = payload.get("usageMetadata")
        if not isinstance(usage, dict):
            return NativeUsageResult(raw_usage=None, usage_status="unknown")
        prompt = int(usage.get("promptTokenCount") or 0)
        completion = int(usage.get("candidatesTokenCount") or 0)
        total = int(usage.get("totalTokenCount") or prompt + completion)
        return NativeUsageResult(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            raw_usage=usage,
            usage_status="parsed",
        )
