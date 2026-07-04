from app.providers.base import ChatProviderAdapter
from app.providers.gemini_native import GeminiNativeProxyAdapter
from app.providers.native_base import NativeProxyAdapter
from app.providers.openai_compatible import OpenAICompatibleAdapter


class ProviderRegistry:
    def __init__(self) -> None:
        self.chat_adapters: dict[str, ChatProviderAdapter] = {}
        self.native_adapters: dict[str, NativeProxyAdapter] = {}

    def register_chat(self, adapter: ChatProviderAdapter) -> None:
        self.chat_adapters[adapter.provider_type] = adapter

    def register_native(self, adapter: NativeProxyAdapter) -> None:
        self.native_adapters[adapter.provider_type] = adapter

    def get_chat(self, provider_type: str) -> ChatProviderAdapter:
        return self.chat_adapters[provider_type]

    def get_native(self, provider_type: str) -> NativeProxyAdapter:
        return self.native_adapters[provider_type]


registry = ProviderRegistry()
registry.register_chat(OpenAICompatibleAdapter())
registry.register_native(GeminiNativeProxyAdapter())
