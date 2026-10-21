# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: ``store.installed_name`` and ``store.check_existing``.

The first is the one place a command acting on an installed item turns a
``tap:name`` into the bare lock key; the second is the one place the install
paths and ``install --dry-run`` decide whether an existing record refuses.
"""
from __future__ import annotations

import pytest

from boost_cli.core import lockfile, projectlock, scopes, store
from boost_cli.errors import BoostError


def _rec(tap, **extra):
    return {"tap": tap, "version": "1.2.3", **extra}


class TestInstalledName:
    def test_an_unqualified_name_is_returned_untouched(self, sandbox):
        assert store.installed_name("anything") == "anything"

    def test_a_qualified_miss_comes_back_bare(self, sandbox):
        assert store.installed_name("owner/repo:ghost") == "ghost"

    @pytest.mark.parametrize("qualifier", ["acme/kit", "kit"])
    def test_a_matching_qualifier_yields_the_bare_key(self, sandbox, qualifier):
        lockfile.set_entry("skill", "x", _rec("acme/kit"))
        assert store.installed_name("%s:x" % qualifier) == "x"

    def test_a_rule_matches_by_its_own_tap(self, sandbox):
        lockfile.set_entry("rule", "r", _rec("acme/rules"))
        assert store.installed_name("rules:r") == "r"

    def test_a_tapless_entry_is_local(self, sandbox):
        lockfile.set_entry("skill", "x", {"version": "1"})
        assert store.installed_name("local:x") == "x"

    def test_a_wrong_tap_raises_and_names_the_real_one(self, sandbox):
        lockfile.set_entry("skill", "x", _rec("acme/kit"))
        with pytest.raises(BoostError) as ei:
            store.installed_name("other/repo:x")
        assert ei.value.message == ("other/repo:x is not installed — x is "
                                    "installed from acme/kit, not other/repo")
        assert ei.value.hint == "name it `x` or `acme/kit:x`"

    def test_a_wrong_tap_lists_each_tap_once(self, sandbox):
        lockfile.set_entry("skill", "x", _rec("acme/kit"))
        lockfile.set_entry("rule", "x", _rec("acme/kit"))
        lockfile.set_entry("workflow", "x", _rec("zed/flows"))
        with pytest.raises(BoostError) as ei:
            store.installed_name("nope:x")
        assert "installed from acme/kit, zed/flows, not nope" in ei.value.message

    def test_a_qualifier_selecting_a_shadowed_kind_is_ambiguous(self, sandbox):
        lockfile.set_entry("skill", "x", _rec("acme/kit"))
        lockfile.set_entry("rule", "x", _rec("zed/rules"))
        with pytest.raises(BoostError) as ei:
            store.installed_name("rules:x")
        assert ei.value.message == (
            "rules:x is ambiguous here — it selects the rule x, but the skill "
            "x from acme/kit is the one this command would act on")
        # The qualifier that names the item the command reaches is fine.
        assert store.installed_name("kit:x") == "x"

    def test_a_project_skill_is_checked_too(self, sandbox, tmp_path, monkeypatch):
        repo = tmp_path / "proj"
        (repo / ".git").mkdir(parents=True)
        monkeypatch.chdir(repo)
        projectlock.set_skill(repo, "p", _rec("acme/kit"))
        assert store.installed_name("kit:p") == "p"
        with pytest.raises(BoostError, match="installed from acme/kit, not zed"):
            store.installed_name("zed:p")

    @pytest.fixture
    def twin(self, sandbox, tmp_path, monkeypatch):
        """User ``x`` from acme/kit, project ``x`` from zed/kit."""
        repo = tmp_path / "proj"
        (repo / ".git").mkdir(parents=True)
        monkeypatch.chdir(repo)
        lockfile.set_entry("skill", "x", _rec("acme/kit"))
        projectlock.set_skill(repo, "x", _rec("zed/kit"))
        return repo

    def test_project_scope_checks_the_project_row(self, twin):
        assert store.installed_name("zed/kit:x", scopes.SCOPE_PROJECT) == "x"
        with pytest.raises(BoostError) as ei:
            store.installed_name("acme/kit:x", scopes.SCOPE_PROJECT)
        assert ei.value.message == ("acme/kit:x is not installed in this repo "
                                    "— x is installed from zed/kit, not "
                                    "acme/kit")
        assert ei.value.hint == "name it `x` or `zed/kit:x`"

    def test_user_scope_checks_the_user_row(self, twin):
        assert store.installed_name("acme/kit:x", scopes.SCOPE_USER) == "x"
        with pytest.raises(BoostError) as ei:
            store.installed_name("zed/kit:x", scopes.SCOPE_USER)
        assert ei.value.message == ("zed/kit:x is not installed in your user "
                                    "config — x is installed from acme/kit, "
                                    "not zed/kit")
        assert ei.value.hint == "name it `x` or `acme/kit:x`"

    def test_no_scope_points_a_project_only_match_at_local(self, twin):
        assert store.installed_name("acme/kit:x") == "x"
        with pytest.raises(BoostError) as ei:
            store.installed_name("zed/kit:x")
        assert ei.value.message == (
            "zed/kit:x is ambiguous here — it selects the skill x, but the "
            "skill x from acme/kit is the one this command would act on")
        assert ei.value.hint == "add `--local` to act on this repo's copy"

    def test_project_scope_outside_a_repo_comes_back_bare(self, sandbox,
                                                          tmp_path,
                                                          monkeypatch):
        monkeypatch.chdir(tmp_path)
        lockfile.set_entry("skill", "x", _rec("acme/kit"))
        assert store.installed_name("zed:x", scopes.SCOPE_PROJECT) == "x"

    def test_a_project_scope_miss_comes_back_bare(self, twin):
        # Only the user lock holds `y`: --local names nothing, and the
        # caller's own lookup says so.
        lockfile.set_entry("skill", "y", _rec("acme/kit"))
        assert store.installed_name("zed:y", scopes.SCOPE_PROJECT) == "y"

    def test_user_scope_ignores_a_project_only_item(self, twin):
        projectlock.set_skill(twin, "p", _rec("zed/kit"))
        assert store.installed_name("acme/kit:p", scopes.SCOPE_USER) == "p"


def _entry(kind="skill", name="x"):
    return {"name": name, "kind": kind, "tap": "acme/kit", "version": "2.0.0"}


class TestCheckExisting:
    def test_nothing_installed_returns_none(self, sandbox):
        assert store.check_existing(_entry()) is None

    def test_an_installed_skill_refuses_without_force(self, sandbox):
        lockfile.set_entry("skill", "x", _rec("acme/kit"))
        with pytest.raises(BoostError) as ei:
            store.check_existing(_entry())
        assert ei.value.message == "x is already installed (v1.2.3)"
        assert ei.value.hint == ("`boost reinstall x` to force, `boost update` "
                                 "to upgrade")

    def test_force_returns_the_record(self, sandbox):
        rec = _rec("acme/kit")
        lockfile.set_entry("skill", "x", rec)
        assert store.check_existing(_entry(), force=True) == rec

    def test_a_pinned_skill_says_pinned(self, sandbox):
        lockfile.set_entry("skill", "x", _rec("acme/kit", pinned=True))
        with pytest.raises(BoostError) as ei:
            store.check_existing(_entry())
        assert ei.value.message == "x is pinned"
        assert ei.value.hint == "`boost unpin x` first"
        assert store.check_existing(_entry(), force=True)["pinned"] is True

    @pytest.mark.parametrize("kind", ["rule", "workflow"])
    def test_an_installed_rule_or_workflow_refuses_without_force(self, sandbox, kind):
        lockfile.set_entry(kind, "x", _rec("acme/kit", scope="user"))
        with pytest.raises(BoostError) as ei:
            store.check_existing(_entry(kind))
        assert ei.value.message == "x is already installed"
        assert store.check_existing(_entry(kind), force=True)["tap"] == "acme/kit"

    def test_the_kind_argument_overrides_the_entry(self, sandbox):
        lockfile.set_entry("rule", "x", _rec("acme/kit", scope="user"))
        assert store.check_existing(_entry("skill")) is None
        with pytest.raises(BoostError, match="already installed"):
            store.check_existing(_entry("skill"), kind="rule")

    def test_a_skill_record_does_not_block_a_same_named_rule(self, sandbox):
        lockfile.set_entry("skill", "x", _rec("acme/kit"))
        assert store.check_existing(_entry("rule")) is None

    def test_a_project_skill_reads_the_project_lock(self, sandbox, tmp_path,
                                                    monkeypatch):
        repo = tmp_path / "proj"
        (repo / ".git").mkdir(parents=True)
        monkeypatch.chdir(repo)
        # A user-scope record is not this scope's install.
        lockfile.set_entry("skill", "x", _rec("acme/kit"))
        assert store.check_existing(_entry(), scope="project") is None
        projectlock.set_skill(repo, "x", _rec("acme/kit"))
        with pytest.raises(BoostError) as ei:
            store.check_existing(_entry(), scope="project")
        assert ei.value.message == "x is already installed in this project (v1.2.3)"
        assert ei.value.hint == "`boost reinstall x --local` to force"
        assert store.check_existing(_entry(), scope="project", force=True)["tap"] \
            == "acme/kit"

    def test_a_cross_tap_user_install_names_the_installed_tap(self, sandbox):
        lockfile.set_entry("skill", "x", _rec("zed/kit"))
        with pytest.raises(BoostError) as ei:
            store.check_existing(_entry())
        assert ei.value.message == ("x is already installed (v1.2.3) from "
                                    "zed/kit, not acme/kit")
        assert ei.value.hint == "`boost install acme/kit:x --force` to replace it"

    def test_a_cross_tap_project_install_keeps_qualifier_and_local(
            self, sandbox, tmp_path, monkeypatch):
        repo = tmp_path / "proj"
        (repo / ".git").mkdir(parents=True)
        monkeypatch.chdir(repo)
        projectlock.set_skill(repo, "x", _rec("zed/kit"))
        with pytest.raises(BoostError) as ei:
            store.check_existing(_entry(), scope="project")
        assert ei.value.message == ("x is already installed in this project "
                                    "(v1.2.3) from zed/kit, not acme/kit")
        assert ei.value.hint == ("`boost install acme/kit:x --local --force` "
                                 "to replace it")

    @pytest.mark.parametrize("installed_tap, entry_tap", [
        ("", "acme/kit"), ("acme/kit", "")])
    def test_a_tapless_side_keeps_the_bare_hint(self, sandbox, installed_tap,
                                                entry_tap):
        lockfile.set_entry("skill", "x", _rec(installed_tap))
        entry = dict(_entry(), tap=entry_tap)
        with pytest.raises(BoostError) as ei:
            store.check_existing(entry)
        assert ei.value.message == "x is already installed (v1.2.3)"
