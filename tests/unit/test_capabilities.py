# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: core/capabilities.py — declared/detected capability classifying."""
from __future__ import annotations

import pytest

from boost_cli.core import capabilities as caps

# ── declared ─────────────────────────────────────────────────────────────

def test_declared_from_a_list():
    assert caps.declared({"capabilities": ["network", "shell"]}) == {"network", "shell"}


def test_declared_from_a_comma_string():
    assert caps.declared({"capabilities": "network, filesystem"}) == \
        {"network", "filesystem"}


def test_declared_folds_aliases():
    assert caps.declared({"capabilities": ["net", "bash", "fs"]}) == \
        {"network", "shell", "filesystem"}


def test_declared_drops_unknown_but_unknown_surfaces_them():
    meta = {"capabilities": ["network", "telepathy"]}
    assert caps.declared(meta) == {"network"}
    assert caps.unknown(meta) == {"telepathy"}


def test_declared_empty_for_no_field():
    assert caps.declared({}) == set()
    assert caps.declared({"capabilities": ""}) == set()


# ── detect ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,cap", [
    ("run `curl https://api.example.com`", "network"),
    ("fetch(url) then parse", "network"),
    ("connect to wss://host/stream", "network"),
    ("```bash\necho hi\n```", "shell"),
    ("uses subprocess.run(...)", "shell"),
    ("pipe it | sh", "shell"),
    ("then `rm -rf build`", "filesystem"),
    ("call shutil.rmtree(path)", "filesystem"),
    ("chmod +x the script", "filesystem"),
])
def test_detect_finds_each_bucket(text, cap):
    assert cap in caps.detect(text)


def test_detect_is_quiet_on_plain_prose():
    text = ("This skill helps the agent brainstorm ideas and cluster them "
            "before converging on the best few.")
    assert caps.detect(text) == set()


def test_effective_unions_declared_and_detected():
    meta = {"capabilities": ["network"]}
    text = "```bash\nrm -rf x\n```"
    assert caps.effective(meta, text) == {"network", "shell", "filesystem"}


# ── violations ───────────────────────────────────────────────────────────

def test_declared_denied_always_violates():
    v = caps.violations({"network"}, set(), {"network"}, enforce_detected=False)
    assert len(v) == 1 and "declares" in v[0] and "network" in v[0]


def test_detected_only_does_not_violate_by_default():
    # Author didn't declare it; the fuzzy detection alone must not block.
    v = caps.violations(set(), {"shell"}, {"shell"}, enforce_detected=False)
    assert v == []


def test_detected_violates_under_strict_mode():
    v = caps.violations(set(), {"shell"}, {"shell"}, enforce_detected=True)
    assert len(v) == 1 and "detected" in v[0] and "shell" in v[0]


def test_a_declared_denied_cap_is_reported_once_not_twice():
    # A cap that is both declared AND detected must not double-count under strict.
    v = caps.violations({"network"}, {"network"}, {"network"}, enforce_detected=True)
    assert len(v) == 1 and "declares" in v[0]


def test_allowed_capabilities_pass():
    v = caps.violations({"filesystem"}, {"network"}, {"shell"}, enforce_detected=True)
    assert v == []
