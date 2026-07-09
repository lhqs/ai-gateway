import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

import jwt
from jwt import InvalidTokenError
from starlette.datastructures import Headers, MutableHeaders, QueryParams
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings


logger = logging.getLogger("uvicorn.error")
LOG_TIMEZONE = ZoneInfo("Asia/Shanghai")

SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "encrypted_api_key",
    "key_hash",
    "key_value",
    "new_password",
    "password",
    "refresh_token",
    "secret",
    "token",
}
SKIPPED_BODY_CONTENT_TYPES = (
    "multipart/form-data",
    "application/octet-stream",
    "audio/",
    "image/",
    "video/",
)


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        settings = get_settings()
        if not _should_log(scope, settings.request_logging_excluded_paths):
            await self.app(scope, receive, send)
            return

        state = scope.setdefault("state", {})
        headers = Headers(scope=scope)
        request_id = _request_id(headers.get("x-request-id"))
        state["request_id"] = request_id

        started_at = time.perf_counter()
        status_code: int | None = None
        body_chunks: list[bytes] = []
        body_truncated = False
        captured_bytes = 0
        capture_body, body_skip_reason = _body_capture_policy(scope, headers)

        async def receive_wrapper() -> Message:
            nonlocal body_truncated, captured_bytes
            message = await receive()
            if capture_body and message["type"] == "http.request":
                chunk = message.get("body", b"")
                if chunk and captured_bytes < settings.request_logging_body_max_bytes:
                    remaining = settings.request_logging_body_max_bytes - captured_bytes
                    body_chunks.append(chunk[:remaining])
                    captured_bytes += min(len(chunk), remaining)
                    body_truncated = body_truncated or len(chunk) > remaining
                elif chunk:
                    body_truncated = True
            return message

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                MutableHeaders(scope=message)["x-request-id"] = request_id
            await send(message)

        error: str | None = None
        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        except Exception as exc:
            error = exc.__class__.__name__
            raise
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_data = _build_log_data(
                scope=scope,
                headers=headers,
                status_code=status_code,
                duration_ms=duration_ms,
                body=b"".join(body_chunks),
                body_truncated=body_truncated,
                body_skipped=not capture_body,
                body_skip_reason=body_skip_reason,
                error=error,
            )
            logger.info("http_request %s", json.dumps(log_data, ensure_ascii=False, default=str))


def get_request_id(scope_or_request: Any) -> str:
    scope = getattr(scope_or_request, "scope", scope_or_request)
    state = scope.setdefault("state", {})
    request_id = state.get("request_id")
    if isinstance(request_id, str) and request_id:
        return request_id
    request_id = uuid.uuid4().hex
    state["request_id"] = request_id
    return request_id


def _should_log(scope: Scope, excluded_paths: list[str]) -> bool:
    if scope["type"] != "http" or not get_settings().request_logging_enabled:
        return False
    path = str(scope.get("path") or "")
    return not any(
        path == excluded or path.startswith(f"{excluded}/") for excluded in excluded_paths
    )


def _body_capture_policy(scope: Scope, headers: Headers) -> tuple[bool, str | None]:
    settings = get_settings()
    path = str(scope.get("path") or "")
    excluded_paths = settings.request_logging_body_excluded_paths
    if any(path == excluded or path.startswith(f"{excluded}/") for excluded in excluded_paths):
        return False, "excluded_path"
    if settings.request_logging_body_max_bytes <= 0:
        return False, "disabled"
    content_type = headers.get("content-type", "").lower()
    if any(content_type.startswith(skipped) for skipped in SKIPPED_BODY_CONTENT_TYPES):
        return False, "content_type"
    return True, None


