# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: child-process text is UTF-8 whatever the locale code page.

Python without UTF-8 mode decodes ``subprocess`` text through
``locale.getencoding()``, which is ``cp1252`` on en-US Windows. Git, gh and
the AI CLIs all speak UTF-8, so a Cyrillic file name in a tap crashed `boost
tap` (and every search after it), an arrow in a skill description crashed
`boost explain`, and a Russian repo description crashed `boost index`. The
``cp1252`` fixture reproduces that default on any OS by patching the one
function ``subprocess`` asks.
"""
from __future__ import annotations

import ast
import json
import locale
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from boost_cli.core import ai, gitutil, util
from boost_cli.errors import BoostError

PKG = Path(__file__).resolve().parents[2] / "boost_cli"

#: Names a subprocess launch is called through (``dialog`` injects ``run``).
_LAUNCHERS = {"run", "Popen", "check_output", "check_call", "call"}
_MUTANT = re.compile(r"__mutmut_\d+$")


def _text_calls_without_encoding(source: str) -> list[int]:
    """Line numbers of launches in ``source`` that decode text with no encoding."""
    tree = ast.parse(source)
    # mutmut keeps each mutant as its own ``x_f__mutmut_N`` copy of a
    # function, and a mutant that deletes ``encoding=`` is the point of it.
    for parent in ast.walk(tree):
        if hasattr(parent, "body") and isinstance(parent.body, list):
            parent.body = [n for n in parent.body if not (
                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and _MUTANT.search(n.name))]
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (func.attr if isinstance(func, ast.Attribute)
                else func.id if isinstance(func, ast.Name) else None)
        if name not in _LAUNCHERS:
            continue
        kw = {k.arg: k.value for k in node.keywords if k.arg}
        textual = [kw[k] for k in ("text", "universal_newlines") if k in kw]
        if not any(not (isinstance(v, ast.Constant) and v.value is False)
                   for v in textual):
            continue
        if "encoding" not in kw:
            bad.append(node.lineno)
    return bad


class TestNoLocaleDecoding:
    def test_every_text_mode_launch_names_its_encoding(self):
        offenders = [
            "%s:%d" % (path.relative_to(PKG).as_posix(), line)
            for path in sorted(PKG.rglob("*.py"))
            for line in _text_calls_without_encoding(
                path.read_text(encoding="utf-8"))]
        assert offenders == [], (
            "text=True without encoding= decodes with the Windows code page; "
            "pass encoding=\"utf-8\", errors=\"replace\"")

    def test_scanner_flags_a_bare_text_launch(self):
        src = ("import subprocess\n"
               "subprocess.run(['git'], text=True)\n"
               "run(['x'],\n    capture_output=True, universal_newlines=1)\n")
        assert _text_calls_without_encoding(src) == [2, 3]

    def test_scanner_skips_mutmut_copies_only(self):
        src = ("def x_f__mutmut_1():\n"
               "    run(['git'], text=True)\n"
               "def x_f__mutmut_orig():\n"
               "    run(['git'], text=True)\n")
        assert _text_calls_without_encoding(src) == [4]

    def test_scanner_passes_encoded_bytes_and_unrelated_calls(self):
        src = ("import subprocess\n"
               "subprocess.run(['git'], text=True, encoding='utf-8')\n"
               "subprocess.Popen(['git'], text=flag, encoding=enc)\n"
               "subprocess.run(['git'], capture_output=True)\n"
               "subprocess.run(['git'], text=False)\n"
               "out.warn('x', text=True)\n")
        assert _text_calls_without_encoding(src) == []


class TestResolveExe:
    def test_swaps_in_the_path_which_found(self, monkeypatch):
        monkeypatch.setattr(util.shutil, "which",
                            lambda n: "C:\\npm\\npx.CMD" if n == "npx" else None)
        argv = ["npx", "--yes", "bmad-method"]
        assert util.resolve_exe(argv) == ["C:\\npm\\npx.CMD", "--yes",
                                          "bmad-method"]
        assert argv == ["npx", "--yes", "bmad-method"]  # caller's list untouched

    def test_unresolvable_name_passes_through_as_a_copy(self, monkeypatch):
        monkeypatch.setattr(util.shutil, "which", lambda n: None)
        argv = ["gh", "api"]
        got = util.resolve_exe(argv)
        assert got == ["gh", "api"]
        assert got is not argv

    def test_empty_argv_never_asks_which(self, monkeypatch):
        def boom(_n):
            raise AssertionError("which called")
        monkeypatch.setattr(util.shutil, "which", boom)
        assert util.resolve_exe([]) == []


@pytest.fixture()
def cp1252(monkeypatch):
    """Decode child text the way en-US Windows does by default."""
    if sys.flags.utf8_mode:
        pytest.skip("UTF-8 mode ignores the locale encoding")
    monkeypatch.setattr(locale, "getencoding", lambda: "cp1252")


def _echo_script(tmp_path: Path, tail: bytes = b"") -> Path:
    """A fake CLI: echoes stdin's bytes back, then ``tail``, as raw bytes."""
    script = tmp_path / "fake_cli.py"
    script.write_text(
        "import sys\n"
        "data = sys.stdin.buffer.read()\n"
        "sys.stdout.buffer.write(data + %r)\n" % tail, encoding="utf-8")
    return script


