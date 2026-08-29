# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Tap registries: GitHub repos (or local paths) full of SKILL.md files."""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path

from ..errors import BoostError
from . import config, gitutil, paths, policy, util


@dataclass
class Tap:
    """One configured tap: name, source URL, and derived on-disk paths."""
    name: str          # "anthropics/skills" or a short alias
    url: str           # https URL or local path
    curated: bool = False

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
    def is_cloned(self) -> bool:
        """True if the tap's clone directory exists on disk."""
        return self.path.is_dir()


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
    if _looks_like_a_directory(p):
        return _checked(p.resolve().name, str(p.resolve()), spec)
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return _checked("/".join(parts), spec, spec)
    if "/" in spec and " " not in spec:
        return _checked(spec, "https://github.com/%s" % spec, spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


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


def list_taps() -> list[Tap]:
    """Configured taps from config.json.

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
    return [Tap(name=t["name"], url=t.get("url", ""), curated=bool(t.get("curated")))
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
    for key in (lambda t: t.name, lambda t: t.safe_name,
                lambda t: t.name.split("/")[-1]):
        hits = [t for t in taps if key(t) == name]
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


def add(spec: str, curated: bool = False) -> Tap:
    """Parse `spec`, shallow-clone it, and record the tap in config.

    Raises BoostError if a tap with that name is already configured.
    """
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`boost update %s` to refresh it" % name)
    tap = Tap(name=name, url=url, curated=curated)
    paths.ensure_dirs()
    if tap.path.exists():
        util.rmtree(tap.path)
    gitutil.clone_shallow(url, tap.path)
    problems = policy.check_tap_signing(tap.path)
    if problems:
        util.rmtree(tap.path)  # leave no half-added tap behind
        raise BoostError(
            "tap %s failed provenance policy: %s" % (name, "; ".join(problems)),
            hint="add its key with `boost trust add <name> <key>`, "
                 "or relax `boost policy set require_signed_taps false`")
    cfg = config.load()
    cfg.setdefault("taps", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def remove(name: str) -> Tap:
    """Deregister a tap and delete its clone and cache file.

    Returns the removed Tap; raises BoostError if it does not exist.
    """
    tap = get(name)
    cfg = config.load()
    cfg["taps"] = [t for t in cfg.get("taps", []) if t["name"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        util.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


#: URL scheme marking a tap that ships inside the wheel rather than living on
#: a remote. :func:`update` refreshes such a tap by re-copying package data —
#: handing this to git is what made a revised built-in rule unreachable.
WHEEL_SCHEME = "builtin:"


def update(name: str | None = None) -> tuple[dict, dict]:
    """git-pull one tap (or all). Returns ``({name: summary}, {name: error})``.

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
    """
    targets = [get(name)] if name else list_taps()
    results: dict = {}
    failures: dict = {}
    for tap in targets:
        try:
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
                results[tap.name] = "refreshed from the installed package"
            elif not tap.is_cloned:
                gitutil.clone_shallow(tap.url, tap.path)
                results[tap.name] = "cloned"
            else:
                results[tap.name] = gitutil.pull(tap.path)
        except BoostError as err:
            if name:
                raise
            # The caller prefixes the tap name, which is the part git never
            # says; git's own first line already carries the URL or path. See
            # gitutil._git_error for why that line is now the one we show.
            failures[tap.name] = err.message
    return results, failures
