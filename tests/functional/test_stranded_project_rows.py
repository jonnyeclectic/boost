# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A rule or workflow installed ``--local``, read from somewhere else.

Those rows live in the *user* lock tagged ``scope: project`` and an absolute
``base``, and their materialization rows are absolute paths too. So there are
two cases, and they want opposite answers:

* **The checkout still exists.** Every reader can grade it from anywhere,
  and does so correctly — so it keeps grading, and the row now says which
  checkout it is in (``list``'s FLAGS, ``verify``'s scope and base).
* **The checkout has been deleted.** Every artifact reads as missing, and
  every remedy that answers "missing" (`reinstall`, `sync`, `heal`, `update`)
  re-materialized into the recorded base — recreating the deleted directory
  with a ``.cursor/`` and a ``CLAUDE.local.md`` in it. These rows are now
  ``stranded`` on every surface, the remedy named is ``boost uninstall``, and
  the write that would recreate the repo is refused.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from boost_cli.cli import COMMANDS
from boost_cli.core import complete, lockfile, paths


def _commit(tap, rel, text, msg):
    p = tap / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    run = lambda *a: subprocess.run(a, cwd=tap, check=True, capture_output=True)
    run("git", "add", rel)
    run("git", "commit", "-qm", msg)


_RULE = "---\nname: house-style\nversion: %s\n---\n\n%s\n"


@pytest.fixture()
def trio(boost, fixture_tap_src, tmp_path):
    """The fixture tap plus one rule and one workflow, tapped."""
    tap = tmp_path / "trio-tap"
    shutil.copytree(fixture_tap_src, tap)
    _commit(tap, "rules/house.mdc", _RULE % ("1.0.0", "Always write tests."),
            "add a rule")
    _commit(tap, "commands/ship-it.md",
            "---\nname: ship-it\nversion: 1.0.0\n---\n\nShip-it checklist.\n",
            "add a workflow")
    boost("tap", str(tap))
    return tap


@pytest.fixture()
def elsewhere(tmp_path):
    d = tmp_path / "elsewhere"
    (d / ".git").mkdir(parents=True)
    return d


