"""Add description here

Revision ID: {revision}
Revises: {down_revision}
Create Date: 2025-09-16 04:57:33

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = {revision!r}
down_revision = {down_revision!r}
branch_labels = {branch_labels!r}
depends_on = {depends_on!r}

def upgrade() -> None:
    """Upgrade database schema."""
    # Modify table users
    op.add_column("users", sa.Column("is_active", sa.Boolean(), server_default=sa.text("True")))
    op.add_column("users", sa.Column("updated_at", sa.DateTime(), server_default="CURRENT_TIMESTAMP"))
    op.add_column("users", sa.Column("full_name", sa.String(200)))
    op.create_index("idx_users_active", "users", ["is_active"])


def downgrade() -> None:
    """Downgrade database schema."""
    # Reverse the upgrade operations
    # This is automatically generated - review before use
    pass