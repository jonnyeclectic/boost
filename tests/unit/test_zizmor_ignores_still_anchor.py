"""Unit tests: every zizmor ignore still points at the line it was written for.

``.github/zizmor.yml`` suppresses accepted findings by ``file:LINE``. A line
number is a fragile anchor: insert anything above the construct and the ignore
silently stops applying, or — worse — starts applying to a different construct
that nobody reviewed.

The config's own comment records that this has bitten before. It bit again
here: adding a header comment to ``ci-failure-issue.yml`` moved its ``on:``
block from line 12 to line 28, and CI's ``lint`` job went red on
``dangerous-triggers`` for a trigger that had been reviewed and accepted months
earlier. Nothing local caught it, because ``make lint`` does not run zizmor at
all — that gap is closed in the same change as this file.

Both directions matter and both are asserted:

* an ignore whose line no longer holds a trigger is **dangling** — the finding
  it was silencing is now live, and the next person sees a red gate for a
  decision that was already made;
* an ignore that has drifted onto some *other* construct is worse than
  dangling, because it suppresses a finding nobody ever accepted.

This does not re-run zizmor (that needs the binary, and CI owns it). It checks
the cheap, mechanical property that the anchors still mean what they say.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".github" / "zizmor.yml"
WORKFLOWS = ROOT / ".github" / "workflows"

pytestmark = pytest.mark.skipif(
    not CONFIG.exists(),
    reason=".github/zizmor.yml not reachable (e.g. mutation sandbox)")

#: `dangerous-triggers` is about the `on:` block, so that is what its anchors
#: must land on. Other rules anchor elsewhere and are checked only for
#: existence, not for what they point at.
_TRIGGER_RULE = "dangerous-triggers"


def ignores() -> dict[str, list[tuple[str, int]]]:
    """``{rule: [(workflow file, line), ...]}`` parsed from zizmor.yml."""
    text = CONFIG.read_text(encoding="utf-8")
    out: dict[str, list[tuple[str, int]]] = {}
    rule = None
    for line in text.splitlines():
        m = re.match(r"^  (\S+):\s*$", line)
        if m and m.group(1) not in ("ignore",):
            rule = m.group(1)
            out.setdefault(rule, [])
            continue
        m = re.match(r"^\s*-\s+([\w.-]+\.ya?ml):(\d+)\s*$", line)
        if m and rule:
            out[rule].append((m.group(1), int(m.group(2))))
    return out


def line_of(workflow: str, number: int) -> str:
    """The 1-indexed line ``number`` of a workflow, or '' if out of range."""
    path = WORKFLOWS / workflow
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines[number - 1] if 0 < number <= len(lines) else ""


class TestTheGuardCanActuallySee:
    def test_ignores_are_parsed(self):
        # Every assertion below is vacuous if the parse returns nothing.
        assert ignores(), "parsed no ignores out of .github/zizmor.yml"

    def test_the_trigger_rule_has_entries(self):
        assert ignores().get(_TRIGGER_RULE), ignores()

    def test_a_known_workflow_is_referenced(self):
        files = {f for entries in ignores().values() for f, _ in entries}
        assert files, "no workflow files referenced"
        assert all((WORKFLOWS / f).is_file() for f in files), sorted(files)


class TestEveryAnchorStillPointsAtItsTrigger:
    @pytest.mark.parametrize(
        "workflow,number",
        ignores().get(_TRIGGER_RULE, []),
        ids=lambda v: str(v))
    def test_the_line_is_the_on_block(self, workflow, number):
        text = line_of(workflow, number)
        assert text.startswith("on:"), (
            "%s:%d is ignored for %s, but that line is %r — the anchor has "
            "drifted. Editing anything above a workflow's `on:` block moves "
            "it and either un-silences an accepted finding or silences a "
            "different one nobody reviewed."
            % (workflow, number, _TRIGGER_RULE, text))

    def test_no_ignore_points_past_the_end_of_its_file(self):
        dangling = [(f, n) for entries in ignores().values()
                    for f, n in entries if not line_of(f, n)]
        assert not dangling, dangling


class TestTheConfigIsSelfConsistent:
    def test_every_referenced_workflow_exists(self):
        missing = sorted({f for entries in ignores().values() for f, _ in entries
                          if not (WORKFLOWS / f).is_file()})
        assert not missing, (
            "zizmor.yml silences findings in workflows that no longer exist: "
            "%s" % ", ".join(missing))

    def test_no_duplicate_anchor(self):
        for rule, entries in ignores().items():
            dupes = sorted({e for e in entries if entries.count(e) > 1})
            assert not dupes, (rule, dupes)
