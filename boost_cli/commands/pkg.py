# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Package Management commands (11): install, uninstall, sync, update,
reinstall, bundle, import, pin, unpin, snapshot, export."""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import zipfile
from datetime import UTC, datetime
from itertools import chain
from pathlib import Path

from .. import cliparse
from ..core import (
    adapters,
    agents,
    catalog,
    complete,
    config,
    frontmatter,
    gitutil,
    installscan,
    integrity,
    journal,
    lockfile,
    paths,
    projectlock,
    registry,
    resolve,
    scopes,
    staleness,
    store,
    typosquat,
    updatediff,
    util,
)
from ..core import output as out
from ..errors import BoostError
from ._common import _shadowed_kinds

_tilde = paths.tilde


def _plural(n: int, word: str) -> str:
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def _warn_confusions(entries: list[dict]) -> None:
    """Warn when a skill about to be installed is confusable with one from a
    *different* tap — the typosquat / owner-confusion guard (core.typosquat).

    Quiet by default: it only speaks up when a near-identical name resolves to
    another owner, which is exactly the fat-finger-into-a-look-alike case.
    """
    if not entries:
        return
    all_entries = catalog.all_entries()
    for e in entries:
        for other in typosquat.find_confusions(e, all_entries)[:3]:
            out.warn("%s (%s) closely resembles %s (%s) — double-check you "
                     "meant this one" % (e["name"], e["tap"],
                                         other["name"], other["tap"]))


def _check_agents(names: list[str] | None) -> list[str] | None:
    """Validate --agent values against configured agents."""
    if not names:
        return None
    known = agents.known_agents()
    bad = [n for n in names if n not in known]
    if bad:
        raise BoostError("unknown agent%s: %s" % ("s" if len(bad) > 1 else "",
                                                 ", ".join(bad)),
                        hint="known agents: %s" % ", ".join(known))
    return names


def _emit_scan(reports) -> None:
    """Print installscan reports as warnings. Silent when there is nothing."""
    for line in installscan.as_lines(reports):
        out.warn(line)


def _warn_injection(res: store.InstallResult) -> None:
    """Flag prompt-injection / risky-content patterns in what was just installed.

    boost installs Markdown the agent then executes, so the installed content is
    scanned (core.injectscan) and any hits are surfaced worst-first. Advisory
    only — it warns, it never blocks the install. The scan itself lives in
    core.installscan so every front end shares it, not just this one.
    """
    _emit_scan(installscan.scan(res, installscan.INJECTION))


def _warn_secrets(res: store.InstallResult) -> None:
    """Flag embedded credentials / secrets in what was just installed.

    Scans the installed content (core.secretscan) for known secret shapes and
    surfaces any hits worst-first, with the secret value redacted. Advisory
    only — it warns, it never blocks the install.
    """
    _emit_scan(installscan.scan(res, installscan.SECRET))


def _offer_mcp(res: store.InstallResult, no_mcp: bool = False) -> None:
    """Surface the MCP servers a just-installed skill needs, and offer to wire them.

    A skill that only works paired with an MCP server used to install "cleanly"
    and then fail in the agent for a reason nothing surfaced. Now the requirement
    is stated at install time, and boost offers to run the registration for the
    servers that came with a runnable spec.

    Advisory, never fatal: a declined prompt, a missing agent CLI or a failed
    registration all leave the skill installed. Suppressed by ``--no-mcp`` (passed
    down as ``no_mcp``) or by exporting ``BOOST_NO_MCP_OFFER``.

    The offer targets whichever agent CLIs are actually installed, so a machine
    with only Gemini CLI is offered ``gemini mcp add`` rather than a ``claude``
    command it cannot run.
    """
    rows = res.mcp_servers
    if not rows or no_mcp or os.environ.get("BOOST_NO_MCP_OFFER"):
        return
    from ..core import mcpdecl, scopes
    # A project-scoped install already recorded these in the repo's .mcp.json
    # (store.register_project_mcp), which is the committable, reviewable
    # registration `--scope project` promises. Offering a `<host> mcp add` on
    # top would register the same servers a second time, machine-wide — which
    # is the bug this path had: the offer never looked at res.scope at all.
    if res.scope == scopes.SCOPE_PROJECT:
        # Report what was RECORDED, not what was declared. The two differ when
        # the sidecar could not be written — a read-only checkout, a root-owned
        # .mcp.json — and claiming success there would be the worse failure,
        # because the skill really is installed and the servers really are not.
        wanted = [r["name"] for r in mcpdecl.registrable(rows)]
        if not wanted:
            return
        out.info("")
        if res.mcp_recorded:
            out.ok("recorded %s in %s"
                   % (_plural(len(res.mcp_recorded), "MCP server"),
                      mcpdecl.SIDECAR))
            out.dim("  %s — commit it to share with the team"
                    % ", ".join(res.mcp_recorded))
        else:
            out.warn("could not write %s — %s not registered"
                     % (mcpdecl.SIDECAR, ", ".join(wanted)))
            out.dim("  the skill is installed; fix the file's permissions and "
                    "reinstall to record them")
        return
    out.info("")
    out.warn("%s needs %s to work:" % (res.name, _plural(len(rows), "MCP server")))
    for row in rows:
        how = ("`%s`" % row["spec"]["command"] if row["spec"]
               and row["spec"].get("command") else "no command declared")
        out.info("  %s  %s" % (out.c(row["name"], out.BOLD),
                               out.role(how, "muted")))
    wirable = mcpdecl.registrable(rows)
    if not wirable:
        # Name-only declarations: boost will not invent a command line.
        out.dim("  install these yourself, then `boost mcp register`")
        return
    from ..core import mcphost
    # Offer the CLIs that are actually here. With none installed we still fall
    # back to the full list so the manual command lines get printed.
    targets = [h for h in mcphost.hosts() if shutil.which(mcphost.cli(h))] \
        or mcphost.hosts()
    where = " · ".join(mcphost.label(h) for h in targets)
    # Name the scope. The prompt used to say only "register N servers with
    # Claude Code now?", which is the one detail the answer turns on — this
    # writes a registration every project on this machine will then launch.
    if not out.confirm("register %s with %s, for every project on this machine?"
                       % (_plural(len(wirable), "server"), where), default=False):
        out.dim("  skipped — `%s mcp add …` when you're ready"
                % mcphost.cli(targets[0]))
        return
    for row in wirable:
        for host in targets:
            _register_mcp_server(row["name"], row["spec"], host=host,
                                 scope=res.scope)


def _register_mcp_server(name: str, spec: dict, host: str = "claude",
                         scope: str = "user") -> None:
    """Run one `<host> mcp add` for a skill-declared server. Never raises.

    ``scope`` is threaded from the install rather than defaulted, because
    ``register_argv``'s own default is ``"user"`` and silently taking it is how
    a ``--scope project`` install ended up registering machine-wide.
    """
    import subprocess

    from ..core import mcpdecl, mcphost
    argv = mcpdecl.register_argv(name, spec, host=host, scope=scope)
    if not shutil.which(mcphost.cli(host)):
        out.warn("`%s` CLI not found — run this yourself:" % mcphost.cli(host))
        out.info("  " + " ".join(argv))
        return
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        out.warn("could not register %s: %s" % (name, e))
        out.info("  run it yourself: " + " ".join(argv))
        return
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()
        out.warn("could not register %s: %s"
                 % (name, tail[-1] if tail else "unknown error"))
        out.info("  run it yourself: " + " ".join(argv))
        return
    out.ok("registered MCP server %s with %s" % (name, mcphost.label(host)))
    journal.log("mcp-register", name, host=host)


def _report_result(res: store.InstallResult, no_mcp: bool = False) -> None:
    """The canonical three-line install report."""
    if res.kind in ("rule", "workflow"):
        where = " (this repo)" if res.scope == "project" else ""
        out.ok("materialized%s → %s"
               % (where, " · ".join(res.linked) or "(no enabled agents)"))
        out.ok("lock updated (.skill-lock.json)")
        _warn_injection(res)
        _warn_secrets(res)
        return
    if res.scope == scopes.SCOPE_PROJECT:
        # No canonical store and no symlinks — a real copy per agent, so the
        # report says "copied into" for each rather than "copied … then linked".
        out.ok("copied into this repo → %s"
               % (" · ".join(res.linked) or "(no enabled agents)"))
        out.ok("project lock updated (%s/%s)"
               % (projectlock.LOCK_DIRNAME, projectlock.LOCK_FILENAME))
        out.dim("  commit %s/ to share these with the team"
                % projectlock.LOCK_DIRNAME)
        _warn_injection(res)
        _warn_secrets(res)
        return
    out.ok("copied to %s" % _tilde(res.dest))
    if res.linked:
        out.ok("linked → %s" % " · ".join(res.linked))
    elif not res.native:
        out.warn("no agent links created (no enabled agents?)")
    # Agents that read the canonical store need no link, but saying nothing
    # would make a Gemini-only install look like it reached no agent at all.
    if res.native:
        out.ok("available to %s (reads the store directly)"
               % " · ".join(agents.display_name(a) for a in res.native))
    for path in res.conflicts:
        out.warn("not linked: %s exists and is not managed by boost" % _tilde(path))
    out.ok("lock updated (.skill-lock.json)")
    _warn_injection(res)
    _warn_secrets(res)
    _offer_mcp(res, no_mcp=no_mcp)


def _boostfile_text(skills: dict[str, dict], via: str = "boost bundle dump") -> str:
    """Render lock entries as a Boostfile (taps first, then sorted skills)."""
    lines = ["# Boostfile — generated by %s" % via]
    taps = sorted({e.get("tap") or "" for e in skills.values()} - {"", "local"})
    for tname in taps:
        try:
            url = registry.get(tname).url
        except BoostError:
            url = ""
        lines.append(("tap %s %s" % (tname, url)).rstrip())
    for name in sorted(skills):
        e = skills[name]
        if (e.get("tap") or "local") == "local":
            lines.append("# local skill (no tap source): %s" % name)
        else:
            lines.append("skill %s:%s@%s" % (e["tap"], name,
                                             e.get("version", "0.0.0")))
    return "\n".join(lines) + "\n"


def _others_installed() -> str:
    """"N rule(s) and N workflow(s)" across the non-skill lock sections — what
    a skills-only artifact (Boostfile, export archive, snapshot) leaves out —
    or "" when there is nothing to leave out."""
    parts = [_plural(len(section), kind)
             for kind, section in (("rule", lockfile.installed_rules()),
                                   ("workflow", lockfile.installed_workflows()))
             if section]
    return " and ".join(parts)


def _rel_list(meta: dict, key: str) -> list[str]:
    """A skill's `requires:`/`conflicts:` frontmatter as a clean name list."""
    val = meta.get(key)
    if val in (None, "", False):
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    return [s.strip() for s in str(val).split(",") if s.strip()]


