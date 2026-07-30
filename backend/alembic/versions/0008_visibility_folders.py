"""visibility + folders + is_superuser default change

Revision ID: 0008_visibility_folders
Revises: 0007_user_sso
Create Date: 2026-07-30

- Presentation.visibility(team/private,默认 team,团队私有素材)
- Presentation.folder_id(单层文件夹归类)
- folders 表
- User.is_superuser 默认改 False(仅显式超管;SSO 用户默认普通)
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_visibility_folders"
down_revision = "0007_user_sso"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # folders 表(先建,因 presentations.folder_id 引用它)
    op.create_table(
        "folders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # presentations 加 visibility + folder_id
    op.add_column(
        "presentations",
        sa.Column("visibility", sa.String(20), nullable=False, server_default="team"),
    )
    op.add_column(
        "presentations",
        sa.Column("folder_id", sa.String(36), sa.ForeignKey("folders.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_presentations_visibility", "presentations", ["visibility"])
    op.create_index("ix_presentations_folder_id", "presentations", ["folder_id"])

    # User.is_superuser 默认改 False。
    # 存量:已是超管的保留 True;非超管显式置 False(原本列默认 True 可能误置)。
    # 这里不改列默认(DB 层),仅回填数据:保留现有 is_superuser=true 的;其余置 false。
    # 新行由 ORM default 控制(model 已改 False)。
    op.execute(
        "UPDATE users SET is_superuser = false WHERE is_superuser IS NULL OR username NOT IN "
        "(SELECT username FROM users WHERE is_superuser = true)"
    )


def downgrade() -> None:
    op.drop_index("ix_presentations_folder_id", table_name="presentations")
    op.drop_index("ix_presentations_visibility", table_name="presentations")
    op.drop_column("presentations", "folder_id")
    op.drop_column("presentations", "visibility")
    op.drop_table("folders")
