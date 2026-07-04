from app.usage.parsers.base import NoopUsageParser, UsageParser
from app.usage.parsers.gemini import GeminiUsageParser
from app.usage.parsers.openai import OpenAIUsageParser


def get_usage_parser(parser_type: str) -> UsageParser:
    parsers: dict[str, UsageParser] = {
        "openai": OpenAIUsageParser(),
        "gemini": GeminiUsageParser(),
        "none": NoopUsageParser(),
    }
    return parsers.get(parser_type, NoopUsageParser())
