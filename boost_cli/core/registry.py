# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Tap registries: GitHub repos (or local paths) full of SKILL.md files."""
from __future__ import annotations

import difflib
import os
import re
import shlex
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Collection
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from ..errors import BoostError
from . import (
    config,
    gitutil,
    lockfile,
    output,
    paths,
    policy,
    projectlock,
    scopes,
    util,
)


@dataclass
class Tap:
    """One configured tap: name, source URL, and derived on-disk paths."""
    name: str          # "anthropics/skills" or a short alias
    url: str           # https URL or local path
    curated: bool = False
    #: A 40-character commit this tap is held at, or "" for "track the default
    #: branch". A pin is durable *because it is recorded here*: `tap --at`
    #: checked a commit out and nothing remembered, so the next `boost update`
    #: moved the clone to HEAD — silently invalidating any prebuilt vectors
    #: imported for that commit, which is the whole reason the pin exists.
    pin: str = ""
    #: When this tap was added (``util.now_iso``), or "" for a config row
    #: written before it was recorded. A lock row with no ``tap_url`` that
    #: predates it was installed from an earlier tap of the same name
    #: (:func:`source_changed`).
    added_at: str = ""

    @property
    def safe_name(self) -> str:
        """Filesystem-safe name: `/` replaced with `__`."""
        return self.name.replace("/", "__")

    @property
    def path(self) -> Path:
        """Local clone directory under `~/.boost/repos/`."""
        return paths.repos_dir() / self.safe_name

    @property
    def cache_file(self) -> Path:
        """Catalog JSON path under `~/.boost/cache/`."""
        return paths.cache_dir() / (self.safe_name + ".json")

    @property
    def owns_cache_file(self) -> bool:
        """False when :attr:`cache_file` is one of boost's own indexes.

        A local tap is named after its directory, so a directory called
        ``rag_index`` mapped onto ``cache/rag_index.json`` — the BM25 index.
        :func:`add` now refuses such a name; this guards a config written
        before it did, so the catalog never overwrites, or `untap` deletes,
        a file that is not the tap's.
        """
        return not reserved_cache_name(self.name)

    @property
    def is_wheel(self) -> bool:
        """True for a tap that ships inside the wheel (no git clone)."""
        return self.url.startswith(WHEEL_SCHEME)

    @property
    def is_cloned(self) -> bool:
        """True if the tap's clone directory exists on disk."""
        return self.path.is_dir()

    @property
    def is_broken_clone(self) -> bool:
        """True if the clone dir exists but is not a git repository.

        `is_cloned` stays `path.is_dir()` — two dozen callers read it as "is
        there a tree to scan", and the wheel tap is a legitimate tree with no
        `.git`. But a git-backed tap whose `.git` is gone (a backup or sync
        tool that skips it, a hand `rm`) answered True there, so doctor said
        healthy, heal said nothing to heal, and every `boost update` failed
        with "not a git repository" without ever re-cloning it.
        """
        return (self.is_cloned and not self.is_wheel
                and not gitutil.is_repo(self.path))


def reserved_cache_name(name: str) -> bool:
    """True when tap ``name``'s catalog cache would be one of boost's own
    files in ``cache/`` (:data:`paths.INTERNAL_CACHE_FILES`).

    Case-folded: on a case-insensitive filesystem ``RAG_INDEX.json`` *is*
    ``rag_index.json``.
    """
    leaf = (Tap(name=name, url="").safe_name + ".json").lower()
    return leaf in paths.INTERNAL_CACHE_FILES


def _reserved(name: str) -> BoostError:
    return BoostError(
        "tap name %s is reserved: its catalog would overwrite boost's own "
        "cache/%s.json" % (name, Tap(name=name, url="").safe_name),
        hint="rename the directory and tap it again")


# One path component, in BYTES. ext4, APFS and NTFS all stop at 255, and
# `Tap.safe_name` maps "/" to "__" — so the whole tap name becomes exactly one
# component under `~/.boost/repos` and this is its ceiling. A GitHub owner/repo
# maxes out at 140 (39 + 1 + 100), so nothing real comes near it.
MAX_NAME_BYTES = 255


def _looks_like_a_directory(p: Path) -> bool:
    """True if `p` is an existing directory, False if the OS will not say.

    `Path.exists()` is not total. pathlib swallows ENOENT, ENOTDIR, EBADF and
    ELOOP — ENAMETOOLONG is *not* in that set, so a long enough component makes
    `os.stat` raise straight out of `parse_spec` as a bare OSError, which is not
    a BoostError and so is never framed by the CLI's error handling. A path the
    OS refuses to look at is not a directory we can tap; that is a "no", not a
    crash.
    """
    try:
        return p.is_dir()
    except OSError:
        return False


