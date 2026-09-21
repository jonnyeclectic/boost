# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""All filesystem locations boost touches.

Everything derives from $HOME (or explicit env overrides) at call time so
tests can sandbox the whole tool by exporting HOME=/tmp/somewhere.

Layout:
  ~/.boost/repos/           shallow git clones of tap registries
  ~/.boost/cache/           JSON catalogs built from SKILL.md frontmatter
  ~/.boost/logs/            command logs
  ~/.boost/state/           pins, tags, policy, profiles, pulse feed, snapshots
  ~/.boost/config.json      configuration
  ~/.agents/skills/        canonical store — single source of truth
  ~/.agents/skills/.skill-lock.json   v3 lock file
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def home() -> Path:
    """Resolve the user's home directory, preferring the ``HOME`` env var."""
    return Path(os.environ.get("HOME") or str(Path.home()))


def expand(p: str) -> Path:
    """Expand a leading ~ against home() (which respects the HOME env var)."""
    if p == "~":
        return home()
    if p.startswith("~/"):
        return home() / p[2:]
    return Path(p)


def tilde(p) -> str:
    """Contract $HOME to ``~`` in a path-ish string for display.

    Only contracts a real path boundary: the string must equal home() or sit
    directly beneath it (``home + os.sep``). A bare ``startswith(home)`` would
    wrongly turn a sibling like ``/Users/bob-backup`` into ``~-backup``. Both
    the raw and resolved forms of home() are tried so symlinked homes contract.

    Always returns ``/``-separated output (even for a path outside $HOME) so
    boost's display text is stable across platforms — Windows accepts forward
    slashes natively, so nothing is lost for a Windows reader either.
    """
    s = str(p)
    for h in (str(home()), str(home().resolve())):
        if s == h:
            return "~"
        if s.startswith(h + os.sep):
            return ("~" + s[len(h):]).replace(os.sep, "/")
    return s.replace(os.sep, "/")


def boost_home() -> Path:
    """Resolve boost's state root: ``$BOOST_HOME`` if set, else ``~/.boost``."""
    override = os.environ.get("BOOST_HOME")
    return Path(override) if override else home() / ".boost"


def repos_dir() -> Path:
    """Return the directory holding shallow clones of tapped registries."""
    return boost_home() / "repos"


def cache_dir() -> Path:
    """Return the directory holding JSON catalogs built from tapped repos."""
    return boost_home() / "cache"


# Files under `cache/` that are boost's own derived artifacts, not a tap's
# catalog. `boost clean` sweeps `cache/*.json` whose stem is not a configured
# tap; `rag_index.json` and `discovery.json` match that shape and no tap can
# ever be named after them, so both were deleted on every run. Losing the BM25
# index is not a cheap self-repair — the next search re-parses every tap catalog
# on the machine (~71k items on a full install).
#
# The .sqlite and .txt entries are outside today's `*.json` glob and are listed
# so a future sweep that widens the glob inherits the guard rather than
# rediscovering the bug. `tests/unit/test_clean_internal_cache.py` fails the
# build when a module writes a cache artifact without registering it here.
INTERNAL_CACHE_FILES = frozenset({
    "rag_index.json",       # rag.index_path()       — BM25 index
    "rag_postings.sqlite",  # rag.postings_path()    — BM25 postings
    "rag_vectors.sqlite",   # dense.db_path()        — dense vectors
    "rerank_cache.json",    # rag.rerank_cache_path() — LLM rerank orders
    "discovery.json",       # discovery._discovery_path()
    "_names.txt",           # complete.names_file()  — shell completion
})


def logs_dir() -> Path:
    """Return the directory holding diagnostic logs and crash reports."""
    return boost_home() / "logs"


def state_dir() -> Path:
    """Return the state directory (pins, tags, policy, profiles, pulse)."""
    return boost_home() / "state"


def tap_refresh_marker() -> Path:
    """File whose mtime records when the taps were last refreshed.

    An mtime rather than a JSON field: the only question asked of it is "how
    long ago", on the search path, where one `stat` is affordable and parsing
    anything is not.
    """
    return state_dir() / "last-tap-refresh"


def shard_sync_marker() -> Path:
    """File whose mtime records when published vectors were last ingested.

    Deliberately beside the tap marker and NOT under ``cache/``: `boost clean`
    sweeps `cache/*.json` whose stem is not a tap, and a marker there would be
    deleted on every clean — after which search would nag about vectors that
    were refreshed this morning. Same one-`stat` contract as the tap marker,
    for the same reason: search reads it, and search does no network.
    """
    return state_dir() / "last-shard-sync"


def snapshots_dir() -> Path:
    """Return the directory for ``snap-*`` store snapshot tarballs."""
    return state_dir() / "snapshots"


def lock_history_dir() -> Path:
    """Return the directory of timestamped ``lock-*.json`` lockfile copies."""
    return state_dir() / "lock-history"


def profiles_dir() -> Path:
    """Return the directory holding saved team profiles as JSON."""
    return state_dir() / "profiles"


