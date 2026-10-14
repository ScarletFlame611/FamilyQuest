"""schema

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "families",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("pin_hash", sa.String(length=255), nullable=True),
        sa.Column("pin_failed_attempts", sa.Integer(), nullable=False),
        sa.Column("pin_locked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_families")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)
    op.create_table(
        "goals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("icon", sa.String(length=32), nullable=False),
        sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("target > 0", name=op.f("ck_goals_target_positive")),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["families.id"],
            name=op.f("fk_goals_family_id_families"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goals")),
    )
    op.create_index(op.f("ix_goals_family_id"), "goals", ["family_id"], unique=False)
    op.create_index(
        "uq_goals_active_family",
        "goals",
        ["family_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "adult",
                "child",
                name="member_role",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("avatar", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(role = 'adult') = (user_id IS NOT NULL)", name=op.f("ck_members_adult_has_user")
        ),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["families.id"],
            name=op.f("fk_members_family_id_families"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_members_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_members")),
        sa.UniqueConstraint("user_id", name=op.f("uq_members_user_id")),
    )
    op.create_index(op.f("ix_members_family_id"), "members", ["family_id"], unique=False)
    op.create_table(
        "rewards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("icon", sa.String(length=32), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price > 0", name=op.f("ck_rewards_price_positive")),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["families.id"],
            name=op.f("fk_rewards_family_id_families"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rewards")),
    )
    op.create_index(op.f("ix_rewards_family_id"), "rewards", ["family_id"], unique=False)
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("balance", sa.Integer(), nullable=False),
        sa.Column("reserved", sa.Integer(), nullable=False),
        sa.CheckConstraint("reserved >= 0", name=op.f("ck_accounts_reserved_not_negative")),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["families.id"],
            name=op.f("fk_accounts_family_id_families"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_accounts_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
        sa.UniqueConstraint("member_id", name=op.f("uq_accounts_member_id")),
    )
    op.create_index(op.f("ix_accounts_family_id"), "accounts", ["family_id"], unique=False)
    op.create_table(
        "child_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_member_id", sa.Uuid(), nullable=False),
        sa.Column("started_by_member_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["child_member_id"],
            ["members.id"],
            name=op.f("fk_child_sessions_child_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["started_by_member_id"],
            ["members.id"],
            name=op.f("fk_child_sessions_started_by_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_child_sessions")),
    )
    op.create_index(
        op.f("ix_child_sessions_child_member_id"),
        "child_sessions",
        ["child_member_id"],
        unique=False,
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_idempotency_keys_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("member_id", "key", name=op.f("pk_idempotency_keys")),
    )
    op.create_table(
        "reward_purchases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("reward_id", sa.Uuid(), nullable=False),
        sa.Column("child_member_id", sa.Uuid(), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "given",
                "cancelled",
                name="purchase_status",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("cancel_reason", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("price > 0", name=op.f("ck_reward_purchases_price_positive")),
        sa.ForeignKeyConstraint(
            ["child_member_id"],
            ["members.id"],
            name=op.f("fk_reward_purchases_child_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["families.id"],
            name=op.f("fk_reward_purchases_family_id_families"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reward_id"],
            ["rewards.id"],
            name=op.f("fk_reward_purchases_reward_id_rewards"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reward_purchases")),
    )
    op.create_index(
        op.f("ix_reward_purchases_child_member_id"),
        "reward_purchases",
        ["child_member_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reward_purchases_family_id"), "reward_purchases", ["family_id"], unique=False
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("icon", sa.String(length=32), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("assignee_member_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_member_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "assigned",
                "marked",
                "confirmed",
                name="task_status",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("reject_reason", sa.String(length=300), nullable=True),
        sa.Column("marked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(status = 'open') = (assignee_member_id IS NULL)",
            name=op.f("ck_tasks_open_has_no_assignee"),
        ),
        sa.CheckConstraint("points > 0", name=op.f("ck_tasks_points_positive")),
        sa.ForeignKeyConstraint(
            ["assignee_member_id"],
            ["members.id"],
            name=op.f("fk_tasks_assignee_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_member_id"],
            ["members.id"],
            name=op.f("fk_tasks_created_by_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["families.id"],
            name=op.f("fk_tasks_family_id_families"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    op.create_index(
        op.f("ix_tasks_assignee_member_id"), "tasks", ["assignee_member_id"], unique=False
    )
    op.create_index(op.f("ix_tasks_family_id"), "tasks", ["family_id"], unique=False)
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "accrual",
                "reserve",
                "release",
                "spend",
                "reversal",
                name="entry_kind",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("purchase_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount <> 0", name=op.f("ck_ledger_entries_amount_not_zero")),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_ledger_entries_account_id_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_id"],
            ["reward_purchases.id"],
            name=op.f("fk_ledger_entries_purchase_id_reward_purchases"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_ledger_entries_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ledger_entries")),
    )
    op.create_index(
        op.f("ix_ledger_entries_account_id"), "ledger_entries", ["account_id"], unique=False
    )
    op.create_index(
        op.f("ix_ledger_entries_created_at"), "ledger_entries", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_ledger_entries_purchase_id"), "ledger_entries", ["purchase_id"], unique=False
    )
    op.create_index(
        "uq_ledger_entries_accrual_task",
        "ledger_entries",
        ["task_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'accrual'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_ledger_entries_accrual_task",
        table_name="ledger_entries",
        postgresql_where=sa.text("kind = 'accrual'"),
    )
    op.drop_index(op.f("ix_ledger_entries_purchase_id"), table_name="ledger_entries")
    op.drop_index(op.f("ix_ledger_entries_created_at"), table_name="ledger_entries")
    op.drop_index(op.f("ix_ledger_entries_account_id"), table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index(op.f("ix_tasks_family_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_assignee_member_id"), table_name="tasks")
    op.drop_table("tasks")
    op.drop_index(op.f("ix_reward_purchases_family_id"), table_name="reward_purchases")
    op.drop_index(op.f("ix_reward_purchases_child_member_id"), table_name="reward_purchases")
    op.drop_table("reward_purchases")
    op.drop_table("idempotency_keys")
    op.drop_index(op.f("ix_child_sessions_child_member_id"), table_name="child_sessions")
    op.drop_table("child_sessions")
    op.drop_index(op.f("ix_accounts_family_id"), table_name="accounts")
    op.drop_table("accounts")
    op.drop_index(op.f("ix_rewards_family_id"), table_name="rewards")
    op.drop_table("rewards")
    op.drop_index(op.f("ix_members_family_id"), table_name="members")
    op.drop_table("members")
    op.drop_index(
        "uq_goals_active_family", table_name="goals", postgresql_where=sa.text("is_active")
    )
    op.drop_index(op.f("ix_goals_family_id"), table_name="goals")
    op.drop_table("goals")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
    op.drop_table("families")
