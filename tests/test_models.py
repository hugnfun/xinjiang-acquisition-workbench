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
