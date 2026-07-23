"""Enforce one extracted question per source record.

Revision ID: 0002_question_idempotency
Revises: 0001_sprint0
Create Date: 2026-07-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_question_idempotency"
down_revision: Union[str, Sequence[str], None] = "0001_sprint0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    wanted = {"source_type", "source_ref"}
    existing = any(
        set(item.get("column_names") or []) == wanted
        for item in (
            inspector.get_unique_constraints("question")
            + inspector.get_indexes("question")
        )
        if item.get("unique", True)
    )
    if existing:
        return
    duplicate = op.get_bind().execute(sa.text(
        "SELECT source_type, source_ref, COUNT(*) FROM question "
        "WHERE source_ref IS NOT NULL GROUP BY source_type, source_ref "
        "HAVING COUNT(*) > 1 LIMIT 1"
    )).first()
    if duplicate:
        raise RuntimeError(
            "cannot enforce question source idempotency: duplicate sources exist"
        )
    op.create_index(
        "uq_question_source",
        "question",
        ["source_type", "source_ref"],
        unique=True,
    )


def downgrade() -> None:
    names = {
        item["name"] for item in sa.inspect(op.get_bind()).get_indexes("question")
    }
    if "uq_question_source" in names:
        op.drop_index("uq_question_source", table_name="question")
