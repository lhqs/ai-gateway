from collections.abc import AsyncIterator
from typing import Protocol

from app.db.models import Provider
from app.schemas.proxy import NativeProxyChunk, NativeProxyRequest, NativeProxyResponse, NativeUsageResult


class NativeProxyAdapter(Protocol):
    provider_type: str

    async def forward(self, provider: Provider, request: NativeProxyRequest) -> NativeProxyResponse:
        ...

    async def stream_forward(self, provider: Provider, request: NativeProxyRequest) -> AsyncIterator[NativeProxyChunk]:
        ...

    async def parse_usage(self, provider: Provider, payload: dict | None) -> NativeUsageResult:
        ...
