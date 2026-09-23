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
    catalog,
    claude_settings,
    complete,
    config,
    frontmatter,
    gitutil,
    imperative,
    integrity,
    journal,
    lockfile,
    logs,
    paths,
    provenance,
    registry,
    report,
    staleness,
    store,
    util,
)
from ..core import output as out
from ..errors import BoostError
from ._common import _iter_installed, _iter_installed_all, _require_lock_integrity, _s

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

    **It does not look in a native-store agent's dir.** `linking_agents`, not
    `enabled_agents`: boost never links into `~/.gemini/skills`, so anything
    dangling there belongs to someone else and is none of this command's
    business. The rest of `cmd_heal` already had this right.

    **It does not report a link boost did not create as ours.** `heal` deletes
    what this returns first, and a broken link is not necessarily garbage — a
    skill on an unmounted volume dangles until the volume comes back. Removing
    a link the user made themselves is not a repair, it is data loss with a
    reassuring name, so those are reported and left alone.
    """
    ours: list[Path] = []
    theirs: list[Path] = []
    for adir in agents.linking_agents().values():
        if not adir.is_dir():
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
    | 'store-missing' | 'n/a' (local imports with no tap source)."""
    sdir = store.skill_store_dir(name)
    store_sha = util.sha256_dir(sdir) if sdir.is_dir() else None
    is_local = entry.get("tap") == "local"
    lock_sha = entry.get("sha256", "")
    source_sha = None
    if store_sha is not None and store_sha == lock_sha and not is_local:
        try:
            src = store.source_dir_for(
                {"name": name, "tap": entry.get("tap", ""),
                 "rel_dir": entry.get("source_dir", ".")})
        except BoostError:
            source_sha = None
        else:
            source_sha = util.sha256_dir(src)
    return staleness.drift_state(store_sha, lock_sha, is_local, source_sha)


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
    st = integrity.materialized_status(name, entry)
    if st == integrity.STATUS_MISSING:
        return "store-missing"
    if st == integrity.STATUS_MODIFIED:
        return "local-edits"
    if entry.get("tap") == "local":
        return "n/a"
    try:
        raw = (registry.get(entry["tap"]).path / entry.get("source_file", "")
               ).read_text(encoding="utf-8", errors="replace")
    except (OSError, BoostError):
        return "source-missing"
    if hashlib.sha256(raw.encode("utf-8")).hexdigest() != entry.get("sha256"):
        return "upstream-moved"
    return "in-sync"


_DRIFT_ROLE = {"in-sync": "success", "local-edits": "warn",
               "upstream-moved": "accent", "source-missing": "danger",
               "store-missing": "danger", "n/a": "muted",
               "quarantined": "muted"}