def parse_spec(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    # Reject control characters HERE, at the parse boundary, rather than letting
    # them travel. A NUL cannot appear in a GitHub owner/repo, a git URL or a
    # usable directory name, so nothing legitimate is turned away — but accepted,
    # it reaches a filesystem call and dies as `ValueError: lstat: embedded null
    # character in path` from inside posixpath, naming neither the tap nor the
    # command, and as a ValueError rather than a BoostError the CLI's error
    # handling never gets to frame it. fuzz.yml found this and failed three
    # scheduled runs out of three before anyone looked (2026-07-25/08-01/08-08).
    # \x1b matters for a second reason: an escape sequence in a name is echoed
    # by every surface that prints a tap list.
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in spec):
        raise BoostError(
            "tap spec contains a control character: %r" % spec,
            hint="use owner/repo, a git URL, or a local directory")
    # paths.expand(), not Path.expanduser(): expanduser() consults the OS's
    # own home-dir lookup (USERPROFILE on Windows), which ignores the $HOME
    # override the whole test suite (and BOOST_HOME sandboxing) relies on.
    p = paths.expand(spec)
    # `file://<dir>` of a directory on this machine is that directory: cloned
    # as a URL it kept the spec as its `url`, so `boost tap <dir>` then
    # `boost tap file://<dir>` was two taps of one repo under one name.
    local = _file_url_path(spec)
    if local is not None and _looks_like_a_directory(local):
        p = local
    if _looks_like_a_directory(p):
        if not gitutil.is_repo(p):
            # The dir exists, so git's own "repository '...' does not exist"
            # (which is what `clone_shallow` would raise next) is a false
            # statement about the very thing this branch just confirmed.
            raise BoostError(
                "%s is not a git repository" % p,
                hint="`git init` it, or `boost import %s` to copy it in "
                     "without a tap" % spec)
        # Whitespace folded to `-`: a tap name is one token in `tap:skill` and
        # in a Boostfile line, so `boost tap "my tap"` named it `my tap` and
        # `bundle dump` wrote a `tap my tap …` line that its own `bundle
        # install` read as a tap called `my`.
        return _checked(_WHITESPACE.sub("-", p.resolve().name),
                        str(p.resolve()), spec)
    # A spec shaped like a path (starts with ./, ../, ~, or a root separator,
    # or is absolute) that is not an actual directory must not fall through to
    # the owner/repo branch below — that branch prepends
    # "https://github.com/" to *anything* containing a "/", so a typo'd local
    # path was silently cloned as a bogus GitHub URL.
    #
    # `p.is_absolute()` catches a Windows `C:\...` spec, but it is NOT a
    # superset of the literal "/" prefix it replaced: on Windows a leading
    # slash is rooted-but-relative (it has no drive), so
    # `PureWindowsPath("/no/such/dir").is_absolute()` is False and
    # `boost tap /no/such/dir` was still cloning
    # `https://github.com//no/such/dir`. Both tests are needed, and this is
    # what the Windows CI leg caught that three POSIX legs could not.
    if spec.startswith(("./", "../", "~", "/", "\\")) or p.is_absolute():
        raise BoostError("no such directory: %s" % p,
                        hint="boost tap needs an existing local git repository")
    # Any `scheme://` is a URL, not only the four this used to list: a
    # `file://` or `git://` spec fell through to the owner/repo branch below
    # and was cloned as `https://github.com/file:///…`. Which transports are
    # safe is `gitutil.clone_shallow`'s call (it refuses `ext::` and kin), not
    # a reason to rewrite the spec here.
    if _SCHEME.match(spec) or spec.startswith("git@"):
        tail = spec.split(":")[-1] if spec.startswith("git@") \
            else spec.split("://", 1)[1]
        segs = [x for x in tail.split("/") if x]
        if segs:
            # The suffix only: `.replace(".git", "")` named
            # `foo/my.github.io` as `foo/myhub.io`.
            segs[-1] = segs[-1].removesuffix(".git")
        return _checked("/".join(segs[-2:]), spec, spec)
    if "/" in spec and " " not in spec:
        return _checked(spec, "https://github.com/%s" % spec, spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


_WHITESPACE = re.compile(r"\s+")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


def _file_url_path(spec: str) -> Path | None:
    """The local path a `file://` spec names, or None if it names none.

    Only an empty or `localhost` host is this machine; `file://otherhost/…`
    stays a URL for git to judge.
    """
    u = urllib.parse.urlparse(spec)
    if u.scheme.lower() != "file" or u.netloc.lower() not in ("", "localhost"):
        return None
    return Path(urllib.request.url2pathname(u.path))


def _checked(name: str, url: str, spec: str) -> tuple[str, str]:
    """The derived pair, or a BoostError if the name cannot be a directory.

    The rule is on the *name*, never on the spec: a deep local path with a short
    basename is a perfectly good tap, and its own length says nothing about the
    component we are about to create. Caught here rather than at clone time,
    where it surfaces as git's own ENAMETOOLONG on a path the user never typed.
    """
    if len(name.encode("utf-8")) > MAX_NAME_BYTES:
        raise BoostError(
            "tap name is too long (%d bytes, limit %d): %r"
            % (len(name.encode("utf-8")), MAX_NAME_BYTES, spec[:80]),
            hint="the name becomes one directory under ~/.boost/repos, and "
                 "no filesystem accepts a longer component")
    return (name, url)


def parse_specs(specs: list[str]) -> list[tuple[str, str]]:
    """Parse each spec to (name, url) via `parse_spec`, touching nothing.

    Used by `tap --dry-run` to preview targets without cloning or writing
    config — `parse_spec` is already pure (a directory stat at worst), so the
    only job here is applying it across a SPEC list in order.
    """
    return [parse_spec(spec) for spec in specs]


def tap_summary(tapped: list[tuple[str, int]]) -> str:
    """"3 registries · 512 items" — what a tap run actually added.

    A count, not a list: the per-tap `✓ tapped X (N items)` lines above it
    already name every registry, and repeating them would make the summary
    longer than the thing it summarises. Pure so it can be asserted on
    directly; the surface decides where to frame it.
    """
    taps = len(tapped)
    items = sum(n for _name, n in tapped)
    # Both spellings written out rather than interpolated onto a stem:
    # codespell reads that stem as a misspelling of "register", and an
    # exception in the lint config costs more than one extra word here.
    return "%d %s · %d %s" % (taps, "registry" if taps == 1 else "registries",
                              items, "item" if items == 1 else "items")


def list_taps() -> list[Tap]:
    """Every ``taps`` row in config.json — boost's OWN tap included.

    The literal clone list, which is the right question for cloning, caching,
    commits and provenance. It is the wrong one for "has this user set boost
    up yet": ``boost/builtin`` is appended by :func:`builtin.ensure_tap` on a
    machine the user has tapped nothing on, so this returns 1 there and every
    setup message keyed on it goes silent. Ask
    :func:`builtin.configured_tap_count` for that.

    Malformed config or entries read as no taps, never raise.
    """
    # `or []`, not just the get() default: config.get returns the default only
    # when the key is ABSENT, so a config.json carrying `"taps": null` (or any
    # non-list scalar) would otherwise reach the comprehension and raise
    # TypeError. A malformed config should read as "no taps", never crash every
    # command that lists them.
    taps = config.get("taps", []) or []
    if not isinstance(taps, list):
        return []
    return [Tap(name=t["name"], url=t.get("url", ""),
                curated=bool(t.get("curated")), pin=str(t.get("pin") or ""),
                added_at=str(t.get("added_at") or ""))
            for t in taps if isinstance(t, dict) and t.get("name")]


def get(name: str) -> Tap:
    """Look up a tap by name, safe_name, or bare repo name.

    Tiered so a qualified name always beats a short one: exact ``owner/repo``
    first, then ``safe_name``, then the bare repo tail. Within a tier a name
    that matches more than one tap is an error rather than a guess — with
    ``angular/skills`` and ``microsoft/skills`` both tapped, ``boost untap
    skills`` used to act on whichever came first in config.json, which for a
    destructive command is the wrong answer half the time.

    Raises BoostError (with a did-you-mean hint) if none match.
    """
    taps = list_taps()
    # The case-folded tier comes last, so an exact spelling always wins: it is
    # what lets `boost untap Obra/Superpowers` find `obra/superpowers`, whose
    # clone is the same directory on a case-insensitive filesystem anyway.
    for key, want in ((lambda t: t.name, name),
                      (lambda t: t.safe_name, name),
                      (lambda t: t.name.split("/")[-1], name),
                      (lambda t: name_key(t.name), name_key(name))):
        hits = [t for t in taps if key(t) == want]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise BoostError(
                "%r is ambiguous — it matches %d taps: %s"
                % (name, len(hits), ", ".join(sorted(t.name for t in hits))),
                hint="use the full owner/repo name")
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def same_source(a: str, b: str) -> bool:
    """True when two tap URLs name the same repository.

    A tap's name is only the last two parts of its URL, so the name alone
    cannot answer "is this already tapped?": `~/a/fixture-tap` and
    `~/b/fixture-tap` are both `fixture-tap`, and a GitHub and a GitLab
    `owner/repo` are both `owner/repo`. Spellings of one remote still match —
    `owner/repo`, `…/repo.git`, `git@host:owner/repo` — so re-tapping a repo
    by another of its names stays the harmless no-op it was. Local paths
    compare exactly (`parse_spec` has already resolved them); a remote's host
    compares case-blind, and its path only on github.com, the one forge boost
    can say that of. Two local spellings of one directory — `~/x` and `~/X`
    on APFS or NTFS, where `resolve()` keeps the case it was given — match
    by asking the filesystem, not by comparing the strings.
    """
    if _source_key(a) == _source_key(b):
        return True
    return _is_local(a) and _is_local(b) and _same_file(a, b)


def source_changed(lk: dict, tap: Tap) -> bool:
    """True when ``tap`` no longer names the repository ``lk`` came from.

    A tap is addressed by its name, and a name is only the tail of a URL:
    untap `~/a/reg` and tap `~/b/reg`, and the lock rows installed from the
    first now resolve to the second. Comparing versions across that seam
    called an unrelated skill of the same name an upgrade, and `boost update`
    applied it. The lock's ``tap_url`` (written at install) is the source.

    A row without one predates the field. While its tap stays configured
    :func:`store.backfill_tap_urls` records the URL from config; once it was
    untapped and the name tapped again, nothing says which repository it came
    from, so a tap added after the row was last written (``added_at``) is a
    change unless the clone still sits at the commit the row recorded. A
    legacy row under a tap row that predates ``added_at`` cannot be told
    apart and keeps the old behaviour.
    """
    recorded = str(lk.get("tap_url") or "")
    if recorded:
        return not same_source(recorded, tap.url)
    return retapped_since(lk, tap)


def retapped_since(lk: dict, tap: Tap) -> bool:
    """Whether ``tap`` was added after lock row ``lk`` was last written.

    Strictly after, so a tap and an install in the same second are one
    source. A clone still at the row's ``commit`` is the same repository.
    """
    written = max(str(lk.get("installed_at") or ""),
                  str(lk.get("updated_at") or ""))
    if not (tap.added_at and written and written < tap.added_at):
        return False
    commit = str(lk.get("commit") or "")
    return not (commit and gitutil.head_commit(tap.path) == commit)


def _is_local(url: str) -> bool:
    return not (url.startswith("git@") or _SCHEME.match(url))


def _same_file(a: str, b: str) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        # A clone source that has since moved or vanished is not evidence
        # that two spellings are one directory.
        return False


def _source_key(url: str) -> str:
    if url.startswith("git@"):
        url = url[len("git@"):].replace(":", "/", 1)
    elif _SCHEME.match(url):
        url = url.split("://", 1)[1]
        # Userinfo sits before the host; an `@` after the first `/` is path.
        url = url.split("@", 1)[-1] if "@" in url.split("/", 1)[0] else url
    else:
        return url
    host, _, path = url.partition("/")
    host = host.lower()
    path = path.rstrip("/").removesuffix(".git")
    # A host is case-blind everywhere, a path only where the forge says so:
    # a self-hosted `Team/Repo` and a `file:///srv/A` are not their
    # lowercase twins.
    if host.split(":", 1)[0] == "github.com":
        path = path.lower()
    return host + "/" + path


def name_key(name: str) -> str:
    """The form of a tap name that decides whether two taps are one.

    Case-folded, because a tap's clone and cache live at paths built from its
    name: on APFS and NTFS `repos/foo` and `repos/FOO` are one directory, so
    two config rows `foo` and `FOO` share one clone, and untapping either
    deletes the other's. Folding everywhere — not only where the filesystem
    happens to — keeps a config written on Linux valid on a Mac.
    """
    return name.casefold()


def _taken(name: str, url: str, existing: str) -> BoostError:
    """The error for `name` already belonging to a different repository."""
    return BoostError(
        "tap name %s is already used by %s" % (name, existing),
        hint="`boost untap %s` first to tap %s in its place" % (name, url))


def is_tapped(name: str) -> bool:
    """True if `name` is a currently configured tap's exact ``Tap.name``.

    Exact match only, unlike ``get()``'s shorthand/ambiguity tiering: a lock
    entry's ``tap`` field always records the full ``owner/repo`` name a skill
    was installed from, so callers checking "is this entry's tap still
    tapped?" want a plain membership test, not a fuzzy lookup that could
    raise on an unrelated ambiguous shorthand.
    """
    return any(t.name == name for t in list_taps())


def unfinished_clones() -> list[Path]:
    """Dirs under `repos/` that no tap lists and whose HEAD does not resolve.

    What a clone killed part-way leaves behind (a timeout, a ^C, a crash):
    `repos/<name>/.git` and nothing recorded. `boost doctor` called that
    machine healthy, because it only ever looked at the taps config lists.
    A listed tap is judged by the tap checks instead, and an unlisted dir
    with a real HEAD is someone's clone, not debris. Empty without git,
    which is what answers whether a HEAD resolves.
    """
    root = paths.repos_dir()
    if not root.is_dir() or not gitutil.has_git():
        return []
    listed = {t.path for t in list_taps()}
    return sorted(d for d in root.iterdir()
                  if d.is_dir() and d not in listed
                  and not gitutil.head_commit(d))


def broken_clone_line(name: str) -> str:
    """The one line doctor and heal print for a `Tap.is_broken_clone` tap.

    Shared so the two cannot prescribe different fixes. Not `boost untap`,
    which is what `update`'s own failure line used to suggest: the source is
    fine, only the local clone is damaged, and `update` re-clones it.
    """
    return ("tap %s is not a git repository (its .git is missing) — run "
            "`boost update %s` to re-clone it" % (name, name))


def _shell_arg(arg: str) -> str:
    """`arg` as one argument a user can paste into their shell."""
    if sys.platform == "win32":
        # cmd.exe and PowerShell both take double quotes; neither takes the
        # single quotes `shlex.quote` emits.
        return '"%s"' % arg if any(c.isspace() for c in arg) else arg
    return shlex.quote(arg)


def retap_hint(name: str, url: str = "") -> str:
    """What to run to re-tap `name` once it is no longer configured.

    The *name* is not a spec in general: a local tap is named after its
    directory's basename (`boost tap fix` does not parse), and a tap from any
    host other than GitHub is named `owner/repo`, which `parse_spec` resolves
    to GitHub — a different repository. So the recorded `url` (the lock's
    `tap_url`) is used when there is one. Without it — a lock entry written
    before the field existed — only an owner/repo-shaped name is offered as a
    command, and anything else gets words rather than a command that fails.
    """
    if url and not url.startswith(WHEEL_SCHEME):
        return "boost tap %s" % _shell_arg(url)
    if url.startswith(WHEEL_SCHEME) or "/" not in name or " " in name:
        return "re-tap %s from its original source (its URL was not recorded)" % name
    return "boost tap %s" % name


def add(spec: str, curated: bool = False, at: str | None = None) -> Tap:
    """Parse `spec`, shallow-clone it, and record the tap in config.

    ``at`` pins the clone to one commit. It exists for published vector shards:
    a shard is only importable while the tap sits at the commit it was built
    from (see ``core.shards``), so "tap this registry as the shard expects it"
    has to be one operation — tapping HEAD and then moving would re-scan the
    catalog for a tree the vectors do not describe.

    Raises BoostError if a tap with that name is already configured.
    """
    name, url = parse_spec(spec)
    if reserved_cache_name(name):
        raise _reserved(name)
    for existing in list_taps():
        if name_key(existing.name) == name_key(name):
            if not same_source(existing.url, url):
                raise _taken(existing.name, url, existing.url)
            raise _already_configured(existing.name, spec, at)
    # Validated here, before the clone, not only inside `checkout_commit`:
    # that check runs after `clone_shallow` below, so a malformed --at used to
    # cost one full clone (~1.6s) before reporting a typo.
    if at and not gitutil._is_sha(at):
        raise BoostError("%r is not a full commit SHA" % at,
                         hint="pin with the 40-character hash a manifest names")
    tap = Tap(name=name, url=url, curated=curated)
    paths.ensure_dirs()
    _clear_path(tap.path)
    gitutil.clone_shallow(url, tap.path)
    if at:
        try:
            gitutil.checkout_commit(tap.path, at)
        except BoostError:
            # A pin that cannot be honoured must not leave a tap silently on
            # HEAD: the caller asked for one tree and would get another, and
            # every shard keyed to the pin would then be refused for a commit
            # mismatch whose cause is three steps back.
            util.rmtree(tap.path)
            raise
    problems = policy.check_tap_signing(tap.path)
    if problems:
        util.rmtree(tap.path)  # leave no half-added tap behind
        raise _signing_refused(name, problems)
    row = _row(name, url, curated, by_user=curated)
    if at:
        row["pin"] = at

    config.mutate(lambda cfg: _append_rows(cfg, [row]))
    start_refresh_clock()
    tap.pin = at or ""
    return tap


#: The phrase every provenance refusal carries, so `boost update` can tell a
#: refused tap (a security answer, worth a non-zero exit) from a dead one.
POLICY_REFUSAL = "failed provenance policy"


def _signing_hint() -> str:
    """What repairs a provenance refusal.

    An unreadable policy.json refuses every tap; trusting a key or relaxing
    signing would not repair it, so say what would.
    """
    if policy.unreadable_violation("tap"):
        return ("repair policy.json first — `boost policy` names each "
                "unreadable value")
    return ("add its key with `boost trust add <name> <key>`, "
            "or relax `boost policy set require_signed_taps false`")


def _signing_refused(name: str, problems: list[str],
                     kept: str = "") -> BoostError:
    """The error for a tap whose tree fails ``require_signed_taps``.

    ``kept`` is the commit the clone stays on when the refused tree was a
    move rather than a first clone — said, because "refused" alone leaves the
    reader to wonder whether the tap is now broken.
    """
    msg = "tap %s %s: %s" % (name, POLICY_REFUSAL, "; ".join(problems))
    if kept:
        msg += " — kept at %s" % kept[:7]
    return BoostError(msg, hint=_signing_hint())


def require_signed_clone(name: str, clone: Path) -> None:
    """Raise :func:`_signing_refused` when the working tree at ``clone``
    fails ``require_signed_taps``; a no-op when the policy is off.

    For a caller that downloads a tap afresh outside this module —
    `boost compact --reclone` — so a fresh download is gated the way
    `boost tap` gates the first one.
    """
    problems = policy.check_tap_signing(clone)
    if problems:
        raise _signing_refused(name, problems)


def _signing_guard(tap: Tap):
    """A ``verify`` callback for :func:`gitutil.pull`/``checkout_commit``.

    Called with the fetched commit before the clone moves onto it, so a new
    upstream commit that drops the signature (or swaps the signer) is refused
    with the clone still on the tree that passed — `boost tap` checked the
    first tree only, and every update after it was taken on trust.
    """
    def verify(commit: str) -> None:
        problems = policy.check_tap_signing(tap.path, commit=commit)
        if problems:
            raise _signing_refused(tap.name, problems,
                                   kept=gitutil.head_commit(tap.path))
    return verify


def _append_rows(cfg: dict, rows: list[dict]) -> bool:
    """Append tap ``rows`` to a fresh config; False when none was new.

    Runs inside :func:`config.mutate`. The duplicate check in :func:`add`
    happens before the clone, outside any lock, so two processes tapping
    one name both pass it — re-checking here keeps the second from adding
    the same tap twice.
    """
    taps = cfg.setdefault("taps", [])
    have = {name_key(str(t.get("name"))) for t in taps
            if isinstance(t, dict) and t.get("name")}
    added = False
    for row in rows:
        if name_key(row["name"]) not in have:
            taps.append(row)
            have.add(name_key(row["name"]))
            added = True
    return added


def _already_configured(name: str, spec: str, at: str | None) -> BoostError:
    """The error for re-tapping a configured tap, with a hint that works.

    With ``at`` the user wants another commit, and `boost update` cannot give
    them one: it skips a pinned tap, and ``--force`` moves to branch HEAD and
    drops the pin. Only a fresh tap at that commit lands there.
    """
    if at:
        return BoostError(
            "tap %s is already configured" % name,
            hint="`boost untap %s`, then `boost tap %s --at %s` to move it "
                 "to that commit" % (name, spec, at))
    return BoostError("tap %s is already configured" % name,
                      hint="`boost update %s` to refresh it" % name)


#: Marks a ★ the user asked for (`--curated`, the defaults), as opposed to one
#: copied from the catalogue's column. :func:`overstarred` never takes one back.
CURATED_BY_USER = "user"


def _row(name: str, url: str, curated: bool, by_user: bool) -> dict:
    row: dict = {"name": name, "url": url, "curated": curated,
                 "added_at": util.now_iso()}
    if curated and by_user:
        row["curated_by"] = CURATED_BY_USER
    return row


def overstarred() -> list[str]:
    """Taps starred in config that the bundled catalogue does not curate.

    Every catalogue row once shipped ``curated: true`` and `tap --catalog`
    stamped the whole batch, so a machine that tapped the catalogue holds
    ~460 starred rows where the catalogue now stars ~40. Only that direction
    is drift: an unstarred tap stays unstarred, because a plain `boost tap` is
    opt-in. A tap the catalogue does not list is the user's own and is never
    named, nor is a row whose star the user asked for (``curated_by``). A row
    written before that marker existed cannot say who starred it, so an
    explicit `--curated` on a catalogue repo from back then reads as drift.
    """
    wanted = {str(e.get("name")): bool(e.get("curated"))
              for e in config.load_registry_catalog()}
    rows = config.get("taps", []) or []
    if not isinstance(rows, list):
        return []
    return [str(t["name"]) for t in rows
            if isinstance(t, dict) and t.get("curated")
            and t.get("curated_by") != CURATED_BY_USER
            and wanted.get(str(t.get("name"))) is False]


def unstar(names: list[str]) -> list[str]:
    """Clear the ★ on ``names`` in one config write; return those cleared.

    Config only. Each tap's cache still carries the old flag on every entry
    (stamped at scan time), so the caller rebuilds those caches.
    """
    todo = set(names)
    if not todo:
        return []
    done: list[str] = []

    def clear(cfg: dict) -> bool:
        for t in cfg.get("taps") or []:
            if (isinstance(t, dict) and t.get("name") in todo
                    and t.get("curated")):
                t["curated"] = False
                done.append(str(t["name"]))
        return bool(done)
    config.mutate(clear)
    return done


#: Default concurrency for :func:`add_many`. Tapping is network-latency bound,
#: not bandwidth or CPU bound: a clone of a catalog registry measures ~1.6 s
#: whether one runs or twelve do, so the wall time of `boost tap --catalog` was
#: 463 x 1.6 s ~= 13 minutes of mostly waiting. Measured on the real catalog,
#: 40 registries went from 58 s serial to 6.4 s at 12 workers with the per-repo
#: median unchanged (1.55 s -> 1.46 s), which is what says the concurrency is
#: not being paid for somewhere else.
DEFAULT_TAP_JOBS = 8

#: Politeness ceiling. Nothing in the measurements argues for more, and this is
#: someone else's server: past this the risk of being throttled outweighs a
#: wall-time gain that is already asymptotic.
MAX_TAP_JOBS = 16


def tap_jobs(requested: int | None = None) -> int:
    """How many clones to run at once, clamped to something defensible."""
    if requested is None:
        env = os.environ.get("BOOST_TAP_JOBS")
        requested = int(env) if env and env.isdigit() else DEFAULT_TAP_JOBS
    return max(1, min(int(requested), MAX_TAP_JOBS))


def _discard(tap: Tap) -> None:
    """Remove a rejected clone, tolerating one that was never created.

    `add` only ever deleted a directory it had just cloned successfully, so it
    could call `rmtree` unguarded. Here the failure may be the clone itself —
    at which point the path does not exist, and `util.rmtree`'s read-only retry
    hook chmods a missing file and raises `FileNotFoundError` out of the worker
    thread, turning "this one registry 404'd" into a crashed catalog tap.
    """
    # Cleanup is best-effort: the caller's real error is the one worth
    # reporting, and a leftover directory is a smaller problem than losing it
    # behind a cleanup failure.
    with suppress(OSError):
        util.remove_path(tap.path)


def _clear_path(path) -> None:
    """Remove whatever is at ``path``, as a tap failure rather than a crash.

    ``util.remove_path`` raises ``OSError`` like the calls it wraps, and the
    three places here that clear a path before cloning are all reached from
    code that handles ``BoostError`` and nothing else: :func:`update`'s
    per-tap loop records a ``BoostError`` as that tap's failure and carries
    on, and :func:`_clone_one` promises "Never raises" to a
    ``ThreadPoolExecutor``. An ``OSError`` out of either — an unwritable
    ``repos/`` is enough — turns one tap's problem into the whole sweep's,
    or into a crashed worker and a 70 from a pool of twelve clones.
    """
    try:
        util.remove_path(path)
    except OSError as exc:
        raise BoostError(
            "could not clear %s" % paths.tilde(Path(path)),
            hint="something is in the way and cannot be removed; delete it "
                 "by hand, then retry") from exc


def _reclone(tap: Tap, pin: str | None) -> None:
    """Clone ``tap`` afresh (checked out at ``pin`` if given), replacing
    whatever is at ``tap.path`` **only once the new clone is complete**.

    The clone lands in a staging sibling first. Clearing the old path and
    then cloning into it lost a broken clone's tree whenever the re-clone
    failed — offline, an auth error, a remote moved or deleted — and that tree
    was still scannable and installable from; doctor and heal both point at
    `boost update <name>`, so their own remedy destroyed it. A failed clone or
    an unhonourable pin now leaves ``tap.path`` exactly as it was. (A pin that
    cannot be checked out still never lands as a tree on HEAD with a stale pin
    beside it: the staging copy is discarded with it.)
    """
    staging = tap.path.with_name(tap.path.name + ".boost-reclone")
    _clear_path(staging)
    try:
        gitutil.clone_shallow(tap.url, staging)
        if pin:
            gitutil.checkout_commit(staging, pin)
        # Checked on the staging tree, before it replaces anything: a
        # re-clone is a fresh download, so it gets the same provenance gate
        # `boost tap` applies — or a tap whose clone went missing would come
        # back from an upstream that dropped its signature.
        problems = policy.check_tap_signing(staging)
        if problems:
            raise _signing_refused(
                tap.name, problems,
                kept=gitutil.head_commit(tap.path) if tap.is_cloned else "")
    except BoostError:
        with suppress(OSError):
            util.remove_path(staging)
        raise
    # `is_cloned` is `path.is_dir()`, which a *dangling* symlink answers
    # False to, so a dangling link reaches here too and is cleared like any
    # other leftover before the finished clone moves into place.
    _clear_path(tap.path)
    try:
        os.replace(staging, tap.path)
    except OSError as exc:
        raise BoostError(
            "could not move the new clone into %s" % paths.tilde(tap.path),
            hint="retry `boost update %s`" % tap.name) from exc


def ensure_cloned(tap: Tap) -> bool:
    """Clone a registered tap that has no clone, **at its pin**. True if it
    cloned.

    The path every consumer of a tap's files takes when the clone is missing
    (`store.source_dir_for`, so `drift`, `info`, `install`). It used to be a
    bare `clone_shallow`, which landed on HEAD while config.json kept the pin:
    a read-only `boost drift` moved the tap, `update` then answered "pinned at
    <pin> (skipped)" for a clone that was not, and `heal` rescanned the catalog
    to match the wrong tree. Routed through :func:`_reclone`, the same staged,
    sparse, pinned clone `update` uses for a missing clone.
    """
    if tap.is_cloned:
        return False
    _reclone(tap, tap.pin or None)
    return True


def off_pin(tap: Tap) -> str | None:
    """The clone's HEAD when ``tap`` is pinned and its clone is not at the
    pin, else ``None``.

    ``None`` too when the answer is unknowable (no git, no clone, an
    unresolvable HEAD): an unread HEAD is not evidence of a move.
    """
    if not tap.pin or not tap.is_cloned or not gitutil.has_git():
        return None
    head = gitutil.head_commit(tap.path)
    return head if head and head.lower() != tap.pin.lower() else None


def _clone_one(spec: str, curated: bool, at: str | None) -> dict:
    """Clone one tap without touching config. Never raises.

    Config is deliberately left alone: `config.load()` -> mutate -> `save()` is
    read-modify-write on a single JSON file, so running it from N threads loses
    taps at random. :func:`add_many` writes once, on one thread, after every
    clone has finished.
    """
    try:
        name, url = parse_spec(spec)
    except BoostError as exc:
        return {"spec": spec, "name": spec, "ok": False, "error": exc.message}
    tap = Tap(name=name, url=url, curated=curated)
    try:
        _clear_path(tap.path)
        gitutil.clone_shallow(url, tap.path)
        if at:
            gitutil.checkout_commit(tap.path, at)
        problems = policy.check_tap_signing(tap.path)
        if problems:
            _discard(tap)
            return {"spec": spec, "name": name, "ok": False,
                    "error": "failed provenance policy: %s" % "; ".join(problems)}
    except BoostError as exc:
        # Leave no half-added tap behind, exactly as `add` does: a clone that
        # failed its pin or its policy check is not a tap, and a directory that
        # looks like one would be indexed on the next scan.
        _discard(tap)
        return {"spec": spec, "name": name, "ok": False, "error": exc.message}
    return {"spec": spec, "name": name, "url": url, "ok": True, "tap": tap}


def add_many(specs: list[str], curated: bool = False,
             pins: dict[str, str] | None = None, jobs: int | None = None,
             on_done=None,
             curated_names: Collection[str] = ()) -> list[dict]:
    """Clone many taps at once and register them in a single config write.

    Returns one result dict per spec, in the order given, each with ``ok`` and
    either ``tap`` or ``error``. One registry's failure never costs another its
    clone — a catalog tap of 463 repos that aborted on the first 404 would be
    worse than useless.

    `pins` maps a tap name to the commit to check out, for published vector
    shards (see ``core.shards``).

    `curated` stars every tap in the batch; `curated_names` stars only the
    named ones. A catalogue tap needs the second: one flag for the whole batch
    is how all 463 registries of `tap --catalog` came out curated, which made
    the ★ mark everything and so mean nothing.
    """
    if not specs:
        return []
    paths.ensure_dirs()
    pins = pins or {}
    existing = {name_key(t.name): t for t in list_taps()}
    batch: dict[str, str] = {}
    results: list[dict] = []
    todo: list[str] = []
    for spec in specs:
        try:
            name, url = parse_spec(spec)
        except BoostError as exc:
            results.append({"spec": spec, "name": spec, "ok": False,
                            "error": exc.message})
            continue
        if reserved_cache_name(name):
            results.append({"spec": spec, "name": name, "ok": False,
                            "error": _reserved(name).message})
            continue
        # A different repository under a taken name is a failure, not a skip:
        # "already tapped" with nothing tapped is the answer that hid it.
        key = name_key(name)
        held = existing.get(key)
        if held is not None and not same_source(held.url, url):
            results.append({"spec": spec, "name": name, "ok": False,
                            "error": _taken(held.name, url, held.url).message})
            continue
        if held is not None:
            results.append({"spec": spec, "name": name, "ok": False,
                            "skipped": True, "error": "already tapped"})
            continue
        # Two specs of this one run claiming a name is not "already used by":
        # nothing holds the name yet, and `boost untap` would not help.
        if key in batch and not same_source(batch[key], url):
            results.append({
                "spec": spec, "name": name, "ok": False,
                "error": "two specs in this batch both name %s: %s and %s"
                         % (name, batch[key], url)})
            continue
        if key in batch:
            results.append({"spec": spec, "name": name, "ok": False,
                            "skipped": True, "error": "already tapped"})
            continue
        # Guard against the same registry appearing twice in one selection:
        # two threads cloning into one directory is a corrupt clone, not a race
        # anyone would enjoy debugging.
        batch[key] = url
        todo.append(spec)

    def work(spec: str) -> dict:
        name, _url = parse_spec(spec)
        return _clone_one(spec, curated or name in curated_names,
                          pins.get(name))

    with ThreadPoolExecutor(max_workers=tap_jobs(jobs)) as pool:
        for res in pool.map(work, todo):
            results.append(res)
            if on_done is not None:
                on_done(res)

    # One read-modify-write, after every clone: N threads doing this each would
    # lose taps, and 463 sequential rewrites of the same file is its own cost.
    fresh = [r for r in results if r.get("ok")]
    if fresh:
        new_rows = []
        for r in fresh:
            row = _row(r["name"], r["url"], r["tap"].curated,
                       by_user=curated)
            pin = pins.get(r["name"])
            if pin:
                row["pin"] = pin
                r["tap"].pin = pin
            new_rows.append(row)

        config.mutate(lambda cfg: _append_rows(cfg, new_rows))
        start_refresh_clock()
    # First occurrence, not last: a dict comprehension over `specs` keeps the
    # LAST index for a repeated spec, which pushed the duplicate — and so its
    # whole position — to the end and reordered everything in between.
    order: dict[str, int] = {}
    for i, spec in enumerate(specs):
        order.setdefault(spec, i)
    # Ties are the repeats themselves; report the clone before the "already
    # tapped" note about it.
    results.sort(key=lambda r: (order.get(r["spec"], len(order)),
                                bool(r.get("skipped"))))
    return results


#: How long a tap set may go unrefreshed before `boost search` mentions it.
#: Two weeks rather than days: registries move slowly, and a hint that fires
#: every other search is one users learn to read past.
STALE_TAPS_DAYS = 14


def mark_refreshed() -> None:
    """Stamp "the taps were refreshed just now"; never fails a refresh."""
    with suppress(OSError):
        paths.ensure_dirs()
        paths.tap_refresh_marker().write_text("", encoding="utf-8")


def start_refresh_clock() -> None:
    """Stamp the refresh marker at a first clone, if nothing has yet.

    `boost update` was the marker's only writer, so a machine that tapped
    (`tap --defaults`, `quickstart`) and never updated had no marker at all —
    and the stale-tap hint on `search`, the one line that says a catalogue
    has drifted (boost deliberately never refreshes in the background), could
    never fire for exactly those users. Two real installs, one with 458 taps,
    had no marker. A fresh clone *is* a refresh, so the first one starts the
    clock. An existing marker is left alone: adding one tap does not refresh
    the taps already here.
    """
    # ponytail: an install that predates this starts its clock at its next
    # tap rather than at its oldest clone; derive it from clone mtimes if
    # that gap ever matters.
    if not paths.tap_refresh_marker().exists():
        mark_refreshed()


def refresh_age_days() -> float | None:
    """Days since the last tap refresh, or None when nothing has recorded one.

    None is not zero and not infinity: on a machine that has never run
    `boost update` there is nothing to report, and inventing an age would make
    every fresh install nag about staleness on its first search.
    """
    marker = paths.tap_refresh_marker()
    try:
        age = time.time() - marker.stat().st_mtime
    except OSError:
        return None
    return max(0.0, age / 86400.0)


def last_refresh_at() -> str | None:
    """ISO8601 UTC timestamp of the last tap refresh, or None when never.

    Same marker :func:`refresh_age_days` reads, in the shape ``util.rel_time``
    expects. A caller reporting "last tap sync" wants this rather than a git
    log timestamp: a tap's newest commit is the *upstream's* clock and does
    not move when the local clone is refreshed, which is what made `boost
    health` claim a sync minutes old was "4w ago" — it was reading when
    someone else last pushed, not when `boost update` last ran here.
    """
    marker = paths.tap_refresh_marker()
    try:
        mtime = marker.stat().st_mtime
    except OSError:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime))


