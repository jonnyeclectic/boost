# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the hard numbers in README.md and the landing page are true.

These are marketing claims a reader checks against reality in ten seconds, and
they had all three drifted — the README said 72 commands and the landing page
said 78, while `COMMANDS` held 78; the mutation count was ~2,600 against a real
~9,900. A wrong number on the front page costs more credibility than the feature
it was describing earned.

Only counts derivable from the code are asserted. Numbers that come from
somewhere else (how many skills the tapped registries expose, say) are marketing
estimates, not facts this repo can check, and pinning them here would be a test
that lies about what it proves.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from boost_cli.cli import COMMANDS  # noqa: E402  (after the sys.path shim)

README = (ROOT / "README.md").read_text(encoding="utf-8")
INDEX = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")


def _command_count() -> int:
    return len(COMMANDS)


def _group_count() -> int:
    return len({group for _name, group, _module, _summary in COMMANDS})


class TestCommandCount:
    def test_readme_heading_matches_the_registry(self):
        m = re.search(r"##\s+(\d+)\s+commands", README)
        assert m, "README has no '## N commands' heading to check"
        assert int(m.group(1)) == _command_count()

    def test_readme_group_count_matches(self):
        m = re.search(r"##\s+\d+\s+commands,\s+organized into\s+(\d+)\s+groups",
                      README)
        assert m, "README's command heading no longer states a group count"
        assert int(m.group(1)) == _group_count()

    def test_every_readme_command_count_agrees(self):
        # The README states the count in more than one place (the heading and
        # the test-layer table). All of them have to move together — the drift
        # that prompted this test was exactly one of them being left behind.
        counts = {int(n) for n in re.findall(r"(\d+)\s+commands", README)}
        assert counts, "README no longer states a command count anywhere"
        assert counts == {_command_count()}, \
            "README states conflicting command counts: %s" % sorted(counts)

    def test_readme_table_lists_exactly_the_registry(self):
        # The integer above was guarded; the enumeration under it was not, so
        # #594 moved the heading to 81 and the table stayed at 80 (quickstart,
        # the README's own onboarding step, was the one missing). Pin the rows
        # by group title and order, the way docs/index.html's list is pinned.
        from boost_cli.cli import GROUPS
        rows = {group: [c.strip() for c in cmds.split("·")]
                for group, cmds in re.findall(
                    r"^\| ([A-Z][^|]*?) \| (.+?) \|$", README, re.M)
                if "·" in cmds}
        want: dict[str, list[str]] = {}
        for name, group, _module, _summary in COMMANDS:
            want.setdefault(GROUPS[group][1], []).append(name)
        assert rows == want
        assert list(rows) == list(want)       # the groups' order too

    def test_landing_page_counts_agree(self):
        counts = {int(n) for n in re.findall(r"(\d+)\s+commands", INDEX)}
        assert counts == {_command_count()}, \
            "docs/index.html states conflicting command counts: %s" % sorted(counts)

    def test_landing_page_stat_tile_agrees(self):
        m = re.search(r"<b>(\d+)</b><span>Commands", INDEX)
        assert m, "the landing page's Commands stat tile is gone"
        assert int(m.group(1)) == _command_count()

    def test_readme_and_landing_page_agree_with_each_other(self):
        readme = {int(n) for n in re.findall(r"(\d+)\s+commands", README)}
        index = {int(n) for n in re.findall(r"(\d+)\s+commands", INDEX)}
        assert readme == index


# The smoke-check count in the README is deliberately NOT asserted here.
# tests/smoke.sh mixes literal `run` lines, a loop over a heredoc list, and an
# `--online` block that only fires with a flag — so any static formula for "how
# many checks does the default run make?" encodes the file's current shape and
# breaks on an unrelated edit. The number in the README comes from running the
# suite and reading its own summary line, which is the only honest source. A
# test whose formula is a guess is worse than no test.


class TestSuiteSizesAgree:
    """The smoke and BDD sizes the docs state.

    They had drifted three ways at once: README said 176 smoke checks,
    CONTRIBUTING and the OpenSSF badge answer 170, the suite ran 183, and the
    badge's 170 was already wrong on the day it was copied in. Per the note
    above, the smoke count is not derived from smoke.sh's shape; what IS
    checkable without a formula is that the docs agree with each other, so a
    reader never has to guess which file is right. The BDD size is
    declarative (one `Scenario:` per scenario), so it is checked outright.
    """

    DOCS = ("README.md", "CONTRIBUTING.md", "docs/openssf-badge.md")

    def _read(self, doc):
        return (ROOT / doc).read_text(encoding="utf-8")

    def test_every_doc_states_the_same_smoke_size(self):
        sizes = {}
        for doc in self.DOCS:
            for line in self._read(doc).splitlines():
                if "smoke" in line:
                    for n in re.findall(r"(\d+) (?:end-to-end )?checks", line):
                        sizes.setdefault(int(n), []).append(doc)
        # Every statement, not just every doc: the badge answer states it twice.
        assert sorted(d for docs in sizes.values() for d in docs) == sorted(
            ["README.md", "CONTRIBUTING.md"] + ["docs/openssf-badge.md"] * 2)
        assert len(sizes) == 1, "docs disagree on the smoke size: %s" % sizes

    def test_bdd_size_matches_the_feature_files(self):
        features = sorted((ROOT / "tests" / "bdd" / "features").glob("*.feature"))
        texts = [f.read_text(encoding="utf-8") for f in features]
        # An outline expands to one scenario per Examples row, and `Example:`
        # is Gherkin's synonym for `Scenario:`; this count models neither, so
        # refuse rather than undercount.
        assert not any(re.search(r"^\s*(Scenario Outline|Example):", t, re.M)
                       for t in texts)
        scenarios = sum(len(re.findall(r"^\s*Scenario:", t, re.M)) for t in texts)
        stated = [(int(f), int(s)) for doc in self.DOCS for f, s in
                  re.findall(r"(\d+) features, (\d+) scenarios", self._read(doc))]
        assert stated and set(stated) == {(len(features), scenarios)}, stated


class TestNoStaleCountsElsewhere:
    @pytest.mark.parametrize("doc", ["README.md", "docs/index.html"])
    def test_no_command_count_is_a_stale_literal(self, doc):
        text = (ROOT / doc).read_text(encoding="utf-8")
        for stale in re.findall(r"all (\d+) commands", text):
            assert int(stale) == _command_count(), \
                "%s says 'all %s commands'" % (doc, stale)
