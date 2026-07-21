"""Embedding / CLIP 扩展点。

默认 NullEmbeddingBackend（不加载 Torch）。
未来启用：设置 ENABLE_CLIP=true，并安装 requirements-clip.txt。
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional, Protocol

from bebcare.config.settings import settings

logger = logging.getLogger(__name__)


class EmbeddingBackend(Protocol):
    """图文向量能力接口；业务侧只依赖本协议，便于替换实现。"""

    @property
    def enabled(self) -> bool: ...

    def embed_image(self, image: Any) -> Optional[List[float]]:
        """返回向量；未启用时返回 None。"""
        ...

    def text_image_similarity(self, text: str, image: Any) -> Optional[float]:
        """文案-图片相似度 [0,1]；未启用时返回 None（调用方应跳过校验）。"""
        ...


class NullEmbeddingBackend:
    """占位实现：零依赖，保留调用链。"""

    @property
    def enabled(self) -> bool:
        return False

    def embed_image(self, image: Any) -> Optional[List[float]]:
        return None

    def text_image_similarity(self, text: str, image: Any) -> Optional[float]:
        return None


_backend: Optional[EmbeddingBackend] = None


def get_embedding_backend() -> EmbeddingBackend:
    global _backend
    if _backend is not None:
        return _backend

    if settings.enable_clip:
        from bebcare.knowledge_base.clip_backend import ClipEmbeddingBackend

        _backend = ClipEmbeddingBackend()
        logger.info("CLIP embedding backend enabled")
    else:
        _backend = NullEmbeddingBackend()
        logger.info("CLIP embedding disabled (ENABLE_CLIP=false); using NullEmbeddingBackend")

    return _backend


def reset_embedding_backend() -> None:
    """测试或热切换配置时重置单例。"""
    global _backend
    _backend = None
