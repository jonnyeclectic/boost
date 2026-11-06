# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The ★ marks a short list, and the short list is coherent.

Every catalogue row used to ship ``curated: true``, so `tap --catalog` starred
all 463 registries it tapped and the marker said nothing. ``CURATED`` in
``scripts/build_registries.py`` now names the most popular and capable ones;
these tests pin that it stays short, names only real rows, never stars a repo
that cannot be searched or installed, and agrees with ``tap --defaults``.

Skips when the repo-root files aren't reachable (the mutation sandbox copies
only ``boost_cli/``).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from boost_cli.core import config

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_registries.py"

pytestmark = pytest.mark.skipif(not _SCRIPT.is_file(),
                                reason="scripts/ not present")


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location("build_registries", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rows(builder):
    return {e["name"]: e for e in builder.build_payload()["registries"]}


def test_curated_is_a_short_list(rows):
    starred = [n for n, e in rows.items() if e["curated"]]
    assert 0 < len(starred) <= 60
    assert len(starred) < len(rows) / 5


def test_every_curated_name_is_a_catalogue_row(builder, rows):
    assert sorted(builder.CURATED - rows.keys()) == []


def test_flag_is_exactly_membership(builder, rows):
    assert {n for n, e in rows.items() if e["curated"]} == builder.CURATED


def test_never_stars_what_cannot_be_searched_or_installed(builder, rows):
    assert [n for n in builder.CURATED if rows[n]["list_only"]] == []
    assert sorted(builder.CURATED & set(builder.SELF_INSTALLING)) == []
    assert sorted(builder.CURATED & set(builder.RETIRED)) == []


def test_default_taps_in_the_catalogue_are_curated(builder, rows):
    # `tap --defaults` stars every default; `tap --catalog` must not tap the
    # same repo unstarred.
    defaults = {str(d["name"]) for d in config.DEFAULT_TAPS}
    assert sorted((defaults & rows.keys()) - builder.CURATED) == []
