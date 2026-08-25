"""Add optional English label column for prompt dimensions."""

from alembic import op
import sqlalchemy as sa


revision = "032_prompt_dimension_name_en"
down_revision = "031_calendar_platform_posts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("prompt_dimensions", sa.Column("name_en", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("prompt_dimensions", "name_en")
