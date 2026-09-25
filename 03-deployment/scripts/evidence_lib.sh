#!/usr/bin/env bash
# Helper for docs/evidence/*.txt capture scripts. Versioned (not scratch)
# because the methodology matters as much as the output: see the bug fixed
# here, referenced by "Supersedes commit 845f632" notes in evidence files.
#
# Bug history: an earlier version of record() did
#   eval "$cmd" 2>&1 | tee -a "$file"
# The left side of a pipe runs in a subshell in bash, so when $cmd was
# `source scripts/toolchain.sh`, its PATH/exports never escaped that subshell
# -- every later command in the same script silently fell back to whatever
# `uv`/`kind`/`kubectl` were first on the *unpinned* PATH. Caught when
# `kind get clusters` failed with "command not found" right after a
# toolchain.sh banner claiming kind was pinned and present, and confirmed via
# .venv/pyvenv.cfg showing `uv = 0.9.26` instead of the pinned 0.12.x.
#
# Fix: record() never puts the command itself on the left side of a pipe (it
# redirects to a temp file, then tees that file's content -- deterministic
# ordering, no subshell on $cmd). toolchain.sh is sourced directly by
# record_header(), never through record().
#
# Second bug history: each Bash tool invocation is its own fresh shell
# process, so neither PATH exports (source toolchain.sh) nor plain shell
# variables survive from one tool call to the next -- an evidence script that
# spans multiple tool calls must re-source toolchain.sh at the top of every
# call, and must never hand-retype a value captured by an earlier call (that
# happened once, for a task-id comparison in 04-kind.txt -- bounded risk
# since a typo would fail the assertion, not pass it, but still wrong).
# Fix: cross-call state goes through state_set/state_get below, backed by
# docs/evidence/.state/ (gitignored), never retyped by hand.
state_set() {
  local key="$1" value="$2"
  mkdir -p docs/evidence/.state
  printf '%s' "$value" > "docs/evidence/.state/$key"
}

state_get() {
  local key="$1"
  cat "docs/evidence/.state/$key" 2>/dev/null
}

set -o pipefail

record_header() {
  local file="$1"
  {
    echo "=== $(date -u +"%Y-%m-%dT%H:%M:%SZ") (UTC) ==="
    echo "OS: $(uname -a)"
    echo "cwd: $(pwd)"
    echo
  } | tee -a "$file"

  echo "\$ source scripts/toolchain.sh" | tee -a "$file"
  local tmp
  tmp=$(mktemp)
  source scripts/toolchain.sh >"$tmp" 2>&1
  local tc_rc=$?
  cat "$tmp" | tee -a "$file"
  echo "[RC=$tc_rc]" | tee -a "$file"
  rm -f "$tmp"

  # Independent re-assertion: don't just trust toolchain.sh's own banner text,
  # actually re-check the tools it claims to have pinned resolve as claimed.
  assert_check "$file" "toolchain.sh sourced cleanly (RC=0)" "[ $tc_rc -eq 0 ]" || return 1
  assert_check "$file" "command -v uv kind kubectl act all resolve" \
    "command -v uv >/dev/null 2>&1 && command -v kind >/dev/null 2>&1 && command -v kubectl >/dev/null 2>&1 && command -v act >/dev/null 2>&1" || return 1
  assert_check "$file" "uv --version matches ^uv 0.12." "uv --version | grep -q '^uv 0\\.12\\.'" || return 1
  assert_check "$file" "kind --version matches 0.30.0" "kind --version | grep -q '0\\.30\\.0'" || return 1
  assert_check "$file" "kubectl version --client matches v1.34." "kubectl version --client | grep -q 'v1\\.34\\.'" || return 1

  return 0
}

# `record <file> "<cmd>"`: runs cmd for real (no pipe on the left side --
# never traps exports in a subshell), tees its real stdout+stderr into the
# evidence file in the correct order, and appends the REAL exit code.
record() {
  local file="$1" cmd="$2"
  local tmp
  tmp=$(mktemp)
  eval "$cmd" >"$tmp" 2>&1
  local rc=$?
  { echo "\$ $cmd"; cat "$tmp"; echo "[RC=$rc]"; } | tee -a "$file"
  rm -f "$tmp"
  return "$rc"
}

# `record_stream <file> "<cmd>"`: for LONG-running commands (image pulls,
# `kind create cluster`, rollouts) whose live progress is worth seeing while
# it runs. Streams output directly (via tee, no buffering temp file) and
# captures the real RC via PIPESTATUS -- unlike record(), the command DOES
# run on the left side of a pipe, so any exports/PATH changes it makes are
# lost outside this call. Never use it for `source scripts/toolchain.sh`;
# use record_header for that (see the file's own history of that exact bug).
record_stream() {
  local file="$1" cmd="$2"
  echo "\$ $cmd" | tee -a "$file"
  eval "$cmd" 2>&1 | tee -a "$file"
  local rc=${PIPESTATUS[0]}
  echo "[RC=$rc]" | tee -a "$file"
  return "$rc"
}

record_note() {
  local file="$1" note="$2"
  echo "# $note" | tee -a "$file"
}

# assert_check <file> <description> <test_expr>: computes PASS/FAIL from
# test_expr's real truth value (evaluated AFTER whatever produced the data it
# checks) and records it with a real exit code. Prose notes are for context
# only -- this is the only thing that may state a verdict.
assert_check() {
  local file="$1" desc="$2" test_expr="$3"
  if eval "$test_expr"; then
    echo "ASSERT PASS: $desc" | tee -a "$file"
    echo "[RC=0]" >> "$file"
    return 0
  else
    echo "ASSERT FAIL: $desc" | tee -a "$file"
    echo "[RC=1]" >> "$file"
    return 1
  fi
}

# Prints ONLY the free port number to stdout (so `p=$(port_free_or_pick ...)`
# captures a clean value) -- the log line goes to the FILE only, never to
# stdout, precisely to avoid contaminating that capture. Tries $1, $1+1, ...
port_free_or_pick() {
  local base="$1" file="$2" p
  for offset in $(seq 0 20); do
    p=$((base + offset))
    if netstat -ano | grep -q ":$p "; then
      echo "port $p busy, trying next" >> "$file"
    else
      echo "port check: $p is free (netstat -ano | grep \":$p \" -> no match)" >> "$file"
      echo "$p"
      return 0
    fi
  done
  echo "no free port found near $base" >&2
  return 1
}
