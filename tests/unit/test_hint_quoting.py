# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Every command a hint prints survives the shell it is pasted into.

A tap is named after its directory with only whitespace folded, so an
apostrophe, `$` or `;` reaches the name; a local tap's URL is any path at all.
Hints spliced both in bare, so `run `boost update fix-ture's-é`` pasted as an
unterminated quote and `boost import /home/my skills` as two arguments. Each
hint now goes through `util.shell_arg`, and these tests pin both the exact text
and that `shlex.split` hands back the argv the hint means.
"""
from __future__ import annotations

import re
import shlex
import subprocess
import sys

import pytest

from boost_cli.core import catalog, registry, store, util
from boost_cli.errors import BoostError

posix = pytest.mark.skipif(sys.platform == "win32",
                           reason="POSIX shell quoting")

#: A name `parse_spec` derives from the directory `fix ture's é`.
NAME = "fix-ture's-\u00e9"
QUOTED_NAME = "'fix-ture'\"'\"'s-\u00e9'"


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True)


def _repo(path):
    (path / "skills" / "a").mkdir(parents=True)
    _git("init", "-q", cwd=path)
    _git("config", "user.email", "t@test", cwd=path)
    _git("config", "user.name", "T", cwd=path)
    (path / "skills" / "a" / "SKILL.md").write_text(
        "---\nname: a\ndescription: A skill\n---\nx\n", encoding="utf-8")
    _git("add", "-A", cwd=path)
    _git("commit", "-qm", "add a", cwd=path)
    return path


def _commands(hint: str) -> list[list[str]]:
    """Each backticked command in `hint`, split the way a shell would."""
    return [shlex.split(c) for c in re.findall(r"`([^`]+)`", hint)]


class TestShellJoin:
    @posix
    def test_posix_quotes_each_word(self):
        argv = ["npx", "--directory", "/h/my proj", "--user-name", "o'b"]
        joined = util.shell_join(argv)
        assert joined == ("npx --directory '/h/my proj' --user-name "
                          "'o'\"'\"'b'")
        assert shlex.split(joined) == argv

    def test_windows_double_quotes_only_what_has_whitespace(self, monkeypatch):
        monkeypatch.setattr(util.sys, "platform", "win32")
        assert util.shell_join(["npx", "C:\\my proj", "x"]) == (
            'npx "C:\\my proj" x')


@posix
class TestRegistryHints:
    def test_a_non_git_dir_hint_imports_the_whole_path(self, tmp_path):
        d = tmp_path / "my skills"
        d.mkdir()
        with pytest.raises(BoostError) as ei:
            registry.parse_spec(str(d))
        assert ei.value.hint == (
            "`git init` it, or `boost import %s` to copy it in without a tap"
            % shlex.quote(str(d)))
        assert _commands(ei.value.hint)[1] == ["boost", "import", str(d)]

    def test_a_taken_name_quotes_the_path_to_tap(self, sandbox, tmp_path):
        first = _repo(tmp_path / "a" / "o'tap")
        other = _repo(tmp_path / "other dir" / "o'tap")
        registry.add(str(first))
        with pytest.raises(BoostError) as ei:
            registry.add(str(other))
        url = str(other.resolve())
        assert ei.value.hint == (
            "`boost untap %s`, then `boost tap %s` to tap it in its place"
            % (shlex.quote("o'tap"), shlex.quote(url)))
        assert _commands(ei.value.hint) == [
            ["boost", "untap", "o'tap"], ["boost", "tap", url]]

    def test_at_on_a_configured_tap_quotes_spec_and_name(
            self, sandbox, tmp_path):
        src = _repo(tmp_path / "fix ture's \u00e9")
        tap = registry.add(str(src))
        assert tap.name == NAME
        with pytest.raises(BoostError) as ei:
            registry.add(str(src), at="HEAD~0")
        assert ei.value.hint == (
            "`boost untap %s`, then `boost tap %s --at 'HEAD~0'` to move it to "
            "that commit" % (QUOTED_NAME, shlex.quote(str(src))))
        assert _commands(ei.value.hint) == [
            ["boost", "untap", NAME],
            ["boost", "tap", str(src), "--at", "HEAD~0"]]

    def test_a_configured_tap_update_hint_quotes_the_name(
            self, sandbox, tmp_path):
        src = _repo(tmp_path / "fix ture's \u00e9")
        registry.add(str(src))
        with pytest.raises(BoostError) as ei:
            registry.add(str(src))
        assert ei.value.hint == "`boost update %s` to refresh it" % QUOTED_NAME

    def test_broken_clone_line_quotes_only_the_command(self):
        line = registry.broken_clone_line(NAME)
        assert line == (
            "tap %s is not a git repository (its .git is missing) — run "
            "`boost update %s` to re-clone it" % (NAME, QUOTED_NAME))
        assert _commands(line) == [["boost", "update", NAME]]

    def test_pin_missing_remedy_quotes_the_name(self):
        hint = registry.pin_missing_remedy(NAME)
        assert hint.startswith("`boost update --force %s` re-clones"
                               % QUOTED_NAME)
        assert _commands(hint)[0] == ["boost", "update", "--force", NAME]

    def test_retap_by_name_quotes_it(self):
        assert registry.retap_hint("o'x/repo") == (
            "boost tap 'o'\"'\"'x/repo'")
        assert registry.retap_hint("owner/repo") == "boost tap owner/repo"


@posix
class TestTapNameHints:
    def test_a_vanished_rule_names_an_update_that_runs(
            self, sandbox, tmp_path):
        tap = registry.add(str(_repo(tmp_path / "fix ture's \u00e9")))
        entry = {"kind": "rule", "tap": tap.name, "name": "r",
                 "skill_md": "rules/r.mdc"}
        with pytest.raises(BoostError) as ei:
            store.source_file_for(entry)
        assert ei.value.hint == "run `boost update %s`" % QUOTED_NAME
        assert _commands(ei.value.hint) == [["boost", "update", NAME]]

    def test_an_uncloned_tap_rebuild_names_an_update_that_runs(self, sandbox):
        tap = registry.Tap(name=NAME, url="/nowhere")
        with pytest.raises(BoostError) as ei:
            catalog.rebuild_tap(tap)
        assert ei.value.hint == "run `boost update %s`" % QUOTED_NAME

    def test_another_taps_copy_hint_quotes_tap_and_name(self, sandbox):
        # Installed from one tap; installing the other's copy is refused
        # with the `tap:name` that replaces it.
        store.lockfile.set_skill("a", {"tap": "other", "version": "1"})
        entry = {"name": "a", "tap": NAME, "version": "1"}
        with pytest.raises(BoostError) as ei:
            store.check_existing(entry)
        assert ei.value.hint == (
            "`boost install %s --force` to replace it"
            % shlex.quote("%s:a" % NAME))
        assert _commands(ei.value.hint) == [
            ["boost", "install", "%s:a" % NAME, "--force"]]


@posix
class TestPkgHints:
    def test_rm_target_is_the_real_path_as_one_word(self):
        from boost_cli.commands import pkg
        target = pkg._rm_target("/h/my repo", ".claude/skills/x")
        assert target == "'/h/my repo/.claude/skills/x'"
        assert shlex.split("rm -rf " + target) == [
            "rm", "-rf", "/h/my repo/.claude/skills/x"]
        assert pkg._rm_target(None, "x y") == "'x y'"

    def test_an_import_over_a_tap_copy_names_a_quoted_install(
            self, sandbox, capsys):
        from types import SimpleNamespace

        from boost_cli.commands import pkg
        res = SimpleNamespace(name="a", replaced_tap=NAME, out_of_scope=[])
        pkg._warn_import(res, False)
        cap = capsys.readouterr()
        flat = " ".join((cap.out + cap.err).split())
        assert ("(`boost install %s --force` puts the tap's copy back)"
                % shlex.quote("%s:a" % NAME)) in flat

    def test_an_unverifiable_clone_names_an_update_that_runs(self, sandbox):
        from boost_cli.core import config, policy
        cfg = config.load()
        cfg["taps"] = [{"name": NAME, "url": "/nowhere", "curated": False}]
        config.save(cfg)
        assert policy.installed_tap_signing(NAME) == [
            "tap %r has no clone here to verify — `boost update %s` "
            "re-clones it" % (NAME, QUOTED_NAME)]
