import json
import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.request_logging import RequestLoggingMiddleware


def _logged_request(caplog) -> dict:
    for record in reversed(caplog.records):
        if record.name == "uvicorn.error" and record.message.startswith("http_request "):
            return json.loads(record.message.removeprefix("http_request "))
    raise AssertionError("request log was not emitted")


def test_request_logging_records_context_and_redacts_body(caplog):
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.post("/items")
    async def create_item(request: Request, payload: dict):
        request.state.request_auth_source = "api_key"
        request.state.request_client_id = 11
        request.state.request_api_key_id = 22
        return {"ok": True, "request_id": request.state.request_id, "payload": payload}

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        response = TestClient(app).post(
            "/items?tag=a&tag=b&token=hidden",
            headers={"x-request-id": "req-test"},
            json={"name": "demo", "password": "secret", "nested": {"api_key": "key"}},
        )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-test"
    log_data = _logged_request(caplog)
    assert log_data["request_id"] == "req-test"
    assert log_data["query_params"] == {"tag": ["a", "b"], "token": "***"}
    assert log_data["body"] == {"name": "demo", "password": "***", "nested": {"api_key": "***"}}
    assert log_data["auth_source"] == "api_key"
    assert log_data["client_id"] == 11
    assert log_data["api_key_id"] == 22
    assert isinstance(log_data["duration_ms"], float)


def test_request_logging_reads_admin_user_from_bearer_token(caplog):
    settings = get_settings()
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/admin")
    async def admin_route():
        return {"ok": True}

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "7",
            "type": "access",
            "token_version": 1,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        response = TestClient(app).get("/admin", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    log_data = _logged_request(caplog)
    assert log_data["auth_source"] == "admin"
    assert log_data["admin_user_id"] == 7


def test_request_logging_omits_configured_body_keys_and_truncates_long_strings(caplog, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "request_logging_body_max_bytes", 20000)
    monkeypatch.setattr(settings, "request_logging_long_value_max_chars", 12)

    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.post("/chat")
    async def chat(payload: dict):
        return {"ok": True, "payload": payload}

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        response = TestClient(app).post(
            "/chat",
            json={"messages": [{"content": "x" * 100}], "note": "abcdefghijklmnop"},
        )

    assert response.status_code == 200
    log_data = _logged_request(caplog)
    assert log_data["body"]["messages"] == "<omitted: list_items=1>"
    assert log_data["body"]["note"] == "abcdefghijkl...<truncated length=16>"


def test_request_logging_skips_multipart_body(caplog):
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.post("/upload")
    async def upload():
        return {"ok": True}

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        response = TestClient(app).post(
            "/upload",
            files={"file": ("sample.txt", b"content", "text/plain")},
        )

    assert response.status_code == 200
    log_data = _logged_request(caplog)
    assert log_data["body"] is None
    assert log_data["body_skipped"] is True
    assert log_data["body_skip_reason"] == "content_type"
