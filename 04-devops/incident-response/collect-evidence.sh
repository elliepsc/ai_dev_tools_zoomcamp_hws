#!/usr/bin/env bash
# Collect a bounded, read-only evidence packet (metrics, logs, traces, deploy state).
# Same code path the responder uses before any model is involved.
#
#   ./incident-response/collect-evidence.sh "/api/orders/{order_id}" /tmp/evidence [window_minutes]
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
route=${1:-}; out=${2:?output dir}; window=${3:-15}
exec uv run --quiet --project "$here" python -m responder.evidence \
  --route "$route" --out "$out" --window "$window" --repo "$here/.."
