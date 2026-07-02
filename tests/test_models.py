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


from sidecar.db.models import Question, QuestionCluster, Asset

def test_question_and_cluster(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    init_db()
    s = get_session()
    cl = QuestionCluster(name="季节", description="出行时间")
    s.add(cl); s.commit()
    q = Question(normalized_text="几月去新疆好", raw_text="几月去新疆好",
                source_ref=1, source_type="comment", cluster_id=cl.id)
    s.add(q); s.commit()
    assert q.id is not None
    assert cl.id is not None
    assert s.query(Question).count() == 1

def test_question_embedding_blob(tmp_path, monkeypatch):
    import numpy as np
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    init_db()
    s = get_session()
    vec = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    q = Question(normalized_text="t", raw_text="t", source_ref=1,
                 source_type="comment", embedding=vec.tobytes())
    s.add(q); s.commit()
    loaded = s.query(Question).first()
    arr = np.frombuffer(loaded.embedding, dtype=np.float32)
    assert list(arr) == [0.1, 0.2, 0.3]

def test_asset_derived_from(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    init_db()
    s = get_session()
    a = Asset(type="selling_point", text="纯玩无购物",
              derived_from=[1, 2, 3], tags=["风景震撼"], disliked=False)
    s.add(a); s.commit()
    loaded = s.query(Asset).first()
    assert loaded.type == "selling_point"
    assert loaded.derived_from == [1, 2, 3]
    assert loaded.tags == ["风景震撼"]
    assert loaded.disliked is False
