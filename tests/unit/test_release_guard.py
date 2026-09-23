# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: scripts/release_guard.py — the decision to publish or skip.

The guard sits in front of a step that uploads to PyPI under Trusted
Publishing, so both of its answers are expensive to get wrong: a false "release"
burns a version number on code that already shipped, and a false "skip" strands
a release that a human then has to notice and dispatch by hand. It lives in
scripts/, which neither of the other quality gates reaches — coverage measures
`boost_cli` and mutmut mutates `boost_cli/core` — so untested here is untested
anywhere.

`decide` takes its PyPI probe as an argument precisely so these run with no
network: every test below supplies a fake.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_guard():
    """Import scripts/release_guard.py by path — scripts/ is not a package.

    Same importlib shim tests/unit/test_eval_gate.py uses.
    """
    spec = importlib.util.spec_from_file_location(
        "boost_release_guard", ROOT / "scripts" / "release_guard.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guard = _load_guard()

# Hermetic: the developer's global gitconfig may sign tags, set a different
# default branch, or install hooks. None of that is what these tests are about.
GIT_ENV = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull,
               GIT_CONFIG_SYSTEM=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="T", GIT_COMMITTER_EMAIL="t@example.com")


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True,
                          capture_output=True, text=True, env=GIT_ENV)


def make_repo(path):
    """A real two-commit repo, tagged on the FIRST commit.

    The shape a release repo is actually in between releases: tags exist, just
    not on HEAD. A repo with no tags at all cannot tell "this commit is
    untagged" apart from "this clone has no tags".
    """
    path.mkdir(parents=True, exist_ok=True)
    git("init", "-q", "-b", "main", cwd=path)
    (path / "a.txt").write_text("1", encoding="utf-8")
    git("add", "a.txt", cwd=path)
    git("commit", "-qm", "one", cwd=path)
    git("tag", "v1.0.283", cwd=path)
    (path / "a.txt").write_text("2", encoding="utf-8")
    git("commit", "-qam", "two", cwd=path)
    return path


@pytest.fixture
def full_clone(tmp_path, monkeypatch):
    """cwd inside a real, NON-shallow repo.

    Every test that lets `git_tags_at` reach git needs this: since the guard
    checks `--is-shallow-repository` first, a test run from a shallow checkout
    of boost itself would otherwise raise about shallowness before ever
    running the `git tag --points-at` the test is about. The verdict must not
    depend on how the tree under test was cloned.
    """
    repo = make_repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    return repo


PROJECT = "boost-skill-cli"


def _probe(**published):
    """A fake PyPI: version -> True (on PyPI) / False (absent) / None (unknown)."""
    return lambda _project, version: published.get(version.replace(".", "_"))


class TestVersionOf:
    def test_strips_the_v_prefix(self):
        assert guard.version_of("v1.0.283") == "1.0.283"

    def test_accepts_a_bare_version(self):
        assert guard.version_of("1.0.283") == "1.0.283"

    def test_tolerates_surrounding_whitespace(self):
        assert guard.version_of("  v1.0.283\n") == "1.0.283"

    def test_two_component_version(self):
        assert guard.version_of("v1.0") == "1.0"

    def test_prerelease_suffixes_are_versions_in_both_pep440_spellings(self):
        """`1.0.283rc1` and `1.0.283-rc1` are both installable PyPI versions.

        boost only cuts plain patch tags today, but if one of these ever lands
        the guard should ask PyPI about it rather than shrug and re-release.
        """
        assert guard.version_of("v1.0.283rc1") == "1.0.283rc1"
        assert guard.version_of("v1.0.283-rc1") == "1.0.283-rc1"

    def test_a_non_release_tag_is_not_a_version(self):
        for tag in ("nightly", "latest", "", "v", "release-2024"):
            assert guard.version_of(tag) is None, tag


