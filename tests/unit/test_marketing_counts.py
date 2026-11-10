# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the hard numbers in README.md and the landing page are true.

These are marketing claims a reader checks against reality in ten seconds, and
they had all three drifted — the README said 72 commands and the landing page
said 78, while `COMMANDS` held 78; the mutation count was ~2,600 against a real
~9,900. A wrong number on the front page costs more credibility than the feature
it was describing earned.

Only counts derivable from the code are asserted. Numbers that come from
somewhere else (how many skills a user's own taps expose, say) are marketing
estimates, not facts this repo can check, and pinning them here would be a test
that lies about what it proves. The catalogue's item count is the exception:
boost_cli/data/registries.json records it as `est_items_scannable`, so a doc
that states one is held to that figure.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from boost_cli.cli import COMMANDS  # noqa: E402  (after the sys.path shim)

README = (ROOT / "README.md").read_text(encoding="utf-8")
INDEX = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
LANGCHAIN_README = (ROOT / "boost_langchain" / "README.md").read_text(
    encoding="utf-8")


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


class TestCatalogueSizeIsNotHardCoded:
    def test_no_doc_states_a_catalogue_size_the_data_disagrees_with(self):
        # `scripts/build_registries.py` moves this number; prose that states
        # it went stale at 463 while registries.json held 464. Say "every
        # catalogued registry" instead, or state the current figure.
        data = json.loads((ROOT / "boost_cli" / "data" / "registries.json")
                          .read_text(encoding="utf-8"))
        size = sum(1 for r in data["registries"] if not r.get("list_only"))
        docs = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
        for doc in docs:
            text = doc.read_text(encoding="utf-8")
            # `\s+`: README broke this very phrase across a line. The second
            # form is "the N-registry catalogue"; a "~N" is an estimate.
            for n in re.findall(r"all\s+(\d+)\s+catalogued\s+registr"
                                r"|(?<![~\d])(\d+)-registry\s+catalogue", text):
                n = next(g for g in n if g)
                assert int(n) == size, "%s says all %s; the catalogue is %d" % (
                    doc.name, n, size)

    def test_the_docs_site_states_the_catalogue_size_the_data_has(self):
        # The landing page said "spans 100+ registries" and the carousel
        # "100+ classified registries" while `boost tap --catalog --dry-run`
        # offered 515; the test above read only Markdown, so neither was
        # checked. Same size as above: list-only rows link out and are never
        # tapped.
        data = json.loads((ROOT / "boost_cli" / "data" / "registries.json")
                          .read_text(encoding="utf-8"))
        size = sum(1 for r in data["registries"] if not r.get("list_only"))
        stated = []
        for doc in [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.html"))]:
            text = doc.read_text(encoding="utf-8")
            stated += [(doc.name, int(n)) for n in re.findall(
                r"spans\s+(\d+)\+?\s+registr"
                r"|(\d+)\+?\s+classified\s+(?:GitHub\s+)?registr", text)
                for n in n if n]
        assert ("index.html", size) in stated, stated
        assert ("README.md", size) in stated, stated
        assert [s for s in stated if s[1] != size] == [], (
            "the catalogue is %d registries: %s" % (size, stated))

    def test_the_readme_item_estimate_is_near_the_data(self):
        # "roughly 30,000 items" stood while the catalogue summed to 35,466.
        # It is an estimate, so it gets 10%; a figure outside that is stale.
        data = json.loads((ROOT / "boost_cli" / "data" / "registries.json")
                          .read_text(encoding="utf-8"))
        m = re.search(r"roughly\s+([\d,]+)\s+items", README)
        assert m, "README no longer estimates the catalogue's item count"
        said = int(m.group(1).replace(",", ""))
        assert abs(said - data["est_items_scannable"]) <= 0.1 * data["est_items_scannable"]

    def test_the_docs_site_item_counts_sit_at_or_under_the_data(self):
        # The landing page's tile said "70,000+ Discoverable assets" and
        # langchain.html "70,000+ retrievable procedures", against an
        # est_items_scannable of 35,466. "N+" claims a floor, so N may not
        # exceed the data; and like the README's estimate it may sit no more
        # than 10% under it, or it has gone stale the other way.
        data = json.loads((ROOT / "boost_cli" / "data" / "registries.json")
                          .read_text(encoding="utf-8"))
        size = data["est_items_scannable"]
        stated = []
        for doc in [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.html"))]:
            text = doc.read_text(encoding="utf-8")
            stated += [(doc.name, int(n.replace(",", ""))) for n in re.findall(
                r"(\d{1,3}(?:,\d{3})+)\+\s*(?:</b><span>)?\s*(?:[A-Za-z]+\s+)?"
                r"(?:items|procedures|assets)\b", text)]
        assert {"index.html", "langchain.html"} <= {d for d, _ in stated}, stated
        assert [s for s in stated if not 0.9 * size <= s[1] <= size] == [], (
            "the catalogue's est_items_scannable is %d: %s" % (size, stated))


class TestPlatformClaimsAgree:
    """SUPPORT.md says which operating systems are supported; the README badge
    and the PyPI classifiers said macOS and Linux while SUPPORT.md listed
    Windows too and `tests (windows-latest, 3.12)` is a required check."""

    def _support(self) -> set[str]:
        text = (ROOT / "SUPPORT.md").read_text(encoding="utf-8")
        m = re.search(r"^\| Operating system \| ([^|]+) \|$", text, re.M)
        assert m, "SUPPORT.md no longer lists supported operating systems"
        return {o.strip().lower() for o in m.group(1).split(",")}

    def test_readme_badge_lists_the_supported_systems(self):
        m = re.search(r"badge/platform-([^-)]+)-", README)
        assert m, "README lost its platform badge"
        badge = {o.strip().lower() for o in
                 m.group(1).replace("%20", " ").split("%7C")}
        assert badge == self._support()

    def test_classifiers_list_the_supported_systems(self):
        import tomllib
        meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        names = {"MacOS": "macos", "POSIX :: Linux": "linux",
                 "Microsoft :: Windows": "windows"}
        got = {names[c.removeprefix("Operating System :: ")]
               for c in meta["project"]["classifiers"]
               if c.startswith("Operating System :: ")}
        assert got == self._support()


class TestPythonClaimsAgree:
    """SUPPORT.md, the README badge and the classifiers name the Pythons CI gates.

    SUPPORT.md said 3.12-3.14 while the badge and the classifiers said
    3.12-3.15, and ci.yml runs its 3.15 cell under `continue-on-error`,
    outside .github/required-checks.txt: a 3.15 regression blocks neither a
    merge nor a release. The gated set is read from ci.yml's `tests` job, so a
    cell that becomes advisory, or stops being, moves all three docs.
    """

    @staticmethod
    def _gated_in(job: dict) -> set[str]:
        pythons = set(job["strategy"]["matrix"]["python"])
        advisory = job.get("continue-on-error", False)
        if advisory is True:
            return set()
        return pythons - set(re.findall(r"matrix\.python == '([\d.]+)'",
                                        str(advisory)))

    def _gated(self) -> set[str]:
        # importorskip, like test_ci_tests_extended.py: the free-threaded
        # canary leg installs no PyYAML (tests/unit/test_canary_deps.py).
        yaml = pytest.importorskip("yaml")
        ci = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml")
                            .read_text(encoding="utf-8"))
        return self._gated_in(ci["jobs"]["tests"])

    @pytest.mark.parametrize("advisory, gated", [
        ("${{ matrix.python == '3.15' }}", {"3.12"}),
        (True, set()),
        (None, {"3.12", "3.15"}),
    ])
    def test_an_advisory_cell_is_not_gated(self, advisory, gated):
        # The reader, on ci.yml's own spelling: a continue-on-error cell
        # holds nothing back, so no doc may call it supported.
        job: dict = {"strategy": {"matrix": {"python": ["3.12", "3.15"]}}}
        if advisory is not None:
            job["continue-on-error"] = advisory
        assert self._gated_in(job) == gated

    def test_support_md_lists_the_gated_pythons(self):
        text = (ROOT / "SUPPORT.md").read_text(encoding="utf-8")
        m = re.search(r"^\| Python \| ([^|]+) \|$", text, re.M)
        assert m, "SUPPORT.md no longer lists supported Pythons"
        assert {v.strip() for v in m.group(1).split(",")} == self._gated()

    def test_classifiers_list_the_gated_pythons(self):
        import tomllib
        meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        got = {c.removeprefix("Programming Language :: Python :: ")
               for c in meta["project"]["classifiers"]
               if re.fullmatch(r"Programming Language :: Python :: 3\.\d+", c)}
        assert got == self._gated()

    def test_readme_badge_spans_the_gated_pythons(self):
        m = re.search(r"\[!\[Python (3\.\d+)–(3\.\d+)\]\(https://img\.shields\.io"
                      r"/badge/python-(3\.\d+)%E2%80%93(3\.\d+)-", README)
        assert m, "README lost its Python badge"
        assert m.group(1, 2) == m.group(3, 4), "badge text and image disagree"
        lo, hi = (int(v.split(".")[1]) for v in m.group(1, 2))
        # A range claims every version inside it.
        assert {"3.%d" % n for n in range(lo, hi + 1)} == self._gated()

    def test_the_gated_floor_is_requires_python(self):
        import tomllib
        meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        floor = meta["project"]["requires-python"].removeprefix(">=")
        assert floor == min(self._gated(), key=lambda v: int(v.split(".")[1]))


class TestLandingPageStatTiles:
    """The hero tiles are counts the code already holds."""

    def _tile(self, label: str) -> int:
        m = re.search(r"<b>(\d+)</b><span>%s" % label, INDEX)
        assert m, "the landing page's %r stat tile is gone" % label
        return int(m.group(1))

    def test_agents_tile_counts_every_agent_boost_targets(self):
        # It said 5 under a lede naming six.
        from boost_cli.core import agents
        assert self._tile("AI agents supported") == len(agents.DISPLAY)

    def test_items_tile_is_still_there_to_be_checked(self):
        # Its number is held to registries.json by
        # TestCatalogueSizeIsNotHardCoded; this keeps the tile in that sweep.
        assert re.search(r"<b>\d{1,3}(?:,\d{3})+\+</b><span>Catalogued items<",
                         INDEX), "the landing page's items tile is gone"

    def test_starter_registries_tile_counts_the_default_taps(self):
        from boost_cli.core import config
        assert self._tile("Starter registries") == len(config.DEFAULT_TAPS)

    def test_nothing_claims_boost_ships_pre_tapped(self):
        # A fresh install has no taps: `boost doctor` on an empty HOME says
        # "no registries tapped". `boost quickstart` is what taps them.
        assert "pre-tapped" not in INDEX.lower()

    def test_the_landing_page_shows_how_to_wire_agents(self):
        # README showed `boost mcp register`; the landing page never did.
        assert INDEX.count("mcp</span> register") >= 2
        assert "<code>boost mcp register</code>" in INDEX


#: The README is also the PyPI long description, and pypi.org resolves a
#: relative target against /project/boost-skill-cli/ — where it serves the
#: project page as text/html, so the demo GIF rendered as a broken image and
#: every relative link led back to the page the reader was already on.
_REPO_FILE = re.compile(
    r"^https://(?:github\.com/jonnyeclectic/boost/(?:blob|tree)/main"
    r"|raw\.githubusercontent\.com/jonnyeclectic/boost/main)/([^#?]+)")


def _readme_targets() -> list[str]:
    return (re.findall(r"\]\(([^)\s]+)\)", README)
            + re.findall(r"""(?:src|href)=["']([^"']+)["']""", README))


class TestReadmeRendersOffGitHub:
    def test_every_link_and_image_is_absolute(self):
        relative = [t for t in _readme_targets()
                    if not re.match(r"(?:https?:|#|mailto:)", t)]
        assert relative == [], (
            "README.md is the PyPI page too, where these resolve to nothing: "
            "%s" % relative)

    def test_every_absolute_link_into_this_repo_names_a_real_path(self):
        # Absolute URLs give up the local-path check a relative link got for
        # free, so a renamed file would 404 only after it reached main.
        targets = [m.group(1) for t in _readme_targets()
                   if (m := _REPO_FILE.match(t))]
        assert targets, "README.md no longer links into this repository"
        missing = [t for t in targets if not (ROOT / t).exists()]
        assert missing == [], "README.md links paths that do not exist: %s" % missing


#: The two roadmap boards are logs: a card records what was true the day it
#: was written ("a narrow-pane audit across all 80 commands"), so the
#: generated card regions are history rather than claims. The boards' own
#: chrome around them is not, and stays in the sweep.
_CARD_REGION = re.compile(r"<!-- ROADMAP:cards\b.*?<!-- /ROADMAP:cards -->", re.S)

_WORDS = {w: n for n, w in enumerate(
    ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
     "nine", "ten", "eleven", "twelve"])}


def _docs_site() -> list[tuple[str, str]]:
    """Every docs page and architecture note, whitespace collapsed."""
    docs = [*sorted((ROOT / "docs").glob("*.html")),
            *sorted((ROOT / "docs" / "architecture").glob("*.md"))]
    return [(doc.relative_to(ROOT).as_posix(),
             re.sub(r"\s+", " ", _CARD_REGION.sub(
                 "", doc.read_text(encoding="utf-8"))))
            for doc in docs]


def _number(token: str) -> int:
    return int(token) if token.isdigit() else _WORDS[token.lower()]


def _mcp_tools() -> list[str]:
    from boost_cli.commands import configuration
    return configuration.REGISTRY.names()


class TestDocsSiteCounts:
    """Every count of commands and MCP tools on the docs site is the code's.

    The checks above read README.md and docs/index.html only, and the pages
    beside them drifted unseen: carousel.html said 78 commands in its heading
    and lede and 76 in its stat tile while COMMANDS held 81 (and its own
    per-group lines summed to 81), docs/architecture/c4-containers.md said
    78, and mcp-hub.html's tile said 6 MCP tools against the 7 a live
    `tools/list` returns.
    """

    def test_every_command_total_is_the_registry(self):
        stated = []
        for name, text in _docs_site():
            # "13 commands in this group" is a per-group count, checked below.
            stated += [(name, int(n)) for n in re.findall(
                r"(\d+)\s+commands\b(?! in this group)", text, re.I)]
            # The stat-tile form: a number and its label in separate tags is
            # how the carousel's 76 got past a `\d+ commands` scan.
            stated += [(name, int(n)) for n in re.findall(
                r"<b>(\d+)</b>\s*<span>Commands\b", text)]
        assert {"docs/carousel.html", "docs/index.html",
                "docs/architecture/c4-containers.md"} <= {d for d, _ in stated}, stated
        assert [s for s in stated if s[1] != _command_count()] == [], (
            "COMMANDS holds %d: %s" % (_command_count(), stated))

    def test_every_group_count_is_the_registry(self):
        stated = [(name, int(n)) for name, text in _docs_site()
                  for n in re.findall(r"(\d+)\s+(?:command\s+)?groups\b", text)]
        assert stated, "no docs page states how many command groups there are"
        assert [s for s in stated if s[1] != _group_count()] == [], (
            "COMMANDS spans %d groups: %s" % (_group_count(), stated))

    def test_the_carousel_group_notes_are_the_registry_in_order(self):
        from collections import Counter

        from boost_cli.cli import GROUPS
        text = dict(_docs_site())["docs/carousel.html"]
        sizes = Counter(group for _name, group, _module, _summary in COMMANDS)
        assert [int(n) for n in re.findall(
            r"(\d+) commands in this group", text)] == [sizes[g] for g in GROUPS]

    def test_every_mcp_tool_count_is_the_registry(self):
        n = len(_mcp_tools())
        number = r"(\d+|%s)" % "|".join(_WORDS)
        stated = []
        for name, text in [*_docs_site(), ("README.md", README)]:
            stated += [(name, _number(t)) for t in re.findall(
                number + r"\s*(?:</b>\s*<span>)?\s*MCP\s+tools\b", text, re.I)]
            stated += [(name, _number(t)) for t in re.findall(
                number + r"\s+tools\s+are\s+exposed\b", text, re.I)]
        assert {"docs/mcp-hub.html", "README.md"} <= {d for d, _ in stated}, stated
        assert [s for s in stated if s[1] != n] == [], (
            "the MCP registry holds %d tools: %s" % (n, stated))

    def test_the_readme_names_every_mcp_tool(self):
        m = re.search(r"tools are exposed: (.+?)\.\s", README, re.S)
        assert m, "README no longer lists the MCP tools it exposes"
        assert re.findall(r"`(boost_\w+)`", m.group(1)) == _mcp_tools()


def _agent_sets() -> tuple[set[str], set[str], set[str]]:
    """(every agent, the ones boost symlinks into, the ones reading the store)."""
    from boost_cli.core import agents
    every = set(agents.DISPLAY.values())
    linking = {agents.DISPLAY[a] for a in agents.DISPLAY
               if agents.flag_default(a, "links_skills")}
    return every, linking, every - linking


def _agent_homes() -> tuple[set[str], set[str]]:
    """(the dirs boost symlinks into, the store-reading agents' dirs), `~/…`.

    Each is the parent of the agent's default skills dir, so
    `~/.gemini/antigravity-cli/skills` is `~/.gemini/antigravity-cli`. Codex's
    `${CODEX_HOME:-~/.codex}/skills` is read at its default, `~/.codex`.
    """
    from boost_cli.core import agents, config
    rows: dict[str, dict] = config.DEFAULTS["agents"]  # type: ignore[assignment]

    def home(agent: str) -> str:
        raw = re.sub(r"\$\{\w+:-([^}]*)\}", r"\1", rows[agent]["dir"])
        return PurePosixPath(raw).parent.as_posix()

    linking = {home(a) for a in agents.DISPLAY
               if agents.flag_default(a, "links_skills")}
    return linking, {home(a) for a in agents.DISPLAY} - linking


def _agent_runs(text: str) -> list[list[str]]:
    """Each run of agent names joined by commas, `·` or "and", tags removed."""
    from boost_cli.core import agents
    names = sorted(agents.DISPLAY.values(), key=len, reverse=True)
    one = r"(?:%s)(?: CLI)?" % "|".join(map(re.escape, names))
    sep = r"(?:\s*,\s*(?:and\s+|or\s+)?|\s+and\s+|\s+or\s+|\s*·\s*)"
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text))
    canon = {n.removesuffix(" CLI"): n for n in names}
    return [[canon[n.removesuffix(" CLI")] for n in re.findall(one, m.group(0))]
            for m in re.finditer(r"(?<![\w-])%s(?:%s%s)+" % (one, sep, one), text)]


