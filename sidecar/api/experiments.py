from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from sidecar.db.models import (
    Asset,
    ContentExperiment,
    ContentExperimentAsset,
    ExperimentMetricSnapshot,
)
from sidecar.db.session import get_db


router = APIRouter()
VALID_STATUSES = ("draft", "published", "archived")
METRIC_FIELDS = (
    "views", "likes", "collects", "comments", "shares", "inquiries",
    "qualified_leads", "wechat_adds", "quotes", "orders", "revenue_cents",
)


class ExperimentCreateIn(BaseModel):
    asset_ids: list[int]
    platform: str = "xiaohongshu"
    final_title: str = ""
    final_body: str = ""
    cluster_id: int | None = None
    target_audience: str | None = None
    notes: str | None = None


class ExperimentUpdateIn(BaseModel):
    asset_ids: list[int] | None = None
    status: str | None = None
    platform: str | None = None
    final_title: str | None = None
    final_body: str | None = None
    published_url: str | None = None
    published_at: datetime | None = None
    cluster_id: int | None = None
    target_audience: str | None = None
    notes: str | None = None


class MetricCreateIn(BaseModel):
    measured_at: datetime | None = None
    views: int = Field(0, ge=0)
    likes: int = Field(0, ge=0)
    collects: int = Field(0, ge=0)
    comments: int = Field(0, ge=0)
    shares: int = Field(0, ge=0)
    inquiries: int = Field(0, ge=0)
    qualified_leads: int = Field(0, ge=0)
    wechat_adds: int = Field(0, ge=0)
    quotes: int = Field(0, ge=0)
    orders: int = Field(0, ge=0)
    revenue_cents: int = Field(0, ge=0)
    notes: str | None = None


class MetricUpdateIn(BaseModel):
    measured_at: datetime | None = None
    views: int | None = Field(None, ge=0)
    likes: int | None = Field(None, ge=0)
    collects: int | None = Field(None, ge=0)
    comments: int | None = Field(None, ge=0)
    shares: int | None = Field(None, ge=0)
    inquiries: int | None = Field(None, ge=0)
    qualified_leads: int | None = Field(None, ge=0)
    wechat_adds: int | None = Field(None, ge=0)
    quotes: int | None = Field(None, ge=0)
    orders: int | None = Field(None, ge=0)
    revenue_cents: int | None = Field(None, ge=0)
    notes: str | None = None


def _metric_view(m: ExperimentMetricSnapshot) -> dict:
    return {
        "id": m.id,
        "measured_at": m.measured_at.isoformat(),
        **{name: getattr(m, name) for name in METRIC_FIELDS},
        "notes": m.notes,
    }


def _experiment_view(e: ContentExperiment, include_metrics: bool = True) -> dict:
    out = {
        "id": e.id,
        "platform": e.platform,
        "status": e.status,
        "final_title": e.final_title,
        "final_body": e.final_body,
        "published_url": e.published_url,
        "published_at": e.published_at.isoformat() if e.published_at else None,
        "cluster_id": e.cluster_id,
        "target_audience": e.target_audience,
        "notes": e.notes,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
        "assets": [
            {
                "id": link.id,
                "asset_id": link.asset_id,
                "role": link.role,
                "position": link.position,
                "text_snapshot": link.text_snapshot,
            }
            for link in e.asset_links
        ],
    }
    if include_metrics:
        out["metrics"] = [_metric_view(m) for m in e.metric_snapshots]
    elif e.metric_snapshots:
        out["latest_metrics"] = _metric_view(e.metric_snapshots[-1])
    else:
        out["latest_metrics"] = None
    return out


def _ordered_assets(s: Session, asset_ids: list[int]) -> list[Asset]:
    unique_ids = list(dict.fromkeys(asset_ids))
    if not unique_ids:
        raise HTTPException(400, "至少选择一个内容片段")
    found = {a.id: a for a in s.query(Asset).filter(Asset.id.in_(unique_ids)).all()}
    missing = [aid for aid in unique_ids if aid not in found]
    if missing:
        raise HTTPException(404, f"内容片段不存在: {missing}")
    return [found[aid] for aid in unique_ids]


