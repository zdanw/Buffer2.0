"""Normalize image providers to one model per config.

Revision ID: 035_single_model_per_provider
Revises: 034_prompt_dimension_name_en
"""

import json

from alembic import op
import sqlalchemy as sa


revision = "035_single_model_per_provider"
down_revision = "034_prompt_dimension_name_en"
branch_labels = None
depends_on = None


def _first_manual_model_id(manual_models) -> str | None:
    if not manual_models:
        return None
    if isinstance(manual_models, str):
        try:
            manual_models = json.loads(manual_models)
        except json.JSONDecodeError:
            return None
    if not isinstance(manual_models, list) or not manual_models:
        return None
    first = manual_models[0]
    if isinstance(first, dict):
        mid = first.get("id") or first.get("model")
        return str(mid).strip() if mid else None
    mid = str(first or "").strip()
    return mid or None


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, default_model, manual_models FROM image_provider_configs"
        )
    ).mappings()
    for row in rows:
        default_model = (row["default_model"] or "").strip() or None
        if not default_model:
            default_model = _first_manual_model_id(row["manual_models"])
        conn.execute(
            sa.text(
                "UPDATE image_provider_configs "
                "SET default_model = :default_model, manual_models = NULL "
                "WHERE id = :id"
            ),
            {"default_model": default_model, "id": row["id"]},
        )


def downgrade() -> None:
    pass
