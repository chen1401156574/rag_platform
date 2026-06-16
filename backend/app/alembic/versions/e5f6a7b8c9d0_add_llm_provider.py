"""add llm provider table"""

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "t_llm_provider",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("encrypted_api_key", sa.Text, nullable=False),
        sa.Column("enabled_models", sa.Text, nullable=False, server_default="[]"),
        sa.Column("is_active", sa.SmallInteger, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("t_llm_provider")
