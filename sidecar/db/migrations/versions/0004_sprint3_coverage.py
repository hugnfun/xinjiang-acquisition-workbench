"""Sprint 3: asset cluster linkage + token/cost tracking.

Revision ID: 0004_sprint3
Revises: 0003_asset_quality
Create Date: 2026-07-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_sprint3"
down_revision: Union[str, Sequence[str], None] = "0003_asset_quality"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table: str) -> set[str]:
    bind = op.get_bind()
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    asset_cols = _column_names("asset")
    if "cluster_id" not in asset_cols:
        op.add_column("asset", sa.Column("cluster_id", sa.Integer(), nullable=True))
        op.create_index("ix_asset_cluster_id", "asset", ["cluster_id"])
    if "target_audience" not in asset_cols:
        op.add_column("asset", sa.Column("target_audience", sa.Text(), nullable=True))
    if "prompt_version" not in asset_cols:
        op.add_column("asset", sa.Column("prompt_version", sa.String(32), nullable=True))
    if "model_name" not in asset_cols:
        op.add_column("asset", sa.Column("model_name", sa.String(64), nullable=True))
    if "token_usage" not in asset_cols:
        op.add_column("asset", sa.Column("token_usage", sa.JSON(), server_default="{}"))

    job_cols = _column_names("scrape_job")
    if "token_usage" not in job_cols:
        op.add_column("scrape_job", sa.Column("token_usage", sa.JSON(), server_default="{}"))


def downgrade() -> None:
    for col in ("cluster_id", "target_audience", "prompt_version", "model_name", "token_usage"):
        try:
            op.drop_column("asset", col)
        except Exception:
            pass
    try:
        op.drop_column("scrape_job", "token_usage")
    except Exception:
        pass
