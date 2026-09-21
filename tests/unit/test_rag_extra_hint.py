# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""One command installs the `[rag]` extra, and every surface prints it.

Three surfaces used to answer "how do I get semantic search" three ways:
quickstart said `pipx inject boost-skill-cli "boost-skill-cli[rag]"`, doctor
and search said `pip install 'boost-skill-cli[rag]'` through
``dense.fix_hint``, and reindex's ``embed.fallback_note`` said
`pip install boost-skill-cli[rag]` — unquoted, which zsh, macOS's default
shell, answers with "no matches found" instead of running. Two of them were
also wrong for somebody: a pipx install told to `pip install` puts the extra
in another Python, and boost goes on without it.

So the tests pin the coupling rather than the wording: every surface prints
the same command, the command runs in zsh, and the requirement is spelled in
exactly one place in the code.
"""
from __future__ import annotations

import ast
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from boost_cli.core import dense, embed, selfupdate

PKG = Path(dense.__file__).resolve().parent.parent

#: A backtick span that names the extra: the command a user would paste.
_SPAN = re.compile(r"`([^`]*boost-skill-cli\[rag\][^`]*)`")


def _commands(text: str) -> list[str]:
    return _SPAN.findall(text)


def _surfaces() -> dict[str, str]:
    """Every core line that tells a user how to install the extra."""
    return {
        "doctor/search (no-backend)": dense.fix_hint("no-backend"),
        "doctor/search (no-key)": dense.fix_hint("no-key"),
        "reindex fallback": embed.fallback_note(),
        "unreadable vectors": dense._unreadable_vectors("a/b", 3, None).hint,
    }


@pytest.fixture()
def installed_with(monkeypatch):
    """Answer `selfupdate.detect` as though boost came from `method`."""
    monkeypatch.delenv("BOOST_NO_EMBED", raising=False)

    def use(method: str) -> None:
        monkeypatch.setattr(selfupdate, "detect", lambda *a, **k: method)
    return use


class TestOneCommand:
    def test_every_surface_prints_the_same_command(self, monkeypatch):
        monkeypatch.delenv("BOOST_NO_EMBED", raising=False)
        found = {name: _commands(text) for name, text in _surfaces().items()}
        for name, cmds in found.items():
            assert len(cmds) == 1, (name, cmds)
        assert len({c[0] for c in found.values()}) == 1, found

    @pytest.mark.parametrize("method", [selfupdate.PIP, selfupdate.GIT,
                                        selfupdate.UNKNOWN,
                                        selfupdate.UV_TOOL])
    def test_a_pip_style_install_is_told_to_pip_install_it(
            self, installed_with, method):
        installed_with(method)
        want = '`pip install "boost-skill-cli[rag]"`'
        assert want in dense.fix_hint("no-backend")
        assert want in embed.fallback_note()

    def test_a_pipx_install_is_told_to_inject_it(self, installed_with):
        # `pip install` under pipx lands the extra in some other Python.
        installed_with(selfupdate.PIPX)
        want = '`pipx inject boost-skill-cli "boost-skill-cli[rag]"`'
        for name, text in _surfaces().items():
            assert want in text, name
        assert dense.install_extra() == want.strip("`")

    def test_no_row_leaks_the_placeholder(self):
        for reason in [*dense._FIX, "not-a-reason"]:
            assert "{install-extra}" not in dense.fix_hint(reason)

    def test_rows_without_the_extra_are_untouched(self, monkeypatch):
        # Detection is paid only by the rows that print the command.
        calls: list = []
        monkeypatch.setattr(dense, "install_extra",
                            lambda: calls.append(1) or "x")
        assert dense.fix_hint("no-store") == "build it: `boost reindex --dense`"
        assert calls == []


@pytest.mark.skipif(shutil.which("zsh") is None, reason="needs zsh")
class TestItRunsInZsh:
    """zsh globs an unquoted `[rag]`, and a failed glob is an error there."""

    @pytest.mark.parametrize("method", [selfupdate.PIP, selfupdate.PIPX])
    def test_every_surface_command_survives_zsh(self, installed_with, method):
        installed_with(method)
        for name, text in _surfaces().items():
            for cmd in _commands(text):
                # `print -rl` stands in for the program: zsh expands the words
                # exactly as it would for pip, and prints what pip would get.
                res = subprocess.run(["zsh", "-f", "-c", "print -rl -- " + cmd],
                                     capture_output=True, text=True,
                                     encoding="utf-8", timeout=30,
                                     stdin=subprocess.DEVNULL, check=False)
                assert res.returncode == 0, (name, cmd, res.stderr)
                assert "boost-skill-cli[rag]" in res.stdout.splitlines(), name


def _docstrings(tree: ast.AST) -> set[int]:
    """ids of the Constant nodes that are docstrings."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                ids.add(id(first.value))
    return ids


def test_the_requirement_is_spelled_in_one_place():
    """A new surface that spells the command itself fails here, not in zsh."""
    hits: list[str] = []
    for path in sorted(PKG.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        skip = _docstrings(tree)
        hits.extend("%s:%d" % (path.relative_to(PKG).as_posix(), node.lineno)
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Constant)
                    and isinstance(node.value, str) and id(node) not in skip
                    and "boost-skill-cli[rag]" in node.value)
    assert len(hits) == 1, hits
    assert hits == ["core/dense.py:%d" % _extra_spec_line()], hits


def _extra_spec_line() -> int:
    src = Path(dense.__file__).read_text(encoding="utf-8").splitlines()
    return next(i for i, line in enumerate(src, 1)
                if line.startswith("EXTRA_SPEC = "))
