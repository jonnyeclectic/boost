"""Installed-skill safety & integrity commands — audit, verify, attest, quarantine.

Lifted out of ``quality.py`` (which had grown to fifteen commands): these four
all answer "is what I have installed still what it claims to be?" — a content
safety scan, a lock-file integrity check, the install attestation record, and
quarantine. Tap-side provenance (``trust``) and the health/diagnostics commands
stay in ``quality.py``.
"""
from __future__ import annotations

import json
import re
import time
from contextlib import suppress
from typing import Any, Dict, List

from .. import cliparse
from ..core import (
    catalog,
    frontmatter,
    gitutil,
    integrity,
    journal,
    lockfile,
    policy,
    provenance,
    registry,
    staleness,
    store,
    trustaudit,
    util,
)
from ..core import output as out
from ..errors import BoostError
from ._common import _iter_installed, _s

# --- audit: dangerous-content patterns ------------------------------------

_AUDIT_PATTERNS = [
    (re.compile(r"(?:curl|wget)[^|\n]*\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b"),
     "HIGH", "remote-exec"),
    (re.compile(r"rm\s+-(?:rf|fr)\s+(?:/|~)(?=[\s'\";`)]|$)", re.MULTILINE),
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


def cmd_audit(argv):
    ap = cliparse.parser(
        prog="boost audit",
        description="Check installed skills against a safety blocklist")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--skills", action="store_true",
                    help="trust/staleness report for installed skills instead "
                         "of the content scan")
    args = ap.parse_args(argv)

    if args.skills:
        return _trust_audit(args.json)

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


# --- audit --skills: trust & staleness across the whole installed set ------
#
# The signals already existed, one per command: `trust` reports tap signing,
# `outdated` reports drift vs the tap, `deps` shows the conflicts: graph. This
# gathers all three over the installed set and hands the decision to
# core/trustaudit.py, which is where every branch of it is unit-tested.

_TRUST_ROLE = {trustaudit.HIGH: "danger", trustaudit.MED: "warn",
               trustaudit.LOW: "muted"}


def _tap_age_days(tap):
    """Days since a tap clone's last commit, or ``None`` when unknowable."""
    try:
        proc = gitutil.run(["-C", str(tap.path), "log", "-1", "--format=%ct"],
                           check=False)
    except BoostError:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        committed = int(proc.stdout.strip())
    except ValueError:
        return None
    return max(0, int((time.time() - committed) // 86400))


def _tap_signals(tap_name, cache):
    """``(provenance status, age in days, HEAD commit)`` for a tap, memoized.

    A tap boost cannot read — unknown name, never cloned — yields
    ``(None, None, "")``, which ``trustaudit`` renders as "signature cannot be
    checked" rather than silently passing.
    """
    if tap_name not in cache:
        try:
            tap = registry.get(tap_name)
        except BoostError:
            cache[tap_name] = (None, None, "")
        else:
            cache[tap_name] = ((provenance.verify_dir(tap.path).status,
                                _tap_age_days(tap), gitutil.head_commit(tap.path))
                               if tap.is_cloned else (None, None, ""))
    return cache[tap_name]


def _upstream_reason(name, lk, tap_name, head):
    """``staleness.upstream_reason`` for one installed skill, or ``None``.

    Same signal-gathering order as ``cmd_outdated`` so the two commands can
    never disagree about whether a skill is behind its tap.
    """
    matches = [e for e in catalog.find(name) if e["tap"] == tap_name]
    if not matches:
        return None
    entry = matches[0]
    latest = str(entry.get("version") or "0.0.0")
    installed_v = str(lk.get("version") or "0.0.0")
    src_sha = None
    if not util.semver_gt(latest, installed_v) and head and head != lk.get("commit"):
        try:
            src_sha = util.sha256_dir(store.source_dir_for(entry))
        except BoostError:
            return None  # source checkout is gone; `verify` owns that finding
    return staleness.upstream_reason(installed_v, latest, lk.get("commit", ""),
                                     head, lk.get("sha256", ""), src_sha)


def _installed_conflicts(names):
    """A ``conflicts_of`` callable reading each installed skill's own copy.

    Reads the store copy rather than the catalog on purpose: the audit is about
    what is *installed*, which can be an older revision than the tap now
    advertises.
    """
    cache: dict = {}

    def conflicts_of(name):
        if name not in cache:
            meta: dict = {}
            # unreadable store copy: `verify` owns that finding, not this
            with suppress(OSError, BoostError):
                text = (store.skill_store_dir(name) / "SKILL.md").read_text(
                    encoding="utf-8", errors="replace")
                meta, _body = frontmatter.parse(text)
            cache[name] = trustaudit.relation_list(meta, "conflicts")
        return cache[name]

    return conflicts_of


def _trust_audit(as_json: bool) -> int:
    """`boost audit --skills` — one trust-health answer for the installed set."""
    installed = dict(_iter_installed())
    peers: dict = {}
    for name, peer in trustaudit.conflict_pairs(list(installed),
                                                _installed_conflicts(installed)):
        peers.setdefault(name, []).append(peer)

    taps: dict = {}
    findings: dict = {}
    for name, lk in sorted(installed.items()):
        tap_name = str(lk.get("tap") or "local")
        is_local = tap_name == "local"
        status, age, head = ((None, None, "") if is_local
                             else _tap_signals(tap_name, taps))
        rows = trustaudit.skill_findings(
            is_local=is_local, provenance_status=status, tap_age_days=age,
            upstream_reason=(None if is_local
                             else _upstream_reason(name, lk, tap_name, head)),
            conflicts_with=peers.get(name, ()))
        if rows:
            findings[name] = rows

    counts = trustaudit.count_severities(findings)
    rc = trustaudit.exit_code(counts)
    if as_json:
        print(json.dumps({"skills_scanned": len(installed),
                          "findings": findings, "counts": counts}, indent=2))
        return rc
    return _render_trust_audit(installed, findings, counts, rc)


def _render_trust_audit(installed, findings, counts, rc: int) -> int:
    """Human rendering for `boost audit --skills`."""
    total = len(installed)
    out.heading("trust audit — %d skill%s" % (total, _s(total)))
    if not total:
        out.info("nothing installed yet — `boost install <skill>` to start")
        return rc
    if not findings:
        out.ok("all %d installed skill%s signed, current and conflict-free"
               % (total, _s(total)))
        return rc
    for name in sorted(findings):
        print("  " + out.c(name, out.BOLD))
        for f in findings[name]:
            print("    %s %s  %s"
                  % (out.role(f["severity"].ljust(4), _TRUST_ROLE[f["severity"]]),
                     f["label"], out.role(f["detail"], "muted")))
    print()
    out.verdict(trustaudit.is_healthy(counts),
                "%d high · %d medium · %d low across %d of %d skill%s"
                % (counts[trustaudit.HIGH], counts[trustaudit.MED],
                   counts[trustaudit.LOW], len(findings), total, _s(total)))
    return rc


def cmd_verify(argv):
    ap = cliparse.parser(
        prog="boost verify",
        description="Validate skill quality & lock-file integrity")
    ap.add_argument("names", nargs="*", metavar="NAME")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    # A named skill may be installed at user OR project scope. Validate against
    # both up front so `boost verify <vendored-skill>` doesn't wrongly error
    # "not installed", and only hand user-scope names to _iter_installed.
    pbase, pskills = integrity.project_skills()
    if args.names:
        unknown = [n for n in args.names
                   if n not in lockfile.installed() and n not in pskills]
        if unknown:
            raise BoostError("not installed: %s" % ", ".join(unknown),
                            hint="see what is with `boost list`")
    user_names = [n for n in (args.names or []) if n in lockfile.installed()]

    results: List[Dict[str, Any]] = []
    for name, entry in _iter_installed(user_names or (None if not args.names else [])):
        missing_fields = [f for f in ("version", "tap", "sha256", "installed_at")
                          if not entry.get(f)]
        # Digest check lives in core.integrity now (the same call the read
        # commands enforce with), so verify reports exactly what enforcement
        # acts on. An UNLOCKED entry has no digest to compare — surface it as a
        # missing field rather than a false "ok".
        status = integrity.status(name, entry)
        if status == integrity.STATUS_UNLOCKED and "sha256" not in missing_fields:
            missing_fields.append("sha256")
        commit_pin = integrity.commit_status(name, entry)
        results.append({"name": name, "status": status, "scope": "user",
                        "missing_fields": missing_fields,
                        "commit_pin": commit_pin})

    # Vendored, project-scoped skills live in the repo's own lock, not the user's
    # — and they are exactly the ones worth verifying, since they arrive by PR
    # and run on every teammate. (pbase/pskills resolved above.)
    for name, entry in sorted(pskills.items()):
        if args.names and name not in args.names:
            continue
        status = integrity.project_status(entry, pbase)
        missing_fields = [f for f in ("version", "tap", "sha256", "installed_at")
                          if not entry.get(f)]
        if status == integrity.STATUS_UNLOCKED and "sha256" not in missing_fields:
            missing_fields.append("sha256")
        results.append({"name": name, "status": status, "scope": "project",
                        "missing_fields": missing_fields, "commit_pin": None})

    bad = [r for r in results if r["status"] != "ok" or r["missing_fields"]
           or r["commit_pin"] == integrity.STATUS_MODIFIED]
    if args.json:
        print(json.dumps({"skills": results, "failed": len(bad)}))
        return 1 if bad else 0

    if not results:
        out.info("no skills installed")
        return 0
    width = max(len(r["name"]) for r in results)
    status_role = {"ok": "success", "modified": "warn", "missing": "danger",
                   "unlocked": "warn"}
    for r in results:
        bits = []
        if r.get("scope") == "project":
            bits.append("project")
        if r["missing_fields"]:
            bits.append("missing lock fields: " + ", ".join(r["missing_fields"]))
        if r["commit_pin"] == integrity.STATUS_OK:
            bits.append("commit-pinned")
        elif r["commit_pin"] == integrity.STATUS_MODIFIED:
            bits.append("commit pin DRIFTED")
        note = ("  " + " · ".join(bits)) if bits else ""
        print("  %s  %s%s" % (r["name"].ljust(width),
                              out.role(r["status"], status_role.get(r["status"], "warn")),
                              out.role(note, "muted")))
    if bad:
        out.warn("%d of %d skill%s failed verification"
                 % (len(bad), len(results), _s(len(results))))
        return 1
    out.ok("lock file integrity OK")
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
        for name, rec in _iter_installed():
            if not rec.get("quarantined"):
                continue
            evs = journal.events(action="quarantine", subject=name)
            since = util.rel_time(evs[0].get("ts", "")) if evs else "?"
            rows.append((name, rec.get("version", "?"),
                         rec.get("tap", "?"), since))
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
