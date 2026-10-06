# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: nothing in this repo leaves a text encoding to the locale.

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
a time. Hence two walkers below, not one. The same omission on a *reader*
of the weights JSON is quieter and worse: ``UnicodeDecodeError`` is a ``ValueError``, so
``_unusable`` would have caught it and reported "not readable JSON" about a
file that reads perfectly well, and the refresh would have been skipped with
a wrong reason.

**Repo-wide, since the sweep landed.** This guard shipped with #1012
scoped to the two files that change there, and a ``WATCHED`` tuple to
extend "as the sweep progresses". The sweep is this change: the 73 sites
it measured are encoded and ``SWEPT`` is now every root that holds Python
— ``boost_cli``, ``scripts``, ``tests``, ``evals``, ``boost_langchain``,
``noxfile.py``. That is every ``.py`` the repo tracks, exactly — pinned
below against ``git ls-files``, not asserted here. It is a claim about
which *files* are opened and parsed, not about which *calls* inside them
the walkers recognise; see the blind spots named further down. The one file the
licence sweep covers and this one does not is the ``./boost`` launcher,
which is a bash shim rather than Python; the reason sits beside ``SWEPT``.
The file count is deliberately not written here — it is
``len(swept_files())``, it changes with every module added, and the
version this sentence first hand-typed was wrong by one. A new unencoded
call fails here rather than on a Windows runner three jobs later.

Of the 73, **72 were in the test suite and one was in ``boost_cli``**:
``core/journal.py`` appended to the pulse feed with ``p.open("a")`` while
``events()`` read it back with ``encoding="utf-8"``. That asymmetry is
latent rather than live — ``json.dumps`` defaults to ``ensure_ascii=True``,
so every byte written today is ASCII and cp1252 agrees with UTF-8 about
all of them — but the reader passes ``errors="replace"``, which is
precisely what would turn the first non-ASCII event into U+FFFD without
raising. See ``tests/unit/test_journal.py``.

**EXEMPT is empty and should stay that way.** An entry here is a file
whose text IO genuinely cannot name an encoding; none exists. A call that
should not be flagged belongs in ``_is_file_open`` or ``_mode``, where it
is fixed for every file at once, rather than in a list that mutes one.

**What the walk covers is every tracked ``.py``; what it judges is not
every text open in them.** The two are easy to read as one claim and they
are not, which ``os.fdopen`` proved: it was excluded three separate ways
at once and hid ``util.atomic_write_text``, the canonical writer behind
nineteen call sites, from *both* guards for as long as they have existed.
So the remaining blind spots are named here rather than left to be
rediscovered the same way. Two shapes open a text file without going
through ``open``/``fdopen``/``write_text``:

* ``tempfile.NamedTemporaryFile(mode, ...)`` — a context manager, not an
  ``open``. Adding it is not one line: its default mode is ``"w+b"``, so
  unlike every name in ``_TEXT_IO`` a *missing* mode means binary, and
  ``_mode`` returning ``None`` would have to stop meaning "assume text".
* ``logging.FileHandler`` and its ``RotatingFileHandler`` subclass — these
  take ``encoding=`` but have **no** ``newline=`` at all, so they can only
  ever join the encoding walker, never the newline one.

Both live sites are correct today — ``commands/run.py`` and
``core/logs.py`` each pass ``encoding="utf-8"`` — and
``TestTheWalkersCannotSeeTheseButTheyAreStillPinned`` below asserts that
directly against the source, so removing one fails a test rather than a
Windows runner. That is a narrower guarantee than the walk gives, and it
is stated narrowly on purpose.

**That number was 116 until the walker was corrected**, and the 43 it lost
are worth naming, because an inflated backlog is not a conservative error:
it sizes a sweep nobody can then finish, and every false positive is a
call the guard would fail on. Thirty were ``tarfile.open(path, "w:gz")``,
three ``os.open`` (a file descriptor, which has no encoding), two
``webbrowser.open(url)``, one a urllib response, and seven were binary
``Path.open("rb")`` miscounted because ``_mode`` read the mode from the
builtin's position. See ``_is_file_open``.

