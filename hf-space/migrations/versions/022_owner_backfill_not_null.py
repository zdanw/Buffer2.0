"""backfill owner_user_id onto earliest admin, then NOT NULL + FK/index

Revision ID: 022_owner_backfill_not_null
Revises: 021_owner_workspace
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa


revision = "022_owner_backfill_not_null"
down_revision = "021_owner_workspace"
branch_labels = None
depends_on = None

OWNER_TABLES = (
    "brands",
    "products",
    "scheduled_tasks",
    "task_executions",
    "manual_task_drafts",
    "publish_records",
    "generate_tasks",
    "image_provider_configs",
    "buffer_accounts",
)


def _earliest_admin_id(bind):
    # SQLite stores bool as 0/1; PostgreSQL uses true/false. Integer compare
    # fails on PG, so pick the predicate per dialect.
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
    bind = op.get_bind()
    admin_id = _earliest_admin_id(bind)
    nulls = _null_owner_rows(bind)
    # Fresh empty databases have tenant tables but no rows and no admin yet
    # (initialize_data runs after migrations). Skip backfill; NOT NULL is still
    # valid. Existing 021 databases with orphan owners still require an admin.
    # Databases already past 022 never re-run this revision.
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
            if table == "brands":
                batch_op.drop_index("ix_brands_slug")
                batch_op.create_unique_constraint(
                    "uq_brands_owner_slug",
                    ["owner_user_id", "slug"],
                )


def downgrade() -> None:
    # Drop constraints/indexes/FKs and make owner_user_id nullable again.
    # Do not undo the admin backfill (no restore of global-sharing semantics).
    for table in reversed(OWNER_TABLES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            if table == "brands":
                batch_op.drop_constraint("uq_brands_owner_slug", type_="unique")
                batch_op.create_index("ix_brands_slug", ["slug"], unique=True)
            batch_op.drop_index(f"ix_{table}_owner_user_id")
            batch_op.drop_constraint(f"fk_{table}_owner_user_id", type_="foreignkey")
            batch_op.alter_column(
                "owner_user_id",
                existing_type=sa.String(length=36),
                nullable=True,
            )
