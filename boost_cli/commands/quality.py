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
    complete,
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
    staleness,
    store,
    util,
)
from ..core import output as out
from ..errors import BoostError
from ._common import _iter_installed, _iter_installed_all, _s

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


def _drift_hint(name: str, status: str) -> str:
    if status == "quarantined":
        return "boost quarantine --release %s to restore" % name
    if status == "upstream-moved":
        return "boost update"
    if status == "local-edits":
        return "boost reinstall %s to discard local edits" % name
    if status == "source-missing":
        return "boost update"
    if status == "store-missing":
        return "boost heal"
    return ""


def _parse_ts(iso: str) -> datetime | None:
    try:
        return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return None


def _fingerprint() -> tuple[str, list[str]]:
    """(sha256 hexdigest, component lines). Deterministic: the same lock file
    and tap commits always produce the same hash."""
    comps = sorted("%s:%s" % (n, e.get("sha256", ""))
                   for n, e in lockfile.installed().items())
    # Rules and workflows are part of the environment the agent runs on —
    # a poisoned CLAUDE.md rule must change the fingerprint. Kind-prefixed so
    # a skill-only environment's fingerprint is unchanged by this addition.
    comps += sorted("%s/%s:%s" % (kind, n, e.get("sha256", ""))
                    for kind, section in lockfile.all_installed().items()
                    if kind != "skill" for n, e in section.items())
    comps += sorted("%s:%s" % (t.name,
                               gitutil.head_commit(t.path)
                               if t.is_cloned and gitutil.has_git() else "")
                    for t in registry.list_taps())
    digest = hashlib.sha256("\n".join(comps).encode()).hexdigest()
    return digest, comps


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
        last = util.rel_time(ts.strftime("%Y-%m-%dT%H:%M:%SZ")) if ts else "never"
        if relevance == "none" and not recent:
            verdict = "decay"
        elif relevance in ("none", "low"):
            verdict = "review"
        else:
            verdict = "ok"
        rows.append({"name": name, "relevance": relevance,
                     "last_activity": last, "verdict": verdict})
    return rows


# --- commands ---------------------------------------------------------------

