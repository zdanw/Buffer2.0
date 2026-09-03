from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from check_docker_production_source import (  # noqa: E402
    check,
    ignore_pattern_matches,
    path_excluded_by_dockerignore,
)


def test_docker_production_source_is_backend():
    errors = check(ROOT / "Dockerfile", ROOT / ".dockerignore")
    assert errors == [], errors


def test_docker_check_fails_on_hf_space_app_copy(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        "FROM python:3.10-slim\n"
        "COPY hf-space/bebcare/ ./bebcare/\n"
        'CMD ["uvicorn", "bebcare.main:app"]\n',
        encoding="utf-8",
    )
    errors = check(dockerfile)
    assert errors, "expected failure when copying hf-space/bebcare"


def test_root_dockerignore_does_not_exclude_backend_tree():
    text = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert path_excluded_by_dockerignore("backend/requirements.txt", text) is None
    assert path_excluded_by_dockerignore("backend/bebcare/", text) is None
    assert path_excluded_by_dockerignore("backend/migrations/", text) is None
    assert path_excluded_by_dockerignore("backend/alembic.ini", text) is None
    assert path_excluded_by_dockerignore("backend/app.py", text) is None
    assert path_excluded_by_dockerignore("backend/.env.example", text) is None
    assert path_excluded_by_dockerignore("backend/.env", text) is not None
    assert path_excluded_by_dockerignore("frontend/package.json", text) is not None


def test_dockerignore_backend_tree_patterns():
    for pattern in ("backend/", "/backend/", "backend/**", "backend"):
        ignore = f"{pattern}\n**/.env\n"
        assert path_excluded_by_dockerignore("backend/requirements.txt", ignore), pattern
        assert path_excluded_by_dockerignore("backend/bebcare/", ignore), pattern


def test_dockerignore_backend_exclusion_fails_check(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        "FROM python:3.10-slim\n"
        "COPY backend/requirements.txt .\n"
        "COPY --chown=user:user backend/bebcare/ ./bebcare/\n"
        "COPY --chown=user:user backend/migrations/ ./migrations/\n"
        "COPY --chown=user:user backend/alembic.ini ./\n"
        "COPY --chown=user:user backend/app.py ./\n"
        "COPY --chown=user:user backend/.env.example ./\n"
        'CMD ["uvicorn", "bebcare.main:app"]\n',
        encoding="utf-8",
    )
    dockerignore = tmp_path / ".dockerignore"
    dockerignore.write_text("backend/\n**/.env\n", encoding="utf-8")
    errors = check(dockerfile, dockerignore)
    assert errors, "expected failure when .dockerignore excludes backend/"
    assert any("backend/requirements.txt" in err for err in errors)
    assert any("backend/" in err for err in errors)


def test_frontend_ignore_does_not_exclude_backend():
    ignore = "frontend/\n**/.env\n*.md\n"
    assert path_excluded_by_dockerignore("backend/app.py", ignore) is None
    assert ignore_pattern_matches("frontend/", "frontend/src/App.tsx")
    assert not ignore_pattern_matches("frontend/", "backend/app.py")


def test_env_example_documents_grounded_rollout_default_off():
    text = (ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
    assert "GROUNDED_ROLLOUT_MODE=off" in text
    for value in ("off", "studio", "manual_automation", "all"):
        assert value in text
    assert "ASSET_INTELLIGENCE_MODE=off" in text
    assert "QUALITY_PROTECTION_MODE=off" in text
    assert "PRODUCT_FIDELITY_PREVENTION_MODE=off" in text
    assert "VISUAL_FIDELITY_QA_MODE=off" in text
    assert "QUALITY_DIVERSITY_SELECTOR_MODE=off" in text
    assert "ASSET_INTELLIGENCE_TRANSPORT=platform" in text
    assert "VISUAL_FIDELITY_QA_TRANSPORT=platform" in text
