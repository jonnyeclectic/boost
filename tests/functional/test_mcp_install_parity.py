# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost_install` and its neighbours must plan an install the way `boost install` does.

Four gaps, each found by driving the MCP tools against the fixture tap:
boost_install skipped the `requires:` closure (and boost_doctor then called the
home healthy without the note CLI doctor prints), skipped the typosquat
warning, could not reach either copy of a name one tap ships twice, and
str()-coerced a non-string argument into a lookup for the skill `'None'`.
"""
from __future__ import annotations

import subprocess

import pytest

from boost_cli.commands import configuration
from boost_cli.core import lockfile, mcp


def _tool(tool, **args):
    return configuration._mcp_tool(tool, args)


def _call(tool, **args):
    """Through the JSON-RPC handler, so a raised BoostError is the reply."""
    resp = mcp.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": tool, "arguments": args}},
        version="test", registry=configuration.REGISTRY)
    res = resp["result"]
    return res["content"][0]["text"], res.get("isError", False)


def _git_tap(root, skills: dict[str, str]):
    """A local tap: ``skills`` maps a rel dir to a SKILL.md body."""
    for rel, text in skills.items():
        (root / rel).mkdir(parents=True)
        (root / rel / "SKILL.md").write_text(text, encoding="utf-8")

    def run(*a):
        subprocess.run(a, cwd=root, check=True, capture_output=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@boost.test")
    run("git", "config", "user.name", "T")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "skills")
    return root


def _md(name, desc, version="1.0.0"):
    return ("---\nname: %s\ndescription: %s\nversion: %s\n---\n\n# %s\n\n%s.\n"
            % (name, desc, version, name, desc))


class TestInstallPullsInRequires:
    def test_the_requires_closure_is_installed_first(self, boost, tapped):
        text, is_err = _tool("boost_install", name="jira-integration")
        assert is_err is False
        lines = text.splitlines()
        assert lines[0] == ("pulling in 1 dependency required by your "
                            "selection: commit-messages")
        assert lines[1].startswith("installed commit-messages v1.0.2 from ")
        assert [ln for ln in lines if ln.startswith("installed ")][1] \
            .startswith("installed jira-integration v2.1.0 from ")
        assert set(lockfile.all_installed()["skill"]) == {"commit-messages",
                                                    "jira-integration"}
        # ...the same two the CLI installs for the same request.
        assert "WARNING" not in text

    def test_a_met_requirement_is_not_reinstalled(self, boost, tapped):
        boost("install", "commit-messages")
        text, is_err = _tool("boost_install", name="jira-integration")
        assert is_err is False
        assert "pulling in" not in text
        assert text.startswith("installed jira-integration v2.1.0 from ")

    def test_a_refused_request_installs_none_of_its_dependencies(
            self, boost, tapped):
        boost("install", "jira-integration", "--no-deps")
        text, is_err = _call("boost_install", name="jira-integration")
        assert is_err is True
        assert "already installed" in text
        assert "commit-messages" not in lockfile.all_installed()["skill"]

    def test_a_failed_dependency_is_a_warning_on_a_success(
            self, boost, tapped, monkeypatch):
        from boost_cli.core import store
        from boost_cli.errors import BoostError
        real = store.install

        def install(e, *a, **kw):
            if e["name"] == "commit-messages":
                raise BoostError("disk full")
            return real(e, *a, **kw)
        monkeypatch.setattr(store, "install", install)
        text, is_err = _call("boost_install", name="jira-integration")
        assert is_err is False
        lines = text.splitlines()
        i = lines.index("WARNING — check before you rely on this install:")
        assert "required skill 'commit-messages' was not installed: disk full" \
            in lines[i + 1:]
        assert set(lockfile.all_installed()["skill"]) == {"jira-integration"}

    def test_a_failure_of_the_requested_item_is_an_error(
            self, boost, tapped, monkeypatch):
        from boost_cli.core import store
        from boost_cli.errors import BoostError
        real = store.install

        def install(e, *a, **kw):
            if e["name"] == "jira-integration":
                raise BoostError("disk full")
            return real(e, *a, **kw)
        monkeypatch.setattr(store, "install", install)
        text, is_err = _call("boost_install", name="jira-integration")
        assert is_err is True
        assert text.startswith("Error: disk full")

    def test_doctor_carries_the_cli_prerequisite_note(self, boost, tapped):
        boost("install", "jira-integration", "--no-deps")
        text, is_err = _tool("boost_doctor")
        assert ("note: 1 installed item declares 1 prerequisite not installed "
                "(commit-messages) — `boost install commit-messages`") in text
        # A note, as on the CLI, not an issue.
        assert text.endswith("healthy — no issues found")
        assert is_err is False

    def test_doctor_says_nothing_when_requirements_are_met(self, boost, tapped):
        boost("install", "jira-integration")
        text, _ = _tool("boost_doctor")
        assert "note:" not in text


class TestInstallWarnsAboutLookalikes:
    def test_a_cross_tap_lookalike_is_named_in_the_reply(
            self, boost, tapped, tmp_path):
        boost("tap", _git_tap(tmp_path / "evil", {
            "skills/brainstormimg": _md("brainstormimg", "Totally legit")}))
        text, is_err = _tool("boost_install", name="brainstormimg")
        assert is_err is False
        lines = text.splitlines()
        i = lines.index("WARNING — check before you rely on this install:")
        assert lines[i + 1] == ("brainstormimg (evil) closely resembles "
                                "brainstorming (fixture-tap) — double-check "
                                "you meant this one")
        # The CLI prints the same words.
        cli = boost("install", "brainstormimg", "--dry-run", expect=None)
        assert lines[i + 1] in cli.out + cli.err


@pytest.fixture()
def twin_tap(boost, sandbox, tmp_path):
    boost("tap", _git_tap(tmp_path / "dup", {
        "a/twin": _md("twin", "first copy of twin"),
        "b/twin": _md("twin", "second copy of twin different")}))
    return "dup"


class TestOneTapShippingANameTwice:
    def test_search_names_the_path_of_each_copy(self, twin_tap):
        text, _ = _tool("boost_search", query="twin")
        assert "twin — first copy of twin (dup) [path: a/twin]" in text
        assert "twin — second copy of twin different (dup) [path: b/twin]" \
            in text

    def test_the_error_hint_names_the_argument_the_tool_takes(self, twin_tap):
        for tool in ("boost_read", "boost_info", "boost_install"):
            text, is_err = _call(tool, name="twin")
            assert is_err is True, tool
            assert text == ("Error: 'twin' matches 2 different skills in dup: "
                            "a/twin, b/twin\nhint: call again with \"path\" "
                            "set to one of the above, e.g. {\"name\": "
                            "\"dup:twin\", \"path\": \"a/twin\"}"), tool

    def test_the_hinted_call_resolves(self, twin_tap):
        """The hint's name is tap-qualified, so following it to the letter
        works — the bare name could resolve to another tap's copy."""
        text, is_err = _call("boost_info", name="dup:twin", path="a/twin")
        assert is_err is False, text
        assert "first copy of twin" in text

    def test_read_shows_either_copy(self, twin_tap):
        a, err_a = _tool("boost_read", name="twin", path="a/twin")
        b, err_b = _tool("boost_read", name="twin", path="b/twin")
        assert (err_a, err_b) == (False, False)
        assert "first copy of twin." in a and "second copy" not in a
        assert "second copy of twin different." in b

    def test_read_says_installed_only_for_the_installed_copy(self, twin_tap):
        _tool("boost_install", name="twin", path="a/twin")
        a, _ = _tool("boost_read", name="twin", path="a/twin")
        b, _ = _tool("boost_read", name="twin", path="b/twin")
        assert "installed: yes" in a
        assert "installed: no" in b

    def test_info_and_install_take_the_path(self, twin_tap):
        text, is_err = _tool("boost_info", name="twin", path="b/twin")
        assert is_err is False
        assert "description: second copy of twin different" in text
        text, is_err = _tool("boost_install", name="twin", path="b/twin")
        assert is_err is False
        assert text.startswith("installed twin v1.0.0 from dup")
        assert lockfile.get_skill("twin") is not None

    def test_a_path_matching_no_copy_is_refused(self, twin_tap):
        text, is_err = _call("boost_install", name="twin", path="c/twin")
        assert is_err is True
        assert text.startswith("Error: no copy of 'twin' whose path ends "
                               "with 'c/twin'")


class TestNonStringArgumentsAreRefused:
    @pytest.mark.parametrize("tool,key", [
        ("boost_search", "query"), ("boost_info", "name"),
        ("boost_read", "name"), ("boost_install", "name"),
        ("boost_install", "path"), ("boost_discover_github", "query")])
    @pytest.mark.parametrize("value,label", [
        (None, "null"), (["a", "b"], "list"), (3, "int")])
    def test_the_field_and_type_are_named(self, sandbox, monkeypatch, tool,
                                          key, value, label):
        monkeypatch.setattr(configuration.shutil, "which", lambda _c: "/gh")
        args = {"name": "x"} if key == "path" else {}
        args[key] = value
        text, is_err = _call(tool, **args)
        assert is_err is True
        assert text == ('Error: invalid argument: "%s" must be a string, '
                        "got %s" % (key, label))
