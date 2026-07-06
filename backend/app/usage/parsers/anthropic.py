from typing import Any

from app.schemas.proxy import NativeUsageResult


class AnthropicUsageParser:
    def parse(self, payload: dict[str, Any] | None) -> NativeUsageResult:
        if not payload:
            return NativeUsageResult(usage_status="unknown")

        usage = payload.get("usage") if "usage" in payload else payload
        if not isinstance(usage, dict):
            return NativeUsageResult(raw_usage=None, usage_status="unknown")

        input_tokens = int(usage.get("input_tokens") or 0)
        cache_creation_tokens = int(usage.get("cache_creation_input_tokens") or 0)
        cache_read_tokens = int(usage.get("cache_read_input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        prompt_tokens = input_tokens + cache_creation_tokens + cache_read_tokens

        return NativeUsageResult(
            prompt_tokens=prompt_tokens,
            completion_tokens=output_tokens,
            total_tokens=prompt_tokens + output_tokens,
            cached_input_tokens=cache_read_tokens,
            raw_usage=usage,
            usage_status="parsed",
        )
