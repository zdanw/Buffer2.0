from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import declarative_base, sessionmaker
from bebcare.config.settings import settings
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()


def _build_engine(database_url: str):
    """按方言创建引擎：本地 SQLite / 生产 PostgreSQL(Supabase)。"""
    if database_url.startswith("sqlite"):
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False, "timeout": 30},
        )

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine

    # PostgreSQL / Supabase：连接探活 + 受控连接池（适配 HF 单实例）
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=1800,
    )


engine = _build_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _legacy_schema_needs_stamp() -> bool:
    """已有表（create_all / 旧部署）但无 alembic_version 时需 stamp，避免重复建表。

    适用于本地 SQLite 与生产 Postgres（Supabase / HF Space）。
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "alembic_version" in tables:
        return False
    return "users" in tables or "products" in tables


def _ensure_missing_tables() -> None:
    """补建 stamp/旧库缺失的表（如 product_dimensions），已存在则跳过。"""
    import bebcare.models  # noqa: F401 — 注册 Base.metadata

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    missing = [t for t in Base.metadata.sorted_tables if t.name not in existing]
    if not missing:
        return
    names = [t.name for t in missing]
    logger.info("Creating missing tables (checkfirst): %s", names)
    Base.metadata.create_all(bind=engine, tables=missing)


def init_db() -> None:
    """启动时初始化 schema。生产禁止 SQLite；优先走 Alembic。"""
    if settings.is_production and settings.is_sqlite:
        raise RuntimeError(
            "APP_ENV=production 时禁止使用 SQLite。"
            "请将 DATABASE_URL 设置为 Supabase PostgreSQL 连接串（postgresql://...）。"
        )

    if settings.auto_migrate:
        from bebcare.db.migrate import run_migrations, stamp_head

        dialect = "sqlite" if settings.is_sqlite else "postgresql"
        if _legacy_schema_needs_stamp():
            logger.info(
                "Detected existing schema without alembic_version; stamping head (env=%s, dialect=%s)",
                settings.app_env,
                dialect,
            )
            stamp_head()
        else:
            logger.info(
                "Running database migrations (env=%s, dialect=%s)",
                settings.app_env,
                dialect,
            )
            run_migrations()

        # Alembic 旧版 env 可能重置 logging；迁移后强制恢复应用日志级别
        from bebcare.logging_config import setup_logging

        setup_logging(settings.log_level, force=True)
        logger.info("Database ready (env=%s, dialect=%s)", settings.app_env, dialect)

        # stamp 不会补新表；已 stamp 的旧库也可能缺 product_dimensions 等 → /products 500
        _ensure_missing_tables()
        return

    # 关闭自动迁移时：仅开发环境允许 create_all 兜底
    if settings.is_development:
        logger.warning("AUTO_MIGRATE=false；development 下使用 create_all 兜底建表")
        Base.metadata.create_all(bind=engine)
        return

    logger.info("AUTO_MIGRATE=false；跳过启动时建表（请由部署流水线执行 alembic upgrade head）")
