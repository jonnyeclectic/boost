# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Thin git wrapper (stdlib subprocess only)."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from ..errors import BoostError


def has_git() -> bool:
    """Return True when a `git` executable is on PATH."""
    return shutil.which("git") is not None


def run(args: list[str], cwd: Path | None = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    """Run `git *args` with captured text output; return the CompletedProcess.

    Raises BoostError if git is missing, on timeout, or (when `check`)
    on nonzero exit.
    """
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git", *args], cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
            # GIT_LFS_SKIP_SMUDGE: taps are indexed for their Markdown, and boost
            # never reads an LFS payload. Without this, tapping a repo that stores
            # large media in LFS downloads all of it on clone — heygen-com/hyperframes
            # tracks 163 files totalling 578 MB (83 .mp4 regression baselines under
            # packages/producer/tests, plus .png/.webm/.mov) beside the 31 SKILL.md
            # files boost actually wants. Pointer files still check out as text, so
            # discovery is unaffected. Only takes effect where git-lfs is installed;
            # elsewhere it is inert.
            env=os.environ | {"GIT_LFS_SKIP_SMUDGE": "1"},
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout)) from None
    if check and proc.returncode != 0:
        name = _subcommand(args)
        raise BoostError("git%s failed: %s"
                         % (" " + name if name else "",
                            _git_error(proc.stderr or proc.stdout or "")))
    return proc


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
    if not sparse:
        run([*base, *tail], timeout=600)
        return

    proc = run([*base, "--filter=blob:none", "--sparse", *tail],
               timeout=600, check=False)
    if proc.returncode != 0:
        stderr = (proc.stderr or "") + (proc.stdout or "")
        if not any(m in stderr.lower() for m in _NO_SUCH_OPTION):
            raise BoostError("git clone failed: %s" % _git_error(stderr))
        # Too old for --sparse/--filter: a full clone still works, just larger.
        shutil.rmtree(dest, ignore_errors=True)
        run([*base, *tail], timeout=600)
        return
    set_sparse_cone(dest)


def set_sparse_cone(repo: Path, patterns=SPARSE_PATTERNS) -> None:
    """Restrict `repo`'s working tree to `patterns`.

    `--no-cone` because cone mode matches directory prefixes only, and boost
    needs `*.md` at any depth.
    """
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
    return {ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.startswith("#")}


def is_sparse(repo: Path) -> bool:
    """True when `repo` has a sparse checkout configured."""
    key = str(repo)
    if key not in _SPARSE:
        proc = run(["-C", key, "config", "--get", "core.sparseCheckout"],
                   check=False)
        _SPARSE[key] = proc.stdout.strip().lower() == "true"
    return _SPARSE[key]


def materialize(repo: Path, rel_dir: str) -> None:
    """Widen `repo`'s sparse checkout so all of `rel_dir` is on disk.

    A skill's own files — `scripts/`, `assets/`, `references/` — sit outside the
    Markdown cone, so they exist in the index but not the working tree. Copying
    such a directory without this step succeeds and silently installs a skill
    with its scripts missing, which is why every consumer of a tap's real files
    goes through ``store.source_dir_for``.

    Uses `add`, never `set`: `set` replaces the pattern list and would un-fetch
    every previously materialized skill. A no-op on full clones (including every
    clone made before taps went sparse) and when `rel_dir` is the repo root.

    An unreadable sparse-checkout file falls through to the git-config check
    rather than returning early: degrading to slower-but-correct is fine, and
    degrading to a silently incomplete copy is the bug this function exists to
    prevent.
    """
    rel = rel_dir.strip("/")
    if not rel or rel == ".":
        return
    pattern = "/%s/*" % rel
    have = _sparse_list(repo)
    if have is not None and pattern in have:
        return
    if not is_sparse(Path(repo)):
        return
    try:
        run(["-C", str(repo), "sparse-checkout", "add", pattern])
    except BoostError as e:
        # The blobs live in the promisor remote, so this is the one step in an
        # install that can need the network. Say that, rather than leaving a
        # bare transport error to read as a broken tap.
        raise BoostError(
            "could not fetch %s from the %s tap: %s" % (rel, Path(repo).name, e),
            hint="this needs network — the tap stores only Markdown locally") from None


def pull(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def head_commit(repo: Path) -> str:
    """Return the full HEAD commit hash of `repo`, or "" if unresolvable."""
    proc = run(["-C", str(repo), "rev-parse", "HEAD"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def remote_url(repo: Path) -> str:
    """Return the URL of `repo`'s `origin` remote, or "" if it has none."""
    proc = run(["-C", str(repo), "remote", "get-url", "origin"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def log_for_path(repo: Path, rel_path: str = ".", n: int = 20) -> list[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--date=short", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def is_repo(path: Path) -> bool:
    """Return True when `path` contains a `.git` entry."""
    return (Path(path) / ".git").exists()
