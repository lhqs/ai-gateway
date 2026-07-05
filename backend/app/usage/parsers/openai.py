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
        prompt_details = usage.get("prompt_tokens_details")
        cached_input = 0
        if isinstance(prompt_details, dict):
            cached_input = int(prompt_details.get("cached_tokens") or 0)
        return NativeUsageResult(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            cached_input_tokens=cached_input,
            raw_usage=usage,
            usage_status="parsed",
        )
