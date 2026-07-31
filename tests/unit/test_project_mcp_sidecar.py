"""Unit tests: a project-scoped install records its MCP servers in the repo.

``boost install <skill> --scope project`` is a promise about blast radius: the
skill lands inside this repo, committable, affecting nobody else's machine. Its
declared MCP servers did not keep that promise — they were registered at *user*
scope, globally, whatever scope the skill was installed at, because
``_offer_mcp`` never read ``res.scope`` and ``_register_mcp_server`` took no
scope at all.

The document logic for doing it properly already existed and had no callers:
``mcpdecl.merge_into`` merges declared servers into an ``.mcp.json`` — the
committable file agents already read — stamping each entry with a marker naming
the skill that asked for it, and ``mcpdecl.strip_owned`` reverses exactly those.
Both are pure. These tests cover the file I/O that wires them up, which lives in
``store`` because ``mcpdecl`` is deliberately I/O-free.

The properties that matter are all about *not* destroying someone else's work:
a hand-configured server, another skill's server, and any unrelated key in the
document must survive both an install and an uninstall.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import mcpdecl, store

pytestmark = pytest.mark.usefixtures("sandbox")


def _rows(*names):
    """Registrable declaration rows, the shape `declared_mcp_servers` returns."""
    return [{"name": n, "spec": {"command": "npx", "args": ["-y", n]}}
            for n in names]


def _read(base):
    return json.loads((base / mcpdecl.SIDECAR).read_text(encoding="utf-8"))


def _servers(base):
    return _read(base).get(mcpdecl.SERVERS_KEY, {})


class TestRegister:
    def test_writes_a_sidecar_naming_the_skill(self, tmp_path):
        added = store.register_project_mcp(tmp_path, _rows("gh"), "my-skill")
        assert added == ["gh"]
        entry = _servers(tmp_path)["gh"]
        assert entry["command"] == "npx"
        assert entry[mcpdecl.MARKER_KEY] == "my-skill"

    def test_the_file_is_json_a_human_can_review(self, tmp_path):
        # The whole point of project scope over `mcp add` is that it lands in a
        # file you can read in a diff and commit.
        store.register_project_mcp(tmp_path, _rows("gh"), "sk")
        text = (tmp_path / mcpdecl.SIDECAR).read_text(encoding="utf-8")
        assert text.endswith("\n")
        assert "\n  " in text, "should be indented, not one line"

    def test_an_existing_hand_written_server_is_never_overwritten(self, tmp_path):
        (tmp_path / mcpdecl.SIDECAR).write_text(json.dumps(
            {mcpdecl.SERVERS_KEY: {"gh": {"command": "mine"}}}), encoding="utf-8")
        added = store.register_project_mcp(tmp_path, _rows("gh"), "sk")
        assert added == []
        assert _servers(tmp_path)["gh"] == {"command": "mine"}, \
            "a server the user configured by hand must survive untouched"

    def test_unrelated_keys_survive(self, tmp_path):
        (tmp_path / mcpdecl.SIDECAR).write_text(
            json.dumps({"inputs": [1, 2], mcpdecl.SERVERS_KEY: {}}),
            encoding="utf-8")
        store.register_project_mcp(tmp_path, _rows("gh"), "sk")
        assert _read(tmp_path)["inputs"] == [1, 2]

    def test_a_corrupt_sidecar_does_not_lose_the_install(self, tmp_path):
        # Best-effort, like declared_mcp_servers: the skill is already on disk
        # by this point, so an unreadable sidecar must not raise.
        (tmp_path / mcpdecl.SIDECAR).write_text("{not json", encoding="utf-8")
        added = store.register_project_mcp(tmp_path, _rows("gh"), "sk")
        assert added == ["gh"]
        assert "gh" in _servers(tmp_path)

    def test_no_rows_writes_nothing(self, tmp_path):
        assert store.register_project_mcp(tmp_path, [], "sk") == []
        assert not (tmp_path / mcpdecl.SIDECAR).exists(), \
            "a skill with no servers must not create an empty sidecar"

    def test_a_name_only_declaration_is_not_invented(self, tmp_path):
        # `registrable` filters these out: boost will not invent a command line.
        assert store.register_project_mcp(
            tmp_path, [{"name": "gh", "spec": {}}], "sk") == []
        assert not (tmp_path / mcpdecl.SIDECAR).exists()

    def test_two_skills_each_keep_their_own_marker(self, tmp_path):
        store.register_project_mcp(tmp_path, _rows("a"), "one")
        store.register_project_mcp(tmp_path, _rows("b"), "two")
        servers = _servers(tmp_path)
        assert servers["a"][mcpdecl.MARKER_KEY] == "one"
        assert servers["b"][mcpdecl.MARKER_KEY] == "two"


class TestUnregister:
    def test_removes_only_this_skills_servers(self, tmp_path):
        store.register_project_mcp(tmp_path, _rows("a"), "one")
        store.register_project_mcp(tmp_path, _rows("b"), "two")
        removed = store.unregister_project_mcp(tmp_path, "one")
        assert removed == ["a"]
        assert list(_servers(tmp_path)) == ["b"], \
            "another skill's server must survive this uninstall"

    def test_a_hand_written_server_survives_uninstall(self, tmp_path):
        (tmp_path / mcpdecl.SIDECAR).write_text(json.dumps(
            {mcpdecl.SERVERS_KEY: {"mine": {"command": "x"}}}), encoding="utf-8")
        store.register_project_mcp(tmp_path, _rows("gh"), "sk")
        store.unregister_project_mcp(tmp_path, "sk")
        assert list(_servers(tmp_path)) == ["mine"]

    def test_unrelated_keys_survive_uninstall(self, tmp_path):
        (tmp_path / mcpdecl.SIDECAR).write_text(
            json.dumps({"inputs": [7], mcpdecl.SERVERS_KEY: {}}),
            encoding="utf-8")
        store.register_project_mcp(tmp_path, _rows("gh"), "sk")
        store.unregister_project_mcp(tmp_path, "sk")
        assert _read(tmp_path)["inputs"] == [7]

    def test_no_sidecar_is_not_an_error(self, tmp_path):
        assert store.unregister_project_mcp(tmp_path, "sk") == []

    def test_a_corrupt_sidecar_is_not_an_error(self, tmp_path):
        (tmp_path / mcpdecl.SIDECAR).write_text("{not json", encoding="utf-8")
        assert store.unregister_project_mcp(tmp_path, "sk") == []

    def test_nothing_owned_leaves_the_file_untouched(self, tmp_path):
        original = json.dumps({mcpdecl.SERVERS_KEY: {"mine": {"command": "x"}}})
        (tmp_path / mcpdecl.SIDECAR).write_text(original, encoding="utf-8")
        assert store.unregister_project_mcp(tmp_path, "sk") == []
        assert (tmp_path / mcpdecl.SIDECAR).read_text(encoding="utf-8") == original, \
            "removing nothing must not rewrite the file"

    def test_register_then_unregister_round_trips(self, tmp_path):
        store.register_project_mcp(tmp_path, _rows("a", "b"), "sk")
        assert sorted(_servers(tmp_path)) == ["a", "b"]
        assert store.unregister_project_mcp(tmp_path, "sk") == ["a", "b"]
        assert _servers(tmp_path) == {}


class TestAnUnwritableSidecarNeverCrashesAnInstall:
    """The write is the half that runs AFTER the install is already committed.

    By the time `register_project_mcp` is called the skill is materialized, the
    project lock is written and the journal is logged. An unwritable
    `.mcp.json` — read-only checkout, root-owned file, full disk — must not
    turn that completed install into a traceback, which is the same contract
    `_load_sidecar` already keeps for a corrupt file on the way in.
    """

    @staticmethod
    def _unwritable(monkeypatch):
        def boom(*_a, **_k):
            raise OSError(13, "Permission denied")
        monkeypatch.setattr(store.Path, "write_text", boom)

    def test_register_reports_nothing_recorded_instead_of_raising(
            self, tmp_path, monkeypatch):
        self._unwritable(monkeypatch)
        assert store.register_project_mcp(tmp_path, _rows("gh"), "sk") == []

    def test_unregister_reports_nothing_removed_instead_of_raising(
            self, tmp_path, monkeypatch):
        (tmp_path / mcpdecl.SIDECAR).write_text(json.dumps(
            {mcpdecl.SERVERS_KEY: {"gh": {"command": "npx",
                                          mcpdecl.MARKER_KEY: "sk"}}}),
            encoding="utf-8")
        self._unwritable(monkeypatch)
        assert store.unregister_project_mcp(tmp_path, "sk") == []

    def test_a_failed_write_is_not_reported_as_success(self, tmp_path,
                                                       monkeypatch):
        # The return value is what the install report prints, so it must not
        # name servers that were never written.
        self._unwritable(monkeypatch)
        recorded = store.register_project_mcp(tmp_path, _rows("a", "b"), "sk")
        assert recorded == [], \
            "claiming a server was recorded when the file could not be " \
            "written is worse than the failure itself"