Ruff's ``PLW1514`` covers part of this and is worth enabling repo-wide once
the sweep lands, but it is not a substitute. Two reasons, both measured.
**It found 0 of the 73.** With ``--preview`` over the pre-sweep tree it
reported nothing at all, because it resolves the receiver syntactically:
it flags ``p.read_text()`` where ``p = Path(...)`` is in view, and every
one of the 73 is a ``tmp_path / "x"`` fixture, a chained call or a
parameter — including the ``md.read_text()`` that actually broke CI.
Secondarily it is a **preview** rule, which means two things:
``ruff check --select PLW1514`` *without* ``--preview`` silently checks
nothing and reports "All checks passed" — indistinguishable from clean —
and switching ``preview`` on in ``pyproject.toml`` to get it also
changes how every other selected rule behaves. One rule in exchange for
that, for 0 sites of 73, is not the trade.
"""
from __future__ import annotations

import ast
import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

from boost_cli.core import complete, util


def _checkout_root(start: Path) -> Path:
    """The working tree *start* sits in, found by walking up for ``.git``.

    ``parents[2]`` is wrong here, and the mutation gate is where it shows.
    mutmut copies ``tests/``, ``boost_cli/`` and the rest into ``mutants/``
    and runs pytest from there, so ``parents[2]`` becomes
    ``<checkout>/mutants`` — a tree that holds no ``noxfile.py`` (it is not
    in ``also_copy``) and whose ``boost_cli/core`` has been **rewritten**,
    every function expanded into its original plus one body per mutant. Both
    halves are wrong for this guard: the first fails ``SWEPT`` on a file that
    exists, and the second would have the walk judge generated code, so a
    mutant that dropped an ``encoding=`` would fail the guard for every
    *other* mutant in its shard too.

    Walking up for the VCS marker lands on the real checkout from either
    tree, and is the same answer ``tests/conftest.checkout_root`` computes
    for the same reason (``.exists()``, not ``.is_dir()``: in a ``git
    worktree`` the marker is a file). The fallback is an unpacked sdist,
    which has no marker and no mutants.
    """
    for d in (start, *start.parents):
        if (d / ".git").exists():
            return d
    return start


ROOT = _checkout_root(Path(__file__).resolve().parent)

#: Every root holding Python this guard walks. A new top-level package
#: belongs here; a new file inside one of these needs no edit at all, which
#: is the point of sweeping by root rather than by path.
#:
#: ``./boost`` is deliberately absent although the licence-header sweep
#: covers it: it is a bash shim, not Python, and ``ast.parse`` on it raises
#: ``SyntaxError`` from inside the embedded heredoc. It opens no files.
SWEPT = ("boost_cli", "boost_langchain", "evals", "scripts", "tests",
         "noxfile.py")

#: Paths excused from the walk, each with the reason it cannot name an
#: encoding. Empty, and see the module docstring before adding to it: a call
#: that should not be flagged is a bug in ``_is_file_open`` or ``_mode``.
EXEMPT: frozenset[str] = frozenset()


def swept_files() -> list[Path]:
    """Every ``.py`` under ``SWEPT``, minus ``EXEMPT``, repo-relative order."""
    out: list[Path] = []
    for root in SWEPT:
        p = ROOT / root
        out.extend([p] if p.is_file() else sorted(p.rglob("*.py")))
    return [p for p in out if p.relative_to(ROOT).as_posix() not in EXEMPT]

_TEXT_IO = frozenset({"read_text", "write_text", "open", "fdopen"})


#: Dotted roots whose ``.open`` is not a filesystem text open. ``tarfile``
#: and ``zipfile`` take an archive mode (``"w:gz"``), ``os.open`` returns a
#: file descriptor and has no encoding at all, and ``webbrowser.open`` takes
#: a URL. Counting them is not a conservative over-report: it inflates the
#: size of a sweep nobody can then finish, and it would fail the guard on a
#: call with no encoding to name, now that the walk covers every file.
#:
#: ``os`` is here for ``os.open`` and **not** for ``os.fdopen``, which is
#: :func:`io.open` on a descriptor and takes both ``encoding=`` and
#: ``newline=``. Excluding the whole module hid the two of them together,
#: and the one it hid is the one that matters:
#: ``util.atomic_write_text`` — the canonical writer behind 19 call sites,
#: among them the lock file, ``config.json``, every tap cache and every
#: rule materialized into a user's ``CLAUDE.md`` — writes through
#: ``os.fdopen`` and so reported clean to *both* walkers. ``fdopen`` is
#: carved out in :func:`_is_file_open` rather than by dropping ``os``.
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
    if call.func.attr == "fdopen":
        return True
    recv = call.func.value
    if _root_name(recv) in _NOT_FILE_OPENS:
        return False
    if isinstance(recv, ast.Call):
        # `build_opener().open(req)` versus `paths.pulse_path().open("a")`.
        # Nothing in an AST says which returns a Path, so judge the factory
        # by its name. Both shapes are in this repo, so the choice is not
        # hypothetical; a factory named for neither is skipped, which keeps
        # the count honest at the price of a miss nothing else would.
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

    ``os.fdopen(fd, "w")`` is the third spelling and sides with the builtin:
    it is an *attribute* call whose mode is nonetheless second, because the
    descriptor takes the first slot. Reading it as ``Path.open`` yields the
    ``fd`` name, which is no ``Constant``, so ``_mode`` answered ``None``
    and ``unpinned_newline`` skipped the call -- exactly the failure this
    docstring already describes, one spelling later.
    """
    attr = getattr(call.func, "attr", None)
    pos = 0 if isinstance(call.func, ast.Attribute) and attr != "fdopen" else 1
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
        if name in ("open", "fdopen") and not _is_file_open(node):
            continue
        if any(kw.arg == "encoding" for kw in node.keywords):
            continue
        # Binary mode has no encoding to name, and `read_bytes` never did.
        mode = _mode(node) if name in ("open", "fdopen") else None
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
        if name in ("open", "fdopen"):
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
    def test_every_swept_root_exists(self):
        missing = [r for r in SWEPT if not (ROOT / r).exists()]
        assert not missing, missing

    def test_the_walk_reaches_the_whole_repo(self):
        """A walk that silently stopped covering a root would pass forever."""
        files = swept_files()
        assert len(files) > 350, len(files)
        rel = {p.relative_to(ROOT).as_posix() for p in files}
        for one in ("boost_cli/core/journal.py", "scripts/mutation_shards.py",
                    "tests/unit/test_mutation_weights_drift.py",
                    "noxfile.py"):
            assert one in rel, one

    def test_both_walkers_see_os_fdopen(self, tmp_path):
        """The spelling that hid the repo's canonical writer from both.

        `os.fdopen` is `io.open` on a descriptor and takes `encoding=` and
        `newline=` — but it was excluded three times over: by name (neither
        walker's name set held it), by receiver (`os` is in
        `_NOT_FILE_OPENS`, which is right for `os.open` and wrong for this),
        and by position (`_mode` reads an attribute call's mode from
        `args[0]`, which here is the descriptor, so the mode came back
        `None` and the call was skipped as non-text).

        `util.atomic_write_text` writes through it, so the lock file,
        `config.json`, every tap cache and every rule materialized into a
        user's `CLAUDE.md` reported clean to a guard that had never looked
        at them. Asserted on a synthetic file so the test keeps meaning
        something after the real call sites are pinned.
        """
        f = tmp_path / "w.py"
        f.write_text("import os\n"
                     "with os.fdopen(fd, 'w') as h: h.write(t)\n"
                     "with os.fdopen(fd, 'w', encoding='utf-8') as h: pass\n"
                     "with os.fdopen(fd, 'wb') as h: pass\n"
                     "fd2 = os.open(p, 0)\n",
                     encoding="utf-8", newline="\n")
        # Line 2 names no encoding; line 3 does; binary and `os.open` are
        # neither's business.
        assert [ln for ln, _ in unencoded(f)] == [2]
        # Both text writes lack `newline=`; the binary one is excluded by
        # mode, which only works because `_mode` now reads position 1.
        assert [ln for ln, _ in unpinned_newline(f)] == [2, 3]

    def test_the_root_is_the_checkout_not_a_copy_inside_it(self, tmp_path):
        """The ``mutants/`` shape, spelled out.

        Under the mutation gate this module is imported from
        ``<checkout>/mutants/tests/unit/``, where ``parents[2]`` is the copy
        and not the checkout. Asserted on a synthetic tree rather than on
        the real one, because the real one only takes that shape inside a
        ``mutmut run``.
        """
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        inner = repo / "mutants" / "tests" / "unit"
        inner.mkdir(parents=True)
        assert _checkout_root(inner) == repo
        assert _checkout_root(repo / "tests" / "unit") == repo
        # No marker anywhere above: an unpacked sdist, which keeps its start.
        loose = tmp_path / "loose" / "tests"
        loose.mkdir(parents=True)
        assert _checkout_root(loose) == loose

    def test_module_root_survives_being_imported_from_a_copy(self, tmp_path):
        """``ROOT`` itself, not just the helper underneath it.

        The test above pins ``_checkout_root``; this pins that ``ROOT`` is
        computed with it. The two are not the same assertion, and only this
        one fails if ``ROOT`` goes back to ``parents[2]`` — in a real
        checkout the two expressions agree, so outside ``mutants/`` the
        revert is otherwise invisible. So the module is loaded from a copy
        of itself at the ``mutants/`` depth and asked what it decided.
        """
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        dest = repo / "mutants" / "tests" / "unit"
        dest.mkdir(parents=True)
        copy = dest / "guard.py"
        copy.write_text(Path(__file__).read_text(encoding="utf-8"),
                        encoding="utf-8")
        spec = importlib.util.spec_from_file_location("guard_copy", copy)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert repo == mod.ROOT, mod.ROOT

    def test_every_exempt_path_exists(self):
        """An EXEMPT entry for a file that is gone mutes nothing and lies."""
        missing = [p for p in EXEMPT if not (ROOT / p).is_file()]
        assert not missing, missing

    def test_the_docstring_names_the_roots_the_code_sweeps(self):
        """Prose and ``SWEPT`` must not contradict each other.

        They did: the docstring listed "``boost_cli``, ``scripts``,
        ``tests``, ``evals``, ``boost_langchain``, ``noxfile.py`` and the
        ``./boost`` launcher" while the comment twenty lines below said
        ``./boost`` is deliberately absent, and ``SWEPT`` agreed with the
        comment. A reader checking the guard's coverage against its own
        description was told it covered a file it never opens.
        """
        # Delimited rather than "every ``x`` before the first period":
        # ``noxfile.py`` has a period in it, and a substring search for
        # "omission" matched an unrelated sentence higher up — which is how
        # the first version of this test passed the bug it was written for.
        _, marker, rest = (__doc__ or "").partition(
            "``SWEPT`` is now every root that holds Python")
        assert marker, "the docstring no longer names its roots"
        listed, end, _ = rest.partition("That is every")
        assert end, "the swept-roots sentence lost its terminator"
        named = set(re.findall(r"``([A-Za-z_./]+)``", listed))
        # Set equality, not containment: under-claiming hides a root from
        # the reader and over-claiming (``./boost``) promises coverage the
        # code does not have. Both are the same bug.
        assert named == set(SWEPT), {
            "prose only": sorted(named - set(SWEPT)),
            "code only": sorted(set(SWEPT) - named)}

    def test_the_walk_covers_every_tracked_python_file(self):
        """``SWEPT`` must not quietly stop being "every ``.py``".

        The docstring's coverage claim, checked rather than asserted. One
        direction only: an untracked scratch file in the checkout is swept
        and not tracked, which is fine, while a *tracked* ``.py`` outside
        ``SWEPT`` is a root someone added without extending the guard —
        a whole directory silently exempt from the encoding rule.
        """
        if not (ROOT / ".git").exists():
            pytest.skip("not a git checkout — nothing to compare against")
        out = subprocess.run(
            ["git", "ls-files", "-z", "*.py"], cwd=ROOT, check=True,
            capture_output=True, text=True).stdout
        tracked = {p for p in out.split("\0") if p}
        swept = {p.relative_to(ROOT).as_posix() for p in swept_files()}
        assert tracked <= swept, sorted(tracked - swept)

    def test_the_docstring_hand_types_no_file_count(self):
        """A count in prose is a counter, and counters here are computed.

        The sentence naming the swept roots also said "413 files" against a
        measured 414 — the one number a reader can check against the code,
        and the one that was wrong. It is gone rather than corrected: it
        moves with every module added, so correcting it resets the clock
        instead of stopping it.
        """
        head = (__doc__ or "").split("Of the 73,")[0]
        assert not re.search(r"\b\d+\s+files\b", head), head
        # The 73 encoded sites are a fact about this change rather than a
        # count that drifts, so that number stays.
        assert "73 sites" in head

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


