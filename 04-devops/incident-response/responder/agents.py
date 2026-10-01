"""Vendor-neutral adapter around headless coding agents.

Every agent receives the same task text and JSON schema and must return a dict that
validates against response.schema.json. What differs per vendor is only the CLI
invocation and how tool permissions are expressed. Two modes:

- read_only : diagnosis only (test alerts, level 0). No edit tool at all.
- edit      : may edit files inside an isolated git worktree and run the test suite.
             No docker, no network tools, no git commit/push, no shell beyond tests.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

# Only these variables reach the agent process: auth for the agent itself + basics.
# Grafana passwords, RESPONDER_TOKEN, cloud credentials... never do.
ENV_ALLOW_PREFIXES = ("ANTHROPIC_", "CLAUDE_CODE_", "CLAUDE_", "OPENAI_", "CODEX_")
ENV_ALLOW_EXACT = {"PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TERM", "TMPDIR", "SHELL",
                   "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "HTTPS_PROXY", "https_proxy",
                   "NO_PROXY", "no_proxy", "SSL_CERT_FILE", "NODE_EXTRA_CA_CERTS", "REQUESTS_CA_BUNDLE",
                   "UV_CACHE_DIR", "UV_NATIVE_TLS"}
ENV_DENY = {"RESPONDER_TOKEN", "GRAFANA_ADMIN_PASSWORD"}
AGENT_MCP_CONFIG = Path(__file__).resolve().parents[1] / "agent-mcp.json"


def agent_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if (k in ENV_ALLOW_EXACT or k.startswith(ENV_ALLOW_PREFIXES)) and k not in ENV_DENY}
    env["NO_COLOR"] = "1"
    return env


@dataclass
class AgentRun:
    agent: str
    model: str | None
    mode: str
    command: list[str]               # recorded for the audit trail (prompt elided)
    returncode: int
    duration_s: float
    structured: dict | None
    raw_text: str
    stderr_tail: str
    meta: dict = field(default_factory=dict)


class Agent:
    name = "base"

    def __init__(self, model: str | None, timeout_s: int, max_turns: int):
        self.model = model
        self.timeout_s = timeout_s
        self.max_turns = max_turns

    def version(self) -> str:
        return "unknown"

    def run(self, prompt: str, schema: dict, workdir: Path, extra_dirs: list[Path], mode: str,
            out_dir: Path) -> AgentRun:
        raise NotImplementedError

    def _exec(self, cmd: list[str], workdir: Path, stdin: str | None = None) -> tuple[int, str, str, float]:
        start = time.monotonic()
        try:
            p = subprocess.run(cmd, cwd=workdir, input=stdin, capture_output=True, text=True,
                               timeout=self.timeout_s, env=agent_env())
            return p.returncode, p.stdout, p.stderr, time.monotonic() - start
        except subprocess.TimeoutExpired as exc:
            return 124, exc.stdout or "", f"timeout after {self.timeout_s}s", time.monotonic() - start


class ClaudeCodeAgent(Agent):
    """`claude -p` with --json-schema; tools restricted with allow/deny lists."""

    name = "claude-code"
    READ_ONLY_TOOLS = ["Read", "Glob", "Grep"]
    EDIT_TOOLS = READ_ONLY_TOOLS + [
        "Edit", "Write",
        # Only the frozen test run (no dependency resolution / network). No git: e.g.
        # `git diff --output=<file>` writes anywhere (security-audit M-07).
        "Bash(uv run --frozen pytest:*)",
    ]
    # Explicit denies also override Claude Code's auto-approval of "read-only" commands
    # (observed: `git diff` ran although git is not allowlisted; `git diff --output=` writes files).
    DENY = ["WebFetch", "WebSearch", "Bash(docker:*)", "Bash(curl:*)", "Bash(wget:*)",
            "Bash(git:*)", "Bash(rm:*)", "Bash(sudo:*)", "mcp__claude-in-chrome",
            "Read(./.env)", "Read(**/.env)", "Read(~/.ssh/**)", "Read(~/.aws/**)", "Read(~/.docker/**)"]

    def version(self) -> str:
        try:
            return subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception:
            return "unavailable"

    def run(self, prompt, schema, workdir, extra_dirs, mode, out_dir):
        tools = self.EDIT_TOOLS if mode == "edit" else self.READ_ONLY_TOOLS
        schema = {k: v for k, v in schema.items() if k != "$schema"}  # the CLI validator is draft-07
        # stream-json keeps every tool call and every permission denial: the audit trail of the run.
        cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--json-schema", json.dumps(schema),
               "--max-turns", str(self.max_turns), "--no-session-persistence",
               "--permission-mode", "acceptEdits" if mode == "edit" else "default",
               "--allowedTools", *tools, "--disallowedTools", *self.DENY,
               # Declared, scannable extension surface (Snyk Agent Scan): no MCP server at all,
               # no skills, no user-level settings/plugins. The EFFECTIVE surface is read back
               # from the init event below and gated by the policy (declared != effective).
               "--strict-mcp-config", "--mcp-config", str(AGENT_MCP_CONFIG),
               "--disable-slash-commands", "--setting-sources", "project"]
        for d in extra_dirs:
            cmd += ["--add-dir", str(d)]
        if self.model:
            cmd += ["--model", self.model]
        rc, out, err, dur = self._exec(cmd, workdir, stdin=prompt)
        (out_dir / "agent-transcript.jsonl").write_text(out)
        structured, raw, meta = None, out, {}
        events = []
        for line in out.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        try:
            (out_dir / "agent-tool-calls.md").write_text(_tool_call_summary(events))
        except Exception as exc:  # the summary is a convenience; never lose the run for it
            (out_dir / "agent-tool-calls.md").write_text(f"summary unavailable: {exc!r}\n")
        try:
            data = next(e for e in reversed(events) if e.get("type") == "result")
            structured = data.get("structured_output")
            raw = data.get("result") or ""
            if structured is None and raw:
                structured = _json_from_text(raw)
            meta = {k: data.get(k) for k in ("total_cost_usd", "num_turns", "duration_ms", "session_id",
                                             "is_error", "subtype", "stop_reason")}
            meta["models_used"] = list((data.get("modelUsage") or {}).keys())
            meta["permission_denials"] = len(data.get("permission_denials") or [])
            init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
            meta["extension_surface"] = {
                "mcp_servers": sorted(m.get("name") for m in init.get("mcp_servers") or [] if isinstance(m, dict)),
                "plugins": sorted(p.get("name") for p in init.get("plugins") or [] if isinstance(p, dict)),
                "skills": len(init.get("skills") or []),
                "mcp_tools": len([t for t in init.get("tools") or [] if str(t).startswith("mcp__")]),
            }
        except StopIteration:
            pass
        return AgentRun(self.name, self.model, mode, _audit_cmd(cmd), rc, dur, structured, raw, err[-2000:], meta)


class CodexAgent(Agent):
    """`codex exec` with --output-schema; OS-level sandbox (read-only / workspace-write, no network)."""

    name = "codex"

    def version(self) -> str:
        try:
            return subprocess.run(["codex", "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception:
            return "unavailable"

    def run(self, prompt, schema, workdir, extra_dirs, mode, out_dir):
        schema_file = out_dir / "codex-schema.json"
        schema_file.write_text(json.dumps(_openai_strict(schema)))
        last = out_dir / "agent-last-message.json"
        cmd = ["codex", "exec", "--skip-git-repo-check", "-C", str(workdir),
               "--sandbox", "workspace-write" if mode == "edit" else "read-only",
               "-c", "sandbox_workspace_write.network_access=false",
               "--output-schema", str(schema_file), "--output-last-message", str(last)]
        for d in extra_dirs:
            cmd += ["--add-dir", str(d)]
        if self.model:
            cmd += ["--model", self.model]
        cmd.append("-")  # prompt on stdin
        rc, out, err, dur = self._exec(cmd, workdir, stdin=prompt)
        (out_dir / "agent-stdout.txt").write_text(out)
        raw = last.read_text() if last.exists() else out
        structured = _json_from_text(raw)
        return AgentRun(self.name, self.model, mode, _audit_cmd(cmd), rc, dur, structured, raw, err[-2000:], {})


class FakeAgent(Agent):
    """Deterministic stand-in for tests: returns RESPONDER_FAKE_RESPONSE (a JSON file)."""

    name = "fake"

    def version(self) -> str:
        return "fake-1"

    def run(self, prompt, schema, workdir, extra_dirs, mode, out_dir):
        data = json.loads(Path(os.environ["RESPONDER_FAKE_RESPONSE"]).read_text())
        patch = os.environ.get("RESPONDER_FAKE_PATCH")
        if patch and mode == "edit":
            subprocess.run(["git", "apply", patch], cwd=workdir, check=True)
        return AgentRun(self.name, None, mode, ["fake"], 0, 0.0, data, json.dumps(data), "", {})


AGENTS = {"claude": ClaudeCodeAgent, "codex": CodexAgent, "fake": FakeAgent}


def make_agent(kind: str, model: str | None, timeout_s: int, max_turns: int) -> Agent:
    if kind not in AGENTS:
        raise ValueError(f"unknown agent {kind!r}; choose one of {sorted(AGENTS)}")
    if kind != "fake" and shutil.which({"claude": "claude", "codex": "codex"}[kind]) is None:
        raise RuntimeError(f"{kind} CLI not found on PATH")
    return AGENTS[kind](model, timeout_s, max_turns)


def _tool_call_summary(events: list[dict]) -> str:
    """Human-readable list of what the agent actually did, and what it was refused."""
    lines = ["# Agent tool calls", ""]
    events = [e for e in events if isinstance(e, dict)]

    def contents(e):
        msg = e.get("message")
        items = msg.get("content") if isinstance(msg, dict) else None
        return items if isinstance(items, list) else []

    results = {}
    for e in events:
        for c in contents(e):
            if isinstance(c, dict) and c.get("type") == "tool_result":
                results[c.get("tool_use_id")] = c
    n = 0
    for e in events:
        if e.get("type") != "assistant":
            continue
        for c in contents(e):
            if isinstance(c, dict) and c.get("type") == "tool_use":
                n += 1
                inp = json.dumps(c.get("input"), ensure_ascii=False)
                res = results.get(c.get("id"), {})
                status = "ERROR/DENIED" if res.get("is_error") else "ok"
                lines.append(f"{n}. `{c.get('name')}` [{status}] {inp[:400]}")
    final = next((e for e in reversed(events) if e.get("type") == "result"), {})
    lines += ["", f"Permission denials: {len(final.get('permission_denials') or [])}"]
    for d in final.get("permission_denials") or []:
        lines.append(f"- {d.get('tool_name')}: {json.dumps(d.get('tool_input'))[:400]}")
    return "\n".join(lines) + "\n"


def _audit_cmd(cmd: list[str]) -> list[str]:
    """Keep the command for the audit trail but elide the (long) schema argument."""
    out, skip = [], False
    for part in cmd:
        if skip:
            out.append("<schema: response.schema.json>")
            skip = False
            continue
        out.append(part)
        skip = part == "--json-schema"
    return out


def _json_from_text(text: str) -> dict | None:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _openai_strict(schema: dict) -> dict:
    """OpenAI structured outputs reject some JSON-Schema keywords; the full schema is
    still enforced afterwards by the responder, so dropping them here is safe."""
    drop = {"$schema", "title", "maxLength", "minLength", "maxItems", "minItems", "minimum", "maximum", "description"}

    def walk(node):
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                if k == "properties":  # property *names* are data, never keywords
                    out[k] = {name: walk(sub) for name, sub in v.items()}
                elif k not in drop:
                    out[k] = walk(v)
            return out
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(copy.deepcopy(schema))
