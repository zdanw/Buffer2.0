"""Phase 2A: local deterministic image metadata. No vision / no paid APIs."""

from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any, Optional

from PIL import Image, ImageOps

DET_META_VERSION = "det_meta_v1"
EXIF_ORIENTATION_TAG = 274

MIME_BY_PIL = {
    "JPEG": "image/jpeg",
    "JPG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
    "BMP": "image/bmp",
    "TIFF": "image/tiff",
}


def content_hash_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def cache_identity(content_hash: str, version: str = DET_META_VERSION) -> str:
    return f"{content_hash}:{version}"


def detect_mime(raw: bytes, pil_format: Optional[str] = None) -> str:
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if raw[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if pil_format:
        return MIME_BY_PIL.get(pil_format.upper(), "application/octet-stream")
    return "application/octet-stream"


def _has_alpha(image: Image.Image) -> bool:
    if image.mode in ("RGBA", "LA", "PA"):
        return True
    if image.mode == "P" and "transparency" in image.info:
        return True
    return False


def _exif_orientation(image: Image.Image) -> Optional[int]:
    try:
        value = image.getexif().get(EXIF_ORIENTATION_TAG)
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def extract_deterministic_metadata(raw: bytes) -> dict[str, Any]:
    """Compute metadata from an in-memory copy. Does not mutate `raw`."""
    if not raw:
        raise ValueError("empty_image_bytes")
    digest = content_hash_bytes(raw)
    image = Image.open(BytesIO(raw))
    image.load()
    mime = detect_mime(raw, image.format)
    orientation = _exif_orientation(image)
    has_alpha = _has_alpha(image)
    oriented = ImageOps.exif_transpose(image)
    work = oriented if oriented is not None else image
    width, height = work.size
    from bebcare.utils.image_utils import calculate_phash

    phash = calculate_phash(work)
    edge = min(int(width), int(height))
    quality: dict[str, Any] = {
        "min_edge": edge,
        "undersized": edge < 256,
    }
    if edge < 256:
        quality["warning"] = "severe_undersize"
    elif edge < 1024:
        quality["warning"] = "mild_undersize"
    else:
        quality["warning"] = None
    return {
        "content_hash": digest,
        "detected_mime_type": mime,
        "has_alpha": has_alpha,
        "exif_orientation": orientation,
        "width": int(width),
        "height": int(height),
        "phash": phash,
        "basic_quality_json": quality,
        "deterministic_metadata_version": DET_META_VERSION,
    }
