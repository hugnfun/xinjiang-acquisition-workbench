from pathlib import Path
import scripts.import_from_folder as imp

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "import_root"

def test_import_folder(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    count = imp.import_folder(FIXTURE_ROOT)
    assert count == 1
    from sidecar.db.session import get_session
    from sidecar.db.models import Material, MaterialImage, Comment
    s = get_session()
    mats = s.query(Material).all()
    assert len(mats) == 1
    assert mats[0].title == "测试标题"
    assert mats[0].likes == 14000  # 1.4万 -> 14000
    assert len(mats[0].images) == 2
    assert s.query(Comment).count() == 3
    s.close()
    # 重复执行同一批导入必须幂等跳过。
    assert imp.import_folder(FIXTURE_ROOT) == 0
    s = get_session()
    assert s.query(Material).count() == 1
    assert s.query(Comment).count() == 3
    s.close()


def test_note_id_supports_explore_url_and_hash_fallback():
    from sidecar.importers.note_importer import note_id_from_url
    assert note_id_from_url(
        "https://www.xiaohongshu.com/explore/ABC123?xsec_token=secret"
    ) == "abc123"
    fallback = note_id_from_url("https://example.com/custom/note")
    assert len(fallback) == 32
    assert fallback != "https://example.com/custom/note"
