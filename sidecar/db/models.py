from datetime import datetime
from sqlalchemy import (
    String, Integer, Float, Boolean, Text, DateTime, ForeignKey, JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Material(Base):
    __tablename__ = "material"
    __table_args__ = (
        UniqueConstraint("platform", "note_id", name="uq_material_platform_note_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), default="xiaohongshu")
    note_id: Mapped[str] = mapped_column(String(64), index=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(128))
    author_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    likes: Mapped[int] = mapped_column(Integer, default=0)
    collects: Mapped[int] = mapped_column(Integer, default=0)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    tags_raw: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    local_folder: Mapped[str | None] = mapped_column(Text, nullable=True)
    images: Mapped[list["MaterialImage"]] = relationship(back_populates="material", cascade="all,delete")
    tags: Mapped[list["MaterialTag"]] = relationship(back_populates="material", cascade="all,delete")

class MaterialImage(Base):
    __tablename__ = "material_image"
    __table_args__ = (
        UniqueConstraint("material_id", "idx", name="uq_material_image_position"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("material.id"))
    idx: Mapped[int] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(16), default="image")
    material: Mapped["Material"] = relationship(back_populates="images")

class Comment(Base):
    __tablename__ = "comment"
    __table_args__ = (
        UniqueConstraint("material_id", "rank", name="uq_comment_material_rank"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("material.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    author: Mapped[str] = mapped_column(String(128))
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profile_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    likes: Mapped[int] = mapped_column(Integer, default=0)
    time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    reply_to: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 问题池增量处理游标：pending | question | not_question | excluded
    question_status: Mapped[str] = mapped_column(String(16), default="pending")
    question_processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class TagDimension(Base):
    __tablename__ = "tag_dimension"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    values: Mapped[list["TagValue"]] = relationship(
        back_populates="dimension", cascade="all,delete", order_by="TagValue.id"
    )

class TagValue(Base):
    __tablename__ = "tag_value"
    __table_args__ = (
        UniqueConstraint("dimension_id", "value", name="uq_tag_value_dimension_value"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    dimension_id: Mapped[int] = mapped_column(ForeignKey("tag_dimension.id"))
    value: Mapped[str] = mapped_column(String(64))
    alias: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    dimension: Mapped["TagDimension"] = relationship(back_populates="values")
    material_tags: Mapped[list["MaterialTag"]] = relationship(back_populates="tag_value")

class MaterialTag(Base):
    __tablename__ = "material_tag"
    __table_args__ = (
        UniqueConstraint("material_id", "tag_value_id", name="uq_material_tag_pair"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("material.id"))
    tag_value_id: Mapped[int] = mapped_column(ForeignKey("tag_value.id"))
    source: Mapped[str] = mapped_column(String(16), default="ai")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    confirmed_by_human: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    material: Mapped["Material"] = relationship(back_populates="tags")
    tag_value: Mapped["TagValue"] = relationship(back_populates="material_tags")

class TagSuggestion(Base):
    __tablename__ = "tag_suggestion"
    id: Mapped[int] = mapped_column(primary_key=True)
    dimension_name: Mapped[str] = mapped_column(String(64))
    proposed_value: Mapped[str] = mapped_column(String(64))
    material_id: Mapped[int | None] = mapped_column(ForeignKey("material.id"), nullable=True)
    sample_context: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ScrapeJob(Base):
    __tablename__ = "scrape_job"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # spec §5.5 进度条：已处理 / 总数
    progress: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)

class JobLog(Base):
    __tablename__ = "job_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("scrape_job.id"), index=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

from sqlalchemy import LargeBinary

class QuestionCluster(Base):
    __tablename__ = "question_cluster"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    # spec §5.3 cluster 树可多级：子簇挂到父簇下
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("question_cluster.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    questions: Mapped[list["Question"]] = relationship(back_populates="cluster")

class Question(Base):
    __tablename__ = "question"
    id: Mapped[int] = mapped_column(primary_key=True)
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    source_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), default="comment")
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    cluster_id: Mapped[int | None] = mapped_column(ForeignKey("question_cluster.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    cluster: Mapped["QuestionCluster | None"] = relationship(back_populates="questions")

class Asset(Base):
    __tablename__ = "asset"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(32))  # title|selling_point|hook|cta
    text: Mapped[str] = mapped_column(Text, default="")
    derived_from: Mapped[list] = mapped_column(JSON, default=list)  # [material_id,...]
    tags: Mapped[list] = mapped_column(JSON, default=list)
    disliked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
