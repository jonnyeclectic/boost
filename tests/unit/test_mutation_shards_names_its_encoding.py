# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the shard planner never leaves a text encoding to the locale.

``Path.read_text()``, ``Path.write_text()`` and ``open()`` in text mode use
``locale.getencoding()`` when no ``encoding=`` is given. On Linux and macOS
that is UTF-8 and nothing ever goes wrong; on a GitHub **Windows** runner it
is cp1252, and the two platforms then disagree about what a file says.

That is not hypothetical here. ``mutation_shards.py drift`` writes its report
with ``encoding="utf-8"`` and the report contains an em dash, so when the
test beside this one read it back with ``read_text()`` the file and the
printed string stopped being the same text — and all three ``tests
(windows-latest, 3.1x)`` jobs failed on a change that had touched nothing
platform-specific.

**Naming the encoding was only half of it**, which the next Windows run said
plainly. Text mode also translates ``"\n"`` to the platform separator on
*write*, so ``write_text(report, encoding="utf-8")`` still put CRLF in the
file while ``sys.stdout.write(report)`` emitted LF, and the same comparison
failed again for an entirely different reason. A writer in this script must
pin ``newline="\n"`` as well: the step summary and the log are one report
written twice and have to agree, and ``$GITHUB_OUTPUT`` is parsed a line at
a time. Hence two walkers below, not one. The same omission on a *reader* of the weights JSON is
quieter and worse: ``UnicodeDecodeError`` is a ``ValueError``, so
``_unusable`` would have caught it and reported "not readable JSON" about a
file that reads perfectly well, and the refresh would have been skipped with
a wrong reason.