class TestDecide:
    def test_an_untagged_commit_releases(self):
        proceed, reason = guard.decide([], PROJECT, _probe())
        assert proceed is True
        assert "no tag" in reason

    def test_a_commit_already_on_pypi_is_skipped(self):
        """The duplicate-release bug itself: run 2 resolves the same tip."""
        proceed, reason = guard.decide(["v1.0.283"], PROJECT,
                                       _probe(**{"1_0_283": True}))
        assert proceed is False
        assert "already on PyPI" in reason and "1.0.283" in reason

    def test_a_tag_whose_upload_failed_still_releases(self):
        """The documented recovery path — re-running a failed release run.

        HEAD is tagged from the first attempt, so a tag-only guard would skip
        the retry and strand the release. This is the case that forces the
        guard to ask PyPI rather than git.
        """
        proceed, reason = guard.decide(["v1.0.283"], PROJECT,
                                       _probe(**{"1_0_283": False}))
        assert proceed is True
        assert "not on PyPI" in reason

    def test_unreadable_pypi_fails_closed(self):
        proceed, reason = guard.decide(["v1.0.283"], PROJECT,
                                       _probe(**{"1_0_283": None}))
        assert proceed is False
        assert "could not be read" in reason

    def test_a_non_release_tag_does_not_block(self):
        proceed, reason = guard.decide(["nightly"], PROJECT, _probe())
        assert proceed is True
        assert "nightly" in reason

    def test_any_published_tag_wins_over_an_unpublished_one(self):
        proceed, _ = guard.decide(["v1.0.283", "v1.0.284"], PROJECT,
                                  _probe(**{"1_0_283": True, "1_0_284": False}))
        assert proceed is False

    def test_several_tags_none_published_releases(self):
        proceed, _ = guard.decide(["v1.0.283", "v1.0.284"], PROJECT,
                                  _probe(**{"1_0_283": False, "1_0_284": False}))
        assert proceed is True

    def test_the_probe_is_asked_for_the_configured_project(self):
        seen = []

        def probe(project, version):
            seen.append((project, version))
            return False

        guard.decide(["v1.0.283"], "some-other-name", probe)
        assert seen == [("some-other-name", "1.0.283")]


class TestPypiHas:
    """The probe itself, with urlopen faked — no network."""

    def _patch(self, monkeypatch, opener):
        monkeypatch.setattr(guard.urllib.request, "urlopen", opener)
        monkeypatch.setattr(guard.time, "sleep", lambda _s: None)

    def test_a_200_means_published(self, monkeypatch):
        class Resp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        self._patch(monkeypatch, lambda *a, **k: Resp())
        assert guard.pypi_has(PROJECT, "1.0.283") is True

    def test_a_404_means_not_published_and_does_not_retry(self, monkeypatch):
        calls = []

        def boom(*_a, **_k):
            calls.append(1)
            raise guard.urllib.error.HTTPError("u", 404, "nf", {}, None)

        self._patch(monkeypatch, boom)
        assert guard.pypi_has(PROJECT, "1.0.283") is False
        assert len(calls) == 1, "404 is a definitive answer, not a transient one"

    def test_a_server_error_is_unknown_after_retries(self, monkeypatch):
        calls = []

        def boom(*_a, **_k):
            calls.append(1)
            raise guard.urllib.error.HTTPError("u", 503, "down", {}, None)

        self._patch(monkeypatch, boom)
        assert guard.pypi_has(PROJECT, "1.0.283", attempts=3) is None
        assert len(calls) == 3

    def test_an_unexpected_status_is_unknown_not_absent(self, monkeypatch):
        """`return 200 <= resp.status < 300` turned a status it did not
        understand into "this version is not on PyPI" — i.e. release it.

        Not reachable through the stock opener, which raises on >= 400 and
        follows 3xx, so this is a default rather than a live hole: the one
        branch in the file where "I could not read the answer" was spelled
        False. Every other unknown here is None; so is this one now.
        """
        class Resp:
            status = 304

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        self._patch(monkeypatch, lambda *a, **k: Resp())
        assert guard.pypi_has(PROJECT, "1.0.283") is None

    def test_a_network_failure_is_unknown_never_false(self, monkeypatch):
        def boom(*_a, **_k):
            raise guard.urllib.error.URLError("no route")

        self._patch(monkeypatch, boom)
        assert guard.pypi_has(PROJECT, "1.0.283", attempts=2) is None


class TestEmit:
    def test_appends_a_step_output(self, tmp_path):
        out = tmp_path / "gh-output"
        guard.emit("proceed", "true", str(out))
        guard.emit("other", "1", str(out))
        assert out.read_text(encoding="utf-8") == "proceed=true\nother=1\n"

    def test_is_a_no_op_without_a_destination(self):
        guard.emit("proceed", "true", "")  # must not raise