def _skill_relations(name: str, key: str) -> list[str]:
    """`requires:`/`conflicts:` for a skill by name, from its catalog entry."""
    matches = catalog.find(name)
    if not matches:
        return []
    return _rel_list(matches[0].get("meta") or {}, key)


def _expand_dependencies(entries: list[dict]) -> tuple[list[dict], resolve.Resolution]:
    """Grow the requested entries into their full `requires:` closure.

    Returns ``(ordered_entries, resolution)`` — the entries to install in
    dependency-first order (roots plus any pulled-in dependencies that are not
    already installed), and the :class:`resolve.Resolution` carrying what was
    added, any advisory conflicts, and unresolved (dangling) requirements.
    """
    # All three lock sections, not just skills: a rule or workflow already
    # installed under a required name must not be re-added to the plan.
    installed = frozenset(chain.from_iterable(lockfile.all_installed().values()))
    res = resolve.resolve(
        [e["name"] for e in entries],
        lambda n: _skill_relations(n, "requires"),
        lambda n: _skill_relations(n, "conflicts"),
        installed=installed,
        known=lambda n: bool(catalog.find(n)),
    )
    by_name = {e["name"]: e for e in entries}
    ordered: list[dict] = []
    for name in res.order:
        if name in by_name:
            ordered.append(by_name[name])
            continue
        try:
            ordered.append(catalog.resolve_one(name))
        except BoostError:
            # A dep that resolves nowhere unambiguously is reported via
            # res.unresolved; skip it here rather than abort the whole install.
            if name not in res.unresolved:
                res.unresolved.append(name)
    return ordered, res


# ── install ──────────────────────────────────────────────────────────────

