#!/usr/bin/env bash
# Deterministic toolchain PATH + version pins for 03-deployment, Windows / Git Bash.
#
# The machine can have multiple installs of the same tool on PATH (e.g. several `uv`
# versions, or Docker Desktop's bundled `kubectl` ahead of a pinned release). Sourcing
# this file makes every command in this directory resolve the same pinned versions,
# regardless of what else is installed system-wide.
#
# Usage: source this at the top of every command in the reproduction/evidence suite:
#   source scripts/toolchain.sh
#
# Expected versions can be overridden for testing without editing this file:
#   EXPECT_KIND=... EXPECT_KUBECTL=... EXPECT_UV=... source scripts/toolchain.sh

export MSYS_NO_PATHCONV=1

: "${EXPECT_KIND:=0.30.0}"
: "${EXPECT_KUBECTL:=v1\.34\.}"
: "${EXPECT_UV:=0\.12\.}"

_toolchain_fail=0

KUBECTL_DIR="$HOME/bin/kubectl134"
WINGET_PKGS="$HOME/AppData/Local/Microsoft/WinGet/Packages"

KIND_INSTALL_HINT="winget install Kubernetes.kind --version 0.30.0 --accept-package-agreements --accept-source-agreements"
UV_INSTALL_HINT="winget install astral-sh.uv --version 0.12.18 --accept-package-agreements --accept-source-agreements"
ACT_INSTALL_HINT="winget install nektos.act --accept-package-agreements --accept-source-agreements"
KUBECTL_INSTALL_HINT='mkdir -p "$HOME/bin/kubectl134" && cd "$HOME/bin/kubectl134" && curl -fsSLO https://dl.k8s.io/release/v1.34.1/bin/windows/amd64/kubectl.exe && curl -fsSLO https://dl.k8s.io/release/v1.34.1/bin/windows/amd64/kubectl.exe.sha256 && [ "$(sha256sum kubectl.exe | cut -d\" \" -f1)" = "$(cat kubectl.exe.sha256)" ] && echo "HASH OK" || echo "HASH MISMATCH - DO NOT USE"'

DOCKER_INSTALL_HINT="https://docs.docker.com/desktop/setup/install/windows-install/"

# Find exactly one winget package directory that actually contains the executable
# (globbing by name prefix alone is not enough: a leftover/backup directory can
# match the same prefix). Zero or more-than-one match is always a FAIL, never a
# guess. `blocking` (default 1) controls whether that FAIL counts toward the
# script's overall exit status — act's discovery uses blocking=0 because act
# itself is informational-only (see _toolchain_require calls below).
# NOTE: this function is invoked as `X=$(_toolchain_find_one ...)`, i.e. inside a
# command-substitution subshell — any assignment to _toolchain_fail here would be
# local to that subshell and lost when it exits. So this function only *reports*
# (echoes the path, or an error, and returns a status code); the caller is what
# sets _toolchain_fail, from the function's real exit code ($?), in the parent shell.
_toolchain_find_one() {
  local label="$1" glob_pattern="$2" exe_name="$3" hint="$4" blocking="${5:-1}"
  local -a matches=()
  local d tag="FAIL"
  [ "$blocking" -eq 0 ] && tag="WARN"
  for d in "$WINGET_PKGS"/$glob_pattern; do
    [ -d "$d" ] || continue
    [ -x "$d/$exe_name" ] && matches+=("$d")
  done
  case "${#matches[@]}" in
    1)
      echo "${matches[0]}"
      return 0
      ;;
    0)
      echo "$tag $label: aucun dossier winget ne contient $exe_name (motif '$glob_pattern')." >&2
      echo "     installer via : $hint" >&2
      return 1
      ;;
    *)
      echo "$tag $label: plusieurs dossiers contiennent $exe_name, choix ambigu :" >&2
      printf '     - %s\n' "${matches[@]}" >&2
      echo "     supprime les dossiers obsolètes, ou réinstalle via : $hint" >&2
      return 1
      ;;
  esac
}

