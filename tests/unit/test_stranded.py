# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`scopes.stranded` and the three core readers that ask it.

A ``--local`` rule or workflow whose repo has been deleted is the one row
whose "missing" remedies recreate a directory the user removed. The predicate
decides it; ``integrity`` names it, ``store`` refuses the write and keeps it
out of the repair plan. Each is pinned in both directions here.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from boost_cli.core import integrity, lockfile, paths, scopes, store
from boost_cli.errors import BoostError


def _row(base, scope="project", **extra):
    return {"scope": scope, "base": base, **extra}


# --- the predicate ----------------------------------------------------------


def test_a_project_row_whose_base_is_gone_is_stranded(tmp_path):
    assert scopes.stranded(_row(str(tmp_path / "deleted"))) is True


def test_a_project_row_whose_base_exists_is_not(tmp_path):
    assert scopes.stranded(_row(str(tmp_path))) is False


def test_a_base_that_is_a_file_is_stranded(tmp_path):
    """`isdir`, not `exists`: a file where the repo was is not the repo."""
    f = tmp_path / "file"
    f.write_text("x", encoding="utf-8")
    assert scopes.stranded(_row(str(f))) is True


def test_a_user_scope_row_is_never_stranded(tmp_path):
    assert scopes.stranded(_row(str(tmp_path / "gone"), scope="user")) is False


def test_a_row_with_a_base_and_no_scope_is_not_stranded(tmp_path):
    assert scopes.stranded({"base": str(tmp_path / "gone")}) is False


@pytest.mark.parametrize("base", [None, "", "relative/gone", {}, 7])
def test_a_base_that_names_no_directory_is_not_stranded(base):
    """No claim on a directory, so nothing to be stranded from — and no raise."""
    assert scopes.stranded(_row(base)) is False


def test_a_path_object_base_is_read(tmp_path):
    assert scopes.stranded(_row(tmp_path / "gone")) is True
    assert scopes.stranded(_row(tmp_path)) is False


# --- integrity --------------------------------------------------------------


def _mat(tmp_path, base):
    path = Path(base) / ".cursor" / "rules" / "r.mdc"
    return _row(str(base), kind="rule",
                materializations=[{"agent": "cursor", "path": str(path),
                                   "sha256": "0" * 64}])


def test_materialized_status_says_stranded_not_missing(sandbox, tmp_path):
    e = _mat(tmp_path, tmp_path / "gone")
    assert integrity.materialized_status("r", e, "rule") == \
        integrity.STATUS_STRANDED


