import json
import logging
import traceback
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_logging import _client_ip, _query_params, _request_context, get_request_id


logger = logging.getLogger("uvicorn.error")

EXPECTED_AUTH_401_DETAILS = {
    "API key expired",
    "Invalid API key",
    "Invalid credentials",
    "Invalid refresh token",
    "Invalid token",
    "Missing admin token",
    "Missing bearer token",
}


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, log_http_exception)
    app.add_exception_handler(RequestValidationError, log_request_validation_exception)
    app.add_exception_handler(Exception, log_unhandled_exception)


async def log_http_exception(request: Request, exc: StarletteHTTPException):
    status_code = int(exc.status_code)
    context = _exception_context(
        request,
        "HTTPException",
        status_code=status_code,
        detail=exc.detail,
    )
    is_expected_auth = (
        status_code == status.HTTP_401_UNAUTHORIZED and exc.detail in EXPECTED_AUTH_401_DETAILS
    )
    if status_code >= 500:
        log_method = logger.error
        log_kwargs = {"exc_info": True}
    elif is_expected_auth:
        log_method = logger.debug
        log_kwargs = {}
    else:
        log_method = logger.warning
        log_kwargs = {}
    log_method(
        "http_exception %s",
        json.dumps(context, ensure_ascii=False, default=str),
        **log_kwargs,
    )
    return await http_exception_handler(request, exc)


async def log_request_validation_exception(request: Request, exc: RequestValidationError):
    context = _exception_context(
        request,
        "RequestValidationError",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=exc.errors(),
    )
    logger.warning(
        "request_validation_exception %s",
        json.dumps(context, ensure_ascii=False, default=str),
    )
    return await request_validation_exception_handler(request, exc)


async def log_unhandled_exception(request: Request, exc: Exception):
    context = _exception_context(
        request,
        exc.__class__.__name__,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(exc),
    )
    context["stack_trace"] = "".join(traceback.format_exception(exc))
    logger.exception("unhandled_exception %s", json.dumps(context, ensure_ascii=False, default=str))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error"},
        headers={"x-request-id": get_request_id(request)},
    )


def _exception_context(
    request: Request,
    exception_type: str,
    *,
    status_code: int,
    detail: Any,
) -> dict[str, Any]:
    headers = request.headers
    auth_context = _request_context(request.scope, headers)
    return {
        "request_id": get_request_id(request),
        "exception_type": exception_type,
        "method": request.method,
        "path": request.url.path,
        "query_params": _query_params(request.scope),
        "status_code": status_code,
        "detail": detail,
        "client_ip": _client_ip(request.scope, headers),
        "auth_source": auth_context.get("auth_source"),
        "client_id": auth_context.get("client_id"),
        "api_key_id": auth_context.get("api_key_id"),
        "admin_user_id": auth_context.get("admin_user_id"),
    }
