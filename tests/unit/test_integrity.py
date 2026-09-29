# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: core/integrity.py — the binding-digest / commit-pin logic.

These drive integrity directly (no CLI) so the mutation gate, which runs only
tests/unit, actually exercises the enforcement decisions. The end-to-end refusal
behaviour has its own coverage in tests/functional/test_integrity_enforce.py.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from boost_cli.core import (
    catalog,
    config,
    integrity,
    lockfile,
    paths,
    registry,
    scopes,
    store,
)
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


# ── verify row pass/role ─────────────────────────────────────────────────
# A `boost verify` row can carry status "ok"/"quarantined" and still be a
# failure — missing lock fields, a drifted commit pin. These pin the single
# source of truth `cmd_verify` uses for both the failure count and the
# rendered color, so the two can never disagree again (audit-verify-findings).

def test_verification_passed_true_for_clean_ok():
    assert integrity.verification_passed(integrity.STATUS_OK, [], None) is True


def test_verification_passed_false_for_ok_with_missing_fields():
    # The exact repro: status "ok" but lock fields stripped — must not pass.
    assert integrity.verification_passed(
        integrity.STATUS_OK, ["version", "installed_at"], None) is False


def test_verification_passed_false_for_quarantined_with_missing_fields():
    assert integrity.verification_passed(
        integrity.STATUS_QUARANTINED, ["sha256"], None) is False


def test_verification_passed_true_for_clean_quarantined():
    assert integrity.verification_passed(integrity.STATUS_QUARANTINED, [], None) is True


def test_verification_passed_false_for_ok_with_drifted_commit_pin():
    assert integrity.verification_passed(
        integrity.STATUS_OK, [], integrity.STATUS_MODIFIED) is False


def test_verification_passed_false_for_modified_status_even_if_fields_present():
    assert integrity.verification_passed(integrity.STATUS_MODIFIED, [], None) is False


def test_verification_role_success_when_ok_and_passed():
    assert integrity.verification_role(integrity.STATUS_OK, True) == "success"


def test_verification_role_danger_when_ok_but_not_passed():
    # The bug: an "ok" status token must not render success-green once the
    # row is a failure for another reason.
    assert integrity.verification_role(integrity.STATUS_OK, False) == "danger"


def test_verification_role_danger_when_quarantined_but_not_passed():
    assert integrity.verification_role(integrity.STATUS_QUARANTINED, False) == "danger"


def test_verification_role_muted_when_quarantined_and_passed():
    assert integrity.verification_role(integrity.STATUS_QUARANTINED, True) == "muted"


def test_verification_role_unaffected_for_already_failing_statuses():
    # modified/missing/unlocked already render a failing color regardless of
    # `passed` — only the success/muted (ok/quarantined) roles get overridden.
    assert integrity.verification_role(integrity.STATUS_MODIFIED, False) == "warn"
    assert integrity.verification_role(integrity.STATUS_MISSING, False) == "danger"
    assert integrity.verification_role(integrity.STATUS_UNLOCKED, False) == "warn"


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
        # `resolve_base`, not `project_root`: patching by name is silent when
        # the code under test moves to the other function, and this test went
        # on passing against the real resolver until the name was updated.
        monkeypatch.setattr(integrity.scopes, "resolve_base", lambda *a, **k: None)
        base, skills = integrity.project_skills()
        assert base is None and skills == {}

    def test_project_skills_reads_an_unmarked_directory(
            self, sandbox, fixture_tap_src):
        # The seam this fixes: `install --local` resolves its base with
        # `resolve_base`, which falls back to the cwd when no VCS marker is
        # above it. Reading with `project_root` answered None for the very
        # directory install had just written, so `doctor` and `verify` called
        # a machine clean while the lock and the agent dirs sat in the cwd.
        #
        # No monkeypatch and no chdir: the `sandbox` fixture already stands in
        # an unmarked directory, so this drives the real resolver — patching
        # `scopes.resolve_base` would patch it for the code under test too,
        # since `integrity.scopes` is that same module object.
        t = registry.add(str(fixture_tap_src))
        catalog.rebuild_tap(t)
        here = Path.cwd().resolve()
        assert scopes.project_root(here) is None, (
            "a VCS marker at or above tmp_path would make this assert nothing")
        store.install(catalog.resolve_one("brainstorming"),
                      scope="project", base=str(here))
        base, skills = integrity.project_skills()
        assert base == here
        assert set(skills) == {"brainstorming"}