def pin(name: str, commit: str) -> Tap:
    """Record `commit` as the tap's pin, so `update` leaves it alone."""
    tap = get(name)

    def put(cfg: dict) -> None:
        for row in cfg.get("taps", []) or []:
            if isinstance(row, dict) and row.get("name") == tap.name:
                row["pin"] = commit
    config.mutate(put)
    tap.pin = commit
    return tap


def unpin(name: str) -> Tap:
    """Drop a tap's pin so it tracks its default branch again."""
    tap = get(name)

    def drop(cfg: dict) -> None:
        for row in cfg.get("taps", []) or []:
            if isinstance(row, dict) and row.get("name") == tap.name:
                row.pop("pin", None)
    config.mutate(drop)
    tap.pin = ""
    return tap


def retarget(name: str, commit: str) -> Tap:
    """Move an existing tap's clone to `commit` and pin it there.

    The operation a published-vector refresh needs and no other entry point
    offers. :func:`add` refuses a registry that is already tapped — deliberately
    — so its ``at=`` pin only ever serves a first tap; :func:`update` moves a tap
    to its branch HEAD and ``--force`` moves it and drops the pin. None of the
    three can land on the commit a manifest names, and the chance that HEAD
    happens to be that commit falls with every push upstream, which is why a
    week-old install could see its vectors go stale with no way to act on it
    but re-embedding locally.

    Checkout first, pin second, and never the reverse: a pin recorded for a
    tree that was not checked out is a lie :func:`update` would then honour by
    skipping the tap forever.
    """
    tap = get(name)
    gitutil.checkout_commit(tap.path, commit, verify=_signing_guard(tap))
    return pin(name, commit)


