"""Add status, quality, reject_reason columns to asset table.

Revision ID: 0003_asset_quality
Revises: 0002_question_idempotency
Create Date: 2026-07-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_asset_quality"
down_revision: Union[str, Sequence[str], None] = "0002_question_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table: str) -> set[str]:
    bind = op.get_bind()
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    cols = _column_names("asset")
    if "status" not in cols:
        op.add_column("asset", sa.Column("status", sa.String(16), server_default="pending"))
    if "quality" not in cols:
        op.add_column("asset", sa.Column("quality", sa.Integer(), nullable=True))
    if "reject_reason" not in cols:
        op.add_column("asset", sa.Column("reject_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    for col in ("reject_reason", "quality", "status"):
        try:
            op.drop_column("asset", col)
        except Exception:
            pass
