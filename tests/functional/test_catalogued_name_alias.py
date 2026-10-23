# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A frontmatter name the catalog had to slug is one name to every command.

`c++-helper` is catalogued as `c--helper` (``+`` is not a path component
character). `boost install c++-helper` found it through the catalog alias and
copied it to `c--helper` without a word; `boost info c++-helper` then said
"invalid skill name" and `boost uninstall c++-helper` said "not installed".
"""
from __future__ import annotations

import json
import subprocess

import pytest

from boost_cli.core import catalog, paths, store

NOTE = "  using name 'c--helper' (from 'c++-helper')\n"


def _git_tap(root):
    skill = root / "skills" / "c++-helper" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: c++-helper\ndescription: Help with C++ "
                     "templates.\n---\n\nUse RAII.\n", encoding="utf-8")
    for argv in (("git", "init", "-q"),
                 ("git", "config", "user.email", "t@boost.test"),
                 ("git", "config", "user.name", "T"),
                 ("git", "add", "-A"), ("git", "commit", "-qm", "x")):
        subprocess.run(argv, cwd=root, check=True, capture_output=True)
    return root


@pytest.fixture()
def cpp_tap(boost, tmp_path):
    boost("tap", _git_tap(tmp_path / "cpp-tap"))


def test_install_info_uninstall_all_take_the_frontmatter_spelling(boost, cpp_tap):
    r = boost("install", "c++-helper")
    assert r.err.startswith(NOTE) and r.err.count("using name") == 1
    assert (paths.store_dir() / "c--helper" / "SKILL.md").is_file()

    r = boost("info", "c++-helper", "--json")
    assert r.err == NOTE
    data = json.loads(r.out)
    assert (data["name"], data["installed"]["tap"]) == ("c--helper", "cpp-tap")

    r = boost("uninstall", "c++-helper", "-y")
    assert r.err.startswith(NOTE) and r.err.count("using name") == 1
    assert not (paths.store_dir() / "c--helper").exists()


def test_info_before_install_resolves_the_alias(boost, cpp_tap):
    r = boost("info", "c++-helper", "--json")
    assert r.err == NOTE
    assert json.loads(r.out)["name"] == "c--helper"


def test_the_slug_itself_needs_no_note(boost, cpp_tap):
    r = boost("install", "c--helper")
    assert "using name" not in r.err
    r = boost("info", "c--helper", "--json")
    assert r.err == ""


def test_addressable_name_follows_only_the_catalog_alias(boost, cpp_tap):
    assert catalog.addressable_name("c++-helper") == "c--helper"
    assert catalog.addressable_name("c--helper") == "c--helper"
    # Never a fresh slug of the input: that would aim `uninstall c+helper`
    # at an unrelated `c-helper`.
    assert catalog.addressable_name("c+helper") == "c+helper"
    assert catalog.addressable_name("../c++-helper") == "../c++-helper"


def test_an_alias_naming_two_slugs_is_left_alone(monkeypatch):
    monkeypatch.setattr(catalog, "find", lambda name: [{"name": "a-1"},
                                                       {"name": "a-2"}])
    assert catalog.addressable_name("a?") == "a?"


def test_installed_name_and_lock_entry_use_the_slug(boost, cpp_tap):
    boost("install", "c++-helper")
    assert store.installed_name("c++-helper") == "c--helper"
    bare, kind, entry = store.resolve_lock_entry("c++-helper")
    assert (bare, kind) == ("c--helper", "skill")
    assert entry is not None


def test_an_unknown_unsafe_name_is_refused_with_its_slug(boost):
    r = boost("info", "x++y", expect=1)
    assert "x++y" in r.err


def test_store_refusal_suggests_the_slug(sandbox):
    from boost_cli.errors import BoostError
    with pytest.raises(BoostError) as exc:
        store.skill_store_dir("c++-helper")
    assert exc.value.message == "invalid skill name 'c++-helper'"
    assert exc.value.hint == ("a name is a-z, A-Z, 0-9, '.', '_' and '-' — "
                              "did you mean 'c--helper'?")
    for bad in ("o/r:x", "a\\b", "a:b", "!!!"):
        with pytest.raises(BoostError) as exc:
            store.skill_store_dir(bad)
        assert exc.value.hint is None, bad
