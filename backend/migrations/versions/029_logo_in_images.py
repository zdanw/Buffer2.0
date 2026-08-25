"""add logo_in_images on brands; has_on_body_branding on products

Revision ID: 029_logo_in_images
Revises: 028_stripe_subscriptions
Create Date: 2026-08-24
"""

from alembic import op
import sqlalchemy as sa

revision = "029_logo_in_images"
down_revision = "028_stripe_subscriptions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "brands",
        sa.Column(
            "logo_in_images",
            sa.String(length=32),
            nullable=False,
            server_default="preserve",
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "has_on_body_branding",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade():
    op.drop_column("products", "has_on_body_branding")
    op.drop_column("brands", "logo_in_images")
