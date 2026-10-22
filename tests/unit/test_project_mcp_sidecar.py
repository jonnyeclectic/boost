# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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
from typing import ClassVar

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

    def test_a_corrupt_sidecar_is_refused_not_rebuilt(self, tmp_path):
        # It used to be rebuilt from an empty view, which dropped every server
        # the user had in it. It must not raise either: the skill is already
        # on disk by this point.
        sidecar = tmp_path / mcpdecl.SIDECAR
        sidecar.write_text("{not json", encoding="utf-8")
        added, err = store.record_project_mcp(tmp_path, _rows("gh"), "sk")
        assert added == []
        assert err is not None and err.startswith("%s: invalid JSON (" % sidecar)
        assert sidecar.read_text(encoding="utf-8") == "{not json"
        assert store.register_project_mcp(tmp_path, _rows("gh"), "sk") == []

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

    @pytest.mark.parametrize("original", ['{"other": 1}', "{}",
                                          '{"mcpServers": null}'])
    def test_no_servers_key_is_not_given_one(self, tmp_path, original):
        (tmp_path / mcpdecl.SIDECAR).write_text(original, encoding="utf-8")
        assert store.forget_project_mcp(tmp_path, "sk") == ([], None)
        assert (tmp_path / mcpdecl.SIDECAR).read_text(encoding="utf-8") == original

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


class TestAnUnusableSidecarIsNeverOverwritten:
    """Finding: a trailing comma, or a list-valued ``mcpServers``, was rebuilt.

    The file is rewritten whole from the parsed view, so an install that could
    not parse it wrote back only its own server and the user's were gone, with
    ``✓ recorded`` and rc 0. Refuse, name the file and the cause, and leave the
    bytes exactly as they were — both on install and on uninstall.
    """

    TRAILING_COMMA = ('{"mcpServers": {"postgres": {"command": "pg-mcp", '
                      '"args": ["--db","prod"]}, "sentry": {"command": '
                      '"sentry-mcp"},}}')
    LIST_SERVERS = '{"mcpServers": [{"name":"postgres","command":"pg"}]}'

    @pytest.mark.parametrize("text, cause", [
        (TRAILING_COMMA, "invalid JSON ("),
        (LIST_SERVERS, "expected 'mcpServers' to be an object, found list"),
        ("[1, 2]", "expected a JSON object, found list"),
        ('{"mcpServers": "x"}', "expected 'mcpServers' to be an object, "
                                "found str"),
    ])
    def test_register_refuses_and_keeps_the_bytes(self, tmp_path, text, cause):
        sidecar = tmp_path / mcpdecl.SIDECAR
        sidecar.write_bytes(text.encode("utf-8"))
        added, err = store.record_project_mcp(tmp_path, _rows("gh"), "sk")
        assert added == []
        assert err is not None
        assert err.startswith("%s: " % sidecar)
        assert cause in err
        assert sidecar.read_bytes() == text.encode("utf-8")

    def test_unregister_refuses_and_keeps_the_bytes(self, tmp_path):
        sidecar = tmp_path / mcpdecl.SIDECAR
        text = '{"mcpServers": [{"x-boost-skill": "sk"}]}'
        sidecar.write_bytes(text.encode("utf-8"))
        removed, err = store.forget_project_mcp(tmp_path, "sk")
        assert removed == []
        assert err == ("%s: expected 'mcpServers' to be an object, found list"
                       % sidecar)
        assert sidecar.read_bytes() == text.encode("utf-8")

    def test_a_null_servers_key_is_empty_not_corrupt(self, tmp_path):
        (tmp_path / mcpdecl.SIDECAR).write_text('{"mcpServers": null}',
                                                encoding="utf-8")
        assert store.record_project_mcp(tmp_path, _rows("gh"), "sk") == (
            ["gh"], None)
        assert list(_servers(tmp_path)) == ["gh"]

    def test_a_missing_file_is_not_an_error(self, tmp_path):
        assert store.record_project_mcp(tmp_path, _rows("gh"), "sk") == (
            ["gh"], None)
        assert store.forget_project_mcp(tmp_path / "nowhere", "sk") == ([], None)

    def test_a_failed_write_names_the_file(self, tmp_path, monkeypatch):
        def boom(*_a, **_k):
            raise OSError(13, "Permission denied")
        monkeypatch.setattr(store.Path, "write_text", boom)
        sidecar = tmp_path / mcpdecl.SIDECAR
        assert store.record_project_mcp(tmp_path, _rows("gh"), "sk") == (
            [], "%s: could not be written" % sidecar)

    def test_already_present_is_no_error(self, tmp_path):
        store.register_project_mcp(tmp_path, _rows("gh"), "one")
        assert store.record_project_mcp(tmp_path, _rows("gh"), "two") == (
            [], None)