def dependents(tap_name: str) -> list[tuple[str, str]]:
    """Installed items (kind, name) whose lock entry names `tap_name`.

    Skill, rule, workflow order, name-sorted within each — untapping the
    source of a live rule or workflow deserves the same warning as untapping
    the source of a skill.
    """
    return [(kind, n)
            for kind, section in lockfile.all_installed().items()
            for n, e in sorted(section.items())
            if e.get("tap") == tap_name]


def project_dependents(tap_name: str) -> list[str]:
    """Skills installed ``--local`` in the current repo whose row names `tap_name`.

    Name-sorted. :func:`dependents` reads the user lock only, so untapping the
    source of a project skill went through with no warning and left a row
    `drift` reads as source-missing. A project lock records skills only, and
    only this repo's is reachable: other checkouts are not known to boost.
    """
    pbase = scopes.resolve_base(scopes.SCOPE_PROJECT)
    if pbase is None:
        return []
    return [n for n, e in sorted(projectlock.installed(pbase).items())
            if e.get("tap") == tap_name]


def _shared(path: Path, others: list[Path]) -> bool:
    """True if `path` names the same file as one of `others`.

    Asked of the filesystem, not of the spelling: `repos/foo` and `repos/FOO`
    are one directory on APFS and two on ext4, and only the first must be kept.
    """
    for other in others:
        if other == path:
            return True
        try:
            if os.path.samefile(path, other):
                return True
        except OSError:
            continue
    return False


