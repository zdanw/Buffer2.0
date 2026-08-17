"""change brand voice columns to Text

Revision ID: 018_brand_voice_text
Revises: 017_buffer_accounts
Create Date: 2026-08-17

brands.voice 与 products.brand_voice 由限长 VARCHAR 改为 Text。
"""

from alembic import op
import sqlalchemy as sa


revision = "018_brand_voice_text"
down_revision = "017_buffer_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("brands", schema=None) as batch_op:
        batch_op.alter_column(
            "voice",
            existing_type=sa.String(length=200),
            type_=sa.Text(),
            existing_nullable=True,
        )
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.alter_column(
            "brand_voice",
            existing_type=sa.String(length=100),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.alter_column(
            "brand_voice",
            existing_type=sa.Text(),
            type_=sa.String(length=100),
            existing_nullable=True,
        )
    with op.batch_alter_table("brands", schema=None) as batch_op:
        batch_op.alter_column(
            "voice",
            existing_type=sa.Text(),
            type_=sa.String(length=200),
            existing_nullable=True,
        )
