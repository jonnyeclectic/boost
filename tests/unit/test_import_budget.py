# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: scripts/import_budget.py — the startup lazy-import guard.

The pure parsing/denylist logic is tested directly; a single integration test
runs the real gate over the live interpreter so a genuine leak (a heavy module
newly imported at startup) fails here too, not just in CI.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "import_budget.py"


def _load():
    spec = importlib.util.spec_from_file_location("import_budget", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pytestmark = pytest.mark.skipif(
    not _SCRIPT.exists(), reason="repo-root scripts/ not reachable (e.g. mutation sandbox)")


# A realistic slice of `python -X importtime` stderr (the real header + rows).
_SAMPLE = """\
import time: self [us] | cumulative | imported package
import time:       120 |        120 |   _io
import time:       200 |        900 |   urllib.request
import time:        90 |         90 |     http.client
import time:       300 |       1200 | boost_cli.cli
import time:       150 |        150 |   sqlite_vec
"""


class TestParseModules:
    def test_extracts_names_and_skips_header(self):
        mod = _load()
        names = mod.parse_modules(_SAMPLE)
        assert "urllib.request" in names
        assert "boost_cli.cli" in names
        assert "sqlite_vec" in names
        # the header row ("self [us] | cumulative | imported package") is not a
        # module and must not be captured
        assert "imported package" not in names
        assert "cumulative" not in names

    def test_strips_nesting_indent(self):
        mod = _load()
        # deeply nested rows keep only the dotted module name, no leading spaces
        names = mod.parse_modules("import time:  90 |  90 |       a.b.c\n")
        assert names == {"a.b.c"}

    def test_ignores_non_importtime_lines(self):
        mod = _load()
        noise = "some other stderr line\nWARNING: whatever\n"
        assert mod.parse_modules(noise) == set()

    def test_ignores_malformed_rows(self):
        mod = _load()
        # a row missing the third field yields nothing rather than a bad name
        assert mod.parse_modules("import time:   10 |   10\n") == set()


class TestLeaksFor:
    def test_flags_denylisted_modules_only(self):
        mod = _load()
        present = {"json", "os", "sqlite_vec", "boost_cli.core.dense", "urllib.request"}
        assert mod.leaks_for(present) == ["boost_cli.core.dense", "sqlite_vec"]

    def test_clean_set_has_no_leaks(self):
        mod = _load()
        assert mod.leaks_for({"json", "os", "boost_cli.cli", "urllib.request"}) == []

    def test_result_is_sorted(self):
        mod = _load()
        present = {"ranx", "anticipation", "numpy", "torch"}
        assert mod.leaks_for(present) == sorted(mod.DENYLIST & present)


class TestMain:
    def test_returns_1_and_reports_on_leak(self, monkeypatch, capsys):
        mod = _load()
        monkeypatch.setattr(mod, "check", lambda: {
            "boost count": {"leaks": ["sqlite_vec"], "count": 210},
        })
        rc = mod.main([])
        out = capsys.readouterr().out
        assert rc == 1
        assert "FAIL" in out and "sqlite_vec" in out and "boost count" in out

    def test_returns_0_when_clean(self, monkeypatch, capsys):
        mod = _load()
        monkeypatch.setattr(mod, "check", lambda: {
            "boost --help": {"leaks": [], "count": 177},
        })
        rc = mod.main([])
        assert rc == 0
        assert "OK" in capsys.readouterr().out

    def test_list_flag_prints_counts(self, monkeypatch, capsys):
        mod = _load()
        monkeypatch.setattr(mod, "check", lambda: {
            "boost list": {"leaks": [], "count": 201},
        })
        mod.main(["--list"])
        assert "201 modules" in capsys.readouterr().out

    def test_soft_ceiling_is_advisory_not_fatal(self, monkeypatch, capsys):
        mod = _load()
        over = mod.SOFT_MODULE_CEILING + 50
        monkeypatch.setattr(mod, "check", lambda: {
            "boost --help": {"leaks": [], "count": over},
        })
        rc = mod.main([])
        # a high module count is a note, not a failure (import graphs differ
        # across Python versions/platforms)
        assert rc == 0
        assert "advisory ceiling" in capsys.readouterr().out


class TestIntegration:
    def test_live_startup_has_no_heavy_imports(self):
        """The real gate over this interpreter must be clean — a genuine
        regression (a heavy module imported at startup) fails the suite here."""
        mod = _load()
        report = mod.check()
        # Dark commands FIRST. Without this the test has exactly the bug this
        # branch fixes: a command that could not be measured records
        # `leaks: []`, so `offenders` is empty and the one test whose docstring
        # promises to catch a genuine regression passes over a gate measuring
        # nothing.
        dark = {label: data["error"]
                for label, data in report.items() if data.get("error")}
        assert not dark, (
            "the gate could not measure these commands, so it asserted "
            "nothing about them: %s" % dark)
        offenders = {label: data["leaks"]
                     for label, data in report.items() if data["leaks"]}
        assert not offenders, (
            "heavy/optional modules leaked into startup: %s — keep the import "
            "lazy (see scripts/import_budget.py)" % offenders)


# --------------------------------------------------------------- measurement

# What `python -X importtime` emits when the interpreter dies before it can
# reach the CLI: a handful of stdlib rows (74 of them, measured) and then a
# traceback. `leaks_for()` on that set is empty, which is indistinguishable
# from a clean run unless the gate looks at the exit status.
_BROKEN = """\
import time: self [us] | cumulative | imported package
import time:       120 |        120 |   _io
import time:       200 |        900 |   encodings.utf_8
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'boost_cli'
"""

_CLEAN = """\
import time: self [us] | cumulative | imported package
import time:       120 |        120 |   _io
import time:       300 |       1200 | boost_cli.cli
"""


class _Recorder:
    """A stand-in for ``subprocess.run`` that records every call."""

    def __init__(self, results):
        self.results = list(results)
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        import subprocess as _sp
        self.calls.append(list(argv))
        rc, stderr = self.results[min(len(self.calls) - 1, len(self.results) - 1)]
        return _sp.CompletedProcess(argv, rc, "", stderr)


def _patch_run(monkeypatch, mod, results):
    import subprocess as _sp
    rec = _Recorder(results)
    monkeypatch.setattr(_sp, "run", rec)
    return rec


class TestUntrustworthyMeasurement:
    """A gate whose assertion is "this name is absent" passes vacuously when
    nothing ran. Each test drives ``main`` and asserts on the *verdict*."""

    def test_nonzero_exit_is_not_a_pass(self, monkeypatch, capsys):
        mod = _load()
        _patch_run(monkeypatch, mod, [(1, _BROKEN)])
        rc = mod.main([])
        out = capsys.readouterr().out
        assert rc == 2, "a command that died was reported as a clean gate"
        assert "OK" not in out

    def test_nonzero_exit_names_the_command_and_its_stderr(self, monkeypatch, capsys):
        mod = _load()
        _patch_run(monkeypatch, mod, [(1, _BROKEN)])
        mod.main([])
        out = capsys.readouterr().out
        assert "boost --help" in out
        assert "exited 1" in out
        assert "No module named 'boost_cli'" in out

    def test_failure_report_drops_the_importtime_noise(self, monkeypatch, capsys):
        mod = _load()
        noise = "\n".join("import time:  10 |  10 |   mod%d" % i for i in range(300))
        _patch_run(monkeypatch, mod, [(1, noise + "\n" + _BROKEN)])
        mod.main([])
        out = capsys.readouterr().out
        assert "No module named 'boost_cli'" in out
        assert "import time:" not in out, "the traceback drowned in 300 import rows"

    def test_measurement_that_never_reached_the_cli_is_refused(self, monkeypatch, capsys):
        mod = _load()
        # rc 0, plenty of modules — but none of them is the CLI, so whatever
        # was measured is not boost starting up.
        stdlib_only = "\n".join(
            ["import time: self [us] | cumulative | imported package"]
            + ["import time:  10 |  10 |   stdmod%d" % i for i in range(80)])
        _patch_run(monkeypatch, mod, [(0, stdlib_only)])
        rc = mod.main([])
        out = capsys.readouterr().out
        assert rc == 2
        assert "boost_cli.cli" in out

    def test_empty_parse_is_refused(self, monkeypatch, capsys):
        mod = _load()
        _patch_run(monkeypatch, mod, [(0, "")])
        rc = mod.main([])
        assert rc == 2
        assert "OK" not in capsys.readouterr().out

    def test_clean_measurement_still_passes(self, monkeypatch, capsys):
        mod = _load()
        _patch_run(monkeypatch, mod, [(0, _CLEAN)])
        rc = mod.main([])
        assert rc == 0
        assert "OK" in capsys.readouterr().out

    def test_every_command_is_attempted_after_one_fails(self, monkeypatch, capsys):
        mod = _load()
        rec = _patch_run(monkeypatch, mod, [(1, _BROKEN), (0, _CLEAN)])
        rc = mod.main([])
        assert rc == 2
        assert len(rec.calls) == len(mod.COMMANDS), (
            "stopping at the first failure hides how much of the gate is dark")

    def test_a_leak_measured_is_still_exit_1(self, monkeypatch, capsys):
        mod = _load()
        leaky = _CLEAN + "import time:  150 |  150 |   sqlite_vec\n"
        _patch_run(monkeypatch, mod, [(0, leaky)])
        rc = mod.main([])
        out = capsys.readouterr().out
        assert rc == 1 and "sqlite_vec" in out

    def test_unmeasured_outranks_a_leak_when_both_happen(self, monkeypatch,
                                                          capsys):
        # Both are non-zero, so the gate fails either way; which code it
        # exits with is the claim being pinned. A run that is partly dark
        # reports dark, because the leak it *did* see says nothing about
        # the commands it never measured -- and a rule stated in the
        # docstring with no test is a rule that can be undone silently.
        mod = _load()
        leaky = _CLEAN + "import time:  150 |  150 |   sqlite_vec\n"
        _patch_run(monkeypatch, mod, [(1, _BROKEN), (0, leaky)])
        rc = mod.main([])
        out = capsys.readouterr().out
        assert rc == 2, "a partly dark run reported as a plain leak"
        assert "sqlite_vec" in out
        assert "exited 1" in out


class TestDiagnosticStderr:
    def test_keeps_only_non_importtime_lines(self):
        mod = _load()
        assert "import time:" not in mod.diagnostic_stderr(_BROKEN)
        assert "ModuleNotFoundError" in mod.diagnostic_stderr(_BROKEN)

    def test_keeps_the_tail_not_the_head(self):
        mod = _load()
        body = "\n".join("line%d" % i for i in range(50))
        tail = mod.diagnostic_stderr(body, limit=3)
        assert tail == "line47\nline48\nline49"

    def test_empty_stream_is_described_not_blank(self):
        mod = _load()
        assert mod.diagnostic_stderr("").strip() != ""


class TestRealSubprocess:
    """The one test that spawns the real interpreter: it proves the ``-c``
    snippet propagates ``main``'s *return value*, not just the exceptions it
    raises. ``cwd``/``PYTHONPATH`` both point at the fake root, so its
    ``boost_cli`` shadows any installed one."""

    def _fake_root(self, tmp_path, body: str):
        pkg = tmp_path / "boost_cli"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "cli.py").write_text(body, encoding="utf-8")
        return tmp_path

    def test_a_command_that_returns_nonzero_fails_the_gate(self, tmp_path, monkeypatch, capsys):
        mod = _load()
        root = self._fake_root(tmp_path, "def main(argv=None):\n    return 3\n")
        monkeypatch.setattr(mod, "ROOT", root)
        rc = mod.main([])
        out = capsys.readouterr().out
        assert rc == 2, "a CLI that exits 3 for every command reported OK"
        assert "exited 3" in out

    def test_a_cli_that_cannot_be_imported_fails_the_gate(self, tmp_path,
                                                          monkeypatch, capsys):
        """The card's reproduction, in the form that survives a dev venv.

        The card measured it by pointing ``ROOT`` at a directory holding no
        ``boost_cli`` — which is only unimportable on an interpreter that has
        no boost installed. Under ``.venv/bin/python`` the editable install
        answers the import whatever ``ROOT`` says, so the fake root here
        *shadows* it with a ``boost_cli`` that raises. Same subprocess death,
        same ~74 stdlib import rows, same empty leak set.
        """
        root = self._fake_root(
            tmp_path, "def main(argv=None):\n    return 0\n")
        (root / "boost_cli" / "__init__.py").write_text(
            "raise ImportError('no module named boost_cli')", encoding="utf-8")
        mod = _load()
        monkeypatch.setattr(mod, "ROOT", root)
        rc = mod.main([])
        out = capsys.readouterr().out
        assert rc == 2, "a broken boost_cli import was reported as a clean gate"
        assert "OK" not in out
        assert "ImportError" in out
