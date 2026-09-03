"""Fail CI if pip resolved a different version than backend/requirements*.txt."""

from pathlib import Path

import apscheduler
import fastapi
import httpx
import pytest
import sqlalchemy
import starlette

BACKEND = Path(__file__).resolve().parents[2]
REQUIREMENTS = BACKEND / "requirements.txt"
REQUIREMENTS_DEV = BACKEND / "requirements-dev.txt"


def _exact_pins(*paths: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for path in paths:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "==" not in line:
                continue
            name, version = line.split("==", 1)
            name = name.split("[", 1)[0].strip().lower()
            pins[name] = version.strip()
    return pins


def test_critical_ci_packages_match_requirement_pins():
    pins = _exact_pins(REQUIREMENTS, REQUIREMENTS_DEV)
    installed = {
        "apscheduler": apscheduler.__version__,
        "starlette": starlette.__version__,
        "httpx": httpx.__version__,
        "fastapi": fastapi.__version__,
        "sqlalchemy": sqlalchemy.__version__,
        "pytest": pytest.__version__,
    }
    for name, version in installed.items():
        assert name in pins, f"missing pin for {name}"
        assert version == pins[name], f"{name} installed {version}, pinned {pins[name]}"
