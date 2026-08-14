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
    brands = sa.table("brands", sa.column("is_system"), sa.column("slug"))
    # Use boolean bind (not 0/1) so Postgres and SQLite both accept it
    op.execute(brands.update().where(brands.c.slug == "bebcare").values(is_system=False))


def downgrade() -> None:
    brands = sa.table("brands", sa.column("is_system"), sa.column("slug"))
    op.execute(brands.update().where(brands.c.slug == "bebcare").values(is_system=True))
    op.drop_column("brands", "logo_url")
