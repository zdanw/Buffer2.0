"""add buffer accounts and brand binding

Revision ID: 017_buffer_accounts
Revises: 016_dimension_scope_unique
Create Date: 2026-08-17

多 Buffer 账户：加密存储 token，品牌通过 buffer_account_id 绑定。
"""

from alembic import op
import sqlalchemy as sa


revision = "017_buffer_accounts"
down_revision = "016_dimension_scope_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "buffer_accounts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("api_token_encrypted", sa.Text(), nullable=False),
        sa.Column("buffer_email", sa.String(length=255), nullable=True),
        sa.Column("buffer_remote_id", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    # SQLite cannot ALTER TABLE to add FKs; use batch copy-and-move.
    with op.batch_alter_table("brands", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("buffer_account_id", sa.String(length=36), nullable=True)
        )
        batch_op.create_index("ix_brands_buffer_account_id", ["buffer_account_id"])
        batch_op.create_foreign_key(
            "fk_brands_buffer_account_id",
            "buffer_accounts",
            ["buffer_account_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("brands", schema=None) as batch_op:
        batch_op.drop_constraint("fk_brands_buffer_account_id", type_="foreignkey")
        batch_op.drop_index("ix_brands_buffer_account_id")
        batch_op.drop_column("buffer_account_id")
    op.drop_table("buffer_accounts")
