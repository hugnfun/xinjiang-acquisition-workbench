"""Work Vault 解析器与导入器测试。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sidecar.importers.work_vault import (
    parse_work_vault_note, scan_vault, insert_work_vault_note, ScanItem,
    backfill_work_vault_authors, extract_material_author,
)
from sidecar.db.session import get_session
from sidecar.db.models import Material, MaterialImage, Comment

FIXTURE = Path(__file__).parent / "fixtures" / "work_vault_sample.md"


# ── 解析器 ──

def test_parse_body_and_tags():
    p = parse_work_vault_note(FIXTURE.read_text(encoding="utf-8"), "test.md")
    assert "Hi～大家好" in p.content
    assert "猜你想搜" not in p.content
    assert "编辑于" not in p.content
    assert "共 832 条评论" not in p.content
    assert "#新疆领队" in p.tags_raw
    assert "#新疆旅游" in p.tags_raw
    assert "#新疆小团" in p.tags_raw


def test_parse_published_at():
    p = parse_work_vault_note(FIXTURE.read_text(encoding="utf-8"), "test.md")
    assert p.published_at == "2025-04-20"


def test_parse_comments():
    p = parse_work_vault_note(FIXTURE.read_text(encoding="utf-8"), "test.md")
    assert p.comments_count == 832
    assert len(p.comments) == 3

    # 置顶评论（作者）
    c0 = p.comments[0]
    assert c0["author"] == "新疆领队-多多"
    assert c0["is_author"] is True
    assert c0["is_pinned"] is True
    assert c0["likes"] == 3
    assert "来咨询" in c0["text"]

    # 普通评论
    c1 = p.comments[1]
    assert c1["author"] == "小红薯16D1F473"
    assert c1["is_author"] is False
    assert c1["text"] == "咨询"
    assert c1["likes"] == 1

    # 无回复数的评论
    c2 = p.comments[2]
    assert c2["author"] == "Banaballa"
    assert c2["likes"] == 1
    assert "8月中" in c2["text"]
    assert extract_material_author(p.comments) == "新疆领队-多多"


def test_parse_empty_file():
    p = parse_work_vault_note("", "empty.md")
    assert p.is_empty is True
    assert p.is_note is False


def test_parse_non_note_file():
    text = "问点点ai\n纯玩小团\n跟团推荐\n搭子7月\n真实\n当地报团"
    p = parse_work_vault_note(text, "ref.md")
    assert p.is_note is False


def test_content_hash_body_only():
    """两个标题不同但正文相同的文件应产生相同 content_hash。"""
    text = "这是正文内容。\n共 0 条评论\n"
    p1 = parse_work_vault_note(text, "file_a.md")
    p2 = parse_work_vault_note(text, "file_b.md")
    assert p1.content_hash == p2.content_hash


def test_standalone_date_without_prefix():
    """没有 "编辑于" 前缀的独立日期行也应被提取。"""
    text = "正文内容\n#标签\n2025-08-04\n共 7 条评论\n"
    p = parse_work_vault_note(text, "test.md")
    assert p.published_at == "2025-08-04"


def test_obsidian_image_extraction():
    text = "![[Pasted image 20260720161421.png]]\n正文内容\n共 0 条评论\n"
    p = parse_work_vault_note(text, "test.md")
    assert len(p.image_refs) == 1
    assert p.image_refs[0] == "Pasted image 20260720161421.png"
    assert "Pasted image" not in p.content


def test_markdown_link_tags():
    """[#tag](url) 格式的标签也应被提取。"""
    text = "正文内容\n[#新疆旅游](https://www.xiaohongshu.com/search_result?keyword=test) [#伊犁](https://example.com)\n共 0 条评论\n"
    p = parse_work_vault_note(text, "test.md")
    assert "#新疆旅游" in p.tags_raw
    assert "#伊犁" in p.tags_raw
    assert "xiaohongshu.com" not in p.content


# ── 扫描 ──

def test_scan_vault(tmp_path):
    """扫描临时 vault 目录，验证分类逻辑。"""
    (tmp_path / "note1.md").write_text("笔记1正文\n共 0 条评论\n", encoding="utf-8")
    (tmp_path / "note2.md").write_text("笔记2正文\n共 0 条评论\n", encoding="utf-8")
    (tmp_path / "dup.md").write_text("笔记1正文\n共 0 条评论\n", encoding="utf-8")
    (tmp_path / "empty.md").write_text("", encoding="utf-8")

    items = scan_vault(str(tmp_path))
    statuses = {i.filename: i.status for i in items}
    assert statuses["note2.md"] == "valid"
    # 排序后 dup.md 先处理 -> valid, note1.md 后处理 -> duplicate_vault
    dup_count = sum(1 for v in statuses.values() if v == "duplicate_vault")
    assert dup_count == 1
    assert statuses["dup.md"] == "valid" or statuses["note1.md"] == "duplicate_vault"
    assert statuses["empty.md"] == "empty"


def test_scan_vault_cross_db_dedup(tmp_path, monkeypatch):
    """已存在于 DB 的笔记应标记为 duplicate_db。"""
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    from sidecar.db.session import init_db, session_scope
    init_db()

    (tmp_path / "note.md").write_text("测试正文\n共 0 条评论\n", encoding="utf-8")
    p = parse_work_vault_note("测试正文\n共 0 条评论\n", "note.md")

    with session_scope() as s:
        m = Material(note_id=p.content_hash, url="", title="note",
                     author="", content="测试正文", platform="xiaohongshu",
                     local_folder="workvault:note.md")
        s.add(m)

    items = scan_vault(str(tmp_path), existing_hashes={p.content_hash})
    note_item = [i for i in items if i.filename == "note.md"][0]
    assert note_item.status == "duplicate_db"


# ── 导入 ──

def test_insert_note(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    from sidecar.db.session import init_db, session_scope
    init_db()

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("测试正文\n共 0 条评论\n", encoding="utf-8")

    with session_scope() as s:
        assert insert_work_vault_note(s, str(vault), "note.md") is True
        mats = s.query(Material).all()
        assert len(mats) == 1
        assert mats[0].title == "note"
        assert mats[0].url == ""
        assert mats[0].local_folder == "workvault:note.md"

    # 重复导入应幂等跳过
    with session_scope() as s:
        assert insert_work_vault_note(s, str(vault), "note.md") is False
        assert s.query(Material).count() == 1


def test_insert_with_comments_and_images(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    from sidecar.db.session import init_db, session_scope
    init_db()

    vault = tmp_path / "vault"
    vault.mkdir()
    img = vault / "Pasted image 20260720161421.png"
    img.write_bytes(b"\x89PNG fake")
    (vault / "note.md").write_text(
        "![[Pasted image 20260720161421.png]]\n正文\n共 2 条评论\n\n"
        "用户A\n问价\n2025-05-01北京\n3\n回复\n\n"
        "作者B\n作者\n回复你\n置顶评论\n2025-05-02新疆\n赞\n回复\n",
        encoding="utf-8",
    )

    with session_scope() as s:
        assert insert_work_vault_note(s, str(vault), "note.md") is True
        m = s.query(Material).first()
        assert m.author == "作者B"
        assert m.comments_count == 2
        assert s.query(Comment).count() == 2
        assert s.query(MaterialImage).count() == 1
        # 图片应被复制到 media 目录
        img_dst = tmp_path / "media" / m.note_id / "Pasted image 20260720161421.png"
        assert img_dst.exists()


def test_backfill_authors_dry_run_and_execute(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    from sidecar.db.session import init_db, session_scope
    init_db()
    vault = tmp_path / "vault"
    vault.mkdir()
    filename = "note.md"
    (vault / filename).write_text(
        "正文\n共 1 条评论\n\n领队多多\n作者\n置顶评论\n欢迎咨询\n"
        "2025-05-02新疆\n赞\n回复\n",
        encoding="utf-8",
    )
    with session_scope() as s:
        s.add(Material(
            note_id="blank-author", url="", title="note", author="",
            content="正文", platform="xiaohongshu",
            local_folder=f"workvault:{filename}",
        ))
    with session_scope() as s:
        preview = backfill_work_vault_authors(s, str(vault), dry_run=True)
        assert preview["repairable"] == 1
        assert preview["updated"] == 0
    with session_scope() as s:
        assert s.query(Material).filter_by(note_id="blank-author").one().author == ""
    with session_scope() as s:
        result = backfill_work_vault_authors(s, str(vault), dry_run=False)
        assert result["updated"] == 1
    with session_scope() as s:
        assert s.query(Material).filter_by(note_id="blank-author").one().author == "领队多多"
