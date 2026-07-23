"""add prompt_dimension_compat_policies

Revision ID: 009_compat_policies
Revises: 008_manual_models
Create Date: 2026-07-23

显式兼容三态：unrestricted / allowlist / blocklist。
存量有边 → allowlist；无边 → 不写策略行（默认 unrestricted = 全部兼容）。
空 allowlist = 都不兼容。
"""

import uuid
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "009_compat_policies"
down_revision = "008_manual_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_dimension_compat_policies",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("dimension_id", sa.String(length=36), nullable=False),
        sa.Column("target_dimension_type", sa.String(length=50), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False, server_default="unrestricted"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["dimension_id"],
            ["prompt_dimensions.dimension_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "dimension_id",
            "target_dimension_type",
            name="uq_compat_policy_dim_target",
        ),
    )
    op.create_index(
        "ix_prompt_dimension_compat_policies_dimension_id",
        "prompt_dimension_compat_policies",
        ["dimension_id"],
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT dimension_id, target_dimension_type, relation_type, is_active
            FROM prompt_dimension_compatibilities
            """
        )
    ).fetchall()
    now = datetime.utcnow()
    seen = set()
    for dimension_id, target_dimension_type, relation_type, is_active in rows:
        if is_active is False or is_active == 0:
            continue
        if (relation_type or "compatible") == "blocked":
            continue
        key = (dimension_id, target_dimension_type)
        if key in seen:
            continue
        seen.add(key)
        conn.execute(
            sa.text(
                """
                INSERT INTO prompt_dimension_compat_policies
                    (id, dimension_id, target_dimension_type, mode, created_at, updated_at)
                VALUES
                    (:id, :dimension_id, :target_dimension_type, 'allowlist', :created_at, :updated_at)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "dimension_id": dimension_id,
                "target_dimension_type": target_dimension_type,
                "created_at": now,
                "updated_at": now,
            },
        )


def downgrade() -> None:
    op.drop_index(
        "ix_prompt_dimension_compat_policies_dimension_id",
        table_name="prompt_dimension_compat_policies",
    )
    op.drop_table("prompt_dimension_compat_policies")
