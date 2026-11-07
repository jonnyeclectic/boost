# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`install --local --no-mcp` leaves the repo's .mcp.json alone, and stays that way.

A project install records a skill's declared MCP servers in the repo's
``.mcp.json`` (``store.record_project_mcp``). ``record_mcp=False`` skips that
write and says so on the result; the lock row keeps ``no_mcp`` so a reinstall,
update or sync that passes nothing replays the choice, and an explicit
``record_mcp=True`` is the way back in.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import catalog, mcpdecl, projectlock, scopes, store


@pytest.mark.parametrize(("record_mcp", "existing", "skipped"), [
    (None, None, False),
    (None, {}, False),
    (None, {"no_mcp": True}, True),
    (None, {"no_mcp": False}, False),
    (False, None, True),
    (False, {}, True),
    (True, {"no_mcp": True}, False),
])
def test_project_mcp_skipped(record_mcp, existing, skipped):
    assert store.project_mcp_skipped(record_mcp, existing) is skipped


@pytest.fixture()
def project(tapped, tmp_path):
    """A repo, and `brainstorming` declaring one server through its sidecar."""
    base = tmp_path / "mcp-repo"
    (base / ".git").mkdir(parents=True)
    entry = next(e for e in catalog.find("brainstorming"))
    (store.source_dir_for(entry) / mcpdecl.SIDECAR).write_text(json.dumps(
        {mcpdecl.SERVERS_KEY: {"gh": {"command": "npx", "args": ["-y", "gh"]}}}),
        encoding="utf-8")
    return base.resolve(), entry


def _install(project, **kw):
    base, entry = project
    return store.install(entry, scope=scopes.SCOPE_PROJECT, base=base, **kw)


def test_record_mcp_false_writes_nothing_and_says_it_skipped(project):
    base, _entry = project
    res = _install(project, record_mcp=False)
    assert not (base / mcpdecl.SIDECAR).exists()
    assert res.mcp_skipped is True
    assert res.mcp_recorded == []
    assert res.mcp_error is None
    assert [r["name"] for r in res.mcp_servers] == ["gh"]
    assert projectlock.get_skill(base, "brainstorming")["no_mcp"] is True


def test_a_reinstall_that_passes_nothing_replays_no_mcp(project):
    base, _entry = project
    _install(project, record_mcp=False)
    res = _install(project, force=True)
    assert not (base / mcpdecl.SIDECAR).exists()
    assert res.mcp_skipped is True
    assert projectlock.get_skill(base, "brainstorming")["no_mcp"] is True


def test_an_explicit_record_mcp_records_and_drops_the_flag(project):
    base, _entry = project
    _install(project, record_mcp=False)
    res = _install(project, force=True, record_mcp=True)
    assert res.mcp_skipped is False
    assert res.mcp_recorded == ["gh"]
    servers = json.loads((base / mcpdecl.SIDECAR).read_text(
        encoding="utf-8"))[mcpdecl.SERVERS_KEY]
    assert servers["gh"][mcpdecl.MARKER_KEY] == "brainstorming"
    assert "no_mcp" not in projectlock.get_skill(base, "brainstorming")


def test_the_default_still_records(project):
    base, _entry = project
    res = _install(project)
    assert res.mcp_skipped is False
    assert res.mcp_recorded == ["gh"]
    assert (base / mcpdecl.SIDECAR).is_file()
    assert "no_mcp" not in projectlock.get_skill(base, "brainstorming")
