# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Team & Collaboration commands: cohort, profile, protocol, pulse, replay, who."""
from __future__ import annotations

import hashlib
import json
import operator
import platform
import shlex
import shutil
import stat
import sys
import urllib.parse
from typing import Any

from .. import cliparse
from ..core import (
    catalog,
    cohort,
    complete,
    dialog,
    integrity,
    journal,
    jsonstate,
    lockfile,
    paths,
    registry,
    store,
    util,
)
from ..core import output as out
from ..core import profiles as profile_rules
from ..errors import BoostError
from ._common import _s
from .pkg import _report_result, _warn_unwritable

_tilde = paths.tilde


def _resolve_entry(name: str, prefer_tap: str | None = None,
                   kind: str | None = None
                   ) -> tuple[dict | None, str | None]:
    """``(entry, why_not)`` for a recorded name (:func:`catalog.resolve_recorded`).

    ``(None, None)`` when no tap ships it; ``(None, reason)`` when one does
    but it cannot be the answer — ambiguous, or its recorded tap is gone —
    with the reason as one printable line.
    """
    try:
        return catalog.resolve_recorded(name, prefer_tap, kind), None
    except BoostError as e:
        return None, ("%s (%s)" % (e.message, e.hint) if e.hint
                      else e.message)


# ---------------------------------------------------------------- cohort

def _cohorts_path():
    return paths.state_dir() / "cohorts.json"


def _save_cohorts(cohorts: dict) -> None:
    """Write ``cohorts.json``, moving a corrupt one aside first.

    `create` over a file with a trailing comma used to read it as empty and
    write the one new cohort over every existing one, with no warning.
    """
    p = _cohorts_path()
    jsonstate.save(p, json.dumps(cohorts, indent=2) + "\n",
                   corrupt=cohort.load(p)[1] is not None, show=_tilde)


def _is_member(user: str, cohort_name: str, percent: int) -> bool:
    """Deterministic per user+cohort: stable across runs and machines."""
    digest = hashlib.sha256(("%s:%s" % (user, cohort_name)).encode()).hexdigest()
    return int(digest, 16) % 100 < percent


def cmd_cohort(argv) -> int:
    """boost cohort [list [NAME]|create NAME --skills a,b --percent N|delete NAME|status [NAME]|apply [NAME]]"""
    p = cliparse.parser(
        prog="boost cohort",
        description="Controlled skill rollouts & team A/B testing",
        epilog="Membership is a deterministic hash of user+cohort, so a 50% "
               "rollout lands on the same half of the team every time. "
               "This machine evaluates its own membership locally.")
    p.add_argument("action", nargs="?", default="list",
                   choices=["list", "create", "delete", "status", "apply"],
                   help="what to do (default: list; status is the same as list)")
    p.add_argument("name", type=util.nonempty_str, nargs="?",
                   help="cohort name (list/status: show only that cohort)")
    p.add_argument("--skills", type=util.nonempty_str, action="append", default=[],
                   help="with `create`: comma-separated skill names "
                        "(repeatable)")
    p.add_argument("--percent", type=int, default=None,
                   help="with `create`: rollout percentage (default 100)")
    p.add_argument("-y", "--yes", action="store_true",
                   help="`delete` without the confirmation prompt")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)
    if args.action != "create":
        stray = [f for f, v in (("--skills", args.skills),
                                ("--percent", args.percent is not None)) if v]
        if stray:
            p.error("%s only appl%s to `cohort create`"
                    % ("/".join(stray), "y" if len(stray) > 1 else "ies"))
    if args.percent is None:
        args.percent = 100

    cohorts, bad = cohort.load(_cohorts_path())
    # `create` replaces the file, so a corrupt one is quarantined by the
    # write; every other action reads cohorts that are not there to read.
    if bad is not None and args.action != "create":
        raise BoostError("cohorts are unreadable: %s" % bad,
                         hint="fix or remove %s — `boost cohort create` "
                              "moves it aside and starts a new one"
                              % _tilde(_cohorts_path()))
    user = util.user()

    if args.action == "create":
        if not args.name:
            p.error("create needs a cohort NAME")
        if not 0 <= args.percent <= 100:
            p.error("--percent must be 0-100")
        skills = cohort.parse_skills(args.skills)
        if not skills:
            p.error("create needs --skills a,b,...")
        for s in skills:
            if not catalog.find(s):
                # stderr: under --json, stdout holds the JSON object alone.
                out.warn("skill %r not found in any tap (kept anyway)" % s,
                         stream=sys.stderr)
        existing = cohorts.get(args.name)
        cohorts[args.name] = {
            "skills": skills, "percent": args.percent,
            # A second `create` over an existing cohort is a replacement, not
            # a new cohort — preserving `created` is what makes the "updated"
            # wording below honest instead of resetting a rollout's history.
            "created": existing["created"] if existing else util.now_iso(),
            "creator": user}
        _save_cohorts(cohorts)
        journal.log("cohort", args.name, op="create", percent=args.percent)
        member = _is_member(user, args.name, args.percent)
        if args.json:
            print(json.dumps({"name": args.name, "percent": args.percent,
                              "skills": skills, "updated": bool(existing),
                              "member": member}, indent=2))
            return 0
        if existing:
            out.ok("updated cohort %s (was %d%% / %d skill%s) — now %d%% "
                   "rollout, %d skill%s — you are %s"
                   % (args.name, existing["percent"], len(existing["skills"]),
                      _s(len(existing["skills"])), args.percent, len(skills),
                      _s(len(skills)), "IN" if member else "OUT"))
        else:
            out.ok("created cohort %s (%d%% rollout, %d skill%s) — you are %s"
                   % (args.name, args.percent, len(skills), _s(len(skills)),
                      "IN" if member else "OUT"))
        return 0

    if args.action == "delete":
        if not args.name:
            p.error("delete needs a cohort NAME")
        if args.name not in cohorts:
            raise BoostError("no cohort named %s" % args.name,
                            hint="list cohorts with `boost cohort list`")
        if not (args.yes or out.confirm("delete cohort %s?" % args.name,
                                        quiet=args.json)):
            if args.json:
                print(json.dumps({"name": args.name, "deleted": False,
                                  "cancelled": True}, indent=2))
                return 1
            out.info("cancelled")
            return 1
        del cohorts[args.name]
        _save_cohorts(cohorts)
        journal.log("cohort", args.name, op="delete")
        if args.json:
            print(json.dumps({"name": args.name, "deleted": True}, indent=2))
            return 0
        out.ok("deleted cohort %s" % args.name)
        return 0

    if args.action == "apply":
        targets = [args.name] if args.name else sorted(cohorts)
        if args.name and args.name not in cohorts:
            raise BoostError("no cohort named %s" % args.name,
                            hint="list cohorts with `boost cohort list`")
        if not targets:
            if args.json:
                print(json.dumps({"cohorts": []}, indent=2))
                return 0
            print(out.empty_state("no cohorts defined"))
            return 0
        applied = skipped = 0
        total_installed = total_present = total_missing = total_failed = 0
        per_cohort = []
        for cname in targets:
            spec = cohorts[cname]
            if not _is_member(user, cname, spec["percent"]):
                per_cohort.append({"cohort": cname, "member": False,
                                   "installed": [], "already_present": [],
                                   "not_found": [], "failed": []})
                if not args.json:
                    out.info(out.role("%s: not in the %d%% rollout — skipping"
                                   % (cname, spec["percent"]), "muted"))
                continue
            if not args.json:
                out.heading("cohort %s" % cname)
            installed_here, present_here, missing_here = [], [], []
            failed_here: list[str] = []
            for skill in spec["skills"]:
                # find_any, not installed(): a cohort item installed as a rule
                # or workflow would otherwise be re-installed on every apply.
                # The lock keys by the bare name, so a `tap:name` member never
                # matched and every apply after the first re-installed it —
                # and the "already installed" error aborted the cohort.
                # A qualifier naming another tap raises there; fall back to
                # the name as written so that member reports "not found"
                # instead of aborting every cohort after it.
                try:
                    key = store.installed_name(skill)
                except BoostError:
                    key = skill
                found = lockfile.find_any(key)
                if found is not None:
                    label = (skill if found[0] == "skill"
                             else "%s (%s)" % (skill, found[0]))
                    if not args.json:
                        out.info(out.role("%s already installed" % label, "muted"))
                    present_here.append(skill)
                    skipped += 1
                    continue
                entry, why = _resolve_entry(skill)
                if entry is None:
                    if not args.json:
                        out.warn("%s — skipped" % why if why else
                                 "%s not found in any tap — skipped" % skill,
                                 wrap=True)
                    missing_here.append(skill)
                    continue
                try:
                    res = store.install(entry)
                except BoostError as err:
                    # One refused member (a policy block, an unwritable
                    # store) used to abort the whole apply: earlier members
                    # stayed installed, later members and cohorts were never
                    # tried, and no summary, JSON or journal entry said so.
                    # Counted and carried on past, as `bundle install` does.
                    if not args.json:
                        out.warn("%s: %s" % (skill, err.message), wrap=True)
                    failed_here.append(skill)
                    continue
                if not args.json:
                    out.ok("installed %s → %s" % (skill, " · ".join(res.linked)))
                    _warn_unwritable(res)
                installed_here.append(skill)
                applied += 1
            per_cohort.append({"cohort": cname, "member": True,
                               "installed": installed_here,
                               "already_present": present_here,
                               "not_found": missing_here,
                               "failed": failed_here})
            journal.log("cohort", cname, op="apply",
                        installed=len(installed_here),
                        present=len(present_here),
                        missing=len(missing_here),
                        failed=len(failed_here))
            total_installed += len(installed_here)
            total_present += len(present_here)
            total_missing += len(missing_here)
            total_failed += len(failed_here)
        # #767's exit code is the substance of that PR — a cohort member no tap
        # can resolve must not read as success — so it applies under --json too:
        # an exit code that depended on the output format would undo it.
        if args.json:
            print(json.dumps({"cohorts": per_cohort, "installed": applied,
                              "already_present": skipped,
                              "failed": total_failed}, indent=2))
            return cohort.apply_exit_code(total_installed, total_present,
                                          total_missing, total_failed)
        out.info(cohort.apply_summary(total_installed, total_present,
                                      total_missing, total_failed))
        return cohort.apply_exit_code(total_installed, total_present,
                                      total_missing, total_failed)

    # list / status — a NAME narrows to that cohort, and one that does not
    # exist is an error rather than every other cohort's data under rc 0.
    if args.name and args.name not in cohorts:
        raise BoostError("no cohort named %s" % args.name,
                        hint="list cohorts with `boost cohort list`")
    rows = []
    data = []
    for cname in [args.name] if args.name else sorted(cohorts):
        spec = cohorts[cname]
        member = _is_member(user, cname, spec["percent"])
        data.append({"name": cname, "skills": spec["skills"],
                     "percent": spec["percent"], "member": member,
                     "created": spec.get("created", "")})
        rows.append((cname, ", ".join(spec["skills"]),
                     "%d%%" % spec["percent"],
                     out.role("IN", "success") if member else out.role("out", "muted")))
    if args.json:
        print(json.dumps(data, indent=2))
        return 0
    if not rows:
        print(out.empty_state(
            "no cohorts defined",
            hint="create one: `boost cohort create pilot --skills "
                 "tdd-workflow --percent 50`",
            wrap=True))
        return 0
    out.table(rows, headers=("COHORT", "SKILLS", "ROLLOUT", "YOU"),
              whole=("COHORT",))  # `cohort status|apply|delete <name>`
    print()
    out.dim("membership = sha256(user:cohort) % 100 < rollout · apply with `boost cohort apply`")
    return 0


