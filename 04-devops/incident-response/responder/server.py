"""HTTP intake for Grafana webhooks: POST /alerts on port 8001.

Security model:
- Requests from loopback (curl on this machine) are accepted without a token.
- Anything else (Grafana container via host.docker.internal) must send
  `Authorization: Bearer $RESPONDER_TOKEN`. No token configured -> loopback only.
- Payload size is capped; the alert is stored and redacted, never executed.
- The webhook returns 202 immediately; one worker thread runs incidents one at a time.
"""

from __future__ import annotations

import hmac
import ipaddress
import logging
import os
import queue
import threading

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from responder.pipeline import Incident, Responder, now_iso

MAX_BODY = 256 * 1024
MAX_QUEUE = 50
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("responder")

app = FastAPI(title="Order Tracker incident responder")
_responder: Responder | None = None
_jobs: "queue.Queue[str]" = queue.Queue(maxsize=MAX_QUEUE)


def responder() -> Responder:
    global _responder
    if _responder is None:
        _responder = Responder()
    return _responder


def _worker() -> None:
    while True:
        inc_id = _jobs.get()
        try:
            responder().handle(inc_id)
        finally:
            _jobs.task_done()


def start_worker() -> None:
    threading.Thread(target=_worker, name="incident-worker", daemon=True).start()


def _authorized(request: Request) -> bool:
    host = request.client.host if request.client else ""
    try:
        if ipaddress.ip_address(host).is_loopback:
            return True
    except ValueError:
        pass
    token = os.getenv("RESPONDER_TOKEN", "")
    header = request.headers.get("authorization", "")
    return bool(token) and hmac.compare_digest(header, f"Bearer {token}")


@app.get("/healthz")
def healthz():
    return {"status": "ok", "queue": _jobs.qsize()}


def _require_auth(request: Request) -> None:
    if not _authorized(request):
        raise HTTPException(401, "missing or invalid bearer token")


@app.post("/alerts", status_code=202)
async def alerts(request: Request):
    _require_auth(request)
    # Browser CSRF guard (security-audit M-01): a web page can POST text/plain to localhost
    # without a CORS preflight. Grafana and curl send JSON and no Origin header.
    if request.headers.get("origin"):
        raise HTTPException(403, "browser-originated requests are not accepted")
    if not request.headers.get("content-type", "").lower().startswith("application/json"):
        raise HTTPException(415, "Content-Type must be application/json")
    body = await request.body()
    if len(body) > MAX_BODY:
        raise HTTPException(413, "payload too large")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "invalid JSON")
    items = payload.get("alerts") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        raise HTTPException(422, "expected an Alertmanager/Grafana payload with a non-empty 'alerts' list")

    r = responder()
    accepted = []
    for alert in items[:20]:
        if not isinstance(alert, dict):
            continue
        if alert.get("status") == "resolved":
            accepted.append({"incident": r.mark_resolved(alert), "status": "resolved"})
            continue
        inc_id, new = r.open_or_attach(alert, payload)
        if new:
            try:
                _jobs.put_nowait(inc_id)
            except queue.Full:
                raise HTTPException(429, "incident queue full")
        accepted.append({"incident": inc_id, "status": "queued" if new else "attached_to_open_incident"})
    return JSONResponse({"accepted": accepted}, status_code=202)


@app.get("/incidents")
def incidents(request: Request):
    _require_auth(request)
    return [{k: s.get(k) for k in ("id", "state", "alertname", "route", "classification", "proposed_action",
                                   "opened_at", "updated_at")} for s in responder().list_incidents()]


@app.get("/incidents/{inc_id}")
def incident(inc_id: str, request: Request):
    _require_auth(request)
    if not inc_id.startswith("INC-") or "/" in inc_id or ".." in inc_id:
        raise HTTPException(404)
    root = responder().s.incidents_dir / inc_id
    if not (root / "status.json").exists():
        raise HTTPException(404)
    return Incident(root).read_json("status.json")


@app.get("/incidents/{inc_id}/report", response_class=PlainTextResponse)
def report(inc_id: str, request: Request):
    _require_auth(request)
    if not inc_id.startswith("INC-") or "/" in inc_id or ".." in inc_id:
        raise HTTPException(404)
    p = responder().s.incidents_dir / inc_id / "report.md"
    if not p.exists():
        raise HTTPException(404, "report not ready yet")
    return p.read_text()


def load_dotenv(path) -> None:
    """Share RESPONDER_* settings with docker compose's .env (never overrides the shell)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key.startswith(("RESPONDER_", "APP_BASE_URL", "PROMETHEUS_URL", "LOKI_URL", "TEMPO_URL")):
            os.environ.setdefault(key, value)


@app.post("/incidents/{inc_id}/close")
async def close(inc_id: str, request: Request):
    """Human disposition: closes an escalated/open incident so new alerts open a new one."""
    _require_auth(request)
    if not inc_id.startswith("INC-") or "/" in inc_id or ".." in inc_id:
        raise HTTPException(404)
    root = responder().s.incidents_dir / inc_id
    if not (root / "status.json").exists():
        raise HTTPException(404)
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    disposition = str(body.get("disposition", "closed by operator"))[:500]
    by = str(body.get("by", "operator"))[:80]
    inc = Incident(root)
    inc.audit("human_disposition", by=by, disposition=disposition)
    return inc.status(state="closed", closed_at=now_iso(), human_disposition=disposition, closed_by=by)


def main() -> None:
    from pathlib import Path

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    responder()  # fail fast on a bad policy file
    start_worker()
    host = os.getenv("RESPONDER_HOST", "0.0.0.0")
    port = int(os.getenv("RESPONDER_PORT", "8001"))
    if host != "127.0.0.1" and not os.getenv("RESPONDER_TOKEN"):
        log.warning("RESPONDER_TOKEN is not set: only loopback clients will be accepted (Grafana will get 401)")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
