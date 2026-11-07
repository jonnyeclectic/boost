# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`build_registries.py --verify-live` reports a renamed repo instead of passing it.

GitHub answers a renamed repo's old name with a 301, and urlopen follows it
silently, so a sweep that read only ``archived`` called five stale rows healthy
on 2026-11-07 — `sickn33/antigravity-awesome-skills` among them, which then
looked like a new candidate under its new name. These tests stub urlopen with
the body GitHub returns after the redirect.

Skips when the repo-root scripts aren't reachable (the mutation sandbox copies
only ``boost_cli/``).
"""
from __future__ import annotations

import importlib.util
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

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


class _Response:
    def __init__(self, body: dict) -> None:
        self._raw = json.dumps(body).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


@pytest.fixture()
def github(monkeypatch):
    """Answer /repos/<name> from a dict; a missing name is a 404."""
    bodies: dict[str, dict] = {}

    def urlopen(req, timeout=None):
        name = req.full_url.split("/repos/", 1)[1]
        if name not in bodies:
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found",
                                         None, None)  # type: ignore[arg-type]
        return _Response(bodies[name])

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return bodies


def test_a_renamed_repo_is_reported_with_its_new_name(builder, github, capsys):
    github["old-owner/old-name"] = {"full_name": "new-owner/new-name",
                                    "archived": False}
    assert builder.verify_live(["old-owner/old-name"]) == 0
    out, err = capsys.readouterr()
    assert out.splitlines() == ["renamed   old-owner/old-name -> new-owner/new-name"]
    assert "1 checked: 0 missing, 0 archived, 1 renamed" in err


def test_a_case_only_difference_is_not_a_rename(builder, github, capsys):
    # GitHub resolves owner/repo case-blind and reports its own spelling;
    # rows like `K-Dense-AI/...` would otherwise all read as renamed.
    github["owner/Repo"] = {"full_name": "Owner/repo"}
    assert builder.verify_live(["owner/Repo"]) == 0
    out, err = capsys.readouterr()
    assert "renamed" not in out
    assert "0 renamed" in err


def test_a_rename_onto_a_listed_row_says_it_is_a_duplicate(builder, github, capsys):
    github["a/old"] = {"full_name": "a/new"}
    github["a/new"] = {"full_name": "a/new"}
    builder.verify_live(["a/old", "a/new"])
    out, _err = capsys.readouterr()
    assert out.splitlines() == ["renamed   a/old -> a/new  (already listed)"]


def test_a_body_without_full_name_is_not_a_rename(builder, github, capsys):
    # A body that omits the field must fall back to the row's own name, not
    # to the string "None", or every such row would read as renamed.
    github["a/plain"] = {"archived": False}
    github["a/null"] = {"full_name": None}
    assert builder.verify_live(["a/plain", "a/null"]) == 0
    out, err = capsys.readouterr()
    assert out == ""
    assert "2 checked: 0 missing, 0 archived, 0 renamed" in err


def test_already_listed_matches_case_blind(builder, github, capsys):
    # GitHub reports its own spelling, and a row may differ only in case.
    github["a/old"] = {"full_name": "A/New"}
    github["a/new"] = {"full_name": "A/New"}
    builder.verify_live(["a/old", "a/new"])
    out, _err = capsys.readouterr()
    assert out.splitlines() == ["renamed   a/old -> A/New  (already listed)"]


def test_archived_and_missing_are_still_reported(builder, github, capsys):
    github["a/frozen"] = {"full_name": "a/frozen", "archived": True}
    github["a/moved"] = {"full_name": "b/moved", "archived": True}
    assert builder.verify_live(["a/frozen", "a/moved", "a/gone"]) == 1
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        "archived  a/frozen",
        "archived  a/moved",
        "renamed   a/moved -> b/moved",
        "MISSING   a/gone",
    ]
    assert "3 checked: 1 missing, 2 archived, 1 renamed" in err
