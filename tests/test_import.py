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