class TestMain:
    def test_reports_release_for_an_untagged_commit(self, capsys, monkeypatch,
                                                    tmp_path):
        monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out"))
        assert guard.main(["--project", PROJECT, "--tag", "nightly"]) == 0
        assert "RELEASE" in capsys.readouterr().out
        assert "proceed=true" in (tmp_path / "out").read_text(encoding="utf-8")

    def test_reports_skip_and_annotates_when_already_published(
            self, capsys, monkeypatch, tmp_path):
        monkeypatch.setattr(guard, "pypi_has", lambda *_a, **_k: True)
        monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out"))
        assert guard.main(["--project", PROJECT, "--tag", "v1.0.283"]) == 0
        out = capsys.readouterr().out
        assert "SKIP" in out and "::notice" in out
        assert "proceed=false" in (tmp_path / "out").read_text(encoding="utf-8")

    def test_a_skip_is_not_a_build_failure(self, monkeypatch, tmp_path):
        """Exit 0 either way — 'nothing to release' is a normal outcome."""
        monkeypatch.setattr(guard, "pypi_has", lambda *_a, **_k: True)
        monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out"))
        assert guard.main(["--tag", "v1.0.283"]) == 0

    def test_falls_back_to_the_real_tag_lookup(self, monkeypatch, tmp_path):
        """With no --tag, the guard asks git what points at the ref."""
        monkeypatch.setattr(guard, "git_tags_at", lambda _ref: ["v9.9.9"])
        monkeypatch.setattr(guard, "pypi_has", lambda *_a, **_k: False)
        monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out"))
        assert guard.main([]) == 0
        assert "proceed=true" in (tmp_path / "out").read_text(encoding="utf-8")


class TestGitTagsAt:
    """The tag lookup, which must never answer "" where it means "I don't know".

    `decide` reads an empty tag list as "this commit carries no tag, publish
    it". So every way git can fail to answer has to arrive as something else:
    outside a repository, with a ref that does not resolve, with no `git` on
    PATH, and — the quiet one — inside a shallow checkout, where git answers
    successfully from a tag list it never fetched.
    """

    def test_a_tagless_commit_in_a_real_repo_is_an_empty_list(self, full_clone):
        """The case that must keep working: HEAD genuinely carries no tag."""
        assert guard.git_tags_at("HEAD") == []
        assert guard.git_tags_at("HEAD~1") == ["v1.0.283"]

    def test_a_tagless_commit_still_releases_end_to_end(self, full_clone,
                                                       tmp_path, monkeypatch,
                                                       capsys):
        monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out"))
        assert guard.main([]) == 0
        assert "RELEASE" in capsys.readouterr().out
        assert "proceed=true" in (tmp_path / "out").read_text(encoding="utf-8")

    def test_an_unreadable_ref_raises_and_names_the_git_call(self, full_clone):
        with pytest.raises(guard.TagLookupError) as exc:
            guard.git_tags_at("definitely-not-a-ref-9f8e7d")
        assert "git tag --points-at definitely-not-a-ref-9f8e7d" in str(exc.value)

    def test_a_missing_git_binary_raises(self, monkeypatch, tmp_path):
        # Patch the PATH the guard resolves `git` on, not
        # `guard.subprocess.run` -- that name is the stdlib module object, so
        # replacing it swaps `subprocess.run` for the whole process. It is
        # restored and the suite runs serially, so nothing breaks today; it
        # would break under in-process parallelism or any plugin that shells
        # out while the fake is installed.
        monkeypatch.setenv("PATH", str(tmp_path))
        with pytest.raises(guard.TagLookupError) as exc:
            guard.git_tags_at()
        assert "could not be run" in str(exc.value)

    def test_a_shallow_checkout_raises_rather_than_reporting_no_tags(
            self, tmp_path, monkeypatch):
        """fetch-depth: 1 makes `git tag --points-at` succeed and say nothing.

        publish.yml checks out with `fetch-depth: 0  # all tags — the guard
        reads them`, but the guard never verified it. A clone that lost that
        line would report every commit as untagged and release every trigger.
        """
        origin = make_repo(tmp_path / "origin")
        shallow = tmp_path / "shallow"
        git("clone", "-q", "--depth", "1", "--no-tags",
            "file://%s" % origin, str(shallow))
        monkeypatch.chdir(shallow)
        assert git("tag", "--points-at", "HEAD",
                   cwd=shallow).stdout.strip() == "", \
            "precondition: a shallow clone answers 'no tags' successfully"
        with pytest.raises(guard.TagLookupError) as exc:
            guard.git_tags_at("HEAD")
        assert "shallow" in str(exc.value)
        assert "is-shallow-repository" in str(exc.value)


