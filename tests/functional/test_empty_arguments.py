# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: an explicitly empty argument is a usage error, exit 2.

Every handler that branches on ``if args.name:`` reads ``""`` as "not given",
so an empty string took the no-argument path: ``attest --verify ""`` verified
every skill and went green, ``cohort apply ""`` applied every cohort,
``lint ""`` scored the current directory, ``tap ""`` and ``import ""`` read
``Path("")`` as the current directory and wrote config, store and lock state
for it, and ``export -o ""`` wrote the default filename. ``boost attest "$UNSET"``
in a script is how a user gets here. ``util.nonempty_str`` refuses it at parse
time, naming the argument; an *omitted* optional NAME still means "all".
"""
from __future__ import annotations

import pytest

from boost_cli.core import paths

# (argv, the argument argparse names in the error)
CASES = [
    (("tap", ""), "spec"),
    (("tap", "   "), "spec"),
    (("import", ""), "URL_OR_PATH"),
    (("cohort", "apply", ""), "name"),
    (("attest", "--verify", ""), "NAME"),
    (("deps", ""), "name"),
    (("impact", ""), "NAME"),
    (("who", ""), "skill"),
    (("log", ""), "name"),
    (("trust", "verify", ""), "name"),
    (("lint", ""), "NAME"),
    (("tag", ""), "name"),
    (("export", "brainstorming", "-o", ""), "-o/--output/--out"),
    (("adapt", "brainstorming", "--to", "crewai", "-o", ""),
     "-o/--output/--out"),
    (("run", "brainstorming", "--print", "-o", ""), "-o/--output/--out"),
    (("infer", "--path", ""), "--path"),
    (("create", "zz", "--dir", ""), "--dir"),
    (("absorb", "--history", ""), "--history"),
    (("list", "--tag", ""), "--tag"),
    (("search", "--category", "", "brainstorm"), "--category"),
    (("search", "brainstorm", "--category="), "--category"),
    (("browse", "--category", ""), "--category"),
    (("pulse", "--action", ""), "--action"),
    (("lint", "--tap", ""), "--tap"),
    (("recommend", "--path", ""), "--path"),
    (("recommend", "--category", ""), "--category"),
    (("onboard", "--repo", ""), "--repo"),
    (("hooks", "add", "SessionStart", "-c", "true", "-n", "x", "-m", ""),
     "-m/--matcher"),
    (("install", "brainstorming", "--agent", ""), "--agent"),
]


@pytest.mark.parametrize(("argv", "arg"), CASES,
                         ids=[" ".join(c[0]) or "?" for c in CASES])
def test_empty_value_is_a_usage_error_naming_the_argument(boost, installed,
                                                          argv, arg):
    r = boost(*argv, expect=2)
    assert r.out == ""
    lines = r.err.splitlines()
    assert lines[0] == "Error: argument %s: must not be empty" % arg
    assert lines[1].startswith("usage: boost %s " % argv[0])


def _snapshot() -> dict[str, bytes | None]:
    """The state files a wrongly-widened command would have written."""
    files = {"config": paths.config_path(), "lock": paths.lockfile_path(),
             "pulse": paths.pulse_path()}
    return {k: (p.read_bytes() if p.is_file() else None)
            for k, p in files.items()}


def test_tap_empty_inside_a_git_repo_taps_nothing(boost, sandbox, tapped,
                                                  fixture_tap_src, monkeypatch):
    # The cwd is a real git repo, so Path("") == "." would have tapped it.
    monkeypatch.chdir(fixture_tap_src)
    before = _snapshot()
    boost("tap", "", expect=2)
    assert _snapshot() == before
    assert "\n1 tap · 5 items\n" in boost("taps").out


def test_import_empty_beside_a_skill_md_imports_nothing(boost, sandbox,
                                                        tmp_path, monkeypatch):
    src = tmp_path / "imp"
    src.mkdir()
    (src / "SKILL.md").write_text(
        "---\nname: bar\ndescription: bar skill\n---\nbody\n", encoding="utf-8")
    monkeypatch.chdir(src)
    before = _snapshot()
    boost("import", "", expect=2)
    assert _snapshot() == before
    assert not (paths.store_dir() / "bar").exists()


def test_cohort_apply_empty_applies_no_cohort(boost, tapped):
    boost("cohort", "create", "team", "--skills", "brainstorming",
          "--percent", "100")
    before = _snapshot()
    boost("cohort", "apply", "", expect=2)
    assert _snapshot() == before
    assert not (paths.store_dir() / "brainstorming").exists()


def test_omitted_name_still_means_all(boost, installed):
    # Only the explicit "" changed: no NAME keeps meaning every skill.
    r = boost("deps")
    assert "across 1 skill" in r.out
    assert boost("list", "--tag", "nosuch").rc == 0
