"""child_profile

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("members", sa.Column("age_group", sa.String(length=16), nullable=True))
    op.add_column(
        "members", sa.Column("parent_consent_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_members_age_group"), "members", "age_group IN ('6-7', '8-10', '11-13')"
    )
    # Уже существующих детей создавал сценарий наполнения от имени взрослого: согласие
    # считается данным в момент создания, группа — младшая, под которую делается PoC
    op.execute(
        "UPDATE members SET age_group = '6-7', parent_consent_at = created_at "
        "WHERE role = 'child'"
    )
    op.create_check_constraint(
        op.f("ck_members_child_profile_complete"),
        "members",
        "role <> 'child' OR (age_group IS NOT NULL AND parent_consent_at IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_members_child_profile_complete"), "members", type_="check")
    op.drop_constraint(op.f("ck_members_age_group"), "members", type_="check")
    op.drop_column("members", "parent_consent_at")
    op.drop_column("members", "age_group")
