"""Tests for scripts/export_session.py on a small synthetic transcript."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import export_session  # noqa: E402

FIXTURE = [
    {"type": "summary", "summary": "demo"},
    {"type": "user", "timestamp": "2026-09-23T10:00:00Z", "message": {"role": "user", "content": "Lance les tests"}},
    {"type": "assistant", "timestamp": "2026-09-23T10:00:05Z", "message": {"role": "assistant", "content": [
        {"type": "text", "text": "Je lance pytest."},
        {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "uv run pytest -q", "description": "Run tests"}},
    ]}},
    {"type": "user", "timestamp": "2026-09-23T10:00:09Z", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "4 passed" + "x" * 50},
    ]}},
    {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "t2", "name": "Edit", "input": {"file_path": "/repo/README.md", "old_string": "a", "new_string": "b"}},
        {"type": "some_future_block"},
    ]}},
]


def write_fixture(tmp_path: Path) -> Path:
    path = tmp_path / "session.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in FIXTURE) + "\nnot json\n", encoding="utf-8")
    return path


def test_markdown_contains_prompts_answers_tools_and_results(tmp_path: Path):
    md = export_session.to_markdown(
        export_session.read_entries(write_fixture(tmp_path)), result_limit=20, title="T"
    )
    assert "## Utilisateur · 2026-09-23T10:00:00Z" in md and "Lance les tests" in md
    assert "## Claude" in md and "Je lance pytest." in md
    assert "**Outil : Bash**" in md and "uv run pytest -q" in md and "_Run tests_" in md
    assert "4 passed" in md and "caractères coupés" in md          # truncated result
    assert "**Outil : Edit** → `/repo/README.md`" in md
    assert "summary × 1" in md and "bloc some_future_block × 1" in md  # summarised, not dumped
    assert "Période : 2026-09-23T10:00:00Z" in md


def test_cli_writes_file_and_project_dir_naming(tmp_path: Path):
    out = tmp_path / "out" / "session.md"
    assert export_session.main([str(write_fixture(tmp_path)), "-o", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("# Session Claude Code : session")
    resolved = str(Path("/home/me/agent-relay").resolve())
    expected = "".join(ch if ch.isalnum() else "-" for ch in resolved)
    assert export_session.project_dir(Path("/home/me/agent-relay")).name == expected