def remove(name: str) -> Tap:
    """Deregister a tap and delete its clone and cache file.

    Returns the removed Tap; raises BoostError if it does not exist.
    """
    tap = get(name)

    def drop(cfg: dict) -> None:
        rows = cfg.get("taps") or []
        # Drop only the row this is, and keep every other row as it was — a
        # malformed one included. `list_taps` reads a nameless or non-dict
        # row as no tap, so indexing `t["name"]` here crashed the one command
        # that could take the real tap out, and untap has no business
        # deleting data it does not own.
        if isinstance(rows, list):
            cfg["taps"] = [t for t in rows
                           if not (isinstance(t, dict)
                                   and t.get("name") == tap.name)]
    config.mutate(drop)
    # A config written before names were case-folded can hold `foo` and
    # `FOO`, which on a case-insensitive filesystem share one clone and one
    # cache. Deleting either would strip the tap that stays configured.
    others = list_taps()
    if not _shared(tap.path, [t.path for t in others]):
        _remove_clone(tap)
    if (tap.cache_file.exists()
            and not _shared(tap.cache_file, [t.cache_file for t in others])):
        _remove_cache(tap)
    return tap


def _remove_clone(tap: Tap) -> None:
    """Delete `tap`'s clone, warning rather than raising if it cannot."""
    try:
        util.remove_path(tap.path)
    except OSError as e:
        # Same reasoning as the cache file below, and the same order of
        # operations makes it worse: config has already been saved, so an
        # unhandled error here exits 70 with the tap deregistered and its clone
        # still on disk — `boost taps` no longer lists it, so nothing points at
        # the directory that is left.
        output.warn("could not remove the clone for %s (%s) — delete %s by "
                    "hand" % (tap.name, e.strerror or e,
                              paths.tilde(tap.path)),
                    stream=sys.stderr, wrap=True)