def _build_log_data(
    *,
    scope: Scope,
    headers: Headers,
    status_code: int | None,
    duration_ms: float,
    body: bytes,
    body_truncated: bool,
    body_skipped: bool,
    body_skip_reason: str | None,
    error: str | None,
) -> dict[str, Any]:
    settings = get_settings()
    content_type = headers.get("content-type", "")
    parsed_body = _parse_body(body, content_type, body_truncated) if body else None
    context = _request_context(scope, headers)
    log_data: dict[str, Any] = {
        "timestamp": datetime.now(LOG_TIMEZONE).isoformat(timespec="milliseconds"),
        "request_id": get_request_id(scope),
        "method": scope.get("method"),
        "path": scope.get("path"),
        "query_params": _sanitize(_query_params(scope)),
        "body": _sanitize(
            parsed_body,
            omit_keys=tuple(settings.request_logging_omit_body_keys),
            max_string_chars=settings.request_logging_long_value_max_chars,
        ),
        "body_truncated": body_truncated,
        "body_skipped": body_skipped,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "client_ip": _client_ip(scope, headers),
        "auth_source": context.get("auth_source"),
        "client_id": context.get("client_id"),
        "api_key_id": context.get("api_key_id"),
        "admin_user_id": context.get("admin_user_id"),
    }
    if body_skip_reason:
        log_data["body_skip_reason"] = body_skip_reason
    if error:
        log_data["error"] = error
    return log_data


def _query_params(scope: Scope) -> dict[str, Any]:
    params = QueryParams(scope.get("query_string", b""))
    result: dict[str, Any] = {}
    for key, value in params.multi_items():
        if key in result:
            current = result[key]
            if isinstance(current, list):
                current.append(value)
            else:
                result[key] = [current, value]
        else:
            result[key] = value
    return result


def _parse_body(body: bytes, content_type: str, body_truncated: bool = False) -> Any:
    if not body:
        return None
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return "<non-utf8-body>"

    content_type = content_type.lower()
    if content_type.startswith("application/json"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            if body_truncated:
                return f"<unparsed-truncated-json-body: captured_bytes={len(body)}>"
            return text
    if content_type.startswith("application/x-www-form-urlencoded"):
        parsed = parse_qs(text, keep_blank_values=True)
        return {key: values[0] if len(values) == 1 else values for key, values in parsed.items()}
    return text


def _sanitize(
    value: Any,
    *,
    omit_keys: tuple[str, ...] = (),
    max_string_chars: int | None = None,
) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            if any(sensitive in normalized_key for sensitive in SENSITIVE_KEYS):
                sanitized[key] = "***"
            elif any(omitted in normalized_key for omitted in omit_keys):
                sanitized[key] = _omitted_value(item)
            else:
                sanitized[key] = _sanitize(
                    item,
                    omit_keys=omit_keys,
                    max_string_chars=max_string_chars,
                )
        return sanitized
    if isinstance(value, list):
        return [
            _sanitize(item, omit_keys=omit_keys, max_string_chars=max_string_chars)
            for item in value
        ]
    if isinstance(value, str) and max_string_chars is not None:
        return _truncate_string(value, max_string_chars)
    return value


def _redact(value: Any) -> Any:
    return _sanitize(value)


def _truncate_string(value: str, max_chars: int) -> str:
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}...<truncated length={len(value)}>"


def _omitted_value(value: Any) -> str:
    if isinstance(value, str):
        return f"<omitted: length={len(value)}>"
    if isinstance(value, bytes):
        return f"<omitted: bytes={len(value)}>"
    if isinstance(value, list):
        return f"<omitted: list_items={len(value)}>"
    if isinstance(value, dict):
        return f"<omitted: object_keys={len(value)}>"
    return "<omitted>"


def _request_context(scope: Scope, headers: Headers) -> dict[str, Any]:
    state = scope.get("state") or {}
    context = {
        "auth_source": state.get("request_auth_source"),
        "client_id": state.get("request_client_id"),
        "api_key_id": state.get("request_api_key_id"),
        "admin_user_id": state.get("request_admin_user_id"),
    }
    if any(value is not None for value in context.values()):
        return context

    auth_header = headers.get("authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return context

    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError:
        context["auth_source"] = "bearer"
        return context

    if payload.get("type") == "access":
        context["auth_source"] = "admin"
        context["admin_user_id"] = _to_int(payload.get("sub"))
    return context


def _client_ip(scope: Scope, headers: Headers) -> str | None:
    forwarded_for = headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    real_ip = headers.get("x-real-ip")
    if real_ip:
        return real_ip
    client = scope.get("client")
    return client[0] if client else None


def _request_id(value: str | None) -> str:
    if not value:
        return uuid.uuid4().hex
    cleaned = value.strip()
    return cleaned[:64] if cleaned else uuid.uuid4().hex


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
