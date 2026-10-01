# Security audit brief (recurring, read-only)

You are reviewing the **Order Tracker** repository with a security reviewer's eye. You may only
read files. Report findings as JSON matching `security-audit/findings.schema.json`.

## Scope
- `app/` (FastAPI app + OpenTelemetry instrumentation)
- `incident-response/` (webhook intake, evidence collection, agent adapter, policy, runbooks)
- `observability/` (Collector, Prometheus, Loki, Tempo, Grafana provisioning), `compose.yaml`, `Dockerfile`

## Threat model to test against
1. **Untrusted alert payloads** reach `POST /alerts` and are embedded in the agent prompt:
   prompt injection, oversized payloads, spoofed alerts, replay/flooding (cost), path traversal.
2. **Excessive agency**: what can the headless agent actually do (tools, filesystem, network,
   git, docker)? Can a model output lead to an action the policy did not intend?
3. **Secrets**: tokens in env, in logs, in the evidence packet, in incident records committed to git.
4. **PII in telemetry**: customer data in spans, metrics, logs; what reaches Loki/Tempo and the agent.
5. **Network exposure**: ports bound beyond localhost, default credentials, unauthenticated backends.
6. **Command injection**: any subprocess or shell script fed with alert/model data.
7. **Supply chain**: unpinned images/binaries, agent extensions (MCP servers, skills).

## Rules
- Cite the exact file and line; quote the code in `evidence`. No finding without evidence.
- Distinguish a real exploitable issue from a hardening suggestion (use severity `info`/`low`).
- Do not report the known, intentional homework bug in `order_detail` (express date).
- A Semgrep run already exists in `security-audit/runs/`; do not repeat pure style findings.