def cmd_doctor(argv):
    ap = cliparse.parser(
        prog="boost doctor", description="Check installation health & report issues")
    ap.parse_args(argv)
    issues = 0

    out.heading("boost doctor")

    def bad(msg, wrap=False):
        nonlocal issues
        issues += 1
        out.warn(msg, wrap=wrap)

    if gitutil.has_git():
        out.ok("git on PATH")
    else:
        bad("git not found on PATH — install git")
    paths.ensure_dirs()  # create silently; never a failure

    taps = registry.list_taps()
    tap_ok = 0
    for tap in taps:
        if not tap.is_cloned:
            bad("tap %s not cloned — run `boost update`" % tap.name)
        elif not tap.cache_file.exists():
            bad("tap %s has no catalog cache — run `boost update %s`"
                % (tap.name, tap.name))
        else:
            tap_ok += 1
    if taps and tap_ok == len(taps):
        out.ok("%d tap%s cloned & cached" % (len(taps), _s(len(taps))))
    elif not taps:
        out.info("no taps configured — add one with `boost tap owner/repo`")

    lock_ok = True
    lp = paths.lockfile_path()
    if lp.exists():
        try:
            raw = json.loads(lp.read_text(encoding="utf-8"))
            if raw.get("version") != lockfile.SCHEMA_VERSION:
                bad("lock file schema is v%s, expected v%d"
                    % (raw.get("version"), lockfile.SCHEMA_VERSION))
                lock_ok = False
        except (json.JSONDecodeError, OSError):
            bad("lock file is corrupt — restore with `boost replay`")
            lock_ok = False
    if lock_ok:
        out.ok("lock file parses (v%d)" % lockfile.SCHEMA_VERSION)

    skills = lockfile.installed()
    enabled = agents.enabled_agents()
    skill_issues = 0
    for name, entry in sorted(skills.items()):
        sdir = store.skill_store_dir(name)
        if not sdir.is_dir():
            bad("skill %s missing from store — run `boost heal`" % name)
            skill_issues += 1
            continue
        if entry.get("quarantined"):
            continue
        # tamper detection: the lock file records a sha256 at install time, but
        # only `boost verify` ever re-checked it — surface content drift here too.
        locked = entry.get("sha256")
        if locked and util.sha256_dir(sdir) != locked:
            bad("skill %s modified since install — run `boost verify`" % name)
            skill_issues += 1
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
                bad("skill %s not linked for %s — %s exists and is not a boost "
                    "link; move or delete it, then run `boost sync`"
                    % (name, agent, paths.tilde(link)))
            else:
                bad("skill %s not linked for %s — run `boost sync`" % (name, agent))
            skill_issues += 1
        # The other direction. `agents` records what is linked and `only_agents`
        # what was asked for, so a link the declaration excludes is pure lock
        # arithmetic here — no second walk of the agent dirs. Doctor has to say
        # it because `boost sync` does: a "healthy" that contradicts the
        # command it tells you to run is worse than no check at all.
        scope = entry.get("only_agents")
        stray = [a for a in entry.get("agents", []) if scope and a not in scope]
        if stray:
            bad("skill %s is linked for %s, outside its declared scope (%s) — "
                "run `boost sync --prune`"
                % (name, ", ".join(stray), ", ".join(scope)))
            skill_issues += 1
    if skills and not skill_issues:
        out.ok("%d skill%s present in store with agent links"
               % (len(skills), _s(len(skills))))

    # Project-scoped skills committed into THIS repo — the governance blind spot
    # #212 left open. They don't touch the user store, so the loop above never
    # saw them; a vendored third-party skill that has drifted from its committed
    # digest is exactly what a health check should surface.
    pbase, pskills = integrity.project_skills()
    proj_issues = 0
    for name, entry in sorted(pskills.items()):
        st = integrity.project_status(entry, pbase)
        if st == integrity.STATUS_MISSING:
            bad("project skill %s is in .boost but its files are gone — "
                "run `boost sync`" % name)
            proj_issues += 1
        elif st == integrity.STATUS_MODIFIED:
            bad("project skill %s modified since install — "
                "run `boost verify`" % name)
            proj_issues += 1
    if pskills and not proj_issues:
        out.ok("%d project skill%s intact in %s"
               % (len(pskills), _s(len(pskills)), paths.tilde(pbase)))

    # Rules and workflows don't live in the store — they materialize into agent
    # dirs (a file drop, or a CLAUDE.md managed block). Health = every recorded
    # materialization is still on disk; a deleted file means the install rotted.
    # Quarantined = materializations removed on purpose; reporting them as rot
    # would send the user to `boost reinstall`, which re-arms the rule — and
    # counting them "fully materialized" would be the opposite lie.
    rules = {n: e for n, e in lockfile.installed_rules().items()
             if not e.get("quarantined")}
    workflows = {n: e for n, e in lockfile.installed_workflows().items()
                 if not e.get("quarantined")}
    mat_issues = 0
    for name, entry in sorted(rules.items()):
        for m in entry.get("materializations") or []:
            p = Path(m.get("path", ""))
            if m.get("mode") == "claude":
                try:
                    present = p.exists() and ("boost:rule:%s start" % name) in \
                        p.read_text(encoding="utf-8")
                except OSError:
                    present = False
            else:
                present = p.is_file()
            if not present:
                bad("rule %s missing its %s materialization — run "
                    "`boost reinstall %s`" % (name, m.get("agent", "?"), name))
                mat_issues += 1
    for name, entry in sorted(workflows.items()):
        for m in entry.get("materializations") or []:
            if not Path(m.get("path", "")).is_file():
                bad("workflow %s missing its %s file — run `boost reinstall %s`"
                    % (name, m.get("agent", "?"), name))
                mat_issues += 1
    if (rules or workflows) and not mat_issues:
        out.ok("%d rule%s and %d workflow%s fully materialized"
               % (len(rules), _s(len(rules)), len(workflows), _s(len(workflows))))

    root = paths.store_dir()
    orphans = [c.name for c in sorted(root.iterdir())
               if c.is_dir() and not c.name.startswith(".") and c.name not in skills
               ] if root.is_dir() else []
    if orphans:
        bad("%d orphaned store dir%s (%s) — run `boost sync`"
            % (len(orphans), _s(len(orphans)), ", ".join(orphans[:5])))

    broken, foreign = _broken_links()
    if broken:
        bad("%d broken symlink%s in agent dirs — run `boost heal`"
            % (len(broken), _s(len(broken))))
    if foreign:
        # `out.info`, not `bad`: this does not raise the issue count, because
        # boost will not fix it and `heal` deliberately leaves it — counting it
        # would leave doctor permanently red on something no boost command can
        # clear, which is how a health check stops being read.
        out.info("%d broken symlink%s in agent dirs not created by boost — "
                 "left alone; yours to remove or repair"
                 % (len(foreign), _s(len(foreign))))

    for dup in store.duplicate_discovery():
        # An agent that reads the canonical store natively, holding its own
        # entry for a skill that store already carries. Boost did not put it
        # there — it never links into a native-store agent — but the agent
        # loads the same skill from two discovery tiers and says so on every
        # session, so a health check that stayed quiet about it would be
        # describing a machine the user is not looking at.
        bad("skill %s is discoverable twice by %s — %s leads to %s, which it "
            "already reads natively; remove the duplicate with "
            "`boost heal --prune-duplicates`"
            % (dup.name, agents.display_name(dup.agent), _tilde(dup.path),
               _tilde(dup.target)), wrap=True)

    for adir in enabled.values():
        if adir.is_dir() and not os.access(str(adir), os.W_OK):
            bad("agent dir %s is not writable" % _tilde(adir))

    rotation = journal.rotation_healthy()
    if not rotation:
        bad("journal is overdue for rotation — run `boost heal`")

    # Which search engine will actually answer a query. Dense retrieval needs
    # three things to line up and every one of them fails silently, so doctor
    # is where the answer belongs — `search` only ever reports the engine that
    # already ran, never that a configured one never got the chance.
    _report_search_engine(bad)

    lp = logs.log_path()
    if lp.exists():
        # Existence is not health: a log the process cannot open makes every
        # invocation print a PermissionError traceback from the logging module
        # while this check happily reported a ✓ for the same file. Diagnostics
        # are the first thing consulted when something else breaks, so a log
        # that silently accepts nothing has to read as a fault.
        if os.access(str(lp), os.W_OK):
            out.ok("diagnostic log at %s" % _tilde(lp))
        else:
            bad("diagnostic log %s is not writable — every invocation is "
                "failing to record; fix its permissions (chmod u+w)"
                % _tilde(lp))
    crashes = sorted(paths.logs_dir().glob("crash-*.log")) \
        if paths.logs_dir().is_dir() else []
    if crashes:
        out.warn("%d crash report%s in %s (newest: %s) — see `boost log --crashes`"
                 % (len(crashes), _s(len(crashes)), _tilde(paths.logs_dir()),
                    crashes[-1].name))

    line1 = ("%d skill%s installed · %d tap%s synced · %d broken link%s"
             % (len(skills), _s(len(skills)), tap_ok, _s(tap_ok),
                len(broken), _s(len(broken))))
    (out.ok if not broken else out.warn)(line1)
    if lock_ok and rotation:
        out.ok("lock file integrity OK · log rotation healthy")
    else:
        out.warn("lock file integrity or log rotation needs attention")

    out.verdict(issues == 0,
                "healthy" if not issues else
                "%d issue%s need attention — see the suggestions above"
                % (issues, _s(issues)))
    return 1 if issues else 0


