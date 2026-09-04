"""Clear brand vision_scene overrides so all brands use global scene-fusion rules.

Revision ID: 036_clear_brand_vision
Revises: 035_single_model_per_provider
"""

from alembic import op


revision = "036_clear_brand_vision"
down_revision = "035_single_model_per_provider"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Scene fusion defaults live in prompt_locale; null brand field = global default.
    op.execute(
        """
        UPDATE brands
        SET vision_scene_system_prompt = NULL
        WHERE vision_scene_system_prompt IS NOT NULL
          AND (
            slug IN ('bebcare', 'generic')
            OR vision_scene_system_prompt LIKE '%婴儿产品场景融合%'
            OR vision_scene_system_prompt LIKE '%你写的是图生图指令%'
          )
        """
    )


def downgrade() -> None:
    pass
