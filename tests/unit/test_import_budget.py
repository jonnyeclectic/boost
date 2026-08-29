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
        offenders = {label: data["leaks"]
                     for label, data in report.items() if data["leaks"]}
        assert not offenders, (
            "heavy/optional modules leaked into startup: %s — keep the import "
            "lazy (see scripts/import_budget.py)" % offenders)
