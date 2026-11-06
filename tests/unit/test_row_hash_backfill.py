# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Rules and workflows installed before their rows carried a hash.

Between 2026-07-20 and 2026-08-04 a rule's or workflow's lock rows were
``{agent, mode|slot, path}`` with no ``sha256``. `boost verify` failed them as
"missing lock fields: materialization sha256" through every update, sync and
heal, and only a reinstall cleared it. `sync` (and `heal`, through the same
``sync_apply``) now records the hash of each file that still holds what boost
writes for the installed source, and names the rest.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from boost_cli.core import catalog, lockfile, paths, registry, rules, store


@pytest.fixture()
def tap(sandbox, fixture_tap_src, tmp_path):
    src = tmp_path / "fixture-tap"
    shutil.copytree(fixture_tap_src, src, symlinks=True)
    t = registry.add(str(src))
    catalog.rebuild_tap(t)
    return t


def _entry(tap, kind, name, rel, text):
    src = tap.path / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(text, encoding="utf-8")
    catalog.rebuild_tap(tap)
    return {"name": name, "kind": kind, "tap": tap.name, "version": "1.0.0",
            "rel_dir": str(src.parent.relative_to(tap.path)), "skill_md": rel,
            "description": "d", "curated": False, "meta": {}}


@pytest.fixture()
def items(tap):
    """A rule and a workflow, installed, with their rows' digests."""
    store.install(_entry(tap, "rule", "house", "rules/house.mdc",
                         "---\nname: house\n---\n\nUse tabs.\n"))
    store.install(_entry(tap, "workflow", "ship-it", "commands/ship-it.md",
                         "---\nname: ship-it\ndescription: release\n---\n\n"
                         "Ship.\n"))
    return {(s, n): {m["path"]: m["sha256"]
                     for m in lockfile.read()[s][n]["materializations"]
                     if not lockfile.is_skill_copy(m)}
            for s, n in (("rules", "house"), ("workflows", "ship-it"))}


def _age(names=(("rules", "house"), ("workflows", "ship-it"))):
    """Rewrite rows to the old shape, as mk_oldkinds.py did, keeping an
    unknown key on the entry so the backfill is seen to leave it alone."""
    lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
    for section, name in names:
        e = lock[section][name]
        for k in ("scope", "only_agents", "base", "tap_url"):
            e.pop(k, None)
        e["someday"] = "kept"
        for m in e["materializations"]:
            if lockfile.is_skill_copy(m):  # newer than the old shape
                shutil.rmtree(Path(m["path"]).parent)
        e["materializations"] = [
            {k: m[k] for k in ("agent", "mode", "slot", "path") if k in m}
            for m in e["materializations"] if not lockfile.is_skill_copy(m)]
    paths.lockfile_path().write_text(json.dumps(lock), encoding="utf-8")


def _rows(section, name):
    return {m["path"]: m.get("sha256")
            for m in lockfile.read()[section][name]["materializations"]}


def _files(n):
    return "file" if n == 1 else "%d files" % n


