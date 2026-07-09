import json
import logging

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.exception_handlers import register_exception_handlers
from app.core.request_logging import RequestLoggingMiddleware


def _logged_event(caplog, prefix: str) -> dict:
    for record in reversed(caplog.records):
        if record.name == "uvicorn.error" and record.message.startswith(prefix):
            return json.loads(record.message.removeprefix(prefix))
    raise AssertionError(f"{prefix.strip()} log was not emitted")


def test_http_exception_is_logged_with_request_context(caplog):
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom():
        raise HTTPException(status_code=404, detail="missing")

    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        response = TestClient(app).get("/boom?x=1", headers={"x-request-id": "req-404"})

    assert response.status_code == 404
    assert response.headers["x-request-id"] == "req-404"
    log_data = _logged_event(caplog, "http_exception ")
    assert log_data["request_id"] == "req-404"
    assert log_data["exception_type"] == "HTTPException"
    assert log_data["path"] == "/boom"
    assert log_data["query_params"] == {"x": "1"}
    assert log_data["status_code"] == 404
    assert log_data["detail"] == "missing"


def test_expected_auth_challenge_is_debug_only(caplog):
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/private")
    async def private():
        raise HTTPException(status_code=401, detail="Missing bearer token")

    with caplog.at_level(logging.DEBUG, logger="uvicorn.error"):
        response = TestClient(app).get("/private")

    assert response.status_code == 401
    records = [
        record
        for record in caplog.records
        if record.name == "uvicorn.error" and record.message.startswith("http_exception ")
    ]
    assert len(records) == 1
    assert records[0].levelno == logging.DEBUG
    assert records[0].exc_info is None


def test_validation_exception_is_logged(caplog):
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/items/{item_id}")
    async def get_item(item_id: int):
        return {"item_id": item_id}

    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        response = TestClient(app).get("/items/not-an-int")

    assert response.status_code == 422
    log_data = _logged_event(caplog, "request_validation_exception ")
    assert log_data["exception_type"] == "RequestValidationError"
    assert log_data["path"] == "/items/not-an-int"
    assert log_data["status_code"] == 422


def test_unhandled_exception_is_logged_with_traceback(caplog):
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    register_exception_handlers(app)

    @app.get("/crash")
    async def crash():
        raise RuntimeError("unexpected")

    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        response = TestClient(app, raise_server_exceptions=False).get(
            "/crash",
            headers={"x-request-id": "req-500"},
        )

    assert response.status_code == 500
    assert response.headers["x-request-id"] == "req-500"
    log_data = _logged_event(caplog, "unhandled_exception ")
    assert log_data["request_id"] == "req-500"
    assert log_data["exception_type"] == "RuntimeError"
    assert log_data["path"] == "/crash"
    assert log_data["detail"] == "unexpected"
    assert "RuntimeError: unexpected" in log_data["stack_trace"]
