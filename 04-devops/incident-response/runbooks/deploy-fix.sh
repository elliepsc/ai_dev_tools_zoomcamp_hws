#!/usr/bin/env bash
# Allowlisted runbook: deploy a fix branch produced by the responder.
# Called ONLY by the responder after the policy gate passed. Never by the model.
#
#   deploy-fix.sh <repo_dir> <fix_branch> <incident_id>
#
# 1. refuse if tracked files in the working tree are dirty (never overwrite human work)
# 2. tag the currently running image as the rollback target
# 3. fast-forward the current branch to the fix branch (no merge commits, no force)
# 4. rebuild + restart ONLY the app service and wait for its healthcheck
# Prints the rollback image tag on the last line.
set -euo pipefail

repo=${1:?repo dir}; branch=${2:?fix branch}; incident=${3:?incident id}
cd "$repo"

# Incident records (written by the responder itself) are the only tracked files allowed to differ.
if ! git diff --quiet HEAD -- . ':(exclude)incident-response/incidents' \
   || ! git diff --cached --quiet -- . ':(exclude)incident-response/incidents'; then
  echo "refusing: tracked files have uncommitted changes in $repo" >&2
  exit 3
fi

image="order-tracker:${ORDER_TRACKER_TAG:-local}"
rollback_tag="order-tracker:rollback-${incident}"
docker image tag "$image" "$rollback_tag"
echo "rollback target: $rollback_tag ($(git rev-parse --short HEAD))"

git merge --ff-only "$branch"
version=$(git rev-parse --short HEAD)

APP_VERSION="$version" docker compose up --build -d --wait --no-deps app
echo "deployed $version"
echo "$rollback_tag"