class TestAgentListsAgree:
    """Docs that list the agents boost installs into list all of them.

    boost targets six agents: it symlinks skills into four (Claude Code,
    Windsurf, Cursor, Antigravity CLI), and two (Gemini CLI, Codex) read
    the canonical store directly. Both C4 diagrams listed Claude Code,
    Cursor, Windsurf and Gemini CLI; c4-containers.md said "Three linking
    agents" and that only Gemini CLI reads the store; adapters.html and
    langchain.html named the same four, and carousel.html three.
    """

    def test_an_install_target_list_is_every_agent_or_the_linking_ones(self):
        # A list naming Cursor and Windsurf is a list of install targets:
        # neither is an MCP or hooks host, which is what the shorter
        # "Claude Code, Gemini CLI, …" lists elsewhere describe. Order is not
        # part of the test: requiring the list to open with Claude Code let
        # the stale four through as "Cursor, Windsurf, Claude Code or Gemini
        # CLI".
        every, linking, _native = _agent_sets()
        # boost_langchain/README.md carries the same "skills in your editor"
        # sentence as docs/langchain.html, and kept the stale four after the
        # page was fixed.
        surfaces = [*_docs_site(), ("README.md", README),
                    ("boost_langchain/README.md", LANGCHAIN_README)]
        lists = [(name, run) for name, text in surfaces
                 for run in _agent_runs(text)
                 if {"Claude Code", "Cursor", "Windsurf"} <= set(run)]
        assert {"README.md", "docs/index.html", "boost_langchain/README.md"} <= {
            d for d, _ in lists}, lists
        wrong = [(d, run) for d, run in lists if set(run) not in (every, linking)]
        assert wrong == [], (
            "boost targets %s and links into %s: %s"
            % (sorted(every), sorted(linking), wrong))

    def test_the_c4_diagrams_name_every_agent(self):
        every, _linking, _native = _agent_sets()
        for doc in ("c4-context.md", "c4-containers.md"):
            text = (ROOT / "docs" / "architecture" / doc).read_text(encoding="utf-8")
            m = re.search(r'System_Ext\(agents, "[^"]*", "([^"]*)"\)', text)
            assert m, "%s lost its agents box" % doc
            assert {a for run in _agent_runs(m.group(1)) for a in run} == every, (
                doc, m.group(1))

    def test_the_container_diagram_splits_them_as_the_code_does(self):
        _every, linking, native = _agent_sets()
        text = (ROOT / "docs" / "architecture" / "c4-containers.md").read_text(
            encoding="utf-8")
        said = re.findall(r"\b(\w+) linking agents\b", text, re.I)
        assert said and {_number(n) for n in said} == {len(linking)}, said
        m = re.search(r'Rel\(agents, store, "Reads directly", "([^"]*)"\)', text)
        assert m, "the container diagram no longer says who reads the store"
        assert {a for run in _agent_runs(m.group(1)) for a in run} == native, \
            m.group(1)

    @pytest.mark.parametrize("doc", ["c4-containers.md", "c4-dynamic-install.md"])
    def test_the_link_box_is_every_linking_agents_dir(self, doc):
        # The agent names above are checked, but the directories beside them
        # were not: either diagram could drop ~/.gemini/antigravity-cli from
        # its symlink box and every name test still passed.
        linking, _native = _agent_homes()
        text = (ROOT / "docs" / "architecture" / doc).read_text(encoding="utf-8")
        m = re.search(r'ContainerDb\(links, "([^"]*)"', text)
        assert m, "%s lost its symlink box" % doc
        assert {d.strip() for d in m.group(1).split(",")} == linking, m.group(1)

    def test_the_native_box_is_every_store_reading_agents_dir(self):
        _linking, native = _agent_homes()
        text = (ROOT / "docs" / "architecture" / "c4-containers.md").read_text(
            encoding="utf-8")
        m = re.search(r'ContainerDb\(native, "([^"]*)"', text)
        assert m, "the container diagram lost its native-store agents' box"
        assert {d.strip() for d in m.group(1).split(",")} == native, m.group(1)

    def test_the_security_model_names_every_agent_dir_boost_writes(self):
        # The threat model's step 3 is "the consequential one", and its list
        # of the directories boost writes into stopped at ~/.gemini/: it left
        # out ~/.codex/, where a rule is written into Codex's AGENTS.md.
        linking, native = _agent_homes()
        dotdirs = {"/".join(PurePosixPath(d).parts[:2]) for d in linking | native}
        text = (ROOT / "docs" / "security-design.md").read_text(encoding="utf-8")
        m = re.search(r"each agent's directory \(([^)]*)\)", text)
        assert m, "docs/security-design.md no longer lists the agent dirs"
        assert set(re.findall(r"`(~/\.[\w-]+)/?`", m.group(1))) == dotdirs, (
            m.group(1))


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


