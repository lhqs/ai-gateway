from typing import Any

from app.schemas.proxy import NativeUsageResult


class OpenAIUsageParser:
    def parse(self, payload: dict[str, Any] | None) -> NativeUsageResult:
        usage = (payload or {}).get("usage")
        if not isinstance(usage, dict):
            return NativeUsageResult(raw_usage=None, usage_status="unknown")
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        total = int(usage.get("total_tokens") or prompt + completion)
        return NativeUsageResult(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            raw_usage=usage,
            usage_status="parsed",
        )
