# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a tap's name decides its identity case-blind, and untap only
removes what it owns.

Three defects, one surface. `boost tap Foo` after `boost tap foo` added a
second config row whose clone and cache were the first one's on APFS/NTFS, so
untapping either deleted the other's; `boost untap` crashed with KeyError on a
config row without a name; and `boost tap SPEC --at SHA` on a tapped registry
hinted at `boost update`, which cannot move a tap to a chosen commit.
"""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from boost_cli.commands import taps as taps_cmd
from boost_cli.core import config, gitutil, paths, registry, util
from boost_cli.errors import BoostError

SHA = "a" * 40


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True)


def _repo(path):
    (path / "skills" / "a").mkdir(parents=True)
    _git("init", "-q", cwd=path)
    _git("config", "user.email", "t@test", cwd=path)
    _git("config", "user.name", "T", cwd=path)
    (path / "skills" / "a" / "SKILL.md").write_text(
        "---\nname: a\ndescription: A skill\n---\nx\n", encoding="utf-8")
    _git("add", "-A", cwd=path)
    _git("commit", "-qm", "add a", cwd=path)
    return path


def _rows(*rows):
    cfg = config.load()
    cfg["taps"] = list(rows)
    config.save(cfg)


def _no_clone(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("must refuse before cloning")
    monkeypatch.setattr(gitutil, "clone_shallow", boom)


def _fake_clone(monkeypatch):
    """Record each spec `add_many` would clone, and clone nothing."""
    seen: list[str] = []

    def fake(spec, curated, pin):
        seen.append(spec)
        name, url = registry.parse_spec(spec)
        return {"spec": spec, "name": name, "url": url, "ok": True,
                "tap": registry.Tap(name=name, url=url)}
    monkeypatch.setattr(registry, "_clone_one", fake)
    return seen


def _gh(name):
    return {"name": name, "url": "https://github.com/" + name,
            "curated": False}


def _folding_dir(tmp_path, name):
    """`tmp_path/name`, created; skip unless `tmp_path/NAME` is the same dir."""
    path = tmp_path / name
    path.mkdir()
    if not (tmp_path / name.upper()).exists():
        pytest.skip("case-sensitive filesystem")
    return path


class TestNameKey:
    def test_folds_case(self):
        assert registry.name_key("Obra/SuperPowers") == "obra/superpowers"

    def test_casefold_not_lower(self):
        # casefold() folds the German sharp s; lower() leaves it.
        assert registry.name_key("STRASSE") == registry.name_key("straße")


class TestAddRefusesACaseVariant:
    def test_github_variant_is_already_configured(self, sandbox, monkeypatch):
        _rows(_gh("idcase/repo-one"))
        _no_clone(monkeypatch)
        with pytest.raises(BoostError) as ei:
            registry.add("IdCase/Repo-One")
        assert ei.value.message == "tap idcase/repo-one is already configured"
        assert ei.value.hint == "`boost update idcase/repo-one` to refresh it"
        assert [t["name"] for t in config.get("taps")] == ["idcase/repo-one"]

    def test_local_variant_of_another_repo_is_taken(self, sandbox, tmp_path):
        first = _repo(tmp_path / "a" / "idcase-local")
        other = _repo(tmp_path / "b" / "IDCASE-LOCAL")
        tap = registry.add(str(first))
        with pytest.raises(BoostError) as ei:
            registry.add(str(other))
        assert ei.value.message == (
            "tap name idcase-local is already used by %s"
            % str(first.resolve()))
        assert ei.value.hint == (
            "`boost untap idcase-local`, then `boost tap %s` to tap it in its "
            "place" % util.shell_arg(str(other)))
        assert [t["name"] for t in config.get("taps")] == ["idcase-local"]
        assert (tap.path / "skills" / "a" / "SKILL.md").is_file()

    def test_local_case_variant_of_one_dir_is_already_configured(
            self, sandbox, tmp_path):
        # The reviewer's repro: `boost tap $H/fix` then `boost tap $H/FIX` on
        # APFS is one directory, so it is "already configured", not "taken".
        first = _repo(_folding_dir(tmp_path, "idcase-same"))
        registry.add(str(first))
        with pytest.raises(BoostError) as ei:
            registry.add(str(tmp_path / "IDCASE-SAME"))
        assert ei.value.message == "tap idcase-same is already configured"
        assert [t["name"] for t in config.get("taps")] == ["idcase-same"]

    def test_exact_name_still_refused(self, sandbox, monkeypatch):
        _rows(_gh("idcase/exact"))
        _no_clone(monkeypatch)
        with pytest.raises(BoostError, match="already configured"):
            registry.add("idcase/exact")


class TestAddManyRefusesACaseVariant:
    def test_variant_of_a_configured_tap_is_skipped(self, sandbox, monkeypatch):
        _rows(_gh("idmany/repo"))
        _no_clone(monkeypatch)
        [res] = registry.add_many(["IDMANY/Repo"])
        assert res["ok"] is False
        assert res["skipped"] is True
        assert res["error"] == "already tapped"
        assert len(config.get("taps")) == 1

    def test_variant_of_another_source_is_taken(self, sandbox, monkeypatch,
                                                tmp_path):
        _rows({"name": "idmany-src", "url": "/srv/a/idmany-src",
               "curated": False})
        _no_clone(monkeypatch)
        other = _repo(tmp_path / "IDMANY-SRC")
        [res] = registry.add_many([str(other)])
        assert res["ok"] is False
        assert "skipped" not in res
        assert res["error"] == ("tap name idmany-src is already used by "
                                "/srv/a/idmany-src")

    def test_two_variants_in_one_batch_clone_once(self, sandbox, monkeypatch):
        seen = _fake_clone(monkeypatch)
        res = registry.add_many(["idbatch/repo", "IDBATCH/REPO"])
        assert seen == ["idbatch/repo"]
        assert [r.get("skipped", False) for r in res] == [False, True]
        assert [t["name"] for t in config.get("taps")] == ["idbatch/repo"]

    def test_two_variants_of_different_sources_conflict(self, sandbox,
                                                        monkeypatch, tmp_path):
        seen = _fake_clone(monkeypatch)
        a = _repo(tmp_path / "x" / "idbatch-two")
        b = _repo(tmp_path / "y" / "IDBATCH-TWO")
        res = registry.add_many([str(a), str(b)])
        assert seen == [str(a)]
        assert res[1]["ok"] is False
        assert res[1]["error"].startswith(
            "two specs in this batch both name IDBATCH-TWO")


class TestSameSourceLocal:
    def test_two_spellings_of_one_dir_match(self, tmp_path):
        d = _folding_dir(tmp_path, "idsrc-one")
        assert registry.same_source(str(d), str(tmp_path / "IDSRC-ONE"))

    @pytest.mark.skipif(sys.platform == "win32", reason="symlinks")
    def test_symlink_to_one_dir_matches(self, tmp_path):
        (tmp_path / "real").mkdir()
        (tmp_path / "alias").symlink_to(tmp_path / "real")
        assert registry.same_source(str(tmp_path / "alias"),
                                    str(tmp_path / "real"))

    def test_two_dirs_do_not_match(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        assert not registry.same_source(str(tmp_path / "a"),
                                        str(tmp_path / "b"))

    def test_vanished_source_does_not_match_or_raise(self, tmp_path):
        (tmp_path / "a").mkdir()
        assert not registry.same_source(str(tmp_path / "a"),
                                        str(tmp_path / "gone"))

    def test_remote_is_never_asked_of_the_filesystem(self, tmp_path,
                                                     monkeypatch):
        def boom(*_a):
            raise AssertionError("samefile on a remote URL")
        monkeypatch.setattr(registry.os.path, "samefile", boom)
        (tmp_path / "a").mkdir()
        local = str(tmp_path / "a")
        assert not registry.same_source(local, "https://example.com/a")
        assert not registry.same_source("https://example.com/a", local)
        assert not registry.same_source(local, "git@example.com:o/a")
        assert not registry.same_source("git@example.com:o/a", local)


class TestTapCommandSkip:
    def test_local_case_variant_of_one_dir_is_skipped(self, sandbox, tmp_path,
                                                      capsys):
        first = _repo(_folding_dir(tmp_path, "idskip-same"))
        registry.add(str(first))
        capsys.readouterr()
        assert taps_cmd.cmd_tap([str(tmp_path / "IDSKIP-SAME")]) == 0
        assert "idskip-same already tapped" in capsys.readouterr().out
        assert [t["name"] for t in config.get("taps")] == ["idskip-same"]

    def test_add_many_skips_a_local_case_variant(self, sandbox, tmp_path):
        first = _repo(_folding_dir(tmp_path, "idmany-same"))
        registry.add(str(first))
        [res] = registry.add_many([str(tmp_path / "IDMANY-SAME")])
        assert res["ok"] is False
        assert res["skipped"] is True
        assert res["error"] == "already tapped"

    def test_case_variant_prints_the_configured_name(self, sandbox, capsys):
        _rows(_gh("idskip/repo"))
        assert taps_cmd._skip_if_already_tapped("IDSKIP/Repo") is True
        assert "idskip/repo already tapped" in capsys.readouterr().out

    def test_other_name_is_not_skipped(self, sandbox):
        _rows(_gh("idskip/repo"))
        assert taps_cmd._skip_if_already_tapped("idskip/other") is False


class TestGetIsCaseBlindLast:
    def test_variant_finds_the_tap(self, sandbox):
        _rows(_gh("idget/repo"))
        assert registry.get("IDGET/Repo").name == "idget/repo"

    def test_exact_spelling_wins(self, sandbox):
        _rows(_gh("idget/dup"), _gh("IDGET/DUP"))
        assert registry.get("IDGET/DUP").name == "IDGET/DUP"
        assert registry.get("idget/dup").name == "idget/dup"

    def test_two_folded_hits_are_ambiguous(self, sandbox):
        _rows(_gh("idget/amb"), _gh("IDGET/AMB"))
        with pytest.raises(BoostError, match="ambiguous"):
            registry.get("Idget/Amb")


class TestShared:
    def test_same_spelling_is_shared_even_when_absent(self, tmp_path):
        p = tmp_path / "nope"
        assert registry._shared(p, [p]) is True

    def test_distinct_dirs_are_not_shared(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        assert registry._shared(tmp_path / "a", [tmp_path / "b"]) is False

    def test_missing_other_is_skipped_not_raised(self, tmp_path):
        (tmp_path / "a").mkdir()
        assert registry._shared(tmp_path / "a",
                                [tmp_path / "gone", tmp_path / "a"]) is True

    def test_nothing_else_is_not_shared(self, tmp_path):
        assert registry._shared(tmp_path, []) is False

    @pytest.mark.skipif(sys.platform == "win32", reason="symlinks")
    def test_alias_of_one_dir_is_shared(self, tmp_path):
        (tmp_path / "real").mkdir()
        (tmp_path / "alias").symlink_to(tmp_path / "real")
        assert registry._shared(tmp_path / "alias", [tmp_path / "real"]) is True


class TestRemoveKeepsASharedClone:
    def test_clone_and_cache_another_tap_uses_survive(self, sandbox,
                                                       monkeypatch):
        # Fold the on-disk name the way APFS and NTFS do, so this holds on a
        # case-sensitive runner too: two legacy rows, one clone, one cache.
        monkeypatch.setattr(registry.Tap, "safe_name", property(
            lambda self: self.name.casefold().replace("/", "__")))
        paths.ensure_dirs()
        _rows(_gh("idrm/keep"), _gh("IDRM/Keep"))
        keep = registry.Tap("idrm/keep", "")
        keep.path.mkdir(parents=True)
        (keep.path / "f").write_text("x", encoding="utf-8")
        keep.cache_file.write_text("[]", encoding="utf-8")
        registry.remove("IDRM/Keep")
        assert (keep.path / "f").is_file()
        assert keep.cache_file.is_file()
        assert [t.name for t in registry.list_taps()] == ["idrm/keep"]

    def test_unshared_clone_and_cache_are_deleted(self, sandbox):
        paths.ensure_dirs()
        _rows(_gh("idrm/keep2"), _gh("idrm/gone2"))
        keep, gone = registry.Tap("idrm/keep2", ""), registry.Tap("idrm/gone2", "")
        for t in (keep, gone):
            t.path.mkdir(parents=True)
            t.cache_file.write_text("[]", encoding="utf-8")
        registry.remove("idrm/gone2")
        assert not gone.path.exists()
        assert not gone.cache_file.exists()
        assert keep.path.is_dir()
        assert keep.cache_file.is_file()

    def test_real_case_folding_filesystem(self, sandbox):
        paths.ensure_dirs()
        probe = paths.repos_dir() / "idrm-probe"
        probe.mkdir()
        folds = (paths.repos_dir() / "IDRM-PROBE").exists()
        probe.rmdir()
        if not folds:
            pytest.skip("case-sensitive filesystem")
        _rows({"name": "idrm-fold", "url": "/x/idrm-fold"},
              {"name": "IDRM-FOLD", "url": "/x/IDRM-FOLD"})
        lower = registry.Tap("idrm-fold", "")
        lower.path.mkdir()
        lower.cache_file.write_text("[]", encoding="utf-8")
        registry.remove("IDRM-FOLD")
        assert lower.path.is_dir()
        assert lower.cache_file.is_file()


class TestRemoveToleratesMalformedRows:
    def test_nameless_and_non_dict_rows_are_kept(self, sandbox):
        nameless = {"url": "https://github.com/x/y"}
        _rows(nameless, "junk", 7, _gh("idbad/real"))
        tap = registry.remove("idbad/real")
        assert tap.name == "idbad/real"
        assert config.load()["taps"] == [nameless, "junk", 7]

    def test_only_the_named_row_goes(self, sandbox):
        _rows(_gh("idbad/a"), {"name": None}, _gh("idbad/b"))
        registry.remove("idbad/a")
        assert config.load()["taps"] == [{"name": None}, _gh("idbad/b")]

    def test_config_on_disk_is_the_one_written(self, sandbox):
        _rows({"url": "u"}, _gh("idbad/c"))
        registry.remove("idbad/c")
        on_disk = json.loads(paths.config_path().read_text(encoding="utf-8"))
        assert on_disk["taps"] == [{"url": "u"}]


class TestAtHintOnATappedRegistry:
    def test_hint_names_untap_then_tap_at(self, sandbox, monkeypatch):
        _rows(_gh("idat/repo"))
        _no_clone(monkeypatch)
        with pytest.raises(BoostError) as ei:
            registry.add("idat/repo", at=SHA)
        assert ei.value.message == "tap idat/repo is already configured"
        assert ei.value.hint == (
            "`boost untap idat/repo`, then `boost tap idat/repo --at %s` to "
            "move it to that commit" % SHA)
        assert "boost update" not in ei.value.hint

    def test_hint_keeps_the_spec_the_user_typed(self, sandbox, monkeypatch):
        _rows(_gh("idat/spec"))
        _no_clone(monkeypatch)
        with pytest.raises(BoostError) as ei:
            registry.add("https://github.com/IDAT/Spec.git", at=SHA)
        assert ei.value.hint == (
            "`boost untap idat/spec`, then `boost tap "
            "https://github.com/IDAT/Spec.git --at %s` to move it to that "
            "commit" % SHA)

    def test_no_at_keeps_the_update_hint(self, sandbox, monkeypatch):
        _rows(_gh("idat/plain"))
        _no_clone(monkeypatch)
        with pytest.raises(BoostError) as ei:
            registry.add("idat/plain", at=None)
        assert ei.value.hint == "`boost update idat/plain` to refresh it"
