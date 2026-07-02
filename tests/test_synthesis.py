import scripts.seed_taxonomy as seed
import scripts.import_from_folder as imp
from pathlib import Path
from sidecar.jobs import synthesis as sy

def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    seed.seed_taxonomy()
    imp.import_folder(Path(__file__).parent / "fixtures" / "import_root")

def test_run_synthesis_writes_assets(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(sy.tc, "synthesize", lambda mats, types: {
        "selling_points": ["纯玩无购物", "六年零差评"],
        "hooks": ["人生必去一次"],
        "ctas": ["私信定制"],
        "titles": ["新疆10日攻略"],
    })
    from sidecar.db.session import get_session
    from sidecar.db.models import Material, Asset
    s = get_session()
    m = s.query(Material).first()
    sy.run_synthesis([m.id], ["selling_point","hook","cta","title"])

    s2 = get_session()
    assets = s2.query(Asset).all()
    types = {a.type for a in assets}
    assert "selling_point" in types
    assert "hook" in types
    assert "cta" in types
    assert "title" in types
    # derived_from 记录来源
    sp = [a for a in assets if a.type=="selling_point"][0]
    assert m.id in sp.derived_from

def test_run_synthesis_empty_materials_error(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    import pytest
    with pytest.raises(ValueError, match="无素材"):
        sy.run_synthesis([], ["selling_point"])

def test_run_synthesis_sets_job_status_done(tmp_path, monkeypatch):
    """Covers the job_id→ScrapeJob.status path flagged in Task 6 review."""
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(sy.tc, "synthesize", lambda mats, types: {
        "selling_points": ["纯玩无购物"],
    })
    from sidecar.db.session import get_session
    from sidecar.db.models import Material, ScrapeJob
    s = get_session()
    m = s.query(Material).first()
    job = ScrapeJob(type="synthesis", status="queued",
                    params={"material_ids": [m.id], "types": ["selling_point"]})
    s.add(job); s.commit(); s.refresh(job)

    sy.run_synthesis([m.id], ["selling_point"], job_id=job.id)

    s2 = get_session()
    j = s2.query(ScrapeJob).get(job.id)
    assert j.status == "done"
    assert j.result_summary == {"written": 1, "types": ["selling_point"]}
    assert j.finished_at is not None


def test_synthesize_prompt_has_fewshot_and_anticliche():
    """B1: prompt 必须带 few-shot 正反例 + 反套话约束，否则 MiniMax 必出套话。"""
    from sidecar.llm.prompts.synthesis import synthesize_prompt
    system, _ = synthesize_prompt(
        [{"title": "赛里木湖攻略", "content": "7月去的湖水冰蓝", "tags": ["目的地:赛里木湖", "季节:7月"]}],
        ["selling_point", "hook", "cta", "title"],
    )
    # few-shot 正反例都在
    assert "正例" in system and "反例" in system
    # 反套话约束在（禁用套话清单）
    assert "禁用套话" in system and "五感治愈" in system
    # 仍按 types 请求对应 JSON 键
    assert "selling_points" in system and "hooks" in system
    assert "ctas" in system and "titles" in system