def config_path() -> Path:
    """Return the path of boost's ``config.json``."""
    return boost_home() / "config.json"


def store_dir() -> Path:
    """Canonical store for installed skills."""
    override = os.environ.get("BOOST_AGENTS_STORE")
    return Path(override) if override else home() / ".agents" / "skills"


def lockfile_path() -> Path:
    """Return the path of the v3 lock file inside the canonical store."""
    return store_dir() / ".skill-lock.json"


def pulse_path() -> Path:
    """Return the path of the append-only pulse event feed (JSONL)."""
    return state_dir() / "pulse.jsonl"


def policy_path() -> Path:
    """Return the path of the policy rules file, ``policy.json``."""
    return state_dir() / "policy.json"


def trusted_keys_path() -> Path:
    """Return the path of the trusted signing-keys store, ``trusted_keys.json``."""
    return state_dir() / "trusted_keys.json"


def package_root() -> Path:
    """The installed boost_cli package directory (holds bundled data/)."""
    return Path(__file__).resolve().parent.parent


def repo_root() -> Path:
    """The boost source checkout this module runs from."""
    return Path(__file__).resolve().parent.parent.parent


def launcher() -> Path:
    """Absolute path other processes should use to invoke boost.

    A pip/pipx install has no `boost` shim next to the package (repo_root()
    lands inside site-packages), so prefer the console script on PATH and
    fall back to the source-checkout shim.
    """
    found = shutil.which("boost")
    return Path(found) if found else repo_root() / "boost"


def boost_dirs() -> tuple[Path, ...]:
    """Every directory boost writes into — what :func:`ensure_dirs` creates.

    One list, so `boost heal --dry-run` names exactly the directories the real
    run's :func:`create_dirs` call makes rather than a hand-kept copy of them.
    """
    return (boost_home(), repos_dir(), cache_dir(), logs_dir(), state_dir(),
            snapshots_dir(), lock_history_dir(), profiles_dir(), store_dir())


def ensure_dirs() -> None:
    """Create every directory boost writes into (idempotent)."""
    for d in boost_dirs():
        d.mkdir(parents=True, exist_ok=True)


def create_dirs(dirs) -> list[Path]:
    """Create each of `dirs` that can be created; return the ones that could not.

    :func:`ensure_dirs` stops at the first refusal, which is right for a
    caller about to write into the dir it failed on. It is wrong for one that
    is not: under a read-only ``~/.boost`` with no cache dir, doctor, heal and
    every journal write exited 70 creating a cache dir none of them needed.
    """
    refused = []
    for d in dirs:
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            refused.append(d)
    return refused


def nearest_existing(p: Path) -> Path:
    """`p` itself if it exists, else its closest ancestor that does.

    ``os.path.lexists``, not ``Path.exists``: under a parent without search
    permission the stat raises, and that parent is the answer, not a crash.
    And a dangling symlink exists: no mkdir gets past one, so it is the answer
    too. Following it called ``~/.claude/skills -> /nonexistent`` creatable,
    and `boost heal --dry-run` promised a mkdir its run then failed.
    """
    while not os.path.lexists(p) and p != p.parent:
        p = p.parent
    return p


def refuses_writes(d: Path) -> Path | None:
    """The directory that stops boost writing into `d`, or None if nothing does.

    An existing `d` answers for itself. A missing one is created from its
    nearest existing ancestor, so that is the directory that refuses: a
    missing cache dir under a read-only ``~/.boost`` is blocked by
    ``~/.boost``, which no check of the cache dir alone can see. Doctor and
    heal both ask this, so a preview and the run it previews agree. A file or
    a dangling symlink where a directory belongs refuses too, since no mkdir
    gets past it.
    """
    here = nearest_existing(d)
    if here.is_dir() and os.access(here, os.W_OK | os.X_OK):
        return None
    return here


def in_the_way(block: Path) -> bool:
    """Something that is not a directory sits where a directory belongs:
    a file, or a symlink that leads nowhere or to a file."""
    return os.path.lexists(block) and not block.is_dir()


def not_writable(d: Path, block: Path) -> str:
    """Say why `d` cannot be written, given ``block = refuses_writes(d)``.

    The block is `d` itself or the ancestor that would not let it be created,
    and a directory that refuses or something that is not a directory at all.
    Doctor, heal and install share the wording.
    """
    why = "%s is %s" % (tilde(block), "not a directory" if in_the_way(block)
                        else "not writable")
    if block == d:
        return why
    return "%s cannot be created: %s" % (tilde(d), why)


def write_remedy(block: Path) -> str:
    """The one step that clears `block`, from :func:`refuses_writes`.

    A directory needs its mode changed. A file or a dangling symlink where a
    directory belongs needs moving: ``chmod`` on a dangling link follows it
    and fails, so advising that was advice that could not work.
    """
    if in_the_way(block):
        return "move %s aside" % tilde(block)
    return "run `chmod u+w %s`" % tilde(block)
