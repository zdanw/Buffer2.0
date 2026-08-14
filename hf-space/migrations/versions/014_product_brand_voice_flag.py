"""add use_brand_voice on products and onboarding_completed_at on users

Revision ID: 014_brand_voice_flag
Revises: 013_brands
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "014_brand_voice_flag"
down_revision = "013_brands"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("use_brand_voice", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("users", sa.Column("onboarding_completed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "onboarding_completed_at")
    op.drop_column("products", "use_brand_voice")
