"""image credit grants, system provider flag, task provider mode

Revision ID: 025_image_credit_grants
Revises: 024_prompt_dimension_owner
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa
import uuid


revision = "025_image_credit_grants"
down_revision = "024_prompt_dimension_owner"
branch_labels = None
depends_on = None

SIGNUP_TRIAL_QTY = 2


def upgrade() -> None:
    bind = op.get_bind()

    with op.batch_alter_table("image_provider_configs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_system",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    # Allow NULL owner for system (platform) providers.
    with op.batch_alter_table("image_provider_configs", schema=None) as batch_op:
        batch_op.alter_column(
            "owner_user_id",
            existing_type=sa.String(length=36),
            nullable=True,
        )

    op.create_table(
        "image_credit_grants",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("remaining", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("external_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_image_credit_grants_user_id", "image_credit_grants", ["user_id"]
    )
    # At most one signup_trial grant per user (partial unique; SQLite + Postgres).
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_image_credit_signup_trial_per_user "
            "ON image_credit_grants (user_id) WHERE source = 'signup_trial'"
        )
    )

    op.create_table(
        "image_credit_reservations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("generate_task_id", sa.String(length=36), nullable=False),
        sa.Column("grant_id", sa.String(length=36), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["generate_task_id"], ["generate_tasks.task_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["grant_id"], ["image_credit_grants.id"]),
        sa.UniqueConstraint("generate_task_id"),
    )
    op.create_index(
        "ix_image_credit_reservations_user_id",
        "image_credit_reservations",
        ["user_id"],
    )

    with op.batch_alter_table("scheduled_tasks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("image_provider_mode", sa.String(length=16), nullable=True)
        )

    # Backfill signup_trial for users with no grants yet.
    users = bind.execute(sa.text("SELECT user_id FROM users")).fetchall()
    existing = {
        row[0]
        for row in bind.execute(
            sa.text("SELECT DISTINCT user_id FROM image_credit_grants")
        ).fetchall()
    }
    for (user_id,) in users:
        if user_id in existing:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO image_credit_grants "
                "(id, user_id, source, quantity, remaining, status, note, "
                "external_ref, created_at, updated_at) "
                "VALUES (:id, :user_id, 'signup_trial', :qty, :qty, 'active', "
                "NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"id": str(uuid.uuid4()), "user_id": user_id, "qty": SIGNUP_TRIAL_QTY},
        )

    if bind.dialect.name == "postgresql":
        for name in ("image_credit_grants", "image_credit_reservations"):
            op.execute(sa.text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for name in ("image_credit_reservations", "image_credit_grants"):
            op.execute(sa.text(f'ALTER TABLE "{name}" DISABLE ROW LEVEL SECURITY'))

    with op.batch_alter_table("scheduled_tasks", schema=None) as batch_op:
        batch_op.drop_column("image_provider_mode")

    op.drop_index(
        "ix_image_credit_reservations_user_id", table_name="image_credit_reservations"
    )
    op.drop_table("image_credit_reservations")
    op.drop_index(
        "uq_image_credit_signup_trial_per_user", table_name="image_credit_grants"
    )
    op.drop_index("ix_image_credit_grants_user_id", table_name="image_credit_grants")
    op.drop_table("image_credit_grants")

    with op.batch_alter_table("image_provider_configs", schema=None) as batch_op:
        batch_op.drop_column("is_system")
        batch_op.alter_column(
            "owner_user_id",
            existing_type=sa.String(length=36),
            nullable=False,
        )
