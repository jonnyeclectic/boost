# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Steps for `boost index` / `boost discover` — the GitHub Code Search-backed
discovery cache. `gh` is always mocked (shutil.which + subprocess.run), never
shelled out to for real, mirroring tests/functional/test_cli_discovery.py.
"""
from __future__ import annotations

import json
import types
from unittest import mock

from behave import given

_ITEMS = [
    {"repo": "octo/skills", "path": "skills/tdd/SKILL.md",
     "url": "u1", "description": "tdd stuff"},
    {"repo": "acme/pack", "path": "skills/web/SKILL.md",
     "url": "u2", "description": "react helpers"},
    {"repo": "acme/pack", "path": "skills/db/SKILL.md",
     "url": "u3", "description": ""},
]


def _patch(context, target, replacement):
    patcher = mock.patch(target, replacement)
    patcher.start()
    context._patchers.append(patcher)


def _gh_page(items, total=7):
    return json.dumps({"total_count": total, "items": items})


def _gh_item(repo, path, desc="Skill repo"):
    return {"repository": {"full_name": repo, "description": desc},
            "path": path, "html_url": "https://github.com/%s/%s" % (repo, path)}


@given("the GitHub CLI is not installed")
def step_gh_missing(context):
    _patch(context, "boost_cli.commands.discovery.shutil.which", lambda c: None)


@given("the GitHub CLI is installed and code search returns 2 sample skill files")
def step_gh_present_two_items(context):
    _patch(context, "boost_cli.commands.discovery.shutil.which",
           lambda c: "/usr/bin/gh")

    def fake_run(cmd, **kw):
        return types.SimpleNamespace(returncode=0, stderr="", stdout=_gh_page(
            [_gh_item("octo/skills", "skills/a/SKILL.md"),
             _gh_item("acme/pack", "skills/b/SKILL.md", desc="")]))

    _patch(context, "boost_cli.commands.discovery.subprocess.run", fake_run)


@given("the GitHub CLI is installed but code search fails")
def step_gh_present_fails(context):
    _patch(context, "boost_cli.commands.discovery.shutil.which",
           lambda c: "/usr/bin/gh")
    _patch(context, "boost_cli.commands.discovery.subprocess.run",
           lambda cmd, **kw: types.SimpleNamespace(
               returncode=1, stdout="", stderr="gh: Not Found (HTTP 404)"))


@given("the discovery index is seeded with sample items")
def step_seed_discovery_index(context):
    from boost_cli.core import paths, util
    paths.ensure_dirs()
    (paths.cache_dir() / "discovery.json").write_text(json.dumps(
        {"generated": util.now_iso(), "github_total": 42, "items": _ITEMS}), encoding="utf-8")


@given("the discovery index is corrupt")
def step_corrupt_discovery_index(context):
    from boost_cli.core import paths
    paths.ensure_dirs()
    (paths.cache_dir() / "discovery.json").write_text("{broken", encoding="utf-8")
