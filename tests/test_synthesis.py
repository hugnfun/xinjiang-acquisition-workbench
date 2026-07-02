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
