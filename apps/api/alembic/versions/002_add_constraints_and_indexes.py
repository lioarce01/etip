"""Add unique constraint on recommendations and missing performance indexes

Revision ID: 002
Revises: 001
Create Date: 2026-04-01
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Unique constraint: one recommendation row per (project, employee)
    op.create_unique_constraint(
        "uq_recommendation_project_employee",
        "recommendations",
        ["project_id", "employee_id"],
    )

    # Index: supports matching deduplication + feedback lookup by project
    op.create_index(
        "ix_recommendations_project_employee",
        "recommendations",
        ["project_id", "employee_id"],
    )

    # Index: availability queries filter on all three columns
    op.create_index(
        "ix_allocations_employee_dates",
        "allocations",
        ["employee_id", "start_date", "end_date"],
    )

    # Index: skill matching joins on both columns
    op.create_index(
        "ix_employee_skills_employee_skill",
        "employee_skills",
        ["employee_id", "skill_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_employee_skills_employee_skill", table_name="employee_skills")
    op.drop_index("ix_allocations_employee_dates", table_name="allocations")
    op.drop_index("ix_recommendations_project_employee", table_name="recommendations")
    op.drop_constraint(
        "uq_recommendation_project_employee", "recommendations", type_="unique"
    )
