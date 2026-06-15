"""Add message metadata fields

Revision ID: d4e5f6a7b8c9
Revises: c2d3e4f5a6b7
Create Date: 2026-06-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _column_names("messages")
    if "message_type" not in columns:
        op.add_column(
            "messages",
            sa.Column(
                "message_type",
                sa.String(length=32),
                nullable=False,
                server_default="answer",
            ),
        )
    if "metadata_json" not in columns:
        op.add_column("messages", sa.Column("metadata_json", sa.Text(), nullable=True))


def downgrade() -> None:
    columns = _column_names("messages")
    if "metadata_json" in columns:
        op.drop_column("messages", "metadata_json")
    if "message_type" in columns:
        op.drop_column("messages", "message_type")
