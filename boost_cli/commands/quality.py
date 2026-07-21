"""Quality & Health commands — doctor, lint, audit, verify, drift, test,
fingerprint, quarantine, decay, heal, conflict, changelog, attest, health.

Shared helpers at the top keep the fourteen commands small: installed-skill
iteration, broken-symlink discovery, drift classification, and the
deterministic environment fingerprint.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from .. import cliparse
from ..core import (agents, ai, catalog, frontmatter, gitutil, imperative,
                    journal, lockfile, logs, output as out, paths, policy,
                    registry, staleness, store, util)
from ..errors import BoostError

# --- audit: dangerous-content patterns ------------------------------------

_AUDIT_PATTERNS = [
    (re.compile(r"(?:curl|wget)[^|\n]*\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b"),
     "HIGH", "remote-exec"),
    (re.compile(r"rm\s+-(?:rf|fr)\s+(?:/|~)(?=[\s'\";`)]|$)", re.M),
     "HIGH", "destructive"),
    (re.compile(r"base64\s+(?:-d|-D|--decode)\b[^\n]*\|\s*(?:ba|z)?sh\b"),
     "HIGH", "obfuscated-exec"),
    (re.compile(r"(?i)ignore\s+(?:all\s+|any\s+)?(?:previous|prior)\s+instructions"),
     "HIGH", "prompt-injection"),
    (re.compile(r"(?i)exfiltrat"), "MED", "exfiltration"),
    (re.compile(r"\bsudo\s"), "LOW", "privilege-escalation"),
]
_CRED_POST = re.compile(r"(?i)(?:curl\b[^\n]*\s(?:-d|--data)\b|POST\s+[^\n]*https?://)")
_CRED_HINT = re.compile(r"(?i)secret|token|api[-_]?key|password|credential")
_SEV_ROLE = {"HIGH": "danger", "MED": "warn", "LOW": "muted"}

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


def _s(n: int) -> str:
    return "" if n == 1 else "s"


def _iter_installed(names: Optional[List[str]] = None) -> List[Tuple[str, dict]]:
    """[(name, lock_entry)] — all installed, or the given names (validated)."""
    skills = lockfile.installed()
    if names:
        missing = [n for n in names if n not in skills]
        if missing:
            raise BoostError("not installed: %s" % ", ".join(missing),
                            hint="see what is with `boost list`")
        return [(n, skills[n]) for n in names]
    return sorted(skills.items())


def _broken_links() -> List[Path]:
    """Broken (dangling) symlinks across every enabled agent dir."""
    broken: List[Path] = []
    for adir in agents.enabled_agents().values():
        if not adir.is_dir():
            continue
        for link in sorted(adir.iterdir()):
            if link.is_symlink() and not link.exists():
                broken.append(link)
    return broken


def _read_skill(skill_dir: Path) -> Tuple[dict, str]:
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


_DRIFT_ROLE = {"in-sync": "success", "local-edits": "warn",
               "upstream-moved": "accent", "source-missing": "danger",
               "store-missing": "danger", "n/a": "muted"}


def _drift_hint(name: str, status: str) -> str:
    if status == "upstream-moved":
        return "boost update"
    if status == "local-edits":
        return "boost reinstall %s to discard local edits" % name
    if status == "source-missing":
        return "boost update"
    if status == "store-missing":
        return "boost heal"
    return ""


def _parse_ts(iso: str) -> Optional[datetime]:
    try:
        return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _fingerprint() -> Tuple[str, List[str]]:
    """(sha256 hexdigest, component lines). Deterministic: the same lock file
    and tap commits always produce the same hash."""
    comps = sorted("%s:%s" % (n, e.get("sha256", ""))
                   for n, e in lockfile.installed().items())
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
    kws: List[str] = []
    try:
        from ..core.stackprobe import detect_stack
        stack = detect_stack(cwd)
        if isinstance(stack, dict):
            kws.extend(str(k) for k in (stack.get("keywords") or []))
    except Exception:
        pass
    for marker, words in _STACK_MARKERS:
        if (Path(cwd) / marker).exists():
            kws.extend(words)
    return {_norm_token(k) for k in kws if _norm_token(k)}


def _decay_rows(cwd: Path) -> List[dict]:
    """Relevance/recency verdict per installed skill (shared by decay/health)."""
    kws = _stack_keywords(cwd)
    last_by: dict = {}
    for e in journal.events():
        subj, ts = e.get("subject"), _parse_ts(e.get("ts", ""))
        if subj and ts and (subj not in last_by or ts > last_by[subj]):
            last_by[subj] = ts
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
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

    def bad(msg):
        nonlocal issues
        issues += 1
        out.warn(msg)

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
            raw = json.loads(lp.read_text())
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
            if not link.is_symlink() or not link.exists():
                bad("skill %s not linked for %s — run `boost sync`" % (name, agent))
                skill_issues += 1
    if skills and not skill_issues:
        out.ok("%d skill%s present in store with agent links"
               % (len(skills), _s(len(skills))))

    # Rules and workflows don't live in the store — they materialize into agent
    # dirs (a file drop, or a CLAUDE.md managed block). Health = every recorded
    # materialization is still on disk; a deleted file means the install rotted.
    rules = lockfile.installed_rules()
    workflows = lockfile.installed_workflows()
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

    broken = _broken_links()
    if broken:
        bad("%d broken symlink%s in agent dirs — run `boost heal`"
            % (len(broken), _s(len(broken))))

    for agent, adir in enabled.items():
        if adir.is_dir() and not os.access(str(adir), os.W_OK):
            bad("agent dir %s is not writable" % _tilde(adir))

    rotation = journal.rotation_healthy()
    if not rotation:
        bad("journal is overdue for rotation — run `boost heal`")

    lp = logs.log_path()
    if lp.exists():
        out.ok("diagnostic log at %s" % _tilde(lp))
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


def cmd_lint(argv):
    ap = cliparse.parser(
        prog="boost lint", description="Validate SKILL.md frontmatter & quality")
    ap.add_argument("names", nargs="*", metavar="NAME")
    ap.add_argument("--tap", metavar="TAP", help="lint every skill in a tap's clone")
    ap.add_argument("--min", type=int, default=40, dest="min_score", metavar="N",
                    help="minimum passing score (default 40)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    targets: List[Tuple[str, Path]] = []
    if args.tap:
        tap = registry.get(args.tap)
        if not tap.is_cloned:
            raise BoostError("tap %s is not cloned" % tap.name,
                            hint="run `boost update %s`" % tap.name)
        entries = catalog.load_tap(tap)
        if args.names:
            wanted = set(args.names)
            entries = [e for e in entries if e["name"] in wanted]
        targets = [(e["name"],
                    tap.path if e["rel_dir"] == "." else tap.path / e["rel_dir"])
                   for e in entries]
    else:
        targets = [(n, store.skill_store_dir(n))
                   for n, _e in _iter_installed(args.names or None)]
    if not targets:
        if args.json:
            print(json.dumps([]))
        else:
            out.info("nothing to lint")
        return 0

    results = []
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
                          "failed": len(failed)}))
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
    if failed:
        out.warn("%d of %d skill%s below %d or with errors"
                 % (len(failed), len(results), _s(len(results)), args.min_score))
        return 1
    out.ok("%d skill%s pass lint (min %d)" % (len(results), _s(len(results)),
                                              args.min_score))
    return 0


def cmd_audit(argv):
    ap = cliparse.parser(
        prog="boost audit",
        description="Check installed skills against a safety blocklist")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    pol = policy.load()
    installed = _iter_installed()
    findings: dict = {}

    def add(name, severity, label, where, snippet):
        findings.setdefault(name, []).append({
            "severity": severity, "label": label, "file": where,
            "snippet": snippet})

    min_score = int(pol.get("min_quality_score") or 0)
    for name, _entry in installed:
        if name in pol.get("blocked_skills", []):
            add(name, "HIGH", "policy-blocked", "policy.json",
                "skill is on the policy blocklist")
        sdir = store.skill_store_dir(name)
        if min_score > 0:
            score, _n = util.score_skill(sdir)
            if score < min_score:
                add(name, "MED", "quality-below-policy", "SKILL.md",
                    "score %d < policy minimum %d" % (score, min_score))
        files = [sdir / "SKILL.md"] if (sdir / "SKILL.md").exists() else []
        if sdir.is_dir():
            files += [p for p in sorted(sdir.rglob("*"))
                      if p.is_file() and p.suffix in (".sh", ".py")]
        for f in files:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = f.relative_to(sdir).as_posix()
            for pat, severity, label in _AUDIT_PATTERNS:
                for m in pat.finditer(text):
                    line_no = text.count("\n", 0, m.start()) + 1
                    line = text.splitlines()[line_no - 1].strip()
                    add(name, severity, label, "%s:%d" % (rel, line_no), line[:90])
            for i, line in enumerate(text.splitlines(), 1):
                if _CRED_POST.search(line) and _CRED_HINT.search(line):
                    add(name, "MED", "credential-exfil",
                        "%s:%d" % (rel, i), line.strip()[:90])

    counts = {"HIGH": 0, "MED": 0, "LOW": 0}
    for fs in findings.values():
        for f in fs:
            counts[f["severity"]] += 1

    if args.json:
        print(json.dumps({"skills_scanned": len(installed),
                          "findings": findings, "counts": counts}))
        return 1 if counts["HIGH"] or counts["MED"] else 0

    out.heading("safety audit — %d skill%s" % (len(installed), _s(len(installed))))
    if not findings:
        out.ok("no safety findings across %d skills" % len(installed))
        return 0
    for name in sorted(findings):
        print("  " + out.c(name, out.BOLD))
        for f in findings[name]:
            print("    %s %s  %s  %s"
                  % (out.role(f["severity"].ljust(4), _SEV_ROLE[f["severity"]]),
                     f["label"], out.role(f["file"], "muted"), f["snippet"]))
    out.info("%d high · %d medium · %d low across %d skill%s"
             % (counts["HIGH"], counts["MED"], counts["LOW"],
                len(installed), _s(len(installed))))
    return 1 if counts["HIGH"] or counts["MED"] else 0


def cmd_verify(argv):
    ap = cliparse.parser(
        prog="boost verify",
        description="Validate skill quality & lock-file integrity")
    ap.add_argument("names", nargs="*", metavar="NAME")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    results = []
    for name, entry in _iter_installed(args.names or None):
        missing_fields = [f for f in ("version", "tap", "sha256", "installed_at")
                          if not entry.get(f)]
        sdir = store.skill_store_dir(name)
        if not sdir.is_dir():
            status = "missing"
        elif util.sha256_dir(sdir) != entry.get("sha256"):
            status = "modified"
        else:
            status = "ok"
        results.append({"name": name, "status": status,
                        "missing_fields": missing_fields})

    bad = [r for r in results if r["status"] != "ok" or r["missing_fields"]]
    if args.json:
        print(json.dumps({"skills": results, "failed": len(bad)}))
        return 1 if bad else 0

    if not results:
        out.info("no skills installed")
        return 0
    width = max(len(r["name"]) for r in results)
    status_role = {"ok": "success", "modified": "warn", "missing": "danger"}
    for r in results:
        note = ("  missing lock fields: " + ", ".join(r["missing_fields"])
                if r["missing_fields"] else "")
        print("  %s  %s%s" % (r["name"].ljust(width),
                              out.role(r["status"], status_role[r["status"]]),
                              out.role(note, "muted")))
    if bad:
        out.warn("%d of %d skill%s failed verification"
                 % (len(bad), len(results), _s(len(results))))
        return 1
    out.ok("lock file integrity OK")
    return 0


def cmd_drift(argv):
    ap = cliparse.parser(
        prog="boost drift",
        description="Detect installed skills diverging from source")
    ap.add_argument("names", nargs="*", metavar="NAME")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rows = []
    for name, entry in _iter_installed(args.names or None):
        status = _drift_status(name, entry)
        rows.append({"name": name, "status": status,
                     "hint": _drift_hint(name, status)})
    if args.json:
        print(json.dumps({"skills": rows}))
        return 0
    if not rows:
        out.info("no skills installed")
        return 0
    out.table([(r["name"], out.role(r["status"], _DRIFT_ROLE[r["status"]]),
                out.role(r["hint"], "muted")) for r in rows],
              headers=("SKILL", "STATUS", "HINT"))
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


def cmd_quarantine(argv):
    ap = cliparse.parser(
        prog="boost quarantine",
        description="Isolate a problematic skill without uninstalling")
    ap.add_argument("name", nargs="?", metavar="NAME")
    ap.add_argument("--release", metavar="NAME",
                    help="re-link a quarantined skill")
    ap.add_argument("--list", action="store_true", dest="list_mode",
                    help="list quarantined skills")
    args = ap.parse_args(argv)

    modes = sum(1 for m in (args.name, args.release, args.list_mode) if m)
    if modes != 1:
        raise BoostError("specify a skill to quarantine, --release NAME, or --list",
                        hint="e.g. `boost quarantine cowboy-coding`")

    if args.list_mode:
        rows = []
        for name, entry in _iter_installed():
            if not entry.get("quarantined"):
                continue
            evs = journal.events(action="quarantine", subject=name)
            since = util.rel_time(evs[0].get("ts", "")) if evs else "?"
            rows.append((name, entry.get("version", "?"),
                         entry.get("tap", "?"), since))
        if not rows:
            out.info("no skills in quarantine")
            return 0
        out.table(rows, headers=("SKILL", "VERSION", "TAP", "SINCE"))
        return 0

    if args.release:
        name = args.release
        entry = lockfile.get_skill(name)
        if not entry:
            raise BoostError("%s is not installed" % name,
                            hint="see what is with `boost list`")
        if not entry.get("quarantined"):
            out.warn("%s is not quarantined" % name)
            return 0
        res = store.link_agents(name)
        entry["quarantined"] = False
        entry["agents"] = res.linked
        lockfile.set_skill(name, entry)
        journal.log("release", name)
        out.ok("released %s (linked: %s)" % (name, ", ".join(res.linked) or "none"))
        return 0

    name = args.name
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    if entry.get("quarantined"):
        out.warn("%s is already quarantined" % name)
        return 0
    store.unlink_agents(name)
    entry["quarantined"] = True
    lockfile.set_skill(name, entry)
    journal.log("quarantine", name)
    out.ok("quarantined %s (store intact, links removed)" % name)
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
    args = ap.parse_args(argv)
    dry = args.dry_run
    actions: List[str] = []

    wanted = [paths.boost_home(), paths.repos_dir(), paths.cache_dir(),
              paths.logs_dir(), paths.state_dir(), paths.snapshots_dir(),
              paths.lock_history_dir(), paths.profiles_dir(),
              paths.store_dir()] + list(agents.enabled_agents().values())
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

    for link in _broken_links():
        if dry:
            out.info("would remove broken link %s" % _tilde(link))
        else:
            link.unlink()
            out.ok("removed broken link %s" % _tilde(link))
        actions.append("unlink %s" % link.name)

    plan = store.sync_plan()
    if dry:
        for name, agent in plan["missing_links"]:
            out.info("would link %s → %s" % (name, agent))
            actions.append("link %s" % name)
        for p in plan["stale_links"]:
            out.info("would remove stale link %s" % _tilde(p))
            actions.append("stale %s" % p)
        for name in plan["missing_store"]:
            out.info("would restore %s from its tap (or drop it from the lock)" % name)
            actions.append("restore %s" % name)
    else:
        for msg in store.sync_apply(plan):
            out.ok(msg.replace(str(paths.home()), "~"))
            actions.append(msg)

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

    if not journal.rotation_healthy():
        if dry:
            out.info("would rotate the journal")
        else:
            out.ok("journal rotation scheduled (next write rotates)")
        actions.append("rotate")

    if not actions:
        out.ok("nothing to heal")
    elif not dry:
        journal.log("heal", "%d actions" % len(actions))
    return 0


def cmd_conflict(argv):
    ap = cliparse.parser(
        prog="boost conflict",
        description="Detect contradictory rules between skills")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    installed = _iter_installed()
    rules = []   # (skill, line, polarity, stem set)
    declared = []
    installed_names = {n for n, _e in installed}
    for name, _entry in installed:
        meta, body = _read_skill(store.skill_store_dir(name))
        conflicts = meta.get("conflicts") or []
        for other in (conflicts if isinstance(conflicts, list) else [conflicts]):
            if str(other) in installed_names and str(other) != name:
                declared.append((name, str(other)))
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

    pairs, seen = [], set()
    for da, db in declared:
        key = tuple(sorted((da, db))) + ("declared",)
        if key in seen:
            continue
        seen.add(key)
        pairs.append({"kind": "declared", "a": da, "b": db,
                      "a_line": "frontmatter declares conflicts: %s" % db,
                      "b_line": ""})
    for a_skill, a_line, a_pol, a_stem in rules:
        for b_skill, b_line, b_pol, b_stem in rules:
            if a_skill == b_skill or not (a_pol == "pos" and b_pol == "neg"):
                continue
            small = min(len(a_stem), len(b_stem))
            if small and len(a_stem & b_stem) / small >= _CONFLICT_OVERLAP:
                key = tuple(sorted(((a_skill, a_line), (b_skill, b_line))))
                if key in seen:
                    continue
                seen.add(key)
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
        out.warn(ai.fallback_note())

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
        print(out.role("  (shallow clone: run `git -C %s fetch --unshallow` "
                    "for full history)" % _tilde(tap.path), "muted"))
    return 0


def cmd_attest(argv):
    ap = cliparse.parser(
        prog="boost attest",
        description="Display/verify the install record for skills")
    ap.add_argument("name", nargs="?", metavar="NAME")
    ap.add_argument("--verify", action="store_true",
                    help="check sha & journal record for each skill")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    targets = _iter_installed([args.name] if args.name else None)
    first_install: dict = {}
    for e in journal.events():  # most-recent-first; oldest wins by overwrite
        if e.get("action") in ("install", "import") and e.get("subject"):
            first_install[e["subject"]] = e

    records, failures = [], 0
    for name, entry in targets:
        ev = first_install.get(name)
        rec = {"name": name,
               "who": (ev or {}).get("user", "?"),
               "when": entry.get("installed_at", "?"),
               "tap": entry.get("tap", "?"),
               "commit": (entry.get("commit") or "")[:9],
               "sha256": (entry.get("sha256") or "")[:12]}
        if args.verify:
            sdir = store.skill_store_dir(name)
            rec["sha_ok"] = (sdir.is_dir()
                             and util.sha256_dir(sdir) == entry.get("sha256"))
            rec["journal"] = ev is not None
            if not rec["sha_ok"]:
                failures += 1
        records.append(rec)

    if args.json:
        print(json.dumps({"skills": records, "failed": failures}))
        return 1 if (args.verify and failures) else 0
    if not records:
        out.info("no skills installed")
        return 0
    out.table([(r["name"], r["who"], util.rel_time(r["when"]), r["tap"],
                r["commit"] or "-", r["sha256"]) for r in records],
              headers=("SKILL", "WHO", "WHEN", "TAP", "COMMIT", "SHA"))
    if args.verify:
        for r in records:
            if not r["sha_ok"]:
                out.warn("%s: store content no longer matches the lock sha" % r["name"])
            elif not r["journal"]:
                out.warn("%s: no journal record (installed before journaling?)" % r["name"])
            else:
                out.ok("%s attestation OK" % r["name"])
        return 1 if failures else 0
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
    for agent, adir in agents.enabled_agents().items():
        linked = sum(1 for n in expected
                     if (adir / n).is_symlink() and (adir / n).exists())
        full = linked == len(expected)
        coverage_ok = coverage_ok and full
        out.kv(agent, "%d/%d %s" % (linked, len(expected),
                                    out.role("✓", "success") if full
                                    else out.role("!", "warn")))

    drift_counts: dict = {}
    for name, entry in installed:
        st = _drift_status(name, entry)
        drift_counts[st] = drift_counts.get(st, 0) + 1
    out.kv("drift", " · ".join("%d %s" % (n, s)
                               for s, n in sorted(drift_counts.items())) or "—")

    decay_n = sum(1 for r in _decay_rows(Path.cwd()) if r["verdict"] == "decay")
    out.kv("decay", "%d candidate%s" % (decay_n, _s(decay_n)))

    broken = _broken_links()
    out.kv("broken links", str(len(broken)))

    last_sync = "never"
    if cloned and gitutil.has_git():
        stamps = []
        for tap in cloned:
            proc = gitutil.run(["-C", str(tap.path), "log", "-1", "--format=%ct"],
                               check=False)
            if proc.returncode == 0 and proc.stdout.strip().isdigit():
                stamps.append(int(proc.stdout.strip()))
        if stamps:
            iso = datetime.fromtimestamp(max(stamps), tz=timezone.utc
                                         ).strftime("%Y-%m-%dT%H:%M:%SZ")
            last_sync = util.rel_time(iso)
    out.kv("last tap sync", last_sync)

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
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
