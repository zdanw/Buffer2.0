"""Category pose hints and short physics placement text for image prompts."""

from typing import Dict, Optional

CATEGORY_POSE_RULES = {
    "Video Monitor": {
        "default": "台面直立，支架底部接触桌面",
        "reflect": True,
    },
    "Night Lights": {
        "default": "台面或床头柜直立，底部完全接触",
        "reflect": False,
    },
    "Audio Monitor": {
        "default": "台面直立，底部接触",
        "reflect": False,
    },
    "Air Purifiers": {
        "default": "地面或台面直立，底部接触，垂直于地面",
        "reflect": False,
    },
    "Wearable Breast Pump": {
        "default": "平放在台面或托盘中，底部完全接触承托面",
        "reflect": False,
    },
}

_DEFAULT_POSE = {
    "default": "底部接触承托面，姿态稳定自然",
    "reflect": False,
}


def resolve_pose_rule(category: Optional[str] = None) -> Dict:
    key = (category or "").strip()
    return CATEGORY_POSE_RULES.get(key, _DEFAULT_POSE)


def build_physics_placement_block(product_info: Optional[Dict] = None) -> str:
    """Short physics constraints (~50-80 chars of core rules + one pose line)."""
    info = product_info or {}
    category = (info.get("category") or info.get("product_type") or "").strip()
    rule = resolve_pose_rule(category)
    pose = rule.get("default") or _DEFAULT_POSE["default"]
    lines = [
        "产品底部须贴合承托面并带接触阴影，透视与场景一致，禁止悬空与贴纸感。",
        f"摆放：{pose}。",
    ]
    if rule.get("reflect"):
        lines.append("亮面带微弱环境反射。")
    return "\n".join(lines)
