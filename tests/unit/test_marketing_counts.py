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


class TestNoStaleCountsElsewhere:
    @pytest.mark.parametrize("doc", ["README.md", "docs/index.html"])
    def test_no_command_count_is_a_stale_literal(self, doc):
        text = (ROOT / doc).read_text(encoding="utf-8")
        for stale in re.findall(r"all (\d+) commands", text):
            assert int(stale) == _command_count(), \
                "%s says 'all %s commands'" % (doc, stale)


# ---------------------------------------------------------------------------
# The README's hero block.
#
# It is the first thing a new user copies, and this file's docstring applies
# double here: nothing in this repo can prove offline that a skill name
# resolves from the seven starter taps, because `boost_cli/data/registries.json`
# records repos and item *counts*, not item names. So these tests pin the two
# things that are derivable here — the block names exactly one skill, and
# `tests/smoke.sh --online` asks a real tap about that same name — and leave
# the resolution itself to the online check, which taps `--defaults` and
# installs it for real.
#
# What went wrong without them: line 25 read `boost install tdd-workflow`, a
# name defined only in `tests/make_fixture.py`, so the fourth line of the
# four-line get-started block exited 1 with three irrelevant close matches
# while `boost install test-driven-development` exited 0 from the same taps.

SMOKE = (ROOT / "tests" / "smoke.sh").read_text(encoding="utf-8")

# Fixture skill names that are also real skills in the starter taps, so naming
# one on the marketing surface would be fine. Empty on purpose: add a name here
# only once `tests/smoke.sh --online` has been seen to install it.
ONLINE_VERIFIED_FIXTURE_NAMES: set[str] = set()


def _hero_block() -> str:
    m = re.search(r"```bash\n(.*?)```", README, re.S)
    assert m, "README no longer opens with a bash code fence"
    return m.group(1)


def _hero_install_name() -> str:
    names = re.findall(r"^boost install (\S+)", _hero_block(), re.M)
    assert names, "the README's hero block no longer installs anything"
    return names[0]


def _fixture_skill_names() -> set[str]:
    import importlib.util
    path = ROOT / "tests" / "make_fixture.py"
    spec = importlib.util.spec_from_file_location("_boost_make_fixture", path)
    assert spec and spec.loader, "cannot load tests/make_fixture.py"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return set(mod.SKILLS)


class TestHeroBlock:
    def test_it_installs_exactly_one_skill(self):
        names = re.findall(r"^boost install (\S+)", _hero_block(), re.M)
        assert len(names) == 1, \
            "the hero block installs %d skills: %s" % (len(names), names)

    def test_the_install_name_is_the_first_one_in_the_file(self):
        # tests/smoke.sh reads the name with `sed ... | head -1` over the whole
        # README rather than parsing fences. The two extractions have to agree,
        # or the online check verifies a different skill than the one a reader
        # copies out of the hero block.
        first = re.search(r"^boost install (\S+)", README, re.M)
        assert first and first.group(1) == _hero_install_name()

    def test_the_online_smoke_check_verifies_that_name(self):
        # The only real falsification of "installable from the shipped
        # defaults" is `bash tests/smoke.sh --online`, which taps --defaults
        # and installs the name it reads out of README.md. This asserts the
        # link exists; it cannot assert the skill resolves.
        _marker, _, online = SMOKE.partition('"${1:-}" = "--online"')
        assert online, "tests/smoke.sh lost its --online block"
        assert "README.md" in online, \
            "smoke.sh --online no longer reads the hero install name from README"
        assert "tap --defaults" in online, \
            "smoke.sh --online no longer taps the starter registries first"
        assert 'install "$HERO"' in online, \
            "smoke.sh --online no longer installs the name it read from README"

    def test_the_name_is_not_a_test_fixture_identifier(self):
        # The defect's mechanism: `tdd-workflow` exists only in boost's own
        # offline fixture, and it reached the marketing surface because the
        # demo tape was verified against that fixture.
        name = _hero_install_name()
        assert name not in _fixture_skill_names() - ONLINE_VERIFIED_FIXTURE_NAMES, (
            "the README's hero block installs %r, which only "
            "tests/make_fixture.py defines" % name)


class TestHeroBlockPromises:
    """The block may only promise what the block's own install line buys."""

    def test_it_does_not_promise_semantic_search_it_never_installs(self):
        # Measured in a virgin HOME: with the plain `pipx install
        # boost-skill-cli` the block itself prescribes, `boost quickstart`
        # imports 0 shard(s) ("0 because semantic search needs the extra") and
        # `boost search` prints "semantic search is off".
        block = _hero_block()
        installs_extra = "[rag]" in block
        claims = [w for w in ("semantic", "vector", "fused")
                  if w in block.lower()]
        assert installs_extra or not claims, (
            "the hero block installs the stdlib default but its comments "
            "claim %s" % ", ".join(claims))
