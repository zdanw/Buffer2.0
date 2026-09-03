"""Provider HTTP request budget: reserve before every network call."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

import pytest
import requests

from bebcare.providers.google_gemini import GoogleGeminiImageProvider
from bebcare.services.asset_intelligence_policy import AnalysisFailure
from bebcare.services.gemini_native_multimodal import (
    PROTOCOL_GENERATE_CONTENT,
    gemini_generate_content,
    set_cached_native_protocol,
)
from bebcare.services.provider_request_budget import (
    KIND_IMAGE,
    KIND_QA,
    KIND_SEMANTIC,
    BudgetExhausted,
    active_provider_request_budget,
    clear_provider_request_budget,
    install_provider_request_budget,
    provider_request_context,
    reserved_provider_call,
)


def _ok(payload):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = payload
    resp.text = ""
    resp.status_code = 200
    return resp


def _http_error(status=404):
    resp = MagicMock()
    resp.status_code = status
    resp.text = "not found"
    err = requests.exceptions.HTTPError(response=resp)
    err.response = resp
    resp.raise_for_status.side_effect = err
    return resp


@pytest.fixture(autouse=True)
def _budget_isolation():
    clear_provider_request_budget()
    yield
    clear_provider_request_budget()


def test_each_http_request_reserves_before_post():
    install_provider_request_budget({KIND_QA: 1})
    provider = GoogleGeminiImageProvider(api_key="AIza-test", base_url="https://example.test/v1beta")
    posts = []

    def fake_post(*_a, **_k):
        posts.append("post")
        return _ok({"candidates": []})

    with provider_request_context(KIND_QA, reason="initial"):
        with patch("bebcare.providers.google_gemini.requests.post", side_effect=fake_post):
            provider.generate_content(model="gemini-test", body={"contents": []})
            with pytest.raises(BudgetExhausted):
                provider.generate_content(model="gemini-test", body={"contents": []})
    assert posts == ["post"]
    snap = active_provider_request_budget().snapshot()
    assert snap["attempted"][KIND_QA] == 1
    assert snap["blocked_by_budget"][KIND_QA] == 1
    assert snap["succeeded"][KIND_QA] == 1


def test_correction_consumes_separate_slot():
    budget = install_provider_request_budget({KIND_SEMANTIC: 2})
    reserved_provider_call(lambda: None, kind=KIND_SEMANTIC, reason="initial")
    reserved_provider_call(lambda: None, kind=KIND_SEMANTIC, reason="correction")
    with pytest.raises(BudgetExhausted):
        reserved_provider_call(lambda: None, kind=KIND_SEMANTIC, reason="correction")
    snap = budget.snapshot()
    assert snap["attempted"][KIND_SEMANTIC] == 2
    assert snap["corrected"][KIND_SEMANTIC] == 1
    assert snap["blocked_by_budget"][KIND_SEMANTIC] == 1


def test_retry_consumes_separate_slot():
    budget = install_provider_request_budget({KIND_IMAGE: 2})
    reserved_provider_call(lambda: None, kind=KIND_IMAGE, reason="initial")
    reserved_provider_call(lambda: None, kind=KIND_IMAGE, reason="retry")
    with pytest.raises(BudgetExhausted):
        reserved_provider_call(lambda: None, kind=KIND_IMAGE, reason="retry")
    snap = budget.snapshot()
    assert snap["retried"][KIND_IMAGE] == 1
    assert snap["attempted"][KIND_IMAGE] == 2


def test_protocol_fallback_consumes_separate_slot():
    install_provider_request_budget({KIND_QA: 2})
    provider = GoogleGeminiImageProvider(api_key="AIza-test", base_url="https://example.test/v1beta")
    posts = {"n": 0}

    def fake_post(url, *args, **kwargs):
        posts["n"] += 1
        if "generateContent" in str(url):
            return _http_error(404)
        return _ok({"output": [], "_text": "{}"})

    set_cached_native_protocol(None)
    with provider_request_context(KIND_QA, reason="initial"):
        with patch("bebcare.services.gemini_native_multimodal.assert_owner_gemini_vpn"):
            with patch(
                "bebcare.services.gemini_native_multimodal.load_owner_gemini_provider",
                return_value=provider,
            ):
                with patch("bebcare.providers.google_gemini.requests.post", side_effect=fake_post):
                    gemini_generate_content(
                        owner_user_id="owner-1",
                        model_id="gemini-test",
                        body={"input": [{"type": "text", "text": "x"}]},
                        protocol=PROTOCOL_GENERATE_CONTENT,
                    )
    snap = active_provider_request_budget().snapshot()
    assert posts["n"] == 2
    assert snap["attempted"][KIND_QA] == 2
    assert snap["retried"][KIND_QA] == 1
    assert snap["failed"][KIND_QA] == 1
    assert snap["succeeded"][KIND_QA] == 1
    set_cached_native_protocol(None)


def test_no_request_after_cap_exhaustion():
    install_provider_request_budget({KIND_IMAGE: 0})
    posts = []
    provider = GoogleGeminiImageProvider(api_key="AIza-test", base_url="https://example.test/v1beta")
    with patch("bebcare.providers.google_gemini.requests.post", side_effect=lambda *a, **k: posts.append(1)):
        with pytest.raises(BudgetExhausted):
            provider.generate(prompt="a cat", model="gemini-test")
    assert posts == []


def test_concurrent_calls_cannot_overspend():
    budget = install_provider_request_budget({KIND_QA: 5})

    def worker():
        try:
            reserved_provider_call(lambda: None, kind=KIND_QA)
            return "ok"
        except BudgetExhausted:
            return "blocked"

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = [fut.result() for fut in as_completed([pool.submit(worker) for _ in range(40)])]
    snap = budget.snapshot()
    assert snap["attempted"][KIND_QA] == 5
    assert results.count("ok") == 5
    assert results.count("blocked") == 35
    assert snap["blocked_by_budget"][KIND_QA] == 35


def test_budget_exhausted_is_analysis_failure():
    install_provider_request_budget({KIND_SEMANTIC: 0})
    with pytest.raises(AnalysisFailure) as exc:
        reserved_provider_call(lambda: None, kind=KIND_SEMANTIC)
    assert exc.value.error_category == "provider_budget_exhausted"
