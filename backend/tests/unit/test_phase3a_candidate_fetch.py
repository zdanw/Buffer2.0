"""Phase 3A dedicated candidate-fetch security tests. No live network."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import requests
from PIL import Image

from bebcare.services.quality_candidate_fetch import (
    OUTCOME_INVALID_URL,
    OUTCOME_PERMANENT,
    OUTCOME_RETRIEVED,
    OUTCOME_TEMPORARY,
    OUTCOME_TOO_LARGE,
    fetch_candidate_bytes,
)


def _png() -> bytes:
    image = Image.new("RGB", (8, 8), (12, 80, 160))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _public_addrinfo(*_args, **_kwargs):
    return [(2, 1, 6, "", ("1.1.1.1", 443))]


def _private_addrinfo(*_args, **_kwargs):
    return [(2, 1, 6, "", ("10.0.0.1", 443))]


def _response(*, status=200, headers=None, chunks=None, content=None):
    resp = MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    payload = content if content is not None else b""
    resp.iter_content.return_value = chunks if chunks is not None else [payload]
    resp.close = MagicMock()
    return resp


def test_https_valid_url_retrieved():
    raw = _png()
    with patch("bebcare.services.quality_candidate_fetch.socket.getaddrinfo", _public_addrinfo), patch(
        "bebcare.services.quality_candidate_fetch.requests.get", return_value=_response(content=raw)
    ):
        result = fetch_candidate_bytes("https://cdn.example/test.png")
    assert result.outcome == OUTCOME_RETRIEVED
    assert result.content == raw
    assert "cdn.example" in (result.details.get("host") or "")


def test_http_rejected():
    result = fetch_candidate_bytes("http://cdn.example/test.png")
    assert result.outcome == OUTCOME_INVALID_URL
    assert result.details["reason"] == "http_not_allowed"


def test_loopback_rejected():
    result = fetch_candidate_bytes("https://127.0.0.1/secret.png")
    assert result.outcome == OUTCOME_INVALID_URL
    assert result.details["kind"] == "loopback"


def test_private_ipv4_rejected():
    result = fetch_candidate_bytes("https://10.1.2.3/img.png")
    assert result.outcome == OUTCOME_INVALID_URL


def test_link_local_rejected():
    result = fetch_candidate_bytes("https://169.254.10.20/img.png")
    assert result.outcome == OUTCOME_INVALID_URL
    assert result.details["kind"] == "link_local"


def test_private_ipv6_rejected():
    result = fetch_candidate_bytes("https://[fd12:3456:789a:1::1]/img.png")
    assert result.outcome == OUTCOME_INVALID_URL


def test_redirect_to_private_target_rejected():
    resp = _response(status=302, headers={"Location": "https://127.0.0.1/steal"})
    with patch("bebcare.services.quality_candidate_fetch.socket.getaddrinfo", _public_addrinfo), patch(
        "bebcare.services.quality_candidate_fetch.requests.get", return_value=resp
    ):
        result = fetch_candidate_bytes("https://cdn.example/go")
    assert result.outcome == OUTCOME_INVALID_URL
    assert result.details.get("redirect") is True


def test_oversized_content_length():
    with patch("bebcare.services.quality_candidate_fetch.MAX_RESPONSE_BYTES", 1024):
        resp = _response(status=200, headers={"Content-Length": "2048"}, chunks=[])
        with patch("bebcare.services.quality_candidate_fetch.socket.getaddrinfo", _public_addrinfo), patch(
            "bebcare.services.quality_candidate_fetch.requests.get", return_value=resp
        ):
            from bebcare.services import quality_candidate_fetch as fetch_mod

            result = fetch_mod.fetch_candidate_bytes("https://cdn.example/big.png")
        assert result.outcome == OUTCOME_TOO_LARGE
        assert result.details["reason"] == "content_length_exceeds_limit"
        resp.iter_content.assert_not_called()


def test_oversized_streamed_response():
    with patch("bebcare.services.quality_candidate_fetch.MAX_RESPONSE_BYTES", 100):
        resp = _response(status=200, headers={}, chunks=[b"x" * 80, b"y" * 80])
        with patch("bebcare.services.quality_candidate_fetch.socket.getaddrinfo", _public_addrinfo), patch(
            "bebcare.services.quality_candidate_fetch.requests.get", return_value=resp
        ):
            from bebcare.services import quality_candidate_fetch as fetch_mod

            result = fetch_mod.fetch_candidate_bytes("https://cdn.example/stream.png")
        assert result.outcome == OUTCOME_TOO_LARGE
        assert result.details["reason"] == "streamed_response_too_large"


def test_bounded_valid_data_url():
    import base64

    raw = _png()
    url = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
    result = fetch_candidate_bytes(url)
    assert result.outcome == OUTCOME_RETRIEVED
    assert result.content == raw


def test_oversized_data_url():
    with patch("bebcare.services.quality_candidate_fetch.MAX_DATA_URL_CHARS", 40):
        from bebcare.services import quality_candidate_fetch as fetch_mod

        result = fetch_mod.fetch_candidate_bytes("data:image/png;base64," + ("A" * 80))
    assert result.outcome == OUTCOME_TOO_LARGE


def test_timeout_is_temporary():
    with patch("bebcare.services.quality_candidate_fetch.socket.getaddrinfo", _public_addrinfo), patch(
        "bebcare.services.quality_candidate_fetch.requests.get",
        side_effect=requests.Timeout("slow"),
    ):
        result = fetch_candidate_bytes("https://cdn.example/slow.png")
    assert result.outcome == OUTCOME_TEMPORARY
    assert result.details["reason"] == "timeout"


def test_safe_cdn_response():
    raw = _png()
    with patch("bebcare.services.quality_candidate_fetch.socket.getaddrinfo", _public_addrinfo), patch(
        "bebcare.services.quality_candidate_fetch.requests.get", return_value=_response(content=raw)
    ) as get:
        result = fetch_candidate_bytes("https://cdn.jsdelivr.net/gh/org/repo/a.png")
    assert result.outcome == OUTCOME_RETRIEVED
    kwargs = get.call_args.kwargs
    assert kwargs["allow_redirects"] is False
    assert "Authorization" not in kwargs["headers"]
    assert result.details.get("host") == "cdn.jsdelivr.net"


def test_hostname_resolving_to_private_rejected():
    with patch("bebcare.services.quality_candidate_fetch.socket.getaddrinfo", _private_addrinfo):
        result = fetch_candidate_bytes("https://evil.example/img.png")
    assert result.outcome == OUTCOME_INVALID_URL
    assert result.details["reason"] == "hostname_resolved_to_prohibited"


def test_cdn_5xx_is_temporary_not_visual():
    resp = _response(status=503, headers={}, chunks=[])
    with patch("bebcare.services.quality_candidate_fetch.socket.getaddrinfo", _public_addrinfo), patch(
        "bebcare.services.quality_candidate_fetch.requests.get", return_value=resp
    ):
        result = fetch_candidate_bytes("https://cdn.example/fail.png")
    assert result.outcome == OUTCOME_TEMPORARY
    assert result.content is None


def test_http_404_permanent():
    resp = _response(status=404, headers={}, chunks=[])
    with patch("bebcare.services.quality_candidate_fetch.socket.getaddrinfo", _public_addrinfo), patch(
        "bebcare.services.quality_candidate_fetch.requests.get", return_value=resp
    ):
        result = fetch_candidate_bytes("https://cdn.example/missing.png")
    assert result.outcome == OUTCOME_PERMANENT
