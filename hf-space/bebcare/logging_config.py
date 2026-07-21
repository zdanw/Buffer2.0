"""应用日志初始化：输出到 stdout，供 Hugging Face Space Logs 查看。"""
from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def setup_logging(level: str = "INFO", *, force: bool = False) -> None:
    """按 LOG_LEVEL 配置根日志。

    force=True：在 Alembic fileConfig 等重置根 logger 后强制恢复。
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    level_name = (level or "INFO").upper().strip()
    log_level = getattr(logging, level_name, None)
    if not isinstance(log_level, int):
        log_level = logging.INFO
        level_name = "INFO"

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(log_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)

    # 降噪：第三方库默认偏吵
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)

    _CONFIGURED = True
    logging.getLogger(__name__).info("Logging configured (level=%s)", level_name)
