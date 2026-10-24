# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a rule or workflow uninstall under a read-only store.

Measured before this: with ``~/.agents/skills`` at 555 a skill uninstall
refused up front, but a rule's removed the CLAUDE.md block and every agent's
rule file, and a workflow's every command file and its store copy, before
the lock save failed. `boost list` then still showed both installed, with
nothing of either on disk. The rule and workflow branches now ask the skill
branch's question first.

And the agents line: a row install refused (``unwritable``) was named in
`list`, `info` and `stats` as reached, while install and `doctor` said "not
written".
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest

from boost_cli import cli
from boost_cli.core import catalog, integrity, lockfile, paths, registry, store
from boost_cli.errors import BoostError

requires_posix_modes = pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX permission semantics")
requires_unprivileged = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root ignores the read-only mode the test relies on")

RULE = "---\nname: py-style\ndescription: Python style.\n---\n\nUse ruff.\n"
WORKFLOW = ("---\nname: review-pr\ndescription: Review a PR.\n---\n\n"
            "Review the diff.\n")


@pytest.fixture()
def installed(sandbox, fixture_tap_src, tmp_path):
    """A tap with one rule and one workflow, both installed."""
    src = tmp_path / "ro-mat-tap"
    shutil.copytree(fixture_tap_src, src, symlinks=True)
    (src / "rules").mkdir()
    (src / "rules" / "py-style.mdc").write_text(RULE, encoding="utf-8")
    (src / "commands").mkdir()
    (src / "commands" / "review-pr.md").write_text(WORKFLOW,
                                                   encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=src, check=True,
                   capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "add"], cwd=src, check=True,
                   capture_output=True)
    catalog.rebuild_tap(registry.add(str(src)))
    store.install(catalog.resolve_one("py-style"))
    store.install(catalog.resolve_one("review-pr"))
    return src


def _files(entry) -> list[str]:
    return sorted(m["path"] for m in entry["materializations"]
                  if os.path.isfile(m["path"]))


@requires_posix_modes
@requires_unprivileged
class TestReadOnlyStore:
    @pytest.mark.parametrize("name,get", [
        ("py-style", lockfile.get_rule),
        ("review-pr", lockfile.get_workflow)])
    def test_uninstall_refuses_before_removing_anything(self, installed,
                                                        name, get):
        before = get(name)
        files = _files(before)
        assert files
        d = paths.store_dir()
        d.chmod(0o555)
        try:
            with pytest.raises(BoostError) as caught:
                store.uninstall(name)
            assert _files(get(name)) == files
        finally:
            d.chmod(0o755)
        assert str(caught.value) == "cannot uninstall %s: %s is not " \
            "writable" % (name, paths.tilde(d))
        assert caught.value.hint == "run `chmod u+w %s`, then re-run" % (
            paths.tilde(d))
        assert get(name) == before
        # ...so the same command finishes once the dir allows it.
        store.uninstall(name)
        assert get(name) is None
        assert _files(before) == []

    def test_the_cli_exits_one_with_the_claude_md_block_intact(
            self, installed, capsys):
        claude_md = paths.home() / ".claude" / "CLAUDE.md"
        text = claude_md.read_text(encoding="utf-8")
        assert "Use ruff." in text
        d = paths.store_dir()
        d.chmod(0o555)
        try:
            rc = cli.main(["uninstall", "py-style"])
        finally:
            d.chmod(0o755)
        assert rc == 1
        assert "cannot uninstall py-style" in capsys.readouterr().err
        assert claude_md.read_text(encoding="utf-8") == text


class TestWrittenAgentNamesSkipsRefusedRows:
    @staticmethod
    def _row(agent, **extra):
        return {"agent": agent, "mode": "file", "sha256": "x" * 64,
                "path": str(paths.home() / ("%s.md" % agent)), **extra}

    @pytest.mark.parametrize("kind", ["rule", "workflow"])
    def test_an_unwritable_row_is_not_named(self, sandbox, kind):
        e = {"kind": kind, "materializations": [
            self._row("cursor", unwritable=True), self._row("claude-code"),
            self._row("windsurf", unwritable=True)]}
        assert integrity.written_agent_names(kind, e) == ["claude-code"]
        # the record still holds all three, for uninstall
        assert len(lockfile.agent_names(kind, e)) == 3

    def test_a_false_flag_is_no_refusal(self, sandbox):
        e = {"kind": "rule", "materializations": [
            self._row("cursor", unwritable=False)]}
        assert integrity.written_agent_names("rule", e) == ["cursor"]

    def test_every_row_refused_names_none_and_is_not_unreachable(self,
                                                                 sandbox):
        """Doctor names the `chmod` for it; enabling an agent is not it."""
        e = {"kind": "rule", "materializations": [
            self._row("cursor", unwritable=True)]}
        assert integrity.written_agent_names("rule", e) == []
        assert integrity.reaches_no_agent("rule", e) is False
        assert integrity.materialized_status("py-style", e, "rule") == \
            integrity.STATUS_MISSING


@requires_posix_modes
@requires_unprivileged
def test_list_and_info_drop_an_agent_install_could_not_write(installed, capsys):
    store.uninstall("py-style")
    rules_dir = paths.home() / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    rules_dir.chmod(0o555)
    try:
        store.install(catalog.resolve_one("py-style"))
    finally:
        rules_dir.chmod(0o755)
    entry = lockfile.get_rule("py-style")
    refused = [m["agent"] for m in entry["materializations"]
               if m.get("unwritable")]
    assert refused == ["cursor"]
    named = integrity.written_agent_names("rule", entry)
    assert "cursor" not in named and named
    capsys.readouterr()
    assert cli.main(["list", "--kind", "rule"]) == 0
    line = next(ln for ln in capsys.readouterr().out.splitlines()
                if "py-style" in ln)
    assert "cursor" not in line and "claude" in line
    assert cli.main(["info", "py-style"]) == 0
    mat = next(ln for ln in capsys.readouterr().out.splitlines()
               if "materialized" in ln)
    assert "cursor" not in mat and "claude-code" in mat
