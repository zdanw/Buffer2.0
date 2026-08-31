"""Product Fidelity Guard v1 additive columns.

Revision ID: 044_product_fidelity_guard
Revises: 043_generation_quality_findings
"""

import sqlalchemy as sa
from alembic import op

revision = "044_product_fidelity_guard"
down_revision = "043_generation_quality_findings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_runs",
        sa.Column("product_fidelity_prevention_mode", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "generation_runs",
        sa.Column("visual_fidelity_qa_mode", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "generation_runs",
        sa.Column("visual_fidelity_policy_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "generation_artifact_quality_findings",
        sa.Column(
            "qa_kind",
            sa.String(length=32),
            nullable=False,
            server_default="deterministic",
        ),
    )
    op.add_column(
        "generation_artifact_quality_findings",
        sa.Column("confidence", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "generation_artifact_quality_findings",
        sa.Column("visual_model_version", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "generation_artifact_quality_findings",
        sa.Column("cache_key", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generation_artifact_quality_findings", "cache_key")
    op.drop_column("generation_artifact_quality_findings", "visual_model_version")
    op.drop_column("generation_artifact_quality_findings", "confidence")
    op.drop_column("generation_artifact_quality_findings", "qa_kind")
    op.drop_column("generation_runs", "visual_fidelity_policy_version")
    op.drop_column("generation_runs", "visual_fidelity_qa_mode")
    op.drop_column("generation_runs", "product_fidelity_prevention_mode")
