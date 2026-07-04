from collections.abc import AsyncIterator

from app.core.errors import ProviderCallError
from app.db.models import Model, Provider
from app.providers.registry import registry
from app.schemas.chat import GatewayChatChunk, GatewayChatRequest, GatewayChatResponse


class ProviderService:
    async def chat_completion(
        self, provider: Provider, model: Model, request: GatewayChatRequest
    ) -> GatewayChatResponse:
        adapter = registry.get_chat(provider.provider_type)
        return await adapter.chat_completion(provider, model, request)

    async def stream_chat_completion(
        self, provider: Provider, model: Model, request: GatewayChatRequest
    ) -> AsyncIterator[GatewayChatChunk]:
        adapter = registry.get_chat(provider.provider_type)
        async for chunk in adapter.stream_chat_completion(provider, model, request):
            yield chunk

    def is_retryable(self, error: ProviderCallError) -> bool:
        return error.retryable
