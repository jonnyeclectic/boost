# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost_install` takes the CLI's `--local`, as `scope: "project"`.

The schema took `name` and `path` only, and `_tool_install` called
`store.install(e)` with its default user scope. Driven over stdio from a git
checkout, `{"name": "tdd-workflow", "scope": "project", "local": true}` replied
"installed ... → ~/.agents/skills/tdd-workflow" and wrote nothing into the
repository — while boost_list, boost_info and boost_search from the same
directory already reported project installs. An agent had no MCP route to the
committable install, and a guessed argument was dropped without a word.

Project scope resolves from the server's working directory, as `--local`
does, but refuses a directory with no version control marker: a user at a
terminal sees `--local`'s "starts a new one here" warning before anything is
written, and an agent cannot see where its host started the server.
"""
from __future__ import annotations

from pathlib import Path

from boost_cli.commands import configuration
from boost_cli.core import lockfile, mcp, paths, projectlock, registry


def _call(tool, **args):
    """Through the JSON-RPC handler, so a raised BoostError is the reply."""
    resp = mcp.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": tool, "arguments": args}},
        version="test", registry=configuration.REGISTRY)
    res = resp["result"]
    return res["content"][0]["text"], res.get("isError", False)


def _repo(tmp_path, monkeypatch):
    """A checkout the server runs in, from a subdirectory of it."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "src").mkdir()
    monkeypatch.chdir(repo / "src")
    return repo


def _schema():
    return {s["name"]: s for s in configuration.REGISTRY.specs()}[
        "boost_install"]["inputSchema"]


class TestTheSchemaOffersBothScopes:
    def test_scope_is_declared_with_both_values(self):
        prop = _schema()["properties"]["scope"]
        assert prop["enum"] == ["user", "project"]
        assert "refused outside a git, hg or svn checkout" in prop["description"]

    def test_scope_stays_optional(self):
        assert _schema()["required"] == ["name"]

    def test_the_description_says_where_each_lands(self):
        desc = {s["name"]: s for s in configuration.REGISTRY.specs()}[
            "boost_install"]["description"]
        assert 'pass scope "project"' in desc
        assert "the reply names where it landed" in desc


class TestAProjectInstallWritesIntoTheRepository:
    def test_it_lands_in_the_checkout_and_its_lock(self, boost, tapped,
                                                   tmp_path, monkeypatch):
        repo = _repo(tmp_path, monkeypatch)
        text, is_err = _call("boost_install", name="tdd-workflow",
                             scope="project")
        assert is_err is False
        assert (repo / ".claude" / "skills" / "tdd-workflow"
                / "SKILL.md").is_file()
        assert projectlock.get_skill(repo, "tdd-workflow") is not None
        # ...and not in the user's store, which is where it used to go.
        assert not (paths.store_dir() / "tdd-workflow").exists()
        assert lockfile.get_skill("tdd-workflow") is None
        assert ("scope: project (%s)" % paths.tilde(repo)) in text
        assert "commit .boost/" in text
        assert "copied into this repository for: " in text
        assert "linked agents" not in text

    def test_the_read_tools_see_what_it_wrote(self, boost, tapped, tmp_path,
                                              monkeypatch):
        _repo(tmp_path, monkeypatch)
        _call("boost_install", name="commit-messages", scope="project")
        listed, _ = _call("boost_list")
        assert "commit-messages v1.0.2 (fixture-tap) [project]" in listed
        info, _ = _call("boost_info", name="commit-messages")
        assert "scope: project (" in info
        found, _ = _call("boost_search", query="commit message discipline")
        hit = next(ln for ln in found.splitlines() if "commit-messages" in ln)
        assert "[installed]" in hit

    def test_a_second_project_install_is_refused_like_the_cli(
            self, boost, tapped, tmp_path, monkeypatch):
        _repo(tmp_path, monkeypatch)
        _call("boost_install", name="tdd-workflow", scope="project")
        text, is_err = _call("boost_install", name="tdd-workflow",
                             scope="project")
        assert is_err is True
        assert "already installed" in text