def test_sync_records_the_hash_of_files_boost_wrote(boost, items):
    _age()
    r = boost("verify", expect=1)
    assert r.out.count("unlocked  rule · missing lock fields: "
                       "materialization sha256 · `boost sync` records it, "
                       "or `boost reinstall house` if a file was edited") == 1
    assert r.out.count("unlocked  workflow · missing lock fields: "
                       "materialization sha256 · `boost sync` records it, "
                       "or `boost reinstall ship-it` if a file was edited") == 1
    assert "2 of 2 items failed verification" in r.err + r.out
    nr, nw = len(items[("rules", "house")]), len(items[("workflows", "ship-it")])
    assert nr >= 2  # a CLAUDE.md block and at least one rule file

    before = paths.lockfile_path().read_bytes()
    dry = boost("heal", "--dry-run")
    assert "would record the hash of rule house's %s" % _files(nr) in dry.out
    assert ("would record the hash of workflow ship-it's %s" % _files(nw)
            in dry.out)
    assert paths.lockfile_path().read_bytes() == before
    diff = boost("sync", "--diff")
    assert "would record the hash of rule house's %s" % _files(nr) in diff.out
    assert "everything in sync" not in diff.out
    assert paths.lockfile_path().read_bytes() == before

    r = boost("sync")
    assert "recorded the hash of rule house's %s" % _files(nr) in r.out
    assert "recorded the hash of workflow ship-it's %s" % _files(nw) in r.out
    assert "everything in sync" not in r.out
    # The digest each install recorded, not merely some digest.
    assert _rows("rules", "house") == items[("rules", "house")]
    assert _rows("workflows", "ship-it") == items[("workflows", "ship-it")]
    assert lockfile.read()["rules"]["house"]["someday"] == "kept"
    r = boost("verify")
    assert "lock file integrity OK" in r.out
    assert "everything in sync" in boost("sync").out
    assert store.backfill_row_hashes() == []


def test_heal_records_them_too(boost, items):
    _age()
    r = boost("heal")
    assert "recorded the hash of rule house's" in r.out
    boost("verify")


def test_an_edited_file_is_not_blessed(boost, items):
    _age((("rules", "house"),))
    block_paths = [p for p in items[("rules", "house")]
                   if Path(p).name not in ("CLAUDE.md",)]
    edited = Path(block_paths[0])
    edited.write_text(edited.read_text(encoding="utf-8") + "mine\n",
                      encoding="utf-8")
    n = len(items[("rules", "house")])
    # A file it cannot vouch for is left unrepaired, so sync fails as heal does.
    r = boost("sync", expect=1)
    out = r.out + r.err
    assert "recorded the hash of rule house's %s" % _files(n - 1) in out
    assert ("rule house has a file with no recorded hash that boost cannot "
            "vouch for — `boost reinstall house` rewrites and records it"
            ) in " ".join(out.split())
    rows = _rows("rules", "house")
    assert rows[str(edited)] is None
    assert all(rows[p] == items[("rules", "house")][p]
               for p in rows if p != str(edited))
    # verify still fails it, and names the reinstall sync just pointed at
    # rather than sending the user back round to sync.
    assert "`boost reinstall house` if a file was edited" in " ".join(
        boost("verify", expect=1).out.split())
    # heal says the same thing, and does not call it healed.
    assert "boost reinstall house" in boost("heal", expect=1).out


def test_a_claude_block_is_compared_as_read_back(boost, items):
    claude = [p for p in items[("rules", "house")]
              if Path(p).name == "CLAUDE.md"]
    assert claude, "claude-code is a default agent; its rule is a block"
    text = Path(claude[0]).read_text(encoding="utf-8")
    assert rules.read_block(text, "house") is not None
    _age((("rules", "house"),))
    boost("sync")
    assert _rows("rules", "house")[claude[0]] == items[("rules", "house")][
        claude[0]]


def test_a_source_that_is_gone_names_reinstall(boost, items, tap):
    _age((("workflows", "ship-it"),))
    lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
    lock["workflows"]["ship-it"]["sha256"] = "0" * 64  # no copy matches it
    paths.lockfile_path().write_text(json.dumps(lock), encoding="utf-8")
    nw = len(items[("workflows", "ship-it")])
    lines = store.backfill_row_hashes()
    assert lines == [
        "workflow ship-it has %s with no recorded hash that boost cannot "
        "vouch for — `boost reinstall ship-it` rewrites and records %s"
        % ("a file" if nw == 1 else "%d files" % nw,
           "it" if nw == 1 else "them")]
    assert all(store.is_unrepaired(line) for line in lines)
    assert set(_rows("workflows", "ship-it").values()) == {None}


def test_quarantined_items_are_left_alone(boost, items):
    _age((("rules", "house"),))
    lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
    lock["rules"]["house"]["quarantined"] = True
    paths.lockfile_path().write_text(json.dumps(lock), encoding="utf-8")
    assert store.backfill_row_hashes() == []


