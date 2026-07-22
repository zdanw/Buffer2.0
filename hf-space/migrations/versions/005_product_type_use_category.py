"""align prompt_dimensions.product_type with products.category

Revision ID: 005_ptype_category
Revises: 004_draft_trace
Create Date: 2026-07-22

将历史 snake_case product_type 迁移为素材管理 category 展示名（方案 A）。
"""

from alembic import op
import sqlalchemy as sa


revision = "005_ptype_category"
down_revision = "004_draft_trace"
branch_labels = None
depends_on = None

# 旧技术 key → 素材 category
_LEGACY_TO_CATEGORY = {
    "night_lights": "Night Lights",
    "audio_monitor": "Audio Monitor",
    "air_purifier": "Air Purifiers",
    "video_motion": "Video Monitor",
    "video_monitor": "Video Monitor",
}


def upgrade() -> None:
    conn = op.get_bind()
    for old, new in _LEGACY_TO_CATEGORY.items():
        conn.execute(
            sa.text(
                "UPDATE prompt_dimensions SET product_type = :new "
                "WHERE product_type = :old"
            ),
            {"old": old, "new": new},
        )


def downgrade() -> None:
    conn = op.get_bind()
    category_to_legacy = {
        "Night Lights": "night_lights",
        "Audio Monitor": "audio_monitor",
        "Air Purifiers": "air_purifier",
        "Video Monitor": "video_motion",
    }
    for new, old in category_to_legacy.items():
        conn.execute(
            sa.text(
                "UPDATE prompt_dimensions SET product_type = :old "
                "WHERE product_type = :new"
            ),
            {"old": old, "new": new},
        )