class TestProjectScopeNeverGuessesTheRepository:
    def test_an_unmarked_directory_is_refused_and_named(self, boost, tapped):
        # The sandbox's cwd carries no marker (tests/conftest.py checks).
        cwd = paths.tilde(Path.cwd())
        text, is_err = _call("boost_install", name="tdd-workflow",
                             scope="project")
        assert is_err is True
        assert "no repository to install into" in text
        assert cwd in text
        assert 'pass scope "user"' in text
        assert not (Path.cwd() / ".claude").exists()
        assert not (Path.cwd() / ".boost").exists()
        assert lockfile.get_skill("tdd-workflow") is None

    def test_home_is_refused(self, boost, tapped, sandbox, monkeypatch):
        monkeypatch.chdir(sandbox)
        text, is_err = _call("boost_install", name="tdd-workflow",
                             scope="project")
        assert is_err is True
        assert "this server is running in ~" in text
        assert not (paths.home() / ".boost" / "skill-lock.json").exists()

    def test_a_checkout_boost_manages_is_refused(self, boost, tapped,
                                                 monkeypatch):
        # A tap clone is a git checkout, so the marker walk finds it; writing
        # agent dirs into it plants files the next rescan indexes as the tap's.
        clone = registry.get("fixture-tap").path
        monkeypatch.chdir(clone)
        text, is_err = _call("boost_install", name="tdd-workflow",
                             scope="project")
        assert is_err is True
        assert "cannot install into this repository" in text
        assert not (clone / ".boost").exists()

    def test_an_unknown_scope_is_refused(self, boost, tapped):
        text, is_err = _call("boost_install", name="tdd-workflow",
                             scope="team")
        assert is_err is True
        assert "unknown scope 'team'" in text
        assert lockfile.get_skill("tdd-workflow") is None


class TestTheReplySaysWhichScope:
    def test_the_default_is_the_user_and_says_so(self, boost, tapped):
        text, is_err = _call("boost_install", name="tdd-workflow")
        assert is_err is False
        assert "scope: user — every project on this machine" in text
        assert lockfile.get_skill("tdd-workflow") is not None

    def test_a_user_install_beside_a_project_copy_says_so(
            self, boost, tapped, tmp_path, monkeypatch):
        repo = _repo(tmp_path, monkeypatch)
        _call("boost_install", name="commit-messages", scope="project")
        text, is_err = _call("boost_install", name="commit-messages")
        assert is_err is False
        assert ("note: commit-messages is also installed in this project (%s)"
                % paths.tilde(repo)) in text

    def test_a_project_install_beside_a_user_copy_says_so(
            self, boost, tapped, tmp_path, monkeypatch):
        _call("boost_install", name="commit-messages")
        _repo(tmp_path, monkeypatch)
        text, is_err = _call("boost_install", name="commit-messages",
                             scope="project")
        assert is_err is False
        assert "note: commit-messages is also installed for the user" in text

    def test_no_note_without_a_second_copy(self, boost, tapped):
        text, _ = _call("boost_install", name="tdd-workflow")
        assert "note:" not in text


class TestAGuessedArgumentIsNotDropped:
    def test_local_is_refused_and_the_real_arguments_named(self, boost, tapped):
        text, is_err = _call("boost_install", name="tdd-workflow", local=True)
        assert is_err is True
        assert text == ("Error: boost_install does not take 'local'\n"
                        "hint: it takes: name, path, scope")
        assert lockfile.get_skill("tdd-workflow") is None

    def test_every_boost_tool_declares_its_arguments(self):
        # A tool registered without `properties` would be left unchecked.
        for spec in configuration.REGISTRY.specs():
            assert isinstance(spec["inputSchema"].get("properties"), dict), \
                spec["name"]
