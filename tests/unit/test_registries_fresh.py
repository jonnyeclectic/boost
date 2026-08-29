# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Committed registries.json stays in lockstep with its generator.

``boost_cli/data/registries.json`` is a generated artifact (source of truth is
the SKILLS/RULES/WORKFLOWS tuples in ``scripts/build_registries.py``). If a repo
row is edited without regenerating, the committed JSON drifts. This test — the
in-suite twin of the ``build_registries.py --check`` CI step — fails on drift so
a stale artifact can't merge.

Skips when the repo-root files aren't reachable (e.g. the mutation sandbox,
which only copies ``boost_cli/``).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "build_registries.py"
_JSON = _ROOT / "boost_cli" / "data" / "registries.json"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_registries", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not (_SCRIPT.exists() and _JSON.exists()),
                    reason="repo-root files not reachable (e.g. mutation sandbox)")
def test_registries_json_is_regenerated():
    builder = _load_builder()
    fresh = builder.render(builder.build_payload())
    committed = _JSON.read_text(encoding="utf-8")
    assert committed == fresh, (
        "boost_cli/data/registries.json is out of date — regenerate with\n"
        "    python3 scripts/build_registries.py\n"
        "and commit the result (see CONTRIBUTING.md)."
    )


@pytest.mark.skipif(not _SCRIPT.exists(),
                    reason="repo-root files not reachable (e.g. mutation sandbox)")
def test_check_flag_passes_on_fresh_tree():
    builder = _load_builder()
    assert builder.main(["--check"]) == 0