@pytest.fixture()
def alive(boost, trio, tmp_path, elsewhere, monkeypatch):
    """Both items installed `--local` into ``repo``, read from ``elsewhere``."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.chdir(repo)
    boost("install", "house-style", "--local")
    boost("install", "ship-it", "--local")
    assert lockfile.get_rule("house-style")["scope"] == "project"
    monkeypatch.chdir(elsewhere)
    return repo


@pytest.fixture()
def stranded(alive):
    """The same, with ``repo`` deleted — what `rm -rf` on a checkout leaves."""
    shutil.rmtree(alive)
    assert not alive.exists()
    return alive


def _flat(text):
    return " ".join(text.split())


# --- the checkout is gone ---------------------------------------------------


def test_doctor_names_the_stranded_row_with_the_remedy_that_clears_it(
        boost, stranded):
    out = _flat(boost("doctor", expect=1).out)
    assert ("rule house-style was installed --local into %s, which no longer "
            "exists — run `boost uninstall house-style`"
            % paths.tilde(stranded)) in out
    assert "workflow ship-it was installed --local into" in out
    # One line per item, not one per agent, and never the remedy that
    # recreates the directory.
    assert out.count("house-style was installed --local") == 1
    assert "boost reinstall house-style" not in out
    assert "fully materialized" not in out
    assert "2 issues need attention" in out


def test_verify_says_stranded_and_fails(boost, stranded):
    res = boost("verify", expect=1)
    flat = _flat(res.out)
    assert "house-style stranded" in flat
    assert "`boost uninstall house-style` drops the record" in flat
    data = json.loads(boost("verify", "--json", expect=1).out)
    row = next(r for r in data["skills"] if r["name"] == "house-style")
    assert row["status"] == "stranded"
    assert row["passed"] is False
    assert row["scope"] == "project"
    assert row["base"] == str(stranded)


def test_drift_says_stranded_and_points_at_uninstall(boost, stranded):
    out = boost("drift").out
    line = next(ln for ln in out.splitlines() if ln.startswith("house-style"))
    assert "stranded" in line
    assert "boost uninstall house-style" in line
    assert "boost heal" not in out


def test_health_needs_attention_for_a_stranded_row(boost, stranded):
    out = boost("health").out
    assert "2 stranded" in out
    assert "needs attention" in out


def test_sync_does_not_recreate_the_deleted_repo(boost, stranded):
    out = boost("sync", "-y").out
    assert not stranded.exists(), "sync recreated %s" % stranded
    assert "re-materialized" not in out


def test_heal_does_not_recreate_the_deleted_repo(boost, stranded):
    boost("heal", expect=None)
    assert not stranded.exists(), "heal recreated %s" % stranded


def test_reinstall_refuses_and_names_uninstall(boost, stranded):
    res = boost("reinstall", "house-style", expect=1)
    assert not stranded.exists(), "reinstall recreated %s" % stranded
    flat = _flat(res.out + res.err)
    assert "which no longer exists" in flat
    assert "`boost uninstall house-style` drops the record" in flat
    # The tally names what was attempted, not "skills".
    assert "Reinstalled 0 rules" in flat


def test_update_skips_a_stranded_row_with_a_reason(boost, trio, stranded):
    _commit(trio, "rules/house.mdc", _RULE % ("1.1.0", "Write tests first."),
            "bump the rule")
    out = _flat(boost("update", expect=None).out)
    assert not stranded.exists(), "update recreated %s" % stranded
    assert ("rule house-style: update skipped — it was installed --local "
            "into %s, which no longer exists" % paths.tilde(stranded)) in out
    assert lockfile.get_rule("house-style")["version"] == "1.0.0"


def test_update_is_silent_about_a_stranded_row_with_nothing_new(boost,
                                                                stranded):
    assert "house-style" not in boost("update", expect=None).out


def test_quarantine_release_does_not_recreate_the_deleted_repo(
        boost, alive, monkeypatch):
    monkeypatch.chdir(alive)
    boost("quarantine", "house-style")
    monkeypatch.chdir(alive.parent)
    shutil.rmtree(alive)
    res = boost("quarantine", "--release", "house-style", expect=1)
    assert not alive.exists(), "release recreated %s" % alive
    assert "which no longer exists" in _flat(res.out + res.err)
    assert lockfile.get_rule("house-style")["quarantined"] is True


def test_attest_names_the_reason(boost, stranded):
    out = _flat(boost("attest", "--verify", expect=1).out)
    assert ("house-style: installed --local into a directory that no longer "
            "exists (boost uninstall house-style)") in out


def test_the_mcp_doctor_tool_counts_it(boost, stranded):
    from boost_cli.commands import configuration
    text, _ = configuration._tool_doctor({})
    assert ("rule house-style: installed --local into a directory that no "
            "longer exists") in text


def test_info_names_the_gone_base_and_lists_no_agents(boost, stranded):
    out = _flat(boost("info", "house-style").out)
    assert "base %s (gone)" % paths.tilde(stranded) in out
    assert ("materialized (none — its repo no longer exists; "
            "`boost uninstall house-style` drops the record)") in out
    assert "claude-code" not in out
    data = json.loads(boost("info", "house-style", "--json").out)
    assert data["stranded"] is True


def test_cat_under_enforcement_refuses_rather_than_serving_the_tap_copy(
        boost, stranded):
    boost("config", "set", "security.enforce_digest", "true")
    res = boost("cat", "house-style", expect=1)
    flat = _flat(res.out + res.err)
    assert ("rule house-style was installed --local into %s, which no longer "
            "exists" % paths.tilde(stranded)) in flat
    assert "`boost uninstall house-style` drops the record" in flat
    assert "Always write tests." not in res.out


def test_doctor_still_names_a_quarantined_stranded_row(boost, alive,
                                                       monkeypatch):
    """Quarantining it must not be the way to make doctor go quiet: release
    refuses a stranded row, so uninstall is still its only remedy."""
    monkeypatch.chdir(alive)
    boost("quarantine", "house-style")
    monkeypatch.chdir(alive.parent)
    shutil.rmtree(alive)
    out = _flat(boost("doctor", expect=1).out)
    assert ("rule house-style was installed --local into %s, which no longer "
            "exists — run `boost uninstall house-style` to drop the record "
            "(it is quarantined; release cannot restore it)"
            % paths.tilde(alive)) in out
    # The workflow is stranded but not quarantined: no quarantine note.
    assert "ship-it to drop the record (it is quarantined" not in out
    from boost_cli.commands import configuration
    text, _ = configuration._tool_doctor({})
    assert "rule house-style: installed --local into a directory" in text


def test_list_marks_the_row_gone(boost, stranded):
    line = next(ln for ln in boost("list").out.splitlines()
                if ln.startswith("house-style"))
    assert "project:%s (gone)" % paths.tilde(stranded) in line


def test_completion_still_offers_it_to_uninstall(boost, stranded):
    """Kept on purpose: `uninstall <name>` is the remedy, so TAB must offer it."""
    assert "house-style" in complete.candidates(["boost", "uninstall", ""],
                                                COMMANDS)


def test_uninstall_clears_it_and_creates_nothing(boost, stranded):
    boost("uninstall", "house-style", "ship-it", "-y")
    assert not stranded.exists()
    assert lockfile.get_rule("house-style") is None
    assert "healthy" in boost("doctor").out


def _remedies(res):
    """Every backticked `boost ...` command a refusal printed, in order."""
    return [c.split()[1:] for c in
            re.findall(r"`(boost [^`]+)`", _flat(res.out + res.err))]


@pytest.fixture()
def fresh(tmp_path, monkeypatch):
    """A new checkout of the deleted repo, standing in it."""
    d = tmp_path / "fresh"
    (d / ".git").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d


@pytest.mark.parametrize("scope_flag", [["--local"], []],
                         ids=["local", "user"])
def test_install_over_a_stranded_row_names_a_remedy_that_runs(
        boost, stranded, fresh, scope_flag):
    """The old refusal said "uninstall it there first" about a deleted dir."""
    res = boost("install", "house-style", *scope_flag, expect=1)
    flat = _flat(res.out + res.err)
    assert ("house-style was installed --local into %s, which no longer "
            "exists" % paths.tilde(stranded)) in flat
    assert "uninstall it there first" not in flat
    assert _remedies(res) == [["uninstall", "house-style"]]
    boost(*_remedies(res)[0], "-y")
    boost("install", "house-style", *scope_flag)  # "then re-run this install"
    assert lockfile.get_rule("house-style")["scope"] == (
        "project" if scope_flag else "user")
    assert not stranded.exists()


def test_reinstall_refusal_remedies_run_in_the_order_printed(
        boost, stranded, fresh):
    """Uninstall first, then `install --local` in the new checkout."""
    steps = _remedies(boost("reinstall", "house-style", expect=1))
    assert steps == [["uninstall", "house-style"],
                     ["install", "house-style", "--local"]]
    boost(*steps[0], "-y")
    boost(*steps[1])
    row = lockfile.get_rule("house-style")
    assert (row["scope"], row["base"]) == ("project", str(fresh))
    assert not stranded.exists()


# --- the checkout still exists ----------------------------------------------


def test_a_live_row_is_still_graded_from_another_directory(boost, alive):
    """Its rows are absolute paths, so doctor can and does check them."""
    row = lockfile.get_workflow("ship-it")["materializations"][0]
    Path(row["path"]).unlink()
    out = _flat(boost("doctor", expect=1).out)
    assert "workflow ship-it missing its %s file — run `boost reinstall ship-it`" \
        % row["agent"] in out
    boost("reinstall", "ship-it")
    assert Path(row["path"]).is_file()


def test_a_live_row_is_not_stranded_anywhere(boost, alive):
    info = _flat(boost("info", "house-style").out)
    assert "base %s" % paths.tilde(alive) in info
    assert "(gone)" not in info and "no longer exists" not in info
    assert json.loads(boost("info", "house-style", "--json").out)[
        "stranded"] is False
    assert "stranded" not in boost("drift").out
    assert "stranded" not in boost("verify").out
    assert "no longer exists" not in boost("doctor", expect=None).out


def test_verify_tags_a_live_project_rule_with_its_base(boost, alive):
    data = json.loads(boost("verify", "--json").out)
    row = next(r for r in data["skills"] if r["name"] == "house-style")
    assert (row["scope"], row["base"], row["passed"]) == (
        "project", str(alive), True)
    assert "project %s" % paths.tilde(alive) in _flat(boost("verify").out)


def test_list_names_the_checkout_and_leaves_a_user_rule_unmarked(
        boost, trio, alive, monkeypatch):
    lines = boost("list").out.splitlines()
    line = next(ln for ln in lines if ln.startswith("ship-it"))
    assert "project:%s" % paths.tilde(alive) in line
    assert "(gone)" not in line
    boost("uninstall", "house-style", "-y")
    boost("install", "house-style")
    line = next(ln for ln in boost("list").out.splitlines()
                if ln.startswith("house-style"))
    assert "project:" not in line