# ---------------------------------------------------------------- profile

def _profile_path(name: str):
    # The file name is checked, not just the slug: a 251-255 byte slug is a
    # legal name until ".json" pushes the component past the limit.
    slug = util.resolve_slug(name, what="profile name")
    return util.check_path_length(paths.profiles_dir() / (slug + ".json"),
                                  what="profile file name")


def _read_profile(path) -> tuple[dict | None, str | None]:
    """:func:`jsonstate.read_object`, plus a ``skills`` map of objects.

    ``show``/``diff``/``use`` and the ``save`` probe all walk ``skills`` and
    call ``.get`` on each record, so ``[]``, ``{"skills": 3}`` or a record
    that is a string crashed them at exit 70 while ``list`` already showed
    the same file as unreadable. One check, shared, keeps them agreeing.
    """
    data, err = jsonstate.read_object(path)
    if data is not None:
        bad = jsonstate.object_map_error(data, "skills")
        if bad is not None:
            return None, "%s: %s" % (path, bad)
    return data, err


def _load_profile(name: str) -> dict:
    p = _profile_path(name)
    data, err = _read_profile(p)
    if err is not None:
        raise BoostError("profile %s is unreadable: %s" % (name, err),
                         hint="replace it with `boost profile save %s`, or "
                              "remove it with `boost profile delete %s`"
                              % (name, name))
    if data is None:
        raise BoostError("no profile named %s" % name,
                        hint="list profiles with `boost profile list`")
    return data


def _profile_row(entry: dict) -> dict:
    """What a profile records about one installed skill.

    Tap and version, plus what ``profile use`` needs to put it back as it was
    rather than merely present: the source ``commit`` it was installed at,
    its agent scope (``only_agents``) and its version pin. Optional keys are
    written only when set, so a profile without them reads as before.
    """
    row = {"tap": entry.get("tap", "local"),
           "version": entry.get("version", "0.0.0")}
    if entry.get("commit"):
        row["commit"] = entry["commit"]
    if entry.get("only_agents") is not None:
        row["only_agents"] = list(entry["only_agents"])
    if entry.get("pinned"):
        row["pinned"] = True
    return row


def _row_differs(saved: dict, entry: dict) -> str:
    """Why an installed ``entry`` is not the profile's ``saved`` row, or "".

    A version first; failing that a recorded commit, since a tap that moved
    can change a skill without bumping its version. A side that records no
    commit (an older profile, a local import) is no evidence either way.
    """
    if str(saved.get("version")) != str(entry.get("version")):
        return "version differs"
    have, want = entry.get("commit"), saved.get("commit")
    if have and want and have != want:
        return "commit differs"
    return ""


def _at(row: dict) -> str:
    """`` @abc1234`` for a row that records its commit, else ""."""
    return " @%s" % row["commit"][:7] if row.get("commit") else ""


