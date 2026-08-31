"""Bounded, SSRF-resistant fetch for Phase 3A candidate inspection.

Not a general download helper. Does not weaken Phase 2B catalog URL rules.
Never logs authorization, bodies, credentialed URLs, or sensitive query values.
"""

from __future__ import annotations

import base64
import ipaddress
import logging
import re
import socket
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote, urlparse

import requests

logger = logging.getLogger(__name__)

OUTCOME_RETRIEVED = "retrieved"
OUTCOME_TEMPORARY = "temporarily_unavailable"
OUTCOME_INVALID_URL = "invalid_or_unsupported_url"
OUTCOME_TOO_LARGE = "response_too_large"
OUTCOME_PERMANENT = "permanent_retrieval_failure"

MAX_RESPONSE_BYTES = 25 * 1024 * 1024
MAX_DATA_URL_CHARS = 8 * 1024 * 1024
CONNECT_TIMEOUT_S = 5.0
READ_TIMEOUT_S = 15.0
MAX_REDIRECTS = 3
ALLOWED_SCHEMES = frozenset({"https", "data"})
CHUNK_SIZE = 64 * 1024

_DATA_URL_RE = re.compile(
    r"^data:(image/[\w.+-]+)(;base64)?,(.*)$",
    flags=re.IGNORECASE | re.DOTALL,
)
_FETCH_HEADERS = {
    "User-Agent": "PulseForgeQualityProtection/3A",
    "Accept": "image/*,*/*;q=0.8",
}


@dataclass
class CandidateFetchResult:
    outcome: str
    content: bytes | None = None
    details: dict[str, Any] = field(default_factory=dict)


def _safe_host(parsed) -> str | None:
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return None
    if "@" in host or ":" in (parsed.netloc or "") and parsed.username:
        return host
    return host


def _log_fetch_event(reason: str, *, host: str | None = None, status: int | None = None) -> None:
    logger.info(
        "qa_candidate_fetch reason=%s host=%s status=%s",
        reason,
        host or "-",
        status if status is not None else "-",
    )


def _is_prohibited_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _is_prohibited_ip(ip.ipv4_mapped)
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
        or (isinstance(ip, ipaddress.IPv4Address) and ip.is_unspecified)
    )


