# Responder capability table

Every capability the incident responder (and the model inside it) holds, who holds it, and what bounds it.
Principle: **the model may reason; the system observes, authorizes, verifies and remembers.**

| # | Capability | Held by | Credential / access used | Bound (where enforced) | Residual risk |
|---|---|---|---|---|---|
| 1 | Receive alerts on `POST /alerts` :8001 | responder (code) | none from loopback; `Bearer RESPONDER_TOKEN` otherwise | `server._authorized` (hmac compare), 256 KB cap, 20 alerts/payload, dedupe by fingerprint | Anyone on the host can post an alert from loopback (by design, for the homework curl). |
| 2 | Query Prometheus / Loki / Tempo | responder (code) | none (backends on 127.0.0.1) | fixed query templates, route regex allowlist, limits (20 logs, 5 traces, 30 series), 10 s timeout, redaction (`evidence.py`) | Backends have no auth; they are bound to 127.0.0.1 only. |
| 3 | Read repo code + evidence | model | filesystem read via CLI tools | Claude: `--allowedTools Read,Glob,Grep` (+ `--add-dir` evidence); Codex: `--sandbox read-only` | The model can read any file the CLI can reach, including `.env` if it is inside the repo. See finding in the report. |
| 4 | Edit code | model | filesystem write | only at level >= 1, only inside an isolated git worktree (`incident/<id>` branch); Claude `acceptEdits` + deny list; Codex `workspace-write` | Edits outside `app/`/`tests/` are possible in the worktree but are **rejected by the gate** before anything is deployed. |
| 5 | Run tests | model | `uv run --frozen pytest` | Claude allow pattern `Bash(uv run --frozen pytest:*)`; no other shell | Test code is Python: a malicious test could execute code on the host (inside the worktree user). Mitigated by the model having no network tool; not a sandbox. |
| 5b | Read-only shell (observed: `sed -n`, `ls`, `git log`) | model | Claude Code auto-approves some read-only commands even outside `--allowedTools` | nothing beyond what `Read` already allows | Seen in `INC-20260930-125833-d5da/agent/agent-tool-calls.md`; keep in mind when reasoning about "allowlist = complete list". |
| 6 | Network, Docker, git push/commit, curl | **nobody in the model** | - | Claude `--disallowedTools WebFetch,WebSearch,Bash(docker:*),Bash(curl:*),Bash(git commit:*),Bash(git push:*)...`; Codex `network_access=false`; no MCP server (`agent-mcp.json` empty, `--strict-mcp-config`) | Deny-lists are weaker than a real sandbox for Claude; run the responder under a dedicated user or container for production. |
| 7 | Commit the fix | responder (code) | local git | only after gate: paths allowlist, <= 4 files, <= 80 lines, confidence >= 0.7, tests re-run by responder, regression test fails without the fix | - |
| 8 | Deploy (rebuild + restart app) | responder (code) | local Docker socket (the operator's) | level 2 only, `runbooks/deploy-fix.sh` only: refuses dirty tree, `--ff-only`, `--no-deps app` | Docker socket = root-equivalent on the host; held by code, never by the model. |
| 9 | Roll back | responder (code) | local Docker | `runbooks/rollback.sh` with the image tagged just before deploy; automatic only after a failed verification | Only covers fixes deployed by the responder (no general release history). |
| 10 | Verify recovery | responder (code) | HTTP GET to app + Prometheus | replays only `GET /api/orders/<id>` paths observed failing (regex), healthz, 5xx counter delta | Replaying GETs is safe here (idempotent); do not extend to POST/PATCH. |
| 11 | Agent auth (Anthropic / OpenAI) | agent CLI | operator's CLI login or API key | env allowlist (`agents.agent_env`): only `ANTHROPIC_*`, `CLAUDE_*`, `OPENAI_*`, `CODEX_*` + basics; `RESPONDER_TOKEN`, Grafana password stripped | Budget: max 6 agent runs/hour, 900 s timeout, 40 turns. |

## Provenance / supply chain
| Component | Source | Pinned? |
|---|---|---|
| Claude Code CLI | npm `@anthropic-ai/claude-code` (operator install) | version recorded per incident in `audit.jsonl` |
| Codex CLI | npm `@openai/codex` (operator install) | version recorded per incident |
| MCP servers / skills for the responder | none (`incident-response/agent-mcp.json`) | scanned with Snyk Agent Scan |
| Python deps | `uv.lock` (app, responder) | yes (lockfiles, `--frozen`) |
| Alert identity | fingerprint recomputed server-side from labels | sender cannot dodge de-duplication |
| Images | Docker Hub tags `prom/prometheus:v3.5.5`, `grafana/loki:3.6.17`, `grafana/tempo:2.10.8`, `otel/opentelemetry-collector-contrib:0.162.0`, `grafana/grafana:12.4.12`, `python:3.12-slim` | tag-pinned, not digest-pinned (Semgrep finding, accepted for the homework) |
