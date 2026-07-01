import scripts.seed_taxonomy as seed

def test_seed_creates_content_type(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    seed.seed_taxonomy()
    seed.seed_taxonomy()  # 幂等
    from sidecar.db.session import get_session
    from sidecar.db.models import TagDimension, TagValue
    s = get_session()
    d = s.query(TagDimension).filter_by(name="content_type").one()
    assert len(d.values) == 6
    assert d.values[0].value == "风景震撼"

def test_seed_other_dimensions(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    seed.seed_taxonomy()
    from sidecar.db.session import get_session
    from sidecar.db.models import TagDimension
    s = get_session()
    names = {d.name for d in s.query(TagDimension).all()}
    assert {"content_type", "season", "audience", "route", "price", "emotion"} <= names
