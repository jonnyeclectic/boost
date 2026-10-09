# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: core/integrity.py — the binding-digest / commit-pin logic.

These drive integrity directly (no CLI) so the mutation gate, which runs only
tests/unit, actually exercises the enforcement decisions. The end-to-end refusal
behaviour has its own coverage in tests/functional/test_integrity_enforce.py.
"""
from __future__ import annotations

import hashlib
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

    `_entry` builds exactly **one** row, so every entry here is also the
    all-rows-unwritten case and now reads ``UNREACHABLE`` rather than ``OK``
    -- still not ``MISSING``, which is the whole of what this class pins.
    The per-item question these answers could not express lives in
    :class:`TestAnItemMaterializedNowhere` below.
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
        assert integrity.materialized_status("x", e) == \
            integrity.STATUS_UNREACHABLE

    def test_a_workflow_row_is_judged_by_the_narrower_set_here_too(self,
                                                                   sandbox):
        """`codex` is enabled and takes rules, and has no command format, so
        the two kinds must answer differently for the same row."""
        assert integrity.materialized_status(
            "x", self._entry("rule", "codex")) == integrity.STATUS_MISSING
        assert integrity.materialized_status(
            "x", self._entry("workflow", "codex")) == \
            integrity.STATUS_UNREACHABLE

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
            "x", e, "workflow") == integrity.STATUS_UNREACHABLE

    def test_the_entrys_field_stays_the_fallback(self, sandbox):
        """A caller holding only the entry still gets the old answer, and an
        explicit `None` is that caller, not a third kind."""
        e = self._entry("workflow", "codex")
        assert integrity.materialized_status("x", e, None) == \
            integrity.STATUS_UNREACHABLE
        assert integrity.materialized_status(
            "x", self._entry("rule", "codex"), None) == integrity.STATUS_MISSING


class TestAnItemMaterializedNowhere:
    """Skipping a row is correct per row and wrong per *item*.

    Skip every row an item has and it reached no agent at all -- the rule is
    in no context file, the workflow in no command palette -- and the loop
    that skipped them had nothing left to judge, so it fell through to
    ``OK``. `verify` passed it, `drift` called it in-sync, `health` counted
    it installed and healthy and `attest --verify` said ``sha_ok``. Only
    `doctor` carried the news, in the one channel the others do not have.

    The opposite error is the dangerous one: keying on "no row was written"
    rather than "rows existed and none was written" condemns every pre-rows
    lock entry on five surfaces at once, so the no-rows case is pinned here
    in all three of its spellings.
    """

    @staticmethod
    def _row(agent, path, sha):
        return {"agent": agent, "mode": "file", "path": str(path),
                "sha256": sha}

    @staticmethod
    def _disable(agent):
        cfg = config.load()
        cfg["agents"][agent]["enabled"] = False
        config.save(cfg)

    def _written_row(self, tmp_path, body="hello\n"):
        """A row for an agent boost still writes, present and correctly hashed."""
        f = tmp_path / "written.md"
        f.write_text(body, encoding="utf-8")
        return self._row("cursor", f,
                         hashlib.sha256(body.encode("utf-8")).hexdigest())

    def _skipped_row(self):
        """A row for an agent boost no longer writes (windsurf, disabled)."""
        self._disable("windsurf")
        return self._row("windsurf", paths.home() / ".windsurf" / "gone.md",
                         "x" * 64)

    # ---------------------------------------------------- the new state

    @pytest.mark.parametrize("kind", ["rule", "workflow"])
    def test_every_row_skipped_is_unreachable(self, sandbox, kind):
        e = {"kind": kind, "materializations": [self._skipped_row()]}
        assert integrity.materialized_status("x", e, kind) == \
            integrity.STATUS_UNREACHABLE
        assert integrity.reaches_no_agent(kind, e) is True

    # ------------------------------------- the control case, all 3 spellings

    @pytest.mark.parametrize("kind", ["rule", "workflow"])
    @pytest.mark.parametrize("entry", [
        {},                             # key absent -- a pre-rows lock entry
        {"materializations": []},       # present and empty
        {"materializations": None},     # present and null
    ], ids=["absent", "empty", "null"])
    def test_an_item_with_no_rows_is_not_unreachable(self, sandbox, kind,
                                                     entry):
        """`bool(rows)` is the entire guard, and this is what it guards.

        A rule installed before rows existed has nothing to be unreachable
        about. Without the conjunct every such entry turns into a fault on
        `verify`, `attest`, `drift`, `health` and the MCP doctor at once.
        """
        e = dict(entry, kind=kind)
        assert integrity.reaches_no_agent(kind, e) is False
        assert integrity.materialized_status("x", e, kind) == \
            integrity.STATUS_OK

    # ------------------------------------------------- the partial case

    def test_one_written_row_is_enough_to_reach_somewhere(self, sandbox,
                                                          tmp_path):
        """The trigger is *every* row skipped, never *any* row skipped.

        This is the mutant one edit away from the bug: `not any(...)` versus
        a count comparison that treats a partially-reached item as lost.
        """
        skipped = self._skipped_row()
        e = {"kind": "rule",
             "materializations": [skipped, self._written_row(tmp_path)]}
        assert integrity.reaches_no_agent("rule", e) is False
        assert integrity.materialized_status("x", e, "rule") == \
            integrity.STATUS_OK

    # ------------------------------------------- mutual exclusivity

    def test_a_written_row_that_is_gone_still_reads_missing(self, sandbox,
                                                            tmp_path):
        """MISSING, MODIFIED and UNLOCKED each need a *written* row, so the
        new early return can never shadow one.

        What this pins is the *over-firing* direction: a `reaches_no_agent`
        that answered True for a partially reached entry would shadow MISSING
        here, and the `not any(...)` -> `any(...)` mutant fails on this exact
        test. The early return's *position* is not pinned and cannot be --
        moving it below the loop leaves the whole unit suite green, because
        every in-loop return and the only `unlocked = True` require a written
        row while this predicate is True only when none is, so the two
        placements are observationally identical. Measured, not predicted: an
        earlier draft of this docstring claimed the move "dies here" and it
        does not. The position is argued in the source comment instead."""
        row = self._written_row(tmp_path)
        (tmp_path / "written.md").unlink()
        e = {"kind": "rule", "materializations": [self._skipped_row(), row]}
        assert integrity.materialized_status("x", e, "rule") == \
            integrity.STATUS_MISSING

    def test_a_written_row_with_no_sha_still_reads_unlocked(self, sandbox,
                                                            tmp_path):
        row = self._written_row(tmp_path)
        del row["sha256"]
        e = {"kind": "rule", "materializations": [self._skipped_row(), row]}
        assert integrity.materialized_status("x", e, "rule") == \
            integrity.STATUS_UNLOCKED

    def test_quarantine_still_wins(self, sandbox):
        """Its artifacts are gone on purpose. Calling that unreachable sends
        the user to a remedy that re-arms what quarantine disarmed."""
        e = {"kind": "rule", "quarantined": True,
             "materializations": [self._skipped_row()]}
        assert integrity.materialized_status("x", e, "rule") == \
            integrity.STATUS_QUARANTINED

    # ------------------------------------------------ the kind decides

    def test_the_kind_decides_the_write_set_here_too(self, sandbox):
        """`codex` is enabled and takes rules, and has no command format. One
        row, two answers -- which is what kills the mutant that drops the
        `kind` argument on the way through."""
        e = {"materializations": [
            self._row("codex", paths.home() / ".codex" / "AGENTS.md",
                      "x" * 64)]}
        assert integrity.reaches_no_agent("workflow", e) is True
        assert integrity.reaches_no_agent("rule", e) is False

    def test_it_resolves_its_own_kind_when_asked_without_one(self, sandbox):
        """`materialized_status` hands it an already-resolved kind, and
        `doctor` and `info` pass the section's. Nothing in the tree reaches
        the fallback, so it is pinned here or the mutant that drops it
        survives -- and a caller holding only the entry would then judge
        every workflow against the wider rule set.
        """
        e = {"kind": "workflow", "materializations": [
            self._row("codex", paths.home() / ".codex" / "AGENTS.md",
                      "x" * 64)]}
        assert integrity.reaches_no_agent(None, e) is True
        assert integrity.reaches_no_agent(None, dict(e, kind="rule")) is False
        # and with no kind anywhere, a rule -- the wider set, so a real gap
        # is reported rather than silently hidden
        del e["kind"]
        assert integrity.reaches_no_agent(None, e) is False

    def test_the_rows_own_scope_decides_the_write_set(self, sandbox):
        """`entry["base"]` is load-bearing, and nothing used to prove it.

        Every other test here builds a user-scope entry, so replacing
        `entry.get("base")` with `None` left the whole unit suite green --
        a free survivor against the 80% gate on a line this change added.
        It is not an equivalent mutant: `project_scope` is read per agent
        out of config exactly as `enabled` is, so one agent turned off for
        project scope makes `materializing_agents(base)` a strict subset of
        `materializing_agents(None)`. A project-scoped rule whose only row
        names that agent is the one input class where the mutant silently
        restores the bug this whole change exists to fix -- it reads OK
        while reaching nothing.
        """
        from boost_cli.core import config
        cfg = config.load()
        cfg["agents"]["cursor"]["project_scope"] = False
        config.save(cfg)
        row = {"agent": "cursor", "mode": "file",
               "path": "/repo/.cursor/rules/x.mdc", "sha256": "a" * 64}
        scoped = {"kind": "rule", "base": "/repo", "materializations": [row]}
        # cursor does not materialize under a project base, so the row's own
        # scope is what condemns the item
        assert integrity.reaches_no_agent("rule", scoped) is True
        # the same row at user scope reaches cursor, so the only difference
        # between the two answers is the `base` the mutant drops
        unscoped = {k: v for k, v in scoped.items() if k != "base"}
        assert integrity.reaches_no_agent("rule", unscoped) is False
        assert integrity.materialized_status("x", scoped, "rule") == \
            integrity.STATUS_UNREACHABLE

    def test_a_row_with_no_agent_counts_as_written(self, sandbox):
        """`agents` answers True for it, preferring a reported gap to a
        dropped one -- so such an entry is judged by the loop, never
        condemned by the new early return."""
        e = {"kind": "rule", "materializations": [
            {"mode": "file", "path": str(paths.home() / "nope.md"),
             "sha256": "x" * 64}]}
        assert integrity.reaches_no_agent("rule", e) is False
        assert integrity.materialized_status("x", e, "rule") == \
            integrity.STATUS_MISSING

    # --------------------------------------------- the verify wiring

    def test_verify_fails_an_unreachable_row(self):
        """`verification_passed` is an allowlist, so a new status fails by
        inheritance. That is convenient and invisible, so it is pinned."""
        assert integrity.verification_passed(
            integrity.STATUS_UNREACHABLE, [], None) is False

    def test_unreachable_wears_the_warn_role(self):
        assert integrity.verification_role(
            integrity.STATUS_UNREACHABLE, False) == "warn"

    def test_every_status_has_a_verify_role(self):
        """`verification_role` falls back to "warn" for an unknown status, so
        a constant added without a row here would be coloured by accident and
        would silently skip the not-passed upgrade beside it."""
        statuses = {v for k, v in vars(integrity).items()
                    if k.startswith("STATUS_") and isinstance(v, str)}
        assert statuses <= set(integrity._VERIFY_ROLE_BY_STATUS)


class TestWrittenAgentNames:
    """`written_agent_names` is what every agents line reads.

    `lockfile.agent_names` lists every *recorded* row, so a rule written for
    one of five recorded agents advertised all five in `list`, `info` and
    `stats` while `doctor` said four were no longer written. This filters
    through `reaches_no_agent`'s own predicate, so the two cannot drift.
    """

    @staticmethod
    def _row(agent):
        r = {"mode": "file", "sha256": "x" * 64,
             "path": str(paths.home() / "x.md")}
        if agent is not None:
            r["agent"] = agent
        return r

    @staticmethod
    def _disable(*names):
        cfg = config.load()
        for n in names:
            cfg["agents"][n]["enabled"] = False
        config.save(cfg)

    def _entry(self, kind, *names):
        return {"kind": kind,
                "materializations": [self._row(n) for n in names]}

    @pytest.mark.parametrize("kind", ["rule", "workflow"])
    def test_a_partial_item_names_only_the_agent_it_reaches(self, sandbox,
                                                            kind):
        """The card's fixture: five recorded rows, only cursor enabled."""
        e = self._entry(kind, "windsurf", "cursor", "claude-code", "gemini",
                        "codex")
        self._disable("claude-code", "codex", "gemini", "windsurf")
        assert integrity.written_agent_names(kind, e) == ["cursor"]
        # the raw reader still lists the record -- uninstall needs it
        assert len(lockfile.agent_names(kind, e)) == 5

    @pytest.mark.parametrize("kind", ["rule", "workflow"])
    def test_an_unreachable_item_names_none(self, sandbox, kind):
        """Agrees with `reaches_no_agent` in its True direction."""
        e = self._entry(kind, "cursor", "windsurf")
        self._disable("cursor", "windsurf")
        assert integrity.reaches_no_agent(kind, e) is True
        assert integrity.written_agent_names(kind, e) == []

    def test_the_kind_decides_the_write_set(self, sandbox):
        """codex takes rules and has no command format: one row, two answers."""
        e = self._entry("rule", "codex", "cursor")
        assert integrity.written_agent_names("rule", e) == ["codex", "cursor"]
        assert integrity.written_agent_names("workflow", e) == ["cursor"]

    def test_the_entrys_kind_is_the_fallback_and_rule_the_default(self,
                                                                  sandbox):
        e = self._entry("workflow", "codex", "cursor")
        assert integrity.written_agent_names(None, e) == ["cursor"]
        del e["kind"]
        assert integrity.written_agent_names(None, e) == ["codex", "cursor"]

    def test_the_rows_own_scope_decides_the_write_set(self, sandbox):
        cfg = config.load()
        cfg["agents"]["cursor"]["project_scope"] = False
        config.save(cfg)
        e = self._entry("rule", "cursor", "claude-code")
        assert integrity.written_agent_names("rule", e) == \
            ["claude-code", "cursor"]
        e["base"] = "/repo"
        assert integrity.written_agent_names("rule", e) == ["claude-code"]

    def test_a_row_with_no_agent_counts_as_written(self, sandbox):
        """As in `reaches_no_agent`: a reported gap beats a dropped one."""
        e = self._entry("rule", None, "windsurf")
        self._disable("windsurf")
        assert integrity.written_agent_names("rule", e) == ["?"]

    def test_names_are_sorted_and_deduplicated(self, sandbox):
        e = self._entry("rule", "windsurf", "cursor", "windsurf")
        assert integrity.written_agent_names("rule", e) == \
            ["cursor", "windsurf"]

    def test_a_skill_passes_through_unfiltered(self, sandbox):
        """A skill records links, not rows -- and no materializations to
        filter, so treating it as a rule would answer [] for every skill."""
        self._disable("windsurf")
        e = {"agents": ["windsurf", "claude-code"]}
        assert integrity.written_agent_names("skill", e) == \
            ["claude-code", "windsurf"]

    @pytest.mark.parametrize("entry", [None, {}])
    def test_no_entry_names_none(self, sandbox, entry):
        assert integrity.written_agent_names("rule", entry) == []
        assert integrity.written_agent_names("skill", entry) == []
