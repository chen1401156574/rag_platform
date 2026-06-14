"""Add role, status and deleted to users

Revision ID: b1a2c3d4e5f6
Revises: 43c6db52e840
Create Date: 2026-06-13 03:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1a2c3d4e5f6"
down_revision: Union[str, None] = "43c6db52e840"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _column_names("users")
    if "role" not in columns:
        op.add_column(
            "users",
            sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
        )
    if "status" not in columns:
        op.add_column(
            "users",
            sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        )
    if "deleted" not in columns:
        op.add_column(
            "users",
            sa.Column("deleted", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        )


def downgrade() -> None:
    columns = _column_names("users")
    if "deleted" in columns:
        op.drop_column("users", "deleted")
    if "status" in columns:
        op.drop_column("users", "status")
    if "role" in columns:
        op.drop_column("users", "role")
