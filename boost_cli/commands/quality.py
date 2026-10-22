# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Quality & Health commands — doctor, lint, drift, test, fingerprint, decay,
heal, conflict, changelog, health, trust.

Installed-skill safety/integrity commands (audit, verify, attest,
quarantine) live in commands/safety.py; shared helpers in commands/_common.py.

"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from itertools import starmap
from pathlib import Path
from typing import Any

from .. import cliparse
from ..core import (
    agents,
    ai,
    builtin,
    catalog,
    claude_settings,
    complete,
    config,
    foreign,
    frontmatter,
    gitutil,
    imperative,
    integrity,
    journal,
    lockfile,
    logs,
    paths,
    policy,
    prereq,
    projectlock,
    provenance,
    registry,
    report,
    scopes,
    staleness,
    store,
    util,
)
from ..core import output as out
from ..core import rules as rule_blocks
from ..errors import BoostError
from ._common import (
    _iter_installed,
    _iter_installed_all,
    _iter_installed_rows,
    _require_lock_integrity,
    _s,
    row_dir,
)

# How many rows the unwritten-materializations note spells out before it
# summarises. The note exists to be read in one glance; a lock with one
# agent turned off has a row per installed rule and workflow, so an uncapped
# list is as long as the install.
_MAT_NOTE_SHOWN = 4


def _first(names: list[str], limit: int = 5) -> str:
    """Up to ``limit`` names for a one-line check, with an ellipsis for more."""
    return ", ".join(names[:limit]) + (", …" if len(names) > limit else "")

# --- conflict: normative-rule extraction -----------------------------------

_NEG_MODALS = {"never", "must not", "do not", "don't", "dont"}
_STOPWORDS = {"the", "a", "an", "to", "of", "and", "in", "for", "with",
              "before", "after", "is", "are", "be", "that", "this", "it",
              "on", "at"}
_NEGATORS = {"without", "not", "no", "unless"}
_CONFLICT_OVERLAP = 0.4  # tuned so the fixture's tdd vs cowboy pair is caught

# --- decay: fallback stack markers when commands/discovery is unavailable --

_STACK_MARKERS = [
    ("package.json", ["javascript", "node", "npm", "frontend", "web"]),
    ("tsconfig.json", ["typescript"]),
    ("pyproject.toml", ["python"]),
    ("requirements.txt", ["python"]),
    ("setup.py", ["python"]),
    ("Cargo.toml", ["rust", "cargo"]),
    ("go.mod", ["go", "golang"]),
    ("pom.xml", ["java", "maven"]),
    ("build.gradle", ["java", "gradle"]),
    ("Gemfile", ["ruby", "rails"]),
    ("Dockerfile", ["docker", "container"]),
    ("docker-compose.yml", ["docker"]),
    (".git", ["git", "commit", "workflow"]),
    ("tests", ["testing", "test"]),
    ("test", ["testing", "test"]),
]


# --- shared helpers ---------------------------------------------------------

_tilde = paths.tilde


def _resolve_as_far_as_it_exists(path: Path) -> Path:
    """Absolute ``path``, symlinks resolved down to its deepest real ancestor.

    Plain ``resolve()`` is wrong on both sides of this comparison. The link's
    target does not exist — that is what makes the link broken — and the store
    dir does, so resolving only the one that can be resolved compares a real
    path against a nominal one. On macOS that is not hypothetical: ``/tmp`` is
    itself a symlink to ``/private/tmp``, so a genuine boost link read as
    foreign and `heal` declined to repair anything.
    """
    path = Path(os.path.abspath(str(path)))
    tail: list[str] = []
    cur = path
    while cur != cur.parent and not cur.exists():
        tail.append(cur.name)
        cur = cur.parent
    # RuntimeError is not redundant with OSError here: Python 3.12's
    # `Path.resolve()` raises RuntimeError("Symlink loop from ...") for a
    # cycle even in non-strict mode, and RuntimeError is NOT an OSError
    # subclass — 3.13+ raises OSError for the same input. See
    # store.resolves_into_store for the identical split, caught the same way.
    with suppress(OSError, RuntimeError):
        cur = cur.resolve()
    return cur.joinpath(*reversed(tail))


def _norm(path: Path) -> str:
    """``path`` as a comparable string, without resolving anything.

    Strips Windows' extended-length prefix — ``os.readlink`` returns
    ``\\\\?\\C:\\...`` for a link the store created while ``store_dir()`` is
    spelled the ordinary way, so the two name one location with two strings —
    and applies `os.path.normcase`, which folds case on Windows (where the
    filesystem is case-insensitive) and is a no-op on POSIX.
    """
    # Strip BEFORE abspath: on a POSIX host a backslash path is not absolute,
    # so abspath would prepend the cwd and move the prefix out of position —
    # which matters because this must be testable off Windows.
    text = str(path)
    for prefix in ("\\\\?\\UNC\\", "\\\\?\\"):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return os.path.normcase(os.path.abspath(text))


def _within(target: str, parent: str) -> bool:
    """True if normalised ``target`` is ``parent`` or sits under it."""
    return target == parent or target.startswith(parent.rstrip(os.sep) + os.sep)


def _link_key(path: Path) -> str:
    """``path`` resolved, then normalised into a comparable string.

    Comparing `Path` objects directly is wrong on Windows, in two ways that
    both read as "boost does not own its own link" and left `heal` refusing to
    repair anything at all there:

    * ``os.readlink`` returns the extended-length form (``\\\\?\\C:\\...``) for
      a link the store created, while ``store_dir()`` is spelled the ordinary
      way — same location, different string.
    * The filesystem is case-insensitive, so ``C:\\Users`` and ``c:\\users``
      are one directory and two unequal `Path`s.

    `os.path.normcase` is a no-op on POSIX, so this stays exact where case is.
    """
    return _norm(_resolve_as_far_as_it_exists(path))


def _owned_link(link: Path) -> bool:
    """True if ``link`` points into boost's canonical store.

    Ownership is read off the link itself rather than the lock, so it still
    answers correctly for a skill uninstalled mid-sweep or a lock that has gone
    missing — the two cases where a dangling link is most likely to exist.
    """
    try:
        raw = Path(os.readlink(str(link)))
    except OSError:
        return False
    target = raw if raw.is_absolute() else link.parent / raw
    store = paths.store_dir()
    # Spelled form first. A link boost made carries the store's own path, so
    # this settles the ordinary case without resolving anything — and every
    # platform quirk lives in resolution. Windows alone supplies three: the
    # extended-length prefix, 8.3 short names, and case-insensitivity.
    if _within(_norm(target), _norm(store)):
        return True
    # Resolved form second, for a store genuinely reached through a symlinked
    # parent — macOS `/tmp` -> `/private/tmp` is the case that made this
    # necessary rather than theoretical.
    return _within(_link_key(target), _link_key(store))


def _broken_links() -> tuple[list[Path], list[Path]]:
    """``(ours, theirs)`` — dangling symlinks in the dirs boost links into.

    Two things this deliberately does NOT do.

    **It does not look in a native-store agent's dir.** `unlinking_agents`,
    not `known_agents`: boost never links into `~/.gemini/skills`, so anything
    dangling there belongs to someone else and is none of this command's
    business. A *disabled* agent's dir is looked in: boost linked there while
    it was enabled, and a link it left behind still dangles where that agent
    reads.

    **It does not report a link boost did not create as ours.** `heal` deletes
    what this returns first, and a broken link is not necessarily garbage — a
    skill on an unmounted volume dangles until the volume comes back. Removing
    a link the user made themselves is not a repair, it is data loss with a
    reassuring name, so those are reported and left alone.
    """
    ours: list[Path] = []
    theirs: list[Path] = []
    # Former dirs too (`agents.sweep_dirs`): repointing an agent's dir left
    # every link made under the old one unreachable by any other check.
    for adir in agents.sweep_dirs():
        # ``os.path``: ``Path.is_dir`` raises under a dotdir with no search
        # bit on Python 3.12 and 3.13, and doctor and heal exited 70 there.
        if not os.path.isdir(adir):  # noqa: FURB146
            continue
        for link in sorted(adir.iterdir()):
            if link.is_symlink() and not link.exists():
                (ours if _owned_link(link) else theirs).append(link)
    return ours, theirs


