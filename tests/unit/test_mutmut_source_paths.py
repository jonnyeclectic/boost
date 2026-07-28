"""Unit tests: the conftest hook that lets functional tests run under mutmut.

mutmut resolves its configured ``source_paths`` *relative to the cwd*, from
inside the trampoline, on every call into mutated code. This suite's functional
tests chdir into throwaway project dirs, so that resolve raises
``FileNotFoundError: <tmpdir>/boost_cli`` and kills the whole stats phase —
which is why the mutation gate is pinned to ``tests/unit/`` and why
``boost_cli/commands/`` cannot be brought under it.

These tests drive the fix against the real failure rather than against a proxy
for it: each one chdirs somewhere else and then does exactly what mutmut does.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

CONFTEST = Path(__file__).resolve().parents[1] / "conftest.py"
ROOT = Path(__file__).resolve().parents[2]


def load_conftest():
    """Import tests/conftest.py by path, the way this repo tests scripts/."""
    spec = importlib.util.spec_from_file_location("boost_conftest_under_test",
                                                  CONFTEST)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class FakeConfig:
    """Stands in for mutmut's Config: a plain mutable dataclass with a list."""

    def __init__(self, source_paths):
        self.source_paths = list(source_paths)


class TestAbsolutizeSourcePaths:
    def test_relative_paths_become_absolute(self, monkeypatch):
        monkeypatch.chdir(ROOT)
        cfg = FakeConfig([Path("boost_cli/core/"), Path("boost_cli/commands/")])
        out = load_conftest().absolutize_source_paths(cfg)
        # Exact equality, not `is_absolute()`: a mutant that resolved against
        # some other directory would still produce absolute paths.
        assert out == [(ROOT / "boost_cli/core").resolve(),
                       (ROOT / "boost_cli/commands").resolve()]
        assert cfg.source_paths == out, "must rewrite the config in place"

    def test_a_chdir_no_longer_breaks_the_resolve(self, tmp_path, monkeypatch):
        # This IS the bug. Before the fix, resolve(strict=True) from a test's
        # temp project dir raises; after it, it returns the real path.
        monkeypatch.chdir(ROOT)
        cfg = FakeConfig([Path("boost_cli/core/")])
        relative = cfg.source_paths[0]
        load_conftest().absolutize_source_paths(cfg)

        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError):
            relative.resolve(strict=True)          # what mutmut used to do
        assert cfg.source_paths[0].resolve(strict=True) == \
            (ROOT / "boost_cli/core").resolve()    # what it does now

    def test_already_absolute_paths_are_unchanged(self, monkeypatch, tmp_path):
        absolute = (ROOT / "boost_cli" / "core").resolve()
        cfg = FakeConfig([absolute])
        monkeypatch.chdir(tmp_path)     # cwd must not matter for these
        assert load_conftest().absolutize_source_paths(cfg) == [absolute]

    def test_an_empty_list_is_left_empty(self):
        cfg = FakeConfig([])
        assert load_conftest().absolutize_source_paths(cfg) == []

    def test_strings_are_accepted_not_just_paths(self, monkeypatch):
        # setup.cfg parsing has changed shape upstream before; accepting str
        # costs nothing and stops a silent AttributeError inside a trampoline.
        monkeypatch.chdir(ROOT)
        cfg = FakeConfig(["boost_cli/core/"])
        assert load_conftest().absolutize_source_paths(cfg) == \
            [(ROOT / "boost_cli/core").resolve()]


class TestPytestConfigureGuard:
    """The hook must be inert outside a mutmut run, and never raise inside one."""

    def test_does_nothing_when_not_under_mutmut(self, monkeypatch):
        monkeypatch.delenv("MUTANT_UNDER_TEST", raising=False)
        mod = load_conftest()
        called = []
        monkeypatch.setattr(mod, "absolutize_source_paths",
                            lambda cfg: called.append(cfg))
        mod.pytest_configure(object())
        assert called == [], "must not touch mutmut config on an ordinary run"

    def test_runs_when_mutmut_sets_the_env_var(self, monkeypatch):
        monkeypatch.setenv("MUTANT_UNDER_TEST", "stats")
        mod = load_conftest()
        seen = []

        class FakeMutmutConfig:
            @staticmethod
            def get():
                return FakeConfig([Path("boost_cli/core/")])

        # Stand in for `from mutmut.configuration import Config`.
        import sys
        import types
        fake = types.ModuleType("mutmut.configuration")
        fake.Config = FakeMutmutConfig
        parent = types.ModuleType("mutmut")
        parent.configuration = fake
        monkeypatch.setitem(sys.modules, "mutmut", parent)
        monkeypatch.setitem(sys.modules, "mutmut.configuration", fake)
        monkeypatch.setattr(mod, "absolutize_source_paths",
                            lambda cfg: seen.append(cfg) or cfg.source_paths)

        mod.pytest_configure(object())
        assert len(seen) == 1, "must normalize exactly once, via Config.get()"

    def test_a_missing_mutmut_is_not_an_error(self, monkeypatch):
        # The env var is set but mutmut is not importable. Raising here would
        # break every test in the run.
        monkeypatch.setenv("MUTANT_UNDER_TEST", "stats")
        import sys
        monkeypatch.setitem(sys.modules, "mutmut.configuration", None)
        load_conftest().pytest_configure(object())   # must simply return

    def test_the_guard_reads_the_variable_mutmut_actually_sets(self):
        # Named explicitly so renaming the env var in the hook fails a test
        # rather than silently disabling it — the hook would then be dead code
        # and the FileNotFoundError would come back with nothing to catch it.
        assert "MUTANT_UNDER_TEST" in CONFTEST.read_text(encoding="utf-8")


def test_the_conftest_hook_is_registered():
    # pytest only calls a hook that is actually named pytest_configure; a typo
    # would leave every assertion above passing while the fix never runs.
    assert hasattr(load_conftest(), "pytest_configure")
    assert os.path.basename(str(CONFTEST)) == "conftest.py"