def cmd_install(argv: list[str]) -> int:
    ap = cliparse.parser(prog="boost install",
                                 description="Install a skill from a tap registry")
    ap.add_argument("names", nargs="+", metavar="NAME",
                    help="skill name, optionally qualified as tap:skill")
    ap.add_argument("--force", action="store_true",
                    help="reinstall even if already installed or pinned")
    ap.add_argument("--path", metavar="P", default=None,
                    help="pick which copy to install when one registry ships "
                         "the name more than once (see the paths that error "
                         "lists); may be a trailing path segment")
    ap.add_argument("--agent", action="append", metavar="A",
                    help="link only into this agent (repeatable)")
    scope_g = ap.add_mutually_exclusive_group()
    scope_g.add_argument("--scope", choices=scopes.SCOPES, default=None,
                         help="install into your user config (default) or the "
                              "current repo (project)")
    scope_g.add_argument("--local", dest="scope", action="store_const",
                         const=scopes.SCOPE_PROJECT,
                         help="into this repo, committable (= --scope project)")
    scope_g.add_argument("--global", dest="scope", action="store_const",
                         const=scopes.SCOPE_USER,
                         help="into your user config (= --scope user, default)")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would happen without changing anything")
    ap.add_argument("--no-deps", action="store_true",
                    help="install only the named skills, not their `requires:`")
    ap.add_argument("--no-mcp", action="store_true",
                    help="don't offer to register MCP servers a skill declares")
    args = ap.parse_args(argv)
    args.scope = args.scope or scopes.SCOPE_USER
    only = _check_agents(args.agent)
    multi = len(args.names) > 1
    entries, failed = [], 0
    for n in args.names:
        try:
            entries.append(catalog.resolve_one(n, path=args.path))
        except BoostError as err:
            if not multi:
                raise
            out.warn("%s: %s" % (n, err.message))
            failed += 1

    _warn_confusions(entries)

    # Grow the request into its `requires:` closure (deps installed first),
    # unless the caller opted out. Only skills carry dependency frontmatter;
    # rules/workflows pass through unchanged.
    if not args.no_deps and entries:
        entries, dep_res = _expand_dependencies(entries)
        if dep_res.added:
            out.info("pulling in %s required by your selection: %s"
                     % (_plural(len(dep_res.added), "dependency"),
                        ", ".join(dep_res.added)))
        for name in dep_res.unresolved:
            out.warn("required skill %r is in no tap — skipped "
                     "(install it manually or `boost tap` its source)" % name)
        for skill, clash in dep_res.conflicts:
            out.warn("%s declares a conflict with %s (also present)" % (skill, clash))
        # Pulling in dependencies can turn a single-name request into a multi-item
        # install (per-item headings); it must never *lower* multi (e.g. when an
        # unknown co-requested name was dropped), so OR rather than reassign.
        multi = multi or len(entries) > 1

    if args.dry_run:
        # TWO lists, because the three kinds do not reach the same agents.
        # Rules and workflows materialize into every enabled agent's dotdir,
        # Gemini included. A skill is symlinked only into the agents that take
        # links — Gemini reads the canonical store directly and is deliberately
        # never linked (see agents.linking_agents). One list for both is how
        # `--dry-run` came to promise a `~/.gemini/skills` symlink that the real
        # install has never created.
        targets = [a for a in agents.enabled_agents() if not only or a in only]
        link_targets = [a for a in agents.linking_agents()
                        if not only or a in only]
        native_targets = [a for a in agents.native_store_agents()
                          if not only or a in only]
        pbase = scopes.resolve_base(args.scope)
        if args.scope == scopes.SCOPE_PROJECT and pbase is None:
            raise BoostError(
                "there is no project here to install into",
                hint="cd into a repo, or drop --local to install for your user")
        for e in entries:
            if args.scope == scopes.SCOPE_PROJECT and e.get("kind", "skill") == "skill":
                seen = projectlock.get_skill(pbase, e["name"])
                out.info("would %s %s v%s from %s into %s"
                         % ("reinstall" if seen else "install", e["name"],
                            e["version"], e["tap"], _tilde(pbase)))
                for agent_name, sdir in agents.enabled_agents().items():
                    if only and agent_name not in only:
                        continue
                    out.info("  copy  → %s"
                             % _tilde(scopes.skill_target(sdir, e["name"], base=pbase)))
                continue
            if e.get("kind") in ("rule", "workflow"):
                k = e["kind"]
                seen = (lockfile.get_rule if k == "rule"
                        else lockfile.get_workflow)(e["name"])
                # Same verb the real run's summary uses ("Upgraded 1 rule");
                # the skill preview below already says "upgrade".
                verb = "upgrade" if seen else "install"
                where = "into this repo" if args.scope == "project" else "user config"
                out.info("would %s %s %s v%s from %s (%s)" % (verb, k, e["name"],
                                                              e["version"], e["tap"],
                                                              where))
                out.info("  materialize → %s" % (" · ".join(targets)
                                                 or "(no enabled agents)"))
                continue
            verb = "upgrade" if lockfile.get_skill(e["name"]) else "install"
            out.info("would %s %s v%s from %s" % (verb, e["name"],
                                                  e["version"], e["tap"]))
            out.info("  copy  %s → %s" % (_tilde(store.source_dir_for(e)),
                                          _tilde(store.skill_store_dir(e["name"]))))
            out.info("  link  → %s" % (" · ".join(link_targets)
                                        or "(no linking agents)"))
            # Mirrors what the real install reports, so a Gemini-only install
            # does not read as reaching no agent at all.
            if native_targets:
                out.info("  available to %s (reads the store directly)"
                         % " · ".join(agents.display_name(a)
                                      for a in native_targets))
        out.info("dry run — nothing was changed")
        return 1 if failed else 0

    results = []
    for e in entries:
        if multi:
            out.heading("%s v%s (%s)" % (e["name"], e["version"], e["tap"]))
        try:
            res = store.install(e, force=args.force, only_agents=only, scope=args.scope)
        except BoostError as err:
            if not multi:
                raise
            out.warn("%s: %s" % (e["name"], err.message))
            failed += 1
            continue
        _report_result(res, no_mcp=args.no_mcp)
        results.append(res)
    if results:
        kinds = {r.kind for r in results}
        noun = next(iter(kinds)) if len(kinds) == 1 else "item"
        new = sum(1 for r in results if not r.upgraded)
        parts = []
        if new:
            parts.append("Installed %s" % _plural(new, "new " + noun))
        if len(results) - new:
            parts.append("Upgraded %s" % _plural(len(results) - new, noun))
        # Quality score is skill-only (rules have no scored tree); omit it when
        # nothing scoreable was installed so a rule doesn't report 0/100.
        scored = [r for r in results if r.kind == "skill"]
        if scored:
            avg = round(sum(r.score for r in scored) / len(scored))
            summary = "%s; quality score %d/100" % ("; ".join(parts), avg)
        else:
            summary = "; ".join(parts)
        lines = [summary]
        if len(results) == 1:
            r0 = results[0]
            if r0.linked:
                lines.append(out.role("%s → %s" % (r0.name, " · ".join(r0.linked)), "muted"))
            lines.append(out.role("next: boost info %s" % r0.name, "muted"))
        print(out.panel(lines, title="installed", hue="green"))
    return 1 if failed else 0


# ── uninstall ────────────────────────────────────────────────────────────

def cmd_uninstall(argv: list[str]) -> int:
    ap = cliparse.parser(
        prog="boost uninstall",
        description="Remove an installed skill, rule, workflow, or config")
    ap.add_argument("names", nargs="+", metavar="NAME")
    ap.add_argument("--local", dest="scope", action="store_const",
                    const=scopes.SCOPE_PROJECT, default=None,
                    help="remove from this repo rather than your user config")
    ap.add_argument("-y", "--yes", action="store_true",
                    help="skip the confirmation prompt")
    args = ap.parse_args(argv)
    # Ask only when someone is there to answer. out.confirm() returns its
    # `default` on a non-TTY, so gating on it unconditionally would turn every
    # scripted `boost uninstall x` — CI step, Makefile, Dockerfile — into a
    # silent no-op exiting 1. A pipeline that cannot see the prompt keeps the
    # behaviour it has today; the prompt is a speed bump for humans only.
    if sys.stdin.isatty() and not args.yes:
        prompt = ("uninstall %s?" % args.names[0] if len(args.names) == 1 else
                  "uninstall %d skills: %s?" % (len(args.names),
                                                ", ".join(args.names)))
        if not out.confirm(prompt):
            out.info("cancelled")
            return 1
    removed, failed = 0, 0
    for name in args.names:
        try:
            if args.scope == scopes.SCOPE_PROJECT:
                info = store.uninstall_project(name)
            else:
                info = store.uninstall(name)
        except BoostError as err:
            if len(args.names) == 1:
                raise
            out.warn("%s: %s" % (name, err.message))
            failed += 1
            continue
        if info["unlinked"]:
            verb = "removed from" if info.get("scope") == scopes.SCOPE_PROJECT \
                else "unlinked ←"
            out.ok("%s %s" % (verb, " · ".join(info["unlinked"])))
        # Report where it actually went, not where a user-scope install would
        # have put it — a project skill never touches the canonical store.
        if info.get("scope") == scopes.SCOPE_PROJECT:
            out.ok("removed from %s" % _tilde(info.get("base", "this repo")))
        else:
            out.ok("removed %s" % _tilde(store.skill_store_dir(name)))
        removed += 1
    if removed:
        lines = ["Uninstalled %s" % _plural(removed, "skill")]
        if removed == 1 == len(args.names):
            lines.append(out.role("next: boost list", "muted"))
        print(out.panel(lines, title="removed", hue="pink"))
    return 1 if failed else 0


# ── sync ─────────────────────────────────────────────────────────────────

_PLAN_LABELS = [
    ("missing_store", "missing from store"),
    ("missing_links", "missing agent links"),
    ("blocked_links", "agent links blocked by a foreign file"),
    ("stale_links", "stale links"),
    ("orphaned_store", "orphaned store dirs"),
    ("missing_materializations", "missing rule/workflow files"),
    ("out_of_scope_links", "linked outside declared scope"),
]

#: Plan keys whose items are ``(skill, agent)`` pairs rather than paths.
_PAIR_KEYS = ("missing_links", "out_of_scope_links")


