"""Autonomy policy: code outside the model decides what is allowed.

Pure functions, no I/O besides loading the YAML, so they are unit-tested.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def load_policy(path: Path) -> dict[str, Any]:
    policy = yaml.safe_load(path.read_text())
    if policy.get("version") != 1:
        raise ValueError("unsupported autonomy policy version")
    return policy


@dataclass
class LevelDecision:
    level: int
    reason: str


def effective_level(policy: dict, labels: dict[str, str]) -> LevelDecision:
    """default_level, lowered by the first matching override. Never raised."""
    default = int(policy["default_level"])
    for rule in policy.get("overrides", []):
        wanted = rule.get("match", {}).get("labels", {})
        if all(str(labels.get(k)) == str(v) for k, v in wanted.items()):
            return LevelDecision(min(default, int(rule["level"])), rule.get("reason", "override"))
    return LevelDecision(default, "default level")


def action_allowed(policy: dict, action: str, level: int) -> bool:
    spec = policy["actions"].get(action)
    return spec is not None and level >= int(spec["min_level"])


def _matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in patterns)


@dataclass
class DiffStats:
    files: list[str]
    added: int
    deleted: int

    @property
    def changed_lines(self) -> int:
        return self.added + self.deleted


@dataclass
class GateResult:
    allowed: bool
    checks: list[dict] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.checks.append({"check": name, "ok": ok, "detail": detail})
        if not ok:
            self.allowed = False


def gate_patch(policy: dict, response: dict, diff: DiffStats, tests_passed: bool | None) -> GateResult:
    """Every condition that must hold before a patch may be deployed."""
    g = policy["guards"]
    result = GateResult(allowed=True)
    result.add("classification", response.get("classification") == "real_incident",
               f"agent classification = {response.get('classification')}")
    result.add("proposed_action", response.get("proposed_action") == "patch",
               f"agent proposed {response.get('proposed_action')}")
    conf = float(response.get("confidence", 0))
    result.add("confidence", conf >= g["min_confidence"], f"{conf:.2f} >= {g['min_confidence']}")
    result.add("diff_not_empty", bool(diff.files), f"{len(diff.files)} file(s) changed")
    bad = [f for f in diff.files if _matches(f, g["forbidden_paths"]) or not _matches(f, g["allowed_paths"])]
    result.add("paths_allowlisted", not bad, "outside allowlist: " + ", ".join(bad) if bad else "all paths allowlisted")
    result.add("max_files", len(diff.files) <= g["max_files_changed"], f"{len(diff.files)} <= {g['max_files_changed']}")
    result.add("max_lines", diff.changed_lines <= g["max_changed_lines"],
               f"{diff.changed_lines} <= {g['max_changed_lines']}")
    if g.get("require_regression_test"):
        result.add("regression_test", any(f.startswith("tests/") for f in diff.files),
                   "a test file changed" if any(f.startswith("tests/") for f in diff.files) else "no test added")
    if g.get("require_tests_pass"):
        result.add("tests_pass_rerun_by_responder", tests_passed is True, f"responder test run passed = {tests_passed}")
    return result


def extension_surface_ok(policy: dict, surface: dict | None) -> tuple[bool, str]:
    """Declared surface (agent-mcp.json, flags) must match the EFFECTIVE one reported by the CLI."""
    allowed = policy.get("extension_surface", {})
    if surface is None:
        return (not allowed.get("require_known", True), "effective surface unknown (agent did not report it)")
    extra_mcp = sorted(set(surface.get("mcp_servers", [])) - set(allowed.get("allowed_mcp_servers", [])))
    extra_plugins = sorted(set(surface.get("plugins", [])) - set(allowed.get("allowed_plugins", [])))
    skills_ok = surface.get("skills", 0) <= allowed.get("max_skills", 0)
    ok = not extra_mcp and not extra_plugins and skills_ok
    return ok, (f"unexpected mcp={extra_mcp} plugins={extra_plugins} skills={surface.get('skills', 0)}"
                if not ok else "effective surface matches the declared one")
