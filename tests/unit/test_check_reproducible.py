# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: scripts/check_reproducible.py — the falsifiability check.

The claim "boost's wheel is reproducible" is only as good as the thing that
keeps re-measuring it. These tests drive the comparison and reporting logic
directly, with the actual `python -m build` invocations replaced by fakes —
a real build takes real seconds and this repo's own dist bytes are not the
thing under test here (tests/functional or a manual run against the real repo
is what proves the pipeline itself; see docs/verifying-releases.md for that
measurement). What must hold regardless of what `build` does: a real mismatch
is reported and fails the process, and the absence of `build` is reported as
"could not check" rather than silently read as success.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "check_reproducible.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_reproducible", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


mod = _load()


class TestCompareDirs:
    def test_identical_files_match(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir()
        b.mkdir()
        (a / "x.whl").write_bytes(b"same bytes")
        (b / "x.whl").write_bytes(b"same bytes")
        report = mod.compare_dirs(a, b)
        assert report == {"x.whl": mod.MATCH}

    def test_differing_files_differ(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir()
        b.mkdir()
        (a / "x.tar.gz").write_bytes(b"one build")
        (b / "x.tar.gz").write_bytes(b"a different build")
        report = mod.compare_dirs(a, b)
        assert report == {"x.tar.gz": mod.DIFFER}

    def test_a_file_missing_on_one_side_differs(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir()
        b.mkdir()
        (a / "only-in-a.whl").write_bytes(b"data")
        report = mod.compare_dirs(a, b)
        assert report == {"only-in-a.whl": mod.DIFFER}

    def test_multiple_artifacts_reported_independently(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir()
        b.mkdir()
        (a / "pkg.whl").write_bytes(b"same")
        (b / "pkg.whl").write_bytes(b"same")
        (a / "pkg.tar.gz").write_bytes(b"different-a")
        (b / "pkg.tar.gz").write_bytes(b"different-b")
        report = mod.compare_dirs(a, b)
        assert report == {"pkg.whl": mod.MATCH, "pkg.tar.gz": mod.DIFFER}


class TestBuildAvailable:
    def test_true_when_build_is_importable(self, monkeypatch):
        # Stubbed, not ambient. Asserting the real environment has `build`
        # installed tests the runner rather than the function: it passed on a
        # dev venv carrying release-tools and failed on every CI leg, which do
        # not install it. The contract is "True iff find_spec resolves", and
        # that is what is pinned here.
        monkeypatch.setattr(mod.importlib.util, "find_spec", lambda name: object())
        assert mod.build_available() is True

    def test_false_when_build_is_not_importable(self, monkeypatch):
        monkeypatch.setattr(mod.importlib.util, "find_spec", lambda name: None)
        assert mod.build_available() is False


class TestMain:
    def test_degrades_cleanly_without_build(self, monkeypatch, capsys):
        monkeypatch.setattr(mod, "build_available", lambda: False)
        rc = mod.main([])
        assert rc == 2
        assert "SKIPPED" in capsys.readouterr().err

    def test_reports_reproducible_when_every_artifact_matches(
            self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(mod, "build_available", lambda: True)

        def fake_build_once(outdir, epoch, *, python=sys.executable):
            (outdir / "pkg-1.0-py3-none-any.whl").write_bytes(b"identical")

        monkeypatch.setattr(mod, "build_once", fake_build_once)
        monkeypatch.setattr(mod, "normalize_sdists", lambda outdir, epoch: None)
        monkeypatch.setattr(mod, "_tip_epoch", lambda: 1700000000)

        rc = mod.main([])
        out = capsys.readouterr().out
        assert rc == 0
        assert "REPRODUCIBLE" in out
        assert "NOT REPRODUCIBLE" not in out

    def test_reports_not_reproducible_and_fails_on_a_real_mismatch(
            self, monkeypatch, tmp_path):
        monkeypatch.setattr(mod, "build_available", lambda: True)
        calls = {"n": 0}

        def fake_build_once(outdir, epoch, *, python=sys.executable):
            calls["n"] += 1
            (outdir / "pkg-1.0.tar.gz").write_bytes(
                b"build one" if calls["n"] == 1 else b"build two, still differs")

        monkeypatch.setattr(mod, "build_once", fake_build_once)
        monkeypatch.setattr(mod, "normalize_sdists", lambda outdir, epoch: None)
        monkeypatch.setattr(mod, "_tip_epoch", lambda: 1700000000)

        rc = mod.main([])
        assert rc == 1

    def test_no_artifacts_built_is_reported_as_unchecked_not_success(
            self, monkeypatch):
        monkeypatch.setattr(mod, "build_available", lambda: True)
        monkeypatch.setattr(mod, "build_once", lambda outdir, epoch, **kw: None)
        monkeypatch.setattr(mod, "normalize_sdists", lambda outdir, epoch: None)
        monkeypatch.setattr(mod, "_tip_epoch", lambda: 1700000000)

        rc = mod.main([])
        assert rc == 2

    def test_a_failed_build_is_reported_as_unchecked_not_success(
            self, monkeypatch):
        monkeypatch.setattr(mod, "build_available", lambda: True)

        def failing_build(outdir, epoch, *, python=sys.executable):
            raise mod.subprocess.CalledProcessError(1, ["python", "-m", "build"],
                                                     stderr="boom")

        monkeypatch.setattr(mod, "build_once", failing_build)
        monkeypatch.setattr(mod, "_tip_epoch", lambda: 1700000000)

        rc = mod.main([])
        assert rc == 2

    def test_skip_normalize_flag_skips_the_sdist_fix(self, monkeypatch):
        monkeypatch.setattr(mod, "build_available", lambda: True)
        monkeypatch.setattr(mod, "_tip_epoch", lambda: 1700000000)

        def fake_build_once(outdir, epoch, *, python=sys.executable):
            (outdir / "pkg-1.0.tar.gz").write_bytes(b"same")

        called = {"normalize": False}

        def fake_normalize(outdir, epoch):
            called["normalize"] = True

        monkeypatch.setattr(mod, "build_once", fake_build_once)
        monkeypatch.setattr(mod, "normalize_sdists", fake_normalize)

        rc = mod.main(["--skip-normalize"])
        assert rc == 0
        assert called["normalize"] is False

    def test_explicit_source_date_epoch_bypasses_git(self, monkeypatch):
        monkeypatch.setattr(mod, "build_available", lambda: True)

        def boom():
            raise AssertionError("git should not be consulted")

        monkeypatch.setattr(mod, "_tip_epoch", boom)
        seen = []

        def fake_build_once(outdir, epoch, *, python=sys.executable):
            seen.append(epoch)
            (outdir / "pkg-1.0.tar.gz").write_bytes(b"same")

        monkeypatch.setattr(mod, "build_once", fake_build_once)
        monkeypatch.setattr(mod, "normalize_sdists", lambda outdir, epoch: None)

        rc = mod.main(["--source-date-epoch", "42"])
        assert rc == 0
        assert seen == [42, 42]