def cmd_sync(argv: list[str]) -> int:
    ap = cliparse.parser(
        prog="boost sync",
        description="Reconcile installed skills & symlinks against the lock file")
    ap.add_argument("--diff", action="store_true",
                    help="show the plan without applying it")
    ap.add_argument("--prune", action="store_true",
                    help="also delete orphaned store dirs and links outside "
                         "a declared --agent scope")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    plan = store.sync_plan()
    # A checkout can be missing skills its project lock records — that is the
    # normal state right after `git clone` — so sync repairs the repo too.
    pplan = store.project_sync_plan()

    if args.diff:
        if args.json:
            print(json.dumps(plan | {"project": pplan}, indent=2))
            return 0
        if not any(plan.values()) and not any(pplan.values()):
            out.ok("everything in sync")
            return 0
        if pplan["missing"]:
            out.heading("missing from this project (%d)" % len(pplan["missing"]))
            for name, agent in pplan["missing"]:
                out.info("%s → %s" % (name, agent))
        if pplan["orphaned"]:
            out.heading("unclaimed project skill dirs (%d)" % len(pplan["orphaned"]))
            for item in pplan["orphaned"]:
                out.info(_tilde(item))
        for key, label in _PLAN_LABELS:
            if not plan[key]:
                continue
            out.heading("%s (%d)" % (label, len(plan[key])))
            for item in plan[key]:
                if key in _PAIR_KEYS:
                    out.info("%s → %s" % (item[0], item[1]))
                elif key == "missing_materializations":
                    out.info("%s %s" % (item[0], item[1]))  # (kind, name)
                else:
                    out.info(_tilde(item))
        return 0

    actions = store.sync_apply(plan) + store.project_sync_apply(pplan)
    # Links outside a declared `--agent` scope work and are in use, so sync
    # reports them and stops. Removing one changes which agents can run a
    # skill, which is the same class of decision as deleting an orphaned store
    # dir — hence the same explicit `--prune`, and its own confirm so the two
    # are never approved as one.
    oos = plan["out_of_scope_links"]
    if args.prune and oos:
        go = (bool(os.environ.get("BOOST_ASSUME_YES")) if args.json else
              out.confirm("Remove %s outside their declared scope: %s?"
                          % (_plural(len(oos), "link"),
                             ", ".join("%s → %s" % (n, a) for n, a in oos))))
        if go:
            actions += store.prune_out_of_scope_links(plan)
            oos = []
    orphans = plan["orphaned_store"]
    pruned = []
    if args.prune and orphans:
        go = (bool(os.environ.get("BOOST_ASSUME_YES")) if args.json else
              out.confirm("Delete %s: %s?" % (_plural(len(orphans), "orphaned store dir"),
                                              ", ".join(orphans))))
        if go:
            for name in orphans:
                target = store.skill_store_dir(name)
                if target.is_dir():
                    util.rmtree(target)
                journal.log("prune", name)
                pruned.append(name)
    left = [n for n in orphans if n not in pruned]
    blocked = plan["blocked_links"]
    if args.json:
        print(json.dumps({"actions": actions, "pruned": pruned,
                          "orphaned_store": left, "out_of_scope_links": oos,
                          "blocked_links": blocked}))
        return 0
    for a in actions:
        out.ok(a)
    for name in pruned:
        out.ok("pruned %s" % _tilde(store.skill_store_dir(name)))
    if left:
        out.warn("%s left in place: %s — remove with `boost sync --prune`"
                 % (_plural(len(left), "orphaned store dir"), ", ".join(left)))
    if oos:
        out.warn("%s outside the declared scope: %s — remove with "
                 "`boost sync --prune`, or widen the scope with "
                 "`boost install <skill> --force` naming every `--agent`"
                 % (_plural(len(oos), "link"),
                    ", ".join("%s → %s" % (n, a) for n, a in oos)))
    # Before this, a blocked link produced no action and no warning, so the
    # branch below reported "everything in sync" for a repair that had just
    # been refused — and `boost doctor` went on prescribing this command.
    if blocked:
        out.warn("%s could not be created: %s. boost will not delete a file it "
                 "does not own — move or delete the path, then re-run `boost "
                 "sync`"
                 % (_plural(len(blocked), "agent link"),
                    ", ".join("%s → %s (%s in the way)"
                              % (n, a, _tilde(Path(p))) for n, a, p in blocked)))
    if not actions and not pruned and not left and not oos and not blocked:
        out.ok("everything in sync")
    return 0


# ── update ───────────────────────────────────────────────────────────────

def _show_and_confirm(label: str, diff, name: str) -> bool:
    """Print why an update is risky, show it, and ask. Shared by all kinds."""
    out.warn("%s: upstream update %s" % (label, "; ".join(diff.reasons)))
    print(diff.text)
    return out.confirm("Apply this update to %s?" % name)


def _confirm_risky_update(name: str, entry: dict) -> bool:
    """Gate an in-place update behind a visible diff when it is risky.

    Diffs the installed skill against the incoming source. If the change adds
    executable-looking instructions or prose aimed at redirecting the agent, the
    unified diff is printed and the update must be confirmed — so a poisoned
    update is *seen* before it lands. Routine edits apply silently. If the
    source can't be read we fail open and let ``store.install`` surface the real
    error rather than blocking on a phantom diff.
    """
    try:
        new_tree = updatediff.read_tree(store.source_dir_for(entry))
    except BoostError:
        return True
    diff = updatediff.diff_tree(updatediff.read_tree(store.skill_store_dir(name)),
                                new_tree)
    if not diff.risky:
        return True
    return _show_and_confirm(name, diff, name)


def _materialized_sides(kind: str, name: str, lk: dict, new_raw: str):
    """``(installed_text, incoming_text)`` for a rule/workflow, same shape both.

    Rules and workflows keep no copy of the source they were installed from —
    only the artifact they were materialized into. That artifact is the honest
    left-hand side anyway: it is the text the agent is loading *right now*, and
    a diff against it is the diff the user actually cares about.

    Each recorded materialization says how it was written, so the incoming half
    is reconstructed the same way: a verbatim rule drop compares raw to raw, a
    CLAUDE.md rule compares managed block to newly rendered block, and a
    workflow compares the rendered file to the same render of the new source —
    which keeps Gemini's TOML comparable with Gemini's TOML.

    Falls back to ``("", new_raw)`` when nothing can be read back, so an
    unreadable artifact scans the whole incoming file rather than nothing.
    """
    from ..core import rules, workflows
    for m in lk.get("materializations") or []:
        try:
            current = Path(m.get("path", "")).read_text(encoding="utf-8")
        except OSError:
            continue
        if kind == "rule":
            if m.get("mode") != rules.MODE_CLAUDE:
                return current, new_raw
            old = rules.read_block(current, name)
            if old is None:
                continue
            meta, body = frontmatter.parse(new_raw)
            return old, rules.render_claude_body(
                str(meta.get("name") or name), body)
        return current, workflows.render(
            m.get("agent"), m.get("slot", ""), name, new_raw)
    return "", new_raw


def _confirm_risky_materialized(kind: str, name: str, lk: dict,
                                new_raw: str) -> bool:
    """The same gate as `_confirm_risky_update`, for rules and workflows.

    This used to be absent, and the asymmetry ran the wrong way: a skill that
    grew a shell command was gated, while a rule — which is merged into the
    standing instructions the agent reads every session, and which this repo's
    own notes call "more invasive than a skill, not less" — was refreshed in
    place with one line of output and no diff.
    """
    old, new = _materialized_sides(kind, name, lk, new_raw)
    diff = updatediff.diff_tree({name: old}, {name: new})
    if not diff.risky:
        return True
    return _show_and_confirm("%s %s" % (kind, name), diff, name)


def _update_materialized(kind: str, installed: dict[str, dict], results) -> int:
    """Re-materialize installed rules/workflows whose tap source moved.

    Mirrors the skill upgrade loop: for each installed item from a refreshed
    tap, reinstall (force) when the source version bumped or its content sha
    changed — behind the same risky-diff gate the skill loop uses, and behind
    the same pin/quarantine skips: a pinned rule stays put, and refreshing a
    quarantined one would re-materialize the very content quarantine removed.
    Returns how many were refreshed.
    """
    import hashlib
    n = 0
    for name, lk in sorted(installed.items()):
        tapname = lk.get("tap")
        if lk.get("pinned") or lk.get("quarantined"):
            continue
        if tapname in (None, "local") or tapname not in results:
            continue
        matches = [e for e in catalog.find(name)
                   if e["tap"] == tapname and e.get("kind", "skill") == kind]
        if not matches:
            out.warn("%s %s is no longer in tap %s — leaving as-is"
                     % (kind, name, tapname))
            continue
        entry = matches[0]
        old_v = str(lk.get("version", "0.0.0"))
        new_v = str(entry.get("version", "0.0.0"))
        bumped = util.semver_gt(new_v, old_v)
        changed = bumped
        if not changed:
            try:
                src = registry.get(tapname).path / entry.get("skill_md", "")
                cur = (hashlib.sha256(
                    src.read_text(encoding="utf-8", errors="replace").encode("utf-8")
                ).hexdigest() if src.is_file() else None)
            except OSError:
                cur = None
            changed = bool(cur and cur != lk.get("sha256"))
        if not changed:
            continue
        try:
            new_raw = (registry.get(tapname).path
                       / entry.get("skill_md", "")).read_text(
                           encoding="utf-8", errors="replace")
        except (OSError, BoostError):
            new_raw = ""        # unreadable: store.install reports the real error
        if new_raw and not _confirm_risky_materialized(kind, name, lk, new_raw):
            out.warn("%s %s: update skipped — review the diff, then `boost "
                     "update --yes` to apply" % (kind, name))
            continue
        try:
            # keep the item where it was installed (user vs a specific repo).
            store.install(entry, force=True,
                          scope=lk.get("scope", "user"), base=lk.get("base"))
        except BoostError as err:
            out.warn("%s: %s" % (name, err.message))
            continue
        out.ok(("upgraded %s %s v%s → v%s" % (kind, name, old_v, new_v)) if bumped
               else ("refreshed %s %s v%s (source changed)" % (kind, name, new_v)))
        n += 1
    return n


