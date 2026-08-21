"""image_credit_grants.expires_at

Revision ID: 027_grant_expires_at
Revises: 026_stripe_checkout_sessions
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa


revision = "027_grant_expires_at"
down_revision = "026_stripe_checkout_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "image_credit_grants",
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_image_credit_grants_expires_at",
        "image_credit_grants",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_image_credit_grants_expires_at", table_name="image_credit_grants")
    op.drop_column("image_credit_grants", "expires_at")
