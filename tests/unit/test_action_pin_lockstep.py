"""Unit tests: sub-actions of one action repo are pinned in lockstep.

``github/codeql-action/init``, ``/analyze`` and ``/upload-sarif`` are three
entry points of a **single** repository at a **single** commit. They are not
independent: ``init`` writes a config file stamped with its own version and
``analyze`` refuses to read one written by a different release.

Dependabot does not know that. A "dependency" to it is one ``uses:`` path, so a
release of codeql-action arrives as one PR **per sub-action** — and each of
those PRs is individually unmergeable, because it moves one pin and leaves its
partner behind. Observed here on 2026-08-09, three PRs from one release:

    #495  github/codeql-action/init         4.37.3 -> 4.37.6   RED
    #496  github/codeql-action/analyze      4.37.3 -> 4.37.6   RED
    #497  github/codeql-action/upload-sarif 4.37.3 -> 4.37.6   green

Both red ones failed with the same line, and it names the split exactly::

    Loaded a configuration file for version '4.37.6', but running version '4.37.3'

#497 was green only because ``upload-sarif`` is used alone in scorecard.yml,
with no partner to disagree with — so "one of the three is green" is not
evidence the other two are fine, and merging it first would not have helped.

``.github/dependabot.yml`` now groups these repos so the pins arrive together.
These tests are the other half: grouping stops the *split PR* being raised, and
this file fails the build if a split ever lands anyway — by hand, by a config
edit, or by a Dependabot behaviour change. It reports the family and the
disagreeing pins, which is the diagnosis; the CodeQL error above only appears
at runtime, in a job whose failing step is named "analyze".

``actions/cache`` is the same shape and the reason this is written against the
class rather than against codeql-action: ``actions/cache``, ``/save`` and
``/restore`` are three pins of one repo, in lockstep today only by luck.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GITHUB = ROOT / ".github"
WORKFLOWS = GITHUB / "workflows"
DEPENDABOT = GITHUB / "dependabot.yml"

pytestmark = pytest.mark.skipif(
    not WORKFLOWS.exists(),
    reason=".github/workflows not reachable (e.g. mutation sandbox)")

# `uses: owner/repo[/sub/path]@<40-hex sha>  # vX.Y.Z`. The version comment is
# optional in the pattern but not in practice — test_workflows.py's pin audit
# already requires it, so a missing one shows up there rather than here.
_USES = re.compile(
    r"uses:\s*(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)(?P<sub>/[\w./-]+)?"
    r"@(?P<sha>[0-9a-f]{40})(?:\s*#\s*(?P<version>\S+))?")


class Pin:
    """One pinned ``uses:`` reference."""

    def __init__(self, family: str, sub: str, sha: str, version: str,
                 where: str) -> None:
        self.family = family      # owner/repo — the unit that shares a SHA
        self.sub = sub            # the full uses path, for the failure message
        self.sha = sha
        self.version = version
        self.where = where

    def __repr__(self) -> str:  # pragma: no cover - failure output only
        return "%s@%s (%s) in %s" % (self.sub, self.sha[:8], self.version,
                                     self.where)


def action_pins(text: str, where: str = "<text>") -> list[Pin]:
    """Every pinned action reference in one workflow's text."""
    pins = []
    for m in _USES.finditer(text):
        family = "%s/%s" % (m.group("owner"), m.group("repo"))
        pins.append(Pin(family=family,
                        sub=family + (m.group("sub") or ""),
                        sha=m.group("sha"),
                        version=m.group("version") or "",
                        where=where))
    return pins


def pinned_files() -> list[Path]:
    """Every file GitHub will read a ``uses:`` out of.

    Deliberately wider than the tree needs today, which is the point. Right now
    every pin lives in ``.github/workflows/*.yml``, so globbing exactly that
    would pass — and would keep passing, silently, the day someone writes a
    ``.yaml`` workflow or factors a job into a composite action under
    ``.github/actions/``. A guard that stops looking is worse than no guard,
    because the green tick still appears. ``TestTheGuardCanActuallySee`` is the
    same instinct applied to the regex.
    """
    found = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    actions = GITHUB / "actions"
    if actions.is_dir():
        found += sorted(actions.rglob("action.yml"))
        found += sorted(actions.rglob("action.yaml"))
    return found