# The remedy table moved to core.dense.fix_hint so `boost search` reports the
# same next action as `boost doctor` — see that function for why.


def _report_search_engine(bad) -> None:
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
        out.ok("semantic search active — %s %s (%d-d), %d chunk%s across %d tap%s"
               % (st["provider"], st["model"], st["dim"] or 0,
                  st["chunks"], _s(st["chunks"]), st["taps"], _s(st["taps"])))
        if not st["quantized"]:
            # Ready but slow, which no other line here would say. `vec0` has no
            # ANN index, so an unquantized store re-scans every vector on every
            # query — 28.2 s measured at 750,416 chunks. The remedy costs no
            # embedding calls, so it is worth naming rather than leaving the
            # user to wonder why the search they enabled feels broken.
            out.warn("the vector store predates binary quantization, so every "
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
        bad("semantic search silently off — %d-chunk vector store %s; "
            "searches are using BM25. %s" % (st["chunks"], detail, fix),
            wrap=True)
        return

    out.info("semantic search not configured — using the full-content BM25 "
             "engine (%s)" % fix, wrap=True)


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
    ap.add_argument("names", nargs="*", metavar="NAME")
    ap.add_argument("--tap", metavar="TAP", help="lint every skill in a tap's clone")
    ap.add_argument("--min", type=int, default=40, dest="min_score", metavar="N",
                    help="minimum passing score (default 40)")
    ap.add_argument("--json", action="store_true")
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
        targets = [(n, store.skill_store_dir(n))
                   for n, _e in _iter_installed(args.names or None)]
    if not targets:
        if args.json:
            print(json.dumps({"min": args.min_score, "skills": [],
                              "skipped": skipped, "failed": 0}))
        else:
            _print_skipped(skipped)
            out.info("nothing to lint")
        return 0

    results: list[dict[str, Any]] = []
    for name, sdir in targets:
        score, notes = util.score_skill(sdir)
        meta, _ = _read_skill(sdir)
        errors = []
        if not (sdir / "SKILL.md").exists():
            errors.append("missing SKILL.md")
        else:
            if not meta.get("name"):
                errors.append("missing required field: name")
            if not meta.get("description"):
                errors.append("missing required field: description")
        notes = [n for n in notes
                 if "missing `name`" not in n and "missing `description`" not in n
                 and n != "missing SKILL.md"]
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
    out.ok("%d skill%s pass lint (min %d)" % (len(results), _s(len(results)),
                                              args.min_score))
    return 0


def cmd_drift(argv):
    ap = cliparse.parser(
        prog="boost drift",
        description="Detect installed skills diverging from source")
    ap.add_argument("names", nargs="*", metavar="NAME")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rows = []
    for kind, name, entry in _iter_installed_all(args.names or None):
        status = (_drift_status(name, entry) if kind == "skill"
                  else _drift_status_materialized(kind, name, entry))
        rows.append({"name": name, "kind": kind, "status": status,
                     "hint": _drift_hint(name, status)})
    if args.json:
        print(json.dumps({"skills": rows}))
        return 0
    if not rows:
        out.info("no skills installed")
        return 0
    out.table([(r["name"] if r["kind"] == "skill"
                else "%s (%s)" % (r["name"], r["kind"]),
                out.role(r["status"], _DRIFT_ROLE[r["status"]]),
                out.role(r["hint"], "muted")) for r in rows],
              headers=("NAME", "STATUS", "HINT"))
    counts: dict = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    out.info(" · ".join("%d %s" % (n, s) for s, n in sorted(counts.items())))
    return 0


def cmd_test(argv):
    ap = cliparse.parser(
        prog="boost test",
        description="Validate installed skills against quality checks")
    ap.add_argument("names", nargs="*", metavar="NAME")
    args = ap.parse_args(argv)

    rows, failed_count = [], 0
    for name, entry in _iter_installed(args.names or None):
        sdir = store.skill_store_dir(name)
        md = sdir / "SKILL.md"
        meta, body = _read_skill(sdir)
        failed = []
        if not (md.exists() and meta.get("name")):
            failed.append("parses")
        score, _notes = util.score_skill(sdir)
        if score < 40:
            failed.append("lint")
        if not sdir.is_dir() or util.sha256_dir(sdir) != entry.get("sha256"):
            failed.append("verify")
        if len(body.encode("utf-8")) > 64 * 1024:
            failed.append("size")
        if not md.exists():
            failed.append("layout")
        if failed:
            failed_count += 1
        rows.append((name,
                     out.role("FAIL", "danger") if failed else out.role("PASS", "success"),
                     out.role(", ".join(failed), "muted")))
    if not rows:
        out.info("no skills installed")
        return 0
    out.table(rows, headers=("SKILL", "RESULT", "FAILED CHECKS"))
    out.info("%d passed, %d failed" % (len(rows) - failed_count, failed_count))
    return 1 if failed_count else 0


def cmd_fingerprint(argv):
    ap = cliparse.parser(
        prog="boost fingerprint",
        description="Deterministic hash of the skill environment")
    ap.add_argument("--verbose", action="store_true",
                    help="show the hashed components")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    digest, comps = _fingerprint()
    if args.json:
        print(json.dumps({"fingerprint": digest, "short": digest[:16],
                          "components": comps}))
        return 0
    out.heading("environment fingerprint")
    print("  " + out.role(digest[:16], "accent", bold=True)
          + "  " + out.role(digest, "muted"))
    if args.verbose:
        out.table([tuple(line.split(":", 1)) for line in comps],
                  headers=("COMPONENT", "DIGEST/COMMIT"))
    return 0


def cmd_decay(argv):
    ap = cliparse.parser(
        prog="boost decay",
        description="Flag skills irrelevant to your current stack")
    ap.add_argument("--json", action="store_true")
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
                r["last_activity"], verdicts[r["verdict"]]) for r in rows],
              headers=("SKILL", "RELEVANCE", "LAST ACTIVITY", "VERDICT"))
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

    # linking_agents, matching agents.ensure_agent_dirs below: a native-store
    # agent's skills dir is never written to, so it is not a missing directory.
    wanted = [paths.boost_home(), paths.repos_dir(), paths.cache_dir(), paths.logs_dir(), paths.state_dir(), paths.snapshots_dir(), paths.lock_history_dir(), paths.profiles_dir(), paths.store_dir(), *list(agents.linking_agents().values())]
    missing = [d for d in wanted if not d.is_dir()]
    if missing:
        if dry:
            out.info("would create %d missing director%s"
                     % (len(missing), "y" if len(missing) == 1 else "ies"))
        else:
            paths.ensure_dirs()
            agents.ensure_agent_dirs()
            out.ok("created %d missing director%s"
                   % (len(missing), "y" if len(missing) == 1 else "ies"))
        actions.append("mkdir %d" % len(missing))

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
        for name in plan["missing_store"]:
            out.info("would restore %s from its tap (or drop it from the lock)" % name)
            actions.append("restore %s" % name)
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

    for tap in registry.list_taps():
        if not tap.is_cloned:
            out.warn("tap %s not cloned — skipped (run `boost update`)" % tap.name)
            continue
        had_cache = tap.cache_file.exists()
        if dry:
            if not had_cache:
                out.info("would rebuild catalog cache for %s" % tap.name)
                actions.append("cache %s" % tap.name)
        else:
            catalog.rebuild_tap(tap)
            if not had_cache:
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

    if not actions:
        # A duplicate this run declined to prune is something `heal` saw, can
        # fix, and deliberately left. A bare "nothing to heal" printed under
        # the line offering the flag contradicts it.
        out.ok("nothing to heal automatically"
               if declined_duplicates else "nothing to heal")
    elif not dry:
        journal.log("heal", "%d actions" % len(actions))
    return 0