class TestNothingLeavesAnEncodingToTheLocale:
    @pytest.mark.parametrize("root", SWEPT)
    def test_every_text_io_names_its_encoding(self, root):
        # Parametrised by root rather than by file: one case per swept
        # file would make the suite's output about this one guard, and a
        # failure names its file and line in the message anyway.
        base = ROOT / root
        bad = []
        for path in swept_files():
            if base != path and base not in path.parents:
                continue
            bad += ["%s:%d (%s)" % (path.relative_to(ROOT).as_posix(), ln, n)
                    for ln, n in unencoded(path)]
        assert not bad, (
            "text IO with no explicit encoding, at %s. On a Windows runner "
            "these resolve to cp1252 while the rest of the repo writes "
            "UTF-8, so the same file reads back as different text. Pass "
            "encoding=\"utf-8\" (or read_bytes() if the content is not "
            "text)." % ", ".join(bad))


class TestTheWalkersCannotSeeTheseButTheyAreStillPinned:
    """The two text opens no walker in this module recognises.

    Named in the module docstring, asserted here. Neither shape goes
    through ``open``/``fdopen``/``write_text``, so both report clean to a
    guard that has never looked at them — the same way ``os.fdopen`` did
    until this change. Reading the source is cruder than an AST walk and
    deliberately so: the point is to fail if someone deletes the
    ``encoding=``, not to re-implement the walker for two call sites.
    """

    def test_the_temporary_runner_script_names_its_encoding(self):
        """``boost run`` writes a Python file for a child interpreter.

        ``tempfile.NamedTemporaryFile`` is a context manager rather than an
        ``open``, and its default mode is binary — which is why it cannot
        be folded into ``_TEXT_IO`` without teaching ``_mode`` that a
        missing mode means ``"w+b"`` here and text everywhere else.
        """
        src = (ROOT / "boost_cli/commands/run.py").read_text(encoding="utf-8")
        call = re.search(r"NamedTemporaryFile\((?:[^()]|\([^()]*\))*\)", src)
        assert call, "the runner no longer writes through NamedTemporaryFile"
        assert 'encoding="utf-8"' in call.group(0), (
            "boost_cli/commands/run.py writes the child runner through "
            "NamedTemporaryFile without an encoding. No walker in this "
            "module can see that call, so this assertion is the only "
            "thing standing between it and cp1252 on a Windows runner.")

    def test_the_rotating_log_handler_names_its_encoding(self):
        """The diagnostic log, written by ``logging`` rather than by boost.

        ``RotatingFileHandler`` takes ``encoding=`` and no ``newline=``, so
        it can only ever join the encoding walker. It is also the one
        writer here boost cannot pin even if it wanted to: ``logging``
        terminates every record with ``"\n"`` through a text stream it
        owns.
        """
        src = (ROOT / "boost_cli/core/logs.py").read_text(encoding="utf-8")
        call = re.search(r"_BestEffortFileHandler\(\s*\n(?:.*\n)*?\s*\)", src)
        assert call, "logs.py no longer constructs the rotating handler"
        assert 'encoding="utf-8"' in call.group(0), (
            "boost_cli/core/logs.py attaches the rotating file handler "
            "without an encoding. logging opens the file itself, so no "
            "walker here sees it and ~/.boost/logs/boost.log would be "
            "written in cp1252 on Windows.")


