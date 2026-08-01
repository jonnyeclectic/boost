#!/usr/bin/env bash
# Tap the pinned Tier 1 eval corpus (tests/eval/taps.txt) into $BOOST_HOME so
# scripts/eval_retrieval.py has the repos its golden set grades against. Used by
# CI's lint job and by `make eval`.
#
# Idempotent: a sentinel skips re-tapping so a local `make check` stays fast (and
# offline) after the first run. CI runs on a fresh $HOME and always taps. Set
# FORCE=1 to re-tap. Honors $PYTHON (defaults to python3) so make can pass its
# venv interpreter.
#
# The tap list carries a commit SHA per repo, and the loop that reads it lives in
# scripts/eval_corpus.py rather than here: the format needs parsing and the pin
# needs a fetch-then-checkout, neither of which a shell loop can be unit-tested
# on. This file keeps what it is good at — the sentinel and the environment.
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
py="${PYTHON:-python3}"
home="${BOOST_HOME:-$HOME/.boost}"
sentinel="$home/.eval-corpus-ready"

if [ -z "${FORCE:-}" ] && [ -f "$sentinel" ]; then
  echo "eval corpus already tapped ($sentinel) — skipping (FORCE=1 to re-tap)"
  exit 0
fi

PYTHONPATH="$root" "$py" "$root/scripts/eval_corpus.py" --ensure

mkdir -p "$home"
: > "$sentinel"
