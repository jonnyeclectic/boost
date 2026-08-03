"""Unit tests: boost_cli/core/registry.py — tap specs, config, clone lifecycle."""
from __future__ import annotations

import re
import subprocess

import pytest

from boost_cli.core import config, gitutil, paths, registry, util
from boost_cli.errors import BoostError


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True)


def _make_repo(path, author="Test Author"):
    path.mkdir(parents=True)
    _git("init", "-q", cwd=path)
    _git("config", "user.email", "t@test", cwd=path)
    _git("config", "user.name", author, cwd=path)
    (path / "a.txt").write_text("one\n", encoding="utf-8")
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

    def test_list_taps_survives_null_taps_key(self, sandbox):
        """`"taps": null` must read as "no taps", not crash every command.

        config.get returns its default only when the key is ABSENT, so an
        explicit null reached the comprehension and raised TypeError
        ('NoneType' object is not iterable) — found by pyright, not mypy.
        """
        cfg = config.load()
        cfg["taps"] = None
        config.save(cfg)
        assert registry.list_taps() == []

    @pytest.mark.parametrize("bogus", ["not-a-list", 42, {"name": "x"}])
    def test_list_taps_ignores_non_list_taps(self, sandbox, bogus):
        cfg = config.load()
        cfg["taps"] = bogus
        config.save(cfg)
        assert registry.list_taps() == []

    def test_list_taps_skips_malformed_entries(self, sandbox):
        """A junk element must not take down the whole listing."""
        cfg = config.load()
        cfg["taps"] = [{"name": "good", "url": "https://x"}, "junk", {}, None]
        config.save(cfg)
        assert [t.name for t in registry.list_taps()] == ["good"]

    def test_get_exact_name(self, sandbox):
        self._seed()
        assert registry.get("owner/repo").name == "owner/repo"

    def test_get_safe_name(self, sandbox):
        self._seed()
        assert registry.get("owner__repo").name == "owner/repo"

    def test_get_short_tail(self, sandbox):
        self._seed()
        assert registry.get("repo").name == "owner/repo"

    # ── ambiguity: a short name that matches two taps must not be guessed.
    # `boost untap skills` with angular/skills and microsoft/skills both tapped
    # used to act on whichever came first in config.json.

    def _seed_two(self):
        cfg = config.load()
        cfg["taps"] = [{"name": "angular/skills", "url": "https://x/a"},
                       {"name": "microsoft/skills", "url": "https://x/m"}]
        config.save(cfg)

    def test_ambiguous_tail_refuses(self, sandbox):
        self._seed_two()
        with pytest.raises(BoostError) as ei:
            registry.get("skills")
        assert "ambiguous" in ei.value.message
        # both candidates named, so the user can pick
        assert "angular/skills" in ei.value.message
        assert "microsoft/skills" in ei.value.message
        assert ei.value.hint == "use the full owner/repo name"

    def test_qualified_name_still_resolves_when_tail_is_ambiguous(self, sandbox):
        self._seed_two()
        assert registry.get("angular/skills").name == "angular/skills"
        assert registry.get("microsoft/skills").name == "microsoft/skills"

    def test_safe_name_still_resolves_when_tail_is_ambiguous(self, sandbox):
        self._seed_two()
        assert registry.get("angular__skills").name == "angular/skills"

    def test_exact_name_beats_another_taps_tail(self, sandbox):
        # A tap literally named "skills" must win over owner/skills' tail.
        cfg = config.load()
        cfg["taps"] = [{"name": "angular/skills", "url": "https://x/a"},
                       {"name": "skills", "url": "https://x/s"}]
        config.save(cfg)
        assert registry.get("skills").name == "skills"

    def test_unambiguous_tail_still_works(self, sandbox):
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
        (stale / "junk.txt").write_text("stale", encoding="utf-8")
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
        tap.cache_file.write_text("{}", encoding="utf-8")
        removed = registry.remove("fixture-tap")
        assert removed.name == "fixture-tap"
        assert not tap.path.exists()
        assert not tap.cache_file.exists()
        assert config.get("taps") == []

    def test_remove_only_drops_the_named_tap(self, sandbox):
        # Removing one of several taps must leave the others in config. Pins the
        # `cfg["taps"] = [t ... if t["name"] != tap.name]` rewrite and its
        # `config.save(cfg)` — a wrong key, empty default, or save(None) would
        # blow away the survivors instead of keeping them.
        cfg = config.load()
        cfg["taps"] = [{"name": "one", "url": "u1", "curated": False},
                       {"name": "two", "url": "u2", "curated": False},
                       {"name": "three", "url": "u3", "curated": False}]
        config.save(cfg)
        registry.remove("two")
        assert [t["name"] for t in config.get("taps")] == ["one", "three"]

    def test_remove_unknown_raises(self, sandbox):
        with pytest.raises(BoostError):
            registry.remove("nope")