def _read_skill(skill_dir: Path) -> tuple[dict, str]:
    """(frontmatter, body) for a skill dir's SKILL.md; ({}, "") if unreadable."""
    md = Path(skill_dir) / "SKILL.md"
    if not md.exists():
        return {}, ""
    try:
        return frontmatter.parse(md.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {}, ""


def _drift_status(name: str, entry: dict) -> str:
    """'in-sync' | 'local-edits' | 'upstream-moved' | 'source-missing'
    | 'source-changed'
    | 'store-missing' | 'n/a' (local imports with no tap source)."""
    sdir = store.copy_dir(name, entry)
    if sdir.is_dir() and integrity.self_sourced(name, entry):
        # Kept in the store itself: an edit there is the skill, not drift.
        return staleness.NA
    store_sha = util.sha256_dir(sdir) if sdir.is_dir() else None
    if store_sha is not None and integrity.exec_drifted(sdir, entry):
        return staleness.LOCAL_EDITS
    return _drift_from_copy(name, entry, store_sha, sdir)


def _drift_from_copy(name: str, entry: dict, copy_sha: str | None,
                     copy: Path | None) -> str:
    """:func:`staleness.drift_state` for an installed copy hashing to ``copy_sha``.

    The tap source is only read once the copy matches the lock, so a missing
    or edited copy never costs a materialization.
    """
    is_local = entry.get("tap") == "local"
    lock_sha = entry.get("sha256", "")
    source_sha = None
    changed = exec_changed = False
    if copy_sha is not None and copy_sha == lock_sha and not is_local:
        changed = _tap_source_changed(entry)
        if not changed:
            cat = {"name": name, "tap": entry.get("tap", ""),
                   "rel_dir": entry.get("source_dir", ".")}
            try:
                source_sha = store.skill_source_sha(cat)
            except BoostError:
                source_sha = None
            if source_sha is not None:
                exec_changed = store.source_exec_changed(cat, entry, copy)
    return staleness.drift_state(copy_sha, lock_sha, is_local, source_sha,
                                 source_changed=changed,
                                 exec_changed=exec_changed)


def _tap_source_changed(entry: dict) -> bool:
    """:func:`registry.source_changed` for a lock row; False when untapped."""
    try:
        tap = registry.get(str(entry.get("tap", "")))
    except BoostError:
        return False
    return registry.source_changed(entry, tap)


def _drift_status_project(name: str, entry: dict, base: Path) -> str:
    """:func:`_drift_status` for a skill installed ``--local`` into ``base``.

    Its copies are judged the way ``verify`` judges them
    (:func:`integrity.project_status`, every copy hashed), so an edit to any
    one is local edits and a deleted row is a missing copy; only then is the
    tap compared, over the same vocabulary as a user-scope row.
    """
    st = integrity.project_status(entry, base)
    if st == integrity.STATUS_MISSING:
        return staleness.STORE_MISSING
    if st == integrity.STATUS_MODIFIED:
        return staleness.LOCAL_EDITS
    d = integrity.project_skill_dir(entry, base)
    copy_sha = (entry.get("sha256", "") if st == integrity.STATUS_OK
                else util.sha256_dir(d) if d is not None else None)
    return _drift_from_copy(name, entry, copy_sha, d)


def _drift_status_materialized(kind: str, name: str, entry: dict) -> str:
    """The rule/workflow analogue of `_drift_status`, over the same vocabulary.

    "Local edits" means the materialized artifact — the CLAUDE.md block or
    rendered command file — no longer hashes to what install wrote; "upstream
    moved" means the tap's source text no longer hashes to the lock's sha256.
    Quarantine removes the artifacts on purpose, which would otherwise read as
    the most alarming status on the board.
    """
    if entry.get("quarantined"):
        return "quarantined"
    st = integrity.materialized_status(name, entry, kind)
    if st == integrity.STATUS_STRANDED:
        # Not "store-missing": that row's hint is `boost heal`, which
        # re-materializes into the recorded base and recreates the repo the
        # user deleted. Before the tap comparison for the same reason as
        # `unreachable` -- a source matching its hash says nothing about an
        # install whose every artifact went with its repo.
        return "stranded"
    if st == integrity.STATUS_MISSING:
        return "store-missing"
    if st == integrity.STATUS_MODIFIED:
        return "local-edits"
    if st == integrity.STATUS_OUTDATED:
        # Before the tap comparison, which matches the lock's new digest and
        # would call an agent still holding the old copy in sync.
        return "outdated"
    if st == integrity.STATUS_UNREACHABLE:
        # Before the tap comparison below, which would otherwise launder an
        # item that reaches no agent into "in-sync" on the strength of a
        # source file matching a hash nothing on disk was written from.
        return "unreachable"
    if entry.get("tap") == "local":
        return "n/a"
    if _tap_source_changed(entry):
        return staleness.SOURCE_CHANGED
    try:
        raw = (registry.get(entry["tap"]).path / entry.get("source_file", "")
               ).read_text(encoding="utf-8", errors="replace")
    except (OSError, BoostError):
        return "source-missing"
    if hashlib.sha256(raw.encode("utf-8")).hexdigest() != entry.get("sha256"):
        return "upstream-moved"
    return "in-sync"


#: Every word `_drift_status` and `_drift_status_materialized` can return.
#: The render site subscripts this directly, so a missing key is a KeyError --
#: not a BoostError, so `boost drift` exits 70 with a crash report rather than
#: mis-painting one cell. `test_drift_vocabulary_is_covered` pins the two
#: against each other.
_DRIFT_ROLE = {"in-sync": "success", "local-edits": "warn",
               "upstream-moved": "accent", "source-missing": "danger",
               "source-changed": "warn",
               "store-missing": "danger", "n/a": "muted",
               "quarantined": "muted", "unreachable": "warn",
               "stranded": "danger", "outdated": "warn",
               "misdirected-link": "warn"}


def _drift_hint(name: str, status: str, tap: str = "",
                tap_url: str = "", scope: str | None = None) -> str:
    # A reinstall of a project row needs `--local`: bare `reinstall` reads the
    # user lock and, given a same-named user install, reinstalls that instead.
    local = " --local" if scope == scopes.SCOPE_PROJECT else ""
    if status == "quarantined":
        return "boost quarantine --release %s to restore" % name
    if status == "upstream-moved":
        return "boost update"
    if status == "source-changed":
        # `boost update` holds these back on purpose: the tap's copy of the
        # name is another repository's item, taken only when asked for.
        return ("boost reinstall %s%s to take the new source's copy, or "
                "re-tap the original" % (name, local))
    if status == "local-edits":
        return "boost reinstall %s%s to discard local edits" % (name, local)
    if status == "source-missing":
        # `boost update` only refreshes configured taps. When the entry's
        # tap has been untapped, that command is a guaranteed no-op — the
        # only remedy that can actually restore the source is re-tapping it.
        # The name is not a spec, so the hint re-taps the recorded source.
        #
        # Still tapped is two states. A clone that is missing or broken is
        # what `update` repairs. A healthy clone without the entry means it
        # was removed upstream, which `update` answers "no longer in tap —
        # leaving as-is" — so hinting it looped. `outdated` words that state
        # through the same helper.
        if not registry.is_tapped(tap):
            return registry.retap_hint(tap, tap_url)
        t = next((t for t in registry.list_taps() if t.name == tap), None)
        if t is not None and t.is_cloned and not t.is_broken_clone:
            return staleness.removed_upstream_remedy(name)
        return "boost update"
    if status in ("store-missing", "misdirected-link"):
        return "boost heal"
    if status == "outdated":
        return "boost sync"
    if status == "stranded":
        # The record is the fault: uninstall drives off its rows and creates
        # nothing, where heal/sync/reinstall would recreate the deleted repo.
        return "boost uninstall %s" % name
    if status == "unreachable":
        # Not `boost sync`: it filters these rows out by design, so it is a
        # guaranteed no-op. Not "re-enable the agent" either -- that is wrong
        # advice for `agents.WITHDRAWN_REASONS`. `doctor` is where
        # `_mat_remedy` words the split correctly.
        return "boost doctor"
    return ""


def _parse_ts(iso: str) -> datetime | None:
    try:
        return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return None


def _q_suffix(e: dict) -> str:
    # Quarantine de-arms a component (a poisoned rule stops being materialized,
    # a skill's links are removed) without deleting its lock entry, so the
    # digest must move too or a quarantined-then-released environment reads
    # as unchanged. Suffixed rather than dropped: dropping the line would make
    # quarantine indistinguishable from uninstall.
    return ":q" if e.get("quarantined") else ""


def _fingerprint() -> tuple[str, list[str], list[str]]:
    """(sha256 hexdigest, component lines, uncloned tap names).

    Deterministic: the same lock file and tap commits always produce the same
    hash. An uncloned tap hashes as an empty commit rather than being skipped
    silently — its name is returned separately so callers can say the digest
    is incomplete instead of passing it off as a real measurement."""
    comps = sorted("%s:%s%s" % (n, e.get("sha256", ""), _q_suffix(e))
                   for n, e in lockfile.installed().items())
    # Rules and workflows are part of the environment the agent runs on —
    # a poisoned CLAUDE.md rule must change the fingerprint. Kind-prefixed so
    # a skill-only environment's fingerprint is unchanged by this addition.
    comps += sorted("%s/%s:%s%s" % (kind, n, e.get("sha256", ""), _q_suffix(e))
                    for kind, section in lockfile.all_installed().items()
                    if kind != "skill" for n, e in section.items())
    uncloned = []
    tap_lines = []
    for t in registry.list_taps():
        if t.is_cloned and gitutil.has_git():
            commit = gitutil.head_commit(t.path)
        else:
            commit = ""
            uncloned.append(t.name)
        tap_lines.append("%s:%s" % (t.name, commit))
    comps += sorted(tap_lines)
    digest = hashlib.sha256("\n".join(comps).encode()).hexdigest()
    return digest, comps, sorted(uncloned)


def _norm_token(tok: str) -> str:
    t = re.sub(r"[^a-z0-9]", "", tok.lower())
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        t = t[:-1]
    return t


def _stack_keywords(cwd: Path) -> set:
    """Tech-stack keywords for the working directory: the discovery module's
    detect_stack keywords, enriched with coarse filesystem markers (so tags
    like `testing` or `git` can match even when detect_stack is language-only)."""
    kws: list[str] = []
    with suppress(Exception):
        from ..core.stackprobe import detect_stack
        stack = detect_stack(cwd)
        if isinstance(stack, dict):
            kws.extend(str(k) for k in (stack.get("keywords") or []))
    for marker, words in _STACK_MARKERS:
        if (Path(cwd) / marker).exists():
            kws.extend(words)
    return {_norm_token(k) for k in kws if _norm_token(k)}


def _decay_rows(cwd: Path) -> list[dict]:
    """Relevance/recency verdict per installed skill (shared by decay/health)."""
    kws = _stack_keywords(cwd)
    last_by: dict = {}
    for e in journal.events():
        subj, ts = e.get("subject"), _parse_ts(e.get("ts", ""))
        if subj and ts and (subj not in last_by or ts > last_by[subj]):
            last_by[subj] = ts
    cutoff = datetime.now(UTC) - timedelta(days=30)
    rows = []
    for name, _entry in _iter_installed():
        meta, _ = _read_skill(store.skill_store_dir(name))
        toks = {_norm_token(t) for t in re.split(r"[-_/\s]+", name)}
        toks |= {_norm_token(w) for w in
                 re.findall(r"[A-Za-z0-9]+", str(meta.get("description") or ""))}
        tags = meta.get("tags") or []
        toks |= {_norm_token(str(t)) for t in (tags if isinstance(tags, list) else [tags])}
        toks.discard("")
        overlap = len(kws & toks)
        relevance = "ok" if overlap >= 2 else ("low" if overlap == 1 else "none")
        ts = last_by.get(name)
        recent = ts is not None and ts >= cutoff
        # Machine value: an ISO timestamp, or None when there is no journal
        # entry — humanizing (`rel_time`, the "never" placeholder) is a
        # display concern the table branch applies, not this shared row.
        last_iso = ts.strftime("%Y-%m-%dT%H:%M:%SZ") if ts else None
        if relevance == "none" and not recent:
            verdict = "decay"
        elif relevance in ("none", "low"):
            verdict = "review"
        else:
            verdict = "ok"
        rows.append({"name": name, "relevance": relevance,
                     "last_activity": last_iso, "verdict": verdict})
    return rows


# --- commands ---------------------------------------------------------------

def _mat_remedy(off: list[tuple[str, str, str, str]]) -> str:
    """The remedy for `boost doctor`'s unwritten-materializations note.

    It is worded from the reasons actually present, because only two of them
    are the user's to reverse (`agents.CONFIG_REASONS`). The note used to say
    "change that agent's entry ... and run `boost sync`" for all of them,
    which for `takes skills only` means setting `antigravity.skills_only:
    false` and for `has no slash-command format` means `codex.workflows:
    true` -- and `config.DEFAULTS` records, for each, that boost turned it
    off because the file written would be one the agent silently never loads
    (`agents.WITHDRAWN_REASONS`). So doctor's first advice was to undo a
    deliberate withdrawal for a worse outcome than the stale record, and the
    warning against it is worth printing precisely because the flag is there
    to be found.

    The upgrade path is the realistic trigger and it reaches only that half:
    a user who installed workflows before `codex` gained `workflows: False`
    now has one codex row per installed workflow, and no config edit helps a
    single one of them.

    One fixable row is enough to offer the config edit, because the note is
    one line for every row it shows and for that row the edit is the whole
    fix. The withdrawal warning is separate and asks its own question, so a
    mixed run does not lose it -- it is on the branch that had nothing better
    to say.
    """
    drop = "`boost uninstall` the item to drop the record"
    reasons = {why for _k, _n, _a, why in off}
    tail = ""
    if reasons & set(agents.WITHDRAWN_REASONS):
        tail = (" A format boost withdrew (%s) is not one to turn back on: "
                "the file written would be one the agent never loads."
                % ", ".join("`%s`" % r for r in agents.WITHDRAWN_REASONS
                            if r in reasons))
    if reasons & set(agents.CONFIG_REASONS):
        return ("Change that agent's entry in %s and run `boost sync`, or "
                "%s.%s" % (paths.config_path(), drop, tail))
    return ("%s, or leave it \u2014 the row is what lets a later uninstall "
            "remove the artifact.%s" % (drop, tail))


def _drifted(kind: str, name: str, entry: dict, bad) -> int:
    """Name a rule/workflow whose written content no longer hashes to the
    lock, and return the issue count it adds.

    Doctor checked only that each materialization existed, so a hand edit
    `boost verify` fails and `boost drift` calls a local edit left the verdict
    "healthy". Asked through the function `verify` uses, so the two cannot
    disagree about one file; only after the presence checks found nothing,
    so a missing artifact is not reported twice.
    """
    if integrity.materialized_status(name, entry, kind) != integrity.STATUS_MODIFIED:
        return 0
    bad(kind, "%s %s modified since install — run `%s` %s"
        % (kind, name, *integrity.modified_remedy(name, kind)), wrap=True)
    return 1


def cmd_doctor(argv):
    ap = cliparse.parser(
        prog="boost doctor", description="Check installation health & report issues")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    # Every check routes through the collector so one run can speak prose or
    # JSON without the message existing in two spellings — see core/report.py.
    rep = report.Report(as_json=args.json)

    if not args.json:
        out.heading("boost doctor")

    def bad(name, msg, wrap=False):
        rep.issue(name, msg, wrap=wrap)

    if gitutil.has_git():
        rep.ok("git", "git on PATH")
    else:
        bad("git", "git not found on PATH — install git")
    # Create silently; one a refused mkdir leaves missing is named below.
    refused = paths.create_dirs(paths.boost_dirs())

    # A corrupt config.json reads as DEFAULTS, so the tap list below comes
    # back empty and the verdict used to be "ready to set up", exit 0, on a
    # machine whose clones were all still on disk. Say what was lost instead.
    cfg_err = config.check()
    if cfg_err:
        clones = config.unlisted_clones()
        bad("config", "%s — boost is running on defaults, so %s. Repair the "
            "file, or re-add your taps; the next write moves the bad file "
            "to config.json.corrupt" % (cfg_err, (
                "the %d tap clone%s on disk %s not listed" % (
                    len(clones), _s(len(clones)),
                    "is" if len(clones) == 1 else "are"))
                if clones else "no taps or settings are read"), wrap=True)

    # Same for policy.json: unreadable, it reads as defaults, and the
    # verdict was "healthy" while every rule in it went unenforced.
    pol_err = policy.check()
    if pol_err:
        bad("policy", "%s — every install is refused until it is repaired; "
            "the next `boost policy set` moves it aside to policy.json.corrupt"
            % pol_err, wrap=True)
    else:
        # Parsed, but a value unreadable at its type reads as its (permissive)
        # default for display while every install is refused.
        for key, value, expected in policy.invalid_values():
            bad("policy", "policy.json holds %s = %s, which expects %s — "
                "every install is refused until it is fixed with `boost "
                "policy set %s <%s>`" % (key, json.dumps(value), expected, key,
                                         policy.spec_for(key)), wrap=True)

    # One agent whose `dir` names an unset `${VAR}` makes `known_agents` raise,
    # and a dozen checks below reach it — the link loop, the materialization
    # checks, the broken-link sweep, duplicate discovery, the agent-dir checks.
    # Left alone, the first of them ended the run: exit 1, one error line, no
    # verdict, and not a byte of `--json`. So the question is asked once, here,
    # and a bad answer turns those sections off rather than the report: each
    # is skipped with `agents_ok`, and the row says that it was, because a
    # skipped check that printed nothing would read as a passed one.
    agent_errs = agents.check()
    agents_ok = not agent_errs
    # A row with no dir is skipped rather than refused, so it leaves the other
    # checks on; it is still a broken config, and nothing else names it.
    for aname in agents.dirless(claim=True):
        bad("agent-config", "agents.%s has no dir, so boost skips it — set one "
            "with `boost config set agents.%s.dir <dir>`, or remove the row "
            "with `boost config unset agents.%s`" % (aname, aname, aname),
            wrap=True)
    for aname, key, value in agents.bad_flags(claim=True):
        bad("agent-config", "agents.%s.%s is %s, not a boolean, so boost reads "
            "it as %s — fix it with `boost config set agents.%s.%s "
            "<true|false>`" % (aname, key, json.dumps(value),
                               str(agents.flag_default(aname, key)).lower(), aname,
                               key), wrap=True)
    if agents_ok:
        for aname, spec in agents.known_agents().items():
            if spec["store_alias"]:
                rep.note("agent-config", "agents.%s.dir (%s) is the canonical "
                         "store, so %s reads every skill there directly — "
                         "boost does not link into it"
                         % (aname, _tilde(spec["dir"]),
                            agents.display_name(aname)), wrap=True)
    for aname, err in agent_errs:
        key = "agents.%s.dir" % aname
        bad("agent-config", "%s: %s — %s, or set a path with `boost config set "
            "%s <dir>`; until then commands that resolve agents refuse, and "
            "doctor skipped its link, materialization and agent-dir checks"
            % (key, err.message, err.hint or "fix the value", key), wrap=True)

    # A cache dir boost cannot write leaves every command rescanning its taps
    # and warning that it could not keep the result (catalog.rebuild_tap), so
    # "cloned & cached" below would be the one line on the screen claiming
    # otherwise. A missing one under a directory that refuses the mkdir is the
    # same problem, fixed in that directory rather than the one never made.
    cache_dir = paths.cache_dir()
    cache_block = paths.refuses_writes(cache_dir)
    # A file or dangling link at the cache path is moved, not chmodded: heal
    # says so, and the two must not prescribe different fixes.
    cache_moved = cache_block is not None and paths.in_the_way(cache_block)
    # `taps` is the literal clone list — every row config.json holds, boost's
    # own `boost/builtin` among them — and the loop below asks clone-and-cache
    # questions of each, which is exactly what it is for. `configured` is the
    # different question "has this user set boost up yet", and it is the one
    # the setup note and the verdict turn on: counting the builtin there
    # reported "1 tap cloned & cached · ● healthy" on the machine `boost mcp`
    # leaves behind, while `boost search` on the same HOME said nothing was
    # tapped. Same helper as the MCP tools now.
    taps = registry.list_taps()
    configured = builtin.configured_tap_count()
    tap_ok = 0
    for tap in taps:
        if not tap.is_cloned:
            bad("tap", "tap %s not cloned — run `boost update`" % tap.name)
        elif tap.is_broken_clone:
            bad("tap", registry.broken_clone_line(tap.name), wrap=True)
        elif (head := registry.off_pin(tap)) is not None:
            # Before the stale-catalog check: its remedy, `heal`, rescans the
            # cache to match the off-pin tree and turns this line green with
            # the clone still on the wrong commit. `update <name>` checks the
            # pin back out (and rescans); `--force` is the other honest exit.
            bad("tap", "tap %s is pinned at %s but its clone is at %s — run "
                "`boost update %s` to return it, or `boost update --force %s` "
                "to follow its default branch"
                % (tap.name, tap.pin[:7], head[:7], tap.name, tap.name),
                wrap=True)
        elif not tap.cache_file.exists():
            bad("tap", "tap %s has no catalog cache — run `boost update %s`%s"
                % (tap.name, tap.name, " once %s is %s"
                   % (_tilde(cache_block), "moved aside" if cache_moved
                      else "writable") if cache_block else ""), wrap=True)
        elif (moved := catalog.stale_commit(tap)) is not None:
            # load_tap serves a cache from another commit as-is, so every
            # lookup answers from the old tree until something rescans it.
            bad("tap", "tap %s catalog is stale (scanned at %s, clone at %s) "
                "— run `boost heal`" % (tap.name, moved[0][:7], moved[1][:7]),
                wrap=True)
        else:
            tap_ok += 1
    # With config.json unreadable no tap is listed, so every clone would read
    # as unlisted; the config row above already names them.
    for half in [] if cfg_err else registry.unfinished_clones():
        bad("tap", "%s is a clone that never finished (no tap lists it and it "
            "has no commit checked out) — delete it" % _tilde(half), wrap=True)
    if taps and cache_block:
        bad("cache", "%s — every command rescans its taps and cannot keep the "
            "result; %s"
            % (paths.not_writable(cache_dir, cache_block),
               paths.write_remedy(cache_block) if cache_moved
               else "make %s writable" % _tilde(cache_block)),
            wrap=True)
    # With no taps the cache line above is silent, but heal still names a
    # cache dir it cannot create, so doctor must too.
    for d in refused:
        if d != cache_dir or not taps:
            bad("dirs", paths.not_writable(d, paths.refuses_writes(d) or d),
                wrap=True)
    # An existing store that refuses writes: the mkdir above succeeds, so
    # `refused` never holds it, and doctor said healthy while every install
    # exited 1 naming it (`store._require_writable`).
    store_dir = paths.store_dir()
    store_block = paths.refuses_writes(store_dir)
    if store_block is not None and store_dir not in refused:
        bad("store", "%s — every install is refused until it is fixed; %s"
            % (paths.not_writable(store_dir, store_block),
               paths.write_remedy(store_block)), wrap=True)
    # A swap's moved-aside copy that could not be deleted: nothing else ever
    # names one, and each failed reinstall added another.
    leftovers = store.leftover_copies()
    if leftovers:
        bad("store", "%d leftover skill cop%s in %s (%s) — `boost clean` "
            "removes %s" % (len(leftovers),
                            "y" if len(leftovers) == 1 else "ies",
                            _tilde(store_dir),
                            ", ".join(p.name for p in leftovers),
                            "it" if len(leftovers) == 1 else "them"),
            wrap=True)
    # What a boost killed mid-write or mid-install left: a temp copy of the
    # lock file, or a staging dir, in the dir agents read skills from.
    temps = store.stale_temps()
    for pth, kind in temps:
        if kind == store.PARKED_STORE:
            bad("store", "%s holds the %s — compare it with %s, move back "
                "what is missing, then delete it" % (_tilde(pth), kind,
                                                    _tilde(store_dir)),
                wrap=True)
    temps = [t for t in temps if t[1] != store.PARKED_STORE]
    if temps:
        bad("store", "%d stale temp file%s or staging dir%s a killed boost "
            "left in %s (%s) — `boost clean` removes %s"
            % (len(temps), _s(len(temps)), _s(len(temps)), _tilde(store_dir),
               ", ".join(p.name for p, _kind in temps),
               "it" if len(temps) == 1 else "them"), wrap=True)
    if configured and tap_ok == len(taps):
        rep.ok("taps", "%d tap%s cloned%s" % (len(taps), _s(len(taps)),
                                              "" if cache_block
                                              else " & cached"))
    elif not configured and not cfg_err:
        # `boost tap --defaults` leads, and it is the same command in the same
        # order that `boost search`'s error, `mcp.no_results` and the MCP
        # `boost_doctor` tool all name. A user who hits two of these surfaces
        # in one session must not see the recommendation flip and read it as
        # two different fixes — which is exactly what happened here: search
        # said `--defaults`, doctor said `owner/repo`.
        rep.note("taps", "no registries tapped — nothing is searchable yet; add the "
                 "recommended ones with `boost tap --defaults`", wrap=True)

    # lockfile.read() collapses missing/corrupt/wrong-schema into an empty
    # skeleton so ordinary reads degrade cleanly — but that is exactly why
    # this used to print "lock file parses (v3)" for a lock file that did not
    # exist. check() reports the raw state instead, so "parses" is only ever
    # claimed for a file doctor actually parsed.
    integ = lockfile.check()
    skills = lockfile.installed()
    # Sorted once, by the check just made: the lock line counts what `boost
    # sync` re-records, and the store-dirs block below names the rest. Not
    # without agents, whose dirs are what say whose a store dir is.
    unrec = store.sort_unrecorded(skills, integ) if agents_ok else None
    if integ.problem == "older":
        # Readable, and every record in it counts: only the schema stamp is
        # behind, and the next write — `boost sync` makes one — records it.
        rep.note("lockfile", "lock file parses, but %s — `boost sync` records "
                 "it as v%d" % (lockfile.fault(integ), lockfile.SCHEMA_VERSION),
                 wrap=True)
        lock_ok = True
    elif integ.ok:
        rep.ok("lockfile", "lock file parses (v%d)" % lockfile.SCHEMA_VERSION)
        lock_ok = True
    elif integ.problem == "missing":
        # What `boost sync` re-records, not every dir in the store: counting
        # another tool's bucket or a copy of Cursor's skills, which sync
        # leaves, kept this line red after the run it prescribes.
        lost = (unrec["unrecorded_store"] if unrec is not None
                else store.unrecorded_store_dirs({}) if store.has_content() else [])
        if lost:
            n = len(lost)
            bad("lockfile", "lock file missing — %d store dir%s unrecorded, "
                "run `boost sync` to re-record %s" % (n, _s(n), "it" if n == 1 else "them"))
            lock_ok = False
        elif unrec is not None and unrec["unreadable_store"]:
            # Not "nothing installed": the dirs boost cannot read may be skills
            # the lock had, and the line below names them.
            rep.note("lockfile", "no lock file — nothing boost can read is "
                     "left to re-record")
            lock_ok = True
        else:
            rep.note("lockfile", "no lock file yet — nothing installed")
            lock_ok = True
    elif integ.problem == "corrupt":
        bad("lockfile", "lock file is corrupt — %s" % lockfile.remedy(integ),
            wrap=True)
        lock_ok = False
    elif lockfile.newer(integ):
        bad("lockfile", "lock file %s — %s"
            % (lockfile.fault(integ), lockfile.remedy(integ)), wrap=True)
        lock_ok = False
    else:  # "schema"
        bad("lockfile", "lock file schema is %s, expected v%d — %s"
            % ("unreadable" if integ.version is None
               else "v%s" % integ.version, lockfile.SCHEMA_VERSION,
               lockfile.remedy(integ)), wrap=True)
        lock_ok = False

    # linking_agents, not enabled_agents, for the same reason `sync_plan` uses
    # it: the lock's `agents` field is measured by `store.linked_agents`, which
    # only walks linking agents — so a native-store name in there is a *stale*
    # row, written before that agent's `links_skills` flipped (gemini's did;
    # codex arrived after). Looking it up in the enabled set finds a real
    # directory holding no symlink and reports "not linked — run `boost sync`",
    # which sync then declines to act on. Doctor and sync have to agree.
    enabled = agents.linking_agents() if agents_ok else {}
    # A skill an enabled plugin ships with the same files gets no Claude Code
    # link, so its absence is no fault (`store.left_to_plugin`).
    coverage = store.plugin_coverage(skills) if agents_ok else {}
    covered = store.covered_skills(coverage)
    skill_issues = 0
    quarantined_skills = 0
    # Withheld by an older boost, which left the copy in the store: no agent
    # link, so nothing below sees it, but Gemini CLI and Codex read the store.
    unheld = set(store.unheld_withheld()) if lock_ok else set()
    for name, entry in sorted(skills.items()):
        if name in unheld:
            bad("skill-held", "%s skill %s is still in %s, where Gemini CLI "
                "and Codex load it — run `boost heal`"
                % ("quarantined" if entry.get("quarantined") else "sidelined",
                   name, _tilde(paths.store_dir())), wrap=True)
            skill_issues += 1
        sdir = store.copy_dir(name, entry)
        if not sdir.is_dir():
            # A pin over a moved source is a repair heal declines, so naming
            # heal sent the user round doctor -> heal -> doctor. Whether the
            # source moved is a hash of the tap source, and reading that goes
            # through `source_dir_for`, which widens a sparse clone and can
            # fetch. Doctor stays read-only and offline, so it names the
            # preview that answers instead of asking itself.
            if entry.get("pinned") and not store.is_url_import(entry):
                bad("skill", "skill %s missing from store — it is pinned, so "
                    "`boost heal --dry-run` shows whether heal can restore it"
                    % name, wrap=True)
                skill_issues += 1
                continue
            fix = ("boost reinstall %s" % name if store.is_url_import(entry)
                   else "boost heal")
            bad("skill", "skill %s missing from store — run `%s`" % (name, fix))
            skill_issues += 1
            continue
        if entry.get("quarantined"):
            quarantined_skills += 1
            # Quarantine skips a link it may not look at or remove, and
            # records that agent in `refused_agents`. A link on disk is the
            # same failure seen after the `chmod`, or one written by a
            # quarantine from before it recorded anything. Either way an
            # agent may still load the skill, which "none active" denied.
            unsure = entry.get("refused_agents") or []
            still = [*unsure, *(a for a, d in enabled.items()
                                if a not in unsure
                                and os.path.islink(d / name))]
            if still:
                bad("skill-quarantine", "quarantined skill %s may still be "
                    "linked for %s — run `boost quarantine %s` again"
                    % (name, ", ".join(still), name))
                skill_issues += 1
            continue
        # tamper detection: the lock file records a sha256 at install time, but
        # only `boost verify` ever re-checked it — surface content drift here too.
        # `integrity.skill_modified` is the test `boost_doctor` asks too.
        if integrity.skill_modified(name, entry):
            cmd, why = integrity.modified_remedy(name)
            bad("skill", "skill %s modified since install — run `%s` %s"
                % (name, cmd, why), wrap=True)
            skill_issues += 1
        # A deliberate sideline (`focus`, `profile use`, `context apply`)
        # unlinked this skill on purpose, and `sidelined_by` says so. Without
        # this the per-agent loop below read the lock's stale `agents` list —
        # what was linked before the sideline — and reported every missing
        # link as damage, sending the reader to `boost sync`, which then
        # undid the switch they had just made.
        if entry.get("sidelined_by"):
            continue
        # The agents the skill's scope takes in, as `boost sync` walks them:
        # the lock's `agents` is what was linked, so a link never made — one
        # refused at install, or for an agent enabled since — was a repair
        # sync offered and doctor never mentioned.
        for agent, adir in store.scoped_agents(entry, enabled).items():
            link = adir / name
            if store.left_to_plugin(name, agent, link, covered):
                continue
            # Two different failures wore one message. `boost sync` creates a
            # link where nothing is in the way and replaces a boost-owned one
            # that dangles — but it will not delete a real file or directory
            # another installer put there, so prescribing it for that case sent
            # the reader in a circle: sync answers "everything in sync", doctor
            # repeats itself. Name the thing in the way instead.
            # ``os.path``: under a dotdir with no search bit ``Path.is_symlink``
            # raises on Python 3.12 and 3.13, and doctor exited 70 on it.
            if os.path.islink(link) and os.path.exists(link):  # noqa: FURB141
                # Live is not enough: one into another skill's store dir has
                # the agent load that skill under this name (`sync_plan`
                # lists it as a missing link, and heal replaces it).
                wrong = store.misdirected(name, link)
                if wrong is not None:
                    bad("skill-link", "skill %s linked for %s to %s, not its "
                        "own store dir — run `boost heal`"
                        % (name, agent, paths.tilde(wrong)), wrap=True)
                    skill_issues += 1
                continue
            if not os.path.lexists(link) and paths.refuses_writes(adir):
                # Not one `boost sync` can make until the dir allows it: the
                # agent-dir line below names the dir and its `chmod`.
                continue
            if not os.path.islink(link) and os.path.exists(link):  # noqa: FURB141
                bad("skill-link", "skill %s not linked for %s — %s exists and is not a boost "
                    "link; move or delete it, then run `boost sync`"
                    % (name, agent, paths.tilde(link)))
            elif os.path.islink(link) and not store.is_boost_link(link):  # noqa: FURB146
                # Dangling, and not boost's: sync leaves it, so prescribing
                # sync alone was a loop.
                bad("skill-link", "skill %s not linked for %s — %s is a broken "
                    "link boost did not make; move or delete it, then run "
                    "`boost sync`" % (name, agent, paths.tilde(link)))
            else:
                bad("skill-link", "skill %s not linked for %s — run `boost sync`" % (name, agent))
            skill_issues += 1
        # The other direction, read from disk as `sync_plan` reads it. Doctor
        # has to say it because `boost sync` does: a "healthy" that
        # contradicts the command it tells you to run is worse than no check
        # at all. The lock's `agents` missed a link made by hand.
        scope = entry.get("only_agents")
        stray = store.out_of_scope_agents(name, entry, enabled)
        if stray:
            bad("skill-scope", "skill %s is linked for %s, outside its declared scope (%s) — "
                "run `boost sync --prune`"
                % (name, ", ".join(stray), ", ".join(scope)))
            skill_issues += 1
    active_skills = len(skills) - quarantined_skills
    # "with agent links" is a claim the loop above only checked with agents_ok.
    if skills and not skill_issues and agents_ok:
        # A quarantined skill has no agent links — the check above counts
        # any it could not remove as an issue — so it must not inflate this count into a false
        # "healthy, N skills with agent links" the way it used to.
        if active_skills:
            rep.ok("skills", "%d skill%s present in store with agent links%s"
                   % (active_skills, _s(active_skills),
                      " (%d quarantined)" % quarantined_skills
                      if quarantined_skills else ""))
        else:
            rep.ok("skills", "%d skill%s quarantined, none active"
                   % (quarantined_skills, _s(quarantined_skills)))

    # Project-scoped skills committed into THIS repo — the governance blind spot
    # #212 left open. They don't touch the user store, so the loop above never
    # saw them; a vendored third-party skill that has drifted from its committed
    # digest is exactly what a health check should surface.
    pbase, pskills = integrity.project_skills()
    proj_issues = 0
    plock_err = projectlock.check(pbase) if pbase is not None else None
    if plock_err:
        # It reads as no project skills, so the loop below finds nothing
        # wrong with copies nothing records any more.
        bad("project-lock", "%s — boost sees no project skills here and "
            "refuses to install or uninstall any until it is repaired; %s"
            % (plock_err, projectlock.RECOVER_HINT % projectlock.LOCK_REL),
            wrap=True)
        proj_issues += 1
    for name, entry in sorted(pskills.items()):
        st = integrity.project_status(entry, pbase)
        if st == integrity.STATUS_MISSING:
            gone = integrity.project_missing_rows(entry, pbase)
            if integrity.project_skill_dirs(entry, pbase):
                # Some copies stand: name the agents' copies that do not, or
                # "its files are gone" reads false over an intact .claude/.
                bad("project-skill", "project skill %s is missing %s — run "
                    "`boost heal`" % (name, ", ".join(gone)), wrap=True)
            else:
                bad("project-skill", "project skill %s is in .boost but its "
                    "files are gone — run `boost sync`" % name)
            proj_issues += 1
        elif st == integrity.STATUS_MODIFIED:
            bad("project-skill", "project skill %s modified since install — "
                "run `%s` %s" % (name, *integrity.modified_remedy(
                    name, scope=scopes.SCOPE_PROJECT)), wrap=True)
            proj_issues += 1
        # An agent enabled after the install has no row, so the status above
        # cannot see it; `boost sync` copies into it, as it does for a rule.
        for agent in store.unmaterialized_project_agents(pbase, name, entry):
            bad("project-skill", "project skill %s was never written for %s "
                "— run `boost sync`" % (name, agent))
            proj_issues += 1
        # Independent of the status above: a redirected row reads intact,
        # because the hash follows the symlink, and is still one uninstall
        # will leave on disk.
        for row in integrity.project_redirected(entry, pbase):
            bad("project-skill", "project skill %s: %s is reached through a "
                "symlink inside the repo, so `boost uninstall --local` will "
                "not remove that copy — it names the row and prints the "
                "`rm -rf` that does"
                % (name, row), wrap=True)
            proj_issues += 1
    if pskills and not proj_issues:
        rep.ok("project-skills", "%d project skill%s intact in %s"
               % (len(pskills), _s(len(pskills)), paths.tilde(pbase)))

    # Rules and workflows don't live in the store — they materialize into agent
    # dirs (a file drop, or a CLAUDE.md managed block). Health = every recorded
    # materialization is still on disk; a deleted file means the install rotted.
    # Quarantined = materializations removed on purpose; reporting them as rot
    # would send the user to `boost reinstall`, which re-arms the rule — and
    # counting them "fully materialized" would be the opposite lie.
    all_rules = lockfile.installed_rules()
    all_workflows = lockfile.installed_workflows()
    rules = {n: e for n, e in all_rules.items() if not e.get("quarantined")}
    workflows = {n: e for n, e in all_workflows.items()
                 if not e.get("quarantined")}
    quarantined_rules = len(all_rules) - len(rules)
    quarantined_workflows = len(all_workflows) - len(workflows)
    mat_issues = 0
    # A `--local` row whose repo has been deleted is one fault, not one per
    # agent, and its remedy is not `boost reinstall`: that re-materializes
    # into the recorded base and recreates the directory (`scopes.stranded`).
    # Named once with the command that drops the record, and kept out of the
    # per-row checks below so they cannot prescribe the resurrecting one.
    # Quarantined rows included: `quarantine --release` refuses a stranded
    # row, so quarantining one must not be the way to make doctor go quiet.
    for kind, section in (("rule", all_rules), ("workflow", all_workflows)):
        for name, entry in sorted(section.items()):
            if scopes.stranded(entry):
                bad(kind, "%s %s was installed --local into %s, which no "
                    "longer exists — run `boost uninstall %s` to drop the "
                    "record%s" % (kind, name, _tilde(Path(entry["base"])), name,
                                  " (it is quarantined; release cannot "
                                  "restore it)" if entry.get("quarantined")
                                  else ""),
                    wrap=True)
                mat_issues += 1
    rules = {n: e for n, e in rules.items() if not scopes.stranded(e)}
    workflows = {n: e for n, e in workflows.items() if not scopes.stranded(e)}
    # Every materialization check asks which agents boost writes, so with an
    # unresolvable agent there is nothing to check them against.
    if not agents_ok:
        rules, workflows = {}, {}
    for kind, section in (("rule", rules), ("workflow", workflows)):
        for name, entry in sorted(section.items()):
            for m in entry.get("materializations") or []:
                if not store.materialization_is_written(kind, entry, m):
                    continue  # named once below, not reported as rot
                if m.get("unwritable"):
                    # Refused at install, so `boost reinstall` would be refused
                    # too until the dir allows it; the agent-dir line below
                    # names the `chmod`, or the move when a file or a dangling
                    # link is in the way. Any file there predates the refusal.
                    block = paths.refuses_writes(Path(m.get("path", "")).parent)
                    if store.occupied(Path(m.get("path", ""))):
                        why = ("%s, then `boost sync` writes it"
                               % store.occupied_refusal(m["path"]))
                    elif block is not None and paths.in_the_way(block):
                        why = ("%s is in the way — `boost sync` writes it once "
                               "it is moved" % _tilde(block))
                    else:
                        why = ("its dir was not writable — `boost sync` writes "
                               "it once it is")
                    bad(kind, "%s %s was not written for %s: %s"
                        % (kind, name, m.get("agent", "?"), why), wrap=True)
                    mat_issues += 1
                elif m.get("stale"):
                    bad(kind, "%s %s for %s is older than the installed v%s — "
                        "run `boost sync`" % (kind, name, m.get("agent", "?"),
                                              out.plain(entry.get("version",
                                                                  "?"))),
                        wrap=True)
                    mat_issues += 1
            # An agent enabled after the install has no row at all, so the
            # loop above never meets it; `boost sync` writes it.
            for agent in store.unmaterialized_agents(kind, entry):
                bad(kind, "%s %s was never written for %s — run `boost sync`"
                    % (kind, name, agent), wrap=True)
                mat_issues += 1
    for name, entry in sorted(rules.items()):
        before = mat_issues
        for m in entry.get("materializations") or []:
            p = Path(m.get("path", ""))
            if m.get("unwritable"):
                continue
            if not store.materialization_is_written("rule", entry, m):
                continue
            if m.get("mode") == "claude":
                try:
                    text = p.read_text(encoding="utf-8") if p.exists() else ""
                except OSError:
                    text = ""
                present = ("boost:rule:%s start" % name) in text
                # The start marker alone counted as present, while `verify`
                # reads the same block as missing and the next write appends
                # a second block after the orphan rather than replacing it.
                if present and rule_blocks.unclosed_block(text, name):
                    bad("rule", "rule %s's block in %s has a start marker and "
                        "no end marker — restore its `%s` line or delete the "
                        "orphaned block, then run `boost reinstall %s`"
                        % (name, _tilde(p), rule_blocks.markers(name)[1], name),
                        wrap=True)
                    mat_issues += 1
                    continue
            else:
                # ``os.path``: ``Path.is_file`` raises under a dotdir with no
                # search bit on Python 3.12 and 3.13.
                present = os.path.isfile(p)  # noqa: FURB146
            if not present:
                bad("rule", "rule %s missing its %s materialization — run "
                    "`boost reinstall %s`" % (name, m.get("agent", "?"), name))
                mat_issues += 1
        # As for a workflow below: the user's own rules-dir file held the path.
        for r in store.foreign_rows(entry):
            if (store.materialization_is_written("rule", entry, r)
                    and not os.path.lexists(r["path"])):
                bad("rule", "rule %s was not written for %s: a file boost did "
                    "not write held %s, and it is gone now — run `boost sync`"
                    % (name, r["agent"], _tilde(r["path"])), wrap=True)
                mat_issues += 1
        if mat_issues == before:
            mat_issues += _drifted("rule", name, entry, bad)
    for name, entry in sorted(workflows.items()):
        before = mat_issues
        for m in entry.get("materializations") or []:
            if not store.materialization_is_written("workflow", entry, m):
                continue
            if not m.get("unwritable") and not os.path.isfile(m.get("path", "")):
                if lockfile.is_skill_copy(m):
                    bad("workflow", "workflow %s missing its skill copy at %s "
                        "— run `boost sync`" % (name, _tilde(m.get("path", ""))),
                        wrap=True)
                else:
                    bad("workflow", "workflow %s missing its %s file — run "
                        "`boost reinstall %s`"
                        % (name, m.get("agent", "?"), name))
                mat_issues += 1
        # The user's own file held this path at install. While it is there
        # that is their choice, not a fault; once it is gone the command is
        # missing, and `boost sync` writes it (`store.sync_plan` agrees).
        for r in store.foreign_rows(entry):
            if (store.materialization_is_written("workflow", entry, r)
                    and not os.path.lexists(r["path"])):
                bad("workflow", "workflow %s was not written for %s: a file "
                    "boost did not write held %s, and it is gone now — run "
                    "`boost sync`" % (name, r["agent"], _tilde(r["path"])),
                    wrap=True)
                mat_issues += 1
        if mat_issues == before:
            mat_issues += _drifted("workflow", name, entry, bad)
    # A note, not an issue: the workflow works for every agent with a workflow
    # format. Only an agent that reads skills alone (Codex) misses it.
    unreached = store.workflows_without_skill_copy() if agents_ok else []
    if unreached:
        rep.note("workflows-as-skills", _as_skill_note(unreached), wrap=True)
    # Said once, as a note rather than an issue: the row is there because the
    # user changed that agent's config after installing, which is their
    # decision, and the two ways out are theirs to pick. Reporting it as a
    # fault instead is what kept `boost doctor` at one permanent issue whose
    # remedy could not run -- see `agents.materialization_is_written`. It
    # names the items and the per-agent reason, because "disabled" is only
    # one of them: an agent can be enabled and still take no workflow.
    off = store.unwritten_materializations() if agents_ok else []
    if off:
        shown = ["%s %s → %s (%s)" % (k, n, a, why)
                 for k, n, a, why in off[:_MAT_NOTE_SHOWN]]
        if len(off) > _MAT_NOTE_SHOWN:
            shown.append("and %d more" % (len(off) - _MAT_NOTE_SHOWN))
        rep.note("unwritten-materializations",
                 "%d recorded materialization%s name%s an agent boost no "
                 "longer writes: %s. %s"
                 % (len(off), _s(len(off)), "s" if len(off) == 1 else "",
                    ", ".join(shown), _mat_remedy(off)),
                 wrap=True)
    # The per-row note above answers "which row, which agent, why". This
    # answers a different question the surfaces had nowhere to put: skip every
    # row an item has and the item reached no agent at all. `rep.note`, not
    # `rep.warn` -- WARN is documented as restating a fault already counted,
    # and this one is counted nowhere -- and not `rep.issue`, which would
    # invert doctor's standing convention that a config-orphaned row is the
    # user's own decision, named once and never scored. `verify` and `attest`
    # are the surfaces that fail; doctor's job here is to stop contradicting
    # its own note.
    nowhere = [(kind, name)
               for kind, section in (("rule", rules), ("workflow", workflows))
               for name, entry in sorted(section.items())
               if integrity.reaches_no_agent(kind, entry)]
    if nowhere:
        # No remedy sentence: every one of these items has at least one row,
        # so the per-row note above has already printed `_mat_remedy`'s
        # wording for it, and repeating it verbatim one line later is how a
        # report teaches the reader to skim past it.
        rep.note("materialized-nowhere",
                 "%d item%s reach%s no agent boost writes, so %s installed "
                 "but loaded by nothing: %s"
                 % (len(nowhere), _s(len(nowhere)),
                    "es" if len(nowhere) == 1 else "",
                    "it is" if len(nowhere) == 1 else "they are",
                    ", ".join("%s %s" % (k, n) for k, n in nowhere)),
                 wrap=True)
    if (all_rules or all_workflows) and not mat_issues and agents_ok:
        # Quarantined rules/workflows are excluded above so their stashed-but-
        # removed materializations don't read as rot — but excluding them from
        # `rules`/`workflows` entirely used to make this line vanish outright
        # when everything installed happened to be quarantined, in place of
        # ever saying so.
        note = ""
        if quarantined_rules or quarantined_workflows:
            bits = []
            if quarantined_rules:
                bits.append("%d rule%s" % (quarantined_rules,
                                           _s(quarantined_rules)))
            if quarantined_workflows:
                bits.append("%d workflow%s" % (quarantined_workflows,
                                               _s(quarantined_workflows)))
            note = " (%s quarantined)" % " and ".join(bits)
        if off:
            # Without this the line reads as a flat contradiction of the note
            # right above it: "fully materialized" is true of the agents boost
            # writes, and that is now a smaller set than the rows record.
            note += " for every agent boost writes"
        # Counted over the items that reach at least one agent. The suffix
        # above is what the note said this line contradicted -- "fully
        # materialized for every agent boost writes" is trivially true of an
        # item whose write set is empty, so counting it there is what made
        # the count true as worded and false as read.
        n_rules = len(rules) - sum(1 for k, _n in nowhere if k == "rule")
        n_flows = len(workflows) - sum(1 for k, _n in nowhere if k == "workflow")
        rep.ok("rules-workflows", "%d rule%s and %d workflow%s fully materialized%s"
               % (n_rules, _s(n_rules), n_flows, _s(n_flows), note))

    # Store dirs the lock does not record, sorted by whose they are: this was
    # one "orphaned store dir" line, prescribing a `boost sync` that did
    # nothing with them while `heal` reported nothing to heal. A dir a lost
    # lock had is the lock line's (`store.sort_unrecorded` keeps it out of
    # these buckets), so no fault is counted twice; one a lock that cannot be
    # read may have recorded is in none of them.
    if unrec is not None:
        mine = unrec["adoptable_store"]
        backup = lockfile.unrestored_corrupt() if mine else None
        if backup:
            # A rollback restores the lock as it was before its last change,
            # so these may be what that change installed, not strays.
            bad("unrecorded-skills", lockfile.unrestored_line(
                len(mine), _first(mine), backup), wrap=True)
        elif mine:
            bad("unrecorded-skills", "%d skill%s added outside boost (%s) — "
                "`boost sync` records %s" % (len(mine), _s(len(mine)),
                                             _first(mine),
                                             "it" if len(mine) == 1 else "them"))
        repos = [r for r in unrec["foreign_store"] if store.is_repo_copy(r)]
        copies = [r[0] for r in unrec["foreign_store"] if r not in repos]
        if copies:
            bad("foreign-copies", "%d store dir%s cop%s another tool's skills, "
                "not boost's (%s) — remove with `boost sync --prune`"
                % (len(copies), _s(len(copies)),
                   "ies" if len(copies) == 1 else "y", _first(copies)), wrap=True)
        # `--prune` leaves a git repository, so naming it there would send the
        # user to a command that keeps it.
        for line in store.foreign_store_lines(repos):
            bad("repo-copies", line, wrap=True)
        if unrec["unreadable_store"]:
            bad("unreadable-store", store.unreadable_line(unrec["unreadable_store"]),
                wrap=True)
        # Notes, not issues: boost leaves these alone by design, so counting
        # them would hold doctor red on a state no boost command changes.
        for line in store.older_copy_lines(unrec["older_copies"]):
            rep.note("older-copies", line, wrap=True)
        if unrec["not_skill_store"]:
            rep.note("not-skills", store.not_skill_line(unrec["not_skill_store"]),
                     wrap=True)
        if unrec["misnamed_store"]:
            rep.note("misnamed", store.misnamed_line(unrec["misnamed_store"]),
                     wrap=True)
        # An issue, not a note: the workflow it belongs to has no record, so
        # no command updates or uninstalls it until `boost install` re-records.
        for line in store.workflow_copy_lines(unrec["workflow_copies"]):
            bad("workflow-copies", line, wrap=True)
        # The same for a rule's block in a context file: the agent reads it
        # every session and `boost uninstall` answers "not installed".
        for line in store.rule_block_lines(unrec["rule_blocks"]):
            bad("rule-blocks", line, wrap=True)
    dups = store.plugin_duplicates(skills, coverage) if agents_ok else []
    same = [r[0] for r in dups if r[3] == foreign.IDENTICAL]
    if same:
        bad("plugin-duplicates", "%d skill%s show%s twice in Claude Code, which "
            "also loads %s from an enabled plugin (%s) — `boost sync --prune` "
            "drops boost's Claude Code link"
            % (len(same), _s(len(same)), "s" if len(same) == 1 else "",
               "it" if len(same) == 1 else "them", _first(same)), wrap=True)
    for line in store.plugin_newer_lines(dups):
        bad("plugin-newer", line, wrap=True)
    for line in store.plugin_variant_lines(dups):
        rep.note("plugin-variants", line, wrap=True)

    broken, strays = _broken_links() if agents_ok else ([], [])
    if broken:
        bad("broken-links", "%d broken symlink%s in agent dirs — run `boost heal`"
            % (len(broken), _s(len(broken))))
    # A live link into the store named for no installed skill: heal and
    # sync remove it (`store.stale_links`), so doctor names it too. The
    # dangling ones are the broken links above.
    live_stale = [p for p in (store.stale_links(skills, store.lock_vouches(integ))
                              if agents_ok else [])
                  if os.path.exists(p)]  # noqa: FURB141
    if live_stale:
        bad("stale-links", "%d stale link%s into the store in agent dirs, for "
            "no installed skill (%s) — run `boost heal`"
            % (len(live_stale), _s(len(live_stale)),
               ", ".join(paths.tilde(p) for p in live_stale)), wrap=True)
    if strays:
        # `out.info`, not `bad`: this does not raise the issue count, because
        # boost will not fix it and `heal` deliberately leaves it — counting it
        # would leave doctor permanently red on something no boost command can
        # clear, which is how a health check stops being read.
        rep.note("foreign-links", "%d broken symlink%s in agent dirs not created by boost — "
                 "left alone; yours to remove or repair"
                 % (len(strays), _s(len(strays))))

    others = claude_settings.foreign_hooks("global")
    if others:
        # `out.info`, not `bad`, for the same reason as the foreign symlinks
        # above: boost did not write these and will never remove them, so
        # counting them would leave doctor permanently red on something no
        # boost command can clear. Naming them is still worth a line — at
        # 130k stars gstack is now a likely second writer of this exact file,
        # and a user debugging a hook needs to know boost is not the only one
        # in it.
        events = sorted({h["event"] for h in others})
        rep.note("foreign-hooks", "%d hook%s in ~/.claude/settings.json not managed by boost "
                 "(%s) — left alone; `boost hooks` only touches its own"
                 % (len(others), _s(len(others)), ", ".join(events)), wrap=True)

    try:
        prereq_rows = prereq.for_installed()
    except BoostError:
        # doctor's contract is to *report* problems, not to raise on one. A
        # BoostError out of the catalog or the lock would otherwise abort the
        # health report part-way through, and this check is the least
        # important thing in it.
        prereq_rows = []
    if prereq_rows:
        # Declared in the items' own frontmatter and resolvable to real
        # catalogued items that are not installed. `rep.note`, not `bad`: it
        # is somebody else's frontmatter, and boost will not install it for
        # them (see `core/prereq`), so counting it would leave doctor
        # permanently red on something no boost command clears on its own.
        #
        # One line, truncated, like `orphans` above — not one per item; a
        # note per declaring item would repeat a single `name` down the whole
        # `--json` `checks` array (see `prereq.summary_line`).
        rep.note("unmet-prerequisite", prereq.summary_line(prereq_rows),
                 wrap=True)

    stars = registry.overstarred()
    if stars:
        # One issue, not one per tap: a machine that tapped the catalogue
        # before the ★ was narrowed holds ~420 of these, and the same remedy.
        bad("curated", "%d tap%s %s a ★ the catalogue no longer gives (%s%s)"
            " — `boost heal` clears %s"
            % (len(stars), _s(len(stars)),
               "carries" if len(stars) == 1 else "carry", ", ".join(stars[:3]),
               ", …" if len(stars) > 3 else "",
               "it" if len(stars) == 1 else "them"), wrap=True)

    for dup in (store.duplicate_discovery() if agents_ok else ()):
        # An agent that reads the canonical store natively, holding its own
        # entry for a skill that store already carries. Boost did not put it
        # there — it never links into a native-store agent — but the agent
        # loads the same skill from two discovery tiers and says so on every
        # session, so a health check that stayed quiet about it would be
        # describing a machine the user is not looking at.
        bad("duplicate-discovery", "skill %s is discoverable twice by %s — %s leads to %s, which it "
            "already reads natively; remove the duplicate with "
            "`boost heal --prune-duplicates`"
            % (dup.name, agents.display_name(dup.agent), _tilde(dup.path),
               _tilde(dup.target)), wrap=True)

    # Every dir boost writes into: the linking agents' skills dirs, and the
    # rules/ and commands/ dirs rules and workflows materialize into. Not a
    # native-store agent's skills dir (Gemini's): boost never writes it, and
    # `boost sync` could not act on it.
    skills_dirs = set(agents.linking_agents().values()) if agents_ok else set()
    for adir, block in (store.blocked_agent_dirs() if agents_ok else ()):
        # A file or a dangling link where the dir belongs. Heal names it,
        # install skips the agent, and doctor said nothing and exited 0.
        bad("agent-dir", "%s — %s, then `boost sync` %s what it missed"
            % (paths.not_writable(adir, block), paths.write_remedy(block),
               "relinks" if adir in skills_dirs else "writes"), wrap=True)
    for adir in (store.unwritable_agent_dirs() if agents_ok else ()):
        # A next action, like the log line below it: without one this was
        # the only issue doctor names that nothing can act on.
        bad("agent-dir", "agent dir %s — %s, then `boost sync` writes what "
            "it missed" % store.unwritable_refusal(str(adir)), wrap=True)

    rotation = journal.rotation_healthy()
    if not rotation:
        bad("journal", "journal is overdue for rotation — run `boost heal`")

    # Which search engine will actually answer a query. Dense retrieval needs
    # three things to line up and every one of them fails silently, so doctor
    # is where the answer belongs — `search` only ever reports the engine that
    # already ran, never that a configured one never got the chance.
    _report_search_engine(rep)

    lp = logs.log_path()
    if lp.exists():
        # Existence is not health: a log the process cannot open makes every
        # invocation print a PermissionError traceback from the logging module
        # while this check happily reported a ✓ for the same file. Diagnostics
        # are the first thing consulted when something else breaks, so a log
        # that silently accepts nothing has to read as a fault. Mode bits
        # (os.access) are not the same question as "can this process actually
        # open it" — an ACL, an immutable flag, or a sandboxing layer can say
        # no where the bits say yes — so ask the real question: attempt the
        # same append-mode open the handler itself performs.
        try:
            with lp.open("a", encoding="utf-8"):
                pass
        except OSError:
            writable = False
        else:
            writable = True
        if writable:
            rep.ok("log", "diagnostic log at %s" % _tilde(lp))
        else:
            bad("log", "diagnostic log %s is not writable — every invocation is "
                "failing to record; fix its permissions (chmod u+w)"
                % _tilde(lp))
    if not logs.dir_writable():
        # The append-open above passes in a read-only directory, but rotation
        # (a rename) and crash reports (a new file) both need to create
        # entries there — rotation failing is what silently froze the log.
        bad("logs", "logs directory %s is not writable — crash reports and "
            "log rotation cannot be written; fix its permissions (chmod u+w)"
            % _tilde(paths.logs_dir()))
    crashes = sorted(paths.logs_dir().glob("crash-*.log")) \
        if paths.logs_dir().is_dir() else []
    if crashes:
        # `out.info`, not `bad`/`out.warn`, for the same reason as the foreign
        # symlinks and hooks above: a crash report is history, not a current
        # fault, so it must not wear the "!" glyph or verdict a healthy
        # machine as having an issue that needs attention.
        rep.note("crashes", "%d crash report%s in %s (newest: %s) — see `boost log --crashes`"
                 % (len(crashes), _s(len(crashes)), _tilde(paths.logs_dir()),
                    crashes[-1].name))

    # `skills` is the user store only, so in a repo holding committed skills
    # the summary said "0 skills installed" on the same screen as the project
    # row that had just counted them. Name the second number rather than fold
    # it into the first: they live in different places and `boost uninstall`
    # treats them differently, so one total would be a different claim.
    line1 = ("%d skill%s installed%s · %d tap%s synced · %s"
             % (len(skills), _s(len(skills)),
                " (+%d in this project)" % len(pskills) if pskills else "",
                tap_ok, _s(tap_ok),
                "%d broken link%s" % (len(broken), _s(len(broken)))
                if agents_ok else "links not checked"))
    # A warn, not an ok, when the links went unchecked: a ✓ beside "links
    # not checked" reads as passed. Restates the agent-config issue above.
    (rep.ok if not broken and agents_ok else rep.warn)("summary", line1)
    if lock_ok and rotation:
        rep.ok("integrity", "lock file integrity OK · log rotation healthy")
    else:
        rep.warn("integrity",
                 "lock file integrity or log rotation needs attention")

    # A machine with no taps has nothing to disagree about, so every check
    # above passes and the verdict read "healthy" — directly under the line
    # saying no registries are tapped. That is the one state where a clean bill
    # of health actively misleads: boost cannot answer anything yet, which is a
    # setup step rather than a fault. Reported, never fatal — the exit code
    # still turns only on real issues, so scripts and CI are unaffected. The
    # MCP `boost_doctor` tool already refused to say "healthy" here; this is
    # the CLI half of the same rule.
    issues = rep.issues
    if issues == 0 and nowhere:
        # Same rule as the no-taps case above, for the same reason: "healthy"
        # is the one word this machine is not. An item nothing loads is not
        # an issue -- it is the user's own config, and doctor's convention is
        # to name that rather than score it -- but `boost health` keys
        # `needs attention` on it and sends the reader here, so a verdict
        # reading "healthy" would close that loop with a flat contradiction.
        # Reported, never fatal: the exit code still turns only on issues.
        # Ahead of the no-taps branch below on purpose: a machine holding an
        # installed item is not "ready to set up", and that wording would
        # bury the more specific fact under a setup prompt.
        rep.verdict(False,
                    "%d item%s installed but loaded by nothing — see above"
                    % (len(nowhere), _s(len(nowhere))))
    elif issues == 0 and not configured:
        rep.verdict(True, "ready to set up — tap a registry to make boost "
                          "searchable")
    else:
        rep.verdict(issues == 0,
                    "healthy" if not issues else
                    "%d issue%s %s attention — see the suggestions above"
                    % (issues, _s(issues), "needs" if issues == 1 else "need"))
    rep.emit()
    return rep.exit_code()


# The remedy table moved to core.dense.fix_hint so `boost search` reports the
# same next action as `boost doctor` — see that function for why.


def _report_search_engine(rep) -> None:
    """Report the engine `boost search` will use, and why it isn't the best one.

    Only a *degraded* dense tier counts against doctor's exit code: BM25 is the
    documented default and most users never opt in, so an unconfigured tier is
    healthy. Vectors already on disk that have stopped serving are not.
    """
    # Local import: the dense/embedding engines are opt-in and stay out of
    # startup for every other command (scripts/import_budget.py enforces it).
    from ..core import dense, rag
    # Before the dense tiers: whatever they say, BM25 is the floor every
    # search lands on, and a docs index over an unreadable postings store
    # answers "no matches" for an exact skill name while every other line
    # here reads healthy.
    fault = rag.postings_fault()
    if fault:
        fix = "`boost reindex --force` rebuilds it"
        rep.issue("search-index",
                  "%s, so keyword search matches nothing — %s" % (fault, fix),
                  hint=fix, wrap=True)
    # count=True: doctor prints the chunk total, and a health check is the one
    # caller that can afford the scan when a legacy store never recorded it.
    # `boost search`'s hint deliberately does not (see `dense._chunk_total`).
    st = dense.status(count=True)

    if st["ready"]:
        rep.ok("search-engine",
               "semantic search active — %s %s (%d-d), %d chunk%s across %d tap%s"
               % (st["provider"], st["model"], st["dim"] or 0,
                  st["chunks"], _s(st["chunks"]), st["taps"], _s(st["taps"])))
        if not st["quantized"]:
            # Ready but slow, which no other line here would say. `vec0` has no
            # ANN index, so an unquantized store re-scans every vector on every
            # query — 28.2 s measured at 750,416 chunks. The remedy costs no
            # embedding calls, so it is worth naming rather than leaving the
            # user to wonder why the search they enabled feels broken.
            # A warning, not an issue: the store still answers every query,
            # so counting it would leave doctor red on a machine whose search
            # works. Same rule as the foreign links and hooks above.
            rep.warn("search-quantization",
                     "the vector store predates binary quantization, so every "
                     "query scans all %d vectors — `boost reindex --dense` "
                     "converts it offline (no re-embedding, no API cost)"
                     % st["chunks"])
        return

    fix = dense.fix_hint(st["reason"], st)
    if st["reason"] == "corrupt":
        # Its own line: there is no chunk count or build to describe, and
        # "not configured" — what this used to say — named the wrong fault.
        rep.issue("search-engine",
                  "semantic search silently off — %s is not a readable "
                  "SQLite database; searches are using BM25 — %s"
                  % (dense.db_path().as_posix(), fix), hint=fix, wrap=True)
        return
    if st["degraded"]:
        # The store was built and is now dead weight: say what it holds, what
        # changed, and that search has silently been on BM25 the whole time.
        built = st["built_model"] or st["built_provider"] or "an older build"
        detail = "built with %s" % built
        if st["reason"] == "model-changed":
            detail += ", live model is %s" % st["model"]
        elif st["reason"] == "provider-changed":
            # "live key is local" named a key that does not exist: the local
            # model is what `provider()` falls through to when every key is
            # gone, which is the commonest way a store reaches this reason.
            detail += ", live provider is %s" % st["provider"]
        elif st["reason"] == "empty":
            detail += " but holds no vectors"
        elif st["reason"] == "model-unavailable":
            # The store is fine; the query embedder is what failed. Say which
            # half and when, because a record from an hour ago on another
            # network reads differently from one made by the last search.
            from ..core import embed
            fail = st.get("model_failure") or {}
            detail += ", but %s" % embed.local_failure_text(fail)
            # A hand-edited marker can hold a number no calendar has a date
            # for (`inf`, 1e30), and `fromtimestamp` raises three different
            # ways on those. Doctor's job here is to report a failure, so it
            # drops the "when" rather than becoming one.
            if isinstance(fail.get("at"), (int, float)):
                with suppress(ValueError, OverflowError, OSError):
                    detail += ", last tried %s" % util.rel_time(
                        datetime.fromtimestamp(fail["at"], UTC)
                        .strftime("%Y-%m-%dT%H:%M:%SZ"))
        rep.issue("search-engine",
                  "semantic search silently off — %d-chunk vector store %s; "
                  "searches are using BM25 — %s" % (st["chunks"], detail, fix),
                  hint=fix, wrap=True)
        return

    if st["reason"] == "disabled":
        # A deliberate opt-out, not a fault, so it stays a note and doctor
        # stays green: BOOST_NO_EMBED is documented as the hard kill switch,
        # and the CI job that sets it is the one caller that most needs a
        # zero exit code. Say the vectors are still there, because the user
        # who turned it off is the user deciding whether to turn it back on.
        held = ""
        if st["store_exists"] and st["chunks"]:
            # "still on disk", not "intact": the switch shadows every rung
            # below it, so a store that is *also* stale (version/model/dim
            # changed) reaches this line too, and unsetting the switch would
            # turn it red rather than green. Say what is measured — the
            # vectors were not discarded — and let the next status say more.
            held = (" — the %d-chunk vector store is still on disk"
                    % st["chunks"])
        rep.note("search-engine",
                 "semantic search off by BOOST_NO_EMBED — using the "
                 "full-content BM25 engine%s (%s)" % (held, fix),
                 hint=fix, wrap=True)
        return

    rep.note("search-engine",
             "semantic search not configured — using the full-content BM25 "
             "engine (%s)" % fix, hint=fix, wrap=True)


def _print_skipped(skipped: list[dict]) -> None:
    """Note the rule/workflow entries `lint` passed over (they have no SKILL.md)."""
    if not skipped:
        return
    out.info("skipped %d rule/workflow item%s (%s) — lint scores SKILL.md skills only"
             % (len(skipped), _s(len(skipped)),
                ", ".join(s["name"] for s in skipped[:5])))


def cmd_lint(argv):
    ap = cliparse.parser(
        prog="boost lint", description="Validate SKILL.md frontmatter & quality")
    ap.add_argument("names", nargs="*", metavar="NAME",
                    help="installed skill name(s), or a path to a skill "
                         "directory / its SKILL.md")
    ap.add_argument("--tap", metavar="TAP", help="lint every skill in a tap's clone")
    ap.add_argument("--min", type=util.score_int, default=40, dest="min_score", metavar="N",
                    help="minimum passing score, 0-100 (default 40)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    targets: list[tuple[str, Path]] = []
    skipped: list[dict] = []
    if args.tap:
        tap = registry.get(args.tap)
        if not tap.is_cloned:
            raise BoostError("tap %s is not cloned" % tap.name,
                            hint="run `boost update %s`" % tap.name)
        targets, skipped = catalog.lint_targets(
            catalog.load_tap(tap), tap.path, args.names or None)
    else:
        names = args.names or []
        path_names = [n for n in names if catalog.is_path_target(n)]
        other_names = [store.installed_name(n) for n in names
                       if n not in path_names]
        for n in path_names:
            p = catalog.resolve_path_target(n)
            # Label it with the name boost installs it under, not its dir.
            targets.append((util.lint_label(p), p))
        if not names or other_names:
            targets += [(r.name, row_dir(r))
                        for r in _iter_installed_rows(other_names or None)]
    if not targets:
        if args.json:
            print(json.dumps({"min": args.min_score, "skills": [],
                              "skipped": skipped, "failed": 0}))
        else:
            _print_skipped(skipped)
            if args.tap or args.names:
                # A narrowed target set (--tap, or explicit names/paths) can
                # legitimately come up empty while skills are installed —
                # "no skills installed" would be false here.
                out.info("nothing to lint")
            else:
                print(out.empty_state("no skills installed",
                                      hint="boost install <skill> to start"))
        return 0

    results: list[dict[str, Any]] = []
    for name, sdir in targets:
        score, notes = util.score_skill(sdir)
        errors = util.lint_errors(sdir)
        notes = [n for n in notes
                 if "missing `name`" not in n and "missing `description`" not in n
                 and n != "missing SKILL.md" and n != frontmatter.UNCLOSED_NOTE]
        mismatch = util.name_dir_note(sdir)
        if mismatch and not errors:
            notes.append(mismatch)
        results.append({"name": name, "score": score, "notes": notes,
                        "errors": errors, "path": str(sdir)})

    failed = [r for r in results if r["score"] < args.min_score or r["errors"]]
    if args.json:
        print(json.dumps({"min": args.min_score, "skills": results,
                          "skipped": skipped, "failed": len(failed)}))
        return 1 if failed else 0

    width = max(len(r["name"]) for r in results)
    for r in results:
        score_role = ("success" if r["score"] >= 80
                      else "warn" if r["score"] >= args.min_score else "danger")
        print("  %s  %s" % (r["name"].ljust(width),
                            out.role("%d/100" % r["score"], score_role)))
        for e in r["errors"]:
            print("    " + out.role("error: " + e, "danger"))
        for n in r["notes"]:
            print("    " + out.role(n, "muted"))
    _print_skipped(skipped)
    if failed:
        out.warn("%d of %d skill%s below %d or with errors"
                 % (len(failed), len(results), _s(len(results)), args.min_score))
        return 1
    out.ok("%d skill%s %s lint (min %d)"
           % (len(results), _s(len(results)),
              "passes" if len(results) == 1 else "pass", args.min_score))
    return 0


def _drift_label(row: dict) -> str:
    """A drift row's NAME cell: the kind for a rule/workflow, the scope for a
    project-lock skill (which can share its name with a user-scope one)."""
    if row["kind"] != "skill":
        return "%s (%s)" % (row["name"], row["kind"])
    if row["scope"] == scopes.SCOPE_PROJECT:
        return "%s (project)" % row["name"]
    return row["name"]


def cmd_drift(argv):
    ap = cliparse.parser(
        prog="boost drift",
        description="Detect installed skills diverging from source")
    ap.add_argument("names", nargs="*", metavar="NAME",
                    help="installed skill, rule or workflow (default: all)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    # Same rule as `boost verify`: a missing/corrupt/wrong-schema lock over a
    # populated store is a fault, not "no skills installed".
    _require_lock_integrity()

    rows = []
    names = [store.installed_name(n) for n in args.names]
    # Skills installed `--local` live in the repo's own lock, the rows
    # `verify` and `doctor` already grade; a name only that lock holds is
    # resolved there instead of answered "not installed".
    pbase, pskills = integrity.project_skills()
    user_names = [n for n in names if lockfile.find_any(n) is not None]
    unknown = [n for n in names if n not in user_names and n not in pskills]
    if unknown:
        _iter_installed_all(unknown)   # raises the usual "not installed"
    for kind, name, entry in _iter_installed_all(
            user_names if names else None):
        status = (_drift_status(name, entry) if kind == "skill"
                  else _drift_status_materialized(kind, name, entry))
        # A copy that matches its source is still not what an agent runs when
        # the agent's link leads to another skill's copy (`store.misdirected`).
        # Content drift outranks it: its remedy is the one to take first.
        if (kind == "skill" and status in ("in-sync", staleness.NA)
                and store.misdirected_links(name)):
            status = "misdirected-link"
        # A rule or workflow installed `--local` is recorded in the user lock
        # with its own `scope`, which is the one to report (as verify does).
        scope = (entry.get("scope") or scopes.SCOPE_USER) if kind != "skill" \
            else scopes.SCOPE_USER
        # A skill's local edit may be a deleted SKILL.md, which heal (not a
        # reinstall) is the repair for — the split doctor and verify name.
        hint = (" ".join(integrity.modified_remedy(name))
                if kind == "skill" and status == "local-edits"
                else _drift_hint(name, status, entry.get("tap", ""),
                                 str(entry.get("tap_url") or "")))
        rows.append({"name": name, "kind": kind, "scope": scope,
                     "status": status, "hint": hint})
    for name, entry in sorted(pskills.items()):
        if pbase is None or (names and name not in names):
            continue
        status = _drift_status_project(name, entry, pbase)
        # A missing project copy is re-materialized by `boost sync`
        # (`store.project_sync_plan`), not by heal's user-store repair.
        hint = ("boost sync" if status == staleness.STORE_MISSING
                else _drift_hint(name, status, entry.get("tap", ""),
                                 str(entry.get("tap_url") or ""),
                                 scope=scopes.SCOPE_PROJECT))
        rows.append({"name": name, "kind": "skill",
                     "scope": scopes.SCOPE_PROJECT, "status": status,
                     "hint": hint})
    if args.json:
        print(json.dumps({"skills": rows}))
        return 0
    if not rows:
        print(out.empty_state("no skills installed",
                              hint="boost install <skill> to start"))
        return 0
    out.table([(_drift_label(r),
                out.role(r["status"], _DRIFT_ROLE[r["status"]]),
                out.role(r["hint"], "muted")) for r in rows],
              # HINT is a command to paste, and an untapped source's carries
              # a whole path or URL: clipped, it is a command that fails.
              headers=("NAME", "STATUS", "HINT"), whole=("NAME",),
              keep=("HINT",))
    counts: dict = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    out.info(" · ".join("%d %s" % (n, s) for s, n in sorted(counts.items())))
    return 0


def cmd_test(argv):
    ap = cliparse.parser(
        prog="boost test",
        description="Validate installed skills against quality checks "
                    "(exits 1 when any skill fails)")
    ap.add_argument("names", nargs="*", metavar="NAME",
                    help="installed skill (default: all)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    rows, failed_count = [], 0
    # The failed-check names, uncoloured. `rows` holds them wrapped in role()
    # escapes for the table, which is display, not data — a consumer parsing
    # those would be parsing our palette.
    results: list[dict] = []
    names = [store.installed_name(n) for n in args.names]
    for row in _iter_installed_rows(names or None):
        name, entry, sdir = row.name, row.entry, row_dir(row)
        md = sdir / "SKILL.md"
        meta, body = _read_skill(sdir)
        failed = []
        if not (md.exists() and meta.get("name")):
            failed.append("parses")
        score, _notes = util.score_skill(sdir)
        if util.lint_failed(sdir, score, min_score=40):
            failed.append("lint")
        if not sdir.is_dir() or (not integrity.self_sourced(name, entry)
                                 and util.sha256_dir(sdir) != entry.get("sha256")):
            failed.append("verify")
        if len(body.encode("utf-8")) > 64 * 1024:
            failed.append("size")
        if not md.exists():
            failed.append("layout")
        if failed:
            failed_count += 1
        results.append({"name": name, "ok": not failed, "failed": failed})
        rows.append((name,
                     out.role("FAIL", "danger") if failed else out.role("PASS", "success"),
                     out.role(", ".join(failed), "muted")))
    if args.json:
        # Emitted even when nothing is installed: an empty `skills` list is the
        # answer to "what failed", and a CI gate that got no output at all
        # could not tell that from a crash.
        print(json.dumps({"skills": results,
                          "passed": len(results) - failed_count,
                          "failed": failed_count,
                          "ok": not failed_count}, indent=2))
        return 1 if failed_count else 0
    if not rows:
        print(out.empty_state("no skills installed",
                              hint="boost install <skill> to start"))
        return 0
    out.table(rows, headers=("SKILL", "RESULT", "FAILED CHECKS"),
              whole=("SKILL",))
    out.info("%d passed, %d failed" % (len(rows) - failed_count, failed_count))
    return 1 if failed_count else 0


def cmd_fingerprint(argv):
    ap = cliparse.parser(
        prog="boost fingerprint",
        description="Deterministic hash of the skill environment")
    ap.add_argument("--verbose", action="store_true",
                    help="show the hashed components")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    digest, comps, incomplete = _fingerprint()
    if args.json:
        print(json.dumps({"fingerprint": digest, "short": digest[:16],
                          "components": comps, "incomplete": incomplete}))
        return 0
    out.heading("environment fingerprint")
    print("  " + out.role(digest[:16], "accent", bold=True)
          + "  " + out.role(digest, "muted"))
    if args.verbose:
        # A sha256 clipped to 38 chars cannot be compared by eye, which is
        # the only reason --verbose lists the components at all.
        out.table([tuple(line.split(":", 1)) for line in comps],
                  headers=("COMPONENT", "DIGEST/COMMIT"),
                  keep=("DIGEST/COMMIT",))
    for name in incomplete:
        out.warn("tap %s not cloned — fingerprint incomplete (boost update)"
                 % name, stream=sys.stderr)
    return 0


def cmd_decay(argv):
    ap = cliparse.parser(
        prog="boost decay",
        description="Flag skills irrelevant to your current stack")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    rows = _decay_rows(scopes.project_dir())
    if args.json:
        print(json.dumps({"skills": rows}))
        return 0
    if not rows:
        print(out.empty_state("no skills installed",
                              hint="boost install <skill> to start"))
        return 0
    rel_role = {"none": "danger", "low": "warn", "ok": "success"}
    verdicts = {"decay": out.role("decay candidate", "danger"),
                "review": out.role("review", "warn"),
                "ok": out.role("ok", "success")}
    out.table([(r["name"], out.role(r["relevance"], rel_role[r["relevance"]]),
                util.rel_time(r["last_activity"]) if r["last_activity"] else "never",
                verdicts[r["verdict"]]) for r in rows],
              headers=("SKILL", "RELEVANCE", "LAST ACTIVITY", "VERDICT"),
              whole=("SKILL",))  # `boost uninstall <name>`
    n_decay = sum(1 for r in rows if r["verdict"] == "decay")
    n_review = sum(1 for r in rows if r["verdict"] == "review")
    out.info("%d decay candidate%s · %d to review · %d ok"
             % (n_decay, _s(n_decay), n_review,
                len(rows) - n_decay - n_review))
    if n_decay:
        print(out.role("  isolate one with `boost quarantine <name>`", "muted"))
    return 0


def _as_skill_note(names: list[str]) -> str:
    """The doctor/heal line for workflows installed without a skill copy."""
    n = len(names)
    shown = ", ".join(names[:_MAT_NOTE_SHOWN]) + (
        " and %d more" % (n - _MAT_NOTE_SHOWN) if n > _MAT_NOTE_SHOWN else "")
    return ("%d workflow%s not reachable as skill%s (%s) — `boost heal "
            "--as-skill` puts %s in the skill store"
            % (n, _s(n), _s(n), shown, "it" if n == 1 else "them"))


def cmd_heal(argv):
    ap = cliparse.parser(
        prog="boost heal",
        description="Self-diagnose & repair the boost environment")
    ap.add_argument("--dry-run", action="store_true",
                    help="show repairs without applying them")
    ap.add_argument("--prune-duplicates", action="store_true",
                    help="remove the duplicate-discovery symlinks `boost doctor` "
                         "reports (an agent that collapses them silently is "
                         "never reported, so never pruned)")
    ap.add_argument("--as-skill", action="store_true",
                    help="give installed workflows their copy in the skill "
                         "store, for agents that read only skills")
    args = ap.parse_args(argv)
    dry = args.dry_run
    actions: list[str] = []

    # linking_agents, not enabled_agents: a native-store agent's skills dir is
    # never written to, so it is not a missing directory.
    wanted = [*paths.boost_dirs(), *agents.linking_agents().values()]
    # ``os.path.isdir``: ``Path.is_dir`` raises under a dir with no search bit
    # on Python 3.12 and 3.13, where this exited 70. Such a dir is "missing"
    # here, and `refuses_writes` below names the parent that hides it.
    missing = [d for d in wanted if not os.path.isdir(d)]  # noqa: FURB146
    # A missing dir whose parent refuses the mkdir is not one heal can create,
    # so the preview does not promise it: it used to say "would create" and
    # exit 0 for a run that crashed at exit 70. Both name it below instead.
    blocked = {d: b for d in missing if (b := paths.refuses_writes(d))}
    creatable = [d for d in missing if d not in blocked]
    if creatable:
        if dry:
            # Named, like every other repair heal previews: a bare count was
            # the one line that never said which paths get written — on a
            # fresh HOME, `~/.agents/skills` and each agent's skills dir.
            for d in creatable:
                out.info("would create directory %s" % _tilde(d))
        else:
            for d in paths.create_dirs(creatable):
                blocked[d] = paths.refuses_writes(d) or d
            made = len(creatable) - sum(d in blocked for d in creatable)
            if made:
                out.ok("created %d missing director%s"
                       % (made, "y" if made == 1 else "ies"))
        actions.append("mkdir %d" % len(creatable))

    ours, theirs = _broken_links()
    for link in ours:
        if dry:
            out.info("would remove broken link %s" % _tilde(link))
        else:
            link.unlink()
            out.ok("removed broken link %s" % out.plain(_tilde(link)))
        actions.append("unlink %s" % link.name)
    plan = store.sync_plan()
    # One where a recorded skill's link goes is named below, as a link it
    # blocks, with what to do about it; saying it twice read as two problems.
    blocking = {Path(p) for _n, _a, p in plan["blocked_links"]}
    for link in theirs:
        if link in blocking:
            continue
        # Named, never touched: it is in a directory boost writes to, so the
        # user should know it is dangling — but boost did not put it there.
        out.warn("broken link %s does not point into %s — left alone"
                 % (_tilde(link), _tilde(paths.store_dir())))
    # Asked before `sync_apply`, which writes a lock where there was none.
    integ = lockfile.check()
    if dry:
        # `ours` above is exactly what a real run unlinks before computing
        # this plan, so `sync_plan`'s stale-link sweep never sees those paths
        # on a real run — only here, where nothing was unlinked yet. Skip
        # them so a preview doesn't report the same path twice under two
        # different actions.
        already_reported = {str(link) for link in ours}
        linking = agents.linking_agents()
        for name, agent in plan["missing_links"]:
            # A dir that refuses writes is skipped by the run, which names it
            # below; promising the link here was a preview the run broke.
            adir = linking.get(agent)
            if adir is not None and paths.refuses_writes(adir) is not None:
                continue
            out.info("would link %s → %s" % (name, agent))
            actions.append("link %s" % name)
        for p in plan["stale_links"]:
            if p in already_reported:
                continue
            out.info("would remove stale link %s" % _tilde(p))
            actions.append("stale %s" % p)
        # The branch `sync_apply` will take, worded by the same planner it
        # uses: this said "would restore X from its tap (or drop it from the
        # lock)" where the live run reinstalls, and previewed no rule or
        # workflow repair at all.
        for msg in store.sync_preview(plan):
            (out.warn if store.is_unrepaired(msg) else out.info)(
                msg.replace(str(paths.home()), "~"))
            actions.append(msg)
    else:
        for msg in store.sync_apply(plan):
            (out.warn if store.is_unrepaired(msg) else out.ok)(
                msg.replace(str(paths.home()), "~"))
            actions.append(msg)
    # A project skill's agent copy deleted from the repo: doctor and verify
    # report it, so heal repairs it the way `boost sync` does -- only the
    # missing agents, never re-copying over a teammate's edit in the others.
    pplan = store.project_sync_plan()
    if dry:
        # Worded by the same source check the run uses, so a copy whose tap
        # is gone is warned about here rather than promised.
        for msg in store.project_sync_preview(pplan):
            (out.warn if store.is_unrepaired(msg) else out.info)(msg)
            actions.append(msg)
    else:
        for msg in store.project_sync_apply({"missing": pplan["missing"]}):
            (out.warn if store.is_unrepaired(msg) else out.ok)(msg)
            actions.append(msg)
    # A repair heal will not make (a pin over a moved source, a URL import it
    # cannot re-clone) fails the run like any other thing it left: exiting 0
    # over a skill still missing is what kept doctor and heal in a loop.
    unrepaired = any(store.is_unrepaired(a) for a in actions)

    # Opt-in, unlike everything above it. The rest of `heal` repairs what boost
    # itself created; these entries boost did not create, so deleting one on a
    # plain `boost heal` would be silently removing another tool's file. Named
    # every run so the flag is discoverable from the command that would use it.
    # Named, never acted on: deleting another tool's copy, or dropping a link
    # Claude Code also gets from a plugin, changes what an agent can run. Both
    # wait for `boost sync --prune`, whose confirm says what each costs.
    for line in store.older_copy_lines(plan["older_copies"]):
        out.info(line, wrap=True)
    for line in (store.foreign_store_lines(plan["foreign_store"])
                 + store.plugin_duplicate_lines(plan["plugin_duplicates"])
                 + store.plugin_variant_lines(plan["plugin_duplicates"])):
        out.info(line, wrap=True)
    # Left alone by design, and named as `sync` names them, so a dir that is
    # not a skill is not silently skipped by the command meant to look.
    if plan["not_skill_store"]:
        out.info(store.not_skill_line(plan["not_skill_store"]), wrap=True)
    if plan["misnamed_store"]:
        out.info(out.plain(store.misnamed_line(plan["misnamed_store"])),
                 wrap=True)
    declined_copies = bool(plan["foreign_store"]) or any(
        store.plugin_serves(r[3]) for r in plan["plugin_duplicates"])

    # Opt-in like --prune-duplicates, though it removes nothing: it writes into
    # the skill store, which a plain heal only ever repairs.
    if args.as_skill:
        if not config.get("workflows_as_skills", True):
            out.info("workflows_as_skills is off, so no workflow gets a skill "
                     "copy — `boost config set workflows_as_skills true` "
                     "turns it on", wrap=True)
        for line in store.backfill_skill_copies(dry=dry):
            if dry or line.startswith("workflow "):
                out.info(line, wrap=True)
            else:
                out.ok(line)
            actions.append(line)
    else:
        unreached = store.workflows_without_skill_copy()
        if unreached:
            out.info(_as_skill_note(unreached), wrap=True)

    duplicates = store.duplicate_discovery()
    declined_duplicates = bool(duplicates) and not args.prune_duplicates
    for dup in duplicates:
        label = "%s → %s (%s)" % (_tilde(dup.path), _tilde(dup.target), dup.agent)
        if not args.prune_duplicates:
            out.info("duplicate skill discovery %s — %s reads the store "
                     "natively; remove it with `boost heal --prune-duplicates`"
                     % (label, agents.display_name(dup.agent)), wrap=True)
        elif dry:
            out.info("would remove duplicate skill discovery %s" % label)
            actions.append("duplicate %s" % dup.path)
        elif store.remove_duplicate_discovery(dup):
            out.ok("removed duplicate skill discovery %s" % label)
            actions.append("duplicate %s" % dup.path)
        else:
            # Re-gated at the point of deletion, so a real directory or a link
            # repointed since the scan lands here rather than being removed.
            out.warn("%s is no longer a symlink into the store — left alone"
                     % _tilde(dup.path))

    # A ★ the catalogue no longer gives. Cleared before the cache loop below,
    # which rebuilds a cache whose stamped ★ no longer matches: the flag is
    # stamped onto each entry at scan time, so flipping config alone would
    # leave browse and the curated fallback reading the old star. One line, not one per tap — a
    # catalogue machine has ~420 of them.
    stars = registry.overstarred()
    if stars:
        shown = ", ".join(stars[:3]) + (", …" if len(stars) > 3 else "")
        if dry:
            out.info("would clear the ★ on %d tap%s the catalogue does not "
                     "curate (%s)" % (len(stars), _s(len(stars)), shown),
                     wrap=True)
            actions.append("unstar %d" % len(stars))
        else:
            cleared = registry.unstar(stars)
            out.ok("cleared the ★ on %d tap%s the catalogue does not curate "
                   "(%s)" % (len(cleared), _s(len(cleared)), shown))
            actions.append("unstar %d" % len(cleared))

    # A dir that refuses writes, or a missing one whose parent refuses the
    # mkdir. A missing one heal CAN create is not stuck: the real run creates
    # it above, so a preview that called it unwritable would exit 1 where the
    # run it previews exits 0.
    cache_dir = paths.cache_dir()
    cache_stuck = paths.refuses_writes(cache_dir) is not None
    broken_taps = []
    # Without git no clone's HEAD can be read, so no cache can be judged
    # fresh or stale: this used to end heal at the first tap with "git is
    # required", after it had already created directories. Said once, and
    # never under an all-clear — doctor counts it as an issue too.
    no_git = not gitutil.has_git()
    if no_git:
        out.warn("git not found on PATH — heal cannot check tap catalogs "
                 "against their clones; install git, then rerun `boost heal`",
                 wrap=True)
    for tap in registry.list_taps():
        if not tap.is_cloned:
            out.warn("tap %s not cloned — skipped (run `boost update`)" % tap.name)
            continue
        if tap.is_broken_clone:
            # Not rebuilt: a catalog of a tree git no longer tracks would
            # certify it. Re-cloning is `update`'s job (network), so heal
            # names it and does not answer "nothing to heal" beneath it.
            broken_taps.append(tap.path)
            out.warn(registry.broken_clone_line(tap.name), wrap=True)
            continue
        if no_git:
            continue
        had_cache = tap.cache_file.exists()
        # One HEAD for both freshness questions below, before and after.
        head = gitutil.head_commit(tap.path)
        fresh = had_cache and catalog.cache_is_fresh(tap, head=head)
        if dry:
            # A cache scanned at another commit is rebuilt by the real run,
            # so the preview names it too; an unresolvable HEAD never reads
            # fresh, and the run claims nothing for it, so neither does this.
            if not fresh and not cache_stuck and (head or not had_cache):
                out.info("would rebuild catalog cache for %s" % tap.name)
                actions.append("cache %s" % tap.name)
        elif not fresh:
            # Only a missing, unreadable or stale cache (older CACHE_FORMAT,
            # or scanned at another commit) — what the dry run promises. An
            # unconditional rescan made "nothing to heal" cost a full scan of
            # every tap and, by bumping each cache mtime, the next search a
            # BM25 index rebuild.
            catalog.rebuild_tap(tap)
            # rebuild_tap survives a cache it cannot write and warns; claiming
            # the rebuild under that warning would certify a file that is
            # still missing, and every later run would claim it again.
            # Fresh *now* is the test for a stale cache that was replaced:
            # its old file still exists when the write failed.
            if tap.cache_file.exists() and (
                    not had_cache or catalog.cache_is_fresh(tap, head=head)):
                out.ok("rebuilt catalog cache for %s" % tap.name)
                actions.append("cache %s" % tap.name)

    if not dry:
        complete.refresh_names()

    if not journal.rotation_healthy():
        if dry:
            out.info("would rotate the journal")
        else:
            out.ok("journal rotation scheduled (next write rotates)")
        actions.append("rotate")

    # Not repairable from here — the tap list is the user's, not derivable —
    # and never covered by an all-clear: with it unreadable, every check
    # above ran against DEFAULTS.
    cfg_err = config.check()
    if cfg_err:
        out.warn("%s — heal cannot repair it: boost is running on defaults "
                 "until the file is fixed or your taps are re-added"
                 % cfg_err, wrap=True)
    # Permissions are the user's to change, not heal's; but a dir heal saw and
    # cannot fix must not sit under an all-clear.
    # A block `blocked` already names for a missing dir is not named twice:
    # both now come from `refuses_writes`.
    stuck = [d for d in store.unwritable_agent_dirs()
             if d not in blocked.values()]
    for adir in stuck:
        out.warn("agent dir %s — heal does not change permissions; run %s, "
                 "then `boost sync`" % store.unwritable_refusal(str(adir)),
                 wrap=True)
    stuck.extend(broken_taps)
    # The same rule for the cache dir doctor flags, and for any directory a
    # refused mkdir left missing: heal cannot make the parent writable, so it
    # must not answer "nothing to heal" beneath the problem. The preview and
    # the run print the same line, naming the directory that refuses.
    # setdefault: a missing cache dir is already in `blocked`, named once.
    if registry.list_taps() and cache_stuck:
        blocked.setdefault(cache_dir,
                           paths.refuses_writes(cache_dir) or cache_dir)
    # The store doctor flags: it exists, so it is never `missing` above.
    store_block = paths.refuses_writes(paths.store_dir())
    if store_block is not None and store_block not in blocked.values():
        blocked.setdefault(paths.store_dir(), store_block)
    # A file or a dangling link where a recorded rule's or workflow's dir
    # belongs. A block already named for a skills dir is named once.
    for d, block in store.blocked_agent_dirs():
        if block not in blocked.values():
            blocked.setdefault(d, block)
    for path in store.occupied_targets():
        stuck.append(path)
        out.warn("%s, then `boost sync` (heal does not move files)"
                 % store.occupied_refusal(path), wrap=True)
    # A real file or dir where a skill's link goes. Neither heal nor sync
    # deletes what boost did not put there, so "nothing to heal" above it was
    # an all-clear for a link that is still missing. A block a whole agent
    # dir is behind is named once, below.
    linking = agents.linking_agents()
    for name, agent, path in plan["blocked_links"]:
        if agent in linking and Path(path) == linking[agent] / name:
            stuck.append(Path(path))
            out.warn("%s not linked for %s: %s is in the way and is not "
                     "boost's — move or delete it, then `boost sync` (heal "
                     "does not move files)" % (name, agent, _tilde(path)),
                     wrap=True)
    # A store dir boost cannot read is not recorded, so heal saw it and left
    # it: an all-clear under it would be the loop the preview used to start.
    if plan["unreadable_store"]:
        stuck.extend(Path(where) for _name, where in plan["unreadable_store"])
        out.warn(store.unreadable_line(plan["unreadable_store"]), wrap=True)
    # A workflow's skill copy the lock lost. Not heal's to re-record — which
    # tap the workflow came from is in the lock that is gone — and never
    # adopted as a skill; named, and heal does not exit 0 over it.
    if plan["workflow_copies"]:
        stuck.extend(store.skill_store_dir(n) for n, _wf in plan["workflow_copies"])
        for line in store.workflow_copy_lines(plan["workflow_copies"]):
            out.warn(line, wrap=True)
    # A rule's block the lock lost: the same, in the file it sits in.
    if plan["rule_blocks"]:
        stuck.extend(Path(p) for _n, p in plan["rule_blocks"])
        for line in store.rule_block_lines(plan["rule_blocks"]):
            out.warn(line, wrap=True)
    # A lock that cannot be read is `boost replay`'s to restore. heal answered
    # "nothing to heal" over it, with every store dir it could not record.
    if not integ.ok and integ.problem != "missing":
        stuck.append(paths.lockfile_path())
        out.warn("the lock file %s, so heal cannot tell which store dirs are "
                 "boost's — %s" % (lockfile.fault(integ), lockfile.remedy(integ)),
                 wrap=True)
    for d, block in blocked.items():
        stuck.append(d)
        out.warn("%s — heal does not %s; %s"
                 % (paths.not_writable(d, block),
                    "move files" if paths.in_the_way(block)
                    else "change permissions",
                    paths.write_remedy(block)), wrap=True)
    # A link outside a declared `--agent` scope works and is in use, so heal
    # leaves it to `sync --prune` as sync does — but names it, because doctor
    # does, and a bare "nothing to heal" under doctor's warning contradicted it.
    oos = plan["out_of_scope_links"]
    if oos:
        out.warn("%d link%s outside the declared scope: %s — remove with "
                 "`boost sync --prune`"
                 % (len(oos), _s(len(oos)),
                    ", ".join("%s → %s" % (n, a) for n, a in oos)), wrap=True)
    if not actions and not stuck and not cfg_err and not no_git:
        # A duplicate this run declined to prune is something `heal` saw, can
        # fix, and deliberately left. A bare "nothing to heal" printed under
        # the line offering the flag contradicts it.
        out.ok("nothing to heal automatically"
               if declined_duplicates or declined_copies or oos
               else "nothing to heal")
    if actions and not dry:
        journal.log("heal", "%d actions" % len(actions))
    return 1 if cfg_err or stuck or unrepaired or no_git else 0


def cmd_conflict(argv):
    ap = cliparse.parser(
        prog="boost conflict",
        description="Detect contradictory rules between skills "
                    "(exits 1 when any conflict is found)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    # Quarantine removes a skill's active links/materialization on purpose
    # (see _drift_status_materialized's docstring) — a quarantined skill has
    # nothing live to be contradicted by, so it is excluded from both sides
    # of conflict detection rather than surfacing a conflict finding no
    # `boost quarantine` can ever clear.
    # Both scopes: a skill installed `--local` is loaded beside the user's
    # own, so it can contradict one — read from the repo's copy.
    installed = [r for r in _iter_installed_rows()
                 if not r.entry.get("quarantined")]
    rules: list[tuple[str, str, str, set]] = []   # skill, line, polarity, stems
    declared: list[tuple[str, str]] = []           # skill, conflicting skill
    installed_names = {r.name for r in installed}
    for row in installed:
        name = row.name
        meta, body = _read_skill(row_dir(row))
        conflicts = meta.get("conflicts") or []
        declared.extend(
            (name, str(other))
            for other in (conflicts if isinstance(conflicts, list) else [conflicts])
            if str(other) in installed_names and str(other) != name
        )
        for raw in body.splitlines():
            m = imperative.RULE_RE.match(raw)
            if not m:
                continue
            modal = re.sub(r"\s+", " ", m.group(1).lower())
            polarity = "neg" if modal in _NEG_MODALS else "pos"
            toks = [_norm_token(t) for t in re.findall(r"[a-z0-9']+",
                                                       m.group(2).lower())]
            if any(t in _NEGATORS for t in toks):
                polarity = "neg" if polarity == "pos" else "pos"
            stem = {t for t in toks
                    if t and t not in _STOPWORDS and t not in _NEGATORS}
            if stem:
                rules.append((name, raw.strip(), polarity, stem))

    pairs: list[dict[str, str]] = []
    seen: set = set()   # holds both key shapes below, declared and heuristic
    for da, db in declared:
        # Two different key SHAPES share `seen` — a flat triple here, a pair of
        # (skill, line) pairs below. Distinct names because reusing one made the
        # second `sorted()` type-check against the first one's element type.
        dkey = (*tuple(sorted((da, db))), "declared")
        if dkey in seen:
            continue
        seen.add(dkey)
        pairs.append({"kind": "declared", "a": da, "b": db,
                      "a_line": "frontmatter declares conflicts: %s" % db,
                      "b_line": ""})
    for a_skill, a_line, a_pol, a_stem in rules:
        for b_skill, b_line, b_pol, b_stem in rules:
            if a_skill == b_skill or not (a_pol == "pos" and b_pol == "neg"):
                continue
            small = min(len(a_stem), len(b_stem))
            if small and len(a_stem & b_stem) / small >= _CONFLICT_OVERLAP:
                hkey = tuple(sorted(((a_skill, a_line), (b_skill, b_line))))
                if hkey in seen:
                    continue
                seen.add(hkey)
                pairs.append({"kind": "heuristic", "a": a_skill, "b": b_skill,
                              "a_line": a_line, "b_line": b_line})

    heuristic = [p for p in pairs if p["kind"] == "heuristic"]
    if heuristic and ai.available():
        listing = "\n".join("%d. %s: %r  vs  %s: %r"
                            % (i, p["a"], p["a_line"], p["b"], p["b_line"])
                            for i, p in enumerate(heuristic, 1))
        reply = ai.ask(
            "These pairs of coding-skill rules were flagged as possibly "
            "contradictory:\n%s\nWhich numbered pairs are genuine "
            "contradictions? Reply with the numbers only, comma-separated, "
            "or 'none'." % listing, max_tokens=100)
        if reply:
            confirmed = {int(x) for x in re.findall(r"\d+", reply)}
            for i, p in enumerate(heuristic, 1):
                if i in confirmed:
                    p["kind"] = "ai-confirmed"
        elif not args.json:
            # The backend was available but the call itself produced nothing —
            # distinct from "no backend at all", so it gets the same
            # attributed note rather than leaving the pairs silently
            # unconfirmed.
            out.warn(ai.fallback_note(), wrap=True)
    elif heuristic and not args.json:
        out.warn(ai.fallback_note(), wrap=True)

    if args.json:
        print(json.dumps({"pairs": pairs}))
        return 1 if pairs else 0
    if not pairs:
        out.ok("no contradictory rules across %d skill%s"
               % (len(installed), _s(len(installed))))
        return 0
    out.heading("rule conflicts")
    for p in pairs:
        out.warn("%s ↔ %s  (%s)" % (p["a"], p["b"], p["kind"]))
        print("      " + out.role("%s: %s" % (p["a"], p["a_line"]), "muted"))
        if p["b_line"]:
            print("      " + out.role("%s: %s" % (p["b"], p["b_line"]), "muted"))
    out.info("%d conflict pair%s found" % (len(pairs), _s(len(pairs))))
    return 1


def cmd_changelog(argv):
    ap = cliparse.parser(
        prog="boost changelog",
        description="Show an item's upstream change history")
    ap.add_argument("name", metavar="NAME",
                    help="skill, rule or workflow, installed or in a tap")
    ap.add_argument("-n", type=util.positive_int, default=20, metavar="N",
                    help="number of entries (default 20)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    # Lock first, all three kinds. A rule or workflow is logged over its own
    # file, not the directory it shares with its siblings.
    bare, _kind, tap_name, rel = store.upstream_source(args.name)
    if tap_name == "local":
        if args.json:
            print(json.dumps({"name": bare, "tap": None, "commits": []},
                             indent=2))
            return 0
        out.info("no upstream history — %s was imported locally" % bare)
        return 0
    tap = registry.get(tap_name)
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    if args.json:
        # `log_entries` parses on an ASCII unit separator rather than
        # re-splitting the display format, whose two-space column gap a commit
        # subject or an author name may itself contain.
        print(json.dumps(
            {"name": bare, "tap": tap.name,
             "commits": gitutil.log_entries(tap.path, rel, args.n)}, indent=2))
        return 0
    lines = gitutil.log_for_path(tap.path, rel, args.n)
    out.heading("changelog for %s (%s)" % (bare, tap.name))
    for line in lines:
        out.info(line)
    if not lines:
        out.warn("no history found for %s in %s" % (rel, tap.name))
    # Fewer entries than -n asked for means git ran out of history. On a
    # shallow clone that end may be the cut, not the first commit, however
    # far the clone was deepened. A short log alone proves nothing: a
    # local-path tap is complete, and there `fetch --unshallow` fails.
    if len(lines) < args.n and gitutil.is_shallow(tap.path):
        note = ("(shallow clone: run `git -C %s fetch --unshallow` "
                "for full history)" % _tilde(tap.path))
        for line in out.wrap(note, max(out.term_width() - 2, 20)):
            print(out.role("  " + line, "muted"))
    return 0


def cmd_health(argv):
    ap = cliparse.parser(
        prog="boost health", description="Dashboard of skill-environment health")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    data: dict = {}

    def kv(key, display, value=None):
        """Record a dashboard row, and print it unless we are emitting JSON.

        `value` carries the structured form where the displayed one is
        decorated — the agent coverage rows embed a role() escape, and a
        consumer parsing those would be parsing our palette.
        """
        data[key] = display if value is None else value
        if not args.json:
            out.kv(key, display)

    # Skills-only used to be the whole dashboard, so a rule or workflow could
    # drift — or vanish from the store entirely — invisibly: the skills line
    # and the drift row below both only ever saw `_iter_installed()`. Walking
    # every kind here is what lets the drift row match `boost drift` on the
    # same lock file instead of silently under-reporting it.
    all_installed = _iter_installed_all()
    by_kind: dict[str, list[tuple[str, dict]]] = {}
    for kind, name, entry in all_installed:
        by_kind.setdefault(kind, []).append((name, entry))
    installed = by_kind.get("skill", [])
    # The skills line counts what `boost list` shows, the current project's
    # `--local` installs included; the rows below stay user-scope.
    skill_items = installed.copy() + [
        (n, e) for n, e in integrity.project_skills()[1].items()]
    taps = registry.list_taps()
    cloned = [t for t in taps if t.is_cloned]

    if not args.json:
        out.heading("boost health")
    for kind, label in (("skill", "skills"), ("rule", "rules"),
                        ("workflow", "workflows")):
        items = skill_items if kind == "skill" else by_kind.get(kind, [])
        q = sum(1 for _n, e in items if e.get("quarantined"))
        p = sum(1 for _n, e in items if e.get("pinned"))
        kv(label, "%d installed · %d quarantined · %d pinned"
           % (len(items), q, p),
           {"installed": len(items), "quarantined": q, "pinned": p})
    kv("taps", "%d configured · %d cloned" % (len(taps), len(cloned)),
       {"configured": len(taps), "cloned": len(cloned)})

    expected = [(n, e) for n, e in installed if not e.get("quarantined")]
    linking = agents.linking_agents()
    # A skill an enabled plugin ships with the same files reaches Claude Code
    # without a link, and boost makes none (`store.left_to_plugin`): it counts
    # as there, or `sync --prune` would leave this row amber for good.
    covered = store.covered_skills(store.plugin_coverage(dict(installed)))
    coverage_ok = True
    for agent, adir in linking.items():
        # Over the skills whose scope takes the agent in, as `boost sync`
        # counts them: one installed `--agent cursor`, or recorded by sync
        # with the links it found, is not missing from the others.
        due = [n for n, e in expected if agent in store.scoped_agents(e, linking)]
        linked = sum(1 for n in due
                     if (os.path.islink(adir / n) and os.path.exists(adir / n)  # noqa: FURB141, FURB146
                         and store.misdirected(n, adir / n) is None)
                     or store.left_to_plugin(n, agent, adir / n, covered))
        full = linked == len(due)
        coverage_ok = coverage_ok and full
        kv(agent, "%d/%d %s" % (linked, len(due),
                                out.role("✓", "success") if full
                                else out.role("!", "warn")),
           {"linked": linked, "expected": len(due), "ok": full})
    # Agents that read the canonical store have no links to count, so they
    # used to be scored an unconditional len(expected)/len(expected) — green
    # even with a skill's store directory gone, in the same report `drift`
    # called store-missing. Stat the store instead. They are listed even when
    # full, because an agent silently absent from a health report reads as
    # "boost is not wired up for it".
    # A sidelined skill's copy is held out of the store on purpose.
    in_store = [n for n, e in expected if not store.is_held(e)]
    store_present = sum(1 for n in in_store if store.skill_store_dir(n).is_dir())
    store_full = store_present == len(in_store)
    for agent in agents.native_store_agents():
        coverage_ok = coverage_ok and store_full
        kv(agent, "%d/%d %s (reads the store directly)"
           % (store_present, len(in_store),
              out.role("✓", "success") if store_full
              else out.role("!", "warn")),
           {"linked": store_present, "expected": len(in_store),
            "ok": store_full, "native_store": True})

    drift_counts: dict = {}
    for kind, name, entry in all_installed:
        st = (_drift_status(name, entry) if kind == "skill"
              else _drift_status_materialized(kind, name, entry))
        drift_counts[st] = drift_counts.get(st, 0) + 1
    kv("drift", " · ".join("%d %s" % (n, s)
                           for s, n in sorted(drift_counts.items())) or "—",
       drift_counts)

    decay_n = sum(1 for r in _decay_rows(scopes.project_dir()) if r["verdict"] == "decay")
    kv("decay", "%d candidate%s" % (decay_n, _s(decay_n)), decay_n)

    broken, strays = _broken_links()
    kv("broken links", "%d%s" % (
        len(broken), " (+%d not ours)" % len(strays) if strays else ""),
       {"ours": len(broken), "foreign": len(strays)})

    # `registry.last_refresh_at` reads the marker `boost update` stamps, not a
    # tap clone's git log — a clone's newest commit is the *upstream's* clock,
    # unmoved by a local sync, which is what made this line read "4w ago"
    # twelve minutes after tapping every configured registry.
    refreshed_at = registry.last_refresh_at()
    last_sync = util.rel_time(refreshed_at) if refreshed_at else "never"
    kv("last tap sync", last_sync,
       # `last_refresh_at` already returns an ISO8601 string, not a datetime.
       {"relative": last_sync, "at": refreshed_at})

    week_ago = datetime.now(UTC) - timedelta(days=7)
    recent = sum(1 for e in journal.events()
                 if (_parse_ts(e.get("ts", "")) or week_ago) > week_ago)
    kv("journal (7d)", "%d event%s" % (recent, _s(recent)), recent)
    kv("fingerprint", _fingerprint()[0][:16])

    # The membership rule is "is there anything there", not "has it drifted":
    # `local-edits` and `upstream-moved` are expected states of a *live*
    # install, while these four each mean the install reaches nothing --
    # the store dir is gone, the source is gone, no agent was ever written,
    # or the repo a `--local` row was installed into has been deleted. Leaving `unreachable` out would be the bug this status was
    # added for, wearing a new word.
    attention = (bool(broken) or not coverage_ok
                 or drift_counts.get("store-missing", 0) > 0
                 or drift_counts.get("source-missing", 0) > 0
                 or drift_counts.get("unreachable", 0) > 0
                 or drift_counts.get("stranded", 0) > 0
                 or not journal.rotation_healthy())
    if args.json:
        print(json.dumps(data | {"ok": not attention,
                                 "status": "needs attention" if attention
                                 else "healthy"}, indent=2))
    elif attention:
        print("  " + out.role("● needs attention (run boost doctor)", "warn"))
    else:
        print("  " + out.role("● healthy", "success"))
    return 0


# --- trust: signing keys & tap provenance ---------------------------------

_PROVENANCE_STYLE = {
    provenance.VERIFIED: "success",
    provenance.UNTRUSTED: "warn",
    # "danger", not "err": out.role() looks the name up in output.ROLES, which
    # has no "err" key — so an invalid tap signature raised KeyError on any
    # color terminal. The suite never caught it because conftest sets NO_COLOR.
    provenance.INVALID: "danger",
    provenance.UNSIGNED: "muted",
}


def _tap_provenance_rows():
    """(tap_name, Result) for every cloned tap, sorted by name."""
    return [(tap.name, provenance.verify_dir(tap.path))
            for tap in sorted(registry.list_taps(), key=lambda t: t.name)
            if tap.is_cloned]


def cmd_trust(argv) -> int:
    """boost trust [list|add NAME KEY|remove NAME|verify [TAP]] [--json]"""
    p = cliparse.parser(
        prog="boost trust",
        description="Manage signing keys & verify tap provenance")
    p.add_argument("action", nargs="?", default="list",
                   choices=("list", "add", "remove", "verify"),
                   help="what to do (default: list)")
    p.add_argument("name", nargs="?",
                   help="key name (add/remove) or tap name (verify)")
    p.add_argument("key", nargs="?",
                   help="with add: a minisign .pub file or its base64 line")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)

    if args.action == "list" and (args.name or args.key):
        p.error("trust list takes no NAME/KEY")
    if args.action == "remove" and args.key:
        p.error("trust remove takes no KEY")
    if args.action == "verify" and args.key:
        p.error("trust verify takes no KEY")

    if args.action == "add":
        if not args.name or not args.key:
            p.error("trust add requires NAME and KEY",
                    hint="`boost trust add acme ./acme.pub`")
        key_path = paths.expand(args.key)
        if key_path.is_file():
            key_text = key_path.read_text(encoding="utf-8")
        elif (("/" in args.key or os.sep in args.key or args.key.endswith(".pub"))
              and not provenance.parses_as_public_key(args.key)):
            # Looks like a path but isn't one — say so, rather than falling
            # through to text parsing and blaming base64 for a typo'd path.
            # '/' is in the base64 alphabet (most 56-char minisign keys hold
            # one), so a string that parses as a key is a key, not a path.
            raise BoostError("no such key file: %s" % args.key,
                             hint="it does not parse as a minisign public key "
                                  "either; pass an existing .pub file")
        else:
            key_text = args.key
        rec = provenance.add_trusted_key(args.name, key_text)
        journal.log("trust", args.name, op="add-key")
        # The fingerprint is the point of this line, not incidental detail: it
        # is how the user checks by eye that the key they just trusted is the
        # one the publisher advertises. CodeQL's py/clear-text-logging-sensitive
        # -data flags it because `name` is user-supplied and `fingerprint` reads
        # like a credential, but a minisign PUBLIC key fingerprint is meant to
        # be published — printing it is the verification, and an autofix that
        # replaced this with a constant string (dc6e827) removed the only check
        # `trust add` offers. Restored, suppressed with the reason, and pinned
        # by tests/functional/test_tap_signing.py so it cannot be quietly
        # dropped a second time.
        out.ok("trusted key %s (%s)"  # codeql[py/clear-text-logging-sensitive-data]
               % (rec["name"], rec["fingerprint"]))
        return 0

    if args.action == "remove":
        if not args.name:
            p.error("trust remove requires a NAME",
                    hint="see the names with `boost trust list`")
        if not provenance.remove_trusted_key(args.name):
            raise BoostError("no trusted key named %r" % args.name)
        journal.log("trust", args.name, op="remove-key")
        out.ok("removed trusted key %s" % args.name)
        return 0

    if args.action == "verify":
        if args.name:
            tap = registry.get(args.name)
            if not tap.is_cloned:
                raise BoostError("tap %s is not cloned" % tap.name,
                                 hint="`boost update %s`" % tap.name)
            results = [(tap.name, provenance.verify_dir(tap.path))]
        else:
            results = _tap_provenance_rows()
        if args.json:
            print(json.dumps(list(starmap(_result_json, results)), indent=2))
        else:
            _print_provenance(results)
            if args.name and results and not results[0][1].ok:
                # The named-tap form used to exit 1 on the table alone, with
                # no line saying why — the sweep form doesn't need this since
                # it only ever alarms on outright tampering.
                tap_name, r = results[0]
                out.warn("%s: not verified (%s)" % (tap_name, r.detail or r.status))
        # A specific tap must verify; a full sweep only alarms on tampering.
        if args.name:
            return 0 if results and results[0][1].ok else 1
        return 1 if any(r.status == provenance.INVALID for _n, r in results) else 0

    # list
    keys = provenance.trusted_keys()
    taps = _tap_provenance_rows()
    if args.json:
        print(json.dumps({
            "trusted_keys": [{"name": k["name"],
                              "fingerprint": k.get("fingerprint", "")}
                             for k in keys],
            "taps": list(starmap(_result_json, taps)),
        }, indent=2))
        return 0
    out.heading("trusted keys")
    if keys:
        # text=("FINGERPRINT",): an all-decimal fingerprint (~0.06% of real
        # keys) is an identifier, not a count — without this it right-aligns
        # like a numeric column.
        out.table([(k["name"], k.get("fingerprint", "?")) for k in keys],
                  headers=("NAME", "FINGERPRINT"), keep=("FINGERPRINT",),
                  text=("FINGERPRINT",),
                  # NAME is what `trust remove` takes; beside a kept
                  # fingerprint it is dropped rather than clipped.
                  whole=("NAME",))
    else:
        out.dim("  none — add one with `boost trust add <name> <key>`", wrap=True)
    print()
    _print_provenance(taps)
    return 0


def _result_json(tap_name: str, r: provenance.Result) -> dict:
    return {"tap": tap_name, "status": r.status, "key_name": r.key_name,
            "fingerprint": r.fingerprint, "trusted_comment": r.trusted_comment}


def _print_provenance(results) -> None:
    """Render a tap-provenance table (name, coloured status, key/detail)."""
    out.heading("tap provenance")
    if not results:
        out.dim("  no cloned taps")
        return
    rows = []
    for name, r in results:
        note = r.key_name or r.detail or ""
        rows.append((name, out.role(r.status, _PROVENANCE_STYLE.get(r.status, "muted")),
                     note))
    # The detail cell is the only explanation an invalid status ever gets.
    out.table(rows, headers=("TAP", "PROVENANCE", "KEY / DETAIL"),
              keep=("KEY / DETAIL",), whole=("TAP",))