**Deliberately file-scoped.** Running ``unencoded`` over the whole
repository finds **73** further sites with no explicit encoding — 72 in the
test suite, 1 in ``boost_cli`` (``core/journal.py:55``) and none in
``scripts``. Fixing those is a sweep of its own and does not belong in a
change about shard balance (CLAUDE.md: "don't bulk-rewrite old code in an
unrelated PR"). This pins the files that change *here*, and ``WATCHED`` is
the list to extend as the sweep progresses — the guard generalises by adding
a path, not by being rewritten.

**That number was 116 until the walker was corrected**, and the 43 it lost
are worth naming, because an inflated backlog is not a conservative error:
it sizes a sweep nobody can then finish, and every false positive is a call
the guard would fail on the day its file joins ``WATCHED``. Thirty were
``tarfile.open(path, "w:gz")``, three ``os.open`` (a file descriptor, which
has no encoding), two ``webbrowser.open(url)``, one a urllib response, and
seven were binary ``Path.open("rb")`` miscounted because ``_mode`` read the
mode from the builtin's position. See ``_is_file_open``.

Ruff's ``PLW1514`` covers part of this and is worth enabling repo-wide once
the sweep lands, but it is not a substitute. Two reasons, both measured.
It is a **preview** rule, so ``ruff check --select PLW1514`` without
``--preview`` silently checks nothing and reports "All checks passed" — the
answer looks the same as clean. And with ``--preview`` it resolves the
receiver syntactically: over ``origin/main`` it reports exactly **one** site,
``scripts/mutation_shards.py:718``, which is one of the ten this commit
encoded, and it never saw the ``md.read_text()`` off a pytest ``tmp_path``
fixture that actually broke CI. On this branch it reports zero while the
walker still reports 73.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: Files this guard covers. Add a path as the repo-wide sweep reaches it.
WATCHED = (
    "scripts/mutation_shards.py",
    "tests/unit/test_mutation_weights_drift.py",
)

_TEXT_IO = frozenset({"read_text", "write_text", "open"})


#: Dotted roots whose ``.open`` is not a filesystem text open. ``tarfile``
#: and ``zipfile`` take an archive mode (``"w:gz"``), ``os.open`` returns a
#: file descriptor and has no encoding at all, and ``webbrowser.open`` takes
#: a URL. Counting them is not a conservative over-report: it inflates the
#: size of a sweep nobody can then finish, and it would fail the guard on a
#: call with no encoding to name the moment one of their files joins
#: ``WATCHED``.
_NOT_FILE_OPENS = frozenset({"tarfile", "zipfile", "os", "webbrowser",
                             "socket", "shelve", "dbm", "sqlite3"})


def _root_name(node: ast.AST) -> str | None:
    """The leftmost ``Name`` of a dotted expression, if it is one."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _is_file_open(call: ast.Call) -> bool:
    """Whether this ``.open``/``open`` call opens a file by path.

    The builtin always does. An attribute ``.open`` is ``Path.open`` only
    when its receiver is not one of the modules above and its first
    positional argument, if any, is a mode string -- ``Path.open``'s
    signature starts ``(mode="r", buffering=-1, encoding=None)``, so a
    non-string first positional means the receiver is something else.
    That is what separates ``p.open("a")`` from ``build_opener().open(req)``
    without having to resolve the receiver's type.
    """
    if isinstance(call.func, ast.Name):
        return True
    recv = call.func.value
    if _root_name(recv) in _NOT_FILE_OPENS:
        return False
    if isinstance(recv, ast.Call):
        # `build_opener().open(req)` versus `paths.pulse_path().open("a")`.
        # Nothing in an AST says which returns a Path, so judge the factory
        # by its name. Both shapes are in this repo, so the choice is not
        # hypothetical; a factory named for neither is skipped, which keeps
        # the count honest at the price of a miss the WATCHED list closes.
        fn = recv.func
        made = fn.attr if isinstance(fn, ast.Attribute) else getattr(
            fn, "id", "")
        return made == "Path" or made.lower().endswith(
            ("path", "dir", "file"))
    return not call.args or isinstance(call.args[0], ast.Constant)


def _mode(call: ast.Call) -> str | None:
    """The literal mode string of an ``open`` call, if it has one.

    The position differs between the two spellings and reading it from the
    wrong one is silent in both directions. ``open(path, mode)`` puts it
    second; ``Path.open(mode)`` puts it **first**, so a check written for
    the builtin returns ``None`` for every ``Path.open`` -- which made
    ``unencoded`` flag binary ``p.open("rb")`` as a missing encoding, and
    made ``unpinned_newline`` skip text ``p.open("w")`` entirely. One bug,
    two guards, opposite directions.
    """
    pos = 0 if isinstance(call.func, ast.Attribute) else 1
    if len(call.args) > pos and isinstance(call.args[pos], ast.Constant):
        return call.args[pos].value
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return None


def unencoded(path: Path) -> list[tuple[int, str]]:
    """``(line, call name)`` for every text-mode IO call with no encoding."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            name = node.func.attr
        elif isinstance(node.func, ast.Name):
            name = node.func.id
        else:
            continue
        if name not in _TEXT_IO:
            continue
        if name == "open" and not _is_file_open(node):
            continue
        if any(kw.arg == "encoding" for kw in node.keywords):
            continue
        # Binary mode has no encoding to name, and `read_bytes` never did.
        mode = _mode(node) if name == "open" else None
        if mode and "b" in mode:
            continue
        out.append((node.lineno, name))
    return out


def unpinned_newline(path: Path) -> list[tuple[int, str]]:
    """``(line, call name)`` for every text WRITE that does not pin newline.

    Writes only. A reader needs no ``newline=``: universal newlines already
    fold CRLF to LF on the way in, which is the behaviour we want and the
    reason the asymmetry is not an oversight.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = (node.func.attr if isinstance(node.func, ast.Attribute)
                else node.func.id if isinstance(node.func, ast.Name) else None)
        if name == "open":
            if not _is_file_open(node):
                continue
            mode = _mode(node)
            if not mode or "b" in mode or not any(c in mode for c in "wax+"):
                continue
        elif name != "write_text":
            continue
        if any(kw.arg == "newline" for kw in node.keywords):
            continue
        out.append((node.lineno, name))
    return out


class TestTheGuardCanActuallySee:
    def test_every_watched_file_exists(self):
        missing = [p for p in WATCHED if not (ROOT / p).is_file()]
        assert not missing, missing

    def test_it_finds_the_calls_it_is_meant_to_judge(self):
        # Vacuous if the walk never reaches a read_text/write_text at all:
        # the real files are full of them, all of them now encoded.
        src = (ROOT / "tests/unit/test_mutation_weights_drift.py").read_text(
            encoding="utf-8")
        assert src.count('encoding="utf-8"') > 10, src.count('encoding="utf-8"')

    def test_it_flags_a_known_bad_call(self, tmp_path):
        bad = tmp_path / "bad.py"
        bad.write_text(
            "from pathlib import Path\n"
            "Path('x').read_text()\n"
            "Path('y').write_text('z')\n"
            "open('w')\n"
            "open('v', 'rb')\n"              # binary: fine
            "Path('u').read_bytes()\n"       # bytes: fine
            "Path('t').read_text(encoding='utf-8')\n",  # encoded: fine
            encoding="utf-8")
        assert [n for _, n in unencoded(bad)] == [
            "read_text", "write_text", "open"]

    def test_it_knows_which_dot_open_is_a_file(self, tmp_path):
        """The mode of `Path.open` is its FIRST argument, not its second.

        Every line below was a false positive or a false negative before
        `_is_file_open` and `_mode`'s position fix: over the repo they came
        to 43 of a reported 116, which is why the sweep's own card quoted a
        number 59% larger than the work it describes.
        """
        bad = tmp_path / "opens.py"
        bad.write_text(
            "import os, tarfile, webbrowser\n"
            "from pathlib import Path\n"
            "from urllib.request import build_opener\n"
            "p = Path('x')\n"
            "p.open('a')\n"                       # text append: a violation
            "p.open()\n"                          # text read: a violation
            "p.open('rb')\n"                      # binary: fine
            "p.open('wb')\n"                      # binary: fine
            "tarfile.open(p, 'w:gz')\n"           # not a text file open
            "os.open(str(p), os.O_WRONLY)\n"      # a file descriptor
            "webbrowser.open('http://x')\n"       # a URL
            "build_opener().open('req')\n"        # a urllib response
            "paths.pulse_path().open('a')\n",      # a Path factory: a violation
            encoding="utf-8")
        assert [ln for ln, _ in unencoded(bad)] == [5, 6, 13]

    def test_it_flags_a_write_that_does_not_pin_its_newline(self, tmp_path):
        bad = tmp_path / "nl.py"
        bad.write_text(
            "from pathlib import Path\n"
            "Path('x').write_text('a', encoding='utf-8')\n"
            "open('y', 'w', encoding='utf-8')\n"
            "open('z', 'a', encoding='utf-8')\n"
            "open('r', encoding='utf-8')\n"            # a reader: fine
            "open('b', 'wb')\n"                        # binary: fine
            "Path('q').read_text(encoding='utf-8')\n"  # a reader: fine
            "Path('p').write_text('a', encoding='utf-8', newline='\\n')\n",
            encoding="utf-8")
        assert [n for _, n in unpinned_newline(bad)] == [
            "write_text", "open", "open"]


class TestNoWatchedFileLeavesAnEncodingToTheLocale:
    @pytest.mark.parametrize("relpath", WATCHED)
    def test_every_text_io_names_its_encoding(self, relpath):
        found = unencoded(ROOT / relpath)
        assert not found, (
            "%s has text IO with no explicit encoding, at %s. On a Windows "
            "runner these resolve to cp1252 while the rest of the repo "
            "writes UTF-8, so the same file reads back as different text. "
            "Pass encoding=\"utf-8\" (or read_bytes() if the content is not "
            "text)." % (relpath, ", ".join("line %d (%s)" % f for f in found)))


class TestTheScriptPinsItsNewlines:
    """Only the script: its writers must round-trip byte for byte.

    Scoped tighter than ``WATCHED`` on purpose. The test file writes JSON
    fixtures whose line endings nothing compares, so requiring ``newline=``
    there would be ceremony; the script writes the step summary, the
    ``$GITHUB_OUTPUT`` lines and the weights file, and all three are read
    back by something that cares.
    """

    def test_every_write_pins_lf(self):
        found = unpinned_newline(ROOT / "scripts/mutation_shards.py")
        assert not found, (
            "scripts/mutation_shards.py writes text without newline=\"\\n\" "
            "at %s. On Windows text mode turns every \\n into \\r\\n, so the "
            "file stops matching what the same report printed to stdout."
            % ", ".join("line %d (%s)" % f for f in found))
