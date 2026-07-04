from dataclasses import dataclass


@dataclass(slots=True)
class ProviderCallError(Exception):
    message: str
    status_code: int | None = None
    error_type: str = "provider_error"
    response_body: str | None = None
    response_headers: dict[str, str] | None = None
    retryable: bool = True

    def __str__(self) -> str:
        return self.message