class TestAPinnedWriterReallyEmitsLF:
    """The dynamic half, and the only half that can fail on the platform.

    Everything else in this module is an AST walk: it proves a ``newline=``
    is *spelled*, never that it *matters*. A round trip on Linux passes
    whether the newline is pinned or not — ``os.linesep`` is already
    ``"\n"`` — which is exactly the class of test the encoding card's own
    verification pass caught twice. So these assert on **bytes**, and they
    are written to be trivially green here and red on
    ``tests (windows-latest, 3.1x)`` until the writer is pinned.

    Monkeypatching ``os.linesep`` does **not** simulate it. The translation
    lives in the C ``TextIOWrapper``, which hardcodes ``"\r\n"`` under
    ``MS_WINDOWS`` and never consults ``os.linesep`` — so a local
    "simulation" of this test would pass against an unpinned writer and
    prove the opposite of what it claims. The Windows runner is the
    instrument; there is no substitute for it.
    """

    def test_atomic_write_text_emits_lf(self, tmp_path):
        """The canonical writer, and the one with the widest blast radius.

        ``util.atomic_write_text`` is behind 19 call sites — the user lock,
        the project lock, ``config.json``, every tap catalog cache, every
        rule materialized into a user's ``CLAUDE.md``, every rendered
        workflow, the BM25 index. It writes through ``os.fdopen``, which
        both walkers were blind to until this change, so none of those 19
        has ever been counted in the backlog.
        """
        p = tmp_path / "x.json"
        util.atomic_write_text(p, "a\nb\n")
        assert b"\r" not in p.read_bytes()
        assert p.read_bytes() == b"a\nb\n"

    def test_the_shell_rc_writer_emits_lf(self, tmp_path):
        """``boost completions install`` rewrites the user's rc file whole.

        ``complete.apply`` writes ``plan.after`` over all of ``~/.bashrc``
        or ``~/.zshrc``, and the reader is **bash**, which does not fold: a
        trailing ``\r`` becomes part of the last word of every command.
        Pinning normalizes the whole file to LF, not just boost's own
        lines — which is what bash wants, and is a change beyond the lines
        boost added, so it is said out loud here.
        """
        rc = tmp_path / ".bashrc"
        rc.write_text("export A=1\n", encoding="utf-8", newline="\n")
        plan = complete.RcPlan(path=rc, action="add",
                               before="export A=1\n",
                               after="export A=1\neval \"$(boost _complete)\"\n")
        complete.apply(plan)
        assert b"\r" not in rc.read_bytes()


