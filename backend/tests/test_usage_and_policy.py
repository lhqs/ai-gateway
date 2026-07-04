from app.core.errors import ProviderCallError
from app.db.models import Provider, RouteRule
from app.providers.gemini_native import GeminiNativeProxyAdapter
from app.schemas.proxy import NativeProxyRequest
from app.services.cache_service import CacheService
from app.services.access_policy_service import AccessPolicyService
from app.services.failover_service import FailoverService
from app.usage.parsers.gemini import GeminiUsageParser


def test_gemini_usage_parser_extracts_metadata():
    result = GeminiUsageParser().parse(
        {
            "usageMetadata": {
                "promptTokenCount": 7,
                "candidatesTokenCount": 11,
                "totalTokenCount": 18,
            }
        }
    )

    assert result.usage_status == "parsed"
    assert result.prompt_tokens == 7
    assert result.completion_tokens == 11
    assert result.total_tokens == 18


def test_gemini_native_adapter_allows_whitelisted_paths_and_filters_headers():
    provider = Provider(
        name="gemini",
        provider_type="gemini",
        base_url="https://generativelanguage.googleapis.com",
        allowed_paths=["v1beta/models/*:generateContent"],
        blocked_headers=["x-secret"],
        protocol_modes=["native_proxy"],
    )
    adapter = GeminiNativeProxyAdapter()
    request = NativeProxyRequest(
        request_id="r1",
        method="POST",
        provider_name="gemini",
        native_path="v1beta/models/gemini-1.5-pro:generateContent",
        query_params=[],
        headers={"authorization": "Bearer internal", "x-secret": "1", "x-safe": "ok"},
        body=b"{}",
    )

    assert adapter._is_allowed_path(provider, request.native_path)
    headers = adapter._filtered_headers(provider, request.headers)
    assert "authorization" not in headers
    assert "x-secret" not in headers
    assert headers["x-safe"] == "ok"


def test_cache_key_is_stable_for_reordered_json_fields():
    service = CacheService(redis=None)
    first = service.build_request_hash(
        1,
        "default-chat",
        {"messages": [{"role": "user", "content": "hi"}], "temperature": 0.2, "top_p": 1},
    )
    second = service.build_request_hash(
        1,
        "default-chat",
        {"top_p": 1, "temperature": 0.2, "messages": [{"content": "hi", "role": "user"}]},
    )

    assert first == second
    assert service.build_cache_key(first).endswith(first)


def test_failover_service_honors_status_and_attempt_limit():
    rule = RouteRule(
        model_alias_id=1,
        primary_model_id=1,
        fallback_model_ids=[2, 3],
        failover_enabled=True,
        failover_on_status_codes=[429, 500],
        failover_on_error_types=["timeout"],
        max_failover_attempts=1,
    )
    service = FailoverService()

    first = service.should_failover(
        ProviderCallError("rate limited", status_code=429, error_type="rate_limit"), rule, 0
    )
    second = service.should_failover(
        ProviderCallError("rate limited", status_code=429, error_type="rate_limit"), rule, 1
    )

    assert first.should_failover
    assert first.reason == "status_code:429"
    assert not second.should_failover


def test_access_policy_denies_unlisted_native_path():
    from app.core.security import AuthContext
    from app.db.models import ApiKey, Client
    from fastapi import HTTPException

    auth = AuthContext(
        client=Client(id=1, name="c", status="active", access_config={"provider_names": ["gemini"]}),
        api_key=ApiKey(
            id=1,
            client_id=1,
            name="k",
            key_prefix="p",
            key_hash="h",
            status="active",
            access_config={"native_paths": ["v1beta/models/*:generateContent"]},
        ),
    )
    provider = Provider(id=1, name="gemini", provider_type="gemini", base_url="https://example.test")

    AccessPolicyService().ensure_native_allowed(auth, provider, "v1beta/models/gemini:generateContent")
    try:
        AccessPolicyService().ensure_native_allowed(auth, provider, "v1beta/files")
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Expected HTTPException")