def all_pins() -> list[Pin]:
    """Every pinned action reference across every workflow and composite action."""
    pins: list[Pin] = []
    for path in pinned_files():
        rel = path.relative_to(GITHUB).as_posix()
        pins.extend(action_pins(path.read_text(encoding="utf-8"), rel))
    return pins


def split_families(pins: list[Pin]) -> dict[str, list[Pin]]:
    """Families whose pins disagree on SHA or version comment.

    A family referenced through a single ``uses:`` path can never split, so only
    multi-path families are considered — that is what makes this a guard on the
    lockstep property rather than a duplicate of the pin-format audit.
    """
    by_family: dict[str, list[Pin]] = {}
    for pin in pins:
        by_family.setdefault(pin.family, []).append(pin)
    return {
        family: group for family, group in by_family.items()
        if len({p.sub for p in group}) > 1
        and (len({p.sha for p in group}) > 1
             or len({p.version for p in group}) > 1)
    }


def multi_path_families(pins: list[Pin]) -> dict[str, set[str]]:
    """Families referenced through more than one ``uses:`` path."""
    by_family: dict[str, set[str]] = {}
    for pin in pins:
        by_family.setdefault(pin.family, set()).add(pin.sub)
    return {f: subs for f, subs in by_family.items() if len(subs) > 1}


class TestTheGuardCanActuallySee:
    """A regex that stops matching would make every test below vacuously green.

    This is the failure mode worth spending three tests on: the guard's whole
    value is that it fires, and nothing else here would notice if it could not.
    """

    def test_pins_are_found_at_all(self):
        assert len(all_pins()) > 10, "the uses: pattern matched almost nothing"

    def test_every_file_holding_a_pin_is_scanned(self):
        # The other half of "can it see": the regex may be fine while the file
        # list has quietly stopped covering where pins live. Ask the tree
        # directly rather than trusting the glob that produced the list.
        scanned = {p.resolve() for p in pinned_files()}
        missed = sorted(
            path.relative_to(ROOT).as_posix()
            for path in GITHUB.rglob("*")
            if path.is_file() and path.suffix in (".yml", ".yaml")
            and path.resolve() not in scanned
            and _USES.search(path.read_text(encoding="utf-8", errors="ignore")))
        assert not missed, (
            "these files pin an action but no test above ever reads them: %s"
            % ", ".join(missed))

    def test_the_two_known_multi_path_families_are_seen(self):
        families = multi_path_families(all_pins())
        assert "github/codeql-action" in families, families
        assert "actions/cache" in families, families

    def test_a_single_path_family_is_not_treated_as_multi_path(self):
        # actions/checkout is used many times, always at the same path — many
        # references are not the same thing as many sub-actions.
        assert "actions/checkout" not in multi_path_families(all_pins())


class TestSubActionsMoveInLockstep:
    def test_no_family_is_split_across_workflows(self):
        split = split_families(all_pins())
        assert not split, (
            "these action repos are one repo at one commit, but their pins "
            "disagree — CodeQL fails at runtime with \"Loaded a configuration "
            "file for version X, but running version Y\": %s" % split)

    def test_codeql_action_shares_one_sha(self):
        # Named explicitly because this is the family that actually broke, and
        # a generic assertion failing on it reads like a config typo.
        pins = [p for p in all_pins() if p.family == "github/codeql-action"]
        assert len({p.sha for p in pins}) == 1, pins

    def test_actions_cache_shares_one_sha(self):
        pins = [p for p in all_pins() if p.family == "actions/cache"]
        assert len({p.sha for p in pins}) == 1, pins