def _literal_ip(host: str):
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def _resolve_host_ips(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    for info in infos:
        addr = info[4][0]
        try:
            ips.append(ipaddress.ip_address(addr))
        except ValueError:
            continue
    return ips


def _validate_remote_url(url: str) -> CandidateFetchResult | None:
    """Return a failure result, or None if the URL may be fetched."""
    text = (url or "").strip()
    if not text:
        return CandidateFetchResult(
            OUTCOME_INVALID_URL,
            details={"reason": "empty_url"},
        )
    parsed = urlparse(text)
    if parsed.scheme.lower() == "http":
        return CandidateFetchResult(
            OUTCOME_INVALID_URL,
            details={"reason": "http_not_allowed", "scheme": "http"},
        )
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return CandidateFetchResult(
            OUTCOME_INVALID_URL,
            details={"reason": "unsupported_scheme", "scheme": parsed.scheme.lower() or "none"},
        )
    if parsed.scheme.lower() == "data":
        return None
    if parsed.username is not None or parsed.password is not None:
        return CandidateFetchResult(
            OUTCOME_INVALID_URL,
            details={"reason": "credentials_in_url"},
        )
    host = _safe_host(parsed)
    if not host:
        return CandidateFetchResult(
            OUTCOME_INVALID_URL,
            details={"reason": "missing_host"},
        )
    if host == "localhost" or host.endswith(".localhost"):
        return CandidateFetchResult(
            OUTCOME_INVALID_URL,
            details={"reason": "prohibited_host", "host": "localhost"},
        )
    literal = _literal_ip(host)
    if literal is not None:
        if _is_prohibited_ip(literal):
            kind = "loopback" if literal.is_loopback else (
                "link_local" if literal.is_link_local else (
                    "multicast" if literal.is_multicast else "private_or_reserved"
                )
            )
            return CandidateFetchResult(
                OUTCOME_INVALID_URL,
                details={"reason": "prohibited_destination", "kind": kind},
            )
        return None
    resolved = _resolve_host_ips(host)
    if not resolved:
        return CandidateFetchResult(
            OUTCOME_PERMANENT,
            details={"reason": "hostname_unresolved", "host": host},
        )
    for ip in resolved:
        if _is_prohibited_ip(ip):
            return CandidateFetchResult(
                OUTCOME_INVALID_URL,
                details={"reason": "hostname_resolved_to_prohibited", "host": host},
            )
    return None


def _decode_data_url(url: str) -> CandidateFetchResult:
    if len(url) > MAX_DATA_URL_CHARS:
        return CandidateFetchResult(
            OUTCOME_TOO_LARGE,
            details={"reason": "data_url_too_large", "chars": len(url)},
        )
    match = _DATA_URL_RE.match(url)
    if not match:
        return CandidateFetchResult(
            OUTCOME_INVALID_URL,
            details={"reason": "unsupported_data_url"},
        )
    payload = match.group(3) or ""
    if len(payload) > MAX_DATA_URL_CHARS:
        return CandidateFetchResult(
            OUTCOME_TOO_LARGE,
            details={"reason": "data_url_too_large", "chars": len(payload)},
        )
    try:
        if match.group(2):
            raw = base64.b64decode(payload, validate=False)
        else:
            raw = unquote(payload).encode("utf-8")
    except Exception:
        return CandidateFetchResult(
            OUTCOME_INVALID_URL,
            details={"reason": "undecodable_data_url"},
        )
    if len(raw) > MAX_RESPONSE_BYTES:
        return CandidateFetchResult(
            OUTCOME_TOO_LARGE,
            details={"reason": "decoded_data_url_too_large", "bytes": len(raw)},
        )
    return CandidateFetchResult(OUTCOME_RETRIEVED, content=raw, details={"scheme": "data"})


def _status_outcome(status: int) -> str:
    if status >= 500 or status == 429:
        return OUTCOME_TEMPORARY
    if status in (301, 302, 303, 307, 308):
        return OUTCOME_TEMPORARY
    if 400 <= status < 500:
        return OUTCOME_PERMANENT
    return OUTCOME_TEMPORARY


def _read_bounded_body(response: requests.Response, *, content_length: int | None) -> CandidateFetchResult:
    if content_length is not None and content_length > MAX_RESPONSE_BYTES:
        return CandidateFetchResult(
            OUTCOME_TOO_LARGE,
            details={"reason": "content_length_exceeds_limit", "content_length": content_length},
        )
    buf = bytearray()
    try:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if not chunk:
                continue
            buf.extend(chunk)
            if len(buf) > MAX_RESPONSE_BYTES:
                return CandidateFetchResult(
                    OUTCOME_TOO_LARGE,
                    details={"reason": "streamed_response_too_large", "bytes_read": len(buf)},
                )
    except requests.Timeout:
        return CandidateFetchResult(OUTCOME_TEMPORARY, details={"reason": "read_timeout"})
    except requests.ConnectionError:
        return CandidateFetchResult(OUTCOME_TEMPORARY, details={"reason": "connection_error"})
    except requests.RequestException:
        return CandidateFetchResult(OUTCOME_TEMPORARY, details={"reason": "request_error"})
    return CandidateFetchResult(OUTCOME_RETRIEVED, content=bytes(buf), details={"bytes": len(buf)})


def _fetch_https(url: str, *, redirects_left: int) -> CandidateFetchResult:
    blocked = _validate_remote_url(url)
    if blocked is not None:
        return blocked
    parsed = urlparse(url)
    host = _safe_host(parsed)
    try:
        response = requests.get(
            url,
            timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S),
            headers=_FETCH_HEADERS,
            allow_redirects=False,
            stream=True,
        )
    except requests.Timeout:
        _log_fetch_event("timeout", host=host)
        return CandidateFetchResult(OUTCOME_TEMPORARY, details={"reason": "timeout", "host": host})
    except requests.ConnectionError:
        _log_fetch_event("connection_error", host=host)
        return CandidateFetchResult(
            OUTCOME_TEMPORARY, details={"reason": "connection_error", "host": host}
        )
    except requests.RequestException:
        _log_fetch_event("request_error", host=host)
        return CandidateFetchResult(
            OUTCOME_TEMPORARY, details={"reason": "request_error", "host": host}
        )
    status = int(response.status_code)
    if status in (301, 302, 303, 307, 308):
        location = (response.headers.get("Location") or "").strip()
        response.close()
        if not location:
            return CandidateFetchResult(
                OUTCOME_PERMANENT,
                details={"reason": "redirect_without_location", "status": status, "host": host},
            )
        loc_parsed = urlparse(location)
        if not loc_parsed.scheme:
            location = f"{parsed.scheme}://{parsed.netloc}{location}"
        dest_fail = _validate_remote_url(location)
        if dest_fail is not None:
            dest_fail.details = {
                **dest_fail.details,
                "reason": dest_fail.details.get("reason") or "redirect_destination_prohibited",
                "redirect": True,
            }
            _log_fetch_event("redirect_rejected", host=host, status=status)
            return dest_fail
        if redirects_left <= 0:
            return CandidateFetchResult(
                OUTCOME_PERMANENT,
                details={"reason": "too_many_redirects", "host": host},
            )
        return _fetch_https(location, redirects_left=redirects_left - 1)
    if status != 200:
        response.close()
        outcome = _status_outcome(status)
        _log_fetch_event("http_status", host=host, status=status)
        return CandidateFetchResult(
            outcome,
            details={"reason": "http_status", "status": status, "host": host},
        )
    length_raw = response.headers.get("Content-Length")
    content_length = None
    if length_raw and str(length_raw).isdigit():
        content_length = int(length_raw)
    try:
        result = _read_bounded_body(response, content_length=content_length)
    finally:
        response.close()
    if result.outcome == OUTCOME_RETRIEVED:
        result.details = {**result.details, "host": host, "scheme": "https"}
    return result


def fetch_candidate_bytes(url: str | None) -> CandidateFetchResult:
    """Fetch a generation candidate for deterministic inspection only."""
    if url is None or not str(url).strip():
        return CandidateFetchResult(OUTCOME_INVALID_URL, details={"reason": "empty_url"})
    text = str(url).strip()
    if text.lower().startswith("data:"):
        return _decode_data_url(text)
    return _fetch_https(text, redirects_left=MAX_REDIRECTS)
