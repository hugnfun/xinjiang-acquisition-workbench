"""Sprint 3 content experiments and metric snapshots.

Revision ID: 0005_experiments
Revises: 0004_sprint3
Create Date: 2026-07-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_experiments"
down_revision: Union[str, Sequence[str], None] = "0004_sprint3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "source_job_id" not in _column_names("asset"):
        op.add_column("asset", sa.Column("source_job_id", sa.Integer(), nullable=True))
        op.create_index("ix_asset_source_job_id", "asset", ["source_job_id"])

    tables = _table_names()
    if "content_experiment" not in tables:
        op.create_table(
            "content_experiment",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("platform", sa.String(32), nullable=False, server_default="xiaohongshu"),
            sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
            sa.Column("final_title", sa.Text(), nullable=False, server_default=""),
            sa.Column("final_body", sa.Text(), nullable=False, server_default=""),
            sa.Column("published_url", sa.Text(), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("cluster_id", sa.Integer(), sa.ForeignKey("question_cluster.id", ondelete="SET NULL"), nullable=True),
            sa.Column("target_audience", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint(
                "status IN ('draft', 'published', 'archived')",
                name="ck_content_experiment_status",
            ),
        )
        op.create_index("ix_content_experiment_status", "content_experiment", ["status"])
        op.create_index("ix_content_experiment_cluster_id", "content_experiment", ["cluster_id"])

    tables = _table_names()
    if "content_experiment_asset" not in tables:
        op.create_table(
            "content_experiment_asset",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("content_experiment.id", ondelete="CASCADE"), nullable=False),
            sa.Column("asset_id", sa.Integer(), sa.ForeignKey("asset.id", ondelete="SET NULL"), nullable=True),
            sa.Column("role", sa.String(32), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("text_snapshot", sa.Text(), nullable=False, server_default=""),
            sa.UniqueConstraint("experiment_id", "asset_id", name="uq_content_experiment_asset_pair"),
        )
        op.create_index("ix_content_experiment_asset_experiment_id", "content_experiment_asset", ["experiment_id"])
        op.create_index("ix_content_experiment_asset_asset_id", "content_experiment_asset", ["asset_id"])

    tables = _table_names()
    if "experiment_metric_snapshot" not in tables:
        metric_columns = [
            sa.Column(name, sa.Integer(), nullable=False, server_default="0")
            for name in (
                "views", "likes", "collects", "comments", "shares",
                "inquiries", "qualified_leads", "wechat_adds", "quotes",
                "orders", "revenue_cents",
            )
        ]
        constraints = [
            sa.CheckConstraint(f"{name} >= 0", name=f"ck_metric_{name}_nonnegative")
            for name in (
                "views", "likes", "collects", "comments", "shares",
                "inquiries", "qualified_leads", "wechat_adds", "quotes",
                "orders", "revenue_cents",
            )
        ]
        op.create_table(
            "experiment_metric_snapshot",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("content_experiment.id", ondelete="CASCADE"), nullable=False),
            sa.Column("measured_at", sa.DateTime(), nullable=False),
            *metric_columns,
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            *constraints,
        )
        op.create_index("ix_experiment_metric_snapshot_experiment_id", "experiment_metric_snapshot", ["experiment_id"])
        op.create_index("ix_experiment_metric_snapshot_measured_at", "experiment_metric_snapshot", ["measured_at"])


def downgrade() -> None:
    for table in (
        "experiment_metric_snapshot",
        "content_experiment_asset",
        "content_experiment",
    ):
        if table in _table_names():
            op.drop_table(table)
    if "source_job_id" in _column_names("asset"):
        try:
            op.drop_index("ix_asset_source_job_id", table_name="asset")
        except Exception:
            pass
        op.drop_column("asset", "source_job_id")
