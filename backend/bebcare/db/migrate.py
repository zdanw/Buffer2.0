from pathlib import Path
from alembic import command
from alembic.config import Config


def _alembic_config() -> Config:
    # backend/bebcare/db/migrate.py → backend/
    backend_dir = Path(__file__).resolve().parents[2]
    ini_path = backend_dir / "alembic.ini"
    cfg = Config(str(ini_path))
    # 目录名勿用 alembic：在 backend 下启动时会遮蔽官方 alembic 包
    cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    return cfg


def run_migrations() -> None:
    """升级到最新 revision（本地 SQLite / 生产 Supabase 共用）。"""
    command.upgrade(_alembic_config(), "head")


def stamp_head() -> None:
    """将已有库标记为最新 revision（不改表结构）。用于已有本地 SQLite。"""
    command.stamp(_alembic_config(), "head")
