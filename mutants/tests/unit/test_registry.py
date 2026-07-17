"""Unit tests: boost_cli/core/registry.py — tap specs, config, clone lifecycle."""
from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from boost_cli.core import config, gitutil, paths, registry
from boost_cli.errors import BoostError


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True)


def _make_repo(path, author="Test Author"):
    path.mkdir(parents=True)
    _git("init", "-q", cwd=path)
    _git("config", "user.email", "t@test", cwd=path)
    _git("config", "user.name", author, cwd=path)
    (path / "a.txt").write_text("one\n")
    _git("add", "-A", cwd=path)
    _git("commit", "-qm", "add a", cwd=path)
    return path


class TestTapProperties:
    def test_safe_name_replaces_slash(self):
        assert registry.Tap("owner/repo", "u").safe_name == "owner__repo"

    def test_safe_name_no_slash_unchanged(self):
        assert registry.Tap("plain", "u").safe_name == "plain"

    def test_path_under_repos_dir(self, sandbox):
        t = registry.Tap("owner/repo", "u")
        assert t.path == paths.repos_dir() / "owner__repo"
        assert str(t.path).startswith(str(sandbox))

    def test_cache_file_under_cache_dir(self, sandbox):
        t = registry.Tap("owner/repo", "u")
        assert t.cache_file == paths.cache_dir() / "owner__repo.json"

    def test_is_cloned(self, sandbox):
        t = registry.Tap("owner/repo", "u")
        assert t.is_cloned is False
        t.path.mkdir(parents=True)
        assert t.is_cloned is True

    def test_curated_defaults_false(self):
        assert registry.Tap("a/b", "u").curated is False


class TestParseSpec:
    def test_owner_repo_becomes_github_url(self):
        assert registry.parse_spec("owner/repo") == (
            "owner/repo", "https://github.com/owner/repo")

    def test_https_url_git_suffix_stripped_from_name(self):
        assert registry.parse_spec("https://github.com/Foo/Bar.git") == (
            "Foo/Bar", "https://github.com/Foo/Bar.git")

    def test_https_url_trailing_slash(self):
        assert registry.parse_spec("https://github.com/foo/bar/") == (
            "foo/bar", "https://github.com/foo/bar")

    def test_git_at_url(self):
        assert registry.parse_spec("git@github.com:foo/bar.git") == (
            "foo/bar", "git@github.com:foo/bar.git")

    def test_ssh_url(self):
        assert registry.parse_spec("ssh://git@github.com/foo/bar") == (
            "foo/bar", "ssh://git@github.com/foo/bar")

    def test_existing_local_dir(self, tmp_path):
        d = tmp_path / "my-tap"
        d.mkdir()
        assert registry.parse_spec(str(d)) == ("my-tap", str(d.resolve()))

    def test_local_dir_trailing_slash(self, tmp_path):
        d = tmp_path / "my-tap"
        d.mkdir()
        assert registry.parse_spec(str(d) + "/") == ("my-tap", str(d.resolve()))

    def test_tilde_expansion_uses_sandbox_home(self, sandbox):
        (sandbox / "hometap").mkdir()
        name, url = registry.parse_spec("~/hometap")
        assert name == "hometap"
        assert url == str((sandbox / "hometap").resolve())

    @pytest.mark.parametrize("bad", ["not a tap spec", "definitely-not-a-real-thing"])
    def test_garbage_raises_with_hint(self, bad):
        with pytest.raises(BoostError) as ei:
            registry.parse_spec(bad)
        assert ei.value.message == "cannot parse tap spec %r" % bad
        assert ei.value.hint == "use owner/repo, a git URL, or a local directory"