def _remove_cache(tap: Tap) -> None:
    """Delete `tap`'s catalog cache, warning rather than raising if it cannot."""
    if not tap.owns_cache_file:
        return      # boost's own index, not this tap's — see owns_cache_file
    try:
        tap.cache_file.unlink()
    except OSError as e:
        # A cache dir boost cannot write (doctor flags it) made untap exit
        # 70 here with the tap already deregistered. The file left behind
        # names no configured tap, which is what `boost clean` sweeps.
        output.warn("could not remove the catalog cache for %s (%s) — "
                    "make %s writable, then run `boost clean`"
                    % (tap.name, e.strerror or e,
                       paths.tilde(tap.cache_file.parent)),
                    stream=sys.stderr, wrap=True)


#: URL scheme marking a tap that ships inside the wheel rather than living on
#: a remote. :func:`update` refreshes such a tap by re-copying package data —
#: handing this to git is what made a revised built-in rule unreachable.
WHEEL_SCHEME = "builtin:"


def _update_needs_git(tap: Tap, force: bool) -> bool:
    """Whether :func:`update` runs git for `tap`: not for boost's own wheel
    tap, and not for a pinned clone it leaves alone."""
    if tap.url.startswith(WHEEL_SCHEME):
        return False
    cloned = tap.is_cloned and not tap.is_broken_clone
    return not (cloned and tap.pin and not force)


