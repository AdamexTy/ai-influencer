import json

import main


def test_load_recovers_malformed_memory_and_creates_backup(tmp_path, monkeypatch):
    mem_path = tmp_path / "memory.json"
    mem_path.write_text('{"channel": {"name": "x"}, "videos": []} trailing', encoding="utf-8")
    monkeypatch.setattr(main, "MEM", mem_path)

    loaded = main.load()

    assert loaded["channel"]["name"] == "x"
    assert loaded["videos"] == []
    assert loaded["lessons"] == []
    backups = list(tmp_path.glob("memory.json.corrupt-*.bak"))
    assert backups, "expected a backup file for malformed memory"
    saved = json.loads(mem_path.read_text(encoding="utf-8"))
    assert set(saved.keys()) == {"channel", "videos", "lessons"}


def test_load_normalizes_wrong_types(tmp_path, monkeypatch):
    mem_path = tmp_path / "memory.json"
    mem_path.write_text(json.dumps({"channel": [], "videos": {}, "lessons": "x"}), encoding="utf-8")
    monkeypatch.setattr(main, "MEM", mem_path)

    loaded = main.load()

    assert loaded == {"channel": {}, "videos": [], "lessons": []}