def cmd_conflict(argv):
    ap = cliparse.parser(
        prog="boost conflict",
        description="Detect contradictory rules between skills")
    ap.add_argument("--json", action="store_true")
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
        description="Show a skill's upstream change history")
    ap.add_argument("name", metavar="NAME")
    ap.add_argument("-n", type=int, default=20, metavar="N",
                    help="number of entries (default 20)")
    args = ap.parse_args(argv)

    entry = lockfile.get_skill(args.name)
    if entry:
        tap_name, rel = entry.get("tap", ""), entry.get("source_dir", ".")
    else:
        e = catalog.resolve_one(args.name)
        tap_name, rel = e["tap"], e["rel_dir"]
    if tap_name == "local":
        out.info("no upstream history — %s was imported locally" % args.name)
        return 0
    tap = registry.get(tap_name)
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    lines = gitutil.log_for_path(tap.path, rel, args.n)
    out.heading("changelog for %s (%s)" % (args.name, tap.name))
    for line in lines:
        out.info(line)
    if not lines:
        out.warn("no history found for %s in %s" % (rel, tap.name))
    if len(lines) < 3:
        note = ("(shallow clone: run `git -C %s fetch --unshallow` "
                "for full history)" % _tilde(tap.path))
        for line in out.wrap(note, max(out.term_width() - 2, 20)):
            print(out.role("  " + line, "muted"))
    return 0


