from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from check_docker_production_source import check  # noqa: E402


def test_docker_production_source_is_backend():
    errors = check(ROOT / "Dockerfile")
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
