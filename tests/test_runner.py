import json
from sidecar.opencli import runner

def test_parse_json_output_extracts_array():
    raw = 'some banner\n[{"a":1}]\nUpdate available'
    assert runner._extract_json(raw) == [{"a": 1}]

def test_parse_json_output_extracts_object():
    raw = '{"ok": true}'
    assert runner._extract_json(raw) == {"ok": True}

def test_run_opencli_calls_subprocess(monkeypatch):
    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        class R:
            returncode = 0
            stdout = '[{"rank":1}]'
            stderr = ""
        return R()
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    out = runner.run_opencli(["xhs", "search", "x", "-f", "json"])
    assert out == [{"rank": 1}]
    assert captured["cmd"][0].endswith("opencli")
