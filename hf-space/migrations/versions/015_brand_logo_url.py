"""add logo_url on brands; bebcare is not a system brand

Revision ID: 015_brand_logo_url
Revises: 014_brand_voice_flag
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "015_brand_logo_url"
down_revision = "014_brand_voice_flag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("brands", sa.Column("logo_url", sa.String(length=500), nullable=True))
    op.execute("UPDATE brands SET is_system = 0 WHERE slug = 'bebcare'")


def downgrade() -> None:
    op.drop_column("brands", "logo_url")
    op.execute("UPDATE brands SET is_system = 1 WHERE slug = 'bebcare'")
