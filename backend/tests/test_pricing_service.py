from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, Model, ModelPriceConfig, Provider, UsageLog
from app.services.usage_service import UsageService


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield factory
    finally:
        await engine.dispose()


async def seed_model_with_price(session, currency: str = "USD") -> Model:
    provider = Provider(
        name=f"provider-{currency.lower()}",
        provider_type="openai_compatible",
        base_url="https://example.test",
        status="active",
    )
    session.add(provider)
    await session.flush()
    model = Model(provider_id=provider.id, name=f"model-{currency.lower()}", status="active")
    session.add(model)
    await session.flush()
    session.add(
        ModelPriceConfig(
            provider_id=provider.id,
            model_id=model.id,
            model_name=model.name,
            currency_code=currency,
            unit_quantity=1_000_000,
            input_unit_price=Decimal("2.00"),
            cached_input_unit_price=Decimal("0.50"),
            output_unit_price=Decimal("8.00"),
            status="active",
        )
    )
    await session.flush()
    return model


@pytest.mark.asyncio
async def test_usage_service_calculates_cached_input_cost(session_factory):
    async with session_factory() as session:
        model = await seed_model_with_price(session)

        await UsageService(session).record(
            request_id="req-cost",
            client_id=1,
            model_alias="default-chat",
            provider_id=model.provider_id,
            model_id=model.id,
            final_model_id=model.id,
            stream=False,
            status="success",
            prompt_tokens=1000,
            cached_input_tokens=400,
            completion_tokens=200,
            total_tokens=1200,
            usage_status="parsed",
            cost_currency="USD",
        )

        log = await session.scalar(select(UsageLog).where(UsageLog.request_id == "req-cost"))

        assert log is not None
        assert log.billable_input_tokens == 600
        assert log.billable_output_tokens == 200
        assert log.pricing_status == "calculated"
        assert log.cost_currency == "USD"
        assert log.input_cost == Decimal("0.001200000000")
        assert log.cached_input_cost == Decimal("0.000200000000")
        assert log.output_cost == Decimal("0.001600000000")
        assert log.total_cost == Decimal("0.003000000000")
        assert log.estimated_cost == Decimal("0.00300000")


@pytest.mark.asyncio
async def test_usage_service_keeps_currencies_independent(session_factory):
    async with session_factory() as session:
        model = await seed_model_with_price(session, "CNY")

        await UsageService(session).record(
            request_id="req-cny",
            client_id=1,
            provider_id=model.provider_id,
            model_id=model.id,
            final_model_id=model.id,
            stream=False,
            status="success",
            prompt_tokens=1000,
            completion_tokens=0,
            total_tokens=1000,
            usage_status="parsed",
            cost_currency="USD",
        )

        log = await session.scalar(select(UsageLog).where(UsageLog.request_id == "req-cny"))

        assert log is not None
        assert log.pricing_status == "missing_price_config"
        assert log.cost_currency == "USD"
        assert log.total_cost is None


@pytest.mark.asyncio
async def test_usage_service_marks_gateway_cache_hit_not_billable(session_factory):
    async with session_factory() as session:
        model = await seed_model_with_price(session)

        await UsageService(session).record(
            request_id="req-cache-hit",
            client_id=1,
            provider_id=model.provider_id,
            model_id=model.id,
            final_model_id=model.id,
            stream=False,
            status="success",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            usage_status="parsed",
            cache_hit=True,
            cost_currency="USD",
        )

        log = await session.scalar(select(UsageLog).where(UsageLog.request_id == "req-cache-hit"))

        assert log is not None
        assert log.pricing_status == "not_billable"
        assert log.total_cost == Decimal("0E-12")
        assert log.estimated_cost == Decimal("0E-8")
