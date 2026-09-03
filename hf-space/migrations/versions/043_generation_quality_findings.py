"""Phase 3A additive quality findings and run provenance.

Revision ID: 043_generation_quality_findings
Revises: 042_analysis_retry_policy
"""

import sqlalchemy as sa
from alembic import op

revision = "043_generation_quality_findings"
down_revision = "042_analysis_retry_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_runs",
        sa.Column("quality_protection_mode", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "generation_runs",
        sa.Column("quality_policy_version", sa.String(length=32), nullable=True),
    )
    op.create_table(
        "generation_artifact_quality_findings",
        sa.Column("finding_id", sa.String(length=36), primary_key=True),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("artifact_id", sa.String(length=36), nullable=True),
        sa.Column("generation_run_id", sa.String(length=36), nullable=False),
        sa.Column("stage", sa.String(length=24), nullable=False),
        sa.Column("check_code", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.user_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["generation_artifacts.artifact_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["generation_run_id"],
            ["generation_runs.run_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_qa_findings_run", "generation_artifact_quality_findings", ["generation_run_id"])
    op.create_index("ix_qa_findings_artifact", "generation_artifact_quality_findings", ["artifact_id"])
    op.create_index("ix_qa_findings_severity", "generation_artifact_quality_findings", ["severity"])
    op.create_index("ix_qa_findings_stage", "generation_artifact_quality_findings", ["stage"])
    op.create_index(
        "ix_qa_findings_hard",
        "generation_artifact_quality_findings",
        ["passed", "severity"],
    )
    op.create_index("ix_qa_findings_owner", "generation_artifact_quality_findings", ["owner_user_id"])
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                'ALTER TABLE "generation_artifact_quality_findings" ENABLE ROW LEVEL SECURITY'
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                'ALTER TABLE "generation_artifact_quality_findings" DISABLE ROW LEVEL SECURITY'
            )
        )
    op.drop_index("ix_qa_findings_owner", table_name="generation_artifact_quality_findings")
    op.drop_index("ix_qa_findings_hard", table_name="generation_artifact_quality_findings")
    op.drop_index("ix_qa_findings_stage", table_name="generation_artifact_quality_findings")
    op.drop_index("ix_qa_findings_severity", table_name="generation_artifact_quality_findings")
    op.drop_index("ix_qa_findings_artifact", table_name="generation_artifact_quality_findings")
    op.drop_index("ix_qa_findings_run", table_name="generation_artifact_quality_findings")
    op.drop_table("generation_artifact_quality_findings")
    op.drop_column("generation_runs", "quality_policy_version")
    op.drop_column("generation_runs", "quality_protection_mode")