def _drift_hint(name: str, status: str, tap: str = "") -> str:
    if status == "quarantined":
        return "boost quarantine --release %s to restore" % name
    if status == "upstream-moved":
        return "boost update"
    if status == "local-edits":
        return "boost reinstall %s to discard local edits" % name
    if status == "source-missing":
        # `boost update` only refreshes configured taps. When the entry's
        # tap has been untapped, that command is a guaranteed no-op — the
        # only remedy that can actually restore the source is re-tapping it.
        return "boost update" if registry.is_tapped(tap) else "boost tap %s" % tap
    if status == "store-missing":
        return "boost heal"
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
    taps = registry.list_taps()
    tap_ok = 0
    for tap in taps:
        if not tap.is_cloned:
            bad("tap", "tap %s not cloned — run `boost update`" % tap.name)
        elif not tap.cache_file.exists():
            bad("tap", "tap %s has no catalog cache — run `boost update %s`%s"
                % (tap.name, tap.name, " once %s is %s"
                   % (_tilde(cache_block), "moved aside" if cache_moved
                      else "writable") if cache_block else ""), wrap=True)
        else:
            tap_ok += 1
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
    if taps and tap_ok == len(taps):
        rep.ok("taps", "%d tap%s cloned%s" % (len(taps), _s(len(taps)),
                                              "" if cache_block
                                              else " & cached"))
    elif not taps and not cfg_err:
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
    if integ.ok:
        rep.ok("lockfile", "lock file parses (v%d)" % lockfile.SCHEMA_VERSION)
        lock_ok = True
    elif integ.problem == "missing":
        if store.has_content():
            n = sum(1 for c in paths.store_dir().iterdir()
                    if c.is_dir() and not c.name.startswith("."))
            bad("lockfile", "lock file missing — %d store dir%s unrecorded, "
                "run `boost sync` to re-record %s" % (n, _s(n), "it" if n == 1 else "them"))
            lock_ok = False
        else:
            rep.note("lockfile", "no lock file yet — nothing installed")
            lock_ok = True
    elif integ.problem == "corrupt":
        bad("lockfile", "lock file is corrupt — restore with `boost replay`")
        lock_ok = False
    else:  # "schema"
        bad("lockfile", "lock file schema is v%s, expected v%d"
            % (integ.version, lockfile.SCHEMA_VERSION))
        lock_ok = False

    skills = lockfile.installed()
    enabled = agents.enabled_agents()
    skill_issues = 0
    quarantined_skills = 0
    for name, entry in sorted(skills.items()):
        sdir = store.skill_store_dir(name)
        if not sdir.is_dir():
            fix = ("boost reinstall %s" % name if store.is_url_import(entry)
                   else "boost heal")
            bad("skill", "skill %s missing from store — run `%s`" % (name, fix))
            skill_issues += 1
            continue
        if entry.get("quarantined"):
            quarantined_skills += 1
            continue
        # tamper detection: the lock file records a sha256 at install time, but
        # only `boost verify` ever re-checked it — surface content drift here too.
        locked = entry.get("sha256")
        if locked and util.sha256_dir(sdir) != locked:
            bad("skill", "skill %s modified since install — run `boost verify`" % name)
            skill_issues += 1
        # A deliberate sideline (`focus`, `profile use`, `context apply`)
        # unlinked this skill on purpose, and `sidelined_by` says so. Without
        # this the per-agent loop below read the lock's stale `agents` list —
        # what was linked before the sideline — and reported every missing
        # link as damage, sending the reader to `boost sync`, which then
        # undid the switch they had just made.
        if entry.get("sidelined_by"):
            continue
        for agent in entry.get("agents", []):
            adir = enabled.get(agent)
            if adir is None:
                continue
            link = adir / name
            # Two different failures wore one message. `boost sync` creates a
            # link where nothing is in the way and replaces a boost-owned one
            # that dangles — but it will not delete a real file or directory
            # another installer put there, so prescribing it for that case sent
            # the reader in a circle: sync answers "everything in sync", doctor
            # repeats itself. Name the thing in the way instead.
            if link.is_symlink() and link.exists():
                continue
            if not link.is_symlink() and link.exists():
                bad("skill-link", "skill %s not linked for %s — %s exists and is not a boost "
                    "link; move or delete it, then run `boost sync`"
                    % (name, agent, paths.tilde(link)))
            else:
                bad("skill-link", "skill %s not linked for %s — run `boost sync`" % (name, agent))
            skill_issues += 1
        # The other direction. `agents` records what is linked and `only_agents`
        # what was asked for, so a link the declaration excludes is pure lock
        # arithmetic here — no second walk of the agent dirs. Doctor has to say
        # it because `boost sync` does: a "healthy" that contradicts the
        # command it tells you to run is worse than no check at all.
        scope = entry.get("only_agents")
        stray = [a for a in entry.get("agents", []) if scope and a not in scope]
        if stray:
            bad("skill-scope", "skill %s is linked for %s, outside its declared scope (%s) — "
                "run `boost sync --prune`"
                % (name, ", ".join(stray), ", ".join(scope)))
            skill_issues += 1
    active_skills = len(skills) - quarantined_skills
    if skills and not skill_issues:
        # A quarantined skill has no agent links — unlink_agents already
        # removed them — so it must not inflate this count into a false
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
    for name, entry in sorted(pskills.items()):
        st = integrity.project_status(entry, pbase)
        if st == integrity.STATUS_MISSING:
            bad("project-skill", "project skill %s is in .boost but its files are gone — "
                "run `boost sync`" % name)
            proj_issues += 1
        elif st == integrity.STATUS_MODIFIED:
            bad("project-skill", "project skill %s modified since install — "
                "run `boost verify`" % name)
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
    for kind, section in (("rule", rules), ("workflow", workflows)):
        for name, entry in sorted(section.items()):
            for m in entry.get("materializations") or []:
                if m.get("unwritable"):
                    # Refused at install, so `boost reinstall` would be refused
                    # too until the dir allows it; the agent-dir line below
                    # names the `chmod`, or the move when a file or a dangling
                    # link is in the way. Any file there predates the refusal.
                    block = paths.refuses_writes(Path(m.get("path", "")).parent)
                    if block is not None and paths.in_the_way(block):
                        why = ("%s is in the way — `boost sync` writes it once "
                               "it is moved" % _tilde(block))
                    else:
                        why = ("its dir was not writable — `boost sync` writes "
                               "it once it is")
                    bad(kind, "%s %s was not written for %s: %s"
                        % (kind, name, m.get("agent", "?"), why), wrap=True)
                    mat_issues += 1
    for name, entry in sorted(rules.items()):
        for m in entry.get("materializations") or []:
            p = Path(m.get("path", ""))
            if m.get("unwritable"):
                continue
            if m.get("mode") == "claude":
                try:
                    present = p.exists() and ("boost:rule:%s start" % name) in \
                        p.read_text(encoding="utf-8")
                except OSError:
                    present = False
            else:
                present = p.is_file()
            if not present:
                bad("rule", "rule %s missing its %s materialization — run "
                    "`boost reinstall %s`" % (name, m.get("agent", "?"), name))
                mat_issues += 1
    for name, entry in sorted(workflows.items()):
        for m in entry.get("materializations") or []:
            if not m.get("unwritable") and not Path(m.get("path", "")).is_file():
                bad("workflow", "workflow %s missing its %s file — run `boost reinstall %s`"
                    % (name, m.get("agent", "?"), name))
                mat_issues += 1
    if (all_rules or all_workflows) and not mat_issues:
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
        rep.ok("rules-workflows", "%d rule%s and %d workflow%s fully materialized%s"
               % (len(rules), _s(len(rules)), len(workflows), _s(len(workflows)),
                  note))

    root = paths.store_dir()
    orphans = [c.name for c in sorted(root.iterdir())
               if c.is_dir() and not c.name.startswith(".") and c.name not in skills
               ] if root.is_dir() else []
    # Only while the lock can vouch. Without one every store dir reads as an
    # orphan, the lock line above already names the state and its remedy, and
    # a second "run `boost sync`" line counted the same fault twice.
    if orphans and store.lock_vouches():
        bad("orphans", "%d orphaned store dir%s (%s) — run `boost sync`"
            % (len(orphans), _s(len(orphans)), ", ".join(orphans[:5])))

    broken, foreign = _broken_links()
    if broken:
        bad("broken-links", "%d broken symlink%s in agent dirs — run `boost heal`"
            % (len(broken), _s(len(broken))))
    if foreign:
        # `out.info`, not `bad`: this does not raise the issue count, because
        # boost will not fix it and `heal` deliberately leaves it — counting it
        # would leave doctor permanently red on something no boost command can
        # clear, which is how a health check stops being read.
        rep.note("foreign-links", "%d broken symlink%s in agent dirs not created by boost — "
                 "left alone; yours to remove or repair"
                 % (len(foreign), _s(len(foreign))))

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

    for dup in store.duplicate_discovery():
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
    skills_dirs = set(agents.linking_agents().values())
    for adir, block in store.blocked_agent_dirs():
        # A file or a dangling link where the dir belongs. Heal names it,
        # install skips the agent, and doctor said nothing and exited 0.
        bad("agent-dir", "%s — %s, then `boost sync` %s what it missed"
            % (paths.not_writable(adir, block), paths.write_remedy(block),
               "relinks" if adir in skills_dirs else "writes"), wrap=True)
    for adir in store.unwritable_agent_dirs():
        # A next action, like the log line below it: without one this was
        # the only issue doctor names that nothing can act on.
        bad("agent-dir", "agent dir %s is not writable — `chmod u+w %s`, "
            "then `boost sync` writes what it missed"
            % (_tilde(adir), _tilde(adir)), wrap=True)

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

    line1 = ("%d skill%s installed · %d tap%s synced · %d broken link%s"
             % (len(skills), _s(len(skills)), tap_ok, _s(tap_ok),
                len(broken), _s(len(broken))))
    (rep.ok if not broken else rep.warn)("summary", line1)
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
    if issues == 0 and not taps:
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
    from ..core import dense
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
    if st["degraded"]:
        # The store was built and is now dead weight: say what it holds, what
        # changed, and that search has silently been on BM25 the whole time.
        built = st["built_model"] or st["built_provider"] or "an older build"
        detail = "built with %s" % built
        if st["reason"] == "model-changed":
            detail += ", live key is %s" % st["model"]
        elif st["reason"] == "provider-changed":
            detail += ", live key is %s" % st["provider"]
        elif st["reason"] == "empty":
            detail += " but holds no vectors"
        elif st["reason"] == "model-unavailable":
            # The store is fine; the query embedder is what failed. Say which
            # half and when, because a record from an hour ago on another
            # network reads differently from one made by the last search.
            from ..core import embed
            fail = st.get("model_failure") or {}
            detail += ", but %s" % embed.local_failure_text(fail)
            if isinstance(fail.get("at"), (int, float)):
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
        other_names = [n for n in names if n not in path_names]
        for n in path_names:
            p = catalog.resolve_path_target(n)
            targets.append((p.name, p))
        if not names or other_names:
            targets += [(n, store.skill_store_dir(n))
                       for n, _e in _iter_installed(other_names or None)]
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
    for kind, name, entry in _iter_installed_all(args.names or None):
        status = (_drift_status(name, entry) if kind == "skill"
                  else _drift_status_materialized(kind, name, entry))
        rows.append({"name": name, "kind": kind, "status": status,
                     "hint": _drift_hint(name, status, entry.get("tap", ""))})
    if args.json:
        print(json.dumps({"skills": rows}))
        return 0
    if not rows:
        print(out.empty_state("no skills installed",
                              hint="boost install <skill> to start"))
        return 0
    out.table([(r["name"] if r["kind"] == "skill"
                else "%s (%s)" % (r["name"], r["kind"]),
                out.role(r["status"], _DRIFT_ROLE[r["status"]]),
                out.role(r["hint"], "muted")) for r in rows],
              headers=("NAME", "STATUS", "HINT"), whole=("NAME",))
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
    for name, entry in _iter_installed(args.names or None):
        sdir = store.skill_store_dir(name)
        md = sdir / "SKILL.md"
        meta, body = _read_skill(sdir)
        failed = []
        if not (md.exists() and meta.get("name")):
            failed.append("parses")
        score, _notes = util.score_skill(sdir)
        if util.lint_failed(sdir, score, min_score=40):
            failed.append("lint")
        if not sdir.is_dir() or util.sha256_dir(sdir) != entry.get("sha256"):
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
        out.info("no skills installed")
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

    rows = _decay_rows(Path.cwd())
    if args.json:
        print(json.dumps({"skills": rows}))
        return 0
    if not rows:
        out.info("no skills installed")
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