class TestTheGuardRejectsASplit:
    """Fed the exact content of PR #495, the guard must go red.

    Written against synthetic text rather than the tree so it keeps proving the
    guard fires after the tree is fixed — a test that only passes because the
    repo is currently correct proves nothing about the guard.
    """

    SPLIT = (
        "      - uses: github/codeql-action/init@"
        + "5" * 40 + " # v4.37.6\n"
        "      - uses: github/codeql-action/analyze@"
        + "e" * 40 + " # v4.37.3\n")

    LOCKSTEP = (
        "      - uses: github/codeql-action/init@"
        + "5" * 40 + " # v4.37.6\n"
        "      - uses: github/codeql-action/analyze@"
        + "5" * 40 + " # v4.37.6\n")

    def test_a_split_sha_is_reported(self):
        split = split_families(action_pins(self.SPLIT))
        assert "github/codeql-action" in split, split

    def test_a_lockstep_pair_is_clean(self):
        assert not split_families(action_pins(self.LOCKSTEP))

    def test_a_matching_sha_with_a_stale_version_comment_is_reported(self):
        # The comment is what a human reads and what zizmor's
        # ref-version-mismatch check compares against; a bump that moves the
        # SHA on one line and the comment on both is still a split.
        stale = self.LOCKSTEP.replace("# v4.37.6\n", "# v4.37.3\n", 1)
        assert "github/codeql-action" in split_families(action_pins(stale))

    def test_one_sub_action_alone_cannot_split(self):
        # scorecard.yml's lone upload-sarif is why #497 was green. A family
        # with one path has no partner to disagree with.
        alone = ("      - uses: github/codeql-action/upload-sarif@"
                 + "5" * 40 + " # v4.37.6\n")
        assert not split_families(action_pins(alone))


class TestDependabotGroupsEveryMultiPathFamily:
    """Grouping is the half that stops the broken PR being raised at all.

    Without it the guard above still fires, but only after three unmergeable
    PRs exist and someone has to work out why one of them is green.
    """

    @staticmethod
    def _github_actions_entry() -> str:
        """The ``github-actions`` block of dependabot.yml, own comments included.

        A comment run sits *above* the entry it documents, so the lines before
        the next ``- package-ecosystem:`` belong to that next entry, not to this
        one. Trimming them matters: without it this block ends with the pip
        entry's long rationale, and an assertion about what this entry explains
        would pass on someone else's prose.
        """
        lines = DEPENDABOT.read_text(encoding="utf-8").splitlines()
        starts = [i for i, line in enumerate(lines)
                  if line.startswith("  - package-ecosystem:")]
        for n, start in enumerate(starts):
            end = starts[n + 1] if n + 1 < len(starts) else len(lines)
            while end > start and lines[end - 1].lstrip().startswith("#"):
                end -= 1
            block = "\n".join(lines[start:end])
            if "package-ecosystem: github-actions" in block:
                return block
        raise AssertionError("no github-actions entry in dependabot.yml")

    def test_the_entry_declares_groups(self):
        assert "groups:" in self._github_actions_entry(), \
            "without groups, one codeql-action release arrives as three " \
            "individually-unmergeable PRs"

    @pytest.mark.parametrize("family", sorted(multi_path_families(all_pins())))
    def test_every_multi_path_family_is_grouped(self, family):
        # Parametrised over what the tree actually uses, so adopting a fourth
        # sub-action of some new repo fails here until it is grouped too —
        # rather than silently reintroducing the split PRs a year from now.
        entry = self._github_actions_entry()
        assert "%s*" % family in entry, (
            "%s is pinned through several uses: paths but has no Dependabot "
            "group, so its next release arrives as one PR per sub-action"
            % family)

    def test_the_reason_is_written_down(self):
        # A bare groups: block reads like churn reduction. The next person
        # needs to know it is a correctness constraint.
        entry = self._github_actions_entry()
        assert "lockstep" in entry.lower() or "same commit" in entry.lower(), \
            "the groups block needs a comment saying why it is not optional"