class TestUnreadableTagsFailClosed:
    """The card: an unreadable tag list used to read as "no tags, go ahead"."""

    def test_decide_refuses_when_the_tag_list_is_unreadable(self):
        proceed, reason = guard.decide(None, PROJECT, _probe(),
                                       "`git tag --points-at HEAD` failed "
                                       "(exit 128): not a git repository")
        assert proceed is False
        assert "not a git repository" in reason
        assert "git tag --points-at HEAD" in reason

    def test_decide_refuses_even_with_no_recorded_reason(self):
        proceed, _ = guard.decide(None, PROJECT, _probe())
        assert proceed is False

    def test_the_probe_is_never_consulted_for_an_unreadable_list(self):
        """There is no version to ask PyPI about — the refusal is unconditional."""
        guard.decide(None, PROJECT,
                     lambda *_a: pytest.fail("PyPI must not be probed"))

    def test_main_refuses_and_names_the_failing_git_call(self, full_clone,
                                                         capsys, monkeypatch,
                                                         tmp_path):
        """The reproduction, end to end.

        Before the fix this printed RELEASE and wrote proceed=true: git exits
        128, `git_tags_at` swallowed it and returned [], and `decide` read that
        as an ordinary untagged commit.
        """
        monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out"))
        assert guard.main(["--ref", "definitely-not-a-ref-9f8e7d"]) == 0
        out = capsys.readouterr().out
        assert "SKIP" in out
        assert "git tag --points-at definitely-not-a-ref-9f8e7d" in out
        assert "::error" in out, "a broken guard is not a routine skip"
        assert "proceed=false" in (tmp_path / "out").read_text(encoding="utf-8")


class TestMalformedTagOverride:
    """`--tag`, the operator override, had the same fail-open shape.

    `--tag "$(git tag --points-at HEAD)"` in a shell puts every tag in ONE
    argument (or, with no tags, an empty one). `version_of` matches neither,
    so `decide` said "carries no release tag, go ahead" — the guard cleared a
    commit that its own caller had just told it was tagged.
    """

    def test_several_tags_crammed_into_one_argument_is_an_error(self, capsys,
                                                                tmp_path):
        code = guard.main(["--tag", "v1.0.283 v1.0.284"])
        assert code == 2
        assert "v1.0.283 v1.0.284" in capsys.readouterr().out

    def test_a_blank_tag_is_an_error(self, capsys):
        assert guard.main(["--tag", ""]) == 2
        assert "--tag" in capsys.readouterr().out

    def test_a_malformed_tag_writes_no_verdict(self, monkeypatch, tmp_path):
        """Exit 2 fails the guard job; it must not also emit proceed=true."""
        out = tmp_path / "out"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out))
        assert guard.main(["--tag", "v1.0.283 v1.0.284"]) == 2
        assert not out.exists()

    def test_surrounding_whitespace_is_still_one_tag(self, monkeypatch,
                                                     tmp_path):
        monkeypatch.setattr(guard, "pypi_has", lambda *_a, **_k: True)
        monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out"))
        assert guard.main(["--tag", "  v1.0.283\n"]) == 0
        assert "proceed=false" in (tmp_path / "out").read_text(encoding="utf-8")

    def test_repeated_tags_are_each_one_tag(self, monkeypatch, tmp_path):
        monkeypatch.setattr(guard, "pypi_has", lambda *_a, **_k: False)
        monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out"))
        assert guard.main(["--tag", "v1.0.283", "--tag", "nightly"]) == 0
        assert "proceed=true" in (tmp_path / "out").read_text(encoding="utf-8")