def _profile_diff(profile: dict):
    """-> (missing, extras, changed, other_kind): profile vs installed.

    ``other_kind`` maps a profile name to the kind it is installed as when
    that kind is not "skill" — reporting those as missing would tell the user
    to install something `boost list` already shows.

    ``extras`` are *active* skills only. `profile save` leaves sidelined
    skills out (``split_sidelined``) and `profile use` sidelines extras, so
    counting a sidelined one as an extra made `diff` report a mismatch right
    after either — and made every repeat `use` sideline it again.
    """
    current = lockfile.installed()
    active, _ = lockfile.split_sidelined(current)
    want = profile.get("skills", {})
    missing, other_kind = [], {}
    for n in sorted(want):
        if n in current:
            continue
        found = lockfile.find_any(n)
        if found is not None:
            other_kind[n] = found[0]
        else:
            missing.append(n)
    extras = sorted(n for n in active if n not in want)
    changed = sorted(n for n in want
                     if n in current and _row_differs(want[n], current[n]))
    return missing, extras, changed, other_kind


def cmd_profile(argv) -> int:
    """boost profile [list|save NAME|use NAME [--prune]|show NAME|diff NAME|delete NAME]"""
    p = cliparse.parser(
        prog="boost profile",
        description="Named skill profiles for context switching")
    p.add_argument("action", nargs="?", default="list",
                   choices=["list", "save", "use", "show", "diff", "delete"],
                   help="what to do (default: list)")
    p.add_argument("name", type=util.nonempty_str, nargs="?", help="profile name")
    p.add_argument("--prune", action="store_true",
                   help="with `use`: fully uninstall skills not in the profile")
    p.add_argument("-y", "--yes", action="store_true",
                   help="`delete` and `use --prune` without the confirmation "
                        "prompt")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)

    if args.prune and args.action != "use":
        # Accepted and ignored, `profile save --prune` reported success and
        # left the user believing a prune had happened.
        p.error("--prune only applies to `profile use`")
    if args.action != "list" and not args.name:
        p.error("%s needs a profile NAME" % args.action)

    if args.action == "list":
        profiles: list[dict[str, Any]] = []
        for f in sorted(paths.profiles_dir().glob("*.json")):
            data, _err = _read_profile(f)
            if data is None:
                # Surfaced rather than skipped: a corrupt profile used to be
                # invisible here yet still block `profile delete` (it parsed
                # the file again as an existence check) — see `delete` below.
                profiles.append({"name": f.stem, "skills": None,
                                 "saved": None, "unreadable": True})
                continue
            profiles.append({"name": data.get("name", f.stem),
                             "skills": len(data.get("skills", {})),
                             "saved": data.get("saved", "?"),
                             "unreadable": False})
        # Sort by the name shown on screen, not the slugged filename that put
        # them there — glob order otherwise prints rows in an order that
        # matches nothing a reader sees (`daily, mixed, !!!, Work Profile`).
        profiles.sort(key=operator.itemgetter("name"))
        if args.json:
            print(json.dumps(profiles, indent=2))
            return 0
        if not profiles:
            print(out.empty_state(
                "no profiles saved",
                hint="snapshot the current setup: `boost profile save daily`",
                wrap=True))
            return 0
        rows = [(pr["name"],
                str(pr["skills"]) if not pr["unreadable"] else "?",
                util.rel_time(pr["saved"]) if not pr["unreadable"]
                else out.role("(unreadable)", "danger"))
               for pr in profiles]
        out.table(rows, headers=("PROFILE", "SKILLS", "SAVED"),
                  whole=("PROFILE",))  # `profile use|show|diff <name>`
        return 0

    if args.action == "save":
        # The active set only: a sidelined skill left out here is an "extra"
        # to `profile use`, which sidelines it again — the saved state, exactly.
        installed, set_aside = lockfile.split_sidelined(lockfile.installed())
        path = _profile_path(args.name)
        old, bad = _read_profile(path)
        was = len(old.get("skills", {})) if old is not None else None
        profile = {"name": args.name, "saved": util.now_iso(), "user": util.user(),
                   "skills": {n: _profile_row(e)
                              for n, e in installed.items()}}
        # A corrupt one is still fine to replace — but not to destroy: the
        # bad bytes go aside, the way every other state file's writer does.
        jsonstate.save(path, json.dumps(profile, indent=2) + "\n",
                       corrupt=bad is not None, noun="profile", show=_tilde)
        journal.log("profile", args.name, op="save", skills=len(installed))
        n_rules = len(lockfile.installed_rules())
        n_workflows = len(lockfile.installed_workflows())
        if args.json:
            print(json.dumps({"name": args.name, "updated": was is not None,
                              "was_skills": was, "skills": len(installed),
                              "sidelined_not_captured": set_aside,
                              "rules_not_captured": n_rules,
                              "workflows_not_captured": n_workflows}, indent=2))
            return 0
        if was is not None:
            out.ok("updated profile %s (was %d skill%s, now %d skill%s)"
                   % (args.name, was, _s(was), len(installed), _s(len(installed))))
        else:
            out.ok("saved profile %s (%d skill%s)"
                   % (args.name, len(installed), _s(len(installed))))
        if set_aside:
            out.info("not captured: %d sidelined skill%s (%s) — `profile use "
                     "%s` keeps %s off" % (len(set_aside), _s(len(set_aside)),
                                           ", ".join(set_aside), args.name,
                                           "them" if len(set_aside) != 1
                                           else "it"), wrap=True)
        if n_rules or n_workflows:
            out.warn("%d rule%s and %d workflow%s not captured — profiles "
                     "carry skills only"
                     % (n_rules, _s(n_rules), n_workflows, _s(n_workflows)))
        return 0

    if args.action == "show":
        profile = _load_profile(args.name)
        if args.json:
            print(json.dumps(profile, indent=2))
            return 0
        out.heading("profile %s" % profile.get("name", args.name))
        out.kv("saved", "%s by %s" % (util.rel_time(profile.get("saved", "")),
                                      profile.get("user", "?")))
        rows = [(n, s.get("version", "?"), s.get("tap", "?"))
                for n, s in sorted(profile.get("skills", {}).items())]
        if rows:
            print()
            out.table(rows, headers=("SKILL", "VERSION", "TAP"),
                      whole=("SKILL",))  # `boost install <name>`
        return 0

    if args.action == "diff":
        profile = _load_profile(args.name)
        missing, extras, changed, other_kind = _profile_diff(profile)
        if args.json:
            print(json.dumps({"missing": missing, "extras": extras,
                              "changed": changed, "other_kind": other_kind},
                             indent=2))
            return 0
        if not (missing or extras or changed or other_kind):
            out.ok("current setup matches profile %s" % args.name)
            return 0
        for n in missing:
            out.info(out.role("+ %s" % n, "success") + out.role("  (in profile, not installed)", "muted"))
        for n in extras:
            out.info(out.role("- %s" % n, "danger") + out.role("  (installed, not in profile)", "muted"))
        current = lockfile.installed()
        want = profile.get("skills", {})
        for n in changed:
            out.info(out.role("~ %s" % n, "warn") + out.role(
                "  (%s)" % _row_differs(want[n], current[n]), "muted"))
        for n, kind in sorted(other_kind.items()):
            out.info(out.role("~ %s" % n, "warn")
                     + out.role("  (in profile, installed as a %s — profiles "
                                "carry skills only)" % kind, "muted"))
        return 0

    if args.action == "delete":
        path = _profile_path(args.name)
        if not path.exists():
            raise BoostError("no profile named %s" % args.name,
                            hint="list profiles with `boost profile list`")
        if not (args.yes or out.confirm("delete profile %s?" % args.name,
                                        quiet=args.json)):
            if args.json:
                print(json.dumps({"name": args.name, "deleted": False,
                                  "cancelled": True}, indent=2))
                return 1
            out.info("cancelled")
            return 1
        path.unlink()
        journal.log("profile", args.name, op="delete")
        if args.json:
            print(json.dumps({"name": args.name, "deleted": True}, indent=2))
            return 0
        out.ok("deleted profile %s" % args.name)
        return 0

    # use
    profile = _load_profile(args.name)
    missing, extras, changed, other_kind = _profile_diff(profile)
    want = profile.get("skills", {})
    for n, kind in sorted(other_kind.items()):
        # Installing it as a skill would shadow the rule/workflow of the same
        # name; say why it is skipped rather than skipping silently.
        if not args.json:
            out.info("%s is installed as a %s — profiles carry skills only, "
                     "leaving it as-is" % (n, kind))
    installed_now: list[str] = []
    not_found: list[str] = []
    failed: list[str] = []
    for n in missing:
        entry, why = _resolve_entry(n, prefer_tap=want[n].get("tap"),
                                   kind=catalog.KIND_SKILL)
        if entry is None:
            if not args.json:
                out.warn("%s — skipped" % why if why else
                         "%s is in the profile but not in any tap — skipped"
                         % n, wrap=True)
            not_found.append(n)
            continue
        saved = want[n]
        # Into the agents the profile recorded: a skill saved linked for one
        # agent came back linked for every agent, so the switch rewrote the
        # scope it was meant to restore.
        try:
            res = store.install(entry,
                                only_agents=saved.get("only_agents") or None)
        except BoostError as err:
            # A refused member (policy, an unwritable store) used to abort the
            # switch halfway: later members untried, extras still linked, no
            # JSON. Counted and carried past, as `bundle install` does.
            if not args.json:
                out.warn("%s: %s" % (n, err.message), wrap=True)
            failed.append(n)
            continue
        if saved.get("pinned"):
            lockfile.update_skill(n, lambda row: row.update(pinned=True))
        if not args.json:
            out.ok("installed %s → %s" % (n, " · ".join(res.linked)))
            _warn_unwritable(res)
        installed_now.append(n)
        why = _row_differs(saved, lockfile.get_skill(n) or entry)
        if why:
            # The tap has moved since the save, so what came back is not what
            # was saved — said here, not left for `profile diff` to find.
            changed.append(n)
            if not args.json:
                out.warn("%s (%s): profile has v%s%s, installed v%s%s — its "
                         "tap has moved since the profile was saved"
                         % (n, why, out.plain(saved.get("version")),
                            _at(saved), out.plain(entry.get("version")),
                            _at(lockfile.get_skill(n) or {})), wrap=True)
    for n in (c for c in changed if c not in installed_now):
        # Mirrors `diff`'s "~ NAME (version differs)" — `use` used to discard
        # this and switch silently, leaving the drift `diff` warns about
        # invisible from the command that is supposed to resolve it. Prose, so
        # it is gated like every other line here; `--json` callers already read
        # the same drift out of `profile diff`.
        if not args.json:
            out.warn("%s (%s)" % (n, _row_differs(
                want[n], lockfile.get_skill(n) or {})))
    for n in sorted(want):
        if lockfile.get_skill(n) and not (lockfile.get_skill(n) or {}).get("quarantined"):
            # unsideline, not link_agents: a skill this profile wants may have
            # been sidelined by an earlier `profile use` (or by `focus` /
            # `context`), and relinking without clearing `sidelined_by` left
            # `list`/`doctor` still calling it set aside.
            _warn_unwritable(store.unsideline(n),
                             stream=sys.stderr if args.json else None)
    uninstalled: list[str] = []
    sidelined: list[str] = []
    kept_extras = False
    only: list[str] = []
    # --prune removes every skill the profile does not name, sidelined ones
    # included — a skill an earlier `use` set aside is still installed. The
    # sideline step takes only the active extras: re-sidelining one already
    # set aside reported a change on every repeat of the same switch.
    prunable = (sorted(n for n in lockfile.installed() if n not in want)
                if args.prune else extras)
    resolved = sum(1 for n in want if lockfile.find_any(n) is not None)
    left_linked: list[str] = []
    if not profile_rules.sideline_allowed(resolved, len(not_found), len(failed)):
        # Nothing the profile names could be installed, so the switch would
        # trade the user's whole setup for nothing.
        left_linked, prunable = extras, []
        if extras and not args.json:
            out.warn("nothing in profile %s could be installed — left %d "
                     "skill%s linked: %s"
                     % (args.name, len(extras), _s(len(extras)),
                        ", ".join(extras)), wrap=True)
    if prunable:
        # A skill `boost sync` recorded where it found it has no copy outside
        # the store, so --prune would delete it for good as a side effect of
        # switching profiles. It is set aside like any extra instead.
        only = [n for n in prunable
                if args.prune and store.only_copy(n, lockfile.get_skill(n) or {})]
        doomed = [n for n in prunable if n not in only]
        # A declined --prune confirm used to leave extras fully installed
        # and linked, then still print the unconditional "switched" below —
        # a checkmark for a state the machine was not in. Falling through to
        # the same sideline extras get without --prune keeps that claim true
        # either way, without a second prompt. `and` short-circuits, so no
        # prompt is raised when --prune was not asked for.
        pruned = args.prune and bool(doomed) and (args.yes or out.confirm(
            "uninstall %d skill%s not in the profile (%s)?"
            % (len(doomed), _s(len(doomed)), ", ".join(doomed)),
            quiet=args.json))
        if pruned:
            for n in doomed:
                store.uninstall(n, kind="skill")
                if not args.json:
                    out.ok("uninstalled %s" % n)
                uninstalled.append(n)
        else:
            # `kept_extras` keeps the meaning #804 published it with — the
            # user was asked to uninstall these and declined, so they are
            # still installed — and is now reported beside a populated
            # `sidelined`: kept, but unlinked. It stays False when --prune
            # was never passed, since nothing was ever kept against a no.
            kept_extras = bool(args.prune) and bool(doomed)
        if not args.json:
            for n in only:
                out.info("kept %s: the store holds its only copy — "
                         "`boost uninstall %s` deletes it" % (n, n))
        sidelined = [n for n in (only if pruned else prunable) if n in extras]
        for n in sidelined:
            store.sideline(n, "profile")
        if sidelined and not args.json:
            out.info("sidelined %d skill%s not in the profile (unlinked, still installed): %s"
                     % (len(sidelined), _s(len(sidelined)), ", ".join(sidelined)))
    journal.log("profile", args.name, op="use")
    if args.json:
        print(json.dumps({"name": args.name, "installed": installed_now,
                          "not_found": not_found, "failed": failed,
                          "uninstalled": uninstalled,
                          "sidelined": sidelined, "kept_extras": kept_extras,
                          "other_kind": other_kind, "differs": sorted(changed),
                          **({"only_copies": only} if only else {}),
                          **({"left_linked": left_linked} if left_linked
                             else {})}, indent=2))
        return profile_rules.use_exit_code(len(not_found), len(failed))
    # "switched" is a claim that this machine now is the profile; with a
    # member missing, refused, or at another version or commit it is not.
    summary = profile_rules.use_summary(args.name, len(not_found), len(failed),
                                   len(changed))
    if summary:
        out.warn(summary, wrap=True)
    else:
        out.ok("switched to profile %s" % args.name)
    return profile_rules.use_exit_code(len(not_found), len(failed))


