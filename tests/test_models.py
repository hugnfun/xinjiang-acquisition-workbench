from sidecar.db.session import init_db, get_session, get_engine
from sidecar.db.models import Material, TagDimension, TagValue

def test_create_material(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    init_db()
    s = get_session()
    m = Material(note_id="abc", url="http://x", title="t", author="a", likes=10)
    s.add(m); s.commit()
    assert m.id is not None
    assert s.query(Material).count() == 1

def test_tag_dimension_value_relationship(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    init_db()
    s = get_session()
    d = TagDimension(name="content_type", description="内容类型")
    s.add(d); s.commit()
    s.add(TagValue(dimension_id=d.id, value="风景震撼", alias=[])); s.commit()
    assert len(d.values) == 1
    assert d.values[0].value == "风景震撼"


def test_get_engine_caches_and_invalidates_on_db_path(tmp_path, monkeypatch):
    from sidecar import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "a.db")
    e1 = get_engine()
    e2 = get_engine()
    # 相同 DB_PATH → 同一 engine（缓存命中）
    assert e1 is e2
    # 不同 DB_PATH → 新 engine（缓存失效重建）
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "b.db")
    e3 = get_engine()
    assert e3 is not e1