def test_materialized_status_still_says_missing_for_a_live_repo(sandbox,
                                                                tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    assert integrity.materialized_status("r", _mat(tmp_path, repo), "rule") \
        == integrity.STATUS_MISSING


def test_quarantine_outranks_stranded(sandbox, tmp_path):
    e = _mat(tmp_path, tmp_path / "gone") | {"quarantined": True}
    assert integrity.materialized_status("r", e, "rule") == \
        integrity.STATUS_QUARANTINED


def test_stranded_fails_verification_and_is_painted(sandbox):
    assert not integrity.verification_passed(integrity.STATUS_STRANDED, [], None)
    assert integrity.verification_role(integrity.STATUS_STRANDED, False) == "warn"


# --- store: the write guard -------------------------------------------------


def test_a_lock_driven_write_into_a_deleted_repo_is_refused(sandbox, tmp_path):
    gone = tmp_path / "gone"
    with pytest.raises(BoostError) as exc:
        store._refuse_stranded_base("project", str(gone), "rule", "r")
    assert "rule r was installed into" in exc.value.message
    assert "no longer exists" in exc.value.message
    assert "`boost uninstall r`" in exc.value.hint
    assert "`boost install r --local`" in exc.value.hint
    assert not gone.exists()


def test_the_refusal_orders_uninstall_before_the_reinstall(sandbox, tmp_path):
    with pytest.raises(BoostError) as exc:
        store._refuse_stranded_base("project", str(tmp_path / "gone"), "rule",
                                    "r")
    hint = exc.value.hint
    assert "; then," in hint
    assert hint.index("`boost uninstall r`") < hint.index(
        "`boost install r --local`")


@pytest.mark.parametrize("scope,base", [("project", "fresh"), ("user", None)])
def test_a_stranded_row_blocks_any_install_and_names_uninstall(
        sandbox, tmp_path, scope, base):
    gone = tmp_path / "gone"
    req = None if base is None else tmp_path / base
    with pytest.raises(BoostError) as exc:
        store._check_scope_conflict("r", _row(str(gone)), scope, req, True)
    assert exc.value.message == (
        "r was installed --local into %s, which no longer exists"
        % paths.tilde(gone))
    assert exc.value.hint == ("`boost uninstall r` drops that record, then "
                              "re-run this install")


def test_a_live_project_row_keeps_the_cross_scope_refusal(sandbox, tmp_path):
    with pytest.raises(BoostError) as exc:
        store._check_scope_conflict("r", _row(str(tmp_path)), "user", None,
                                    True)
    assert "already installed at project scope" in exc.value.message
    assert "uninstall it there first" in exc.value.hint


def test_a_live_same_base_row_is_still_already_installed(sandbox, tmp_path):
    with pytest.raises(BoostError) as exc:
        store._check_scope_conflict("r", _row(str(tmp_path)), "project",
                                    tmp_path, False)
    assert exc.value.message == "r is already installed"
    assert store._check_scope_conflict("r", _row(str(tmp_path)), "project",
                                       tmp_path, True) is None


def test_a_lock_driven_write_into_a_live_repo_is_allowed(sandbox, tmp_path):
    assert store._refuse_stranded_base("project", str(tmp_path), "rule",
                                       "r") is None


def test_a_user_scope_write_is_not_guarded(sandbox, tmp_path):
    """The guard is about a *project's* directory; user scope has none."""
    store._refuse_stranded_base("user", str(tmp_path / "gone"), "rule", "r")


def test_a_fresh_local_install_passes_no_base_and_is_not_guarded(sandbox):
    store._refuse_stranded_base("project", None, "rule", "r")


@pytest.mark.parametrize("kind", ["rule", "workflow"])
def test_install_refuses_both_kinds_into_a_deleted_repo(sandbox, tmp_path,
                                                        kind):
    """Wired into both writers, ahead of any filesystem work."""
    gone = tmp_path / "gone"
    entry = {"name": "r", "kind": kind, "tap": "t", "skill_md": "r.md"}
    with pytest.raises(BoostError) as exc:
        store.install(entry, scope="project", base=str(gone))
    assert exc.value.message.startswith("%s r was installed into" % kind)
    assert not gone.exists()


# --- store: the readers -----------------------------------------------------


def _record(name, kind, entry):
    lock = lockfile.read()
    lock["rules" if kind == "rule" else "workflows"][name] = entry
    lockfile.write(lock)


@pytest.mark.parametrize("kind", ["rule", "workflow"])
def test_sync_plan_leaves_a_stranded_row_out(sandbox, tmp_path, kind):
    _record("r", kind, _mat(tmp_path, tmp_path / "gone"))
    assert store.sync_plan()["missing_materializations"] == []


@pytest.mark.parametrize("kind", ["rule", "workflow"])
def test_sync_plan_still_lists_a_live_repos_missing_row(sandbox, tmp_path,
                                                        kind):
    repo = tmp_path / "repo"
    repo.mkdir()
    _record("r", kind, _mat(tmp_path, repo))
    assert store.sync_plan()["missing_materializations"] == [(kind, "r")]


def test_unwritten_materializations_skip_a_stranded_row(sandbox, tmp_path):
    e = _mat(tmp_path, tmp_path / "gone")
    e["materializations"][0]["agent"] = "no-such-agent"
    _record("r", "rule", e)
    assert store.unwritten_materializations() == []
    repo = tmp_path / "repo"
    repo.mkdir()
    e["base"] = str(repo)
    _record("r", "rule", e)
    assert [row[:3] for row in store.unwritten_materializations()] == [
        ("rule", "r", "no-such-agent")]
