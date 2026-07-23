"""Unit tests: core/integrity.py — the binding-digest / commit-pin logic.

These drive integrity directly (no CLI) so the mutation gate, which runs only
tests/unit, actually exercises the enforcement decisions. The end-to-end refusal
behaviour has its own coverage in tests/functional/test_integrity_enforce.py.
"""
from __future__ import annotations

import pytest

from boost_cli.core import catalog, config, integrity, lockfile, paths, registry, store
from boost_cli.errors import BoostError


@pytest.fixture()
def installed(sandbox, fixture_tap_src):
    t = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(t)
    store.install(catalog.resolve_one("brainstorming"))
    return "brainstorming"


def _tamper(name):
    (paths.store_dir() / name / "SKILL.md").write_text("TAMPERED\n", encoding="utf-8")


# ── status ───────────────────────────────────────────────────────────────

def test_status_ok_for_an_untouched_install(installed):
    assert integrity.status(installed) == integrity.STATUS_OK


def test_status_modified_after_a_content_change(installed):
    _tamper(installed)
    assert integrity.status(installed) == integrity.STATUS_MODIFIED


def test_status_missing_when_the_store_dir_is_gone(installed):
    from boost_cli.core import util
    util.rmtree(paths.store_dir() / installed)
    assert integrity.status(installed) == integrity.STATUS_MISSING


def test_status_unlocked_when_the_lock_has_no_digest(installed):
    entry = lockfile.get_skill(installed)
    del entry["sha256"]
    lockfile.set_skill(installed, entry)
    assert integrity.status(installed) == integrity.STATUS_UNLOCKED


def test_status_unlocked_for_an_unknown_skill(sandbox):
    assert integrity.status("nope") == integrity.STATUS_UNLOCKED


def test_status_accepts_a_supplied_entry(installed):
    # The read path already has the entry — passing it avoids a re-read, and
    # must give the same answer as looking it up.
    entry = lockfile.get_skill(installed)
    assert integrity.status(installed, entry) == integrity.STATUS_OK


# ── enforcement toggle ───────────────────────────────────────────────────

def test_enforcement_is_off_by_default(installed):
    assert integrity.enforcement_enabled() is False


def test_enforcement_reads_the_config_flag(installed):
    config.set_value("security.enforce_digest", "true")
    assert integrity.enforcement_enabled() is True


def test_enforce_is_a_noop_when_disabled_even_if_modified(installed):
    _tamper(installed)
    integrity.enforce(installed)          # must not raise — enforcement is off


def test_enforce_raises_on_modified_when_enabled(installed):
    _tamper(installed)
    config.set_value("security.enforce_digest", "true")
    with pytest.raises(BoostError) as err:
        integrity.enforce(installed)
    assert "modified since install" in err.value.message
    assert "reinstall" in err.value.hint


def test_enforce_raises_on_missing_when_enabled(installed):
    from boost_cli.core import util
    util.rmtree(paths.store_dir() / installed)
    config.set_value("security.enforce_digest", "true")
    with pytest.raises(BoostError) as err:
        integrity.enforce(installed)
    assert "store directory is gone" in err.value.message


def test_enforce_does_not_raise_on_ok_when_enabled(installed):
    config.set_value("security.enforce_digest", "true")
    integrity.enforce(installed)          # clean tree — must pass


def test_enforce_does_not_block_an_unlocked_entry(installed):
    # No digest to compare — blocking would punish an old lock, not catch tampering.
    entry = lockfile.get_skill(installed)
    del entry["sha256"]
    lockfile.set_skill(installed, entry)
    config.set_value("security.enforce_digest", "true")
    integrity.enforce(installed)          # must not raise


def test_enforce_is_a_noop_for_an_unknown_skill(sandbox):
    config.set_value("security.enforce_digest", "true")
    integrity.enforce("nope")             # nothing installed — nothing to guard


# ── commit pinning ───────────────────────────────────────────────────────

def test_commit_status_none_when_not_pinned(installed):
    assert integrity.commit_status(installed) is None


def test_set_commit_pin_freezes_the_current_commit(installed):
    commit = integrity.set_commit_pin(installed, lockfile.get_skill(installed))
    assert commit
    assert lockfile.get_skill(installed)["commit_pin"] == commit
    assert integrity.commit_status(installed) == integrity.STATUS_OK


def test_commit_status_modified_when_the_commit_moves(installed):
    integrity.set_commit_pin(installed, lockfile.get_skill(installed))
    entry = lockfile.get_skill(installed)
    entry["commit"] = "0" * 40
    lockfile.set_skill(installed, entry)
    assert integrity.commit_status(installed) == integrity.STATUS_MODIFIED


