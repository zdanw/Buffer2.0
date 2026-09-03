"""QDS v1 additive selection persistence and decision events.

Revision ID: 045_qds_selection_events
Revises: 044_product_fidelity_guard
"""

import sqlalchemy as sa
from alembic import op

revision = "045_qds_selection_events"
down_revision = "044_product_fidelity_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_runs",
        sa.Column("requested_selector_strategy", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "generation_runs",
        sa.Column("executed_selector_strategy", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "generation_runs",
        sa.Column("selection_seed", sa.String(length=64), nullable=True),
    )
    op.create_table(
        "generation_reference_selections",
        sa.Column("selection_id", sa.String(length=36), primary_key=True),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("generation_run_id", sa.String(length=36), nullable=False),
        sa.Column("selector_version", sa.String(length=64), nullable=False),
        sa.Column("seed", sa.String(length=64), nullable=True),
        sa.Column("strategy", sa.String(length=64), nullable=False),
        sa.Column("requested_strategy", sa.String(length=64), nullable=True),
        sa.Column("executed_strategy", sa.String(length=64), nullable=False),
        sa.Column("risk_profile", sa.String(length=24), nullable=True),
        sa.Column("coverage_class", sa.String(length=24), nullable=True),
        sa.Column("selected_primary_image_id", sa.String(length=36), nullable=True),
        sa.Column("selected_scene_image_id", sa.String(length=36), nullable=True),
        sa.Column("candidate_summary", sa.JSON(), nullable=True),
        sa.Column("selected_manifest", sa.JSON(), nullable=True),
        sa.Column("fingerprint", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["generation_run_id"], ["generation_runs.run_id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("generation_run_id", name="uq_qds_selection_run"),
    )
    op.create_index(
        "ix_qds_selection_owner_created",
        "generation_reference_selections",
        ["owner_user_id", "created_at"],
    )
    op.create_index(
        "ix_qds_selection_run",
        "generation_reference_selections",
        ["generation_run_id"],
    )
    op.create_table(
        "generation_decision_events",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("generation_run_id", sa.String(length=36), nullable=False),
        sa.Column("generation_artifact_id", sa.String(length=36), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=24), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("policy_name", sa.String(length=64), nullable=True),
        sa.Column("policy_version", sa.String(length=32), nullable=True),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["generation_run_id"], ["generation_runs.run_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["generation_artifact_id"],
            ["generation_artifacts.artifact_id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "generation_run_id", "sequence_number", name="uq_decision_event_run_seq"
        ),
    )
    op.create_index("ix_decision_event_run", "generation_decision_events", ["generation_run_id"])
    op.create_index("ix_decision_event_owner", "generation_decision_events", ["owner_user_id"])
    op.create_index("ix_decision_event_type", "generation_decision_events", ["event_type"])
    op.create_index("ix_decision_event_created", "generation_decision_events", ["created_at"])
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text('ALTER TABLE "generation_reference_selections" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "generation_decision_events" ENABLE ROW LEVEL SECURITY'))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text('ALTER TABLE "generation_decision_events" DISABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "generation_reference_selections" DISABLE ROW LEVEL SECURITY'))
    op.drop_index("ix_decision_event_created", table_name="generation_decision_events")
    op.drop_index("ix_decision_event_type", table_name="generation_decision_events")
    op.drop_index("ix_decision_event_owner", table_name="generation_decision_events")
    op.drop_index("ix_decision_event_run", table_name="generation_decision_events")
    op.drop_table("generation_decision_events")
    op.drop_index("ix_qds_selection_run", table_name="generation_reference_selections")
    op.drop_index("ix_qds_selection_owner_created", table_name="generation_reference_selections")
    op.drop_table("generation_reference_selections")
    op.drop_column("generation_runs", "selection_seed")
    op.drop_column("generation_runs", "executed_selector_strategy")
    op.drop_column("generation_runs", "requested_selector_strategy")