@pytest.mark.skipif(sys.platform == "win32", reason=(
    "Windows feeds stdin from a thread, so the encode error kills the writer "
    "and the child waits for EOF until the timeout"))
def test_cp1252_fixture_reproduces_the_windows_failure(cp1252, tmp_path):
    """Negative control: without an encoding the patched default bites."""
    script = _echo_script(tmp_path)
    with pytest.raises(UnicodeEncodeError):
        subprocess.run([sys.executable, str(script)], input="a \u2192 b",
                       capture_output=True, text=True, timeout=60)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, encoding="utf-8",
                          timeout=60).stdout


@pytest.fixture()
def cyrillic_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@test")
    _git(repo, "config", "user.name", "T")
    (repo / "docs").mkdir()
    (repo / "docs" / "\u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435.md").write_text(
        "# notes\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "ru")
    yield repo
    util.rmtree(repo)


class TestGitUnderCp1252:
    LOWER = "docs/\u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435.md"
    UPPER = "docs/\u041e\u041f\u0418\u0421\u0410\u041d\u0418\u0415.md"

    def test_case_collisions_reads_cyrillic_paths(self, cp1252, cyrillic_repo):
        repo = cyrillic_repo
        _git(repo, "config", "core.ignorecase", "true")
        blob = _git(repo, "rev-parse", "HEAD:" + self.LOWER).strip()
        # An index entry only: a case-insensitive disk cannot hold both.
        _git(repo, "update-index", "--add", "--cacheinfo",
             "100644,%s,%s" % (blob, self.UPPER))
        assert gitutil.case_collisions(repo) == [[self.UPPER, self.LOWER]]

    def test_require_checked_out_names_a_skipped_cyrillic_file(
            self, cp1252, cyrillic_repo):
        repo = cyrillic_repo
        _git(repo, "update-index", "--skip-worktree", self.LOWER)
        with pytest.raises(BoostError) as err:
            gitutil._require_checked_out(repo, "docs")
        assert "could not check out 1 file of docs" in str(err.value)
        assert self.LOWER in str(err.value)

    def test_require_checked_out_passes_a_checked_out_tree(
            self, cp1252, cyrillic_repo):
        assert gitutil._require_checked_out(cyrillic_repo, "docs") is None

    def test_bytes_mode_stays_bytes(self, cyrillic_repo):
        proc = gitutil._exec(["git", "-C", str(cyrillic_repo), "ls-files", "-z"],
                             cwd=None, timeout=60, env=dict(os.environ),
                             text=False)
        assert proc.stdout == (self.LOWER + "\0").encode("utf-8")

    def test_invalid_bytes_decode_to_the_replacement_character(self, cp1252):
        proc = gitutil._exec(
            [sys.executable, "-c",
             "import sys; sys.stdout.buffer.write(b'ok \\xff')"],
            cwd=None, timeout=60, env=dict(os.environ))
        assert proc.stdout == "ok \ufffd"


class TestAiCliUnderCp1252:
    def test_prompt_and_reply_cross_as_utf8(self, cp1252, sandbox, tmp_path,
                                            monkeypatch):
        script = _echo_script(tmp_path, tail=b" \xff")
        monkeypatch.setattr(ai.aihost, "argv",
                            lambda *a, **k: [sys.executable, str(script)])
        monkeypatch.setattr(ai.aihost, "fold_system",
                            lambda backend, system, prompt: prompt)
        got = ai._ask_cli("claude", "Map a request \u2192 plan \u2192 patch",
                          None, "m", 60)
        # the arrows survive the round trip; the invalid byte degrades to
        # U+FFFD instead of raising
        assert got == "Map a request \u2192 plan \u2192 patch \ufffd"

    def test_an_unencodable_prompt_degrades_to_none(self, sandbox, monkeypatch):
        def run(cmd, **kw):
            raise UnicodeEncodeError("utf-8", "\ud800", 0, 1, "surrogate")
        monkeypatch.setattr(ai.subprocess, "run", run)
        monkeypatch.setattr(ai.aihost, "argv", lambda *a, **k: ["claude", "-p"])
        assert ai._ask_cli("claude", "x", None, "m", 60) is None

    def test_launches_the_resolved_cli_with_utf8(self, sandbox, monkeypatch):
        seen = []

        def run(cmd, **kw):
            seen.append((cmd, kw["encoding"], kw["errors"], kw["input"]))
            return subprocess.CompletedProcess(cmd, 0, "ok\n", "")
        monkeypatch.setattr(ai.subprocess, "run", run)
        monkeypatch.setattr(ai.aihost, "argv", lambda *a, **k: ["claude", "-p"])
        monkeypatch.setattr(util.shutil, "which",
                            lambda n: "C:\\npm\\claude.cmd" if n == "claude"
                            else None)
        assert ai._ask_cli("claude", "hi", None, "m", 60) == "ok"
        assert seen == [(["C:\\npm\\claude.cmd", "-p"], "utf-8", "replace",
                         "hi")]


_GH_JSON = json.dumps({
    "total_count": 1,
    "items": [{"path": "skills/lint/SKILL.md",
               "html_url": "https://github.com/o/r/blob/main/skills/lint/SKILL.md",
               "repository": {"full_name": "o/r",
                              "description": "\u041b\u0438\u043d\u0442\u0435\u0440 "
                                             "\u0434\u043b\u044f"}}]},
    ensure_ascii=False).encode("utf-8")


def _fake_gh(tmp_path: Path, monkeypatch, payload: bytes) -> list[list[str]]:
    """Route `gh` to a Python script printing ``payload``; record each argv."""
    script = tmp_path / "fake_gh.py"
    script.write_text("import sys\nsys.stdout.buffer.write(%r)\n" % payload,
                      encoding="utf-8")
    launched: list[list[str]] = []

    def resolve(argv):
        launched.append(list(argv))
        return [sys.executable, str(script)]
    monkeypatch.setattr(util, "resolve_exe", resolve)
    monkeypatch.setattr(util.shutil, "which", lambda n: "/x/" + n)
    return launched


class TestGhUnderCp1252:
    def test_github_skill_search_decodes_cyrillic(self, cp1252, sandbox,
                                                  tmp_path, monkeypatch):
        from boost_cli.commands import discovery
        launched = _fake_gh(tmp_path, monkeypatch, _GH_JSON)
        assert discovery.github_skill_search("lint", limit=5) == [{
            "repo": "o/r", "path": "skills/lint/SKILL.md",
            "url": "https://github.com/o/r/blob/main/skills/lint/SKILL.md",
            "description": "\u041b\u0438\u043d\u0442\u0435\u0440 \u0434\u043b\u044f"}]
        assert [a[:2] for a in launched] == [["gh", "api"]]

    def test_invalid_bytes_in_gh_output_are_replaced(self, cp1252, sandbox,
                                                     tmp_path, monkeypatch):
        from boost_cli.commands import discovery
        payload = _GH_JSON.replace(b'"o/r"', b'"o/\xffr"')
        _fake_gh(tmp_path, monkeypatch, payload)
        got = discovery.github_skill_search("lint", limit=5)
        assert got is not None
        assert got[0]["repo"] == "o/\ufffdr"

    def test_index_writes_the_cyrillic_description(self, cp1252, boost,
                                                   sandbox, tmp_path,
                                                   monkeypatch):
        from boost_cli.core import paths
        _fake_gh(tmp_path, monkeypatch, _GH_JSON)
        r = boost("index", "lint", "--limit", "5")
        assert "indexed 1 skill files across 1 repos" in r.out
        data = json.loads((paths.cache_dir() / "discovery.json").read_text(
            encoding="utf-8"))
        assert data["items"][0]["description"] == (
            "\u041b\u0438\u043d\u0442\u0435\u0440 \u0434\u043b\u044f")
