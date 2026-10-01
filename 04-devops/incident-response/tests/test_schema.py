import json
from pathlib import Path

import jsonschema

from responder.agents import _openai_strict

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "response.schema.json").read_text())

EXAMPLE = {
    "classification": "test_notification", "summary": "Test alert", "user_impact": "none",
    "root_cause": None, "evidence": [], "confidence": 0.95, "proposed_action": "none", "changes": [],
    "tests": {"ran": False, "command": None, "passed": None, "summary": "not needed"},
    "verification_requests": [], "escalation_reason": None,
    "final_message": "Test notification received.\nNo incident: nothing to fix.",
}


def test_example_validates_and_extra_keys_are_rejected():
    jsonschema.validate(EXAMPLE, SCHEMA)
    try:
        jsonschema.validate({**EXAMPLE, "run_shell": "rm -rf /"}, SCHEMA)
        raise AssertionError("extra key accepted")
    except jsonschema.ValidationError:
        pass


def test_openai_variant_keeps_property_named_description():
    strict = _openai_strict(SCHEMA)
    assert "description" in strict["properties"]["changes"]["items"]["properties"]
    assert "maxLength" not in json.dumps(strict)


def test_tool_call_summary_tolerates_odd_events():
    from responder.agents import _tool_call_summary

    events = [
        "not a dict",
        {"type": "system", "message": "string message"},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "1", "name": "Read", "input": {"file_path": "a"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "1", "is_error": True}]}},
        {"type": "result", "permission_denials": [{"tool_name": "Bash", "tool_input": {"command": "docker ps"}}]},
    ]
    out = _tool_call_summary(events)
    assert "`Read` [ERROR/DENIED]" in out and "docker ps" in out


def test_redaction_keeps_decorators_and_hides_emails_and_tokens():
    from responder.evidence import redact

    text = 'x = "\\n\\n@pytest.mark.parametrize" by bob@example.com token=abcd1234'
    out = redact(text)
    assert "@pytest.mark.parametrize" in out
    assert "bob@example.com" not in out and "abcd1234" not in out