def cmd_update(argv: list[str]) -> int:
    ap = cliparse.parser(prog="boost update",
                                 description="Sync taps or update installed skills")
    ap.add_argument("tap", nargs="?", metavar="TAP", help="refresh only this tap")
    ap.add_argument("--taps-only", action="store_true",
                    help="refresh tap clones & catalogs without touching skills")
    # Declared because this command *advertises* it: a skipped risky update
    # prints "review the diff, then `boost update --yes` to apply", and without
    # this line that instruction died on `unrecognized arguments: --yes` — the
    # only escape from the confirmation was a flag the parser rejected. The
    # behaviour needs nothing else: out.confirm() already honours --yes/-y off
    # sys.argv, so this makes the printed advice true rather than adding a path.
    ap.add_argument("-y", "--yes", action="store_true",
                    help="skip the confirmation prompt")
    args = ap.parse_args(argv)
    results, failures = registry.update(args.tap or None)
    if not results and not failures:
        out.info("no taps configured — start with `boost tap --defaults`")
        return 0
    for tname, summary in results.items():
        catalog.rebuild_tap(registry.get(tname))
        out.ok("%s: %s" % (tname, summary))
    # Report the dead ones by name, after the successes, so a broken upstream
    # reads as one line of bad news rather than as the whole command failing.
    for tname, err in failures.items():
        out.warn("%s: %s" % (tname, err))
    if failures:
        out.info(out.role(
            "%d of %d taps could not be refreshed — the rest are up to date. "
            "Drop a dead one with `boost untap <name>`."
            % (len(failures), len(results) + len(failures)), "muted"))
    # A pulled tap can add, drop, or rename catalogue entries, so the
    # completion name cache must not survive an update unrefreshed.
    complete.refresh_names()
    journal.log("update", args.tap or "all")
    if args.taps_only:
        # Same exit-code rule as the end of the full path: non-zero only when
        # nothing was refreshed at all. This early return predates that rule
        # and kept answering 0 with every tap dead — and a cron'd
        # `boost update --taps-only` exists precisely to notice that morning.
        return 1 if failures and not results else 0

    upgraded = 0
    for name, lk in sorted(lockfile.installed().items()):
        tapname = lk.get("tap")
        if (lk.get("pinned") or lk.get("quarantined")
                or tapname == "local" or tapname not in results):
            continue
        matches = [e for e in catalog.find(name) if e["tap"] == tapname]
        if not matches:
            out.warn("%s is no longer in tap %s — leaving as-is" % (name, tapname))
            continue
        entry = matches[0]
        old_v = str(lk.get("version", "0.0.0"))
        new_v = str(entry.get("version", "0.0.0"))
        head, src_sha = "", None
        if not util.semver_gt(new_v, old_v):
            head = gitutil.head_commit(registry.get(tapname).path)
            if head and head != lk.get("commit"):
                try:
                    src_sha = util.sha256_dir(store.source_dir_for(entry))
                except BoostError:
                    continue
        reason = staleness.upstream_reason(old_v, new_v, lk.get("commit", ""),
                                           head, lk.get("sha256", ""), src_sha)
        if reason is None:
            continue
        if not _confirm_risky_update(name, entry):
            out.warn("%s: update skipped — review the diff, then `boost update "
                     "--yes` to apply" % name)
            continue
        try:
            store.install(entry, force=True)
        except BoostError as err:
            out.warn("%s: %s" % (name, err.message))
            continue
        if reason == "version":
            out.ok("upgraded %s v%s → v%s" % (name, old_v, new_v))
        else:
            out.ok("refreshed %s v%s (source changed)" % (name, new_v))
        upgraded += 1
    # Rules and workflows refresh from the same tap update.
    upgraded += _update_materialized("rule", lockfile.installed_rules(), results)
    upgraded += _update_materialized("workflow", lockfile.installed_workflows(), results)
    if not upgraded:
        # Don't claim "everything up to date" when some taps were never
        # reached — that is exactly the false all-clear this fix exists to stop.
        out.ok("everything up to date" if not failures
               else "everything up to date, except the taps above")
    # Non-zero only when nothing was refreshed at all. A partial run did the job
    # it could do, and failing it would put us back to one dead upstream
    # breaking `boost update` for the other 79.
    return 1 if failures and not results else 0


# ── reinstall ────────────────────────────────────────────────────────────

def cmd_reinstall(argv: list[str]) -> int:
    ap = cliparse.parser(prog="boost reinstall",
                                 description="Reinstall an installed skill, "
                                             "rule or workflow (force)")
    ap.add_argument("names", nargs="*", metavar="NAME")
    ap.add_argument("--all", action="store_true",
                    help="reinstall every installed skill, rule and workflow")
    args = ap.parse_args(argv)
    done, failed = 0, 0
    done_kinds: set[str] = set()
    items: list[tuple] = []
    if args.all:
        items = [(kind, name, entry)
                 for kind, section in lockfile.all_installed().items()
                 for name, entry in sorted(section.items())]
        if not items:
            raise BoostError("nothing to reinstall",
                            hint="nothing installed yet — see `boost list`")
    elif not args.names:
        raise BoostError("nothing to reinstall",
                        hint="name a skill or pass --all")
    else:
        for name in args.names:
            found = lockfile.find_any(name)
            if found is None:
                if len(args.names) == 1:
                    raise BoostError("%s is not installed" % name,
                                    hint="see what is with `boost list`")
                out.warn("%s is not installed — skipped" % name)
                failed += 1
                continue
            items.append((found[0], name, found[1]))
    for kind, name, lk in items:
        if kind != "skill":
            # Rules/workflows always come from a tap (`boost import` is
            # skill-only), so resolve the catalog entry the way
            # _update_materialized does and re-materialize where it was
            # installed (user config vs a specific repo). store.install with
            # force also clears a quarantine flag — the reinstall puts the
            # content back, so the lock must say so.
            matches = [e for e in catalog.find(name)
                       if e["tap"] == lk.get("tap")
                       and e.get("kind", "skill") == kind]
            if not matches:
                out.warn("%s %s not found in tap %s — skipped (try `boost update`)"
                         % (kind, name, lk.get("tap")))
                failed += 1
                continue
            try:
                store.install(matches[0], force=True,
                              scope=lk.get("scope", "user"), base=lk.get("base"))
            except BoostError as err:
                out.warn("%s: %s" % (name, err.message))
                failed += 1
                continue
            out.ok("reinstalled %s %s v%s"
                   % (kind, name, matches[0].get("version", "0.0.0")))
            done += 1
            done_kinds.add(kind)
            continue
        if lk.get("tap") == "local":
            src = Path(str(lk.get("source_dir") or ""))
            if src.is_dir() and (src / "SKILL.md").exists():
                # force=True to match the tap branch's `install(..., force=True)`:
                # reinstalling a pinned skill is the point of the command. Policy
                # still applies. The try/except mirrors the tap branch too —
                # without it one policy-blocked skill aborts `--all` mid-run and
                # the remaining names are never attempted.
                try:
                    store.install_from_path(src, name=name, force=True)
                except BoostError as err:
                    out.warn("%s: %s" % (name, err.message))
                    failed += 1
                    continue
                out.ok("reinstalled %s (local, from %s)" % (name, _tilde(src)))
                done += 1
                done_kinds.add("skill")
            else:
                out.warn("%s: local source %s is gone — skipped" % (name, _tilde(src)))
                failed += 1
            continue
        matches = [e for e in catalog.find(name) if e["tap"] == lk.get("tap")]
        if not matches:
            out.warn("%s not found in tap %s — skipped (try `boost update`)"
                     % (name, lk.get("tap")))
            failed += 1
            continue
        try:
            store.install(matches[0], force=True)
        except BoostError as err:
            out.warn("%s: %s" % (name, err.message))
            failed += 1
            continue
        out.ok("reinstalled %s v%s" % (name, matches[0].get("version", "0.0.0")))
        done += 1
        done_kinds.add("skill")
    # Name the kind when only one was touched; a mixed run says "items".
    noun = next(iter(done_kinds)) if len(done_kinds) == 1 else (
        "item" if done_kinds else "skill")
    out.info("Reinstalled %s" % _plural(done, noun))
    return 1 if failed else 0