#: The hero fence is identified by what it DOES, not by where it sits. "the
#: first bash fence" and smoke.sh's "the first `boost install` in the file" are
#: two spellings of the same guess, so a decoy fence added above the hero moved
#: both at once and the pin between them stayed green while the online check
#: verified a skill nobody is told to install. Anchoring on the install command
#: the block prescribes is the one property that cannot drift.
HERO_ANCHOR = "pipx install --python 3.13 --fetch-python=always"


def _hero_block() -> str:
    for body in re.findall(r"```bash\n(.*?)```", README, re.S):
        if HERO_ANCHOR in body:
            return body
    raise AssertionError(
        "no bash fence in README.md runs %r — the hero block is gone, or it "
        "no longer prescribes the install it is meant to demonstrate"
        % HERO_ANCHOR)


def _smoke_hero_pipeline() -> str:
    """The shell smoke.sh actually runs to pick the name, lifted verbatim.

    Lifted rather than re-implemented: a Python copy of the extraction would
    agree with itself forever, which is exactly the tautology this pin
    replaced.
    """
    m = re.search(r'^\s*HERO="\$\((.*)\)"\s*$', SMOKE, re.M)
    assert m, "tests/smoke.sh no longer extracts a hero name"
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

    @pytest.mark.skipif(sys.platform == "win32",
                        reason="runs smoke.sh's own bash/awk line; smoke.sh is POSIX")
    def test_smoke_extracts_the_same_name_this_test_does(self):
        """Run smoke.sh's own extraction and compare, rather than re-spelling it.

        The previous version of this test compared "the first `boost install`
        in the file" against "the first `boost install` in the first bash
        fence" — two spellings of the same guess, so a decoy fence above the
        hero satisfied both while pointing the online check at a skill nobody
        is told to install. Executing the shell pipeline is the only
        comparison that catches drift in either direction.
        """
        pipeline = _smoke_hero_pipeline()
        got = subprocess.run(["bash", "-c", pipeline], cwd=ROOT,
                             capture_output=True, text=True, check=True)
        assert got.stdout.strip() == _hero_install_name(), (
            "smoke.sh reads %r, the hero fence installs %r"
            % (got.stdout.strip(), _hero_install_name()))

    @pytest.mark.skipif(sys.platform == "win32",
                        reason="runs smoke.sh's own bash/awk line; smoke.sh is POSIX")
    def test_a_decoy_install_line_cannot_steal_the_check(self, tmp_path):
        """The regression this pin exists for, executed rather than asserted."""
        decoy = README.replace(
            "```bash\n" + HERO_ANCHOR,
            "```bash\nboost install code-review\n```\n\n```bash\n" + HERO_ANCHOR, 1)
        assert decoy != README
        readme = tmp_path / "README.md"
        readme.write_text(decoy, encoding="utf-8")
        got = subprocess.run(["bash", "-c", _smoke_hero_pipeline()], cwd=tmp_path,
                             capture_output=True, text=True, check=True)
        assert got.stdout.strip() != "code-review", (
            "smoke.sh followed a decoy `boost install` line instead of the "
            "fence that prescribes %r" % HERO_ANCHOR)

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
        # The defect's mechanism: `tdd-workflow` is a name boost's own offline
        # fixture defines and no STARTER registry ships — four unrelated
        # registries elsewhere in the catalog do ship one, which is why the
        # bad line looked plausible — and it reached the marketing surface
        # because the demo tape was verified against that fixture.
        name = _hero_install_name()
        assert name not in _fixture_skill_names() - ONLINE_VERIFIED_FIXTURE_NAMES, (
            "the README's hero block installs %r, which only "
            "tests/make_fixture.py defines" % name)


