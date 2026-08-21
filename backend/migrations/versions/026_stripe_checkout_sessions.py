"""stripe_checkout_sessions + unique stripe grant external_ref

Revision ID: 026_stripe_checkout_sessions
Revises: 025_image_credit_grants
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa


revision = "026_stripe_checkout_sessions"
down_revision = "025_image_credit_grants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stripe_checkout_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("stripe_session_id", sa.String(length=255), nullable=True),
        sa.Column("price_id", sa.String(length=255), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("grant_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("stripe_session_id"),
    )
    op.create_index(
        "ix_stripe_checkout_sessions_user_id",
        "stripe_checkout_sessions",
        ["user_id"],
    )
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_image_credit_stripe_external_ref "
            "ON image_credit_grants (external_ref) "
            "WHERE source = 'stripe' AND external_ref IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS uq_image_credit_stripe_external_ref"))
    op.drop_index(
        "ix_stripe_checkout_sessions_user_id", table_name="stripe_checkout_sessions"
    )
    op.drop_table("stripe_checkout_sessions")