# ---------------------------------------------------------------- protocol

def _handler_script():
    return paths.state_dir() / "boost-protocol-handler.sh"


def _desktop_file():
    return paths.home() / ".local" / "share" / "applications" / "boost-protocol.desktop"


def _parse_boost_url(url: str):
    """boost://install/<skill> | boost://install/<tap>:<skill> | boost://tap/<owner>/<repo>
    -> (verb, argument)"""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "boost":
        raise BoostError("not a boost:// URL: %s" % url,
                        hint="expected boost://install/<skill> or boost://tap/<owner>/<repo>")
    verb = parsed.netloc
    arg = urllib.parse.unquote(parsed.path.lstrip("/"))
    if verb not in ("install", "tap") or not arg:
        raise BoostError("cannot parse %s" % url,
                        hint="supported: boost://install/<skill>, "
                             "boost://install/<tap>:<skill>, boost://tap/<owner>/<repo>")
    return verb, arg


#: The flag the registered handler passes. Not a bypass: it moves the question
#: from a terminal (which an OS-launched handler does not have) to a desktop
#: dialog. Its presence in the script is how `status` tells a handler written
#: before it existed — one that could only ever cancel.
_GUI_FLAG = "--gui"


def _protocol_confirm(args, question: str, ok_label: str, system: str) -> bool:
    """Whether the person approved opening ``args.url``.

    ``--gui`` (the handler's mode) asks only through a dialog and honours
    neither ``-y`` nor ``BOOST_ASSUME_YES``: the URL came from whatever page
    the person clicked, so the person must be the one who says yes. Without a
    dialog to show, it installs nothing and names the command that would.
    """
    if not args.gui:
        return bool(args.yes) or out.confirm(question)
    answer = dialog.ask("A boost:// link asks to %s" % question, ok_label, system)
    if answer is None:
        out.warn("no terminal and no dialog tool to ask with — nothing was "
                 "changed", wrap=True)
        out.info("to go ahead, run in a terminal: `boost protocol open %s`"
                 % shlex.quote(args.url), wrap=True)
    return bool(answer)


