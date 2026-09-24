"""Convert a Claude Code session transcript (JSONL) into readable Markdown.

Claude Code stores every session on the machine where it runs, one JSON object
per line, in:

    ~/.claude/projects/<project-path-with-dashes>/<session-id>.jsonl

This script turns such a file into a Markdown "journal": your prompts,
Claude's visible answers, each tool call (command, file edited...) and a
truncated view of its result. Other entry types are counted and summarised
at the end instead of being dumped.

Usage:
    uv run python scripts/export_session.py --list                      # sessions of the current project
    uv run python scripts/export_session.py --latest -o docs/session.md # most recent session of this project
    uv run python scripts/export_session.py path/to/session.jsonl -o session.md
    claude -p "..." --output-format stream-json --verbose > run.jsonl
    uv run python scripts/export_session.py run.jsonl -o run.md          # headless run log works too

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"


def project_dir(cwd: Path) -> Path:
    """Claude Code names the folder after the absolute project path, with
    every non-alphanumeric character replaced by '-'."""

    name = "".join(ch if ch.isalnum() else "-" for ch in str(cwd.resolve()))
    return CLAUDE_PROJECTS / name


def list_sessions(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)


def read_entries(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                print(f"warning: line {number} is not valid JSON, skipped", file=sys.stderr)


def shorten(text: str, limit: int) -> str:
    text = text.rstrip()
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit] + f"\n… [{len(text) - limit} caractères coupés]"


def fence(text: str, lang: str = "") -> str:
    ticks = "````" if "```" in text else "```"
    return f"{ticks}{lang}\n{text}\n{ticks}"


def result_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, dict):
                parts.append(f"[{item.get('type', 'contenu')} non textuel]")
        return "\n".join(parts)
    return json.dumps(content, ensure_ascii=False)


def describe_tool_call(block: dict[str, Any]) -> str:
    name = block.get("name", "outil")
    args = block.get("input") or {}
    if name == "Bash":
        body = ""
        if args.get("description"):
            body += f"_{args['description']}_\n\n"
        return f"**Outil : Bash**\n\n{body}{fence(args.get('command', ''), 'bash')}"
    if name in {"Write", "Edit", "Read"} and "file_path" in args:
        return f"**Outil : {name}** → `{args['file_path']}`"
    return f"**Outil : {name}**\n\n{fence(json.dumps(args, ensure_ascii=False, indent=2)[:2000], 'json')}"


def to_markdown(entries: Iterable[dict[str, Any]], *, result_limit: int, title: str) -> str:
    out: list[str] = [f"# {title}", ""]
    skipped: Counter[str] = Counter()
    first_ts = last_ts = None

    for entry in entries:
        kind = entry.get("type")
        message = entry.get("message")
        if kind not in {"user", "assistant"} or not isinstance(message, dict):
            skipped[str(kind)] += 1
            continue
        ts = entry.get("timestamp")
        first_ts = first_ts or ts
        last_ts = ts or last_ts
        content = message.get("content")
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else (content or [])

        for block in blocks:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text" and block.get("text", "").strip():
                who = "Utilisateur" if kind == "user" else "Claude"
                stamp = f" · {ts}" if ts else ""
                out += [f"## {who}{stamp}", "", block["text"].strip(), ""]
            elif btype == "tool_use":
                out += [describe_tool_call(block), ""]
            elif btype == "tool_result":
                text = shorten(result_text(block.get("content")), result_limit)
                label = "Résultat (erreur)" if block.get("is_error") else "Résultat"
                out += [f"<details><summary>{label}</summary>", "", fence(text), "", "</details>", ""]
            else:
                skipped[f"bloc {btype}"] += 1

    header = []
    if first_ts:
        header.append(f"Période : {first_ts} → {last_ts}")
    if skipped:
        header.append("Entrées non exportées : " + ", ".join(f"{k} × {v}" for k, v in sorted(skipped.items())))
    if header:
        out[2:2] = ["> " + line for line in header] + [""]
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("transcript", nargs="?", type=Path, help="fichier .jsonl à convertir")
    parser.add_argument("--latest", action="store_true", help="session la plus récente du projet courant")
    parser.add_argument("--list", action="store_true", help="lister les sessions du projet courant")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="dossier du projet (défaut : cwd)")
    parser.add_argument("-o", "--output", type=Path, help="fichier Markdown de sortie (défaut : stdout)")
    parser.add_argument("--max-result-chars", type=int, default=1500, help="troncature des résultats (0 = rien)")
    args = parser.parse_args(argv)

    directory = project_dir(args.project)
    if args.list:
        sessions = list_sessions(directory)
        if not sessions:
            print(f"Aucune session trouvée dans {directory}", file=sys.stderr)
            return 1
        for path in sessions:
            print(f"{path}  ({path.stat().st_size // 1024} Ko)")
        return 0

    path = args.transcript
    if args.latest:
        sessions = list_sessions(directory)
        if not sessions:
            print(f"Aucune session trouvée dans {directory}", file=sys.stderr)
            return 1
        path = sessions[0]
    if path is None:
        parser.error("donner un fichier .jsonl, --latest ou --list")
    if not path.exists():
        parser.error(f"fichier introuvable : {path}")

    markdown = to_markdown(read_entries(path), result_limit=args.max_result_chars, title=f"Session Claude Code : {path.stem}")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
        print(f"Écrit : {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
