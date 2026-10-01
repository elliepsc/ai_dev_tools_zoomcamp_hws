from pathlib import Path

from responder.policy import DiffStats, action_allowed, effective_level, gate_patch, load_policy

POLICY = load_policy(Path(__file__).resolve().parents[1] / "autonomy-policy.yaml")
GOOD = {"classification": "real_incident", "proposed_action": "patch", "confidence": 0.9}


def test_test_alert_is_forced_to_observe():
    lvl = effective_level(POLICY, {"alertname": "ResponderTest", "test": "true"})
    assert lvl.level == 0
    assert not action_allowed(POLICY, "patch", lvl.level)
    assert not action_allowed(POLICY, "deploy", lvl.level)


def test_real_alert_gets_default_level():
    assert effective_level(POLICY, {"alertname": "OrderTracker5xx"}).level == POLICY["default_level"]


def test_small_tested_patch_passes_gate():
    diff = DiffStats(["app/main.py", "tests/test_api.py"], 12, 2)
    assert gate_patch(POLICY, GOOD, diff, tests_passed=True).allowed


def test_gate_rejects_forbidden_paths_untested_or_unconfident_patches():
    assert not gate_patch(POLICY, GOOD, DiffStats(["Dockerfile", "tests/t.py"], 1, 0), True).allowed
    assert not gate_patch(POLICY, GOOD, DiffStats(["app/main.py", "tests/t.py"], 1, 0), False).allowed
    assert not gate_patch(POLICY, GOOD, DiffStats(["app/main.py"], 1, 0), True).allowed  # no regression test
    low = {**GOOD, "confidence": 0.4}
    assert not gate_patch(POLICY, low, DiffStats(["app/main.py", "tests/t.py"], 1, 0), True).allowed
    big = DiffStats(["app/main.py", "tests/t.py"], 500, 0)
    assert not gate_patch(POLICY, GOOD, big, True).allowed


def test_effective_extension_surface_must_match_declaration():
    from responder.policy import extension_surface_ok

    assert extension_surface_ok(POLICY, {"mcp_servers": [], "plugins": [], "skills": 0})[0]
    ok, detail = extension_surface_ok(POLICY, {"mcp_servers": ["claude-in-chrome"], "plugins": [], "skills": 0})
    assert not ok and "claude-in-chrome" in detail
    assert not extension_surface_ok(POLICY, {"mcp_servers": [], "plugins": ["x"], "skills": 0})[0]
    assert not extension_surface_ok(POLICY, {"mcp_servers": [], "plugins": [], "skills": 61})[0]
    assert extension_surface_ok(POLICY, None)[0]  # unknown (Codex) is allowed but recorded
