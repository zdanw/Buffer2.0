"""Deterministic Phase 2B analysis failure classification and retry policy."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
from pydantic import ValidationError

MAX_ANALYSIS_ATTEMPTS = 3
ACTIVE_JOB_LEASE = timedelta(minutes=2)
BACKOFF_AFTER_ATTEMPT = {
    1: timedelta(minutes=5),
    2: timedelta(minutes=30),
}
USABLE_STATUSES = ("ready", "partial")
FAILURE_TRANSIENT = "transient"
FAILURE_PERMANENT = "permanent"

TRANSIENT_HTTP = frozenset({408, 429, *range(500, 600)})
PERMANENT_HTTP = frozenset({400, 401, 403})


class AnalysisFailure(Exception):
    """Typed analysis error. str() is a short category, not a provider body."""

    def __init__(
        self,
        failure_type: str,
        error_category: str,
        *,
        http_status: int | None = None,
        raw: str | None = None,
        usage: dict[str, Any] | None = None,
        request_count: int = 1,
        correction_used: bool = False,
        validation_errors: str | None = None,
        latency_ms: int | None = None,
    ):
        self.failure_type = failure_type
        self.error_category = error_category
        self.http_status = http_status
        self.raw = raw
        self.usage = usage or {}
        self.request_count = request_count
        self.correction_used = correction_used
        self.validation_errors = validation_errors
        self.latency_ms = latency_ms
        super().__init__(error_category)


def next_retry_at_for_attempt(attempt_count: int, *, now: datetime | None = None) -> Optional[datetime]:
    """attempt_count is the count after the failure just recorded."""
    if attempt_count >= MAX_ANALYSIS_ATTEMPTS:
        return None
    delay = BACKOFF_AFTER_ATTEMPT.get(attempt_count)
    if delay is None:
        return None
    return (now or datetime.utcnow()) + delay


def is_usable_cache_hit(row: Any) -> bool:
    if row is None:
        return False
    status = (getattr(row, "status", None) or "").strip()
    if status not in USABLE_STATUSES:
        return False
    payload = getattr(row, "normalized_result", None)
    if not payload:
        return False
    from bebcare.schemas.asset_intelligence import parse_intelligence_result

    try:
        parse_intelligence_result(payload)
    except Exception:
        return False
    return True


def is_retry_eligible(row: Any, *, now: datetime | None = None) -> bool:
    if row is None:
        return True
    if is_usable_cache_hit(row):
        return False
    clock = now or datetime.utcnow()
    status = (getattr(row, "status", None) or "").strip()
    last_at = getattr(row, "last_attempt_at", None)
    if status == "analyzing" and last_at and (clock - last_at) < ACTIVE_JOB_LEASE:
        return False
    if (getattr(row, "failure_type", None) or "") == FAILURE_PERMANENT:
        return False
    attempts = int(getattr(row, "attempt_count", 0) or 0)
    if attempts >= MAX_ANALYSIS_ATTEMPTS:
        return False
    nxt = getattr(row, "next_retry_at", None)
    if nxt is not None and nxt > clock:
        return False
    return True


def classify_analysis_failure(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, AnalysisFailure):
        return exc.failure_type, exc.error_category
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return FAILURE_TRANSIENT, "timeout"
    if isinstance(
        exc,
        (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
            httpx.NetworkError,
            ConnectionError,
        ),
    ):
        return FAILURE_TRANSIENT, "connection_error"
    if isinstance(exc, httpx.HTTPStatusError):
        status = int(getattr(exc.response, "status_code", 0) or 0)
        if status in TRANSIENT_HTTP:
            if status == 408:
                return FAILURE_TRANSIENT, "http_408"
            if status == 429:
                return FAILURE_TRANSIENT, "http_429"
            return FAILURE_TRANSIENT, "http_5xx"
        if status in PERMANENT_HTTP:
            if status == 400:
                return FAILURE_PERMANENT, "http_400_invalid_request"
            if status in (401, 403):
                return FAILURE_PERMANENT, "http_auth"
            return FAILURE_PERMANENT, f"http_{status}"
        return FAILURE_PERMANENT, f"http_{status or 'error'}"
    if isinstance(exc, ValidationError):
        return FAILURE_PERMANENT, "structured_output_invalid"
    text = str(exc)
    if "platform_vision_unconfigured" in text:
        return FAILURE_PERMANENT, "invalid_analysis_configuration"
    if "unsupported_image" in text or "empty_image" in text:
        return FAILURE_PERMANENT, "invalid_image_input"
    return FAILURE_TRANSIENT, type(exc).__name__[:64]
