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


def test_a_no_mcp_skill_does_not_inherit_a_server_another_uninstall_frees(
        project):
    """An opt-out is not a declaration. `tdd-workflow` was installed with
    --no-mcp and declares the same server `brainstorming` recorded; when
    `brainstorming` goes, the server goes with it instead of being re-marked
    to the skill that was told to keep it out of .mcp.json."""
    base, _entry = project
    tdd = next(e for e in catalog.find("tdd-workflow"))
    (store.source_dir_for(tdd) / mcpdecl.SIDECAR).write_text(json.dumps(
        {mcpdecl.SERVERS_KEY: {"gh": {"command": "npx", "args": ["-y", "gh"]}}}),
        encoding="utf-8")
    store.install(tdd, scope=scopes.SCOPE_PROJECT, base=base, record_mcp=False)
    _install(project)
    assert store._project_declarers(base) == ({"gh": "brainstorming"}, True)
    projectlock.remove_skill(base, "brainstorming")
    removed, err = store.forget_project_mcp(base, "brainstorming")
    assert (removed, err) == (["gh"], None)
    # Empty again, and boost created it, so the file goes too.
    assert not (base / mcpdecl.SIDECAR).exists()


def test_a_skip_over_an_earlier_record_says_the_server_is_still_there(project):
    # --no-mcp writes nothing and removes nothing: a server the first
    # install recorded stays in the file, and the result says so.
    base, _entry = project
    _install(project)
    res = _install(project, force=True, record_mcp=False)
    assert res.mcp_skipped is True
    assert res.mcp_present == ["gh"]
    servers = json.loads((base / mcpdecl.SIDECAR).read_text(
        encoding="utf-8"))[mcpdecl.SERVERS_KEY]
    assert "gh" in servers


def test_a_skip_with_nothing_recorded_names_nothing_present(project):
    res = _install(project, record_mcp=False)
    assert res.mcp_present == []


def test_a_recording_install_leaves_present_empty(project):
    res = _install(project)
    assert res.mcp_present == []


@pytest.mark.parametrize(("text", "present"), [
    (None, []),
    ("{not json", []),
    (json.dumps({"mcpServers": {"other": {"command": "x"}}}), []),
    (json.dumps({"other": 1}), []),
    # A name-only declaration is never "present": boost records none.
    (json.dumps({"mcpServers": {"gh": {"command": "y"},
                                "named-only": {"command": "z"}}}), ["gh"]),
])
def test_project_mcp_present(project, text, present):
    base, _entry = project
    if text is not None:
        (base / mcpdecl.SIDECAR).write_text(text, encoding="utf-8")
    rows = [{"name": "gh", "spec": {"command": "npx"}},
            {"name": "named-only", "spec": None}]
    assert store.project_mcp_present(base, rows) == present
