# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: ``boost info`` names the tap and where it lives.

``tap`` and ``tap_url`` sit at the top of every ``--json`` payload — skill,
rule or workflow, installed or not — and the card prints a ``tap url`` row
under ``tap``. Before, a script wanting the repository had to join
``boost taps --json`` on the tap name, and a rule's JSON had its tap only
inside the nested lock row.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess

from boost_cli.core import lockfile, paths, registry


def _tap():
    return next(t for t in registry.list_taps() if t.name != "boost/builtin")


def test_installed_skill_json_has_tap_and_tap_url(boost, installed):
    tap = _tap()
    data = json.loads(boost("info", installed, "--json").out)
    assert data["tap"] == tap.name
    assert data["tap_url"] == tap.url
    assert data["tap_url"] == lockfile.get_skill(installed)["tap_url"]


def test_not_installed_skill_json_has_the_configured_url(boost, tapped):
    data = json.loads(boost("info", "commit-messages", "--json").out)
    assert data["installed"] is None
    assert data["tap_url"] == _tap().url


def test_the_url_recorded_at_install_outlives_the_tap(boost, installed):
    url = _tap().url
    boost("untap", _tap().name, "--yes", expect=None)
    data = json.loads(boost("info", installed, "--json").out)
    assert data["tap_url"] == url


def test_card_prints_a_tap_url_row_under_tap(boost, installed):
    out = boost("info", installed).out
    lines = [ln.strip() for ln in out.splitlines()]
    at = next(i for i, ln in enumerate(lines) if re.match(r"tap\s", ln))
    assert re.match(r"tap url\s+%s$" % re.escape(paths.tilde(_tap().url)),
                    lines[at + 1])


def test_rule_json_has_tap_and_tap_url_at_the_top(boost, fixture_tap_src,
                                                  tmp_path):
    src = tmp_path / "rule-tap"
    shutil.copytree(fixture_tap_src, src)
    (src / "rules").mkdir()
    (src / "rules" / "house.mdc").write_text(
        "---\nname: house\nversion: 1.0.0\ndescription: House style.\n---\n\n"
        "Use tabs.\n", encoding="utf-8")
    for args in (("add", "-A"), ("-c", "user.email=t@b.test", "-c",
                                 "user.name=t", "commit", "-qm", "rule")):
        subprocess.run(["git", "-C", str(src), *args], check=True,
                       capture_output=True)
    boost("tap", src)
    boost("install", "house", "--agent", "claude-code")
    data = json.loads(boost("info", "house", "--json").out)
    assert data["kind"] == "rule"
    assert data["tap"] == _tap().name
    assert data["tap_url"] == _tap().url
    assert re.search(r"tap url\s+\S", boost("info", "house").out)


def test_an_import_reports_its_source_url_and_prints_no_extra_row(
        boost, installed, monkeypatch):
    # A URL import records `tap: local` and the repository as `source_url`;
    # the card's `source` row already prints it, so only --json repeats it.
    row = dict(lockfile.get_skill(installed), tap="local", tap_url=None,
               source_url="https://github.com/o/r")
    lockfile.set_skill(installed, row)
    data = json.loads(boost("info", installed, "--json").out)
    assert data["tap"] == "local"
    assert data["tap_url"] == "https://github.com/o/r"
    out = boost("info", installed).out
    assert "tap url" not in out
    assert "https://github.com/o/r" in out
