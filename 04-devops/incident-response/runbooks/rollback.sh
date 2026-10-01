#!/usr/bin/env bash
# Allowlisted runbook: put the previous app image back in service (no rebuild).
#
#   rollback.sh <repo_dir> <rollback_image_tag> [<git_ref_to_restore>]
#
# The image is the source of truth for what was running. If a git ref is given,
# the branch is reset to it too (only fast, local, reversible: the fix commit
# stays reachable on its incident/* branch).
set -euo pipefail

repo=${1:?repo dir}; rollback_image=${2:?rollback image tag}; git_ref=${3:-}
cd "$repo"

docker image inspect "$rollback_image" >/dev/null
tag=${rollback_image#order-tracker:}
ORDER_TRACKER_TAG="$tag" APP_VERSION="rollback" docker compose up -d --wait --no-deps --no-build app
echo "app now runs $rollback_image"

if [[ -n "$git_ref" ]]; then
  git reset --keep "$git_ref"
  echo "branch reset to $git_ref"
fi
