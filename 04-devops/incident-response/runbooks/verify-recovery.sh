#!/usr/bin/env bash
# Verify recovery from the USER's point of view AND from telemetry.
#
#   verify-recovery.sh <route_template> <path> [<path>...]
#
# - /healthz must answer 200
# - every previously failing GET path is replayed N times: no 5xx allowed
# - after the metric export interval, the 5xx counter of the route must not have grown
# Exit 0 = recovered. Prints a JSON summary on the last line.
set -euo pipefail

route=${1:?route template}; shift
app=${APP_BASE_URL:-http://localhost:8000}
prom=${PROMETHEUS_URL:-http://localhost:9090}
attempts=${VERIFY_ATTEMPTS:-3}
settle=${VERIFY_SETTLE_SECONDS:-12}

five_xx_total() {
  local q="sum(app_http_requests_total{job=\"order-tracker\",http_route=\"$route\",http_response_status_code=~\"5..\"}) or vector(0)"
  curl -fsS -G "$prom/api/v1/query" --data-urlencode "query=$q" \
    | python3 -c 'import sys,json; r=json.load(sys.stdin)["data"]["result"]; print(int(float(r[0]["value"][1])) if r else 0)'
}

ok=true
health=$(curl -s -o /dev/null -w '%{http_code}' "$app/healthz" || echo 000)
[[ "$health" == "200" ]] || ok=false
echo "healthz -> $health"

# Counter is per process; after a redeploy it restarts from 0. Read it now (after deploy).
sleep "$settle"
before=$(five_xx_total || echo "error")

codes=()
for path in "$@"; do
  for ((i = 1; i <= attempts; i++)); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "$app$path" || echo 000)
    codes+=("$path=$code")
    echo "GET $path -> $code"
    [[ "$code" =~ ^5 || "$code" == "000" ]] && ok=false
  done
done

sleep "$settle"
after=$(five_xx_total || echo "error")
echo "5xx counter for $route: before=$before after=$after"
if [[ "$before" == "error" || "$after" == "error" ]]; then
  ok=false
elif (( after > before )); then
  ok=false
fi

printf '{"recovered": %s, "healthz": "%s", "five_xx_before": "%s", "five_xx_after": "%s", "replayed": "%s"}\n' \
  "$ok" "$health" "$before" "$after" "${codes[*]:-}"
[[ "$ok" == true ]]
