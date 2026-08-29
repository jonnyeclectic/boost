# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: scripts/check_licenses.py — the SPDX compatibility gate.

Driven against the licence strings dependencies *actually* publish, not against
tidy identifiers. Every awkward value below was observed in boost's own
resolved closures, which is the whole reason the check matches by regex instead
of using ``pip-licenses --fail-on``.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_licenses.py"

# Verbatim from `pip-licenses --format=json` over `pip install .[eval]`.
TIKTOKEN = ("MIT License\n\nCopyright (c) 2022 OpenAI, Shantanu Jain\n\n"
            "Permission is hereby granted, free of charge, …")
SQLITE_VEC = "MIT License, Apache License, Version 2.0"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("check_licenses", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(m)
    return m


def rows(*pairs):
    return [{"Name": n, "Version": "1.0", "License": lic} for n, lic in pairs]


class TestPermissiveLicencesPass:
    @pytest.mark.parametrize("licence", [
        "MIT", "MIT License", "BSD License", "BSD-3-Clause", "Apache-2.0",
        "Apache Software License", "Python Software Foundation License",
        "PSF-2.0", "MIT-CMU", "Apache-2.0 OR BSD-2-Clause",
        "BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0",
        "MPL-2.0 AND (Apache-2.0 OR MIT)",
        "Mozilla Public License 2.0 (MPL 2.0)",
        SQLITE_VEC, TIKTOKEN,
    ])
    def test_no_violation(self, mod, licence):
        assert mod.violations(rows(("pkg", licence))) == []

    def test_lgpl_and_mpl_are_fine_to_consume(self, mod):
        # Weak copyleft is not a problem for a GPL-3.0 project, and banning it
        # would fail builds for no reason.
        assert mod.violations(rows(
            ("a", "GNU Lesser General Public License v3 (LGPLv3)"),
            ("b", "GNU Lesser General Public License v2 or later (LGPLv2+)"),
            ("c", "Mozilla Public License 2.0 (MPL 2.0)"),
            ("d", "Eclipse Public License 2.0"))) == []

    def test_gplv3_and_gplv2_or_later_pass(self, mod):
        # GPL-3.0 is the project's own licence; "v2 or later" permits taking
        # v3, so both combine cleanly. Only v2-*only* does not.
        assert mod.violations(rows(
            ("a", "GNU General Public License v3 (GPLv3)"),
            ("b", "GNU General Public License v2 or later (GPLv2+)"),
            ("c", "GPL-2.0-or-later"))) == []


class TestIncompatibleLicencesFail:
    @pytest.mark.parametrize("licence", [
        "GNU Affero General Public License v3",
        "AGPL-3.0", "AGPL-3.0-only", "agpl-3.0-or-later",
    ])
    def test_agpl(self, mod, licence):
        [problem] = mod.violations(rows(("pkg", licence)))
        assert "network-use copyleft" in problem
        assert problem.startswith("pkg: ")

    @pytest.mark.parametrize("licence", [
        "GNU General Public License v2 (GPLv2)", "GPL-2.0", "GPL-2.0-only",
    ])
    def test_gplv2_only(self, mod, licence):
        [problem] = mod.violations(rows(("pkg", licence)))
        assert "GPLv2-only" in problem

    @pytest.mark.parametrize("licence", [
        "Other/Proprietary License", "Proprietary", "All Rights Reserved",
        "SSPL-1.0", "BUSL-1.1", "MIT with Commons Clause",
    ])
    def test_non_open_source(self, mod, licence):
        [problem] = mod.violations(rows(("pkg", licence)))
        assert "not an open-source licence" in problem

    def test_a_multi_line_licence_reports_only_its_first_line(self, mod):
        # A whole licence text in the failure message would bury the finding.
        [problem] = mod.violations(rows(
            ("pkg", "Other/Proprietary License\n\nblah\n" * 40)))
        assert "\n" not in problem
        assert len(problem) < 200

    def test_every_offender_is_reported_not_just_the_first(self, mod):
        problems = mod.violations(rows(("a", "AGPL-3.0"), ("b", "MIT"),
                                       ("c", "Other/Proprietary License")))
        assert len(problems) == 2
        assert problems[0].startswith("a: ") and problems[1].startswith("c: ")

    def test_a_package_is_reported_once_even_if_it_trips_twice(self, mod):
        [problem] = mod.violations(rows(("pkg", "AGPL-3.0 AND Proprietary")))
        assert problem.startswith("pkg: ")


class TestUndeclaredLicences:
    @pytest.mark.parametrize("licence", ["UNKNOWN", "unknown", "", "  ", "None"])
    def test_recognised_as_undeclared(self, mod, licence):
        assert mod.is_undeclared(licence) is True

    @pytest.mark.parametrize("licence", ["MIT", "Unknown Software License"])
    def test_not_undeclared(self, mod, licence):
        assert mod.is_undeclared(licence) is False

    def test_an_undeclared_package_fails_by_default(self, mod):
        [problem] = mod.violations(rows(("mystery", "UNKNOWN")))
        assert "declares no licence" in problem

    def test_the_documented_exception_passes(self, mod):
        # ragas is Apache-2.0 upstream; its wheel carries no License field.
        assert mod.violations(rows(("ragas", "UNKNOWN"))) == []
        assert "ragas" in mod.UNDECLARED_OK

    def test_cramjam_is_exempt(self, mod):
        # cramjam is MIT upstream. 2.11.0 declared `License: MIT`; 2.12.0
        # dropped it, and the wheel now ships `License-File: LICENSE` alone —
        # nothing a metadata reader can resolve to an identifier. It arrives
        # transitively (ranx -> fastparquet -> cramjam), so the only remedies
        # the error offers are this entry or dropping [eval] entirely.
        assert mod.violations(rows(("cramjam", "UNKNOWN"))) == []
        assert "cramjam" in mod.UNDECLARED_OK

    def test_every_exception_names_the_upstream_licence(self, mod):
        # An allowlist entry with no reason is indistinguishable from silence.
        for pkg, reason in mod.UNDECLARED_OK.items():
            assert reason.strip(), pkg
            assert pkg == pkg.lower(), "keys are matched lowercased"


class TestMain:
    def test_a_clean_report_exits_zero(self, mod, tmp_path, capsys):
        p = tmp_path / "l.json"
        p.write_text(json.dumps(rows(("a", "MIT"))), encoding="utf-8")
        assert mod.main([str(p)]) == 0
        assert "1 package(s): 0 problem(s)" in capsys.readouterr().out

    def test_a_violation_exits_one_with_an_annotation(self, mod, tmp_path,
                                                      capsys):
        p = tmp_path / "l.json"
        p.write_text(json.dumps(rows(("a", "AGPL-3.0"))), encoding="utf-8")
        assert mod.main([str(p)]) == 1
        assert "::error::a: AGPL" in capsys.readouterr().out

    def test_an_empty_report_is_a_failure_not_a_pass(self, mod, tmp_path,
                                                     capsys):
        # This is how a licence gate quietly stops gating: the environment was
        # never populated, every package passes, the step goes green.
        p = tmp_path / "l.json"
        p.write_text("[]", encoding="utf-8")
        assert mod.main([str(p)]) == 2
        assert "nothing was scanned" in capsys.readouterr().out

    def test_unparseable_input_is_a_failure(self, mod, tmp_path, capsys):
        p = tmp_path / "l.json"
        p.write_text("not json", encoding="utf-8")
        assert mod.main([str(p)]) == 2
        assert "could not parse" in capsys.readouterr().out
