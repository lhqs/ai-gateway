from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.model_price_configs import ModelPriceConfigRepository


ZERO = Decimal("0")


class PricingService:
    def __init__(self, session: AsyncSession | None) -> None:
        self.session = session

    @staticmethod
    def normalize_currency(value: str | None) -> str | None:
        return value.upper() if value else None

    async def calculate_for_usage(self, data: dict[str, Any]) -> dict[str, Any]:
        prompt_tokens = int(data.get("prompt_tokens") or 0)
        completion_tokens = int(data.get("completion_tokens") or 0)
        cached_input_tokens = int(data.get("cached_input_tokens") or 0)
        billable_input_tokens = int(
            data.get("billable_input_tokens")
            if data.get("billable_input_tokens") is not None
            else max(prompt_tokens - cached_input_tokens, 0)
        )
        billable_output_tokens = int(
            data.get("billable_output_tokens")
            if data.get("billable_output_tokens") is not None
            else completion_tokens
        )
        base = {
            "cached_input_tokens": cached_input_tokens,
            "billable_input_tokens": billable_input_tokens,
            "billable_output_tokens": billable_output_tokens,
        }

        if data.get("cache_hit"):
            return {
                **base,
                "pricing_status": "not_billable",
                "estimated_cost": ZERO,
                "total_cost": ZERO,
                "cost_currency": self.normalize_currency(data.get("cost_currency")),
                "cost_breakdown": {"reason": "gateway_response_cache_hit", "total_cost": "0"},
            }

        has_usage = prompt_tokens > 0 or completion_tokens > 0 or cached_input_tokens > 0
        if data.get("status") != "success" and not has_usage:
            return {**base, "pricing_status": "not_billable"}
        if data.get("usage_status") not in {"parsed", "estimated"} and not has_usage:
            return {**base, "pricing_status": "usage_unknown"}
        if not self.session:
            return {**base, "pricing_status": "not_calculated"}

        model_id = data.get("final_model_id") or data.get("model_id")
        if not model_id:
            return {**base, "pricing_status": "missing_model_context"}

        currency = self.normalize_currency(data.get("cost_currency"))
        if not currency:
            return {**base, "pricing_status": "missing_currency"}

        at_time = data.get("created_at")
        if not isinstance(at_time, datetime):
            at_time = datetime.now(timezone.utc)

        config = await ModelPriceConfigRepository(self.session).get_active_for_model(
            int(model_id), currency, at_time
        )
        if not config:
            return {**base, "cost_currency": currency, "pricing_status": "missing_price_config"}

        unit_quantity = Decimal(config.unit_quantity)
        input_cost = self._line_cost(billable_input_tokens, config.input_unit_price, unit_quantity)
        cached_input_cost = self._line_cost(
            cached_input_tokens, config.cached_input_unit_price, unit_quantity
        )
        output_cost = self._line_cost(
            billable_output_tokens, config.output_unit_price, unit_quantity
        )
        total_cost = input_cost + cached_input_cost + output_cost
        breakdown = {
            "unit_type": config.unit_type,
            "unit_quantity": config.unit_quantity,
            "currency": config.currency_code,
            "items": [
                self._breakdown_item(
                    "input", billable_input_tokens, config.input_unit_price, input_cost
                ),
                self._breakdown_item(
                    "cached_input",
                    cached_input_tokens,
                    config.cached_input_unit_price,
                    cached_input_cost,
                ),
                self._breakdown_item(
                    "output", billable_output_tokens, config.output_unit_price, output_cost
                ),
            ],
        }
        return {
            **base,
            "pricing_status": "calculated",
            "pricing_config_id": config.id,
            "cost_currency": config.currency_code,
            "cost_unit_type": config.unit_type,
            "cost_unit_quantity": config.unit_quantity,
            "input_cost": input_cost,
            "cached_input_cost": cached_input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
            "estimated_cost": total_cost,
            "cost_breakdown": breakdown,
        }

    @staticmethod
    def _line_cost(quantity: int, unit_price: Decimal | None, unit_quantity: Decimal) -> Decimal:
        if quantity <= 0 or unit_price is None:
            return ZERO
        return Decimal(quantity) / unit_quantity * unit_price

    @staticmethod
    def _breakdown_item(
        name: str, quantity: int, unit_price: Decimal | None, cost: Decimal
    ) -> dict[str, Any]:
        return {
            "name": name,
            "quantity": quantity,
            "unit_price": str(unit_price) if unit_price is not None else None,
            "cost": str(cost),
        }