def _project_skill(base, name, sidecar=None, frontmatter=""):
    """Put an installed project skill on disk and in the project lock."""
    from boost_cli.core import projectlock
    rel = ".claude/skills/%s" % name
    d = base / rel
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: %s\n%s---\nbody\n"
                                % (name, frontmatter), encoding="utf-8")
    if sidecar is not None:
        (d / mcpdecl.SIDECAR).write_text(json.dumps(
            {mcpdecl.SERVERS_KEY: {s: {"command": "npx"} for s in sidecar}}),
            encoding="utf-8")
    projectlock.set_skill(base, name, {
        "kind": "skill", "materializations": [{"agent": "claude-code",
                                               "path": rel}]})


class TestAServerAnotherSkillDeclaresSurvives:
    """Finding: uninstalling alpha removed the server beta still declared.

    ``merge_into`` skips a name already present, so beta's claim was never
    written and ``strip_owned`` matched alpha's marker alone. Reference
    counting is by declaration: the remaining project skills' declarations
    keep the server, re-marked to one of them so its uninstall removes it.
    """

    def test_kept_and_re_marked_to_the_remaining_declarer(self, tmp_path):
        _project_skill(tmp_path, "beta", sidecar=["gh"])
        store.register_project_mcp(tmp_path, _rows("gh", "solo"), "alpha")
        assert store.forget_project_mcp(tmp_path, "alpha") == (["solo"], None)
        assert _servers(tmp_path) == {
            "gh": {"command": "npx", "args": ["-y", "gh"],
                   mcpdecl.MARKER_KEY: "beta"}}

    def test_the_last_declarer_removes_it(self, tmp_path):
        from boost_cli.core import projectlock
        _project_skill(tmp_path, "beta", sidecar=["gh"])
        store.register_project_mcp(tmp_path, _rows("gh"), "alpha")
        store.forget_project_mcp(tmp_path, "alpha")
        projectlock.remove_skill(tmp_path, "beta")
        assert store.forget_project_mcp(tmp_path, "beta") == (["gh"], None)
        # alpha's install created the file, so the last uninstall removes it.
        assert not (tmp_path / mcpdecl.SIDECAR).exists()
        assert store.SIDECAR_CREATED_KEY not in projectlock.read(tmp_path)

    def test_a_name_only_declaration_counts(self, tmp_path):
        _project_skill(tmp_path, "beta", frontmatter="mcp: gh\n")
        store.register_project_mcp(tmp_path, _rows("gh"), "alpha")
        assert store.forget_project_mcp(tmp_path, "alpha") == ([], None)
        assert _servers(tmp_path)["gh"][mcpdecl.MARKER_KEY] == "beta"

    def test_the_first_declarer_by_name_takes_it(self, tmp_path):
        _project_skill(tmp_path, "zeta", sidecar=["gh"])
        _project_skill(tmp_path, "beta", sidecar=["gh"])
        store.register_project_mcp(tmp_path, _rows("gh"), "alpha")
        store.forget_project_mcp(tmp_path, "alpha")
        assert _servers(tmp_path)["gh"][mcpdecl.MARKER_KEY] == "beta"

    def test_an_undeclared_server_still_goes(self, tmp_path):
        _project_skill(tmp_path, "beta", sidecar=["other"])
        store.register_project_mcp(tmp_path, _rows("gh"), "alpha")
        assert store.forget_project_mcp(tmp_path, "alpha") == (["gh"], None)

    def test_an_unreadable_remaining_skill_removes_nothing(self, tmp_path):
        # A teammate's clone that never synced beta: what beta declares is
        # unknown, so nothing is removed and the file is not rewritten.
        from boost_cli.core import projectlock
        projectlock.set_skill(tmp_path, "beta", {
            "kind": "skill",
            "materializations": [{"agent": "claude-code",
                                  "path": ".claude/skills/beta"}]})
        store.register_project_mcp(tmp_path, _rows("gh"), "alpha")
        before = (tmp_path / mcpdecl.SIDECAR).read_bytes()
        assert store.forget_project_mcp(tmp_path, "alpha") == ([], None)
        assert (tmp_path / mcpdecl.SIDECAR).read_bytes() == before

    def test_a_lock_path_outside_the_repo_is_not_read(self, tmp_path):
        from boost_cli.core import projectlock
        outside = tmp_path / "outside"
        (outside / "beta").mkdir(parents=True)
        (outside / "beta" / "SKILL.md").write_text(
            "---\nname: beta\nmcp: gh\n---\n", encoding="utf-8")
        repo = tmp_path / "repo"
        repo.mkdir()
        projectlock.set_skill(repo, "beta", {
            "kind": "skill",
            "materializations": [{"agent": "claude-code",
                                  "path": "../outside/beta"}]})
        store.register_project_mcp(repo, _rows("gh"), "alpha")
        assert store.forget_project_mcp(repo, "alpha") == ([], None), \
            "an escaping lock path is unreadable, so nothing is removed"
        assert _servers(repo)["gh"][mcpdecl.MARKER_KEY] == "alpha"

    def test_a_second_materialization_is_tried(self, tmp_path):
        from boost_cli.core import projectlock
        _project_skill(tmp_path, "beta", sidecar=["gh"])
        entry = projectlock.get_skill(tmp_path, "beta")
        entry["materializations"].insert(
            0, {"agent": "cursor", "path": ".cursor/skills/beta"})
        projectlock.set_skill(tmp_path, "beta", entry)
        store.register_project_mcp(tmp_path, _rows("gh"), "alpha")
        assert store.forget_project_mcp(tmp_path, "alpha") == ([], None)
        assert _servers(tmp_path)["gh"][mcpdecl.MARKER_KEY] == "beta"


