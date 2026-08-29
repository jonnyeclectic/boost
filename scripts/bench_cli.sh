#!/usr/bin/env bash
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
# Wall-clock benchmark of the real `boost` binary via hyperfine — the actual
# fork+exec CLI, not the in-process pytest-benchmark suite (tests/perf).
# Opt-in (`make bench-cli`); not part of `make check`. Degrades cleanly if
# hyperfine isn't installed.
set -uo pipefail

if ! command -v hyperfine >/dev/null 2>&1; then
  echo "hyperfine not installed — install via 'brew install hyperfine', skipping"
  exit 0
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SB="$(mktemp -d "${TMPDIR:-/tmp}/boost-bench-XXXXXX")"
trap 'rm -rf "$SB"' EXIT
export HOME="$SB" BOOST_NO_AI=1 BOOST_ASSUME_YES=1 NO_COLOR=1

FIX="$(python3 "$ROOT/tests/make_fixture.py" "$SB/fixture-tap")"
"$ROOT/boost" tap "$FIX" >/dev/null
"$ROOT/boost" install brainstorming >/dev/null

echo "== hyperfine: $(command -v hyperfine) over $ROOT/boost (sandbox: $SB)"
hyperfine --warmup 3 \
  "$ROOT/boost --help" \
  "$ROOT/boost list" \
  "$ROOT/boost search brainstorming" \
  "$ROOT/boost count"