def cmd_protocol(argv) -> int:
    """boost protocol [status|register|unregister|open [-y|--gui] URL]"""
    p = cliparse.parser(
        prog="boost protocol",
        description="Manage the boost:// one-click-install handler")
    p.add_argument("action", nargs="?", default="status",
                   choices=["status", "register", "unregister", "open"],
                   help="what to do (default: status)")
    p.add_argument("url", type=util.nonempty_str, nargs="?", help="a boost:// URL (for `open`)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("-y", "--yes", action="store_true",
                      help="`open` without the confirmation prompt")
    mode.add_argument(_GUI_FLAG, action="store_true",
                      help="`open` asks in a desktop dialog instead of the "
                           "terminal (what the registered handler passes)")
    args = p.parse_args(argv)
    if args.action != "open":
        if args.gui:
            p.error("%s only applies to `protocol open`" % _GUI_FLAG)
        if args.url:
            p.error("a URL only applies to `protocol open`")
    system = platform.system()

    if args.action == "open":
        if not args.url:
            p.error("open needs a boost:// URL")
        verb, arg = _parse_boost_url(args.url)
        if verb == "install":
            entry = catalog.resolve_one(arg)
            if not _protocol_confirm(
                    args, "install %s from %s?" % (entry["name"], entry["tap"]),
                    "Install", system):
                out.info("cancelled")
                return 1
            res = store.install(entry, via="protocol")
            _report_result(res)
            if res.kind == "skill":
                out.ok("quality score %d/100" % res.score)
            return 0
        # tap
        if not _protocol_confirm(args, "tap %s?" % arg, "Tap", system):
            out.info("cancelled")
            return 1
        tap = registry.add(arg)
        entries = catalog.rebuild_tap(tap)
        complete.refresh_names()
        journal.log("tap", tap.name, via="protocol")
        out.ok("tapped %s (%d items)" % (tap.name, len(entries)))
        return 0

    if args.action == "register":
        paths.ensure_dirs()
        shim = paths.launcher()
        script = _handler_script()
        # newline="\n" because this artifact is a bash script and bash is a
        # non-Python parser reading it byte for byte. The write sits *above*
        # the platform branch below, so unlike the Linux .desktop file it
        # does run on Windows, where the stub at the end of this command
        # tells the user to invoke the script themselves.
        #
        # Which CR failure bites is shell-specific and is deliberately not
        # claimed here: "bad interpreter: bash\r" is kernel binfmt_script
        # behaviour, and Windows has no kernel shebang support, so under
        # Git Bash the shebang is likely tolerated while under WSL the
        # launcher path is unexecutable for unrelated reasons. The URL route
        # is ruled out — `_parse_boost_url` goes through `urlparse`, which
        # strips CR. What is left is simply that the file is wrong, which is
        # reason enough for a one-keyword pin.
        #
        # Never -y, never BOOST_ASSUME_YES: any page can open a boost:// link,
        # so the handler must ask. With no TTY to ask on, --gui asks in a
        # dialog; the unset keeps an exported BOOST_ASSUME_YES from leaking
        # in from the session that launched the browser.
        script.write_text("#!/usr/bin/env bash\n"
                          "# boost:// URL handler — invoked with the URL as $1\n"
                          "unset BOOST_ASSUME_YES\n"
                          'exec "%s" protocol open %s "$1"\n' % (shim, _GUI_FLAG),
                          encoding="utf-8", newline="\n")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        out.ok("wrote handler script %s" % _tilde(script))
        out.info("a boost:// link asks in a desktop dialog before it installs "
                 "or taps anything; with no dialog it changes nothing",
                 wrap=True)
        if system == "Darwin":
            out.info("macOS routes URL schemes through app bundles, so one manual step remains:")
            out.info("  1. Automator → New → Application → 'Run Shell Script'")
            out.info('  2. script: %s "$1"   (pass input: as arguments)' % _tilde(script))
            out.info("  3. save as Boost.app, then add CFBundleURLTypes for 'boost' to its Info.plist")
            out.info(out.role("  (or: brew install duti && duti -s <bundle-id> boost)", "muted"))
        elif system == "Linux":
            desktop = _desktop_file()
            desktop.parent.mkdir(parents=True, exist_ok=True)
            desktop.write_text("[Desktop Entry]\nType=Application\nName=boost protocol handler\n"
                               "Exec=%s %%u\nMimeType=x-scheme-handler/boost;\nNoDisplay=true\n"
                               % script, encoding="utf-8")
            out.ok("wrote %s" % _tilde(desktop))
            if not (shutil.which("zenity") or shutil.which("kdialog")):
                out.warn("neither zenity nor kdialog found — the handler "
                         "cannot ask, so a link will change nothing until one "
                         "is installed", wrap=True)
            if shutil.which("xdg-mime"):
                import subprocess
                proc = subprocess.run(["xdg-mime", "default", "boost-protocol.desktop",
                                       "x-scheme-handler/boost"], capture_output=True)
                if proc.returncode == 0:
                    out.ok("registered x-scheme-handler/boost via xdg-mime")
                else:
                    out.warn("xdg-mime registration failed — run it manually")
            else:
                out.warn("xdg-mime not found — handler written but not registered")
        else:
            out.warn("no automatic registration on %s — use the handler script directly" % system)
        journal.log("protocol", "register")
        return 0

    if args.action == "unregister":
        removed = 0
        for artifact in (_handler_script(), _desktop_file()):
            if artifact.exists():
                artifact.unlink()
                out.ok("removed %s" % _tilde(artifact))
                removed += 1
        if not removed:
            out.info("nothing registered")
        journal.log("protocol", "unregister")
        return 0

    # status
    out.kv("platform", system)
    if system == "Darwin":
        # `register` on Darwin only ever writes the handler script and prints
        # manual Automator steps (macOS routes URL schemes through app
        # bundles, not a CLI call) — it never touches Launch Services. A
        # single "handler" key that shows the script path once written reads
        # as "registered", which is false until the user finishes building
        # Boost.app. Splitting the path from the yes/no keeps that path from
        # answering a question it can't.
        out.kv("script", _tilde(_handler_script())
               if _handler_script().exists() else "not written")
        out.kv("registered", "no — build Boost.app (see `boost protocol register`)")
    else:
        out.kv("handler", _tilde(_handler_script())
               if _handler_script().exists() else "not registered")
    if _handler_script().exists() and _GUI_FLAG not in _handler_script().read_text(
            encoding="utf-8", errors="replace"):
        out.warn("the handler script predates its confirmation dialog and "
                 "cancels every link — re-run `boost protocol register`",
                 wrap=True)
    if system == "Linux":
        out.kv("desktop", _tilde(_desktop_file())
               if _desktop_file().exists() else "not registered")
    # One form per row rather than a `·`-joined run: the run was 100 columns,
    # and wrapping it strands a bare `·` at the start of a line, because the
    # separator is a word to any wrapper. A form per row needs no separator and
    # reads the same at every width.
    for i, form in enumerate(("boost://install/<skill>",
                              "boost://install/<tap>:<skill>",
                              "boost://tap/<owner>/<repo>")):
        out.kv("URL forms" if i == 0 else "", form)
    out.dim("  try it: boost protocol open boost://install/brainstorming")
    return 0


