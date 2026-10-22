# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`info`, `explain` and the MCP read tools describe the item that is installed.

Four ways they did not. Once `update --taps-only` moved a tap, the catalog row
(the tap's HEAD) supplied the description beside the lock's older version.
`info` on a rule or workflow never showed the update `outdated` listed. A tap
shipping one name as a skill and a workflow had the installed one described by
its namesake. And a rule installed `--local` into another repo read, over MCP,
as plainly installed.
"""
from __future__ import annotations

import json
import re
import subprocess

import pytest

from boost_cli.commands import configuration


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   capture_output=True)


def _write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _item(name, desc, version="1.0.0", body="Always use tabs."):
    return ("---\nname: %s\ndescription: %s\nversion: %s\n---\n\n# %s\n\n- %s\n"
            % (name, desc, version, name.title(), body))


def _commit(root, msg):
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", msg)


@pytest.fixture()
def mytap(boost, tmp_path):
    """A real git tap with a skill, a rule and a workflow at 1.0.0."""
    root = tmp_path / "mytap"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@boost.test")
    _git(root, "config", "user.name", "Tap")
    _write(root, "skills/alpha/SKILL.md", _item("alpha", "Alpha old description"))
    _write(root, "rules/style.mdc", _item("style", "Style rule old"))
    _write(root, "commands/ship.md", _item("ship", "Ship old"))
    _commit(root, "v1")
    boost("tap", root)
    return root


def _bump(root):
    """Move every item upstream to 2.0.0 with a new description and body."""
    for rel, name, desc in (("skills/alpha/SKILL.md", "alpha", "Alpha NEW description"),
                            ("rules/style.mdc", "style", "Style rule NEW"),
                            ("commands/ship.md", "ship", "Ship NEW")):
        _write(root, rel, _item(name, desc, "2.0.0", "Always use spaces."))
    _commit(root, "v2")


def _tool(tool, **args):
    return configuration._mcp_tool(tool, args)


def _kv(out, key):
    m = re.search(r"^  %s\s+(.*)$" % re.escape(key), out, re.MULTILINE)
    return m.group(1).rstrip() if m else None


class TestHomonymPicksTheInstalledKind:
    @pytest.fixture()
    def twin_tap(self, mytap):
        _write(mytap, "skills/wf/SKILL.md", _item("wf", "WF as SKILL"))
        _write(mytap, "workflows/wf.md", _item("wf", "WF as WORKFLOW"))
        _write(mytap, "skills/dup/SKILL.md", _item("dup", "Dup SKILL desc"))
        _write(mytap, "commands/dup.md", _item("dup", "Dup WORKFLOW desc"))
        _commit(mytap, "homonyms")
        return mytap

    def test_installed_workflow_is_described_as_the_workflow(self, boost,
                                                             twin_tap):
        boost("update", "--taps-only")
        boost("install", "wf", "--path", "workflows")
        r = boost("info", "wf")
        assert _kv(r.out, "description") == "WF as WORKFLOW"
        assert _kv(r.out, "source") == "workflows/wf.md"
        text, is_err = _tool("boost_info", name="wf")
        assert is_err is False
        assert "kind: workflow" in text.splitlines()
        assert "description: WF as WORKFLOW" in text.splitlines()

    def test_installed_skill_is_described_as_the_skill(self, boost, twin_tap):
        boost("update", "--taps-only")
        boost("install", "dup", "--path", "skills/dup")
        r = boost("info", "dup")
        assert _kv(r.out, "description") == "Dup SKILL desc"
        text, is_err = _tool("boost_info", name="dup")
        assert is_err is False
        assert "description: Dup SKILL desc" in text.splitlines()
        assert "kind: workflow" not in text


class TestDescriptionIsTheInstalledCopys:
    @pytest.fixture()
    def moved(self, boost, mytap):
        for n in ("alpha", "style", "ship"):
            boost("install", n)
        _bump(mytap)
        boost("update", "--taps-only")
        return mytap

    def test_skill_info_text_and_json(self, boost, moved):
        r = boost("info", "alpha")
        assert _kv(r.out, "description") == "Alpha old description"
        assert _kv(r.out, "upstream") == "Alpha NEW description"
        assert _kv(r.out, "version") == "1.0.0"
        data = json.loads(boost("info", "alpha", "--json").out)
        assert data["description"] == "Alpha old description"
        assert data["upstream_description"] == "Alpha NEW description"
        assert data["latest"] == "2.0.0"

    @pytest.mark.parametrize(("name", "old", "new"),
                             [("style", "Style rule old", "Style rule NEW"),
                              ("ship", "Ship old", "Ship NEW")])
    def test_rule_and_workflow_info(self, boost, moved, name, old, new):
        r = boost("info", name)
        assert _kv(r.out, "description") == old
        assert _kv(r.out, "upstream") == new
        data = json.loads(boost("info", name, "--json").out)
        assert data["description"] == old
        assert data["upstream_description"] == new

    def test_mcp_boost_info(self, boost, moved):
        for name, old, new in (("alpha", "Alpha old description",
                                "Alpha NEW description"),
                               ("style", "Style rule old", "Style rule NEW"),
                               ("ship", "Ship old", "Ship NEW")):
            lines = _tool("boost_info", name=name)[0].splitlines()
            assert "version: 1.0.0" in lines
            assert "description: %s" % old in lines
            assert "upstream description: %s" % new in lines
            assert "latest: 2.0.0 (update available)" in lines

    def test_explain_does_not_mix_versions(self, boost, moved):
        r = boost("explain", "style")
        assert "Style rule old" in r.out
        assert "NEW" not in r.out
        assert "Always use tabs." in r.out

    def test_old_lock_without_description_labels_the_tap_text(self, boost,
                                                               moved):
        from boost_cli.core import lockfile
        for get, put, name in ((lockfile.get_rule, lockfile.set_rule, "style"),
                               (lockfile.get_workflow, lockfile.set_workflow,
                                "ship")):
            row = get(name)
            del row["description"]
            put(name, row)
        r = boost("info", "style")
        assert _kv(r.out, "description") is None
        assert _kv(r.out, "upstream") == "Style rule NEW"
        r = boost("explain", "style")
        assert ("Upstream description (the tap's current version, not the "
                "installed one): Style rule NEW") in " ".join(r.out.split())
        lines = _tool("boost_info", name="ship")[0].splitlines()
        assert not any(ln.startswith("description:") for ln in lines)
        assert "upstream description: Ship NEW" in lines

    def test_unmoved_tap_shows_one_description(self, boost, mytap):
        boost("install", "alpha")
        boost("install", "style")
        r = boost("info", "style")
        assert _kv(r.out, "description") == "Style rule old"
        assert _kv(r.out, "upstream") is None
        assert _kv(r.out, "latest") is None
        assert "update available" not in r.out
        r = boost("info", "alpha")
        assert _kv(r.out, "upstream") is None
        lines = _tool("boost_info", name="style")[0].splitlines()
        assert "latest: 1.0.0" in lines
        assert not any(ln.startswith("upstream") for ln in lines)

    def test_skill_without_a_frontmatter_description(self, boost, mytap):
        # The scanner describes it by its first prose line; the installed
        # copy must read the same way, not as "no description, upstream X".
        _write(mytap, "skills/plain/SKILL.md",
               "---\nname: plain\nversion: 1.0.0\n---\n\n# Plain\n\n"
               "Does a thing from the body.\n")
        _commit(mytap, "plain")
        boost("update", "--taps-only")
        boost("install", "plain")
        r = boost("info", "plain")
        assert _kv(r.out, "description") == "Does a thing from the body."
        assert _kv(r.out, "upstream") is None
        r = boost("explain", "plain")
        assert "Does a thing from the body." in r.out
        assert "Upstream description" not in r.out
        lines = _tool("boost_info", name="plain")[0].splitlines()
        assert "description: Does a thing from the body." in lines
        assert not any(ln.startswith("upstream") for ln in lines)


class TestInfoReportsTheUpdateOutdatedLists:
    def test_rule_and_workflow_match_outdated(self, boost, mytap):
        boost("install", "style")
        boost("install", "ship")
        _bump(mytap)
        boost("update", "--taps-only")
        rows = {r["name"]: r for r in json.loads(boost("outdated", "--json").out)}
        assert rows["style"]["latest"] == "2.0.0"
        assert rows["ship"]["latest"] == "2.0.0"
        for name, kind in (("style", "rule"), ("ship", "workflow")):
            r = boost("info", name)
            assert "update available" in r.out.splitlines()[1]
            assert _kv(r.out, "latest") == "2.0.0  (update available)"
            data = json.loads(boost("info", name, "--json").out)
            assert data["latest"] == "2.0.0"
            assert data["update_available"] is True
            assert data["kind"] == kind

    def test_content_change_without_a_version_bump(self, boost, mytap):
        boost("install", "style")
        _write(mytap, "rules/style.mdc", _item("style", "Style rule old",
                                               body="Always use spaces."))
        _commit(mytap, "body only")
        boost("update", "--taps-only")
        rows = json.loads(boost("outdated", "--json").out)
        assert [(r["name"], r["reason"]) for r in rows] == [("style", "content")]
        r = boost("info", "style")
        assert _kv(r.out, "latest") == "1.0.0  (content changed)"
        assert json.loads(boost("info", "style", "--json").out)[
            "update_available"] is True
        assert "latest: 1.0.0 (content changed)" in _tool(
            "boost_info", name="style")[0].splitlines()


class TestMcpCarriesTheProjectScope:
    def test_a_local_rule_and_workflow_viewed_from_another_repo(
            self, boost, mytap, tmp_path, monkeypatch):
        from boost_cli.core import paths
        proj = tmp_path / "proj"
        (proj / ".git").mkdir(parents=True)
        other = tmp_path / "other"
        (other / ".git").mkdir(parents=True)
        monkeypatch.chdir(proj)
        boost("install", "style", "--local")
        boost("install", "ship", "--local")
        where = paths.tilde(proj.resolve())
        monkeypatch.chdir(other)

        listed = _tool("boost_list")[0].splitlines()
        assert "style v1.0.0 (mytap) [rule] [project %s]" % where in listed
        assert "ship v1.0.0 (mytap) [workflow] [project %s]" % where in listed

        lines = _tool("boost_info", name="style")[0].splitlines()
        assert "scope: project (%s)" % where in lines

        text = _tool("boost_read", name="style")[0]
        assert "installed: yes (project %s)" % where in text.splitlines()

    def test_a_user_rule_has_no_project_marker(self, boost, mytap):
        boost("install", "style")
        listed = _tool("boost_list")[0].splitlines()
        assert "style v1.0.0 (mytap) [rule]" in listed
        assert not any(ln.startswith("scope:") for ln in
                       _tool("boost_info", name="style")[0].splitlines())
        assert "installed: yes" in _tool(
            "boost_read", name="style")[0].splitlines()

    def test_a_deleted_checkout_is_marked_gone(self, boost, mytap, tmp_path,
                                               monkeypatch):
        from boost_cli.core import paths, util
        proj = tmp_path / "proj"
        (proj / ".git").mkdir(parents=True)
        monkeypatch.chdir(proj)
        boost("install", "style", "--local")
        where = paths.tilde(proj.resolve())
        monkeypatch.chdir(tmp_path)
        util.rmtree(proj)
        listed = _tool("boost_list")[0].splitlines()
        assert "style v1.0.0 (mytap) [rule] [project %s (gone)]" % where in listed
        assert "scope: project (%s (gone))" % where in _tool(
            "boost_info", name="style")[0].splitlines()


def test_a_rule_without_frontmatter_description_records_the_catalogs(
        boost, mytap):
    # The scanner derives a description from the body when the frontmatter
    # has none; the lock records that same text, so info shows it once.
    _write(mytap, "rules/bare.mdc",
           "---\nname: bare\nversion: 1.0.0\n---\n\nAlways be bare.\n")
    _commit(mytap, "bare")
    boost("update", "--taps-only")
    boost("install", "bare")
    from boost_cli.core import catalog, lockfile
    want = catalog.find("bare")[0]["description"]
    assert lockfile.get_rule("bare")["description"] == want
    r = boost("info", "bare")
    assert _kv(r.out, "upstream") is None
    data = json.loads(boost("info", "bare", "--json").out)
    assert data["description"] == want
    assert data["upstream_description"] is None