def _write_calls_containing(path: Path, marker: str) -> list[ast.Call]:
    """Every text-write call in *path* whose own source contains *marker*.

    Anchored on the source text of the call rather than on a line number,
    because a line number in a table goes stale the first time anything
    above it moves and then silently guards the wrong call. A marker that
    stops matching fails loudly instead, which is the behaviour wanted: it
    means the writer was rewritten and its reason needs re-deciding.
    """
    src = path.read_text(encoding="utf-8")
    out: list[ast.Call] = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        name = (node.func.attr if isinstance(node.func, ast.Attribute)
                else getattr(node.func, "id", None))
        if name not in ("write_text", "open", "fdopen"):
            continue
        if marker in (ast.get_source_segment(src, node) or ""):
            out.append(node)
    return out


#: The writers pinned on purpose, each with the reader that makes it matter.
#:
#: Deliberately a *table of five* against 934 unpinned writes in the same
#: tree, and the asymmetry is the finding, not an omission: a blanket sweep
#: would be 934 edits of which 929 are churn, and churn is what makes the
#: five unreviewable. Every row names a reader that sees the bytes without
#: folding them. A row with no such reader does not belong here — the
#: roadmap card ``writers-whose-bytes-are-compared-do-not-pin-their-newline``
#: carries the measured tiering and the two triage rules that keep this
#: table from growing on plausibility.
PINNED_WRITERS: tuple[tuple[str, str, str, str], ...] = (
    (
        "boost_cli/core/util.py",
        'fd, "w", encoding=encoding',
        "1-live",
        "atomic_write_text is the canonical durable writer, behind 19 call"
        " sites (17 after R1; rag.py's two bare json.dumps emit no literal"
        " newline). The non-folding reader is git, via exactly one of them:"
        " projectlock.write stamps <repo>/.boost/skill-lock.json, which that"
        " module says is meant to be committed. NOT sha256_dir — every one"
        " of those hashes a copytree'd skill dir, never a file this writes."
        " Measured red on tests (windows-latest, 3.14): b'a\\r\\nb\\r\\n'.",
    ),
    (
        "boost_cli/core/complete.py",
        "plan.after",
        "1-live",
        "complete.apply rewrites the user's whole ~/.bashrc or ~/.zshrc, and"
        " bash does not fold. Measured on bash 3.2 and zsh, a CRLF rc does"
        " not merely mangle tokens — it stops parsing at the first compound"
        " statement (fi\\r -> syntax error: unexpected end of file), so the"
        " rest of the user's own file never runs. Measured red on the same"
        " job: b'export A=1\\r\\neval \"$(boost _complete)\"\\r\\n'.",
    ),
    (
        "boost_cli/commands/team.py",
        "#!/usr/bin/env bash",
        "1-live",
        "boost protocol register writes a bash script, and bash is a"
        " non-Python parser reading it byte for byte. The write sits above"
        " the Darwin/Linux branch, so it is the one part of that command"
        " that runs on Windows. Which CR failure bites is shell-specific"
        " and deliberately unclaimed: 'bad interpreter: bash\\r' is kernel"
        " binfmt_script behaviour and Windows has none, and the URL route"
        " is ruled out because urlparse strips CR. The artifact is simply"
        " wrong, which is reason enough for one keyword.",
    ),
    (
        "boost_cli/commands/intelligence.py",
        'SKILL.md").write_text',
        "2-latent",
        "distill/infer/absorb stage a generated SKILL.md that"
        " install_from_path copies into the canonical store and stamps with"
        " util.sha256_dir. Latent, not live: every comparison against that"
        " digest is local today, so nothing breaks — but the digest should"
        " not record which OS generated the skill.",
    ),
    (
        "boost_cli/commands/intelligence.py",
        "skill_md.write_text",
        "2-latent",
        "evolve --apply rewrites a skill in the store and hashes it on the"
        " very next line. Same latent class, and the store is what gets"
        " symlinked into every agent's skills dir.",
    ),
)


