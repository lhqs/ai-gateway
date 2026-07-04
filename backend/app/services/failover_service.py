from dataclasses import dataclass

from app.core.errors import ProviderCallError
from app.db.models import RouteRule


@dataclass(slots=True)
class FailoverDecision:
    should_failover: bool
    reason: str | None = None


class FailoverService:
    def should_failover(self, error: ProviderCallError, rule: RouteRule, attempt_index: int) -> FailoverDecision:
        if not rule.failover_enabled:
            return FailoverDecision(False)
        if attempt_index >= max(rule.max_failover_attempts, 0):
            return FailoverDecision(False)
        if error.status_code and error.status_code in (rule.failover_on_status_codes or []):
            return FailoverDecision(True, f"status_code:{error.status_code}")
        if error.error_type in (rule.failover_on_error_types or []):
            return FailoverDecision(True, f"error_type:{error.error_type}")
        return FailoverDecision(False)
