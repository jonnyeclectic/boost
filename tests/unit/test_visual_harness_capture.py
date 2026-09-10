# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the screenshot is an artifact, and the exit code is the gate.

`tests/visual/visual_check.mjs` asserts render invariants over 10 pages x 5
widths and exits non-zero when one breaks. Its own header states the division:
"Screenshots land in tests/visual/out/ for eyeballing; the exit code is the
gate." The harness then took the screenshot *before* emitting the verdict, and
took it unguarded, so the artifact could decide the gate's fate.

It did. `docs/roadmap.html` is generated from `docs/roadmap/items/*.md` and
grows a card at a time; at 291 cards the full-page capture at 1280px asked for
more than Chrome will composite:

    ProtocolError: Protocol error (Page.captureScreenshot): Page is too large.
        at async .../tests/visual/visual_check.mjs:182:5

That is an unhandled rejection out of the await, so node died on the spot.

**The red X was the cheap half.** The verdict for `docs/roadmap.html @1280` had
already been computed on the line above and was discarded unprinted, and the
six combinations queued behind it -- roadmap @1680, and `design-roadmap.html`
at all five widths -- never ran at all. So the sweep reported failure while it
had quietly stopped checking a page and a half, and what it reported was a
screenshot error, which tells a reader nothing about the coverage it lost.

The board crossed the ceiling on 2026-09-09: `visual` was green on `main` at
`a37f7be5` (01:13Z) and red at `52b5adcd` (18:25Z), the merge of #836, which
added 41 cards. Every run on `main` and every branch failed from there.

**The sibling harness in this directory already had the answer.**
`console_check.mjs` wraps its own per-page navigation and records the failure
as a finding instead of throwing, reasoning that "a third party going down must
never redden a deploy check". Same rule, pointed the other way: an artifact
boost cannot capture must never end the sweep.

These tests are the ratchet, in the shape `test_visual_harness_flags.py`
established for this directory. The bug there was that one file was fixed and
the other was not, and the only thing recording it was a comment. A comment
cannot fail a build.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HARNESS = ROOT / "tests" / "visual" / "visual_check.mjs"


def _code() -> str:
    """`visual_check.mjs` with its `//` prose blanked, offsets preserved.

    One assertion here is about ORDER, so comments are blanked in place rather
    than dropped -- an index into this string still points at the same code.
    `://` is deliberately left alone: the harness builds `file://` page URLs,
    and a naive split on `//` would truncate the line that does it.
    """
    assert HARNESS.is_file(), "%s is missing" % HARNESS
    out = []
    for line in HARNESS.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("//"):
            out.append("")
            continue
        m = re.search(r"(?<![:'\"])//", line)
        out.append(line[: m.start()] if m else line)
    return "\n".join(out)


def _captures(code: str) -> list[int]:
    """Offsets of every `.screenshot(` call in the harness."""
    return [m.start() for m in re.finditer(r"\.screenshot\s*\(", code)]


def _catch_body(code: str, after: int) -> str:
    """The `{...}` body of the first `catch` at or after `after`."""
    m = re.search(r"\bcatch\s*\([^)]*\)\s*\{", code[after:])
    assert m, "no catch block follows the capture at offset %d" % after
    start = after + m.end()
    depth, i = 1, start
    while i < len(code) and depth:
        depth += {"{": 1, "}": -1}.get(code[i], 0)
        i += 1
    return code[start : i - 1]


class TestTheCaptureCannotEndTheSweep:
    def test_every_capture_is_guarded(self):
        """A bare `await page.screenshot(...)` is what killed the run.

        Brace-depth rather than a JS parser: what distinguishes a guarded call
        from a bare one is that more `try {` than `catch (` have opened above
        it, and that is exactly what an unhandled rejection turns on.
        """
        code = _code()
        shots = _captures(code)
        assert shots, "no `.screenshot(` call found -- did the sweep stop capturing?"
        for pos in shots:
            before = code[:pos]
            opened = len(re.findall(r"\btry\s*\{", before))
            closed = len(re.findall(r"\bcatch\s*\(", before))
            assert opened > closed, (
                "visual_check.mjs takes a screenshot outside any try (line %d) "
                "-- Chrome refusing one page's capture then ends the whole "
                "sweep, and every page/width queued behind it goes unchecked"
                % (before.count("\n") + 1))

    def test_the_verdict_is_emitted_before_the_capture(self):
        """Ordering is the coverage invariant, stated once.

        Even guarded, a capture that runs first can be interrupted -- a timeout,
        a killed job -- between computing a verdict and printing it. The
        assertions are already complete by then; nothing may sit between them
        and the line that reports them.
        """
        code = _code()
        verdict = code.find("failures++")
        assert verdict != -1, "no `failures++` in the harness -- how does it fail?"
        first = _captures(code)[0]
        assert verdict < first, (
            "visual_check.mjs captures before it reports: the verdict for the "
            "page being captured is computed and then discarded if the capture "
            "throws. Report first, capture last.")


class TestACaptureFailureIsNotAVisualFailure:
    def test_the_reason_is_logged_rather_than_swallowed(self):
        """A silent catch trades a red build for a lying green one."""
        body = _catch_body(code := _code(), _captures(code)[0])
        assert "console." in body, (
            "the capture's catch block says nothing -- a page too tall to "
            "screenshot would then look identical to one captured fine")

    def test_a_refused_capture_does_not_count_as_a_regression(self):
        """`failures` means a render invariant broke, not that a PNG is missing."""
        body = _catch_body(code := _code(), _captures(code)[0])
        assert "failures++" not in body, (
            "a refused screenshot increments `failures` -- that reddens the "
            "gate for a missing artifact, which is the confusion this whole "
            "module exists to undo")
