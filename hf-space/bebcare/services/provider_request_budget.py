"""Authoritative provider HTTP request budget.

Reserve a slot immediately before each network request. Disabled by default so
production traffic is unlimited; benchmarks and tests install hard caps.
Counters live on one process-wide object and are not reset by helpers.
"""

from __future__ import annotations

import os
import threading
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Iterator, Optional

from bebcare.services.asset_intelligence_policy import FAILURE_PERMANENT, AnalysisFailure

KIND_SEMANTIC = "semantic"
KIND_QA = "qa"
KIND_IMAGE = "image"
KINDS = (KIND_SEMANTIC, KIND_QA, KIND_IMAGE)
KIND_ALIASES = {
    "visual_qa": KIND_QA,
    "visual-qa": KIND_QA,
    "image_generation": KIND_IMAGE,
    "image-generation": KIND_IMAGE,
}
REASONS = ("initial", "correction", "retry", "fallback")

_kind_var: ContextVar[str | None] = ContextVar("provider_budget_kind", default=None)
_reason_var: ContextVar[str] = ContextVar("provider_budget_reason", default="initial")
_lock = threading.Lock()
_active: Optional["ProviderRequestBudget"] = None


class BudgetExhausted(AnalysisFailure):
    """Raised before any network activity when a kind cap is exhausted."""

    def __init__(self, kind: str):
        super().__init__(FAILURE_PERMANENT, "provider_budget_exhausted")
        self.kind = kind


def normalize_kind(kind: str | None) -> str:
    raw = (kind or "").strip().lower()
    return KIND_ALIASES.get(raw, raw)


class ProviderRequestBudget:
    def __init__(self, caps: dict[str, int] | None = None):
        self._lock = threading.Lock()
        self.caps = {normalize_kind(k): int(v) for k, v in (caps or {}).items()}
        self.attempted: Counter[str] = Counter()
        self.succeeded: Counter[str] = Counter()
        self.failed: Counter[str] = Counter()
        self.corrected: Counter[str] = Counter()
        self.retried: Counter[str] = Counter()
        self.fallback: Counter[str] = Counter()
        self.blocked_by_budget: Counter[str] = Counter()

    def remaining(self, kind: str) -> int | None:
        key = normalize_kind(kind)
        cap = self.caps.get(key)
        if cap is None:
            return None
        with self._lock:
            return max(0, cap - self.attempted[key])

    def reserve(self, kind: str, *, reason: str = "initial") -> None:
        key = normalize_kind(kind)
        if key not in KINDS:
            key = KIND_IMAGE if key in ("", "unknown") else key
        why = reason if reason in REASONS else "initial"
        with self._lock:
            cap = self.caps.get(key)
            if cap is not None and self.attempted[key] >= cap:
                self.blocked_by_budget[key] += 1
                raise BudgetExhausted(key)
            self.attempted[key] += 1
            if why == "correction":
                self.corrected[key] += 1
            elif why == "retry":
                self.retried[key] += 1
            elif why == "fallback":
                self.fallback[key] += 1

    def record_success(self, kind: str) -> None:
        with self._lock:
            self.succeeded[normalize_kind(kind)] += 1

    def record_failure(self, kind: str) -> None:
        with self._lock:
            self.failed[normalize_kind(kind)] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "caps": dict(self.caps),
                "attempted": dict(self.attempted),
                "succeeded": dict(self.succeeded),
                "failed": dict(self.failed),
                "corrected": dict(self.corrected),
                "retried": dict(self.retried),
                "fallback": dict(self.fallback),
                "blocked_by_budget": dict(self.blocked_by_budget),
            }


def install_provider_request_budget(caps: dict[str, int]) -> ProviderRequestBudget:
    global _active
    budget = ProviderRequestBudget(caps)
    with _lock:
        _active = budget
    return budget


def clear_provider_request_budget() -> None:
    """Test-only reset. Live/benchmark helpers cannot clear production counters."""
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        return
    global _active
    with _lock:
        _active = None


def active_provider_request_budget() -> ProviderRequestBudget | None:
    with _lock:
        return _active


def current_provider_kind() -> str | None:
    return _kind_var.get()


def current_provider_reason() -> str:
    return _reason_var.get() or "initial"


@contextmanager
def provider_request_context(kind: str, *, reason: str = "initial") -> Iterator[None]:
    kind_token = _kind_var.set(normalize_kind(kind))
    reason_token = _reason_var.set(reason if reason in REASONS else "initial")
    try:
        yield
    finally:
        _reason_var.reset(reason_token)
        _kind_var.reset(kind_token)


@contextmanager
def provider_request_reason(reason: str) -> Iterator[None]:
    token = _reason_var.set(reason if reason in REASONS else "initial")
    try:
        yield
    finally:
        _reason_var.reset(token)


def reserve_provider_request(kind: str | None = None, *, reason: str | None = None) -> None:
    budget = active_provider_request_budget()
    if budget is None:
        return
    resolved = normalize_kind(kind or current_provider_kind() or KIND_IMAGE)
    why = reason or current_provider_reason()
    budget.reserve(resolved, reason=why)


def reserved_provider_call(
    fn: Callable[[], Any],
    *,
    kind: str | None = None,
    reason: str | None = None,
) -> Any:
    resolved = normalize_kind(kind or current_provider_kind() or KIND_IMAGE)
    reserve_provider_request(resolved, reason=reason)
    budget = active_provider_request_budget()
    try:
        result = fn()
    except Exception:
        if budget is not None:
            budget.record_failure(resolved)
        raise
    if budget is not None:
        budget.record_success(resolved)
    return result
