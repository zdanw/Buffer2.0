"""Fresh SQLite can reach Alembic head without create_all or a pre-existing admin."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from bebcare.config.settings import settings


def _alembic_cfg(url: str) -> Config:
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_empty_sqlite_upgrade_head_and_downgrade_045(tmp_path, monkeypatch):
    dbfile = tmp_path / "fresh.db"
    url = f"sqlite:///{dbfile.as_posix()}"
    monkeypatch.setattr(settings, "database_url", url)
    cfg = _alembic_cfg(url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert version
    assert "generation_reference_selections" in tables
    assert "generation_decision_events" in tables
    command.downgrade(cfg, "044_product_fidelity_guard")
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        version_after = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        tables_after = {
            row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
    assert version_after == version
    assert "generation_reference_selections" in tables_after


def test_single_alembic_head_and_038_chain(tmp_path, monkeypatch):
    from alembic.script import ScriptDirectory

    dbfile = tmp_path / "chain.db"
    url = f"sqlite:///{dbfile.as_posix()}"
    monkeypatch.setattr(settings, "database_url", url)
    cfg = _alembic_cfg(url)
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert heads == ["046_generation_run_output_snapshot"]
    command.upgrade(cfg, "038_grounded_generation_foundation")
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "038_grounded_generation_foundation")
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "046_generation_run_output_snapshot"


def test_existing_sqlite_copy_upgrades_to_head(tmp_path, monkeypatch):
    import shutil

    src = Path(__file__).resolve().parents[2] / "bebcare.db"
    if not src.exists():
        return
    dest = tmp_path / "existing.db"
    shutil.copy2(src, dest)
    url = f"sqlite:///{dest.as_posix()}"
    monkeypatch.setattr(settings, "database_url", url)
    cfg = _alembic_cfg(url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "046_generation_run_output_snapshot"
