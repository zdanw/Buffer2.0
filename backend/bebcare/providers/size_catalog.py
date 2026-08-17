"""Image output size catalog by provider type.

Vendor /models endpoints do not expose supported sizes; this module is the
source of truth for preset UI options. Custom WxH strings are also accepted.
"""

import re
from typing import Any, Dict, List, Optional

DEFAULT_SIZE = "2048x2048"
_SIZE_RE = re.compile(r"^(\d{2,5})[xX*](\d{2,5})$")
_MIN_DIM = 64
_MAX_DIM = 8192

# Shared high-res options for Doubao Ark / Aliyun MaaS / OpenAI-compatible gateways
# that accept WxH strings (Aliyun converts x → * in the provider).
_COMMON_SIZES: List[Dict[str, Any]] = [
    {"aspect": "1:1", "size": "2048x2048", "width": 2048, "height": 2048, "label": "1:1"},
    {"aspect": "16:9", "size": "2560x1440", "width": 2560, "height": 1440, "label": "16:9"},
    {"aspect": "9:16", "size": "1440x2560", "width": 1440, "height": 2560, "label": "9:16"},
    {"aspect": "4:3", "size": "2304x1728", "width": 2304, "height": 1728, "label": "4:3"},
    {"aspect": "3:4", "size": "1728x2304", "width": 1728, "height": 2304, "label": "3:4"},
]

_BY_PROVIDER: Dict[str, List[Dict[str, Any]]] = {
    "doubao_ark": _COMMON_SIZES,
    "aliyun_maas": _COMMON_SIZES,
    "openai_compatible": _COMMON_SIZES,
}


def get_size_capabilities(
    provider_type: Optional[str] = None,
    model: Optional[str] = None,  # reserved for future per-model filtering
) -> Dict[str, Any]:
    _ = model
    sizes = _BY_PROVIDER.get(provider_type or "doubao_ark", _COMMON_SIZES)
    return {
        "supported_sizes": sizes,
        "default_size": DEFAULT_SIZE,
        "allow_custom": True,
    }


def normalize_size(size: Optional[str]) -> Optional[str]:
    """Return canonical '{w}x{h}' if size is a valid WxH (or W*H) string."""
    if not size or not isinstance(size, str):
        return None
    m = _SIZE_RE.match(size.strip())
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    if not (_MIN_DIM <= w <= _MAX_DIM and _MIN_DIM <= h <= _MAX_DIM):
        return None
    return f"{w}x{h}"


def resolve_size(size: Optional[str], provider_type: Optional[str] = None) -> str:
    caps = get_size_capabilities(provider_type)
    normalized = normalize_size(size)
    if normalized:
        return normalized
    return caps["default_size"]
