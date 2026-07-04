from collections.abc import AsyncIterator
from typing import Protocol

from app.db.models import Model, Provider
from app.schemas.chat import GatewayChatChunk, GatewayChatRequest, GatewayChatResponse


class ChatProviderAdapter(Protocol):
    provider_type: str

    async def chat_completion(
        self, provider: Provider, model: Model, request: GatewayChatRequest
    ) -> GatewayChatResponse:
        ...

    async def stream_chat_completion(
        self, provider: Provider, model: Model, request: GatewayChatRequest
    ) -> AsyncIterator[GatewayChatChunk]:
        ...