def _set(section, name, **fields):
    lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
    lock[section][name].update(fields)
    paths.lockfile_path().write_text(json.dumps(lock), encoding="utf-8")


def test_a_stranded_local_install_is_left_alone(boost, items, tmp_path):
    _age((("rules", "house"),))
    _set("rules", "house", scope="project", base=str(tmp_path / "gone"))
    assert store.backfill_row_hashes() == []


def test_a_refused_row_is_neither_stamped_nor_named(boost, items):
    _age((("rules", "house"),))
    lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
    rows = lock["rules"]["house"]["materializations"]
    rows[0]["unwritable"] = True
    paths.lockfile_path().write_text(json.dumps(lock), encoding="utf-8")
    n = len(items[("rules", "house")])
    assert store.backfill_row_hashes() == [
        "recorded the hash of rule house's %s" % _files(n - 1)]
    assert _rows("rules", "house")[rows[0]["path"]] is None


def test_a_skill_copy_row_without_a_hash_is_not_counted(boost, items):
    _age((("workflows", "ship-it"),))
    lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
    rows = lock["workflows"]["ship-it"]["materializations"]
    rows.append({"agent": None, "slot": "skill",
                 "path": str(store.skill_store_dir("ship-it") / "SKILL.md")})
    paths.lockfile_path().write_text(json.dumps(lock), encoding="utf-8")
    n = len(items[("workflows", "ship-it")])
    assert store.backfill_row_hashes(dry=True) == [
        "would record the hash of workflow ship-it's %s" % _files(n)]


def test_a_missing_file_is_left_to_rematerialize(boost, items):
    _age((("rules", "house"),))
    gone = next(p for p in items[("rules", "house")]
                if Path(p).name != "CLAUDE.md")
    Path(gone).unlink()
    n = len(items[("rules", "house")])
    assert store.backfill_row_hashes(dry=True) == [
        "would record the hash of rule house's %s" % _files(n - 1)]


def test_a_row_for_a_disabled_agent_is_left_alone(boost, items):
    from boost_cli.core import config
    _age((("rules", "house"),))
    cfg = config.load()
    for agent in cfg["agents"]:
        cfg["agents"][agent]["enabled"] = False
    config.save(cfg)
    assert store.backfill_row_hashes() == []


@pytest.mark.parametrize("raw_version", [4, "3"])
def test_a_lock_sync_refuses_is_not_stamped(boost, items, raw_version):
    """A newer or unknown schema is `boost replay`'s: stamping a row into it
    went through `lockfile.write`, which restamped the lock as v3 under the
    line saying sync records nothing."""
    _age()
    lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
    lock["version"] = raw_version
    paths.lockfile_path().write_text(json.dumps(lock), encoding="utf-8")
    before = paths.lockfile_path().read_bytes()
    assert store.backfill_row_hashes(dry=True) == []
    assert store.backfill_row_hashes() == []
    diff = boost("sync", "--diff")
    assert "would record the hash" not in diff.out
    r = boost("sync", expect=1)
    assert "recorded the hash" not in r.out
    assert paths.lockfile_path().read_bytes() == before


def test_an_older_lock_is_migrated_and_backfilled_in_one_sync(boost, items):
    _age()
    lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
    del lock["version"]
    paths.lockfile_path().write_text(json.dumps(lock), encoding="utf-8")
    # The preview of an older lock still names the rows sync will record.
    assert store.backfill_row_hashes(dry=True) == [
        "would record the hash of rule house's %s"
        % _files(len(items[("rules", "house")])),
        "would record the hash of workflow ship-it's %s"
        % _files(len(items[("workflows", "ship-it")]))]
    boost("sync")
    assert lockfile.check() == (True, None, 3)
    assert _rows("rules", "house") == items[("rules", "house")]
    assert _rows("workflows", "ship-it") == items[("workflows", "ship-it")]