# ---------------------------------------------------------------- pulse

_ACTION_ROLE = {"install": "success", "uninstall": "danger",
                "evolve": "warn", "edit": "warn"}


def cmd_pulse(argv) -> int:
    """boost pulse [-n N] [--all] [--action A] [--json]"""
    p = cliparse.parser(
        prog="boost pulse",
        description="Team activity feed of skill-management events")
    p.add_argument("-n", type=util.positive_int, default=20,
                   help="events to show (default 20)")
    p.add_argument("--all", action="store_true", help="show the whole journal")
    p.add_argument("--action", type=util.nonempty_str, help="filter by action (install, tap, ...)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)

    events = journal.events(None if args.all else args.n, action=args.action)
    if args.json:
        print(json.dumps(events, indent=2))
        return 0
    if not events:
        # A second, unfiltered read only on this rare (nothing matched) path —
        # needed to tell "no events at all" apart from "this filter matched
        # nothing", which used to render the identical message either way.
        all_events = journal.events() if args.action else events
        print(out.empty_state(
            journal.pulse_empty_state(args.action, all_events), wrap=True))
        return 0
    for e in events:
        # A journal row repeats the tap's frontmatter (`version=`, a subject
        # read off a SKILL.md): a display copy, terminal controls dropped.
        e = out.plain_fields(e)
        action = e.get("action", "?")
        action_role = _ACTION_ROLE.get(action, "accent")
        extras = {k: v for k, v in e.items()
                  if k not in ("ts", "user", "action", "subject")}
        extra_s = ("  " + " ".join("%s=%s" % kv for kv in sorted(extras.items()))
                   if extras else "")
        print("  %s  %s  %s  %s%s" % (
            util.rel_time(e.get("ts", "")).rjust(7),
            out.role(e.get("user", "?").ljust(10), "accent"),
            out.role(action.ljust(11), action_role),
            out.c(e.get("subject", ""), out.BOLD),
            out.role(extra_s, "muted")))
    print()
    out.dim("local journal · share it with your team via `boost onboard`")
    return 0


# ---------------------------------------------------------------- replay

def cmd_replay(argv) -> int:
    """boost replay [list|show ID|rollback ID]"""
    p = cliparse.parser(
        prog="boost replay",
        description="View version history & roll back skills")
    p.add_argument("action", nargs="?", default="list",
                   choices=["list", "show", "rollback"],
                   help="what to do (default: list; rollback restores skills "
                        "only)")
    p.add_argument("id", type=util.nonempty_str, nargs="?", help="history entry id (from `boost replay list`)")
    p.add_argument("-y", "--yes", action="store_true",
                   help="`rollback` without the confirmation prompt")
    p.add_argument("--discard-edits", action="store_true",
                   help="`rollback` even where it uninstalls a skill with "
                        "local edits, deleting them")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)

    if args.action == "list":
        history, skipped = lockfile.history_list(with_skipped=True)
        if args.json:
            print(json.dumps(history, indent=2))
            return 0
        if not history:
            print(out.empty_state(
                "no lock history yet — every install/uninstall snapshots "
                "the lock file", wrap=True))
            if skipped:
                out.dim("%d unreadable snapshot%s skipped"
                        % (skipped, "" if skipped == 1 else "s"))
            return 0
        rows = []
        prev_items = None
        annotated = []
        for h in history:  # oldest -> newest
            try:
                snap = lockfile.history_read(h["id"])
            except BoostError:
                snap = {}
            # All three sections, keyed by (kind, name): a snapshot that
            # gained a rule is a +1, not a no-op.
            items = {(kind, n) for kind, section in lockfile.SECTIONS
                     for n in snap.get(section, {})}
            if prev_items is None:
                delta = ""
            else:
                n_added, n_removed = (len(items - prev_items),
                                      len(prev_items - items))
                parts = ([("+%d" % n_added)] if n_added else []) + \
                        ([("-%d" % n_removed)] if n_removed else [])
                delta = " ".join(parts)
            annotated.append((h, delta))
            prev_items = items
        for h, delta in reversed(annotated):  # newest first
            rows.append((h["id"], util.rel_time(h["updated"]),
                         str(h["count"]), delta))
        # ID is what the footer's `replay show|rollback <id>` take.
        out.table(rows, headers=("ID", "WHEN", "ITEMS", "Δ"), whole=("ID",))
        print()
        if skipped:
            out.dim("%d unreadable snapshot%s skipped"
                    % (skipped, "" if skipped == 1 else "s"))
        out.dim("inspect with `boost replay show <id>` · restore with `boost replay rollback <id>`")
        return 0

    if not args.id:
        p.error("%s needs a history ID" % args.action)
    snapshot = lockfile.history_read(args.id)
    integ = lockfile.check()
    # Any lock boost cannot use but a newer boost's (whose last change a
    # rollback would discard): through the diff below, write() refuses it,
    # and its hint named this very command.
    if (args.action == "rollback" and not integ.ok
            and integ.problem != "missing" and not lockfile.newer(integ)):
        # Every other write refuses a corrupt lock, and the diff below would
        # read it as empty and reinstall each skill over it. Restoring is the
        # snapshot itself becoming the lock; the corrupt bytes stay aside.
        # Kept now, so the name below is the backup that holds these bytes
        # (a backup from an earlier corruption may hold another state). One
        # that cannot be kept — or a lock boost cannot read, which may be
        # intact — refuses here, before the prompt names a backup.
        backup = paths.tilde(lockfile.backup_for_restore(integ))
        if not (args.yes or out.confirm(
                "the lock file %s — make snapshot %s the lock file? "
                "It is the lock as it was before the change after it; the "
                "newest record stays only in %s"
                % (lockfile.fault(integ), args.id, backup),
                quiet=args.json)):
            if args.json:
                print(json.dumps({"id": args.id, "cancelled": True}, indent=2))
            else:
                out.info("cancelled")
            return 1
        lockfile.restore(args.id)
        if not args.json:
            out.ok("restored the lock file from %s, as it was before the "
                   "change after it — anything that change recorded is only "
                   "in %s" % (args.id, backup))
    now_all = lockfile.all_installed()
    # Per-kind diff: snapshots carry all three sections, so a rule that
    # appeared since the snapshot is a real difference, labeled as one. A
    # row in both states is compared field by field (lockfile.row_differences):
    # by version alone, a pin flip or a same-version content change read as
    # "matches this snapshot".
    diffs = {}
    row_diffs: dict[str, dict[str, dict]] = {}
    for kind, section in lockfile.SECTIONS:
        snap = snapshot.get(section, {})
        cur = now_all[kind]
        row_diffs[kind] = {}
        for n in sorted(cur):
            if n in snap:
                d = lockfile.row_differences(snap[n], cur[n])
                if d:
                    row_diffs[kind][n] = d
        diffs[kind] = (
            sorted(n for n in cur if n not in snap),
            sorted(n for n in snap if n not in cur),
            sorted(row_diffs[kind]))
    snap_skills = snapshot.get("skills", {})
    current = now_all["skill"]
    added, removed, changed = diffs["skill"]
    any_diff = any(a or r or c for a, r, c in diffs.values())

    if args.action == "show":
        if args.json:
            payload: dict = {"added": added, "removed": removed,
                             "changed": changed}
            if row_diffs["skill"]:
                payload["differences"] = {
                    n: {f: list(v) for f, v in d.items()}
                    for n, d in row_diffs["skill"].items()}
            for kind in ("rule", "workflow"):
                a, r, c = diffs[kind]
                payload[kind + "s"] = {"added": a, "removed": r, "changed": c}
            print(json.dumps({"id": args.id, "since_snapshot": payload},
                             indent=2))
            return 0
        out.heading("since %s (%s)" % (args.id,
                                       util.rel_time(snapshot.get("updated", ""))))
        if not any_diff:
            out.ok("current state matches this snapshot")
            return 0
        for kind, _section in lockfile.SECTIONS:
            a, r, c = diffs[kind]
            label = "" if kind == "skill" else " (%s)" % kind
            for n in a:
                out.info(out.role("+ %s%s" % (n, label), "success")
                         + out.role("  added since", "muted"))
            for n in r:
                out.info(out.role("- %s%s" % (n, label), "danger")
                         + out.role("  removed since", "muted"))
            for n in c:
                out.info(out.role("~ %s%s  %s" % (
                    n, label, _row_diff_line(row_diffs[kind][n])), "warn"))
        return 0

    # rollback — skills only; rule/workflow differences are named, never
    # silently absorbed into an "already at this snapshot" all-clear.
    mat_diff = ["%s %s" % (kind, n) for kind in ("rule", "workflow")
                for group in diffs[kind] for n in group]
    if mat_diff and not args.json:
        out.warn("not rolled back (rollback restores skills only): %s — "
                 "reinstall or uninstall these by hand" % ", ".join(mat_diff))

    # A "removed" skill no tap can resolve will never come back through
    # _resolve_entry, so counting it as pending work promised a restore that
    # could never land — and because nothing about that ever changes, every
    # later run repeated the same warning and still claimed "complete". Split
    # it out up front: it never gates the confirm prompt below, only whether
    # there is anything else left to do.
    # A skill recorded since the snapshot whose only copy is the store — one
    # `boost sync` found and recorded — is deleted for good by an uninstall,
    # so rollback leaves it and says how to remove it.
    only = [n for n in added if store.only_copy(n, current[n])]
    added = [n for n in added if n not in only]
    if only and not args.json:
        for n in only:
            out.info("kept %s: the store holds its only copy — `boost "
                     "uninstall %s` deletes it" % (n, n))
    # An edited store copy is in no history entry and no tap: uninstalling
    # it deleted the edits for good, and rolling forward again brought back
    # the tap's copy. Refused before anything changes, as `update` holds an
    # edited item, unless the user says to discard them.
    edited = [n for n in added
              if integrity.locally_edited("skill", n, current[n])]
    if edited and not args.discard_edits:
        if args.json:
            print(json.dumps({"id": args.id, "refused": "local-edits",
                              "edited": edited}, indent=2))
            return 1
        out.warn("not rolled back: it would uninstall %s, which %s local "
                 "edits nothing else holds — copy %s aside, or `boost replay "
                 "rollback %s --discard-edits` deletes them"
                 % (", ".join(edited), "has" if len(edited) == 1 else "have",
                    "it" if len(edited) == 1 else "them", args.id), wrap=True)
        return 1
    lookups = {n: _resolve_entry(n, prefer_tap=snap_skills[n].get("tap"),
                                  kind=catalog.KIND_SKILL)
               for n in removed}
    resolved = {n: entry for n, (entry, _why) in lookups.items()
                if entry is not None}
    restorable = [n for n in removed if n in resolved]
    gone = [n for n in removed if n not in resolved]

    def _gone_line(n: str) -> str:
        why = lookups[n][1]
        return ("%s — cannot restore" % why if why
                else "%s is gone from every tap — cannot restore" % n)

    if not (added or restorable or changed):
        if args.json:
            # #804's payload verbatim: `gone` is deliberately not reported
            # here. Adding it broke that PR's own contract test, and the test
            # is the specification — see the note on this train's PR.
            print(json.dumps({"id": args.id, "no_changes": True,
                              "not_rolled_back": mat_diff,
                              **({"only_copies": only} if only else {})},
                             indent=2))
            return 0
        for n in gone:
            out.warn(_gone_line(n), wrap=True)
        out.ok("nothing else to roll back" if only else
               "skills already match this snapshot — nothing to do"
               if mat_diff else "already at this snapshot — nothing to do")
        return 0
    if not args.json:
        out.info("rollback to %s will: uninstall %d, install %d, revisit %d changed skill(s)"
                 % (args.id, len(added), len(restorable), len(changed)))
    if not (args.yes or out.confirm("proceed?", quiet=args.json)):
        if args.json:
            print(json.dumps({"id": args.id, "cancelled": True}, indent=2))
            return 1
        out.info("cancelled")
        return 1
    uninstalled, restored, version_diffs = [], [], []
    holds_restored: list[str] = []

    def _left(n: str, want: dict, row: dict | None) -> dict:
        """The content differences rollback could not undo for ``n``."""
        left = {f: v for f, v in lockfile.row_differences(want, row or {}).items()
                if f in lockfile.CONTENT_FIELDS}
        if left:
            version_diffs.append({"skill": n, "snapshot": want.get("version"),
                                  "current": (row or {}).get("version"),
                                  "fields": sorted(left)})
        return left

    for n in added:  # in current, not in snapshot
        store.uninstall(n, kind="skill")
        if not args.json:
            out.ok("uninstalled %s" % n)
        uninstalled.append(n)
    for n in gone:
        if not args.json:
            out.warn(_gone_line(n), wrap=True)
    for n in restorable:  # in snapshot, missing now, resolvable
        want = snap_skills[n]
        entry = resolved[n]
        # Restore the row as the snapshot recorded it: its agent scope, then
        # its version and commit holds — a fresh install carries none of them.
        res = store.install(entry, force=True,
                            only_agents=want.get("only_agents") or None)
        if store.reapply_recorded_holds(n, want) and not args.json:
            out.warn("%s is commit-pinned at %s, but its tap now serves %s — "
                     "`boost verify` will flag it"
                     % (n, str(want.get("commit_pin"))[:12],
                        str((lockfile.get_skill(n) or {}).get("commit") or "?")[:12]),
                     wrap=True)
        # ...and set aside again, if the snapshot recorded it set aside: an
        # install resets both flags, which brought a quarantined skill back
        # linked into every agent.
        aside = store.reapply_recorded_aside(n, want)
        left = _left(n, want, lockfile.get_skill(n))
        if not args.json:
            if left:
                out.warn("restored %s from current tap state, which differs "
                         "from the snapshot: %s" % (n, _row_diff_line(left)),
                         wrap=True)
            elif aside:
                out.ok("restored %s (%s, as the snapshot recorded)"
                       % (n, aside))
            else:
                out.ok("restored %s → %s" % (n, " · ".join(res.linked)))
            _warn_unwritable(res)
        restored.append(n)
    for n in changed:  # in both, recorded differently
        want = snap_skills[n]
        fields = store.restore_recorded_holds(n, want)
        if fields:
            holds_restored.append(n)
            if not args.json:
                out.ok("restored %s's %s as the snapshot recorded"
                       % (n, ", ".join(fields)))
        left = _left(n, want, lockfile.get_skill(n))
        if left and not args.json:
            out.warn("%s differs from the snapshot: %s — taps only carry "
                     "their current state; `boost pin` prevents future drift"
                     % (n, _row_diff_line(left)), wrap=True)
    journal.log("replay", args.id, op="rollback")
    if args.json:
        print(json.dumps({"id": args.id, "uninstalled": uninstalled,
                          "restored": restored, "unrestorable": gone,
                          "version_diffs": version_diffs,
                          "not_rolled_back": mat_diff,
                          **({"holds_restored": holds_restored}
                             if holds_restored else {}),
                          **({"only_copies": only} if only else {})}, indent=2))
        return 1 if gone or version_diffs else 0
    if gone or version_diffs:
        parts = []
        if gone:
            parts.append("%d skill%s not restored: %s"
                         % (len(gone), _s(len(gone)), ", ".join(gone)))
        if version_diffs:
            names = [str(d["skill"]) for d in version_diffs]
            parts.append("%d skill%s still differing from the snapshot: %s"
                         % (len(names), _s(len(names)), ", ".join(names)))
        out.warn("finished with %s" % "; ".join(parts), wrap=True)
        return 1
    out.ok("rollback to %s complete" % args.id)
    return 0