def update(name: str | None = None,
           force: bool = False) -> tuple[dict, dict]:
    """git-pull one tap (or all). Returns ``({name: summary}, {name: error})``.

    **A pinned, already-cloned tap is skipped** unless ``force``, which also
    clears the pin — an update that silently moved a pinned clone is what made
    `tap --at` a suggestion rather than a guarantee. **A pinned tap with no
    clone is not skipped**: there is no clone to hold still, so it is cloned
    and checked out at its pin (reusing the same checkout path `add(at=...)`
    uses), never left on HEAD with a pin that no longer describes it.

    **A named tap still raises.** ``boost update sometap`` is a request about
    that one tap, so its failure is the answer to the question asked.

    **Across all taps it does not.** Upstream repos get deleted, renamed and
    made private by people who have never heard of this machine, and one of them
    used to abort the whole loop: every tap after the dead one went unrefreshed,
    the ones already pulled never had their catalogs rebuilt, and the user saw a
    bare git error naming neither the tap nor the URL. With 80+ taps that is a
    near-certainty rather than an edge case. Collecting failures instead lets the
    other 79 refresh, and lets the caller name the broken one.

    This mirrors what the skill-update loop in ``cmd_update`` already does — warn
    per item and carry on. The tap loop was the one place that did not.

    Pulls run concurrently (mirroring :func:`add_many`'s clone pool) — a pull
    is latency, not CPU, so a plain sweep over dozens of already-current taps
    used to cost one network round trip per tap, serially.
    """
    targets = [get(name)] if name else list_taps()
    if any(_update_needs_git(t, force) for t in targets):
        # Once, up front: per tap, a missing git became N copies of the same
        # failure and a summary advising `boost untap` for every healthy tap.
        gitutil.require_git()
    results: dict = {}
    failures: dict = {}

    def work(tap: Tap) -> tuple[str, bool]:
        """Do the git work for one tap. Returns ``(summary, clear_pin)`` —
        ``clear_pin`` is true when ``force`` moved a previously pinned tap and
        its pin must be dropped. That drop is *reported* here but not *done*
        here: dropping a pin is a `config.json` read-modify-write, and doing
        it from a pool worker — once per tap — would race the same way
        concurrent `registry.add` calls do (see `add_many`'s own single-write
        comment). The caller collects every tap that needs one and clears
        them all in one write after the pool finishes.
        """
        if tap.url.startswith(WHEEL_SCHEME):
            # boost's own tap arrives with the wheel, so there is no remote
            # to pull and the files are re-copied from package data. Git
            # was reached for anyway, against a directory with no .git —
            # `is_cloned` is false, so the *clone* branch handed
            # `builtin:boost` to git as a URL. It failed on every run, and
            # because every downstream loop skips a tap that is not in
            # `results`, a revised built-in rule could never reach a
            # machine that already had it. Imported here rather than at
            # module scope: `builtin` imports this module.
            from . import builtin
            builtin.ensure_tap()
            return "refreshed from the installed package", False
        elif not tap.is_cloned or tap.is_broken_clone:
            # A clone dir with no `.git` takes this branch too: `pull` can
            # only fail there ("not a git repository"), forever, and the
            # remedy is the same re-clone a missing dir gets.
            #
            # A missing clone has nothing to hold still, so a pin here is
            # a target to land on rather than a reason to skip — skipping
            # used to report "pinned … (skipped)" while leaving nothing on
            # disk at all. `force` means "stop holding this tap still", so
            # it clones at HEAD and drops the pin instead.
            #
            # `is_cloned` is `path.is_dir()`, which a *dangling* symlink
            # answers False to — so this branch is exactly where one lands,
            # and git refuses to clone onto an existing link ("could not
            # create work tree dir ... File exists"). Without the removal the
            # tap can never be recovered: doctor reports it not cloned and
            # points at `update`, and update fails the same way forever.
            pin = tap.pin if not force else None
            _reclone(tap, pin)
            if pin:
                return "cloned at %s" % pin[:7], False
            return "cloned", bool(tap.pin)
        elif tap.pin and not force:
            # A pinned tap is held at one commit on purpose: prebuilt
            # vectors are keyed to it, and moving the clone would make
            # them stale while still present — the failure that looks
            # like nothing at all. Not an error, because "update
            # everything" over 400 taps should not fail because three are
            # pinned.
            #
            # Unless the clone is not *at* the pin (a hand checkout, or a
            # clone some older path made at HEAD): "skipped" would then name
            # a commit the tree does not sit on, forever. Put it back — the
            # remedy doctor prints for exactly this — and report it as a
            # move, so the caller rescans the catalog and resyncs vectors.
            head = off_pin(tap)
            if head:
                gitutil.checkout_commit(tap.path, tap.pin,
                                        verify=_signing_guard(tap))
                return ("%s → %s (back on its pin)"
                        % (head[:7], tap.pin[:7]), False)
            return "pinned at %s (skipped)" % tap.pin[:7], False
        return (gitutil.pull(tap.path, verify=_signing_guard(tap)),
                bool(tap.pin))

    to_clear: list[str] = []

    def finalize(tap_name: str, summary: str, clear_pin: bool) -> str:
        if not clear_pin:
            return summary
        # `--force` is a decision to stop holding this tap still, so the pin
        # goes with the move — reported here rather than silently, so a
        # config that went from 20 pins to 0 says so once per tap instead of
        # leaving the reader to notice later. The drop itself is batched
        # below, not applied here.
        to_clear.append(tap_name)
        return summary + " (pin cleared)"

    if name:
        # A single named target: nothing to parallelize, and its failure is
        # the direct answer to the question asked, not a collected one.
        tap = targets[0]
        summary, clear_pin = work(tap)
        results[tap.name] = finalize(tap.name, summary, clear_pin)
    else:
        def run(tap: Tap) -> tuple[str, str | None, bool, str | None]:
            try:
                summary, clear_pin = work(tap)
                return tap.name, summary, clear_pin, None
            except BoostError as err:
                # The caller prefixes the tap name, which is the part git
                # never says; git's own first line already carries the URL
                # or path. See gitutil._git_error for why that line is now
                # the one we show.
                return tap.name, None, False, err.message

        # pool.map yields in call order regardless of completion order (same
        # guarantee `add_many` already relies on), so `results`/`failures`
        # come out in `targets` order exactly as the old serial loop did.
        with ThreadPoolExecutor(max_workers=tap_jobs(None)) as pool:
            for tname, psummary, clear_pin, err in pool.map(run, targets):
                if psummary is None:
                    failures[tname] = err or "unknown error"
                else:
                    results[tname] = finalize(tname, psummary, clear_pin)

    if to_clear:
        # One read-modify-write for every pin `force` dropped this sweep —
        # the same single-write discipline `add_many` uses for newly tapped
        # registries, and for the same reason: N threads each doing their own
        # `config.load()`/`save()` would lose each other's drops at random.
        wanted = set(to_clear)

        def drop_pins(cfg: dict) -> None:
            for row in cfg.get("taps", []) or []:
                if isinstance(row, dict) and row.get("name") in wanted:
                    row.pop("pin", None)
        config.mutate(drop_pins)

    if results:
        # Stamped on any successful sweep, including one where every tap was
        # already current: "refreshed" is about having asked, not about having
        # found something.
        mark_refreshed()
    return results, failures