def _replace_assets(
    s: Session, experiment: ContentExperiment, assets: list[Asset]
) -> None:
    experiment.asset_links.clear()
    s.flush()
    for position, asset in enumerate(assets):
        experiment.asset_links.append(ContentExperimentAsset(
            asset_id=asset.id,
            role=asset.type,
            position=position,
            text_snapshot=asset.text,
        ))
        if asset.status not in ("adopted", "published"):
            asset.status = "adopted"


def _check_publish_fields(
    s: Session,
    experiment: ContentExperiment,
    published_url: str | None,
    published_at: datetime | None,
) -> tuple[str, datetime]:
    url = (published_url or "").strip()
    if not url or published_at is None:
        raise HTTPException(400, "发布时必须填写发布链接和发布时间")
    duplicate = s.query(ContentExperiment).filter(
        ContentExperiment.id != experiment.id,
        ContentExperiment.status != "archived",
        ContentExperiment.published_url == url,
    ).first()
    if duplicate:
        raise HTTPException(409, f"发布链接已用于实验 #{duplicate.id}")
    return url, published_at


@router.post("/experiments")
def create_experiment(body: ExperimentCreateIn, s: Session = Depends(get_db)):
    assets = _ordered_assets(s, body.asset_ids)
    if not body.final_title.strip() and not body.final_body.strip():
        raise HTTPException(400, "最终标题和正文不能同时为空")
    experiment = ContentExperiment(
        platform=body.platform.strip() or "xiaohongshu",
        status="draft",
        final_title=body.final_title.strip(),
        final_body=body.final_body.strip(),
        cluster_id=body.cluster_id,
        target_audience=(body.target_audience or "").strip() or None,
        notes=(body.notes or "").strip() or None,
    )
    s.add(experiment)
    _replace_assets(s, experiment, assets)
    s.commit()
    s.refresh(experiment)
    return _experiment_view(experiment)


@router.get("/experiments")
def list_experiments(
    status: str | None = None,
    cluster_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    s: Session = Depends(get_db),
):
    q = s.query(ContentExperiment)
    if status:
        if status not in VALID_STATUSES:
            raise HTTPException(400, "无效实验状态")
        q = q.filter_by(status=status)
    if cluster_id is not None:
        q = q.filter_by(cluster_id=cluster_id)
    total = q.count()
    items = q.order_by(ContentExperiment.updated_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "items": [_experiment_view(e, False) for e in items]}


@router.get("/experiments/analytics")
def experiment_analytics(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    cluster_id: int | None = None,
    s: Session = Depends(get_db),
):
    q = s.query(ContentExperiment).filter(
        ContentExperiment.status.in_(("published", "archived"))
    )
    if cluster_id is not None:
        q = q.filter_by(cluster_id=cluster_id)
    experiments = q.all()
    latest_rows = []
    for experiment in experiments:
        metrics = [
            m for m in experiment.metric_snapshots
            if (date_from is None or m.measured_at >= date_from)
            and (date_to is None or m.measured_at <= date_to)
        ]
        if metrics:
            latest_rows.append((experiment, metrics[-1]))
    totals = {name: sum(getattr(m, name) for _, m in latest_rows) for name in METRIC_FIELDS}
    engagements = totals["likes"] + totals["collects"] + totals["comments"] + totals["shares"]
    views = totals["views"]
    inquiries = totals["inquiries"]

    def rate(numerator: int, denominator: int) -> float:
        return round(numerator / denominator, 6) if denominator else 0

    ranking = sorted(
        (
            {
                "experiment_id": e.id,
                "title": e.final_title,
                "cluster_id": e.cluster_id,
                "measured_at": m.measured_at.isoformat(),
                **{name: getattr(m, name) for name in METRIC_FIELDS},
                "engagement_rate": rate(
                    m.likes + m.collects + m.comments + m.shares, m.views
                ),
                "inquiry_rate": rate(m.inquiries, m.views),
                "order_rate": rate(m.orders, m.inquiries),
            }
            for e, m in latest_rows
        ),
        key=lambda row: (row["orders"], row["inquiries"], row["views"]),
        reverse=True,
    )
    return {
        "published_count": len(experiments),
        "measured_count": len(latest_rows),
        **totals,
        "engagements": engagements,
        "engagement_rate": rate(engagements, views),
        "inquiry_rate": rate(inquiries, views),
        "wechat_rate": rate(totals["wechat_adds"], inquiries),
        "order_rate": rate(totals["orders"], inquiries),
        "ranking": ranking,
    }


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: int, s: Session = Depends(get_db)):
    experiment = s.get(ContentExperiment, experiment_id)
    if not experiment:
        raise HTTPException(404)
    return _experiment_view(experiment)


