# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Re-installing an unchanged unversioned rule or workflow is a no-op.

The skill half of this landed first (test_unversioned_reinstall.py): install
stamps the catalog entry's ``content`` digest into the lock row, and
`store.same_install` matches an unversioned re-install only when that digest
equals the catalog's. Rule and workflow rows recorded none, so the same
re-install still failed with rc 1. Both kinds now stamp it, user scope and
--local alike; the decision itself is the one shared `same_install`.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from boost_cli.core import catalog, lockfile, registry, store
from boost_cli.errors import AlreadyInstalled, BoostError

ITEMS = {
    "rule": ("rules/house.mdc", "house"),
    "workflow": ("commands/ship.md", "ship"),
}


def _tap(root: Path) -> None:
    for rel, name in ITEMS.values():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(
            "---\nname: %s\ndescription: no version here\n---\n\n%s body\n"
            % (name, name), encoding="utf-8")

    def run(*a):
        subprocess.run(a, cwd=root, check=True, capture_output=True)
    run("git", "init", "-q")
    run("git", "add", "-A")
    run("git", "-c", "user.email=t@t.test", "-c", "user.name=t",
        "commit", "-qm", "items")
    catalog.rebuild_tap(registry.add(str(root)))


@pytest.fixture(params=sorted(ITEMS))
def item(request, sandbox, tmp_path):
    """``(entry, get row, put row)`` for one unversioned rule or workflow."""
    _tap(tmp_path / "tap")
    kind = request.param
    name = ITEMS[kind][1]
    [entry] = [e for e in catalog.find(name) if e.get("kind") == kind]
    assert entry["version"] == catalog.UNDECLARED_VERSION
    assert entry["content"]
    if kind == "rule":
        return (entry, lambda: lockfile.get_rule(name),
                lambda row: lockfile.set_rule(name, row))
    return (entry, lambda: lockfile.get_workflow(name),
            lambda row: lockfile.set_workflow(name, row))


@pytest.fixture(params=["user", "project"])
def scope(request, tmp_path):
    if request.param == "user":
        return {}
    repo = tmp_path / "repo"
    repo.mkdir()
    return {"scope": "project", "base": str(repo)}


def _written(row: dict) -> dict[str, str]:
    """Every file the row says it materialized, by path, with its text."""
    out = {}
    for m in row["materializations"]:
        p = Path(m["path"])
        out[m["path"]] = p.read_text(encoding="utf-8") if p.is_file() else None
    assert out, "the install materialized nothing"
    return out


def test_install_records_the_digest(item, scope):
    entry, get, _put = item
    store.install(entry, **scope)
    assert get()["content"] == entry["content"]


def test_the_same_body_again_is_already_installed(item, scope):
    entry, get, _put = item
    store.install(entry, **scope)
    row, files = get(), _written(get())
    with pytest.raises(AlreadyInstalled) as ei:
        store.install(entry, **scope)
    assert ei.value.name == entry["name"]
    assert ei.value.version == catalog.UNDECLARED_VERSION
    # Nothing written: neither the lock row nor a context file or command.
    assert get() == row
    assert _written(get()) == files


def test_check_existing_says_the_same(item, scope):
    """`boost_install` (MCP) and `browse` decide on check_existing."""
    entry, _get, _put = item
    store.install(entry, **scope)
    with pytest.raises(AlreadyInstalled):
        store.check_existing(entry, **scope)


def test_a_changed_body_is_refused(item, scope):
    entry, _get, _put = item
    store.install(entry, **scope)
    with pytest.raises(BoostError) as ei:
        store.install({**entry, "content": "0" * 16}, **scope)
    assert type(ei.value) is BoostError
    assert ei.value.message == "%s is already installed" % entry["name"]


def test_another_agent_is_refused(item, scope):
    entry, _get, _put = item
    store.install(entry, **scope)
    with pytest.raises(BoostError) as ei:
        store.install(entry, only_agents=["cursor"], **scope)
    assert type(ei.value) is BoostError
    assert "--force" in (ei.value.hint or "")


def test_a_legacy_row_without_a_digest_is_refused(item, scope):
    entry, get, put = item
    store.install(entry, **scope)
    row = get()
    del row["content"]
    put(row)
    assert "content" not in get()
    with pytest.raises(BoostError) as ei:
        store.install(entry, **scope)
    assert type(ei.value) is BoostError


def test_two_absent_digests_are_refused(item, scope):
    entry, get, _put = item
    bare = {k: v for k, v in entry.items() if k != "content"}
    store.install(bare, **scope)
    assert "content" not in get()
    with pytest.raises(BoostError) as ei:
        store.install(bare, **scope)
    assert type(ei.value) is BoostError


def test_a_forced_reinstall_rerecords_the_digest(item, scope):
    entry, get, _put = item
    store.install({**entry, "content": "0" * 16}, **scope)
    store.install(entry, force=True, **scope)
    assert get()["content"] == entry["content"]