class TestARowNothingWritesIsNotAMissingArtifact:
    """`materialized_status` is the fifth reader of a materialization row.

    A row for an agent boost no longer writes names a file nothing wrote and
    nothing will write. Read as ``STATUS_MISSING`` it failed `boost verify`
    on every run and made `boost drift` and `boost health` demand a
    `boost sync` that skips the row by design -- the same closed loop
    `boost doctor` was fixed for
    (sync-repairs-a-disabled-agents-row-every-run). Five commands read it:
    `verify`, `attest`, `drift`, `health` and `serve`.
    """

    @staticmethod
    def _entry(kind, agent):
        gone = paths.home() / ".cursor" / "nothing-wrote-this"
        return {"kind": kind, "materializations": [
            {"agent": agent, "mode": "file", "path": str(gone),
             "sha256": "x" * 64}]}

    @staticmethod
    def _disable(agent):
        cfg = config.load()
        cfg["agents"][agent]["enabled"] = False
        config.save(cfg)

    @pytest.mark.parametrize("kind", ["rule", "workflow"])
    def test_a_disabled_agents_row_stops_reading_as_missing(self, sandbox,
                                                            kind):
        e = self._entry(kind, "cursor")
        assert integrity.materialized_status("x", e) == integrity.STATUS_MISSING
        self._disable("cursor")
        assert integrity.materialized_status("x", e) == integrity.STATUS_OK

    def test_a_workflow_row_is_judged_by_the_narrower_set_here_too(self,
                                                                   sandbox):
        """`codex` is enabled and takes rules, and has no command format, so
        the two kinds must answer differently for the same row."""
        assert integrity.materialized_status(
            "x", self._entry("rule", "codex")) == integrity.STATUS_MISSING
        assert integrity.materialized_status(
            "x", self._entry("workflow", "codex")) == integrity.STATUS_OK

    def test_an_entry_with_no_kind_is_judged_as_a_rule(self, sandbox):
        """Locks written before entries carried `kind` must not be read as
        workflows: that is the narrower set, so it would hide a real gap."""
        e = self._entry("rule", "codex")
        del e["kind"]
        assert integrity.materialized_status("x", e) == integrity.STATUS_MISSING

    def test_the_callers_kind_wins_over_the_entrys_own_field(self, sandbox):
        """Every caller loops one lock section at a time, so it knows the
        kind for certain; the entry's field is a copy that can be wrong.

        A workflow entry whose `kind` says `rule` -- restored from a snapshot
        older than the field, or hand-edited -- would be judged as a rule
        here and as a workflow by `store`, and `boost verify` and
        `boost doctor` would then give opposite answers for one row with
        nothing to say which was right. Passing the section's kind removes
        the disagreement at the source.
        """
        e = self._entry("rule", "codex")           # says rule, is a workflow
        assert integrity.materialized_status("x", e) == integrity.STATUS_MISSING
        assert integrity.materialized_status(
            "x", e, "workflow") == integrity.STATUS_OK

    def test_the_entrys_field_stays_the_fallback(self, sandbox):
        """A caller holding only the entry still gets the old answer, and an
        explicit `None` is that caller, not a third kind."""
        e = self._entry("workflow", "codex")
        assert integrity.materialized_status("x", e, None) == \
            integrity.STATUS_OK
        assert integrity.materialized_status(
            "x", self._entry("rule", "codex"), None) == integrity.STATUS_MISSING