# ── bundle ───────────────────────────────────────────────────────────────

def cmd_bundle(argv: list[str]) -> int:
    ap = cliparse.parser(prog="boost bundle",
                                 description="Export/install skill sets via a Boostfile")
    ap.add_argument("action", choices=("dump", "install"))
    ap.add_argument("file", nargs="?", metavar="FILE",
                    help="Boostfile (dump: default stdout; "
                         "install: default ./Boostfile, '-' = stdin)")
    args = ap.parse_args(argv)
    if args.action == "dump":
        return _bundle_dump(args.file)
    return _bundle_install(args.file)


def _bundle_dump(file: str | None) -> int:
    text = _boostfile_text(lockfile.installed())
    others = _others_installed()
    if not file or file == "-":
        print(text, end="")
        if others:
            # stdout IS the Boostfile here; the omission notice goes to stderr
            # so `boost bundle dump > Boostfile` stays a parseable artifact.
            print("  ! %s not captured — Boostfiles carry skills only" % others,
                  file=sys.stderr)
        return 0
    dest = paths.expand(file)
    try:
        dest.write_text(text, encoding="utf-8")
    except OSError as e:
        raise BoostError("cannot write %s: %s" % (_tilde(dest), e.strerror or e),
                        hint="check the path exists and is writable") from e
    n_taps = sum(1 for ln in text.splitlines() if ln.startswith("tap "))
    n_skills = sum(1 for ln in text.splitlines() if ln.startswith("skill "))
    out.ok("wrote %s (%s, %s)" % (_tilde(dest), _plural(n_taps, "tap"),
                                  _plural(n_skills, "skill")))
    if others:
        out.warn("%s not captured — Boostfiles carry skills only" % others)
    return 0


def _bundle_install(file: str | None) -> int:
    if file == "-":
        text, label = sys.stdin.read(), "<stdin>"
    else:
        path = paths.expand(file or "./Boostfile")
        if not path.exists():
            raise BoostError("no Boostfile at %s" % _tilde(path),
                            hint="create one with `boost bundle dump Boostfile`")
        if path.is_dir():
            raise BoostError("%s is a directory, not a Boostfile" % _tilde(path),
                            hint="point at the Boostfile itself, "
                                 "or use `boost import` for skill directories")
        try:
            text, label = path.read_text(encoding="utf-8"), str(path)
        except OSError as e:
            raise BoostError("cannot read %s: %s" % (_tilde(path), e.strerror or e)) from e
    taps_added = installed_n = present = failed = 0
    have_taps = {t.name for t in registry.list_taps()}
    # name -> kind across every lock section, so a `skill` line naming an
    # already-installed rule/workflow is counted present, not re-installed.
    have_installed: dict[str, str] = {}
    for kind, section in lockfile.all_installed().items():
        for n in section:              # first section wins: skill > rule >
            have_installed.setdefault(n, kind)  # workflow, same as find_any

    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 2)
        if parts[0] == "tap" and len(parts) >= 2:
            tname, turl = parts[1], parts[2] if len(parts) > 2 else ""
            if tname in have_taps:
                continue
            try:
                tap = registry.add(turl or tname)
                catalog.rebuild_tap(tap)
            except BoostError as err:
                out.warn("tap %s failed: %s" % (tname, err.message))
                failed += 1
                continue
            have_taps.add(tap.name)
            taps_added += 1
            out.ok("tapped %s" % tap.name)
        elif parts[0] == "skill" and len(parts) >= 2:
            tapq, _, rest = parts[1].rpartition(":")
            sname, _, sver = rest.partition("@")
            kind_here = have_installed.get(sname)
            if kind_here is not None:
                if kind_here != "skill":
                    out.info("%s is already installed as a %s — skipped"
                             % (sname, kind_here))
                present += 1
                continue
            matches = catalog.find(sname, tap=tapq or None)
            if not matches:
                out.warn("%s not found%s — skipped"
                         % (sname, (" in tap %s" % tapq) if tapq else ""))
                failed += 1
                continue
            if len({e["tap"] for e in matches}) > 1:
                # A Boostfile is meant to be reproducible, so guessing which tap
                # `skills:brainstorming` meant is the one thing this must not do.
                out.warn("%s is ambiguous — in %s; qualify it as owner/repo:%s"
                         % (sname, ", ".join(sorted({e["tap"] for e in matches})),
                            sname))
                failed += 1
                continue
            entry = matches[0]
            if sver and str(entry.get("version")) != sver:
                out.warn("%s: Boostfile wants @%s, tap has %s — installing that"
                         % (sname, sver, entry.get("version")))
            try:
                store.install(entry)
            except BoostError as err:
                out.warn("%s: %s" % (sname, err.message))
                failed += 1
                continue
            out.ok("installed %s v%s (%s)" % (sname, entry.get("version"),
                                              entry["tap"]))
            have_installed[sname] = entry.get("kind", "skill")
            installed_n += 1
        else:
            out.warn("line %d: unrecognised: %s" % (lineno, line))
            failed += 1
    if taps_added:
        complete.refresh_names()
    journal.log("bundle-install", label, taps=taps_added, skills=installed_n)
    summary = "Installed %s" % _plural(installed_n, "skill")
    if taps_added:
        summary += ", added %s" % _plural(taps_added, "tap")
    if present:
        summary += ", %d already present" % present
    if failed:
        summary += ", %d failed" % failed
    out.info(summary)
    return 1 if failed else 0


# ── import ───────────────────────────────────────────────────────────────

def cmd_import(argv: list[str]) -> int:
    ap = cliparse.parser(
        prog="boost import",
        description="Import skills from a GitHub URL or local path")
    ap.add_argument("source", metavar="URL_OR_PATH")
    ap.add_argument("--name", metavar="N",
                    help="skill to pick when several are found (or a rename)")
    ap.add_argument("--all", action="store_true", help="import every skill found")
    ap.add_argument("--agent", action="append", metavar="A",
                    help="link only into this agent (repeatable)")
    args = ap.parse_args(argv)
    only = _check_agents(args.agent)
    tmp = None
    try:
        if args.source.startswith(("http://", "https://", "git@", "ssh://")):
            tmp = Path(tempfile.mkdtemp(prefix="boost-import-"))
            root = tmp / "repo"
            out.info("cloning %s …" % args.source)
            # Full checkout, not a tap's Markdown cone: import reads whatever the
            # repo ships and copies it verbatim, assets included.
            gitutil.clone_shallow(args.source, root, sparse=False)
        else:
            root = paths.expand(args.source)
            if not root.is_dir():
                raise BoostError("no such directory: %s" % args.source,
                                hint="pass a local path or a git URL")
        return _import_root(root, args.name, args.all, only, args.source)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def _import_root(root: Path, name: str | None, do_all: bool,
                 only: list[str] | None, display: str) -> int:
    def one(skill_dir: Path, rename: str | None = None) -> int:
        res = store.install_from_path(skill_dir, name=rename, only_agents=only)
        _report_result(res)
        out.info("Imported %s; quality score %d/100" % (res.name, res.score))
        return 0

    if (root / "SKILL.md").exists():
        return one(root, rename=name)
    entries = catalog.scan_dir(root)
    if not entries:
        raise BoostError("no SKILL.md found under %s" % display)

    def dir_of(e: dict) -> Path:
        return root if e["rel_dir"] == "." else root / e["rel_dir"]

    if len(entries) == 1:
        return one(dir_of(entries[0]), rename=name)
    if name and not do_all:
        picks = [e for e in entries if e["name"] == name]
        if not picks:
            raise BoostError("no skill named %r in %s" % (name, display),
                            hint="available: %s" % ", ".join(e["name"] for e in entries))
        return one(dir_of(picks[0]))
    if do_all:
        # One refused skill must not abandon the rest: same contract as a
        # multi-skill `boost install`, which warns per item and still reports a
        # summary (test_multi_policy_block_rc1_others_install).
        imported, refused = 0, 0
        for e in entries:
            try:
                res = store.install_from_path(dir_of(e), only_agents=only)
            except BoostError as err:
                out.warn("%s: %s" % (e["name"], err.message))
                refused += 1
                continue
            out.ok("imported %s v%s (score %d/100)" % (res.name, e["version"],
                                                       res.score))
            imported += 1
        out.info("Imported %s" % _plural(imported, "skill"))
        return 1 if refused else 0
    out.heading("%d skills in %s" % (len(entries), display))
    out.table([(e["name"], "v" + e["version"], (e["description"] or "")[:60])
               for e in entries])
    raise BoostError("multiple skills found — pick one or import all",
                    hint="add `--name NAME` or `--all`")


