"""stripe_subscriptions for cancel/resume + admin refund

Revision ID: 028_stripe_subscriptions
Revises: 027_grant_expires_at
Create Date: 2026-08-22
"""

from alembic import op
import sqlalchemy as sa


revision = "028_stripe_subscriptions"
down_revision = "027_grant_expires_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_users_stripe_customer_id",
        "users",
        ["stripe_customer_id"],
        unique=True,
    )
    op.create_table(
        "stripe_subscriptions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=False),
        sa.Column("price_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("stripe_subscription_id"),
    )
    op.create_index(
        "ix_stripe_subscriptions_user_id",
        "stripe_subscriptions",
        ["user_id"],
    )
    op.create_index(
        "ix_stripe_subscriptions_stripe_customer_id",
        "stripe_subscriptions",
        ["stripe_customer_id"],
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text('ALTER TABLE "stripe_subscriptions" ENABLE ROW LEVEL SECURITY')
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text('ALTER TABLE "stripe_subscriptions" DISABLE ROW LEVEL SECURITY')
        )
    op.drop_index(
        "ix_stripe_subscriptions_stripe_customer_id",
        table_name="stripe_subscriptions",
    )
    op.drop_index(
        "ix_stripe_subscriptions_user_id",
        table_name="stripe_subscriptions",
    )
    op.drop_table("stripe_subscriptions")
    op.drop_index("ix_users_stripe_customer_id", table_name="users")
    op.drop_column("users", "stripe_customer_id")
