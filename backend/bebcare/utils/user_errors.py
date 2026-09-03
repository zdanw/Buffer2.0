"""Sanitize exception text before returning it in API responses."""

from __future__ import annotations

import json
import logging
import re
from typing import Final

logger = logging.getLogger(__name__)

GENERATE_TASK_FAILED: Final[str] = "generate_task_failed"
SCHEDULER_IMAGE_FAILED: Final[str] = "scheduler_image_failed"

_BLOCKED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"scripts[/\\]", re.I),
    re.compile(r"\.ps1\b", re.I),
    re.compile(r"\.sh\b", re.I),
    re.compile(r"\bpython\s+", re.I),
    re.compile(r"\bnpm\s+", re.I),
    re.compile(r"\byarn\s+", re.I),
    re.compile(r"\bpnpm\s+", re.I),
    re.compile(r"dev\s+proxy", re.I),
    re.compile(r"localhost:", re.I),
    re.compile(r"127\.0\.0\.1", re.I),
    re.compile(r"\buvicorn\b", re.I),
    re.compile(r"\bECONNREFUSED\b"),
    re.compile(r"Traceback\b"),
    re.compile(r'File "', re.I),
    re.compile(r"\bat line \d+", re.I),
    re.compile(r"HTTPConnectionPool", re.I),
)


def _is_json_blob(value: str) -> bool:
    trimmed = value.strip()
    if not trimmed.startswith("{") and not trimmed.startswith("["):
        return False
    try:
        json.loads(trimmed)
        return True
    except json.JSONDecodeError:
        return False


def is_safe_user_message(message: str) -> bool:
    trimmed = message.strip()
    if not trimmed:
        return False
    if _is_json_blob(trimmed):
        return False
    return not any(pattern.search(trimmed) for pattern in _BLOCKED_PATTERNS)


def user_safe_detail(exc: BaseException, *, fallback: str) -> str:
    message = str(exc).strip()
    if message and is_safe_user_message(message):
        return message
    if message:
        logger.warning(
            "Suppressed unsafe error detail from %s",
            type(exc).__name__,
            exc_info=exc,
        )
    return fallback


def user_safe_task_error(exc: BaseException) -> str:
    return user_safe_detail(exc, fallback=GENERATE_TASK_FAILED)
