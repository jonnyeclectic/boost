# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Tap registries: GitHub repos (or local paths) full of SKILL.md files."""
from __future__ import annotations

import difflib
import os
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
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
    #: A 40-character commit this tap is held at, or "" for "track the default
    #: branch". A pin is durable *because it is recorded here*: `tap --at`
    #: checked a commit out and nothing remembered, so the next `boost update`
    #: moved the clone to HEAD — silently invalidating any prebuilt vectors
    #: imported for that commit, which is the whole reason the pin exists.
    pin: str = ""

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


def parse_specs(specs: list[str]) -> list[tuple[str, str]]:
    """Parse each spec to (name, url) via `parse_spec`, touching nothing.

    Used by `tap --dry-run` to preview targets without cloning or writing
    config — `parse_spec` is already pure (a directory stat at worst), so the
    only job here is applying it across a SPEC list in order.
    """
    return [parse_spec(spec) for spec in specs]


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
    return [Tap(name=t["name"], url=t.get("url", ""),
                curated=bool(t.get("curated")), pin=str(t.get("pin") or ""))
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
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`boost update %s` to refresh it" % name)
    tap = Tap(name=name, url=url, curated=curated)
    paths.ensure_dirs()
    if tap.path.exists():
        util.rmtree(tap.path)
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
        raise BoostError(
            "tap %s failed provenance policy: %s" % (name, "; ".join(problems)),
            hint="add its key with `boost trust add <name> <key>`, "
                 "or relax `boost policy set require_signed_taps false`")
    cfg = config.load()
    row = {"name": name, "url": url, "curated": curated}
    if at:
        row["pin"] = at
    cfg.setdefault("taps", []).append(row)
    config.save(cfg)
    tap.pin = at or ""
    return tap


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
        if tap.path.exists():
            util.rmtree(tap.path)


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
        if tap.path.exists():
            util.rmtree(tap.path)
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
             on_done=None) -> list[dict]:
    """Clone many taps at once and register them in a single config write.

    Returns one result dict per spec, in the order given, each with ``ok`` and
    either ``tap`` or ``error``. One registry's failure never costs another its
    clone — a catalog tap of 463 repos that aborted on the first 404 would be
    worse than useless.

    `pins` maps a tap name to the commit to check out, for published vector
    shards (see ``core.shards``).
    """
    if not specs:
        return []
    paths.ensure_dirs()
    pins = pins or {}
    existing = {t.name for t in list_taps()}
    results: list[dict] = []
    todo: list[str] = []
    for spec in specs:
        try:
            name, _url = parse_spec(spec)
        except BoostError as exc:
            results.append({"spec": spec, "name": spec, "ok": False,
                            "error": exc.message})
            continue
        if name in existing:
            results.append({"spec": spec, "name": name, "ok": False,
                            "skipped": True, "error": "already tapped"})
            continue
        # Guard against the same registry appearing twice in one selection:
        # two threads cloning into one directory is a corrupt clone, not a race
        # anyone would enjoy debugging.
        existing.add(name)
        todo.append(spec)

    def work(spec: str) -> dict:
        name, _url = parse_spec(spec)
        return _clone_one(spec, curated, pins.get(name))

    with ThreadPoolExecutor(max_workers=tap_jobs(jobs)) as pool:
        for res in pool.map(work, todo):
            results.append(res)
            if on_done is not None:
                on_done(res)

    # One read-modify-write, after every clone: N threads doing this each would
    # lose taps, and 463 sequential rewrites of the same file is its own cost.
    fresh = [r for r in results if r.get("ok")]
    if fresh:
        cfg = config.load()
        rows = cfg.setdefault("taps", [])
        for r in fresh:
            row = {"name": r["name"], "url": r["url"], "curated": curated}
            pin = pins.get(r["name"])
            if pin:
                row["pin"] = pin
                r["tap"].pin = pin
            rows.append(row)
        config.save(cfg)
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


def pin(name: str, commit: str) -> Tap:
    """Record `commit` as the tap's pin, so `update` leaves it alone."""
    tap = get(name)
    cfg = config.load()
    for row in cfg.get("taps", []) or []:
        if isinstance(row, dict) and row.get("name") == tap.name:
            row["pin"] = commit
    config.save(cfg)
    tap.pin = commit
    return tap


def unpin(name: str) -> Tap:
    """Drop a tap's pin so it tracks its default branch again."""
    tap = get(name)
    cfg = config.load()
    for row in cfg.get("taps", []) or []:
        if isinstance(row, dict) and row.get("name") == tap.name:
            row.pop("pin", None)
    config.save(cfg)
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
    gitutil.checkout_commit(tap.path, commit)
    return pin(name, commit)


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


def update(name: str | None = None,
           force: bool = False) -> tuple[dict, dict]:
    """git-pull one tap (or all). Returns ``({name: summary}, {name: error})``.

    **A pinned tap is skipped** unless ``force``, which also clears the pin —
    an update that silently moved a pinned clone is what made `tap --at` a
    suggestion rather than a guarantee.

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
        if tap.pin and not force:
            # A pinned tap is held at one commit on purpose: prebuilt vectors
            # are keyed to it, and moving the clone would make them stale while
            # still present — the failure that looks like nothing at all. Not
            # an error, because "update everything" over 400 taps should not
            # fail because three are pinned.
            results[tap.name] = "pinned at %s (skipped)" % tap.pin[:7]
            continue
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
                if tap.pin:
                    # `--force` is a decision to stop holding this tap still,
                    # so the pin goes with the move rather than silently
                    # re-applying on the next run.
                    unpin(tap.name)
        except BoostError as err:
            if name:
                raise
            # The caller prefixes the tap name, which is the part git never
            # says; git's own first line already carries the URL or path. See
            # gitutil._git_error for why that line is now the one we show.
            failures[tap.name] = err.message
    if results:
        # Stamped on any successful sweep, including one where every tap was
        # already current: "refreshed" is about having asked, not about having
        # found something.
        mark_refreshed()
    return results, failures