def _row_value_text(field: str, value) -> str:
    """One side of a :func:`lockfile.row_differences` pair, for a person."""
    if field == "pinned":
        return "yes" if value else "no"
    if value is None:
        return "none"
    if field == "only_agents":
        return ",".join(value)
    text = out.plain(str(value))
    return text[:12] if field in ("commit", "sha256", "commit_pin") else text


def _row_diff_line(diff: dict) -> str:
    """``version 1.0 → 1.1 · pinned no → yes`` for a row's differences."""
    return " · ".join("%s %s → %s" % (f, _row_value_text(f, want),
                                      _row_value_text(f, have))
                      for f, (want, have) in diff.items())


# ---------------------------------------------------------------- who

def cmd_who(argv) -> int:
    """boost who [SKILL] [--json]"""
    p = cliparse.parser(
        prog="boost who",
        description="Discover who on the team has skill expertise")
    p.add_argument("skill", type=util.nonempty_str, nargs="?", help="focus on one skill")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)

    events = journal.events(subject=args.skill) if args.skill else journal.events()
    # #780 made the empty state filter-aware; #804 made it honor --json.
    # Both are wanted: a --json caller falls through to the emitter below
    # rather than getting prose on stdout.
    if not events and not args.json:
        if args.skill:
            # Second, unfiltered read only on this rare (nothing matched)
            # path — same reasoning as cmd_pulse above.
            all_events = journal.events()
            known = sorted({e.get("subject", "") for e in all_events
                           if e.get("subject")})
            msg = journal.who_empty_state(
                args.skill, all_events, lockfile.find_any(args.skill) is not None,
                known)
        else:
            msg = journal.who_empty_state(None, [], False)
        print(out.empty_state(msg, wrap=True))
        return 0

    if args.skill:
        # find_any: "installed: false" for a rule the journal clearly shows
        # being installed would contradict `boost list`.
        found = lockfile.find_any(args.skill)
        kind, lk = found if found is not None else (None, None)
        rows = [(util.rel_time(e.get("ts", "")), e.get("user", "?"),
                 e.get("action", "?"))
                for e in events if journal.is_expertise_event(e)] or \
               [(util.rel_time(e.get("ts", "")), e.get("user", "?"),
                 e.get("action", "?")) for e in events]
        if args.json:
            print(json.dumps({"skill": args.skill, "installed": lk is not None,
                              "kind": kind, "events": events}, indent=2))
            return 0
        out.heading(args.skill)
        if lk:
            installed_s = "v%s from %s" % (lk.get("version"), lk.get("tap"))
            if kind != "skill":
                installed_s += " (%s)" % kind
            out.kv("installed", installed_s)
        out.table(rows[:20], headers=("WHEN", "USER", "ACTION"))
        print()
        out.dim("based on the local journal — in a team setup, pulse feeds "
                "aggregate via `boost onboard`", wrap=True)
        return 0

    users: dict[str, dict] = {}
    for e in events:
        u = users.setdefault(e.get("user", "?"), {
            "events": 0, "skills": set(), "installs": 0, "last": e.get("ts", "")})
        u["events"] += 1
        if e.get("subject") and journal.is_expertise_event(e):
            u["skills"].add(e["subject"])
        # New installs only, as `boost trending` counts them: an update or a
        # reinstall journals "install" too, and is not one.
        if journal.is_new_install(e):
            u["installs"] += 1
        u["last"] = max(u["last"], e.get("ts", ""))
    if args.json:
        print(json.dumps({u: {"events": d["events"], "installs": d["installs"],
                              "skills": sorted(d["skills"]),
                              "last_active": d["last"]}
                          for u, d in users.items()}, indent=2))
        return 0
    board = [(u, str(d["events"]), str(len(d["skills"])), str(d["installs"]),
              util.rel_time(d["last"]))
             for u, d in sorted(users.items(), key=lambda kv: -kv[1]["events"])]
    out.table(board, headers=("USER", "EVENTS", "SKILLS", "INSTALLS", "LAST ACTIVE"))
    print()
    out.dim("based on the local journal — in a team setup, pulse feeds aggregate "
            "via `boost onboard`", wrap=True)
    return 0