class TestUpdate:
    def test_update_clones_missing_tap(self, sandbox, tmp_path):
        origin = _make_repo(tmp_path / "pullme")
        tap = registry.add(str(origin))
        util.rmtree(tap.path)
        assert registry.update("pullme") == ({"pullme": "cloned"}, {})
        assert tap.is_cloned

    def test_update_already_up_to_date(self, sandbox, tmp_path):
        origin = _make_repo(tmp_path / "pullme")
        registry.add(str(origin))
        assert registry.update() == ({"pullme": "already up to date"}, {})

    def test_update_pulls_new_commit(self, sandbox, tmp_path):
        origin = _make_repo(tmp_path / "pullme")
        tap = registry.add(str(origin))
        before = gitutil.head_commit(tap.path)
        (origin / "b.txt").write_text("two\n", encoding="utf-8")
        _git("add", "-A", cwd=origin)
        _git("commit", "-qm", "add b", cwd=origin)
        summary = registry.update("pullme")[0]["pullme"]
        after = gitutil.head_commit(tap.path)
        assert re.fullmatch(r"[0-9a-f]{7} → [0-9a-f]{7}", summary)
        assert summary == "%s → %s" % (before[:7], after[:7])
        assert after == gitutil.head_commit(origin)

    def test_update_unknown_tap_raises(self, sandbox):
        with pytest.raises(BoostError):
            registry.update("nope")

    def test_one_dead_upstream_does_not_stop_the_others(self, sandbox, tmp_path):
        """The regression: `update()` had no error handling, so the first tap
        with a deleted upstream aborted the loop and every later tap went
        unrefreshed — with the successful pulls thrown away unreported.
        """
        dead_origin = _make_repo(tmp_path / "deadtap")
        registry.add(str(dead_origin))
        live_origin = _make_repo(tmp_path / "livetap")
        registry.add(str(live_origin))
        util.rmtree(dead_origin)             # upstream deleted out from under us

        results, failures = registry.update()
        assert "livetap" in results          # the healthy tap still refreshed
        assert "deadtap" not in results      # and is not reported as a success
        assert "deadtap" in failures
        assert failures["deadtap"]           # carries a reason, not an empty string

    def test_a_named_dead_tap_still_raises(self, sandbox, tmp_path):
        """Asking about one tap makes its failure the answer, not a warning."""
        origin = _make_repo(tmp_path / "solo")
        registry.add(str(origin))
        util.rmtree(origin)
        with pytest.raises(BoostError):
            registry.update("solo")


class TestGitErrorLine:
    """gitutil._git_error — git states the cause first, then advises."""

    def test_prefers_the_first_fatal_line_over_the_hint_tail(self):
        # Real `git fetch` output for a missing remote. The last line is the
        # tail of a prose hint; the first names the bad path.
        text = ("fatal: '/nope' does not appear to be a git repository\n"
                "fatal: Could not read from remote repository.\n"
                "\n"
                "Please make sure you have the correct access rights\n"
                "and the repository exists.\n")
        assert gitutil._git_error(text) == (
            "fatal: '/nope' does not appear to be a git repository")

    def test_error_prefix_counts_too(self):
        assert gitutil._git_error("error: pathspec 'x' did not match\ntrailing\n") == (
            "error: pathspec 'x' did not match")

    def test_falls_back_to_last_line_without_a_marker(self):
        assert gitutil._git_error("something odd\nlast word\n") == "last word"

    def test_blank_output_is_named_rather_than_empty(self):
        assert gitutil._git_error("   \n\n") == "unknown error"

    def test_skips_blank_lines_when_falling_back(self):
        assert gitutil._git_error("only line\n\n\n") == "only line"
