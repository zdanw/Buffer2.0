"""enable row level security on app tables (no policies)

Revision ID: 023_enable_rls
Revises: 022_owner_backfill_not_null
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa

from bebcare.db.rls_tables import APP_RLS_TABLES


revision = "023_enable_rls"
down_revision = "022_owner_backfill_not_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for name in APP_RLS_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for name in APP_RLS_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{name}" DISABLE ROW LEVEL SECURITY'))