class TestEveryPinnedWriterIsStillPinned:
    """The table above, checked against the tree rather than trusted.

    Three failure modes, and each gets its own assertion: the marker stops
    matching (the writer was rewritten, so its reason needs re-deciding),
    it matches more than once (the marker stopped being specific and the
    row now guards an unknown call), and the ``newline=`` is gone.
    """

    @pytest.mark.parametrize(("rel", "marker", "tier", "reason"),
                             PINNED_WRITERS,
                             ids=[r[0].rsplit("/", 1)[-1] + ":" + r[1][:18]
                                  for r in PINNED_WRITERS])
    def test_the_pin_is_there(self, rel, marker, tier, reason):
        calls = _write_calls_containing(ROOT / rel, marker)
        assert len(calls) == 1, (
            "%s: %d writes match %r, expected exactly 1. A row of"
            " PINNED_WRITERS no longer names one call, so it is guarding"
            " nothing or guarding the wrong thing." % (rel, len(calls), marker))
        kw = {k.arg: k.value for k in calls[0].keywords}
        assert "newline" in kw, (
            "%s line %d lost newline=\"\\n\". It is pinned (%s) because:"
            " %s" % (rel, calls[0].lineno, tier, reason))
        assert isinstance(kw["newline"], ast.Constant), (
            "%s line %d pins a non-literal newline" % (rel, calls[0].lineno))
        assert kw["newline"].value == "\n", (
            "%s line %d pins newline=%r, not LF"
            % (rel, calls[0].lineno, kw["newline"].value))

    def test_every_tier_is_one_the_card_defines(self):
        """No row may invent a tier, because the tier is the justification."""
        assert {t for _, _, t, _ in PINNED_WRITERS} <= {
            "1-live", "2-latent"}, (
            "PINNED_WRITERS may only hold writers whose bytes a non-folding"
            " reader sees (1-live) or will see (2-latent). A 3-tracked or"
            " 4-folds row is the churn this table exists to refuse.")

    def test_the_table_does_not_quietly_become_a_sweep(self):
        """Five rows against 934 unpinned writes is the point of the card.

        Not a cap on correctness — a new row with a real reader is welcome.
        It is a cap on *silence*: crossing it means the scoping argument in
        the roadmap card has changed and should be rewritten rather than
        outgrown one row at a time.
        """
        assert len(PINNED_WRITERS) <= 12, (
            "PINNED_WRITERS has grown past a dozen. Re-read the roadmap card"
            " writers-whose-bytes-are-compared-do-not-pin-their-newline: if"
            " a sweep is now the right answer, say so there first.")


class TestTheScriptPinsItsNewlines:
    """Only the script: its writers must round-trip byte for byte.

    Scoped tighter than ``SWEPT`` on purpose, and that asymmetry is the
    point. A *reader* needs no ``newline=`` at all, and most writers in this
    repo produce files whose line endings nothing compares, so sweeping
    every unpinned write the encoding sweep passed over would be ceremony at
    best and churn at worst. How many there are, and which subset is a real
    bug, is counted and scoped in its own roadmap card
    (``writers-whose-bytes-are-compared-do-not-pin-their-newline``) rather
    than hand-typed here. The script is the exception: it writes the step
    summary, the ``$GITHUB_OUTPUT`` lines and the weights file, and all three
    are read back by something that cares about the bytes.
    """

    def test_every_write_pins_lf(self):
        found = unpinned_newline(ROOT / "scripts/mutation_shards.py")
        assert not found, (
            "scripts/mutation_shards.py writes text without newline=\"\\n\" "
            "at %s. On Windows text mode turns every \\n into \\r\\n, so the "
            "file stops matching what the same report printed to stdout."
            % ", ".join("line %d (%s)" % f for f in found))
