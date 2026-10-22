# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Thin git wrapper (stdlib subprocess only)."""
from __future__ import annotations

import contextlib
import os
import re
import shutil
import signal
import subprocess
import sys
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from ..errors import BoostError
from . import util


def has_git() -> bool:
    """Return True when a `git` executable is on PATH."""
    return shutil.which("git") is not None


def require_git() -> None:
    """Raise the one "install git" error when `git` is not on PATH."""
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")


class BranchState(NamedTuple):
    """cwd's git state, keeping three states separate that callers used to
    flatten into one ``None``: no git binary on PATH, cwd outside any repo,
    and cwd inside a repo with no commits yet (``in_repo`` True, ``branch``
    None)."""
    has_git: bool
    in_repo: bool
    branch: str | None


def branch_state(cwd: Path | None = None) -> BranchState:
    """Return `cwd`'s :class:`BranchState`.

    Distinct from a bare ``None`` branch: a caller that only checked "do I
    have a branch name" could not tell a missing `git` binary from a cwd
    that simply isn't a repo, and reported both the same way.
    """
    if not has_git():
        return BranchState(has_git=False, in_repo=False, branch=None)
    cwd = cwd or Path.cwd()
    wt = run(["-C", str(cwd), "rev-parse", "--is-inside-work-tree"], check=False)
    if wt.returncode != 0 or wt.stdout.strip() != "true":
        return BranchState(has_git=True, in_repo=False, branch=None)
    proc = run(["-C", str(cwd), "rev-parse", "--abbrev-ref", "HEAD"], check=False)
    if proc.returncode == 0:
        return BranchState(has_git=True, in_repo=True,
                           branch=proc.stdout.strip() or None)
    # rev-parse resolves HEAD to a COMMIT, so it also fails on an unborn HEAD —
    # a repo between `git init` and its first commit. Readers here take a
    # `None` branch inside a repo for "not a repo at all": `boost context
    # status` printed "(not in a git repository)" while standing in one, and
    # `boost context apply` declined to do anything there. `symbolic-ref` reads
    # the ref HEAD points at without requiring it to exist yet, so the branch
    # is named from the first `git init` onward.
    sym = run(["-C", str(cwd), "symbolic-ref", "--short", "HEAD"], check=False)
    branch = sym.stdout.strip() or None if sym.returncode == 0 else None
    return BranchState(has_git=True, in_repo=True, branch=branch)


