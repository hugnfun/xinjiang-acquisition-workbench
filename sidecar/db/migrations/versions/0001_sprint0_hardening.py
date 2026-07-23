"""Sprint 0 schema hardening for legacy create_all databases.

Revision ID: 0001_sprint0
Revises:
Create Date: 2026-07-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_sprint0"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _has_unique_columns(table: str, columns: tuple[str, ...]) -> bool:
    inspector = sa.inspect(op.get_bind())
    wanted = set(columns)
    for item in inspector.get_unique_constraints(table):
        if set(item.get("column_names") or []) == wanted:
            return True
    for item in inspector.get_indexes(table):
        if item.get("unique") and set(item.get("column_names") or []) == wanted:
            return True
    return False


def _assert_no_duplicates(table: str, columns: tuple[str, ...]) -> None:
    quoted = ", ".join(f'"{c}"' for c in columns)
    row = op.get_bind().execute(sa.text(
        f'SELECT {quoted}, COUNT(*) AS n FROM "{table}" '
        f"GROUP BY {quoted} HAVING COUNT(*) > 1 LIMIT 1"
    )).first()
    if row:
        raise RuntimeError(
            f"cannot add unique constraint to {table}({', '.join(columns)}): "
            "duplicate rows exist"
        )


def _create_unique_index(name: str, table: str, columns: tuple[str, ...]) -> None:
    if _has_unique_columns(table, columns):
        return
    _assert_no_duplicates(table, columns)
    op.create_index(name, table, list(columns), unique=True)


def upgrade() -> None:
    comment_columns = _column_names("comment")
    if "question_status" not in comment_columns:
        op.add_column(
            "comment",
            sa.Column("question_status", sa.String(length=16), nullable=False,
                      server_default="pending"),
        )
    if "question_processed_at" not in comment_columns:
        op.add_column(
            "comment",
            sa.Column("question_processed_at", sa.DateTime(), nullable=True),
        )

    job_columns = _column_names("scrape_job")
    if "progress" not in job_columns:
        op.add_column(
            "scrape_job",
            sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        )
    if "progress_total" not in job_columns:
        op.add_column(
            "scrape_job",
            sa.Column("progress_total", sa.Integer(), nullable=False, server_default="0"),
        )
    if "cancel_requested" not in job_columns:
        op.add_column(
            "scrape_job",
            sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    cluster_columns = _column_names("question_cluster")
    if "parent_id" not in cluster_columns:
        op.add_column(
            "question_cluster",
            sa.Column("parent_id", sa.Integer(), nullable=True),
        )

    # 已经产出 Question 的评论视为处理完成；其余历史顶层评论保持 pending，
    # 由下一次增量任务明确判定，避免把潜在问题永久跳过。
    op.execute(sa.text(
        "UPDATE comment SET question_status='question', "
        "question_processed_at=CURRENT_TIMESTAMP "
        "WHERE id IN (SELECT source_ref FROM question "
        "WHERE source_type='comment' AND source_ref IS NOT NULL)"
    ))
    op.execute(sa.text(
        "UPDATE comment SET question_status='excluded', "
        "question_processed_at=CURRENT_TIMESTAMP "
        "WHERE is_reply=1 AND question_status='pending'"
    ))

    _create_unique_index(
        "uq_material_platform_note_id", "material", ("platform", "note_id")
    )
    _create_unique_index(
        "uq_material_image_position", "material_image", ("material_id", "idx")
    )
    _create_unique_index(
        "uq_comment_material_rank", "comment", ("material_id", "rank")
    )
    _create_unique_index(
        "uq_tag_value_dimension_value", "tag_value", ("dimension_id", "value")
    )
    _create_unique_index(
        "uq_material_tag_pair", "material_tag", ("material_id", "tag_value_id")
    )


def downgrade() -> None:
    # SQLite 上删除列需要重建表；Sprint 0 只支持向前升级，避免破坏用户数据。
    for name, table in (
        ("uq_material_tag_pair", "material_tag"),
        ("uq_tag_value_dimension_value", "tag_value"),
        ("uq_comment_material_rank", "comment"),
        ("uq_material_image_position", "material_image"),
        ("uq_material_platform_note_id", "material"),
    ):
        indexes = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}
        if name in indexes:
            op.drop_index(name, table_name=table)
