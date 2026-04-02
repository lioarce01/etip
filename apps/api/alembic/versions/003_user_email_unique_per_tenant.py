"""Add unique constraint on (tenant_id, email) for users table.

Revision ID: 003
Revises: 002
Create Date: 2026-03-31
"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_user_tenant_email",
        "users",
        ["tenant_id", "email"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_user_tenant_email", "users", type_="unique")