def run(args: list[str], cwd: Path | None = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    """Run `git *args` with captured text output; return the CompletedProcess.

    Raises BoostError if git is missing, on timeout, or (when `check`)
    on nonzero exit.
    """
    require_git()
    try:
        proc = _exec(
            ["git", *args], cwd=str(cwd) if cwd else None, timeout=timeout,
            # GIT_LFS_SKIP_SMUDGE: taps are indexed for their Markdown, and boost
            # never reads an LFS payload. Without this, tapping a repo that stores
            # large media in LFS downloads all of it on clone — heygen-com/hyperframes
            # tracks 163 files totalling 578 MB (83 .mp4 regression baselines under
            # packages/producer/tests, plus .png/.webm/.mov) beside the 31 SKILL.md
            # files boost actually wants. Pointer files still check out as text, so
            # discovery is unaffected. Only takes effect where git-lfs is installed;
            # elsewhere it is inert.
            # GIT_TERMINAL_PROMPT=0: without it, a clone/fetch against a
            # deleted or private repo falls back to an interactive
            # "Username for 'https://github.com':" prompt — on a real
            # terminal this blocks tap/import/update forever, and in a
            # sandbox with no tty it dies as "Device not configured", an
            # unrelated-looking crash for what is really a 404. With the
            # flag set git fails fast instead, with wording clone_shallow
            # and pull() translate into the actual cause.
            env=os.environ | {"GIT_LFS_SKIP_SMUDGE": "1",
                              "GIT_TERMINAL_PROMPT": "0"},
        )
    except subprocess.TimeoutExpired:
        name = _subcommand(args)
        raise BoostError("git%s timed out after %ds"
                         % (" " + name if name else "", timeout)) from None
    if check and proc.returncode != 0:
        name = _subcommand(args)
        raise BoostError("git%s failed: %s"
                         % (" " + name if name else "",
                            _git_error(proc.stderr or proc.stdout or "")))
    return proc


def _exec(argv: list[str], *, cwd: str | None, timeout: float,
          env: dict[str, str], text: bool = True) -> subprocess.CompletedProcess:
    """`subprocess.run(argv, capture_output=True, text=True)`, except that a
    timeout (or an interrupt) kills git's whole process tree, not only git.

    `subprocess.run(timeout=)` SIGKILLs the direct child and nothing else, and
    git does its network work in children — `git clone`/`fetch` over https run
    `git remote-http` and `git-remote-http`. Measured against a server that
    accepts and never answers: after "git clone timed out" both helpers were
    still running, reparented to PID 1 and holding the connection, long after
    boost had exited. So git runs as the leader of its own session (POSIX) and
    the timeout kills the group; on Windows `taskkill /T` walks the tree.
    """
    kwargs: dict = {}
    if sys.platform != "win32":
        kwargs["start_new_session"] = True
    # Git emits UTF-8 paths and messages on every platform; without an
    # explicit encoding, text mode decodes with the locale code page (cp1252
    # on en-US Windows), where a Cyrillic or CJK file name raises
    # UnicodeDecodeError out of `ls-files -z`.
    with subprocess.Popen(argv, cwd=cwd, env=env, text=text,
                          encoding="utf-8" if text else None,
                          errors="replace" if text else None,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          **kwargs) as proc:
        try:
            out, err = proc.communicate(timeout=timeout)
        except BaseException:
            # Ctrl-C too: in its own session git no longer gets the
            # terminal's SIGINT, and Popen's __exit__ would wait on it.
            _kill_tree(proc)
            raise
    return subprocess.CompletedProcess(argv, proc.returncode, out, err)


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill `proc` and every process it started, then reap it."""
    if sys.platform == "win32":
        # Best effort, bounded: a taskkill that is missing or hangs must not
        # replace the timeout being reported with an error of its own.
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, check=False, timeout=10)
        with contextlib.suppress(OSError):
            proc.kill()
    else:
        with contextlib.suppress(OSError):
            os.killpg(proc.pid, signal.SIGKILL)
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.communicate(timeout=5)


def _subcommand(args: list[str]) -> str:
    """The git subcommand in `args`, skipping global flags.

    Most calls in this module are repo-scoped (`-C <path> …`), so `args[0]` is
    `-C` and every one of their failures read `git -C failed` — naming a flag
    as if it were the command. `-C` and `-c` take a value; other leading flags
    do not.
    """
    i = 0
    while i < len(args):
        if args[i] in ("-C", "-c"):
            i += 2
        elif args[i].startswith("-"):
            i += 1
        else:
            return args[i]
    return ""


def _git_error(text: str) -> str:
    """Pull the one useful line out of git's multi-line failure output.

    git states the cause first and then advises, so the LAST line is usually the
    tail of a prose hint. A missing remote prints::

        fatal: '/nope' does not appear to be a git repository
        fatal: Could not read from remote repository.
        <blank>
        Please make sure you have the correct access rights
        and the repository exists.

    Taking the last line surfaced "and the repository exists." — a sentence
    fragment, with the one line that names the bad path thrown away. Prefer the
    first ``fatal:``/``error:`` line, which is git's own convention for the
    cause, and fall back to the last non-empty line for output that has neither.
    """
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    for line in lines:
        low = line.lower()
        if low.startswith(("fatal:", "error:")):
            return line
    return lines[-1] if lines else "unknown error"


# The wording git uses once GIT_TERMINAL_PROMPT=0 stops it from blocking on a
# credential prompt — all three cover the same underlying cause (a repo that
# does not exist, or exists but is private to the caller).
_CREDENTIAL_PROMPT_MARKERS = (
    "could not read username",
    "repository not found",
    "authentication failed",
)


def _credential_error(spec: str, stderr: str) -> BoostError | None:
    """A friendlier BoostError for a 404/private remote, or None otherwise.

    git's own text here — "could not read Username for '...': terminal
    prompts disabled" — reads as a login problem, not the actual cause. Name
    the spec and say what is really going on instead.
    """
    low = stderr.lower()
    if any(m in low for m in _CREDENTIAL_PROMPT_MARKERS):
        return BoostError("%s: repository not found or private" % spec,
                          hint="check the spelling, or that you have access")
    return None


# git's remote-helper transports run arbitrary commands straight from the URL
# (notably `ext::sh -c …`), so refuse them outright — boost only ever clones
# real http(s)/ssh/git remotes.
_UNSAFE_TRANSPORTS = ("ext::", "file::", "fd::")


# The working tree boost actually reads. `catalog.scan_dir` opens exactly three
# things: SKILL.md and loose workflow Markdown (`*.md`), the rule suffixes
# (`*.mdc`), and the rule filenames. Everything else a tap ships is freight —
# measured across 458 taps on one machine, 12 GB of clones held 1.9 GB of
# Markdown; `Shopify/agent-skills` was 611 MB for the 30 SKILL.md files boost
# wanted, and checks out at 11 MB under this cone with a byte-identical catalog.
#
# Deliberately duplicated from catalog.RULE_SUFFIXES / RULE_FILENAMES rather
# than imported: catalog imports gitutil, so the dependency cannot run the other
# way without a cycle. `tests/unit/test_gitutil_sparse.py` fails the build if the
# two ever drift, which is what keeps the duplication honest.
#
# `/.boost/*` is the one non-Markdown entry and is not optional: it holds
# `tap.manifest` and `tap.manifest.minisig` (core.provenance). Left out of the
# cone, every signed tap silently reports `unsigned` — a signature check that
# fails open, which is worse than one that fails.
SPARSE_PATTERNS = ("*.md", "*.mdc",
                   ".cursorrules", ".windsurfrules", ".clinerules",
                   "/.boost/*")

# git ≥2.25 for `--sparse`, ≥2.19 for `--filter`. Older git reports the flag as
# unknown rather than degrading, so we retry without it. A server that cannot
# filter needs no handling: git warns and sends everything by itself.
_NO_SUCH_OPTION = ("unknown option", "unrecognized option", "unknown switch")


def clone_shallow(url: str, dest: Path, sparse: bool = True) -> None:
    """Shallow-clone (`--depth 1`) `url` into `dest`, creating parent dirs.

    By default the clone is *blobless and sparse*: only the Markdown boost
    indexes is fetched and checked out (:data:`SPARSE_PATTERNS`), and anything
    else is left in the promisor remote until :func:`materialize` asks for it.
    Pass ``sparse=False`` for a full working tree — `boost import`, which reads
    a repo's whole contents rather than its catalog.

    Raises BoostError for unsafe remote-helper transports like `ext::`.
    """
    if url.lstrip().lower().startswith(_UNSAFE_TRANSPORTS):
        raise BoostError(
            "refusing to clone via unsafe git transport: %s" % url,
            hint="use an https://, ssh://, or git@ remote")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # `-c core.autocrlf=false`: check out tap content byte-for-byte. On Windows
    # the default `autocrlf=true` rewrites LF->CRLF on checkout, which would
    # change the bytes of a signed manifest (core.provenance) and any content we
    # digest for integrity — so a tap that verifies on Linux would fail on
    # Windows. Forcing it off makes a clone identical across platforms.
    # `--` ends option parsing so a URL beginning with `-` cannot be read as a
    # git flag — argument-injection defense-in-depth beside registry.parse_spec.
    base = ["clone", "--depth", "1", "--quiet",
            "-c", "core.autocrlf=false", "-c", "core.eol=lf"]
    tail = ["--", url, str(dest)]
    existed = dest.exists()
    try:
        _clone(base, tail, url, dest, sparse)
    except BaseException:
        # A clone that failed or timed out part-way leaves `dest/.git` behind:
        # not a tap (nothing recorded it), yet a directory under repos/ that
        # every later look at the disk takes for one. Only a dir this call
        # created is removed — a caller's existing tree is not ours to delete.
        if not existed:
            # util.remove_path, not shutil.rmtree(ignore_errors=True): git
            # writes its objects read-only, which Windows will not unlink.
            with contextlib.suppress(OSError):
                util.remove_path(dest)
        raise


def _clone(base: list[str], tail: list[str], url: str, dest: Path,
           sparse: bool) -> None:
    """The body of :func:`clone_shallow`, which owns cleanup on failure."""
    if not sparse:
        _clone_or_translate([*base, *tail], url)
        _refuse_empty(dest, url)
        return

    proc = run([*base, "--filter=blob:none", "--sparse", *tail],
               timeout=600, check=False)
    if proc.returncode != 0:
        stderr = (proc.stderr or "") + (proc.stdout or "")
        if not any(m in stderr.lower() for m in _NO_SUCH_OPTION):
            _raise_git_error("git clone failed", url, stderr)
        # Too old for --sparse/--filter: a full clone still works, just larger.
        shutil.rmtree(dest, ignore_errors=True)
        _clone_or_translate([*base, *tail], url)
    else:
        set_sparse_cone(dest)
    _refuse_empty(dest, url)


def _refuse_empty(dest: Path, url: str) -> None:
    """Raise, removing `dest`, when the clone has no commit at all.

    git clones a repo with no commits without complaint, so `boost tap` of a
    freshly `git init`ed directory reported "tapped (0 items)" over skills
    sitting uncommitted in its working tree — and the next `boost update` died
    on git's own "ambiguous argument 'FETCH_HEAD'". A tap is a clone, and a
    clone carries only what was committed.
    """
    if run(["-C", str(dest), "rev-parse", "--verify", "--quiet", "HEAD"],
           check=False).returncode == 0:
        return
    shutil.rmtree(dest, ignore_errors=True)
    raise BoostError("%s has no commits" % url,
                     hint="commit your skills first — a tap indexes committed "
                          "content only")


def _clone_or_translate(argv: list[str], url: str) -> None:
    """`run(argv, timeout=600)`, translating a credential-prompt failure.

    Runs with ``check=False`` and inspects the raw output itself rather than
    catching the BoostError `run` would otherwise raise: `_git_error` keeps
    only the first `fatal:`/`error:` line, which for a 404 discards the
    preceding `remote: Repository not found.` line `_credential_error` also
    matches against.
    """
    proc = run(argv, timeout=600, check=False)
    if proc.returncode != 0:
        stderr = (proc.stderr or "") + (proc.stdout or "")
        _raise_git_error("git clone failed", url, stderr)


def _raise_git_error(prefix: str, spec: str, stderr: str) -> None:
    """Raise a BoostError for a failed git op, translating a credential
    prompt into the actual cause first."""
    cred = _credential_error(spec, stderr)
    if cred is not None:
        raise cred
    raise BoostError("%s: %s" % (prefix, _git_error(stderr)))


def set_sparse_cone(repo: Path, patterns=SPARSE_PATTERNS) -> None:
    """Restrict `repo`'s working tree to `patterns`.

    `--no-cone` because cone mode matches directory prefixes only, and boost
    needs `*.md` at any depth.
    """
    # Under the same lock as :func:`_sparse_add`, which deletes a
    # sparse-checkout.lock it finds while holding it: a `boost compact`
    # running `set` beside an install must not have its live lock taken.
    with _sparse_guard(Path(repo)):
        run(["-C", str(repo), "sparse-checkout", "set", "--no-cone", *patterns])
    _SPARSE[str(repo)] = True


def narrow(repo: Path, patterns=SPARSE_PATTERNS) -> None:
    """Apply the sparse cone to an existing clone, in place and offline.

    For the clones already on disk when taps went sparse. The freight leaves the
    working tree; `.git` keeps every blob it already downloaded, because a clone
    cannot be made blobless after the fact — that needs a re-clone.

    The refresh is load-bearing: git silently declines to remove a path it
    considers not up to date, so a clone whose mtimes have moved — a restored
    backup, a copied BOOST_HOME — keeps every file while reporting success.
    `update-index --refresh` exits nonzero precisely when it had work to do.
    """
    run(["-C", str(repo), "update-index", "--refresh"], check=False)
    set_sparse_cone(repo, patterns)
    run(["-C", str(repo), "sparse-checkout", "reapply"], check=False)


# repo path -> is-sparse, for the lifetime of the process. `materialize` runs
# once per installed skill in the loops `outdated`, `drift` and `sync` build, and
# a git subprocess each time cost ~135 ms — 4.5 s added to a 33-skill machine.
# Sparseness only changes through this module, which invalidates on the way.
_SPARSE: dict[str, bool] = {}


def _sparse_list(repo: Path) -> set[str] | None:
    """Patterns in `repo`'s sparse-checkout file, or None if it has none.

    A plain file read, so the common "already materialized" answer costs no
    subprocess at all.
    """
    try:
        text = (Path(repo) / ".git" / "info"
                / "sparse-checkout").read_text(encoding="utf-8")
    except OSError:
        return None
    return {_pattern_line(ln) for ln in text.splitlines()
            if ln.strip() and not ln.startswith("#")}


def _pattern_line(line: str) -> str:
    """One sparse-checkout line as git reads it: an escaped trailing space
    (``\\ ``, which :func:`sparse_escape` writes) is part of the pattern."""
    body = line.strip()
    tail = line.rstrip("\r")
    return tail.lstrip() if tail.endswith("\\ ") else body


def is_sparse(repo: Path) -> bool:
    """True when `repo` has a sparse checkout configured."""
    key = str(repo)
    if key not in _SPARSE:
        proc = run(["-C", key, "config", "--get", "core.sparseCheckout"],
                   check=False)
        _SPARSE[key] = proc.stdout.strip().lower() == "true"
    return _SPARSE[key]


#: What git's no-cone sparse-checkout (gitignore) syntax reads as a wildcard
#: or an escape rather than as itself.
_PATTERN_SPECIAL = frozenset("\\[]*?")


def sparse_escape(rel: str) -> str:
    """``rel`` spelled as a sparse-checkout pattern matching only itself.

    The cone is no-cone (gitignore syntax), and `sparse-checkout add` writes
    a pattern verbatim, so a skill dir named ``glob[1]`` added as
    ``/skills/glob[1]/*`` was a character class matching ``glob1``: the real
    dir was never checked out and its ``scripts/`` installed as nothing,
    with no error. Each metacharacter takes a backslash, and so does a
    trailing space, which gitignore otherwise strips. A leading ``!`` or
    ``#`` needs nothing: every pattern built from this starts with ``/``.
    """
    out = "".join("\\" + c if c in _PATTERN_SPECIAL else c for c in rel)
    stripped = out.rstrip(" ")
    return stripped + "\\ " * (len(out) - len(stripped))


def materialize(repo: Path, rel_dir: str) -> None:
    """Widen `repo`'s sparse checkout so all of `rel_dir` is on disk.

    A skill's own files — `scripts/`, `assets/`, `references/` — sit outside the
    Markdown cone, so they exist in the index but not the working tree. Copying
    such a directory without this step succeeds and silently installs a skill
    with its scripts missing, which is why every consumer of a tap's real files
    goes through ``store.source_dir_for``.

    Uses `add`, never `set`: `set` replaces the pattern list and would un-fetch
    every previously materialized skill. A no-op on full clones (including every
    clone made before taps went sparse).

    A skill at the repo root (``rel_dir`` ``"."``) owns the whole tree, so the
    cone widens to ``/*``. This was once a no-op on the theory that the root
    needs no narrowing, but a sparse clone's root holds only Markdown: the
    skill's ``scripts/`` installed as nothing while verify, drift and doctor
    all called the copy healthy.

    An unreadable sparse-checkout file falls through to the git-config check
    rather than returning early: degrading to slower-but-correct is fine, and
    degrading to a silently incomplete copy is the bug this function exists to
    prevent.
    """
    rel = rel_dir.strip("/")
    if rel in ("", "."):
        rel = "."
        patterns = ["/*"]
    else:
        patterns = ["/%s/*" % sparse_escape(form) for form in _spellings(rel)]
    have = _sparse_list(repo)
    if have is not None and all(p in have for p in patterns):
        return
    if not is_sparse(Path(repo)):
        return
    _sparse_add(Path(repo), patterns, rel)
    _require_checked_out(Path(repo), rel)


#: Passed to every git call that writes or reads a sparse pattern or an index
#: path. macOS git defaults ``core.precomposeunicode`` to true and rewrites its
#: *argv* to NFC, so a pattern for a path the index holds in NFD (a repo
#: authored on Linux: ``cafe\u0301``) was stored precomposed and matched
#: nothing. The skill's ``scripts/`` stayed skip-worktree and installed as
#: nothing, while doctor, drift and verify all called the copy healthy.
_RAW_PATHS = ["-c", "core.precomposeunicode=false"]


def _spellings(rel: str) -> list[str]:
    """``rel`` in NFC and NFD, deduplicated (one entry for plain ASCII).

    The name boost holds comes from a directory walk, and which form that
    returns depends on the filesystem (HFS+ decomposes, APFS keeps what git
    wrote), not on what the index records. A pattern in each form matches
    whichever one the index holds.
    """
    return list(dict.fromkeys(unicodedata.normalize(f, rel)
                              for f in ("NFC", "NFD")))


def _fold(path: str) -> str:
    """``path`` as a case- and normalization-insensitive filesystem sees it."""
    return unicodedata.normalize("NFC", path).casefold()


def _require_checked_out(repo: Path, rel: str) -> None:
    """Refuse when a file under ``rel`` is still outside the sparse checkout.

    Run once, right after the cone was widened for ``rel``: a pattern git
    stored but did not match leaves the files skip-worktree, and the copy
    that follows would install the half that exists and report success.
    """
    proc = run([*_RAW_PATHS, "-C", str(repo), "ls-files", "-t", "-z"],
               check=False)
    # Normalization only, never case: on a case-sensitive clone
    # ``skills/Lint`` is another skill, rightly left outside the checkout
    # that widened ``skills/lint``.
    # The root (``"."``) owns every path, so any skip-worktree file fails it.
    # ``rel`` itself matches too: a link may lead to a file.
    want = unicodedata.normalize("NFC", rel)

    def under(path: str) -> bool:
        path = unicodedata.normalize("NFC", path)
        return rel == "." or path == want or path.startswith(want + "/")

    skipped = [rec[2:] for rec in (proc.stdout or "").split("\0")
               if rec.startswith("S ") and under(rec[2:])]
    if skipped:
        raise BoostError(
            "could not check out %d file%s of %s from the %s tap (%s), so "
            "installing it would copy a partial skill"
            % (len(skipped), "" if len(skipped) == 1 else "s",
               "the repo root" if rel == "." else rel, repo.name,
               ", ".join(sorted(skipped)[:5])),
            hint="`boost update %s` and try again; if it persists, the tap's "
                 "sparse checkout cannot match this path" % repo.name,
            wrap=True)


#: The index mode of a gitlink: a submodule's commit, not a tree or a blob.
GITLINK_MODE = "160000"


def gitlinks(repo: Path, rel_dir: str) -> list[str]:
    """Repo-relative paths under ``rel_dir`` that are git submodules.

    boost never runs ``submodule update`` — a tap is a shallow clone of one
    repo — so a submodule checks out as an empty directory, and a skill whose
    ``scripts/`` is one installed as nothing, reported as a success. Read from
    the index (``ls-files -s``, mode ``160000``), which knows a gitlink
    whether or not the sparse cone holds its path. Empty when ``repo`` is not
    a git checkout git can read: nothing can be said about it, and the
    install that follows reports its own failures.
    """
    rel = rel_dir.strip("/")
    spec = [] if rel in ("", ".") else ["--", rel]
    proc = run([*_RAW_PATHS, "-C", str(repo), "ls-files", "-s", "-z", *spec],
               check=False)
    if proc.returncode != 0:
        return []
    found: list[str] = []
    for rec in (proc.stdout or "").split("\0"):
        meta, _tab, path = rec.partition("\t")
        if path and meta.split(" ", 1)[0] == GITLINK_MODE:
            found.append(path)
    return sorted(found)


def materialize_paths(repo: Path, rels: list[str]) -> None:
    """Widen `repo`'s sparse checkout to each repo-relative path in `rels`.

    For what a skill's symlinks point at elsewhere in the tap
    (``skills/x/helper.py -> ../../shared/helper.py``): :func:`materialize`
    checks out the skill's own dir, and a link out of it would otherwise lead
    to a file the cone never fetched. Each path is added as itself and as a
    directory (``/p`` and ``/p/*``), since a link may name either. One `add`
    for all of them, never `set`, and a no-op on a full clone.

    Each path is then checked as :func:`materialize` checks a skill's dir: a
    pattern git stored but did not match would leave the target
    skip-worktree, and the copy would hold whatever happened to be on disk.
    """
    patterns: list[str] = []
    for rel in rels:
        rel = rel.strip("/")
        if rel and rel != ".":
            for form in _spellings(rel):
                form = sparse_escape(form)
                patterns += ["/%s" % form, "/%s/*" % form]
    have = _sparse_list(repo) or set()
    patterns = [p for p in dict.fromkeys(patterns) if p not in have]
    if not patterns or not is_sparse(Path(repo)):
        return
    _sparse_add(Path(repo), patterns, ", ".join(rels))
    for rel in rels:
        rel = rel.strip("/")
        if rel and rel != ".":
            _require_checked_out(Path(repo), rel)


_CORE_IGNORECASE = re.compile(
    r"^\[core\][^\[]*?^\s*ignorecase\s*=\s*(true|yes|on|1)\s*$",
    re.IGNORECASE | re.MULTILINE | re.DOTALL)


def _ignorecase(repo: Path) -> bool:
    """Whether the clone records ``core.ignorecase = true``, read from
    ``.git/config`` as a file: `rebuild_tap` asks once per tap, and a git
    subprocess each time is ~40 ms over hundreds of taps."""
    try:
        text = (repo / ".git" / "config").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return _CORE_IGNORECASE.search(text) is not None


def case_collisions(repo: Path) -> list[list[str]]:
    """Index paths of ``repo`` that its checkout cannot hold apart.

    Each group is two or more paths that differ only by case (or Unicode
    normalization), sorted, e.g. ``["skills/Lint/SKILL.md",
    "skills/lint/SKILL.md"]``. On a case-insensitive filesystem git checks
    out one file for the lot, and every other file of each spelling lands in
    the same directory: `git clone` warns "the following paths have
    collided", which boost captures and never shows. Empty unless the clone
    records ``core.ignorecase`` (git sets it per clone after probing the
    filesystem), because on a case-sensitive one each path is its own file.

    Directories are grouped too, each spelling with a trailing ``/``
    (``["skills/Lint/", "skills/lint/"]``): two dirs that share no file name
    still check out as one, so ``skills/Lint`` holds ``skills/lint``'s
    scripts without any file colliding.
    """
    if not _ignorecase(Path(repo)):
        return []
    proc = run([*_RAW_PATHS, "-C", str(repo), "ls-files", "-z"], check=False)
    groups: dict[str, set[str]] = {}
    for path in (proc.stdout or "").split("\0"):
        if not path:
            continue
        groups.setdefault(_fold(path), set()).add(path)
        parts = path.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            spelled = "/".join(parts[:i]) + "/"
            groups.setdefault(_fold(spelled), set()).add(spelled)
    return sorted(sorted(g) for g in groups.values() if len(g) > 1)


#: Words in a git failure that mean the promisor fetch could not reach the
#: remote — the one case where "this needs network" is the true cause.
_TRANSPORT_ERRORS = ("unable to access", "could not resolve", "could not read "
                     "from remote", "failed to connect", "connection",
                     "timed out", "network")
NETWORK_HINT = "this needs network — the tap stores only Markdown locally"
#: Longer than :func:`run`'s own five minutes: a waiter must outlast the
#: slowest fetch another install can be making under the same lock.
SPARSE_LOCK_TIMEOUT = 330.0


def _git_lock_busy(err: BoostError) -> bool:
    """True for git's "Unable to create '...sparse-checkout.lock': File exists"."""
    text = str(err)
    return "sparse-checkout.lock" in text and "File exists" in text


def _sparse_hint(err: BoostError, git_lock: Path) -> str | None:
    if _git_lock_busy(err):
        return ("another git process is working in this tap's clone; if none "
                "is, remove %s" % git_lock)
    low = str(err).lower()
    if any(w in low for w in _TRANSPORT_ERRORS):
        return NETWORK_HINT
    return None


def _sparse_guard(repo: Path):
    """Boost's own lock on ``repo``'s sparse cone (see :func:`_sparse_add`).

    Not strict: where the sidecar cannot be made — ``.git`` is a gitfile, or
    read-only — git's own error about that clone is the one worth reading,
    not a FileExistsError from boost's lock.
    """
    return util.file_lock(repo / ".git" / "boost-sparse.lock",
                          SPARSE_LOCK_TIMEOUT,
                          what="the %s tap's checkout" % repo.name,
                          strict=False)


def _sparse_add(repo: Path, patterns: list[str], what: str) -> None:
    """`git sparse-checkout add` ``patterns``, one boost process at a time.

    git takes ``.git/info/sparse-checkout.lock`` for the duration and fails
    outright — no wait, no retry — when it is already there, so 40 parallel
    `boost install`s from one tap lost one to "File exists". And a git that
    is killed (Ctrl-C, or :func:`run`'s timeout) cannot remove it, which used
    to fail every later install from that tap for good. So boost serialises on
    its own OS lock (``.git/boost-sparse.lock``, released when its holder
    dies), and while holding it treats a leftover git lock as a dead git's:
    no other boost can be in a sparse checkout of this clone just then. It
    is removed once and the add retried, the way :func:`unshallow` handles
    ``shallow.lock``.

    The cone is re-read inside the lock: the install that held it may have
    just added the very pattern this one is waiting to add.
    """
    git_lock = repo / ".git" / "info" / "sparse-checkout.lock"
    with _sparse_guard(repo):
        have = _sparse_list(repo) or set()
        todo = [p for p in patterns if p not in have]
        if not todo:
            return
        argv = [*_RAW_PATHS, "-C", str(repo), "sparse-checkout", "add", *todo]
        try:
            try:
                run(argv)
            except BoostError as e:
                if not _git_lock_busy(e):
                    raise
                # Suppressed: on Windows a live git holding it open makes
                # unlink raise, and the retry's own error then says so.
                with contextlib.suppress(OSError):
                    git_lock.unlink(missing_ok=True)
                run(argv)
        except BoostError as e:
            # The blobs live in the promisor remote, so this is the one step in
            # an install that can need the network — but say so only when the
            # error is a transport one: a local tap needs none, and blaming
            # the network for a lock file sent the user nowhere.
            raise BoostError(
                "could not fetch %s from the %s tap: %s" % (what, repo.name, e),
                hint=_sparse_hint(e, git_lock)) from None


def _depth(repo: Path) -> list[str]:
    """``--depth 1`` for a shallow clone, nothing for a complete one.

    A clone :func:`unshallow` deepened so its skills' dates can be read must
    stay deep: a ``fetch --depth 1`` puts ``.git/shallow`` back and cuts the
    history to one commit again, and every date read after it is the HEAD's.
    """
    return ["--depth", "1"] if is_shallow(repo) else []


_HEADS = "refs/heads/"
_WILDCARD_REFSPEC = "+refs/heads/*:refs/remotes/origin/*"


def remote_default_branch(repo: Path) -> str:
    """The branch the remote's HEAD points at *now*, or "" when it won't say.

    Asks the remote (``ls-remote --symref origin HEAD``) rather than reading
    ``origin/HEAD``, which git sets once at clone time and never refreshes. An
    old server, a dumb transport or a detached remote HEAD prints no symref
    line; that, and any failure, is "" — the caller keeps today's behaviour.
    """
    proc = run(["-C", str(repo), "ls-remote", "--symref", "origin", "HEAD"],
               check=False)
    if proc.returncode != 0:
        return ""
    for line in (proc.stdout or "").splitlines():
        ref, _, name = line.partition("\t")
        if name.strip() == "HEAD" and ref.startswith("ref: " + _HEADS):
            return ref[len("ref: " + _HEADS):].strip()
    return ""


def follow_default_branch(repo: Path) -> str:
    """Point `repo`'s fetch refspec at the remote's current default branch.

    A tap is cloned ``--depth 1``, which implies ``--single-branch``: the
    refspec names the branch that was default *at clone time*. When upstream
    renames ``master`` to ``main`` or switches HEAD to a new branch, a plain
    ``fetch origin`` keeps fetching the old one — so `boost update` reported a
    stale clone "already up to date", and once the old branch was deleted it
    failed on every run with "couldn't find remote ref" until the tap was
    re-cloned. Returns the branch followed, or "" when the remote would not
    name one (the refspec is then left alone). A wildcard refspec already
    covers every branch and is kept.
    """
    branch = remote_default_branch(repo)
    if not branch:
        return ""
    spec = "+%s%s:refs/remotes/origin/%s" % (_HEADS, branch, branch)
    have = run(["-C", str(repo), "config", "--get-all", "remote.origin.fetch"],
               check=False).stdout.split()
    if spec not in have and _WILDCARD_REFSPEC not in have:
        run(["-C", str(repo), "config", "--replace-all",
             "remote.origin.fetch", spec])
    return branch


def read_blob(repo: Path, rev: str, path: str) -> bytes | None:
    """The exact bytes of ``path`` at commit ``rev``, or ``None`` if absent.

    Read from the object store, not the working tree, so a fetched commit can
    be inspected before the clone moves onto it. Bytes, not text: a signature
    covers the manifest's bytes, and text mode would translate its newlines.
    A blobless clone fetches the blob on demand; a blob it cannot fetch reads
    as absent, which a signature check treats as unsigned — failing closed.
    """
    require_git()
    try:
        proc = _exec(["git", "-C", str(repo), "cat-file", "blob",
                      "%s:%s" % (rev, path)], cwd=None, timeout=300,
                     env=os.environ | {"GIT_TERMINAL_PROMPT": "0"}, text=False)
    except subprocess.TimeoutExpired:
        return None
    return proc.stdout if proc.returncode == 0 else None


def _rev(repo: Path, ref: str) -> str:
    """``ref`` resolved to a commit hash in ``repo``, or "" if it does not."""
    proc = run(["-C", str(repo), "rev-parse", "--verify", "--quiet",
                ref + "^{commit}"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def pull(repo: Path, verify: Callable[[str], None] | None = None) -> str:
    """Update a clone to the remote's current default branch, keeping it as
    shallow as it is. Returns a one-line summary.

    ``verify`` is called with the fetched commit **before** the clone moves
    onto it; raising from it leaves the working tree and HEAD exactly where
    they were. It is how a tap's provenance is checked on update: resetting
    first and checking after would put an unverified tree on disk, scannable
    and installable, for as long as the check took — or for good, if it
    crashed.
    """
    before = head_commit(repo)
    branch = follow_default_branch(repo)
    proc = run(["-C", str(repo), "fetch", *_depth(repo), "--quiet", "origin"],
              check=False)
    if proc.returncode != 0:
        stderr = (proc.stderr or "") + (proc.stdout or "")
        _raise_git_error("git fetch failed", remote_url(repo) or str(repo), stderr)
    if branch:
        # `origin/HEAD` is a clone-time symref; move it with the branch so the
        # reset below lands on what was just fetched, not on the old branch.
        run(["-C", str(repo), "symbolic-ref", "refs/remotes/origin/HEAD",
             "refs/remotes/origin/" + branch], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    target = _rev(repo, "origin/HEAD")
    if not target or target == before:
        fetched = _rev(repo, "FETCH_HEAD")
        if not fetched and not before:
            # An upstream with no commits fetches nothing, and resetting to the
            # FETCH_HEAD it never wrote surfaced as git's "ambiguous argument
            # 'FETCH_HEAD'" — true, and no help to anyone holding a tap.
            raise BoostError(
                "%s has no commits" % (remote_url(repo) or repo),
                hint="commit to it first — a tap indexes committed content only")
        target = fetched or target
    if target:
        if verify is not None and target != before:
            verify(target)
        # Reset even when nothing moved: it is also what puts a hand-edited
        # clone back to the commit it claims to be at.
        run(["-C", str(repo), "reset", "--hard", "--quiet", target])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (
        before[:7] or "(no commits)", after[:7])


def head_commit(repo: Path) -> str:
    """Return the full HEAD commit hash of `repo`, or "" if unresolvable.

    "" with no git on PATH as well: this is a probe, and `run` would raise the
    "git is required" error from inside it — which ended `boost doctor` (and
    its `--json`) at the first cached tap, before its verdict, on the one
    machine where doctor's own "git not found" row was the useful line.
    """
    if not has_git():
        return ""
    proc = run(["-C", str(repo), "rev-parse", "HEAD"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


#: git's words, lowercased, for a fetch by SHA of a commit the remote does not
#: serve: `upload-pack` over file/ssh ("not our ref"), the smart-HTTP protocol
#: ("unadvertised object") and a protocol-v2 server ("couldn't find remote
#: ref"). After a force-push and gc upstream, a pinned commit is simply gone.
_MISSING_COMMIT = ("not our ref", "unadvertised object",
                   "couldn't find remote ref")


class CommitNotUpstream(BoostError):
    """A commit asked for by SHA is not on the remote any more (or never was).

    Its own type so a caller that knows *why* it wanted the commit -- a tap's
    pin -- can say so and name the remedy that works, rather than relaying
    git's "fatal: git upload-pack: not our ref <sha>".
    """

    def __init__(self, sha: str, url: str):
        self.sha, self.url = sha, url
        super().__init__(
            "commit %s is not on %s (history rewritten upstream?)"
            % (sha[:7], url),
            hint="pin a commit that exists there, or tap without `--at` to "
                 "follow its default branch", wrap=True)


def checkout_commit(repo: Path, sha: str,
                    verify: Callable[[str], None] | None = None) -> None:
    """Detach `repo` at `sha`, fetching that commit first if it is absent.

    A tap is cloned `--depth 1`, so the commit a published shard was built from
    is usually *not* in the clone: the fetch is the normal path, not the
    fallback. GitHub serves a fetch by full SHA for a reachable commit, which
    is what makes pinning possible without un-shallowing a repo that exists to
    stay small.

    The fetch keeps `--depth 1` and the blobless filter for the same reason the
    clone does — pinning a tap must not cost the history and blobs the sparse
    clone was built to avoid (458 taps held 12 GB before that work). A clone
    that is already complete stays so (:func:`_depth`).
    """
    if not _is_sha(sha):
        raise BoostError("%r is not a full commit SHA" % sha,
                         hint="pin with the 40-character hash a manifest names")
    have = run(["-C", str(repo), "cat-file", "-e", sha + "^{commit}"],
               check=False)
    if have.returncode != 0:
        fetched = run(["-C", str(repo), "fetch", "--quiet", *_depth(repo),
                       "--filter=blob:none", "origin", sha], check=False)
        if fetched.returncode != 0:
            text = fetched.stderr or fetched.stdout or ""
            if any(m in text.lower() for m in _MISSING_COMMIT):
                raise CommitNotUpstream(sha, remote_url(repo) or "its remote")
            raise BoostError("git fetch failed: %s" % _git_error(text))
    if verify is not None:
        # As in `pull`: the commit is checked while the tree is still on the
        # old one, so a refusal moves nothing.
        verify(sha)
    run(["-C", str(repo), "checkout", "--quiet", "--detach", sha])
    # A detached checkout leaves the sparse cone as it was, but re-applying is
    # cheap and keeps a pinned clone byte-identical to a freshly cloned one.
    run(["-C", str(repo), "sparse-checkout", "reapply"], check=False)


def _is_sha(value: str) -> bool:
    """True for a full 40-character hex commit hash.

    Deliberately strict. An abbreviated hash is ambiguous across a fetch, and a
    branch or tag name is not a pin at all — both would silently give a
    different tree than the shard was built against, which `import_shard` would
    then refuse with a confusing commit mismatch.
    """
    return len(value) == 40 and all(c in "0123456789abcdef" for c in value.lower())


def tracks(repo: Path, rel: str) -> bool:
    """Whether git at ``repo`` tracks ``rel``, so `git checkout -- rel` restores it.

    False without git or outside a work tree, never raising: it decides which
    remedy a message offers, and a checkout git cannot do is no remedy.
    """
    if not has_git():
        return False
    proc = run(["-C", str(repo), "ls-files", "--error-unmatch", "--", rel],
               check=False)
    return proc.returncode == 0


def remote_url(repo: Path) -> str:
    """Return the URL of `repo`'s `origin` remote, or "" if it has none."""
    proc = run(["-C", str(repo), "remote", "get-url", "origin"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def is_shallow(repo: Path) -> bool:
    """True when ``repo`` is a shallow clone, i.e. its history is cut short.

    ``.git/shallow`` lists the graft points and exists only in a shallow
    clone: git itself checks this file. A short log is not the same thing.
    A tap cloned from a local path is complete, because git ignores
    ``--depth`` there, and a path with one commit has a one-line history in
    any clone. Using the log's length made ``boost changelog`` recommend
    ``fetch --unshallow``, which fails on a complete repository.
    """
    return (Path(repo) / ".git" / "shallow").is_file()


#: Seconds :func:`unshallow` waits for history before giving the date up.
UNSHALLOW_TIMEOUT = 60


def unshallow(repo: Path) -> bool:
    """Fetch the rest of a shallow clone's history, still without blobs.

    What makes a skill's date readable (:func:`path_updated_at`). Measured on
    real taps: 0.5 s and 156 KB for ``anthropics/skills`` (60 commits), 3 s
    and 11.5 MB for one with 3,220; a second run costs nothing. Commits and
    trees only — a blobless fetch brings no file outside the sparse cone.
    True when the clone is complete afterwards; a failure (offline, a remote
    that is gone) is False and raises nothing, since a date is never worth
    failing the install or update that asked for it. The fetch gets
    :data:`UNSHALLOW_TIMEOUT` rather than :func:`run`'s five minutes, so a
    huge or stalled remote costs an install a minute and an undated skill,
    not five.

    A timeout kills git, which then cannot remove the ``.git/shallow.lock``
    it took, and every later fetch of that tap (``boost update``) fails on
    "Unable to create ... shallow.lock: File exists". So a lock this fetch
    created is removed when it dies; one that was there before is another
    git process's and is left alone.
    """
    if not is_shallow(repo):
        return True
    lock = Path(repo) / ".git" / "shallow.lock"
    held = lock.exists()
    try:
        proc = run(["-C", str(repo), "fetch", "--quiet", "--unshallow",
                    "--filter=blob:none", "origin"], check=False,
                   timeout=UNSHALLOW_TIMEOUT)
    except BoostError:
        if not held:
            lock.unlink(missing_ok=True)
        return False
    return proc.returncode == 0 and not is_shallow(repo)


def _graft_points(repo: Path) -> set[str]:
    """The commits a shallow repo's history is cut at; empty for a complete one.

    Located with ``rev-parse --git-path``, so a worktree or submodule whose
    ``.git`` is a file finds its repository's list too.
    """
    proc = run(["-C", str(repo), "rev-parse", "--git-path", "shallow"], check=False)
    rel = proc.stdout.strip()
    if proc.returncode != 0 or not rel:
        return set()
    try:
        text = (Path(repo) / rel).read_text(encoding="utf-8")
    except OSError:
        return set()
    return {ln.strip() for ln in text.splitlines() if ln.strip()}


def path_updated_at(repo: Path, rel_dir: str = ".", rev: str = "HEAD") -> int | None:
    """When ``rel_dir`` last changed at ``rev``: a Unix time, or None.

    The committer time of the newest commit touching any file under the dir,
    so a change to a script or an asset counts as much as one to ``SKILL.md``.
    None when no commit touched it, git fails, or the commit found is one the
    history is cut at (:func:`_graft_points`). That last is not caution: git
    reads a graft point as a root commit that added every file, so in a
    ``--depth 1`` clone every dir "changed" in the HEAD commit, and the date
    is the HEAD's for all of them. Only the trees are read, which a blobless
    clone holds.
    """
    proc = run(["-C", str(repo), "log", "-1", "--format=%H" + _LOG_SEP + "%ct",
                rev or "HEAD", "--", rel_dir or "."], check=False)
    sha, _sep, when = proc.stdout.strip().partition(_LOG_SEP)
    if proc.returncode != 0 or not when.isdigit():
        return None
    return None if sha in _graft_points(repo) else int(when)


def head_time(repo: Path) -> int | None:
    """The HEAD commit's committer time, or None. No earlier than any date
    :func:`path_updated_at` can find at HEAD, shallow clone or not."""
    proc = run(["-C", str(repo), "log", "-1", "--format=%ct", "HEAD"], check=False)
    when = proc.stdout.strip()
    return int(when) if proc.returncode == 0 and when.isdigit() else None


def log_for_path(repo: Path, rel_path: str = ".", n: int = 20) -> list[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--date=short", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


#: Field separator for the machine-readable log format. ASCII US (unit
#: separator) rather than a printable delimiter: git will not insert it, and a
#: commit subject may legitimately contain a pipe, a tab, or the two-space run
#: `log_for_path`'s display format uses between its columns.
_LOG_SEP = "\x1f"


def log_entries(repo: Path, rel_path: str = ".", n: int = 20) -> list[dict]:
    """Structured one-line log rows for a path inside a repo.

    The data counterpart of :func:`log_for_path`, which formats the same
    commits for display. Splitting that display string back into fields is a
    guess — the columns are separated by two spaces and an author name or a
    subject may contain them — so this asks git for an unambiguous separator
    instead of taking the format apart afterwards.

    ``maxsplit`` is pinned to three so a subject containing the separator
    cannot shift the other fields, and a blank subject still yields all four
    keys rather than a short row the caller would have to pad.
    """
    proc = run(["-C", str(repo), "log", "--date=short", "-n", str(n),
                "--pretty=format:" + _LOG_SEP.join(("%h", "%ad", "%an", "%s")),
                "--", rel_path], check=False)
    rows = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split(_LOG_SEP, 3)
        if len(parts) < 4:
            continue
        sha, date, author, subject = parts
        rows.append({"sha": sha, "date": date, "author": author,
                     "subject": subject})
    return rows


def is_repo(path: Path) -> bool:
    """Return True when `path` contains a `.git` entry."""
    return (Path(path) / ".git").exists()


def is_repo_root(path: Path) -> bool:
    """True when `path` is itself a git repository, bare or with a worktree.

    :func:`is_repo` asks for a ``.git`` entry, which every bare repository
    (``git clone --bare``, the usual shape of a local or self-hosted remote)
    lacks — so `boost tap <dir>.git` called a valid repo "not a git
    repository" and suggested `git init` on it. ``rev-parse --git-dir`` alone
    over-accepts: run from a subdirectory of a repo it answers with the
    parent's git dir, and that subdirectory is not something git can clone.
    So the git dir must be ``path`` itself (bare) or ``path/.git``. Both sides
    are resolved: on macOS a ``/var/folders`` path resolves to ``/private/var``.
    """
    p = Path(path)
    if (p / ".git").exists():
        return True
    proc = run(["-C", str(p), "rev-parse", "--absolute-git-dir"], check=False)
    if proc.returncode != 0:
        return False
    try:
        return Path(proc.stdout.strip()).resolve() == p.resolve()
    except OSError:
        return False
