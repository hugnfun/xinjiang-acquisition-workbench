from pathlib import Path
from sidecar.importers.note_md import parse_note_md, ParsedNote

FIXTURE = Path(__file__).parent / "fixtures" / "sample_note.md"

def test_parse_title_and_metadata():
    n = parse_note_md(FIXTURE.read_text(encoding="utf-8"))
    assert n.title == "测试标题"
    assert n.metadata["作者"] == "测试作者"
    assert n.metadata["点赞"] == "1.4万"
    assert n.metadata["评论数"] == "721"
    assert n.metadata["标签"] == "#赛里木湖, #无滤镜"

def test_parse_content():
    n = parse_note_md(FIXTURE.read_text(encoding="utf-8"))
    assert "这是正文内容" in n.content

def test_parse_images():
    n = parse_note_md(FIXTURE.read_text(encoding="utf-8"))
    assert n.image_paths == ["images/abc_1.jpg", "images/abc_2.jpg"]

def test_parse_comments():
    n = parse_note_md(FIXTURE.read_text(encoding="utf-8"))
    assert len(n.comments) == 2
    top = n.comments[0]
    assert top["author"] == "张三"
    assert top["likes"] == 5
    assert top["time"] == "2025-10-12湖北"
    assert top["is_reply"] is False
    assert "一个人去有风险吗" in top["text"]
    reply = n.comments[1]
    assert reply["is_reply"] is True
    assert reply["reply_to"] == "张三"
    assert reply["author"] == "测试作者"
    assert reply["likes"] == 8