def cmd_heal(argv):
    ap = cliparse.parser(
        prog="boost heal",
        description="Self-diagnose & repair the boost environment")
    ap.add_argument("--dry-run", action="store_true",
                    help="show repairs without applying them")
    ap.add_argument("--prune-duplicates", action="store_true",
                    help="remove symlinks in a native-store agent's skills dir "
                         "that lead back into the canonical store")
    args = ap.parse_args(argv)
    dry = args.dry_run
    actions: list[str] = []

    # linking_agents, not enabled_agents: a native-store agent's skills dir is
    # never written to, so it is not a missing directory.
    wanted = [*paths.boost_dirs(), *agents.linking_agents().values()]
    missing = [d for d in wanted if not d.is_dir()]
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
            out.ok("removed broken link %s" % _tilde(link))
        actions.append("unlink %s" % link.name)
    for link in theirs:
        # Named, never touched: it is in a directory boost writes to, so the
        # user should know it is dangling — but boost did not put it there.
        out.warn("broken link %s does not point into %s — left alone"
                 % (_tilde(link), _tilde(paths.store_dir())))

    plan = store.sync_plan()
    if dry:
        # `ours` above is exactly what a real run unlinks before computing
        # this plan, so `sync_plan`'s stale-link sweep never sees those paths
        # on a real run — only here, where nothing was unlinked yet. Skip
        # them so a preview doesn't report the same path twice under two
        # different actions.
        already_reported = {str(link) for link in ours}
        for name, agent in plan["missing_links"]:
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
            out.info(msg.replace(str(paths.home()), "~"))
            actions.append(msg)
    else:
        for msg in store.sync_apply(plan):
            out.ok(msg.replace(str(paths.home()), "~"))
            actions.append(msg)

    # Opt-in, unlike everything above it. The rest of `heal` repairs what boost
    # itself created; these entries boost did not create, so deleting one on a
    # plain `boost heal` would be silently removing another tool's file. Named
    # every run so the flag is discoverable from the command that would use it.
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

    # A dir that refuses writes, or a missing one whose parent refuses the
    # mkdir. A missing one heal CAN create is not stuck: the real run creates
    # it above, so a preview that called it unwritable would exit 1 where the
    # run it previews exits 0.
    cache_dir = paths.cache_dir()
    cache_stuck = paths.refuses_writes(cache_dir) is not None
    for tap in registry.list_taps():
        if not tap.is_cloned:
            out.warn("tap %s not cloned — skipped (run `boost update`)" % tap.name)
            continue
        had_cache = tap.cache_file.exists()
        if dry:
            if not had_cache and not cache_stuck:
                out.info("would rebuild catalog cache for %s" % tap.name)
                actions.append("cache %s" % tap.name)
        else:
            catalog.rebuild_tap(tap)
            # rebuild_tap survives a cache it cannot write and warns; claiming
            # the rebuild under that warning would certify a file that is
            # still missing, and every later run would claim it again.
            if not had_cache and tap.cache_file.exists():
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
    stuck = store.unwritable_agent_dirs()
    for adir in stuck:
        out.warn("agent dir %s is not writable — heal does not change "
                 "permissions; run `chmod u+w %s`, then `boost sync`"
                 % (_tilde(adir), _tilde(adir)), wrap=True)
    # The same rule for the cache dir doctor flags, and for any directory a
    # refused mkdir left missing: heal cannot make the parent writable, so it
    # must not answer "nothing to heal" beneath the problem. The preview and
    # the run print the same line, naming the directory that refuses.
    # setdefault: a missing cache dir is already in `blocked`, named once.
    if registry.list_taps() and cache_stuck:
        blocked.setdefault(cache_dir,
                           paths.refuses_writes(cache_dir) or cache_dir)
    # A file or a dangling link where a recorded rule's or workflow's dir
    # belongs. A block already named for a skills dir is named once.
    for d, block in store.blocked_agent_dirs():
        if block not in blocked.values():
            blocked.setdefault(d, block)
    for d, block in blocked.items():
        stuck.append(d)
        out.warn("%s — heal does not %s; %s"
                 % (paths.not_writable(d, block),
                    "move files" if paths.in_the_way(block)
                    else "change permissions",
                    paths.write_remedy(block)), wrap=True)
    if not actions and not stuck and not cfg_err:
        # A duplicate this run declined to prune is something `heal` saw, can
        # fix, and deliberately left. A bare "nothing to heal" printed under
        # the line offering the flag contradicts it.
        out.ok("nothing to heal automatically"
               if declined_duplicates else "nothing to heal")
    if actions and not dry:
        journal.log("heal", "%d actions" % len(actions))
    return 1 if cfg_err or stuck else 0


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
    installed = [(n, e) for n, e in _iter_installed() if not e.get("quarantined")]
    rules: list[tuple[str, str, str, set]] = []   # skill, line, polarity, stems
    declared: list[tuple[str, str]] = []           # skill, conflicting skill
    installed_names = {n for n, _e in installed}
    for name, _entry in installed:
        meta, body = _read_skill(store.skill_store_dir(name))
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
    taps = registry.list_taps()
    cloned = [t for t in taps if t.is_cloned]

    if not args.json:
        out.heading("boost health")
    for kind, label in (("skill", "skills"), ("rule", "rules"),
                        ("workflow", "workflows")):
        items = by_kind.get(kind, [])
        q = sum(1 for _n, e in items if e.get("quarantined"))
        p = sum(1 for _n, e in items if e.get("pinned"))
        kv(label, "%d installed · %d quarantined · %d pinned"
           % (len(items), q, p),
           {"installed": len(items), "quarantined": q, "pinned": p})
    kv("taps", "%d configured · %d cloned" % (len(taps), len(cloned)),
       {"configured": len(taps), "cloned": len(cloned)})

    expected = [n for n, e in installed if not e.get("quarantined")]
    coverage_ok = True
    for agent, adir in agents.linking_agents().items():
        linked = sum(1 for n in expected
                     if (adir / n).is_symlink() and (adir / n).exists())
        full = linked == len(expected)
        coverage_ok = coverage_ok and full
        kv(agent, "%d/%d %s" % (linked, len(expected),
                                out.role("✓", "success") if full
                                else out.role("!", "warn")),
           {"linked": linked, "expected": len(expected), "ok": full})
    # Agents that read the canonical store have no links to count, so they
    # used to be scored an unconditional len(expected)/len(expected) — green
    # even with a skill's store directory gone, in the same report `drift`
    # called store-missing. Stat the store instead. They are listed even when
    # full, because an agent silently absent from a health report reads as
    # "boost is not wired up for it".
    store_present = sum(1 for n in expected if store.skill_store_dir(n).is_dir())
    store_full = store_present == len(expected)
    for agent in agents.native_store_agents():
        coverage_ok = coverage_ok and store_full
        kv(agent, "%d/%d %s (reads the store directly)"
           % (store_present, len(expected),
              out.role("✓", "success") if store_full
              else out.role("!", "warn")),
           {"linked": store_present, "expected": len(expected),
            "ok": store_full, "native_store": True})

    drift_counts: dict = {}
    for kind, name, entry in all_installed:
        st = (_drift_status(name, entry) if kind == "skill"
              else _drift_status_materialized(kind, name, entry))
        drift_counts[st] = drift_counts.get(st, 0) + 1
    kv("drift", " · ".join("%d %s" % (n, s)
                           for s, n in sorted(drift_counts.items())) or "—",
       drift_counts)

    decay_n = sum(1 for r in _decay_rows(Path.cwd()) if r["verdict"] == "decay")
    kv("decay", "%d candidate%s" % (decay_n, _s(decay_n)), decay_n)

    broken, foreign = _broken_links()
    kv("broken links", "%d%s" % (
        len(broken), " (+%d not ours)" % len(foreign) if foreign else ""),
       {"ours": len(broken), "foreign": len(foreign)})

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

    attention = (bool(broken) or not coverage_ok
                 or drift_counts.get("store-missing", 0) > 0
                 or drift_counts.get("source-missing", 0) > 0
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
            raise BoostError("trust add requires NAME and KEY",
                             hint="`boost trust add acme ./acme.pub`")
        key_path = paths.expand(args.key)
        if key_path.is_file():
            key_text = key_path.read_text(encoding="utf-8")
        elif os.sep in args.key or args.key.endswith(".pub"):
            # Looks like a path but isn't one — say so, rather than falling
            # through to text parsing and blaming base64 for a typo'd path.
            raise BoostError("no such key file: %s" % args.key)
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
            raise BoostError("trust remove requires a NAME")
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
        out.dim("  none — add one with `boost trust add <name> <key>`")
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
