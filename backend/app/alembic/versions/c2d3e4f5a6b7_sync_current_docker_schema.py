"""Sync current Docker schema

Revision ID: c2d3e4f5a6b7
Revises: b1a2c3d4e5f6
Create Date: 2026-06-14 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from models import Base


revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1a2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _ensure_columns() -> None:
    for table in Base.metadata.sorted_tables:
        existing_columns = _column_names(table.name)
        if not existing_columns:
            continue
        for column in table.columns:
            if column.name not in existing_columns:
                op.add_column(table.name, column.copy())


def _ensure_indexes() -> None:
    bind = op.get_bind()
    for table in Base.metadata.sorted_tables:
        existing_indexes = _index_names(table.name)
        for index in table.indexes:
            if index.name and index.name not in existing_indexes:
                index.create(bind=bind)


def _backfill_message_alias_columns() -> None:
    columns = _column_names("messages")
    if {"created_at", "create_time"}.issubset(columns):
        op.execute(
            sa.text(
                "UPDATE messages SET created_at = create_time "
                "WHERE created_at IS NULL AND create_time IS NOT NULL"
            )
        )
    if {"documents", "retrieval_content"}.issubset(columns):
        op.execute(
            sa.text(
                "UPDATE messages SET documents = retrieval_content "
                "WHERE documents IS NULL AND retrieval_content IS NOT NULL"
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    Base.metadata.create_all(bind=bind)
    _ensure_columns()
    _ensure_indexes()
    _backfill_message_alias_columns()


def downgrade() -> None:
    # This migration is intentionally schema-synchronizing and non-destructive.
    pass
