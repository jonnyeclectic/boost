# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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
from pathlib import Path
from typing import Any

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
from ..core import rules as rules_mod
from ..errors import BoostError
from ._common import _iter_installed, _iter_installed_all, _s, _shadowed_kinds

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

    # Rules and workflows get the same content scan, over what is actually
    # materialized — the CLAUDE.md block or rendered command file is the text
    # the agent loads. One materialization per item suffices (every agent gets
    # the same content, rendered); quarantined items have no active artifacts.
    mat_scanned = 0
    for kind, section in (("rule", lockfile.installed_rules()),
                          ("workflow", lockfile.installed_workflows())):
        for name, entry in sorted(section.items()):
            if entry.get("quarantined"):
                continue
            mat_scanned += 1
            if name in pol.get("blocked_skills", []):
                add(name, "HIGH", "policy-blocked", "policy.json",
                    "%s is on the policy blocklist" % kind)
            for m in entry.get("materializations") or []:
                path = Path(m.get("path", ""))
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if m.get("mode") == rules_mod.MODE_CLAUDE:
                    text = rules_mod.read_block(text, name) or ""
                where = "%s %s" % (kind, path.name)
                for pat, severity, label in _AUDIT_PATTERNS:
                    for hit in pat.finditer(text):
                        line_no = text.count("\n", 0, hit.start()) + 1
                        line = text.splitlines()[line_no - 1].strip()
                        add(name, severity, label,
                            "%s:%d" % (where, line_no), line[:90])
                for i, line in enumerate(text.splitlines(), 1):
                    if _CRED_POST.search(line) and _CRED_HINT.search(line):
                        add(name, "MED", "credential-exfil",
                            "%s:%d" % (where, i), line.strip()[:90])
                break  # identical content per agent — one scan is the signal

    counts = {"HIGH": 0, "MED": 0, "LOW": 0}
    for fs in findings.values():
        for f in fs:
            counts[f["severity"]] += 1

    scanned = len(installed) + mat_scanned
    if args.json:
        print(json.dumps({"skills_scanned": len(installed),
                          "materialized_scanned": mat_scanned,
                          "findings": findings, "counts": counts}))
        return 1 if counts["HIGH"] or counts["MED"] else 0

    out.heading("safety audit — %d item%s" % (scanned, _s(scanned)))
    if not findings:
        out.ok("no safety findings across %d item%s" % (scanned, _s(scanned)))
        return 0
    for name in sorted(findings):
        print("  " + out.c(name, out.BOLD))
        for f in findings[name]:
            print("    %s %s  %s  %s"
                  % (out.role(f["severity"].ljust(4), _SEV_ROLE[f["severity"]]),
                     f["label"], out.role(f["file"], "muted"), f["snippet"]))
    out.info("%d high · %d medium · %d low across %d item%s"
             % (counts["HIGH"], counts["MED"], counts["LOW"],
                scanned, _s(scanned)))
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
    # Quarantine removes a skill's active links on purpose — pairing it as a
    # conflict source or target would report a finding `boost quarantine`
    # (its own documented remedy) can never clear. Non-quarantined skills are
    # still checked against a quarantined peer's *declared* conflicts via
    # `_installed_conflicts`, so only the pairing set is trimmed here.
    active_names = [n for n, lk in installed.items() if not lk.get("quarantined")]
    for name, peer in trustaudit.conflict_pairs(active_names,
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

    # A named item may be installed at user OR project scope. Validate against
    # both up front so `boost verify <vendored-skill>` doesn't wrongly error
    # "not installed", and only hand user-scope names to the iterator. User
    # scope resolves through find_any: an installed rule or workflow is
    # exactly as verifiable as a skill, and "not installed" for one was the
    # roadmap card's headline lie.
    pbase, pskills = integrity.project_skills()
    if args.names:
        unknown = [n for n in args.names
                   if lockfile.find_any(n) is None and n not in pskills]
        if unknown:
            raise BoostError("not installed: %s" % ", ".join(unknown),
                            hint="see what is with `boost list`")
    user_names = [n for n in (args.names or [])
                  if lockfile.find_any(n) is not None]

    results: list[dict[str, Any]] = []
    for kind, name, entry in _iter_installed_all(
            user_names or (None if not args.names else [])):
        missing_fields = [f for f in ("version", "tap", "sha256", "installed_at")
                          if not entry.get(f)]
        # Digest check lives in core.integrity now (the same call the read
        # commands enforce with), so verify reports exactly what enforcement
        # acts on. An UNLOCKED entry has no digest to compare — surface it as a
        # missing field rather than a false "ok".
        if kind == "skill":
            status = integrity.status(name, entry)
            if status == integrity.STATUS_UNLOCKED and "sha256" not in missing_fields:
                missing_fields.append("sha256")
        else:
            status = integrity.materialized_status(name, entry)
            if status == integrity.STATUS_UNLOCKED:
                missing_fields.append("materialization sha256")
        commit_pin = integrity.commit_status(name, entry)
        results.append({"name": name, "kind": kind, "status": status,
                        "scope": "user", "missing_fields": missing_fields,
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
        results.append({"name": name, "kind": "skill", "status": status,
                        "scope": "project", "missing_fields": missing_fields,
                        "commit_pin": None})

    bad = [r for r in results
           if r["status"] not in ("ok", "quarantined") or r["missing_fields"]
           or r["commit_pin"] == integrity.STATUS_MODIFIED]
    if args.json:
        print(json.dumps({"skills": results, "failed": len(bad)}))
        return 1 if bad else 0

    if not results:
        out.info("nothing installed")
        return 0
    width = max(len(r["name"]) for r in results)
    status_role = {"ok": "success", "modified": "warn", "missing": "danger",
                   "unlocked": "warn", "quarantined": "muted"}
    for r in results:
        bits = []
        if r.get("kind") not in (None, "skill"):
            bits.append(r["kind"])
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
        out.warn("%d of %d item%s failed verification"
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
        for kind, section in lockfile.all_installed().items():
            for name, rec in sorted(section.items()):
                if not rec.get("quarantined"):
                    continue
                evs = journal.events(action="quarantine", subject=name)
                since = util.rel_time(evs[0].get("ts", "")) if evs else "?"
                rows.append((name, kind, rec.get("version", "?"),
                             rec.get("tap", "?"), since))
        if not rows:
            out.info("nothing in quarantine")
            return 0
        out.table(rows, headers=("NAME", "KIND", "VERSION", "TAP", "SINCE"))
        return 0

    if args.release:
        name = args.release
        found = lockfile.find_any(name)
        if not found:
            raise BoostError("%s is not installed" % name,
                            hint="see what is with `boost list`")
        kind, entry = found
        if not entry.get("quarantined"):
            # The bare name resolves skill-first, but --release means "the
            # quarantined one": a rule shadowed by a same-named skill would
            # otherwise be unreleasable by the exact command every hint names.
            for okind, section in lockfile.all_installed().items():
                other = section.get(name)
                if okind != kind and other is not None and other.get("quarantined"):
                    kind, entry = okind, other
                    break
        if not entry.get("quarantined"):
            out.warn("%s is not quarantined" % name)
            return 0
        if kind == "skill":
            res = store.link_agents(name)
            entry["quarantined"] = False
            entry["agents"] = res.linked
            lockfile.set_skill(name, entry)
            journal.log("release", name)
            out.ok("released %s (linked: %s)"
                   % (name, ", ".join(res.linked) or "none"))
        else:
            restored = store.release_materialized(kind, name, entry)
            out.ok("released %s %s (restored: %s)"
                   % (kind, name, ", ".join(restored) or "none"))
        return 0

    name = args.name
    found = lockfile.find_any(name)
    if not found:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    kind, entry = found
    for other in _shadowed_kinds(name, kind):
        out.warn("a %s named %s is also installed — this quarantines the %s "
                 "only; the %s stays active" % (other, name, kind, other))
    if entry.get("quarantined"):
        # A quarantined entry whose artifacts are still on disk is an
        # interrupted quarantine (stash persisted, removal did not finish) —
        # finish it rather than reporting the half-armed state as done.
        if kind != "skill" and store.stale_quarantine_artifacts(name, entry):
            store.quarantine_materialized(kind, name, entry)
            out.ok("finished an interrupted quarantine of %s %s"
                   % (kind, name))
            return 0
        out.warn("%s is already quarantined" % name)
        return 0
    if kind == "skill":
        store.unlink_agents(name)
        entry["quarantined"] = True
        lockfile.set_skill(name, entry)
        journal.log("quarantine", name)
        out.ok("quarantined %s (store intact, links removed)" % name)
    else:
        # A rule/workflow has no store copy to keep — the artifact is stashed
        # on the lock entry and `--release` restores it byte-for-byte.
        store.quarantine_materialized(kind, name, entry)
        out.ok("quarantined %s %s (content stashed, materializations removed)"
               % (kind, name))
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

    targets = _iter_installed_all([args.name] if args.name else None)
    first_install: dict = {}
    for e in journal.events():  # most-recent-first; oldest wins by overwrite
        if e.get("action") in ("install", "import") and e.get("subject"):
            first_install[e["subject"]] = e

    records, failures = [], 0
    for kind, name, entry in targets:
        ev = first_install.get(name)
        rec = {"name": name, "kind": kind,
               "who": (ev or {}).get("user", "?"),
               "when": entry.get("installed_at", "?"),
               "tap": entry.get("tap", "?"),
               "commit": (entry.get("commit") or "")[:9],
               "sha256": (entry.get("sha256") or "")[:12]}
        if args.verify:
            if kind == "skill":
                sdir = store.skill_store_dir(name)
                rec["sha_ok"] = (sdir.is_dir()
                                 and util.sha256_dir(sdir) == entry.get("sha256"))
            else:
                # The artifact the agent loads, against the hash recorded when
                # it was written. UNLOCKED (a pre-hash entry) never fails.
                rec["sha_ok"] = integrity.materialized_status(name, entry) not in (
                    integrity.STATUS_MODIFIED, integrity.STATUS_MISSING)
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
    # Kind folds into the name cell only when it is not a skill, so the
    # everyday all-skills table keeps its width and nothing truncates.
    out.table([(r["name"] if r["kind"] == "skill"
                else "%s (%s)" % (r["name"], r["kind"]),
                r["who"], util.rel_time(r["when"]),
                r["tap"], r["commit"] or "-", r["sha256"]) for r in records],
              headers=("NAME", "WHO", "WHEN", "TAP", "COMMIT", "SHA"))
    if args.verify:
        for r in records:
            if not r["sha_ok"]:
                out.warn("%s: %s content no longer matches the lock sha"
                         % (r["name"], "store" if r["kind"] == "skill"
                            else "materialized"))
            elif not r["journal"]:
                out.warn("%s: no journal record (installed before journaling?)" % r["name"])
            else:
                out.ok("%s attestation OK" % r["name"])
        return 1 if failures else 0
    return 0
