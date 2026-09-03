"""Add durable output snapshot on generation_runs for admin history.

Revision ID: 046_gen_run_output_snapshot
Revises: 045_qds_selection_events
"""

import sqlalchemy as sa
from alembic import op

revision = "046_gen_run_output_snapshot"
down_revision = "045_qds_selection_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_runs",
        sa.Column("output_snapshot", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generation_runs", "output_snapshot")