UV_DIR=$(_toolchain_find_one "uv" "astral-sh.uv_*" "uv.exe" "$UV_INSTALL_HINT"); UV_FOUND=$?
KIND_DIR=$(_toolchain_find_one "kind" "Kubernetes.kind_*" "kind.exe" "$KIND_INSTALL_HINT"); KIND_FOUND=$?
ACT_DIR=$(_toolchain_find_one "act" "nektos.act_*" "act.exe" "$ACT_INSTALL_HINT" 0); ACT_FOUND=$?

# ACT_FOUND is deliberately NOT propagated to _toolchain_fail: act stays
# informational-only (see the act block below), per spec.
[ "$KIND_FOUND" -ne 0 ] && _toolchain_fail=1
[ "$UV_FOUND" -ne 0 ] && _toolchain_fail=1

for d in "$KUBECTL_DIR" "$UV_DIR" "$KIND_DIR" "$ACT_DIR"; do
  if [ -n "$d" ] && [ -d "$d" ]; then
    export PATH="$d:$PATH"
  fi
done

_toolchain_require() {
  # name, binary, expect_regex, install_hint, already_diagnosed(1 = the
  # directory search above already FAILed and printed why — don't repeat it)
  local name="$1" bin="$2" expect="$3" hint="$4" already_diagnosed="${5:-0}"
  if ! command -v "$bin" >/dev/null 2>&1; then
    if [ "$already_diagnosed" -ne 1 ]; then
      echo "FAIL $name: introuvable sur le PATH."
      echo "     installer via : $hint"
      _toolchain_fail=1
    fi
    return
  fi
  local got
  got=$("$bin" --version 2>&1 || true)
  if [[ "$bin" == "kubectl" ]]; then
    got=$(kubectl version --client 2>&1 | head -1)
  fi
  if [[ "$got" =~ $expect ]]; then
    echo "OK   $name: $got"
  else
    echo "FAIL $name: version '$got' ne correspond pas à \$EXPECT_${name^^} (/$expect/)."
    echo "     installer/réinstaller via : $hint"
    _toolchain_fail=1
  fi
}

# kind/uv already had their directory resolved (or diagnosed) above; kubectl's
# directory is fixed (not globbed), so it's never "already diagnosed" here.
_toolchain_require "kind" "kind" "$EXPECT_KIND" "$KIND_INSTALL_HINT" "$KIND_FOUND"
_toolchain_require "kubectl" "kubectl" "$EXPECT_KUBECTL" "$KUBECTL_INSTALL_HINT" 0
_toolchain_require "uv" "uv" "$EXPECT_UV" "$UV_INSTALL_HINT" "$UV_FOUND"

if command -v act >/dev/null 2>&1; then
  echo "INFO act: $(act --version 2>&1)"
else
  echo "INFO act: introuvable (non bloquant) — installer via : $ACT_INSTALL_HINT"
fi

# docker / docker compose: presence + CLI responsiveness only (no daemon
# contact needed for `--version` or `compose version`). Whether the *engine*
# is actually reachable right now is a separate, per-step check — this file
# is about which binaries and versions resolve, not runtime engine state.
if command -v docker >/dev/null 2>&1; then
  echo "OK   docker: $(docker --version 2>&1)"
else
  echo "FAIL docker: introuvable sur le PATH."
  echo "     installer via : $DOCKER_INSTALL_HINT"
  _toolchain_fail=1
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "OK   docker compose: $(docker compose version 2>&1)"
else
  echo "FAIL docker compose: plugin introuvable ou ne répond pas."
  echo "     installer via : $DOCKER_INSTALL_HINT (inclut Compose v2)"
  _toolchain_fail=1
fi

if [ "$_toolchain_fail" -ne 0 ]; then
  echo "toolchain.sh: version check FAILED — voir ci-dessus" >&2
  return 1 2>/dev/null || exit 1
fi

echo "toolchain.sh: OK — MSYS_NO_PATHCONV=1, PATH pinné (kubectl134, uv winget, kind, act)"