@router.put("/experiments/{experiment_id}")
def update_experiment(
    experiment_id: int,
    body: ExperimentUpdateIn,
    s: Session = Depends(get_db),
):
    experiment = s.get(ContentExperiment, experiment_id)
    if not experiment:
        raise HTTPException(404)
    data = body.model_dump(exclude_unset=True)
    target_status = data.get("status", experiment.status)
    if target_status not in VALID_STATUSES:
        raise HTTPException(400, "无效实验状态")
    allowed = {
        "draft": {"draft", "published"},
        "published": {"published", "archived"},
        "archived": {"archived"},
    }
    if target_status not in allowed[experiment.status]:
        raise HTTPException(
            409, f"实验状态不能从 {experiment.status} 变为 {target_status}"
        )
    if experiment.status != "draft" and "asset_ids" in data:
        raise HTTPException(409, "仅草稿可修改内容片段")
    if "asset_ids" in data:
        _replace_assets(s, experiment, _ordered_assets(s, data.pop("asset_ids")))
    for field in (
        "platform", "final_title", "final_body", "published_url",
        "published_at", "cluster_id", "target_audience", "notes",
    ):
        if field in data:
            value = data[field]
            if isinstance(value, str):
                value = value.strip()
            setattr(experiment, field, value or None if field in (
                "published_url", "target_audience", "notes"
            ) else value)
    if target_status == "published":
        experiment.published_url, experiment.published_at = _check_publish_fields(
            s, experiment, experiment.published_url, experiment.published_at
        )
        for link in experiment.asset_links:
            if link.asset_id:
                asset = s.get(Asset, link.asset_id)
                if asset:
                    asset.status = "published"
    experiment.status = target_status
    experiment.updated_at = datetime.utcnow()
    s.commit()
    s.refresh(experiment)
    return _experiment_view(experiment)


@router.post("/experiments/{experiment_id}/metrics")
def create_metric(
    experiment_id: int,
    body: MetricCreateIn,
    s: Session = Depends(get_db),
):
    experiment = s.get(ContentExperiment, experiment_id)
    if not experiment:
        raise HTTPException(404)
    if experiment.status != "published":
        raise HTTPException(409, "仅已发布实验可录入指标")
    data = body.model_dump()
    data["measured_at"] = data["measured_at"] or datetime.utcnow()
    metric = ExperimentMetricSnapshot(experiment_id=experiment_id, **data)
    s.add(metric)
    experiment.updated_at = datetime.utcnow()
    s.commit()
    s.refresh(metric)
    return _metric_view(metric)


@router.put("/experiments/{experiment_id}/metrics/{snapshot_id}")
def update_metric(
    experiment_id: int,
    snapshot_id: int,
    body: MetricUpdateIn,
    s: Session = Depends(get_db),
):
    metric = s.get(ExperimentMetricSnapshot, snapshot_id)
    if not metric or metric.experiment_id != experiment_id:
        raise HTTPException(404)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(metric, field, value)
    experiment = s.get(ContentExperiment, experiment_id)
    if experiment:
        experiment.updated_at = datetime.utcnow()
    s.commit()
    s.refresh(metric)
    return _metric_view(metric)