# ── pin / unpin ──────────────────────────────────────────────────────────

def cmd_pin(argv: list[str]) -> int:
    ap = cliparse.parser(prog="boost pin",
                                 description="Pin a skill to its current version")
    ap.add_argument("name", metavar="NAME")
    ap.add_argument("--commit", action="store_true",
                    help="also freeze the exact source commit (integrity pin)")
    args = ap.parse_args(argv)
    rc = _set_pin(args.name, True)
    found = lockfile.find_any(args.name)
    if rc == 0 and args.commit and found is not None:
        kind, entry = found
        commit = integrity.set_commit_pin(args.name, entry, kind=kind)
        journal.log("pin-commit", args.name, commit=commit)
        out.ok("commit-pinned %s at %s" % (args.name, commit[:12]))
        out.dim("  `boost verify` fails if the recorded commit ever moves off it")
    return rc


def cmd_unpin(argv: list[str]) -> int:
    ap = cliparse.parser(prog="boost unpin",
                                 description="Allow a pinned skill to update again")
    ap.add_argument("name", metavar="NAME")
    args = ap.parse_args(argv)
    # Releasing the version pin releases the commit pin with it — a commit pin
    # only makes sense while the skill is otherwise frozen.
    found = lockfile.find_any(args.name)
    if found and integrity.clear_commit_pin(args.name, found[1], kind=found[0]):
        out.dim("  released the commit pin too")
    return _set_pin(args.name, False)


def _set_pin(name: str, pinned: bool) -> int:
    # All three kinds pin: the flag is persisted on any lock entry and the
    # update loops (skills at cmd_update, rules/workflows at
    # _update_materialized) each honour it.
    found = lockfile.find_any(name)
    if not found:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    kind, entry = found
    for other in _shadowed_kinds(name, kind):
        out.warn("a %s named %s is also installed — this pins the %s only"
                 % (other, name, kind))
    label = name if kind == "skill" else "%s %s" % (kind, name)
    version = entry.get("version", "0.0.0")
    if bool(entry.get("pinned")) == pinned:
        out.info("%s is already %s" % (label, "pinned at v%s" % version
                                       if pinned else "unpinned"))
        return 0
    entry["pinned"] = pinned
    lockfile.set_entry(kind, name, entry)
    journal.log("pin" if pinned else "unpin", name)
    if pinned:
        out.ok("pinned %s at v%s — `boost update` will skip it" % (label, version))
    else:
        out.ok("unpinned %s (v%s) — updates apply again" % (label, version))
    return 0


# ── snapshot ─────────────────────────────────────────────────────────────

def cmd_snapshot(argv: list[str]) -> int:
    ap = cliparse.parser(prog="boost snapshot",
                                 description="Save & restore whole skill environments")
    ap.add_argument("action", choices=("save", "list", "restore"))
    ap.add_argument("arg", nargs="?", metavar="LABEL|ID",
                    help="label for save, snapshot id for restore")
    ap.add_argument("--json", action="store_true",
                    help="machine-readable output (list)")
    args = ap.parse_args(argv)
    if args.action == "save":
        return _snapshot_save(args.arg)
    if args.action == "list":
        return _snapshot_list(args.json)
    if not args.arg:
        raise BoostError("restore needs a snapshot id",
                        hint="see `boost snapshot list`")
    return _snapshot_restore(args.arg)


def _snapshot_save(label: str | None) -> int:
    paths.ensure_dirs()
    base = "snap-" + datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    snap_id, serial = base, 1
    while (paths.snapshots_dir() / (snap_id + ".tar.gz")).exists():
        serial += 1
        snap_id = "%s-%d" % (base, serial)
    tar_path = paths.snapshots_dir() / (snap_id + ".tar.gz")
    with tarfile.open(str(tar_path), "w:gz") as tf:
        for child in sorted(paths.store_dir().iterdir()):
            tf.add(str(child), arcname=child.name)
    skill_count = len(lockfile.installed())
    manifest = {"id": snap_id, "label": label or "", "created": util.now_iso(),
                "skills": skill_count}
    (paths.snapshots_dir() / (snap_id + ".json")).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    journal.log("snapshot", snap_id, label=label)
    out.ok("saved %s (%s, %s)" % (snap_id, _plural(skill_count, "skill"),
                                  util.human_size(tar_path.stat().st_size)))
    others = _others_installed()
    if others:
        out.warn("%s not captured — snapshots cover the skill store only" % others)
    out.info("restore with `boost snapshot restore %s`" % snap_id)
    return 0