def test_set_commit_pin_refuses_without_a_source_commit(installed):
    entry = lockfile.get_skill(installed)
    entry["commit"] = ""
    lockfile.set_skill(installed, entry)
    with pytest.raises(BoostError) as err:
        integrity.set_commit_pin(installed, lockfile.get_skill(installed))
    assert "no recorded source commit" in err.value.message


def test_clear_commit_pin_reports_whether_one_was_present(installed):
    integrity.set_commit_pin(installed, lockfile.get_skill(installed))
    assert integrity.clear_commit_pin(installed, lockfile.get_skill(installed)) is True
    assert integrity.clear_commit_pin(installed, lockfile.get_skill(installed)) is False
    assert integrity.commit_status(installed) is None


def test_commit_enforcement_raises_on_a_drifted_pin(installed):
    integrity.set_commit_pin(installed, lockfile.get_skill(installed))
    entry = lockfile.get_skill(installed)
    entry["commit"] = "0" * 40
    lockfile.set_skill(installed, entry)
    config.set_value("security.enforce_commit", "true")
    with pytest.raises(BoostError) as err:
        integrity.enforce(installed)
    assert "pinned to commit" in err.value.message


def test_commit_enforcement_off_by_default_does_not_block_drift(installed):
    integrity.set_commit_pin(installed, lockfile.get_skill(installed))
    entry = lockfile.get_skill(installed)
    entry["commit"] = "0" * 40
    lockfile.set_skill(installed, entry)
    integrity.enforce(installed)          # commit enforcement off — must not raise


class TestProjectScope:
    """integrity over project-scoped skills (committed into a repo, not the store)."""

    @staticmethod
    def _repo(tmp_path):
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        return repo

    def _install_local(self, sandbox, fixture_tap_src, tmp_path):
        t = registry.add(str(fixture_tap_src))
        catalog.rebuild_tap(t)
        repo = self._repo(tmp_path)
        store.install(catalog.resolve_one("brainstorming"),
                      scope="project", base=str(repo))
        from boost_cli.core import projectlock
        return repo, projectlock.get_skill(repo, "brainstorming")

    def test_project_status_ok(self, sandbox, fixture_tap_src, tmp_path):
        repo, entry = self._install_local(sandbox, fixture_tap_src, tmp_path)
        assert integrity.project_status(entry, repo) == integrity.STATUS_OK

    def test_project_status_modified(self, sandbox, fixture_tap_src, tmp_path):
        repo, entry = self._install_local(sandbox, fixture_tap_src, tmp_path)
        (repo / ".claude" / "skills" / "brainstorming" / "SKILL.md").write_text(
            "EVIL\n", encoding="utf-8")
        assert integrity.project_status(entry, repo) == integrity.STATUS_MODIFIED

    def test_project_status_missing_when_dirs_gone(self, sandbox, fixture_tap_src,
                                                   tmp_path):
        from boost_cli.core import util
        repo, entry = self._install_local(sandbox, fixture_tap_src, tmp_path)
        for m in entry["materializations"]:
            util.rmtree(repo / m["path"])
        assert integrity.project_status(entry, repo) == integrity.STATUS_MISSING

    def test_project_status_unlocked_without_a_digest(self, sandbox,
                                                      fixture_tap_src, tmp_path):
        repo, entry = self._install_local(sandbox, fixture_tap_src, tmp_path)
        entry = dict(entry)
        del entry["sha256"]
        assert integrity.project_status(entry, repo) == integrity.STATUS_UNLOCKED

    def test_project_status_ignores_an_escaping_materialization(self, sandbox,
                                                               fixture_tap_src,
                                                               tmp_path):
        # A doctored committed lock pointing outside the repo must not be hashed
        # (resolve_in_base refuses it) — so it reads as MISSING, never OK.
        repo, entry = self._install_local(sandbox, fixture_tap_src, tmp_path)
        entry = dict(entry)
        entry["materializations"] = [{"agent": "claude-code", "path": "../../etc"}]
        assert integrity.project_status(entry, repo) == integrity.STATUS_MISSING

    def test_project_skills_none_outside_a_repo(self, sandbox, monkeypatch):
        # Patch the resolver rather than chdir'ing — a unit test that chdirs
        # breaks mutmut's instrumentation (it resolves boost_cli off the cwd).
        monkeypatch.setattr(integrity.scopes, "project_root", lambda *a, **k: None)
        base, skills = integrity.project_skills()
        assert base is None and skills == {}
