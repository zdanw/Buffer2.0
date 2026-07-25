# Env + stubs must run before any bebcare import.
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

_TEST_DIR = Path(__file__).resolve().parent
_TEST_DB = _TEST_DIR / "_pytest_bebcare.db"
if _TEST_DB.exists():
    _TEST_DB.unlink()

os.environ.update(
    {
        "APP_ENV": "development",
        "DATABASE_URL": f"sqlite:///{_TEST_DB.as_posix()}",
        "AUTO_MIGRATE": "false",
        "DEEPSEEK_API_KEY": "test-deepseek-key",
        "DOUBAO_API_KEY": "test-doubao-key",
        "BUFFER_API_TOKEN": "test-buffer-token",
        "GITHUB_TOKEN": "test-github-token",
        "GITHUB_USERNAME": "test-user",
        "GITHUB_REPO": "test-repo",
        "SECRET_KEY": "ci-test-secret-key-32-characters!",
        "ADMIN_USERNAME": "admin",
        "ADMIN_EMAIL": "admin@test.local",
        "ADMIN_PASSWORD": "AdminTestPass123!",
        "ALLOWED_ORIGINS": "http://localhost:5173",
        "ENABLE_CLIP": "false",
        "LOG_LEVEL": "WARNING",
    }
)


def _stub_module(name: str, **attrs):
    mod = ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = mod
    return mod


# Optional heavy deps — keep API tests runnable without full ML stack.
if "imagehash" not in sys.modules:
    _stub_module("imagehash", average_hash=MagicMock(), phash=MagicMock())
if "chromadb" not in sys.modules:
    chroma = _stub_module("chromadb")
    chroma.PersistentClient = MagicMock(
        return_value=MagicMock(
            get_collection=MagicMock(side_effect=Exception("missing")),
            create_collection=MagicMock(return_value=MagicMock()),
        )
    )

import pytest
from fastapi import Depends, FastAPI, APIRouter
from fastapi.testclient import TestClient

from bebcare.database import Base, engine, init_db
from bebcare.initial_data import initialize_data
from bebcare.api.auth_routes import router as auth_router
from bebcare.api.generate_routes import router as generate_router
from bebcare.services.auth_dependency import get_current_active_user
import bebcare.models  # noqa: F401 — register metadata


def _build_test_app() -> FastAPI:
    init_db()
    initialize_data()

    app = FastAPI(title="Bebcare Test API")
    api = APIRouter(prefix="/v1")
    api.include_router(auth_router)
    api.include_router(generate_router, dependencies=[Depends(get_current_active_user)])
    app.include_router(api)

    @app.get("/")
    def root():
        return {"message": "ok"}

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    return app


@pytest.fixture(scope="session")
def client():
    app = _build_test_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_tokens(client: TestClient):
    resp = client.post(
        "/v1/auth/login/",
        data={"username": "admin", "password": "AdminTestPass123!"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    return body


@pytest.fixture
def auth_headers(admin_tokens):
    return {"Authorization": f"Bearer {admin_tokens['access_token']}"}