def _smoke_examples_pipeline() -> str:
    """smoke.sh's own extraction of every README example name, verbatim."""
    m = re.search(r'^\s*EXAMPLES="\$\((.*)\)"\s*$', SMOKE, re.M)
    assert m, "tests/smoke.sh no longer extracts the README's example names"
    return m.group(1)


def _readme_example_names(readme: str = README) -> set[str]:
    names = set()
    for body in re.findall(r"```bash\n(.*?)```", readme, re.S):
        names |= set(re.findall(r"^boost (?:install|uninstall|info) ([a-z]\S*)",
                                body, re.M))
    return names


@pytest.mark.skipif(sys.platform == "win32",
                    reason="runs smoke.sh's own bash/awk line; smoke.sh is POSIX")
class TestReadmeExamples:
    """Every skill a README fence names is checked online, not just the hero's.

    `boost install code-review --local` and `boost install my-jira` sat in
    the scope and workflow sections and both exited 1 after `boost
    quickstart`: no starter registry ships either name. Only `smoke.sh
    --online` can prove a name resolves, so these pin that it is asked about
    every one of them.
    """

    def _run(self, cwd: Path) -> set[str]:
        got = subprocess.run(["bash", "-c", _smoke_examples_pipeline()], cwd=cwd,
                             capture_output=True, text=True, check=True)
        return set(got.stdout.split())

    def test_smoke_checks_every_name_the_readme_fences_use(self):
        assert self._run(ROOT) == _readme_example_names()
        assert _hero_install_name() in self._run(ROOT)

    def test_the_names_that_exited_1_would_have_been_checked(self, tmp_path):
        old = ("```bash\nboost install code-review --local\n"
               "boost uninstall code-review --local\n```\n\n"
               "```bash\nboost search jira\nboost install my-jira\n```\n")
        (tmp_path / "README.md").write_text(old, encoding="utf-8")
        assert self._run(tmp_path) == {"code-review", "my-jira"}

    def test_the_online_block_runs_them(self):
        _marker, _, online = SMOKE.partition('"${1:-}" = "--online"')
        assert 'in $EXAMPLES; do run' in online
        assert './boost info "$name"' in online

    def test_no_example_is_a_test_fixture_identifier(self):
        clash = _readme_example_names() & (
            _fixture_skill_names() - ONLINE_VERIFIED_FIXTURE_NAMES)
        assert clash == set(), (
            "README examples name skills only tests/make_fixture.py defines: "
            "%s" % sorted(clash))


class TestHeroBlockPromises:
    """The block may only promise what the block's own install line buys."""

    def test_it_does_not_promise_semantic_search_it_never_installs(self):
        # Measured in a virgin HOME: with the plain `pipx install
        # boost-skill-cli` the block itself prescribes, `dense.have_backend()`
        # is False, so the shard manifest is never fetched, `quickstart` prints
        # "semantic search needs the extra" and `boost search` reports "ranked
        # by full-content BM25". (The "0 because …" wording belongs to
        # `--dry-run`, which is not what a reader runs.)
        block = _hero_block()
        installs_extra = "[rag]" in block
        claims = [w for w in ("semantic", "vector", "fused")
                  if w in block.lower()]
        assert installs_extra or not claims, (
            "the hero block installs the stdlib default but its comments "
            "claim %s" % ", ".join(claims))
