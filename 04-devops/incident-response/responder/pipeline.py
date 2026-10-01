"""Incident pipeline: evidence -> agent -> policy gate -> runbook -> verification -> record.

The model may reason; the system observes, authorizes, verifies and remembers.
Everything that happens is appended to incidents/<id>/audit.jsonl.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from responder import evidence as ev
from responder.agents import make_agent
from responder.policy import (DiffStats, action_allowed, effective_level, extension_surface_ok, gate_patch,
                              load_policy)

log = logging.getLogger("responder")
HERE = Path(__file__).resolve().parents[1]           # incident-response/


def _env_path(name: str, default: Path) -> Path:
    return Path(os.getenv(name, str(default))).resolve()


@dataclass
class Settings:
    repo: Path = field(default_factory=lambda: _env_path("RESPONDER_REPO_DIR", HERE.parent))
    incidents_dir: Path = field(default_factory=lambda: _env_path("RESPONDER_INCIDENTS_DIR", HERE / "incidents"))
    worktrees_dir: Path = field(default_factory=lambda: _env_path("RESPONDER_WORKTREES_DIR", HERE / ".worktrees"))
    policy_path: Path = field(default_factory=lambda: _env_path("RESPONDER_POLICY", HERE / "autonomy-policy.yaml"))
    agent: str = field(default_factory=lambda: os.getenv("RESPONDER_AGENT", "claude"))
    model: str | None = field(default_factory=lambda: os.getenv("RESPONDER_MODEL") or None)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fingerprint(alert: dict) -> str:
    """Computed server-side from the labels: a sender-chosen fingerprint could dodge
    de-duplication (security-audit M-06). For Grafana, labels define alert identity anyway."""
    labels = json.dumps(alert.get("labels", {}), sort_keys=True)
    return hashlib.sha256(labels.encode()).hexdigest()[:16]


class Incident:
    def __init__(self, root: Path):
        self.root = root
        self.id = root.name

    def write(self, name: str, content) -> Path:
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content if isinstance(content, str) else json.dumps(content, indent=2, default=str))
        return p

    def read_json(self, name: str) -> dict:
        return json.loads((self.root / name).read_text())

    def audit(self, step: str, **detail) -> None:
        with (self.root / "audit.jsonl").open("a") as f:
            f.write(json.dumps({"ts": now_iso(), "step": step, **detail}, default=str) + "\n")
        log.info("[%s] %s %s", self.id, step, json.dumps(detail, default=str)[:300])

    def status(self, **fields) -> dict:
        path = self.root / "status.json"
        cur = json.loads(path.read_text()) if path.exists() else {}
        cur.update(fields, updated_at=now_iso())
        path.write_text(json.dumps(cur, indent=2, default=str))
        return cur


# Agent-written tests run with a minimal environment: no API keys, no tokens (security-audit M-02).
TEST_ENV = {"UV_NO_PROGRESS": "1"}
_TEST_ENV_KEEP = {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "UV_CACHE_DIR", "UV_NATIVE_TLS", "SSL_CERT_FILE",
                  "HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy", "UV_PYTHON_INSTALL_DIR"}


def run(cmd: list[str], cwd: Path, timeout: int = 600, env: dict | None = None,
        clean_env: bool = False) -> tuple[int, str]:
    if clean_env:
        base = {k: v for k, v in os.environ.items() if k in _TEST_ENV_KEEP}
    else:
        base = {k: v for k, v in os.environ.items() if k not in {"VIRTUAL_ENV", "RESPONDER_TOKEN"}}
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env={**base, **(env or {})})
    return p.returncode, (p.stdout + p.stderr)


class Responder:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or Settings()
        self.policy = load_policy(self.s.policy_path)
        self.schema = json.loads((HERE / "response.schema.json").read_text())
        self.task_template = (HERE / "responder-task.md").read_text()
        self.s.incidents_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()          # one incident mutates the repo at a time
        self._index_lock = threading.Lock()

    # ------------------------------------------------------------------ intake
    def open_or_attach(self, alert: dict, group_payload: dict) -> tuple[str, bool]:
        """Returns (incident_id, is_new). Same fingerprint within the dedupe window = same incident."""
        fp = fingerprint(alert)
        window = self.policy["budget"]["dedupe_window_minutes"] * 60
        with self._index_lock:
            for st in self.list_incidents():
                if st.get("fingerprint") == fp and st.get("state") not in {"closed", "resolved"} \
                        and time.time() - st.get("opened_ts", 0) < window:
                    inc = Incident(self.s.incidents_dir / st["id"])
                    inc.audit("alert_attached", status=alert.get("status"))
                    return inc.id, False
            inc_id = f"INC-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
            inc = Incident(self.s.incidents_dir / inc_id)
            inc.root.mkdir(parents=True)
            inc.write("alert.json", ev.redact({"alert": alert, "group": {
                k: group_payload.get(k) for k in ("receiver", "status", "groupKey", "externalURL", "title", "message")
                if k in group_payload}}))
            inc.status(id=inc_id, fingerprint=fp, state="open", opened_at=now_iso(), opened_ts=time.time(),
                       alertname=alert.get("labels", {}).get("alertname"),
                       route=self._route(alert))
            inc.audit("incident_opened", fingerprint=fp, alertname=alert.get("labels", {}).get("alertname"))
            return inc_id, True

    def mark_resolved(self, alert: dict) -> str | None:
        fp = fingerprint(alert)
        for st in self.list_incidents():
            if st.get("fingerprint") == fp and st.get("state") not in {"closed"}:
                inc = Incident(self.s.incidents_dir / st["id"])
                inc.audit("alert_resolved_by_grafana")
                inc.status(alert_resolved_at=now_iso())
                return inc.id
        return None

    def list_incidents(self) -> list[dict]:
        out = []
        for d in sorted(self.s.incidents_dir.glob("INC-*"), reverse=True):
            p = d / "status.json"
            if p.exists():
                out.append(json.loads(p.read_text()))
        return out

    def agent_runs_last_hour(self) -> int:
        return sum(1 for st in self.list_incidents()
                   if st.get("agent_started_ts") and time.time() - st["agent_started_ts"] < 3600)

    @staticmethod
    def _route(alert: dict) -> str | None:
        labels, ann = alert.get("labels", {}), alert.get("annotations", {})
        route = labels.get("http_route") or ann.get("endpoint")
        try:
            return ev.validate_route(route)
        except ValueError:
            return None

    # ---------------------------------------------------------------- pipeline
    def handle(self, inc_id: str) -> None:
        with self._lock:
            inc = Incident(self.s.incidents_dir / inc_id)
            try:
                self._handle(inc)
            except Exception as exc:  # never lose an incident silently
                log.exception("pipeline failed")
                inc.audit("pipeline_error", error=repr(exc))
                wt = self.s.worktrees_dir / inc.id
                if wt.exists():  # leave no half-edited worktree behind; keep the branch for humans
                    self._cleanup_worktree(inc, wt, f"incident/{inc.id}", keep_branch=True)
                self._escalate(inc, f"responder pipeline error: {exc!r}")

    def _handle(self, inc: Incident) -> None:
        alert = inc.read_json("alert.json")["alert"]
        labels = {k: str(v) for k, v in alert.get("labels", {}).items()}
        route = self._route(alert)

        # 1. Observe: evidence first, model later.
        inc.status(state="collecting_evidence")
        packet = ev.collect(route, inc.root / "evidence", self.s.repo)
        inc.audit("evidence_collected", route=route, logs=packet["logs"].get("count"),
                  traces=packet["traces"].get("count"), samples=packet["failing_request_samples"])

        # 2. Authorize the *mode* of the run before the model sees anything.
        lvl = effective_level(self.policy, labels)
        level_name = self.policy["levels"][lvl.level]
        mode = "edit" if lvl.level >= 1 else "read_only"
        inc.audit("autonomy_level", level=lvl.level, name=level_name, reason=lvl.reason, agent_mode=mode)

        budget = self.policy["budget"]
        if self.agent_runs_last_hour() >= budget["max_agent_runs_per_hour"]:
            self._escalate(inc, "agent run budget exhausted for this hour; evidence packet attached")
            return

        branch, workdir = None, self.s.repo
        if mode == "edit":
            branch = f"incident/{inc.id}"
            workdir = self.s.worktrees_dir / inc.id
            self.s.worktrees_dir.mkdir(parents=True, exist_ok=True)
            rc, out = run(["git", "worktree", "add", "-b", branch, str(workdir), "HEAD"], self.s.repo)
            inc.audit("worktree_created", branch=branch, rc=rc, out=out[-300:])
            if rc != 0:
                self._escalate(inc, f"could not create worktree: {out[-300:]}")
                return
        base_sha = run(["git", "rev-parse", "--short", "HEAD"], self.s.repo)[1].strip()

        # 3. Reason: headless agent behind the adapter.
        prompt = self.task_template.format(
            mode=mode, level=lvl.level, level_name=level_name, branch=branch or "(none: read-only)",
            incident_id=inc.id, evidence_dir=str(inc.root / "evidence"),
            alert_json=json.dumps(alert, indent=2)[:4000],
            summary_md=(inc.root / "evidence" / "summary.md").read_text()[:12000])
        inc.write("prompt.md", prompt)
        agent = make_agent(self.s.agent, self.s.model, budget["agent_timeout_seconds"], budget["agent_max_turns"])
        inc.status(state="agent_running", agent=agent.name, agent_started_ts=time.time())
        inc.audit("agent_started", agent=agent.name, version=agent.version(), model=self.s.model or "cli default",
                  mode=mode, cwd=str(workdir))
        (inc.root / "agent").mkdir(exist_ok=True)
        result = agent.run(prompt, self.schema, workdir, [inc.root / "evidence"], mode, inc.root / "agent")
        inc.write("agent/run.json", ev.redact({k: v for k, v in result.__dict__.items() if k != "structured"}))
        for raw in (inc.root / "agent").glob("agent-*"):   # stored transcripts are redacted too
            raw.write_text(ev.redact(raw.read_text(), limit=None) if len(raw.read_text()) < 2_000_000 else "[too large]")
        inc.audit("agent_finished", rc=result.returncode, duration_s=round(result.duration_s, 1), meta=result.meta)

        response = result.structured
        try:
            jsonschema.validate(response, self.schema)
        except jsonschema.ValidationError as exc:
            inc.write("response.invalid.json", {"response": response, "error": exc.message, "raw": result.raw_text[-4000:]})
            self._cleanup_worktree(inc, workdir, branch)
            self._escalate(inc, f"agent output failed schema validation: {exc.message}")
            return
        inc.write("response.json", ev.redact(response))
        inc.status(classification=response["classification"], proposed_action=response["proposed_action"],
                   final_message=response["final_message"])
        log.info("[%s] agent final message:\n%s", inc.id, response["final_message"])

        # 4. Policy decision on what the model proposed.
        action = response["proposed_action"]
        decision = {"level": lvl.level, "level_name": level_name, "level_reason": lvl.reason,
                    "proposed_action": action, "executed": [], "checks": []}

        if action in ("none", "escalate") or mode == "read_only" and action == "patch":
            decision["allowed"] = action_allowed(self.policy, action, lvl.level)
            decision["outcome"] = "no_change" if action == "none" else "escalated"
            if mode == "read_only" and action == "patch":
                decision["outcome"] = "escalated"
                decision["note"] = "patch proposed but level forbids edits"
            inc.write("decision.json", decision)
            inc.audit("policy_decision", **{k: decision[k] for k in ("allowed", "outcome")})
            self._cleanup_worktree(inc, workdir, branch)
            if decision["outcome"] == "escalated":
                self._escalate(inc, response.get("escalation_reason") or "agent asked for a human")
            else:
                self._close(inc, "closed", "no action required")
            return

        if action == "rollback":
            # Supported by runbooks/rollback.sh; only automatic after a *failed* fix here,
            # because a rollback target for arbitrary incidents needs release tracking.
            decision.update(allowed=False, outcome="escalated",
                            note="agent-initiated rollback not enabled without release history")
            inc.write("decision.json", decision)
            self._cleanup_worktree(inc, workdir, branch)
            self._escalate(inc, "agent proposed rollback: needs human confirmation of the target release")
            return

        # action == patch in edit mode: verify the diff and the tests ourselves.
        run(["git", "add", "-A"], workdir)
        rc, numstat = run(["git", "diff", "--cached", "--numstat", "HEAD"], workdir)
        files, added, deleted = [], 0, 0
        for line in numstat.splitlines():
            a, d, f = line.split("\t", 2)
            files.append(f)
            added += int(a) if a.isdigit() else 0
            deleted += int(d) if d.isdigit() else 0
        diff = DiffStats(files, added, deleted)
        inc.write("fix.patch", run(["git", "diff", "--cached", "HEAD"], workdir)[1])

        # Cheap checks first: never execute agent-written code whose diff is already out of policy.
        early = gate_patch(self.policy, response, diff, tests_passed=True)
        early_fail = [c for c in early.checks if not c["ok"]]
        if early_fail:
            decision.update(checks=early.checks, diff={"files": files, "added": added, "deleted": deleted},
                            allowed=False, outcome="escalated")
            inc.write("decision.json", decision)
            inc.audit("policy_decision", allowed=False, stage="pre-test", failed=[c["check"] for c in early_fail])
            self._cleanup_worktree(inc, workdir, branch, keep_branch=True)
            self._escalate(inc, "patch rejected by policy before running it: " +
                           "; ".join(f"{c['check']} ({c['detail']})" for c in early_fail))
            return

        test_cmd = self.policy["guards"]["test_command"]
        trc, tout = run(test_cmd, workdir, timeout=600, env=TEST_ENV, clean_env=True)
        inc.write("tests.log", f"$ {' '.join(test_cmd)}\n{tout}\nexit={trc}\n")
        inc.audit("responder_test_run", command=test_cmd, rc=trc, tail=tout.strip().splitlines()[-1:] if tout else [])

        # Fail-before / pass-after: with the code change removed (tests kept), the suite must FAIL.
        # Otherwise the "regression test" proves nothing (see the rollback drill in the report).
        fails_before = None
        if self.policy["guards"].get("require_fail_before_fix") and trc == 0:
            code_files = [f for f in files if not f.startswith("tests/")]
            if code_files:
                code_patch = run(["git", "diff", "--cached", "HEAD", "--", *code_files], workdir)[1]
                inc.write("code-only.patch", code_patch)
                run(["git", "checkout", "HEAD", "--", *code_files], workdir)
                brc, bout = run(test_cmd, workdir, timeout=600, env=TEST_ENV, clean_env=True)
                run(["git", "apply", "--index", str(inc.root / "code-only.patch")], workdir)
                fails_before = brc != 0
                inc.write("tests-before-fix.log", f"$ {' '.join(test_cmd)}  # code change removed\n{bout}\nexit={brc}\n")
                inc.audit("fail_before_fix_check", rc=brc, fails_before=fails_before)
            else:
                fails_before = False

        gate = gate_patch(self.policy, response, diff, trc == 0)
        if self.policy["guards"].get("require_fail_before_fix"):
            gate.add("regression_test_fails_without_fix", fails_before is True,
                     f"suite without the code change failed = {fails_before}")
        gate.add("action_patch_allowed_at_level", action_allowed(self.policy, "patch", lvl.level), f"level {lvl.level}")
        if result.agent != "fake":
            surf_ok, surf_detail = extension_surface_ok(self.policy, (result.meta or {}).get("extension_surface"))
            gate.add("agent_extension_surface_as_declared", surf_ok, surf_detail)
        deploy_ok = action_allowed(self.policy, "deploy", lvl.level)
        decision.update(checks=gate.checks, diff={"files": files, "added": added, "deleted": deleted},
                        allowed=gate.allowed, deploy_allowed_at_level=deploy_ok)
        inc.audit("policy_decision", allowed=gate.allowed, deploy_allowed=deploy_ok,
                  failed=[c["check"] for c in gate.checks if not c["ok"]])

        if not gate.allowed:
            decision["outcome"] = "escalated"
            inc.write("decision.json", decision)
            self._cleanup_worktree(inc, workdir, branch, keep_branch=True)
            self._escalate(inc, "patch rejected by policy: " +
                           "; ".join(f"{c['check']} ({c['detail']})" for c in gate.checks if not c["ok"]))
            return

        title = response["summary"].splitlines()[0][:72]
        msg = (f"fix({inc.id}): {title}\n\nIncident: {inc.id}\nAgent: {result.agent} "
               f"model={self.s.model or 'cli default'}\nPolicy: level {lvl.level} ({level_name}), "
               f"tests re-run by responder: passed\nEvidence: incident-response/incidents/{inc.id}/")
        rc, out = run(["git", "-c", "user.name=incident-responder", "-c", "user.email=responder@localhost",
                       "commit", "-q", "-m", msg], workdir)
        fix_sha = run(["git", "rev-parse", "--short", "HEAD"], workdir)[1].strip()
        inc.audit("fix_committed", branch=branch, sha=fix_sha, rc=rc)
        self._cleanup_worktree(inc, workdir, branch, keep_branch=True)

        if not deploy_ok:
            decision["outcome"] = "fix_proposed_on_branch"
            inc.write("decision.json", decision)
            self._escalate(inc, f"fix ready on branch {branch} ({fix_sha}); level {lvl.level} forbids deploy")
            return

        # 5. Act through the allowlisted runbook, then verify from the user's side.
        inc.status(state="deploying")
        cmd = [str(HERE / "runbooks" / "deploy-fix.sh"), str(self.s.repo), branch, inc.id.lower()]
        rc, out = run(cmd, self.s.repo, timeout=900)
        inc.write("deploy.log", f"$ {' '.join(cmd)}\n{out}\nexit={rc}\n")
        decision["executed"].append({"runbook": "deploy-fix.sh", "command": cmd, "rc": rc})
        inc.audit("runbook_deploy_fix", rc=rc, tail=out.strip().splitlines()[-2:])
        rollback_tag = next((ln.strip() for ln in out.splitlines() if ln.startswith("order-tracker:rollback-")), None)
        if rc != 0:
            decision["outcome"] = "deploy_failed"
            inc.write("decision.json", decision)
            self._escalate(inc, f"deploy-fix.sh failed (exit {rc}); nothing changed in production if exit 3")
            return

        inc.status(state="verifying", deployed_sha=fix_sha)
        paths = self._verification_paths(packet, response)
        vcmd = [str(HERE / "runbooks" / "verify-recovery.sh"), route or "/", *paths]
        vrc, vout = run(vcmd, self.s.repo, timeout=300,
                        env={"VERIFY_ATTEMPTS": str(self.policy["verification"]["attempts_per_request"]),
                             "VERIFY_SETTLE_SECONDS": str(self.policy["verification"]["settle_seconds"])})
        inc.write("verify.log", f"$ {' '.join(vcmd)}\n{vout}\nexit={vrc}\n")
        decision["executed"].append({"runbook": "verify-recovery.sh", "command": vcmd, "rc": vrc})
        inc.audit("verify_recovery", rc=vrc, summary=vout.strip().splitlines()[-1:] if vout else [])

        if vrc == 0:
            decision["outcome"] = "fixed_and_verified"
            inc.write("decision.json", decision)
            self._close(inc, "resolved", f"fix {fix_sha} deployed and verified")
            return

        # 6. Verification failed: roll back automatically (allowlisted), then escalate.
        rcmd = [str(HERE / "runbooks" / "rollback.sh"), str(self.s.repo), rollback_tag, base_sha]
        rrc, rout = run(rcmd, self.s.repo, timeout=600)
        inc.write("rollback.log", f"$ {' '.join(rcmd)}\n{rout}\nexit={rrc}\n")
        decision["executed"].append({"runbook": "rollback.sh", "command": rcmd, "rc": rrc})
        decision["outcome"] = "rolled_back"
        inc.write("decision.json", decision)
        self._escalate(inc, f"verification failed after deploying {fix_sha}; rolled back (exit {rrc})")

    # ---------------------------------------------------------------- helpers
    def _verification_paths(self, packet: dict, response: dict) -> list[str]:
        route_re = re.compile(r"^/api/orders/[A-Za-z0-9_\-]{1,64}$")  # replay only safe GETs we understand
        paths = list(packet.get("failing_request_samples", []))
        for p in response.get("verification_requests", []):
            if route_re.match(p) and p not in paths:
                paths.append(p)
        return paths[:5] or ["/healthz"]

    def _cleanup_worktree(self, inc: Incident, workdir: Path, branch: str | None, keep_branch: bool = False) -> None:
        if branch is None:
            return
        run(["git", "worktree", "remove", "--force", str(workdir)], self.s.repo)
        if not keep_branch:
            run(["git", "branch", "-D", branch], self.s.repo)
        inc.audit("worktree_removed", branch=branch, branch_kept=keep_branch)

    def _close(self, inc: Incident, state: str, note: str) -> None:
        inc.status(state=state, closed_at=now_iso(), note=note)
        inc.audit("incident_closed", state=state, note=note)
        inc.write("report.md", render_report(inc))

    def _escalate(self, inc: Incident, reason: str) -> None:
        inc.status(state="escalated", escalated_at=now_iso(), escalation_reason=reason)
        inc.audit("escalated", reason=reason)
        inc.write("escalation.md", render_escalation(inc, reason))
        inc.write("report.md", render_report(inc))


def _maybe(inc: Incident, name: str):
    p = inc.root / name
    if not p.exists():
        return None
    return json.loads(p.read_text()) if name.endswith(".json") else p.read_text()


def render_report(inc: Incident) -> str:
    st = _maybe(inc, "status.json") or {}
    alert = (_maybe(inc, "alert.json") or {}).get("alert", {})
    resp = _maybe(inc, "response.json") or {}
    dec = _maybe(inc, "decision.json") or {}
    run_meta = _maybe(inc, "agent/run.json") or {}
    L = [f"# Incident {inc.id}", "",
         f"- **State**: {st.get('state')} ({st.get('note') or st.get('escalation_reason') or ''})",
         f"- **Opened**: {st.get('opened_at')} | **closed/escalated**: {st.get('closed_at') or st.get('escalated_at')}",
         f"- **Alert**: {alert.get('labels', {}).get('alertname')} status={alert.get('status')} "
         f"route=`{st.get('route')}` labels=`{json.dumps(alert.get('labels', {}))}`",
         f"- **Summary (Grafana)**: {alert.get('annotations', {}).get('summary')}", "",
         "## Agent", f"- Agent: {run_meta.get('agent')} | model: {run_meta.get('model') or 'CLI default'} "
                     f"| mode: {run_meta.get('mode')} | exit: {run_meta.get('returncode')} "
                     f"| duration: {round(run_meta.get('duration_s') or 0, 1)} s",
         f"- Models reported by the CLI: {(run_meta.get('meta') or {}).get('models_used')}",
         f"- Command: `{' '.join(run_meta.get('command') or [])}`", ""]
    if resp:
        L += [f"- Classification: **{resp['classification']}** (confidence {resp['confidence']})",
              f"- Proposed action: **{resp['proposed_action']}**",
              f"- User impact: {resp['user_impact']}", f"- Root cause: {resp['root_cause']}", "",
              "### Evidence cited by the agent"]
        L += [f"- [{e['source']}] {e['reference']}: {e['observation']}" for e in resp["evidence"]] or ["- none"]
        L += ["", "### Agent final message", "```", resp["final_message"], "```", ""]
    if dec:
        L += ["## Policy decision", f"- Level {dec.get('level')} ({dec.get('level_name')}): {dec.get('level_reason')}",
              f"- Allowed: {dec.get('allowed')} | outcome: **{dec.get('outcome')}**"]
        L += [f"  - {'PASS' if c['ok'] else 'FAIL'} {c['check']}: {c['detail']}" for c in dec.get("checks", [])]
        if dec.get("diff"):
            L.append(f"- Diff: {dec['diff']}")
        L += ["", "## Commands executed by the responder (not by the model)"]
        L += [f"- `{' '.join(x['command'])}` -> exit {x['rc']}" for x in dec.get("executed", [])] or ["- none"]
    for name in ("verify.log", "deploy.log", "rollback.log"):
        body = _maybe(inc, name)
        if body:
            L += ["", f"## {name}", "```", body[-2500:], "```"]
    L += ["", "Files: alert.json, evidence/, prompt.md, agent/, response.json, decision.json, fix.patch, tests.log, "
              "deploy.log, verify.log, audit.jsonl"]
    return "\n".join(L) + "\n"


def render_escalation(inc: Incident, reason: str) -> str:
    st = _maybe(inc, "status.json") or {}
    resp = _maybe(inc, "response.json") or {}
    return "\n".join([
        f"# Escalation packet: {inc.id}", "",
        f"**Why a human is needed**: {reason}", "",
        f"- Route: `{st.get('route')}`",
        f"- Agent diagnosis: {resp.get('root_cause') or 'n/a'} (confidence {resp.get('confidence', 'n/a')})",
        f"- Proposed action: {resp.get('proposed_action', 'n/a')}", "",
        "Start with `evidence/summary.md`, then `response.json` and `audit.jsonl`.",
        "Fix branch (if any): `git branch --list 'incident/*'`.", ""])
