"""No-model reference suitability. Never downloads CDN bytes."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from bebcare.config.settings import settings

# 64-bit pHash bit Hamming. Images at or below this distance are near-duplicates.
# Configurable via settings.phash_near_duplicate_hamming (default 8).
PHASH_NEAR_DUPLICATE_HAMMING = 8
MIN_VALID_EDGE = 1
SEVERE_UNDERSIZE_EDGE = 256
SUFFICIENT_QUALITY_EDGE = 1024
PRODUCT_ASPECT_WEIGHT = 0.2
SCENE_ASPECT_WEIGHT = 0.8
DIVERSITY_PENALTY = 0.08
DIVERSITY_CAP = 5
UNDERSCORE_SEVERE = 5.0
UNDERSCORE_MILD = 1.0


def near_duplicate_threshold() -> int:
    try:
        value = int(settings.phash_near_duplicate_hamming)
    except Exception:
        value = PHASH_NEAR_DUPLICATE_HAMMING
    return max(0, value)


def phash_bit_hamming(hash_a: Optional[str], hash_b: Optional[str]) -> Optional[int]:
    if not hash_a or not hash_b:
        return None
    a = str(hash_a).strip().lower()
    b = str(hash_b).strip().lower()
    if not a or not b or len(a) != len(b):
        return None
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except ValueError:
        return None


def is_near_duplicate(hash_a: Optional[str], hash_b: Optional[str]) -> bool:
    distance = phash_bit_hamming(hash_a, hash_b)
    if distance is None:
        return False
    return distance <= near_duplicate_threshold()


def parse_target_aspect(image_size: Optional[str]) -> Optional[float]:
    if not image_size or "x" not in str(image_size).lower():
        return None
    try:
        width_s, height_s = str(image_size).lower().split("x", 1)
        width, height = int(width_s), int(height_s)
        if width <= 0 or height <= 0:
            return None
        return width / height
    except (TypeError, ValueError):
        return None


def image_aspect(width: Optional[int], height: Optional[int]) -> Optional[float]:
    if not width or not height or width <= 0 or height <= 0:
        return None
    return width / height


def has_valid_dimensions(width: Optional[int], height: Optional[int]) -> bool:
    return bool(width and height and width >= MIN_VALID_EDGE and height >= MIN_VALID_EDGE)


def aspect_penalty(
    width: Optional[int],
    height: Optional[int],
    target_aspect: Optional[float],
    *,
    strong: bool,
) -> float:
    if target_aspect is None:
        return 0.0
    aspect = image_aspect(width, height)
    if aspect is None:
        return 0.0
    delta = abs(math.log(aspect / target_aspect))
    weight = SCENE_ASPECT_WEIGHT if strong else PRODUCT_ASPECT_WEIGHT
    return min(1.0, delta) * weight


def resolution_penalty(width: Optional[int], height: Optional[int]) -> float:
    if not has_valid_dimensions(width, height):
        return 100.0
    edge = min(int(width), int(height))
    if edge < SEVERE_UNDERSIZE_EDGE:
        return UNDERSCORE_SEVERE
    if edge < SUFFICIENT_QUALITY_EDGE:
        return UNDERSCORE_MILD * (1.0 - (edge - SEVERE_UNDERSIZE_EDGE) / (
            SUFFICIENT_QUALITY_EDGE - SEVERE_UNDERSIZE_EDGE
        ))
    return 0.0


def diversity_penalty(repeat_count: int) -> float:
    return DIVERSITY_PENALTY * min(max(int(repeat_count), 0), DIVERSITY_CAP)


def suitability_score(
    *,
    width: Optional[int],
    height: Optional[int],
    target_aspect: Optional[float],
    image_type: str,
    primary_repeat_count: int = 0,
    apply_diversity: bool = True,
) -> float:
    """Higher is better. Does not encode semantic content."""
    score = 10.0
    score -= resolution_penalty(width, height)
    score -= aspect_penalty(
        width,
        height,
        target_aspect,
        strong=(image_type == "scene"),
    )
    if apply_diversity:
        score -= diversity_penalty(primary_repeat_count)
    return score


def tie_break_key(sort_index: Optional[int], uploaded_at: Optional[datetime], image_id: str):
    index = sort_index if sort_index is not None else 10**9
    stamp = uploaded_at or datetime.min
    return (index, stamp, str(image_id))
