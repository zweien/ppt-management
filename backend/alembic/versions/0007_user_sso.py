"""user SSO fields (external_id / email / display_name)

Revision ID: 0007_user_sso
Revises: 0006_source_format
Create Date: 2026-07-30

SSO 集成:User 加 external_id(Authentik subject)、email、display_name;
password_hash 改 nullable(SSO 用户无密码)。
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_user_sso"
down_revision = "0006_source_format"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("external_id", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("display_name", sa.String(255), nullable=True))
    op.create_index("ix_users_external_id", "users", ["external_id"])
    # password_hash 改 nullable(原 NOT NULL;SSO 用户无密码)
    op.alter_column("users", "password_hash",
                    existing_type=sa.Text(),
                    nullable=True)


def downgrade() -> None:
    op.alter_column("users", "password_hash",
                    existing_type=sa.Text(),
                    nullable=False)
    op.drop_index("ix_users_external_id", table_name="users")
    op.drop_column("users", "display_name")
    op.drop_column("users", "email")
    op.drop_column("users", "external_id")
