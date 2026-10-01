"""Bounded, repeatable evidence packet, collected BEFORE any model is involved.

- Read-only HTTP GETs against Prometheus, Loki and Tempo, from a fixed set of query
  templates. The only variable part is the route, which is validated first.
- Every list is capped and every string truncated; secrets-looking values are redacted.
- Output: evidence.json (machine) + summary.md (human and agent).

CLI: python -m responder.evidence --route "/api/orders/{order_id}" --out DIR
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROUTE_RE = re.compile(r"^/[A-Za-z0-9_\-./{}]{0,120}$")
MAX_STR = 4000
REDACTIONS = [
    (re.compile(r"(?i)(authorization|bearer|token|password|passwd|secret|api[_-]?key)(\"?\s*[:=]\s*\"?)[^\s\",]+"), r"\1\2[REDACTED]"),
    # local part must not start right after a backslash (JSON "\n@decorator" is not an email)
    (re.compile(r"(?<![\\A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b(sk|ghp|gho|xox[abp])[-_][A-Za-z0-9-_]{16,}\b"), "[REDACTED_KEY]"),
]


def cfg(name: str, default: str) -> str:
    return os.getenv(name, default).rstrip("/")


def redact(value: Any, limit: int | None = MAX_STR) -> Any:
    if isinstance(value, str):
        for pattern, repl in REDACTIONS:
            value = pattern.sub(repl, value)
        return value if limit is None or len(value) <= limit else value[:limit] + "...[truncated]"
    if isinstance(value, list):
        return [redact(v, limit) for v in value]
    if isinstance(value, dict):
        return {k: redact(v, limit) for k, v in value.items()}
    return value


def validate_route(route: str | None) -> str | None:
    if route is None or route == "":
        return None
    if not ROUTE_RE.match(route):
        raise ValueError(f"route rejected by allowlist regex: {route!r}")
    return route


def _get(client: httpx.Client, url: str, params: dict) -> dict:
    try:
        r = client.get(url, params=params)
        r.raise_for_status()
        return {"ok": True, "data": r.json()}
    except Exception as exc:  # evidence collection must never crash the responder
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:500]}


def _prom(client, query: str) -> dict:
    res = _get(client, cfg("PROMETHEUS_URL", "http://localhost:9090") + "/api/v1/query", {"query": query})
    if res["ok"]:
        res = {"ok": True, "query": query,
               "result": [{"labels": s["metric"], "value": s["value"][1]} for s in res["data"]["data"]["result"]][:30]}
    else:
        res["query"] = query
    return res


def five_xx_expr(route: str | None) -> str:
    sel = 'job="order-tracker", http_response_status_code=~"5.."'
    if route:
        sel += f', http_route="{route}"'
    m = f"app_http_requests_total{{{sel}}}"
    return f"sum by (http_route, error_type, service_version) (({m} unless {m} offset 5m) or increase({m}[5m]))"


def collect_metrics(client, route: str | None, window_m: int) -> dict:
    sel = 'job="order-tracker"' + (f', http_route="{route}"' if route else "")
    return {
        "five_xx_last_5m": _prom(client, five_xx_expr(route)),
        "requests_by_status_window": _prom(
            client,
            f"sum by (http_route, http_response_status_code) (increase(app_http_requests_total{{{sel}}}[{window_m}m]))"),
        "cumulative_by_status": _prom(
            client, f"sum by (http_route, http_response_status_code, error_type) (app_http_requests_total{{{sel}}})"),
        "deployed_versions": _prom(client, 'count by (service_version) (app_http_requests_total{job="order-tracker"})'),
    }


def collect_logs(client, route: str | None, window_m: int, limit: int = 20) -> dict:
    q = '{service_name="order-tracker"} | severity_text="ERROR"'
    if route:
        q += f' | http_route="{route}"'
    now = time.time_ns()
    res = _get(client, cfg("LOKI_URL", "http://localhost:3100") + "/loki/api/v1/query_range",
               {"query": q, "limit": limit, "direction": "backward",
                "start": now - window_m * 60 * 10**9, "end": now})
    if not res["ok"]:
        return {**res, "query": q}
    keep = ("trace_id", "span_id", "http_route", "order_id", "http_response_status_code", "error_type",
            "exception_type", "exception_message", "exception_stacktrace", "service_version", "code_file_path",
            "code_line_number")
    lines = []
    for stream in res["data"]["data"]["result"]:
        labels = stream["stream"]
        for ts, line in stream["values"]:
            lines.append({"ts": datetime.fromtimestamp(int(ts) / 1e9, timezone.utc).isoformat(),
                          "line": line, **{k: labels[k] for k in keep if k in labels}})
    lines.sort(key=lambda x: x["ts"], reverse=True)
    return {"ok": True, "query": q, "count": len(lines), "lines": lines[:limit]}


def _attrs(attributes: list[dict]) -> dict:
    out = {}
    for a in attributes or []:
        v = a.get("value", {})
        out[a["key"]] = next(iter(v.values()), None) if v else None
    return out


def collect_traces(client, route: str | None, window_m: int, limit: int = 5,
                   log_trace_ids: list[str] | None = None) -> dict:
    tempo = cfg("TEMPO_URL", "http://localhost:3200")
    q = '{resource.service.name="order-tracker" && status=error' + (f' && span.http.route="{route}"' if route else "") + "}"
    now = int(time.time())
    res = _get(client, tempo + "/api/search", {"q": q, "limit": limit, "start": now - window_m * 60, "end": now})
    if not res["ok"]:
        return {**res, "query": q}
    found = res["data"].get("traces", [])[:limit]
    # Search lags a few seconds behind ingestion; lookup by id does not. Fall back to the
    # trace ids carried by the error logs so the packet does not depend on that timing.
    for tid in (log_trace_ids or []):
        if len(found) >= limit:
            break
        if tid and all(t["traceID"] != tid for t in found):
            found.append({"traceID": tid, "rootTraceName": None, "durationMs": None, "startTimeUnixNano": "0",
                          "via": "trace_id from error log"})
    traces = []
    for t in found:
        full = _get(client, f"{tempo}/api/v2/traces/{t['traceID']}", {})
        spans, seen = [], set()
        if full["ok"]:
            for rs in full["data"].get("trace", {}).get("resourceSpans", []):
                for ss in rs.get("scopeSpans", []):
                    for s in ss.get("spans", []):
                        if s["spanId"] in seen:
                            continue
                        seen.add(s["spanId"])
                        spans.append({
                            "name": s["name"],
                            "status": s.get("status", {}),
                            "attributes": _attrs(s.get("attributes")),
                            "events": [{"name": e.get("name"), **_attrs(e.get("attributes"))} for e in s.get("events", [])],
                        })
        root = next((sp for sp in spans if sp["attributes"].get("http.route")), None)
        traces.append({"trace_id": t["traceID"], "root": t.get("rootTraceName") or (root or {}).get("name"),
                       "duration_ms": t.get("durationMs"), "found_via": t.get("via", "tempo search"),
                       "start": datetime.fromtimestamp(int(t["startTimeUnixNano"]) / 1e9, timezone.utc).isoformat(),
                       "spans": spans})
    return {"ok": True, "query": q, "count": len(traces), "traces": traces}


def _run(cmd: list[str], cwd: Path) -> str:
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=20).stdout.strip()[:3000]
    except Exception as exc:
        return f"unavailable: {exc}"


def collect_deploy(repo: Path) -> dict:
    app = cfg("APP_BASE_URL", "http://localhost:8000")
    try:
        health = httpx.get(app + "/healthz", timeout=3)
        health_s = f"{health.status_code} {health.text[:200]}"
    except Exception as exc:
        health_s = f"unreachable: {exc}"
    return {
        "git_head": _run(["git", "rev-parse", "--short", "HEAD"], repo),
        "git_branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo),
        "recent_commits": _run(["git", "log", "-8", "--pretty=format:%h %ad %s", "--date=iso"], repo).splitlines(),
        "app_container": _run(["docker", "compose", "ps", "app", "--format",
                               "{{.Name}} {{.Image}} {{.State}} {{.Status}} created={{.CreatedAt}}"], repo),
        "healthz": health_s,
    }


def failing_request_samples(traces: dict, logs: dict | None = None) -> list[str]:
    """Concrete GET paths that failed, rebuilt from span / log attributes (order.id)."""
    paths = []
    for line in (logs or {}).get("lines", []):
        oid = line.get("order_id")
        if line.get("http_route") == "/api/orders/{order_id}" and oid:
            p = f"/api/orders/{oid}"
            if p not in paths and ROUTE_RE.match(p):
                paths.append(p)
    for t in traces.get("traces", []):
        for s in t["spans"]:
            a = s["attributes"]
            route, oid = a.get("http.route"), a.get("order.id")
            if route == "/api/orders/{order_id}" and oid and a.get("http.request.method") == "GET":
                p = f"/api/orders/{oid}"
                if p not in paths and ROUTE_RE.match(p):
                    paths.append(p)
    return paths[:5]


def collect(route: str | None, out_dir: Path, repo: Path, window_m: int = 15) -> dict:
    route = validate_route(route)
    window_m = max(1, min(int(window_m), 60))
    out_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=10) as client:
        packet = {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "route": route,
            "window_minutes": window_m,
            "metrics": collect_metrics(client, route, window_m),
            "logs": collect_logs(client, route, window_m),
        }
        packet["traces"] = collect_traces(client, route, window_m,
                                          log_trace_ids=[l.get("trace_id") for l in packet["logs"].get("lines", [])][:3])
        packet.update({
            "deploy": collect_deploy(repo),
        })
    packet["failing_request_samples"] = failing_request_samples(packet["traces"], packet["logs"])
    packet = redact(packet)
    (out_dir / "evidence.json").write_text(json.dumps(packet, indent=2))
    (out_dir / "summary.md").write_text(render_summary(packet))
    return packet


def render_summary(p: dict) -> str:
    L = [f"# Evidence packet ({p['collected_at']})", "",
         f"- Route under investigation: `{p['route']}`" if p["route"] else "- Route: none given by the alert",
         f"- Window: last {p['window_minutes']} min", ""]
    L.append("## Metrics (Prometheus)")
    for name, m in p["metrics"].items():
        L.append(f"- **{name}** `{m.get('query')}`")
        if not m.get("ok"):
            L.append(f"  - query failed: {m.get('error')}")
        for r in m.get("result", [])[:10]:
            L.append(f"  - {json.dumps(r['labels'], sort_keys=True)} = {r['value']}")
        if m.get("ok") and not m.get("result"):
            L.append("  - (no series)")
    L += ["", "## Error logs (Loki)", f"`{p['logs'].get('query')}` -> {p['logs'].get('count', 0)} line(s)"]
    for line in p["logs"].get("lines", [])[:5]:
        L.append(f"- {line['ts']} {line['line']} trace_id={line.get('trace_id')} "
                 f"exception={line.get('exception_type')}: {line.get('exception_message')}")
    first = next((l for l in p["logs"].get("lines", []) if l.get("exception_stacktrace")), None)
    if first:
        L += ["", "Most recent stack trace:", "```", first["exception_stacktrace"][-2500:], "```"]
    L += ["", "## Error traces (Tempo)", f"`{p['traces'].get('query')}` -> {p['traces'].get('count', 0)} trace(s)"]
    for t in p["traces"].get("traces", [])[:3]:
        L.append(f"- trace {t['trace_id']} `{t['root']}` {t['duration_ms']} ms at {t['start']}")
        for s in t["spans"]:
            attrs = {k: v for k, v in s["attributes"].items() if k in (
                "http.route", "http.response.status_code", "order.id", "order.priority", "error.type")}
            L.append(f"  - span `{s['name']}` status={s['status'].get('code', 'UNSET')} {json.dumps(attrs)}")
            for e in s["events"]:
                if e.get("name") == "exception":
                    L.append(f"    - exception {e.get('exception.type')}: {e.get('exception.message')}")
    L += ["", "## Failing request samples (rebuilt from span attributes)"]
    L += [f"- GET {x}" for x in p["failing_request_samples"]] or ["- none"]
    d = p["deploy"]
    L += ["", "## Deployment", f"- git HEAD: {d['git_head']} on {d['git_branch']}", f"- app container: {d['app_container']}",
          f"- /healthz: {d['healthz']}", "- recent commits:"] + [f"  - {c}" for c in d["recent_commits"]]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--route", default=None)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--window", default=15, type=int)
    ap.add_argument("--repo", default=Path(__file__).resolve().parents[2], type=Path)
    a = ap.parse_args()
    packet = collect(a.route, a.out, a.repo, a.window)
    print(json.dumps({"out": str(a.out), "logs": packet["logs"].get("count"), "traces": packet["traces"].get("count"),
                      "samples": packet["failing_request_samples"]}))


if __name__ == "__main__":
    main()
