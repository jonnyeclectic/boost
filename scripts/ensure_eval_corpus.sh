#!/usr/bin/env bash
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
# Tap the pinned Tier 1 eval corpus (tests/eval/taps.txt) into $BOOST_HOME so
# scripts/eval_retrieval.py has the repos its golden set grades against. Used by
# CI's lint job and by `make eval`.
#
# Idempotent: a sentinel skips re-tapping so a local `make check` stays fast (and
# offline) after the first run. Set FORCE=1 to re-tap; CI does, because a cached
# corpus must still be re-verified rather than trusted. Honors $PYTHON (defaults
# to python3) so make can pass its venv interpreter.
#
# THE SENTINEL CARRIES THE TAP LIST'S DIGEST, and that is not decoration. An
# empty sentinel said "some corpus has been built here", so editing taps.txt —
# moving a pin, adding a repo — left `make eval` scoring the OLD corpus against
# the NEW file's baseline, silently, for as long as the sentinel survived. That
# is the same class of bug as the unpinned list this whole area exists to fix,
# one directory further along. Keying on the digest makes an edit a cache miss.
#
# THE SENTINEL ALSO HAS TO SEE THE CLONES, for the same reason. It records that
# a corpus was built for this tap list; it cannot record that the corpus is
# still there. Reclaim the 265 MB `repos/` tree by hand and the sentinel and the
# per-tap catalog caches both survive, so this script skips, `rag.build` finds
# every entry and none of their files, and the gate scores a frontmatter index
# under the "BM25 full-content" label — passing all four floors, by a wider
# margin than the real corpus. An empty `repos/` is a cache miss, which turns
# that state into a re-tap instead of a false green.
#
# The tap list carries a commit SHA and an entry count per repo, and the loop
# that reads it lives in scripts/eval_corpus.py rather than here: the format
# needs parsing, the pin needs a fetch-then-checkout, and the count needs
# verifying — none of which a shell loop can be unit-tested on. This file keeps
# what it is good at, the sentinel and the environment. Per-repo presence is
# checked there too (`--ensure` re-pins every row); what belongs here is only
# the cheap "is there a corpus at all" that decides whether to call it.
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
py="${PYTHON:-python3}"
home="${BOOST_HOME:-$HOME/.boost}"
sentinel="$home/.eval-corpus-ready"
taps="$root/tests/eval/taps.txt"

digest=$("$py" -c 'import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$taps")

if [ -z "${FORCE:-}" ] && [ -f "$sentinel" ] && [ "$(cat "$sentinel")" = "$digest" ]; then
  if [ -d "$home/repos" ] && [ -n "$(ls -A "$home/repos" 2>/dev/null)" ]; then
    echo "eval corpus already tapped for this taps.txt — skipping (FORCE=1 to re-tap)"
    exit 0
  fi
  echo "eval corpus sentinel is present but $home/repos is empty — re-tapping" >&2
fi

PYTHONPATH="$root" "$py" "$root/scripts/eval_corpus.py" --ensure

# Only after a clean --ensure: `set -e` means a corpus that could not be
# materialised, or that did not match its pinned counts, never gets a sentinel
# and so is never skipped on the next run.
mkdir -p "$home"
printf '%s\n' "$digest" > "$sentinel"
