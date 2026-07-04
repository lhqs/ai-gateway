from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.api.v1 import chat, proxy
from app.api.v1.admin import resources
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    redis: Redis | None = None
    try:
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        await redis.ping()
    except Exception:
        redis = None
    app.state.redis = redis
    yield
    if redis:
        await redis.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(chat.router, prefix="/v1", tags=["chat"])
    app.include_router(proxy.router, prefix="/proxy", tags=["native-proxy"])
    app.include_router(resources.router, prefix="/admin", tags=["admin"])

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
