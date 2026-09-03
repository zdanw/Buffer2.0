"""Phase 1B additive: persist GenerationPlan JSON on generation_runs.

Revision ID: 039_generation_plan
Revises: 038_grounded_gen_foundation
"""

import sqlalchemy as sa
from alembic import op

revision = "039_generation_plan"
down_revision = "038_grounded_gen_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_runs",
        sa.Column("generation_plan", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generation_runs", "generation_plan")
