"""add owner_user_id to prompt dimension tables and backfill admin

Revision ID: 024_prompt_dimension_owner
Revises: 023_enable_rls
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa


revision = "024_prompt_dimension_owner"
down_revision = "023_enable_rls"
branch_labels = None
depends_on = None

OWNER_TABLES = (
    "prompt_dimensions",
    "prompt_dimension_compatibilities",
    "prompt_dimension_compat_policies",
)


def _earliest_admin_id(bind):
    if bind.dialect.name == "postgresql":
        sql = (
            "SELECT user_id FROM users WHERE is_admin IS TRUE "
            "ORDER BY created_at ASC LIMIT 1"
        )
    else:
        sql = (
            "SELECT user_id FROM users WHERE is_admin = 1 "
            "ORDER BY created_at ASC LIMIT 1"
        )
    return bind.execute(sa.text(sql)).scalar()


def _null_owner_rows(bind) -> int:
    total = 0
    for table in OWNER_TABLES:
        total += int(
            bind.execute(
                sa.text(f"SELECT COUNT(*) FROM {table} WHERE owner_user_id IS NULL")
            ).scalar()
            or 0
        )
    return total


def upgrade() -> None:
    for table in OWNER_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("owner_user_id", sa.String(length=36), nullable=True)
            )
            batch_op.add_column(
                sa.Column("workspace_id", sa.String(length=36), nullable=True)
            )

    bind = op.get_bind()
    admin_id = _earliest_admin_id(bind)
    nulls = _null_owner_rows(bind)
    if nulls and admin_id is None:
        raise RuntimeError("Cannot backfill owner_user_id without an admin user")
    if admin_id is not None:
        for table in OWNER_TABLES:
            op.execute(
                sa.text(
                    f"UPDATE {table} SET owner_user_id = :aid WHERE owner_user_id IS NULL"
                ).bindparams(aid=admin_id)
            )

    for table in OWNER_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                "owner_user_id",
                existing_type=sa.String(length=36),
                nullable=False,
            )
            batch_op.create_foreign_key(
                f"fk_{table}_owner_user_id",
                "users",
                ["owner_user_id"],
                ["user_id"],
                ondelete="CASCADE",
            )
            batch_op.create_index(f"ix_{table}_owner_user_id", ["owner_user_id"])
            if table == "prompt_dimensions":
                batch_op.drop_constraint(
                    "uq_prompt_dimension_scope_item", type_="unique"
                )
                batch_op.create_unique_constraint(
                    "uq_prompt_dimension_owner_scope_item",
                    ["owner_user_id", "product_type", "dimension_type", "item_id"],
                )


def downgrade() -> None:
    for table in reversed(OWNER_TABLES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            if table == "prompt_dimensions":
                batch_op.drop_constraint(
                    "uq_prompt_dimension_owner_scope_item", type_="unique"
                )
                batch_op.create_unique_constraint(
                    "uq_prompt_dimension_scope_item",
                    ["product_type", "dimension_type", "item_id"],
                )
            batch_op.drop_index(f"ix_{table}_owner_user_id")
            batch_op.drop_constraint(f"fk_{table}_owner_user_id", type_="foreignkey")
            batch_op.drop_column("workspace_id")
            batch_op.drop_column("owner_user_id")