def cmd_health(argv):
    ap = cliparse.parser(
        prog="boost health", description="Dashboard of skill-environment health")
    ap.parse_args(argv)

    installed = _iter_installed()
    quarantined = sum(1 for _n, e in installed if e.get("quarantined"))
    pinned = sum(1 for _n, e in installed if e.get("pinned"))
    taps = registry.list_taps()
    cloned = [t for t in taps if t.is_cloned]

    out.heading("boost health")
    out.kv("skills", "%d installed · %d quarantined · %d pinned"
           % (len(installed), quarantined, pinned))
    out.kv("taps", "%d configured · %d cloned" % (len(taps), len(cloned)))

    expected = [n for n, e in installed if not e.get("quarantined")]
    coverage_ok = True
    for agent, adir in agents.linking_agents().items():
        linked = sum(1 for n in expected
                     if (adir / n).is_symlink() and (adir / n).exists())
        full = linked == len(expected)
        coverage_ok = coverage_ok and full
        out.kv(agent, "%d/%d %s" % (linked, len(expected),
                                    out.role("✓", "success") if full
                                    else out.role("!", "warn")))
    # Agents that read the canonical store have no links to count — scoring
    # them 0/N would report a healthy setup as broken. They are listed anyway,
    # because an agent silently absent from a health report reads as "boost is
    # not wired up for it".
    for agent in agents.native_store_agents():
        out.kv(agent, "%d/%d %s (reads the store directly)"
               % (len(expected), len(expected), out.role("✓", "success")))

    drift_counts: dict = {}
    for name, entry in installed:
        st = _drift_status(name, entry)
        drift_counts[st] = drift_counts.get(st, 0) + 1
    out.kv("drift", " · ".join("%d %s" % (n, s)
                               for s, n in sorted(drift_counts.items())) or "—")

    decay_n = sum(1 for r in _decay_rows(Path.cwd()) if r["verdict"] == "decay")
    out.kv("decay", "%d candidate%s" % (decay_n, _s(decay_n)))

    broken, foreign = _broken_links()
    out.kv("broken links", "%d%s" % (
        len(broken), " (+%d not ours)" % len(foreign) if foreign else ""))

    last_sync = "never"
    if cloned and gitutil.has_git():
        stamps = []
        for tap in cloned:
            proc = gitutil.run(["-C", str(tap.path), "log", "-1", "--format=%ct"],
                               check=False)
            if proc.returncode == 0 and proc.stdout.strip().isdigit():
                stamps.append(int(proc.stdout.strip()))
        if stamps:
            iso = datetime.fromtimestamp(max(stamps), tz=UTC
                                         ).strftime("%Y-%m-%dT%H:%M:%SZ")
            last_sync = util.rel_time(iso)
    out.kv("last tap sync", last_sync)

    week_ago = datetime.now(UTC) - timedelta(days=7)
    recent = sum(1 for e in journal.events()
                 if (_parse_ts(e.get("ts", "")) or week_ago) > week_ago)
    out.kv("journal (7d)", "%d event%s" % (recent, _s(recent)))
    out.kv("fingerprint", _fingerprint()[0][:16])

    attention = (bool(broken) or not coverage_ok
                 or drift_counts.get("store-missing", 0) > 0
                 or drift_counts.get("source-missing", 0) > 0
                 or not journal.rotation_healthy())
    if attention:
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

    if args.action == "add":
        if not args.name or not args.key:
            raise BoostError("trust add requires NAME and KEY",
                             hint="`boost trust add acme ./acme.pub`")
        key_path = paths.expand(args.key)
        key_text = (key_path.read_text(encoding="utf-8")
                    if key_path.is_file() else args.key)
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
        out.table([(k["name"], k.get("fingerprint", "?")) for k in keys],
                  headers=("NAME", "FINGERPRINT"))
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
    out.table(rows, headers=("TAP", "PROVENANCE", "KEY / DETAIL"))