def _snapshot_list(as_json: bool) -> int:
    paths.ensure_dirs()
    snaps = []
    # newest first; file mtime keeps same-second saves (snap-...-2) in order
    for tar_path in sorted(paths.snapshots_dir().glob("snap-*.tar.gz"),
                           key=lambda p: (p.stat().st_mtime, p.name),
                           reverse=True):
        snap_id = tar_path.name[:-len(".tar.gz")]
        side = tar_path.parent / (snap_id + ".json")
        meta = {}
        if side.exists():
            try:
                meta = json.loads(side.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                meta = {}
        snaps.append({"id": snap_id, "created": meta.get("created", ""),
                      "label": meta.get("label", ""),
                      "skills": meta.get("skills", "?"),
                      "size": tar_path.stat().st_size})
    if as_json:
        print(json.dumps(snaps, indent=2))
        return 0
    if not snaps:
        out.info("no snapshots yet — create one with `boost snapshot save`")
        return 0
    out.table([(s["id"], util.rel_time(s["created"]) if s["created"] else "?",
                s["label"] or "—", s["skills"], util.human_size(s["size"]))
               for s in snaps],
              headers=("ID", "WHEN", "LABEL", "SKILLS", "SIZE"))
    return 0


def _snapshot_restore(snap_id: str) -> int:
    if not snap_id.startswith("snap-"):
        snap_id = "snap-" + snap_id
    tar_path = paths.snapshots_dir() / (snap_id + ".tar.gz")
    if not tar_path.exists():
        raise BoostError("no snapshot %s" % snap_id,
                        hint="see `boost snapshot list`")
    root = paths.store_dir()
    if not out.confirm("Restore %s? This replaces everything in %s"
                       % (snap_id, _tilde(root))):
        out.info("cancelled")
        return 0
    paths.ensure_dirs()
    # Read the whole archive BEFORE touching the store, so a corrupt
    # snapshot can never leave us with an emptied environment.
    try:
        tf = tarfile.open(str(tar_path), "r:gz")  # noqa: SIM115  (opened in a try to translate the error; used via `with tf:` below)
    except (tarfile.TarError, OSError, EOFError) as e:
        raise BoostError("snapshot %s is unreadable: %s" % (snap_id, e),
                        hint="the store was left untouched — "
                             "see `boost snapshot list` for other snapshots") from e
    with tf:
        try:
            members = tf.getmembers()
        except (tarfile.TarError, OSError, EOFError) as e:
            raise BoostError("snapshot %s is corrupt: %s" % (snap_id, e),
                            hint="the store was left untouched — "
                                 "see `boost snapshot list` for other snapshots") from e
        for child in root.iterdir():
            if child.is_dir() and not child.is_symlink():
                util.rmtree(child)
            else:
                child.unlink()
        try:
            tf.extractall(str(root), members=members, filter="data")
        except TypeError:  # Python < 3.12: no data filter available
            # snapshots are archives boost itself produced under the user's own
            # store (never fetched from a remote), so this legacy-interpreter
            # fallback restores a locally-trusted tar.
            tf.extractall(str(root), members=members)  # noqa: S202
    for action in store.sync_apply(store.sync_plan()):
        out.ok(action)
    journal.log("snapshot-restore", snap_id)
    out.ok("restored %s (%s)" % (snap_id,
                                 _plural(len(lockfile.installed()), "skill")))
    others = _others_installed()
    if others:
        out.warn("%s untouched — snapshots cover the skill store only" % others)
    return 0


# ── export ───────────────────────────────────────────────────────────────

def cmd_export(argv: list[str]) -> int:
    ap = cliparse.parser(
        prog="boost export",
        description="Package skills as shareable zip/tar archives")
    ap.add_argument("names", nargs="*", metavar="NAME",
                    help="skills to export (default: all installed)")
    ap.add_argument("-o", "--out", metavar="OUT", help="output archive path")
    ap.add_argument("--zip", action="store_true",
                    help="build a .zip instead of .tar.gz")
    args = ap.parse_args(argv)
    installed = lockfile.installed()
    names = args.names or sorted(installed)
    if not names:
        others = _others_installed()
        raise BoostError("no skills installed to export",
                        hint=("%s installed, but export packages skills only"
                              % others) if others
                             else "install some with `boost install`")
    chosen = {}
    for name in names:
        if name not in installed:
            found = lockfile.find_any(name)
            if found is not None:
                # Same truth _iter_installed tells: it exists, as another kind
                # — a rule/workflow has no store directory to package.
                raise BoostError("%s is a %s — `boost export` applies to skills"
                                % (name, found[0]),
                                hint="rules and workflows materialize into "
                                     "agent config files; reinstall them "
                                     "from their tap")
            raise BoostError("%s is not installed" % name,
                            hint="see what is with `boost list`")
        if not store.skill_store_dir(name).is_dir():
            raise BoostError("store dir for %s is missing" % name,
                            hint="repair with `boost sync`")
        chosen[name] = installed[name]
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    ext = ".zip" if args.zip else ".tar.gz"
    dest = paths.expand(args.out) if args.out else Path(
        "boost-skills-%s%s" % (stamp, ext))
    manifest = _boostfile_text(chosen, via="boost export")
    try:
        if args.zip:
            with zipfile.ZipFile(str(dest), "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("Boostfile", manifest)
                for name in chosen:
                    sdir = store.skill_store_dir(name)
                    for f in sorted(p for p in sdir.rglob("*") if p.is_file()):
                        zf.write(str(f), arcname="%s/%s" % (name, f.relative_to(sdir).as_posix()))
        else:
            with tarfile.open(str(dest), "w:gz") as tf:
                data = manifest.encode()
                ti = tarfile.TarInfo("Boostfile")
                ti.size = len(data)
                ti.mtime = int(datetime.now(UTC).timestamp())
                ti.mode = 0o644
                tf.addfile(ti, io.BytesIO(data))
                for name in chosen:
                    tf.add(str(store.skill_store_dir(name)), arcname=name)
    except OSError as e:
        raise BoostError("cannot write %s: %s" % (_tilde(dest), e.strerror or e),
                        hint="check the output path exists and is writable") from e
    out.ok("exported %s → %s (%s)" % (_plural(len(chosen), "skill"),
                                      _tilde(dest.resolve()),
                                      util.human_size(dest.stat().st_size)))
    others = _others_installed()
    if others:
        out.warn("%s not included — export packages skills only" % others)
    return 0


def _resolve_skill(name: str):
    """(display, description, body, skill_md_path, meta) for a skill.

    Resolves the installed store first, then any tap clone, and returns the
    SKILL.md path + parsed frontmatter alongside the display fields so callers
    that need the skill's directory (e.g. subagent discovery for multi-agent
    adaptation) don't re-resolve. Raises BoostError if the name resolves
    nowhere.
    """
    p = store.skill_store_dir(name) / "SKILL.md"
    if not p.exists():
        entry = catalog.resolve_one(name)   # raises BoostError if unknown
        p = registry.get(entry["tap"]).path / entry["skill_md"]
        if not p.exists():
            raise BoostError("SKILL.md missing for %s" % name,
                            hint="refresh the tap with `boost update`")
    meta, body = frontmatter.parse(p.read_text(encoding="utf-8", errors="replace"))
    display = str(meta.get("name") or name).strip() or name
    return display, str(meta.get("description") or "").strip(), body, p, meta


def _resolve_skill_source(name: str):
    """(display_name, description, body) for a skill — the text-only view of
    :func:`_resolve_skill`, used where the skill's directory isn't needed."""
    display, description, body, _p, _meta = _resolve_skill(name)
    return display, description, body


def cmd_adapt(argv: list[str]) -> int:
    ap = cliparse.parser(
        prog="boost adapt",
        description="Render a skill as another agent framework's native source")
    ap.add_argument("name", help="skill to adapt")
    ap.add_argument("--to", metavar="FRAMEWORK", required=True,
                    help="target framework: %s" % ", ".join(adapters.formats()))
    ap.add_argument("--model", metavar="M", default=None,
                    help="LLM the exported agent runs on (default: boost's "
                         "ai.model; pass 'none' for the framework's own default)")
    ap.add_argument("-o", "--out", metavar="FILE",
                    help="write to FILE instead of stdout")
    args = ap.parse_args(argv)
    if args.to not in adapters.FORMATS:
        raise BoostError("unknown framework: %s" % args.to,
                        hint="supported: %s" % ", ".join(adapters.formats()))
    # Default to boost's configured model so exported agents run on the same LLM
    # boost uses; `--model none` opts out and lets the framework pick.
    model = args.model if args.model is not None else str(config.get("ai.model") or "")
    if model.strip().lower() in ("none", "off", ""):
        model = None
    display, description, body, skill_md, meta = _resolve_skill(args.name)
    # A skill that declares subagents projects to a runnable multi-agent
    # workflow (a CrewAI Crew / LangGraph StateGraph) when the target supports
    # one; flat skills — and multi-agent targets without a crew path — keep the
    # single-Agent render.
    subagents = adapters.discover_subagents(skill_md.parent)
    crew_size = 0
    if subagents and adapters.supports_multi(args.to):
        primary = adapters.AgentSpec(display, description, body,
                                     adapters.parse_tools(meta))
        source = adapters.render_multi(args.to, display, description,
                                       [primary, *subagents], model)
        crew_size = len(subagents) + 1
    else:
        if subagents:
            sys.stderr.write(
                "note: %s declares %d subagent(s); %s has no crew/graph path, "
                "so only its primary agent was rendered.\n"
                % (display, len(subagents), args.to))
        source = adapters.render(args.to, display, description, body, model)
    if args.out:
        dest = paths.expand(args.out)
        try:
            util.atomic_write_text(dest, source)
        except OSError as e:
            raise BoostError("cannot write %s: %s" % (_tilde(dest), e.strerror or e),
                            hint="check the output path exists and is writable") from e
        shape = "crew of %d" % crew_size if crew_size else args.to
        out.ok("adapted %s → %s (%s · %s)" % (display, _tilde(dest.resolve()),
                                              shape, model or "framework default"))
    else:
        sys.stdout.write(source)
    return 0
