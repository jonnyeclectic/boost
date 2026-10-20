# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost update` and `boost heal` rescan only the taps that need it.

Both used to run `catalog.rebuild_tap` over every tap on every run, so an
"everything up to date" / "nothing to heal" cost a full scan of the catalogue,
and the rewrite bumped each cache's mtime so the next search rebuilt the BM25
index too (`rag.stale` is stat-only). `update` also paid one git subprocess and
one whole-catalogue `find` per installed skill.
"""
from __future__ import annotations

import json
import subprocess

import pytest

from boost_cli.core import catalog, gitutil, registry


@pytest.fixture()
def scans(monkeypatch):
    calls: list[str] = []
    real = catalog.scan_dir

    def counting(path, tapname, *a, **kw):
        calls.append(tapname)
        return real(path, tapname, *a, **kw)

    monkeypatch.setattr(catalog, "scan_dir", counting)
    return calls


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture()
def own_tap(boost, tmp_path):
    """A tap whose upstream this test may move (the shared fixture is not)."""
    root = tmp_path / "own-tap"
    _add_skill(root, "alpha")
    (root / "rules").mkdir()
    (root / "rules" / "house.mdc").write_text(
        "---\nname: house\nversion: 1.0.0\ndescription: House style\n---\n"
        "\n## House\n\nUse tabs.\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "own@boost.test")
    _git(root, "config", "user.name", "Own Tap")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "alpha")
    boost("tap", root)
    return root


def _add_skill(root, name):
    d = root / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: %s\ndescription: The %s skill\nversion: 1.0.0\n---\n\n"
        "# %s\n" % (name, name, name), encoding="utf-8")


def _cache(tapname):
    tap = registry.get(tapname)
    return tap, json.loads(tap.cache_file.read_text(encoding="utf-8"))


def _set_format(tapname, fmt):
    tap, data = _cache(tapname)
    data["format"] = fmt
    tap.cache_file.write_text(json.dumps(data), encoding="utf-8")


class TestUpdate:
    def test_an_unchanged_tap_is_not_rescanned_or_rewritten(self, boost,
                                                            tapped, scans):
        tap = registry.get("fixture-tap")
        before = tap.cache_file.stat().st_mtime_ns
        r = boost("update")
        assert "fixture-tap: already up to date" in r.out
        assert "everything up to date" in r.out
        assert scans == []
        assert tap.cache_file.stat().st_mtime_ns == before

    def test_taps_only_leaves_an_unchanged_cache_alone(self, boost, tapped,
                                                       scans):
        tap = registry.get("fixture-tap")
        before = tap.cache_file.stat().st_mtime_ns
        boost("update", "--taps-only")
        assert scans == []
        assert tap.cache_file.stat().st_mtime_ns == before

    def test_a_moved_tap_is_rescanned(self, boost, own_tap, scans):
        _add_skill(own_tap, "beta")
        _git(own_tap, "add", "-A")
        _git(own_tap, "commit", "-qm", "beta")
        r = boost("update", "--taps-only")
        assert "own-tap: " in r.out and "→" in r.out
        assert scans == ["own-tap"]
        tap, data = _cache("own-tap")
        assert data["commit"] == gitutil.head_commit(tap.path)
        assert sorted(e["name"] for e in data["skills"]) == ["alpha", "beta",
                                                          "house"]

    def test_an_old_format_cache_is_still_backfilled(self, boost, tapped,
                                                     scans):
        _set_format("fixture-tap", catalog.CACHE_FORMAT - 1)
        boost("update", "--taps-only")
        assert scans == ["fixture-tap"]
        assert _cache("fixture-tap")[1]["format"] == catalog.CACHE_FORMAT

    def test_a_cache_from_another_commit_is_rescanned(self, boost, tapped,
                                                      scans):
        tap, data = _cache("fixture-tap")
        data["commit"] = "0" * 40
        tap.cache_file.write_text(json.dumps(data), encoding="utf-8")
        boost("update", "--taps-only")
        assert scans == ["fixture-tap"]
        assert _cache("fixture-tap")[1]["commit"] == gitutil.head_commit(
            tap.path)

    def test_per_skill_cost_does_not_grow_with_installed_skills(
            self, boost, tapped, monkeypatch):
        # One HEAD per tap and one catalogue read for the whole run: each
        # used to be paid again for every installed skill.
        def measure():
            heads: list[str] = []
            reads: list[int] = []
            real_head, real_all = gitutil.head_commit, catalog.all_entries
            monkeypatch.setattr(gitutil, "head_commit",
                                lambda p: heads.append(str(p)) or real_head(p))
            monkeypatch.setattr(catalog, "all_entries",
                                lambda: reads.append(1) or real_all())
            boost("update")
            monkeypatch.setattr(gitutil, "head_commit", real_head)
            monkeypatch.setattr(catalog, "all_entries", real_all)
            return len(heads), len(reads)

        boost("install", "brainstorming")
        one = measure()
        boost("install", "commit-messages")
        boost("install", "tdd-workflow")
        three = measure()
        assert three == one

    def test_an_installed_skill_still_resolves_and_updates(self, boost,
                                                           own_tap):
        boost("install", "alpha")
        skill = own_tap / "skills" / "alpha" / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8")
                         .replace("1.0.0", "1.1.0"), encoding="utf-8")
        _git(own_tap, "commit", "-qam", "bump")
        r = boost("update")
        assert "alpha" in r.out and "1.1.0" in r.out
        assert "everything up to date" not in r.out


    def test_an_installed_rule_still_resolves_and_updates(self, boost,
                                                          own_tap, scans):
        boost("install", "house")
        rule = own_tap / "rules" / "house.mdc"
        rule.write_text(rule.read_text(encoding="utf-8")
                        .replace("1.0.0", "1.1.0"), encoding="utf-8")
        _git(own_tap, "commit", "-qam", "bump rule")
        scans.clear()
        r = boost("update")
        assert "house" in r.out and "1.1.0" in r.out
        assert "everything up to date" not in r.out
        assert scans == ["own-tap"]


class TestHeal:
    def test_a_healthy_install_rescans_nothing(self, boost, tapped, scans):
        boost("heal")                    # creates the agent dirs a fresh HOME lacks
        assert scans == []
        tap = registry.get("fixture-tap")
        before = tap.cache_file.stat().st_mtime_ns
        assert "nothing to heal" in boost("heal").out
        assert scans == []
        assert tap.cache_file.stat().st_mtime_ns == before

    def test_a_deleted_cache_is_rebuilt(self, boost, tapped, scans):
        registry.get("fixture-tap").cache_file.unlink()
        r = boost("heal")
        assert "rebuilt catalog cache for fixture-tap" in r.out
        assert scans == ["fixture-tap"]

    def test_an_old_format_cache_is_rebuilt(self, boost, tapped, scans):
        _set_format("fixture-tap", catalog.CACHE_FORMAT - 1)
        boost("heal")
        assert scans == ["fixture-tap"]
        assert _cache("fixture-tap")[1]["format"] == catalog.CACHE_FORMAT
        boost("heal")
        assert scans == ["fixture-tap"]          # and then left alone
