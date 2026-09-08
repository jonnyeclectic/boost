# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Pure logic behind `boost index`, kept out of the command layer so it's
covered by the unit suite and targeted by the mutation gate.

Two failure modes an audit found in `commands/discovery.cmd_index`:
zero GitHub results silently wiping a working ``discovery.json``, and a
`gh` rate-limit failure surfacing as raw multi-line stderr instead of a
boost-native hint.
"""
from __future__ import annotations

_RATE_LIMIT_MARKERS = ("rate limit", "gh auth login")
_RATE_LIMIT_HINT = ("GitHub rate limit hit — wait a minute or authenticate: "
                     "`gh auth login` / GH_TOKEN")


def gh_failure_hint(raw: str) -> str:
    """A one-line, boost-native hint for a failed ``gh api`` call.

    `gh` reports rate limiting and auth failures as multi-line prose plus a
    JSON blob — passed straight through as a :class:`BoostError` hint it
    reads as noise with no boost-native next step. Detected here by the
    markers `gh` itself uses (a rate-limit message, an HTTP 403, or its own
    ``gh auth login`` suggestion) and replaced with one line naming the fix.
    Anything else falls back to the tool's own last few lines, which is at
    least specific to what broke.
    """
    lowered = raw.lower()
    if any(marker in lowered for marker in _RATE_LIMIT_MARKERS) or "403" in raw:
        return _RATE_LIMIT_HINT
    tail = "\n".join(raw.strip().splitlines()[-3:])
    return tail or "check `gh auth status`"


def should_write_index(item_count: int, index_exists: bool) -> bool:
    """Whether a `boost index` run should write its ``discovery.json``.

    A zero-result run (an over-narrow query, a `gh` hiccup that still
    returns 200 with an empty page) still exits 0, so nothing else signals
    the loss if it overwrites a working index with an empty one. Write only
    when there's something to write, or when nothing was there before —
    a first run still leaves a valid (if empty) file behind rather than
    none at all.
    """
    return item_count > 0 or not index_exists
