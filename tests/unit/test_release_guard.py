# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
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
import sys
from pathlib import Path

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
    def test_an_unreadable_ref_yields_no_tags(self, capsys):
        assert guard.git_tags_at("definitely-not-a-ref-9f8e7d") == []
        assert "could not list tags" in capsys.readouterr().out