class TestTheFileKeepsItsOwnStyle:
    """Finding: a round trip rewrote a committed ``.mcp.json`` sorted, 2-space
    and ``\\u``-escaped, and left ``{"mcpServers": {}}`` in a repo that had no
    such file before the install.
    """

    MINE: ClassVar[dict] = {"mine": {"command": "node", "args": ["srv.js"],
                     "env": {"NOTE": "café"}}}

    def _lock(self, base):
        from boost_cli.core import projectlock
        projectlock.set_skill(base, "sk", {"kind": "skill",
                                           "materializations": []})
        projectlock.remove_skill(base, "sk")

    @pytest.mark.parametrize(("text", "want"), [
        (None, (2, "\n")),
        ("", (2, "\n")),
        ('{"a": 1}', (None, "")),
        ('{"a": 1}\n', (None, "\n")),
        ('{\n    "a": 1\n}\n', (4, "\n")),
        ('{\n\t"a": 1\n}', ("\t", "")),
        ('{\n"a": 1\n}\n', (2, "\n")),
    ])
    def test_sidecar_style(self, text, want):
        assert store.sidecar_style(text) == want

    def test_a_pretty_printed_file_round_trips_byte_identical(self, tmp_path):
        self._lock(tmp_path)
        f = tmp_path / mcpdecl.SIDECAR
        original = json.dumps({mcpdecl.SERVERS_KEY: self.MINE}, indent=4,
                              ensure_ascii=False) + "\n"
        f.write_text(original, encoding="utf-8")
        assert store.register_project_mcp(tmp_path, _rows("gh"), "sk") == ["gh"]
        text = f.read_text(encoding="utf-8")
        assert '\n        "gh": {' in text
        assert "café" in text and "\\u00e9" not in text
        # Insertion order, not sorted: the user's server stays first.
        assert text.index('"mine"') < text.index('"gh"')
        assert text.index('"command": "node"') < text.index('"args"')
        assert store.unregister_project_mcp(tmp_path, "sk") == ["gh"]
        assert f.read_text(encoding="utf-8") == original

    def test_a_compact_inner_object_keeps_indent_order_and_text(self, tmp_path):
        self._lock(tmp_path)
        f = tmp_path / mcpdecl.SIDECAR
        f.write_text('{\n    "mcpServers": {\n        "mine": {"command": '
                     '"node", "args": ["srv.js"], "env": {"NOTE": '
                     '"café"}}\n    }\n}\n', encoding="utf-8")
        store.register_project_mcp(tmp_path, _rows("gh"), "sk")
        store.unregister_project_mcp(tmp_path, "sk")
        text = f.read_text(encoding="utf-8")
        assert text == json.dumps({mcpdecl.SERVERS_KEY: self.MINE}, indent=4,
                                  ensure_ascii=False) + "\n"

    def test_a_file_boost_created_is_removed_when_empty_again(self, tmp_path):
        from boost_cli.core import projectlock
        self._lock(tmp_path)
        store.register_project_mcp(tmp_path, _rows("gh"), "sk")
        assert projectlock.read(tmp_path)[store.SIDECAR_CREATED_KEY] is True
        assert store.forget_project_mcp(tmp_path, "sk") == (["gh"], None)
        assert not (tmp_path / mcpdecl.SIDECAR).exists()
        assert store.SIDECAR_CREATED_KEY not in projectlock.read(tmp_path)

    def test_a_file_the_user_had_is_kept_when_empty_again(self, tmp_path):
        from boost_cli.core import projectlock
        self._lock(tmp_path)
        f = tmp_path / mcpdecl.SIDECAR
        f.write_text('{"mcpServers": {}}\n', encoding="utf-8")
        store.register_project_mcp(tmp_path, _rows("gh"), "sk")
        assert store.SIDECAR_CREATED_KEY not in projectlock.read(tmp_path)
        store.forget_project_mcp(tmp_path, "sk")
        assert f.read_text(encoding="utf-8") == '{"mcpServers": {}}\n'

    def test_a_created_file_with_other_keys_is_kept(self, tmp_path):
        self._lock(tmp_path)
        f = tmp_path / mcpdecl.SIDECAR
        store.register_project_mcp(tmp_path, _rows("gh"), "sk")
        doc = json.loads(f.read_text(encoding="utf-8"))
        doc["inputs"] = [1]
        f.write_text(json.dumps(doc), encoding="utf-8")
        store.forget_project_mcp(tmp_path, "sk")
        assert json.loads(f.read_text(encoding="utf-8")) == {
            "inputs": [1], mcpdecl.SERVERS_KEY: {}}

    def test_no_project_lock_records_no_creation(self, tmp_path):
        store.register_project_mcp(tmp_path, _rows("gh"), "sk")
        assert not (tmp_path / ".boost").exists()
