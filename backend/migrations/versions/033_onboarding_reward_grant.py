"""unique onboarding_reward credit grant per user

Revision ID: 033_onboarding_reward_grant
Revises: 032_task_realistic_placement
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa

revision = "033_onboarding_reward_grant"
down_revision = "032_task_realistic_placement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_image_credit_onboarding_reward_per_user "
            "ON image_credit_grants (user_id) WHERE source = 'onboarding_reward'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DROP INDEX IF EXISTS uq_image_credit_onboarding_reward_per_user")
    )