class TestListAndGet:
    def _seed(self):
        cfg = config.load()
        cfg["taps"] = [
            {"name": "owner/repo", "url": "https://x", "curated": True},
            {"name": "solo"},
        ]
        config.save(cfg)

    def test_list_taps_from_config(self, sandbox):
        self._seed()
        taps = registry.list_taps()
        assert [(t.name, t.url, t.curated) for t in taps] == [
            ("owner/repo", "https://x", True), ("solo", "", False)]

    def test_list_taps_empty_by_default(self, sandbox):
        assert registry.list_taps() == []

    def test_get_exact_name(self, sandbox):
        self._seed()
        assert registry.get("owner/repo").name == "owner/repo"

    def test_get_safe_name(self, sandbox):
        self._seed()
        assert registry.get("owner__repo").name == "owner/repo"

    def test_get_short_tail(self, sandbox):
        self._seed()
        assert registry.get("repo").name == "owner/repo"

    def test_get_miss_did_you_mean(self, sandbox):
        self._seed()
        with pytest.raises(BoostError) as ei:
            registry.get("owner/rep0")
        assert ei.value.message == "no such tap: owner/rep0"
        assert ei.value.hint == "did you mean owner/repo?"

    def test_get_miss_no_close_match(self, sandbox):
        self._seed()
        with pytest.raises(BoostError) as ei:
            registry.get("zzzzzz")
        assert ei.value.hint == "list taps with `boost taps`"


class TestAddRemove:
    def test_add_local_repo_clones_and_persists(self, sandbox, fixture_tap_src):
        tap = registry.add(str(fixture_tap_src))
        assert tap.name == "fixture-tap"
        assert tap.url == str(fixture_tap_src.resolve())
        assert tap.is_cloned
        assert (tap.path / "skills" / "brainstorming" / "SKILL.md").is_file()
        assert config.get("taps") == [
            {"name": "fixture-tap", "url": str(fixture_tap_src.resolve()),
             "curated": False}]

    def test_add_curated_persisted(self, sandbox, fixture_tap_src):
        registry.add(str(fixture_tap_src), curated=True)
        assert config.get("taps")[0]["curated"] is True
        assert registry.list_taps()[0].curated is True

    def test_add_replaces_stale_clone_dir(self, sandbox, fixture_tap_src):
        stale = paths.repos_dir() / "fixture-tap"
        stale.mkdir(parents=True)
        (stale / "junk.txt").write_text("stale")
        tap = registry.add(str(fixture_tap_src))
        assert not (tap.path / "junk.txt").exists()
        assert (tap.path / "skills" / "brainstorming" / "SKILL.md").is_file()

    def test_add_duplicate_raises(self, sandbox, fixture_tap_src):
        registry.add(str(fixture_tap_src))
        with pytest.raises(BoostError) as ei:
            registry.add(str(fixture_tap_src))
        assert ei.value.message == "tap fixture-tap is already configured"
        assert ei.value.hint == "`boost update fixture-tap` to refresh it"

    def test_remove_deletes_clone_cache_and_config(self, sandbox, fixture_tap_src):
        tap = registry.add(str(fixture_tap_src))
        tap.cache_file.write_text("{}")
        removed = registry.remove("fixture-tap")
        assert removed.name == "fixture-tap"
        assert not tap.path.exists()
        assert not tap.cache_file.exists()
        assert config.get("taps") == []

    def test_remove_unknown_raises(self, sandbox):
        with pytest.raises(BoostError):
            registry.remove("nope")


class TestUpdate:
    def test_update_clones_missing_tap(self, sandbox, tmp_path):
        origin = _make_repo(tmp_path / "pullme")
        tap = registry.add(str(origin))
        shutil.rmtree(tap.path)
        assert registry.update("pullme") == {"pullme": "cloned"}
        assert tap.is_cloned

    def test_update_already_up_to_date(self, sandbox, tmp_path):
        origin = _make_repo(tmp_path / "pullme")
        registry.add(str(origin))
        assert registry.update() == {"pullme": "already up to date"}

    def test_update_pulls_new_commit(self, sandbox, tmp_path):
        origin = _make_repo(tmp_path / "pullme")
        tap = registry.add(str(origin))
        before = gitutil.head_commit(tap.path)
        (origin / "b.txt").write_text("two\n")
        _git("add", "-A", cwd=origin)
        _git("commit", "-qm", "add b", cwd=origin)
        summary = registry.update("pullme")["pullme"]
        after = gitutil.head_commit(tap.path)
        assert re.fullmatch(r"[0-9a-f]{7} → [0-9a-f]{7}", summary)
        assert summary == "%s → %s" % (before[:7], after[:7])
        assert after == gitutil.head_commit(origin)

    def test_update_unknown_tap_raises(self, sandbox):
        with pytest.raises(BoostError):
            registry.update("nope")
