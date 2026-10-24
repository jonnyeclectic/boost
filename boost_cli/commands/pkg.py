# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Package Management commands (11): install, uninstall, sync, update,
reinstall, bundle, import, pin, unpin, snapshot, export."""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tarfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from .. import cliparse, spin
from ..core import (
    adapters,
    agents,
    archive,
    boostfile,
    catalog,
    complete,
    config,
    foreign,
    frontmatter,
    gitutil,
    installplan,
    installscan,
    integrity,
    journal,
    lockfile,
    paths,
    projectlock,
    rag,
    registry,
    scopes,
    snapshot,
    staleness,
    store,
    typedvalue,
    updatediff,
    util,
)
from ..core import output as out
from ..errors import BoostError
from ._common import _shadowed_kinds

_tilde = paths.tilde


def _plural(n: int, word: str) -> str:
    if n != 1 and word.endswith("y") and word[-2:-1] not in "aeiou":
        return "%d %s" % (n, word[:-1] + "ies")  # entry -> entries
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def _warn_confusions(entries: list[dict]) -> None:
    """Warn when a skill about to be installed is confusable with one from a
    *different* tap — the typosquat / owner-confusion guard."""
    for line in installplan.confusion_lines(entries):
        out.warn(line)


def _print_plan(the_plan: installplan.InstallPlan) -> None:
    """Say what :func:`installplan.plan` found, in ``boost install``'s words.

    A look-alike from a *different* tap (the typosquat / owner-confusion
    guard), the dependencies pulled in, and the requirements left out. The
    words live in ``core.installplan`` so MCP ``boost_install`` and ``boost
    browse`` say the same thing."""
    for line in the_plan.confusions:
        out.warn(line)
    if the_plan.added:
        out.info(the_plan.added)
    for line in the_plan.dep_warnings:
        out.warn(line, wrap=True)


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
    if not rows or no_mcp or typedvalue.env_flag("BOOST_NO_MCP_OFFER", unknown=True):
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
        elif res.mcp_error:
            # Refused rather than rebuilt: the file is the user's, and
            # rewriting an unparseable one from an empty view loses every
            # server in it.
            out.warn("%s left unchanged — %s not recorded"
                     % (mcpdecl.SIDECAR, ", ".join(wanted)))
            out.dim("  %s" % res.mcp_error)
            out.dim("  the skill is installed; fix %s and reinstall to record "
                    "them" % mcpdecl.SIDECAR, wrap=True)
        else:
            # Every server was already there — another skill's or the user's.
            out.dim("  %s already in %s" % (", ".join(wanted), mcpdecl.SIDECAR))
        return
    out.info("")
    out.warn("%s needs %s to work:" % (res.name, _plural(len(rows), "MCP server")))
    for row in rows:
        line = mcpdecl.command_line(row["spec"]) if row["spec"] else ""
        how = "`%s`" % line if line else "no command declared"
        out.info("  %s  %s" % (out.c(row["name"], out.BOLD),
                               out.role(how, "muted")))
    wirable = mcpdecl.registrable(rows)
    if not wirable:
        # Name-only declarations: boost will not invent a command line.
        out.dim("  install these yourself, then `boost mcp register`", wrap=True)
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
    if not out.confirm(
            "  register %s with %s, for every project on this machine?"
            % (_plural(len(wirable), "server"), where), default=False):
        out.dim("  skipped — run these yourself when you're ready:", wrap=True)
        for row in wirable:
            # One line per host, not `targets[0]` — the prompt named every
            # host and a yes would have registered with every one, so a no
            # that prints only the first hands back an incomplete answer.
            # `hosts()` order puts the newest host last — agy when this was
            # written, Codex now — so the host whose grammar differs most
            # from Claude's was the one never shown.
            for host in targets:
                argv = mcpdecl.register_argv(row["name"], row["spec"],
                                             host=host, scope=res.scope)
                out.info("    " + mcphost.shell_line(argv))
        return
    for row in wirable:
        for host in targets:
            _register_mcp_server(row["name"], row["spec"], host=host,
                                 scope=res.scope)


def _register_mcp_server(name: str, spec: dict, host: str = "claude",
                         scope: str = "user") -> None:
    """Run one `<host> mcp add` for a skill-declared server.

    Never raises on a *runtime* failure — a missing CLI, a refused config
    file, a timeout or a non-zero exit is reported and swallowed, because an
    install must not die on the optional step that follows it. A scope this
    function cannot model is a different thing: a programming error, and it
    raises.

    ``scope`` is threaded from the install rather than defaulted, because
    ``register_argv``'s own default is ``"user"`` and silently taking it is how
    a ``--scope project`` install ended up registering machine-wide.

    Only user scope reaches here — :func:`_offer_mcp` returns early for a
    project install — and the guard below is why that stays an invariant
    rather than a coincidence: it models the *user-scope* file, so a project
    registration (``<cwd>/.mcp.json``) would be judged against a path nothing
    was going to write. Fail loudly instead of guarding the wrong file.
    """
    import subprocess

    from ..core import mcpdecl, mcphost
    if scope != "user":
        raise ValueError("MCP registration is user-scope only, got %r" % scope)
    argv = mcpdecl.register_argv(name, spec, host=host, scope=scope)
    if not shutil.which(mcphost.cli(host)):
        out.warn("`%s` CLI not found — run this yourself:" % mcphost.cli(host))
        out.info("  " + mcphost.shell_line(argv))
        return
    # The same sandbox guard `boost mcp` applies, for the same reason: the
    # child resolves its config home from the ambient environment, so an
    # install run under HOME=<tempdir> would write a skill's MCP server into
    # the real one. There is no --force here — this is an install prompt, not
    # a flag surface — so the argv is printed and the user decides.
    boost_home = paths.home()
    cfg = mcphost.escapes_home(host, os.environ, boost_home)
    if cfg:
        out.warn("not registering %s with %s: %s is outside this $HOME (%s)"
                 % (name, mcphost.label(host), cfg, boost_home), wrap=True)
        out.info("  run it yourself: " + mcphost.shell_line(argv))
        return
    try:
        proc = subprocess.run(util.resolve_exe(argv), capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        out.warn("could not register %s: %s" % (name, e))
        out.info("  run it yourself: " + mcphost.shell_line(argv))
        return
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()
        out.warn("could not register %s: %s"
                 % (name, tail[-1] if tail else "unknown error"))
        out.info("  run it yourself: " + mcphost.shell_line(argv))
        return
    out.ok("registered MCP server %s with %s" % (name, mcphost.label(host)))
    journal.log("mcp-register", name, host=host)


def _report_result(res: store.InstallResult, no_mcp: bool = False) -> None:
    """The canonical three-line install report."""
    if res.kind in ("rule", "workflow"):
        where = " (this repo)" if res.scope == "project" else ""
        out.ok("materialized%s → %s"
               % (where, " · ".join(res.linked) or "(no enabled agents)"))
        _report_skill_copy(res)
        _warn_unwritable(res)
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
                % projectlock.LOCK_DIRNAME, wrap=True)
        _warn_submodules(res)
        _warn_injection(res)
        _warn_secrets(res)
        _offer_mcp(res, no_mcp=no_mcp)
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
    _warn_unwritable(res)
    out.ok("lock updated (.skill-lock.json)")
    _warn_injection(res)
    _warn_secrets(res)
    _offer_mcp(res, no_mcp=no_mcp)


def _report_skill_copy(res) -> None:
    """The workflow's copy in the skill store, on its own line. Its own line
    so the ``materialized →`` field stays the list of agents a dry run
    predicts. Why there is none is :func:`_warn_unwritable`'s to say, so
    update, reinstall and sync say it too."""
    copy = getattr(res, "skill_copy", None)
    if copy is not None:
        out.ok("as a skill → %s" % _tilde(copy))


def _warn_submodules(res, stream=None) -> None:
    """A submodule installs as an empty dir: said by name, so the success
    line is not read as a complete skill."""
    for sub in getattr(res, "submodules", None) or ():
        out.warn("%s: %s" % (res.name, store.submodule_note(sub)),
                 stream=stream, wrap=True)


def _warn_unwritable(res, stream=None) -> None:
    """Name what an install skipped, and the remedy — every path that
    installs, reinstall and update included, so none reports success over an
    agent it silently left out.

    A conflict is a real file squatting a skill's link path. An unwritable dir
    refused a link, or a rule or workflow file; the refused agent is still
    recorded, so `boost sync` writes it once the dir allows it.

    ``stream`` for a caller speaking JSON on stdout: relinking under
    `focus --json` must still say what it skipped, on stderr."""
    # What became of the workflow's skill copy: retired, kept as edited, or
    # skipped for a name something else holds. Every caller that installs
    # passes through here, so none removes a copy without a word.
    note = getattr(res, "skill_note", None)
    if note:
        out.info(note, stream=stream, wrap=True)
    # Written, but not everything in the source survived the conversion.
    for line in getattr(res, "render_notes", None) or ():
        out.warn("%s: %s" % (res.name, line), stream=stream, wrap=True)
    # A link in the skill the copy left out: the rest installed, and this
    # names the file the skill may still expect.
    for line in getattr(res, "skipped_links", None) or ():
        out.warn("%s: not copied — the link %s" % (res.name, out.plain(line)),
                 stream=stream, wrap=True)
    _warn_submodules(res, stream=stream)
    conflicts, refused = _skipped_agent_lines(res)
    for line in conflicts:
        out.warn(line, stream=stream)
    for line in refused:
        out.warn(line, stream=stream, wrap=True)
    # Not a skip to repair: the plugin already puts the skill in front of
    # Claude Code, and a link would list it twice. Said, so the missing link
    # is not a mystery.
    for plugin_id in dict.fromkeys(getattr(res, "covered", None) or ()):
        out.info("not linked into Claude Code: plugin %s already loads the "
                 "same files" % plugin_id, stream=stream, wrap=True)


def _skipped_agent_lines(res) -> tuple[list[str], list[str]]:
    """What :func:`_warn_unwritable` prints, as text: the conflict lines and
    the refused-dir lines, apart because only the second kind is wrapped.

    Text so a caller that cannot print — the browse TUI's install worker,
    whose report is a status message in the detail pane — says the same
    thing in the same words. ``getattr`` because that worker also takes a
    caller's own ``install`` callable, whose result need not carry every
    field of an ``InstallResult``.
    """
    what = ("not linked", "adds the link") \
        if getattr(res, "kind", "skill") == "skill" else ("not written", "writes it")
    conflicts = ["not linked: %s exists and is not managed by boost" % _tilde(path)
                 for path in getattr(res, "conflicts", None) or ()
                 if what[0] == "not linked"]
    refused = ["%s: %s — %s, then `boost sync` %s"
               % (what[0], *store.unwritable_refusal(adir), what[1])
               for adir in getattr(res, "unwritable", None) or ()]
    # Something in the way of the dir: no chmod clears a file or a dangling
    # link, so the remedy is the move `store.link_refusal` names.
    refused += ["%s: %s — %s, then `boost sync` %s"
                % (what[0], *store.link_refusal(adir, block), what[1])
                for adir, block in getattr(res, "blocked", None) or ()]
    refused += ["%s: %s — %s, then `boost sync` %s"
                % (what[0], *store.symlink_refusal(adir), what[1])
                for adir in getattr(res, "unlinkable", None) or ()]
    # A rule's or workflow's conflict is a directory where its file goes
    # (`store.occupied`): "not linked" named an action that kind never takes,
    # and its remedy is a move, worded the way sync, heal and doctor word it.
    if what[0] != "not linked":
        refused += ["not written: %s, then `boost sync` writes it"
                    % store.occupied_refusal(path)
                    for path in getattr(res, "conflicts", None) or ()]
    # A file of the user's own at a workflow's path: never replaced, and
    # recorded apart (`store.foreign_rows`), so uninstall never touches it and
    # `boost sync` writes the command once the path is free. `install` again
    # would only say "already installed".
    refused += ["not written: %s exists and is not managed by boost — left "
                "alone; move it aside, then `boost sync` writes it"
                % _tilde(path)
                for path in getattr(res, "foreign", None) or ()]
    # Rendered and withheld: that agent rejects the file at load, so writing
    # it would report a workflow the agent never runs. The source is the fix.
    refused += ["not written for %s: %s %s — fix it in the tap, then "
                "`boost reinstall %s`" % (agent, res.name, why, res.name)
                for agent, why in getattr(res, "declined", None) or ()]
    return conflicts, refused


def _boostfile_text(skills: dict[str, dict], via: str = "boost bundle dump",
                    project: dict[str, dict] | None = None) -> str:
    """Render lock entries as a Boostfile (taps first, then sorted skills).

    ``project`` holds the current repo's project-scope skills. Each is written
    with a trailing ``--local`` — `boost install`'s own spelling — so `bundle
    install` puts it back at project scope rather than in the user store; a
    parser that predates the token ignores it, as it ignores any extra field.

    Each skill line also carries the state `bundle install` must put back for
    it to be the same install — agent scope, version and commit pins, tags —
    in the options ``core.boostfile`` parses (see ``boostfile.GRAMMAR``).
    """
    project = project or {}
    lines = ["# Boostfile — generated by %s" % via]
    taps = sorted({e.get("tap") or "" for section in (skills, project)
                   for e in section.values()} - {"", "local"})
    for tname in taps:
        try:
            tap = registry.get(tname)
            url, pin = tap.url, tap.pin
        except BoostError:
            url = pin = ""
        # The tap's `--at` pin goes with it: without it a fresh machine taps
        # HEAD, and every `@version` below names a tree it no longer has.
        lines.append(boostfile.render_tap(tname, url, pin))
    for name in sorted(skills):
        e = skills[name]
        if (e.get("tap") or "local") == "local":
            lines.append("# local skill (no tap source): %s" % name)
        else:
            lines.append(boostfile.render_skill(e, name))
    for name in sorted(project):
        e = project[name]
        if (e.get("tap") or "local") == "local":
            lines.append("# local skill (no tap source, project scope): %s"
                         % name)
        else:
            lines.append(boostfile.render_skill(e, name, local=True))
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


def _report_prerequisites(entries: list[dict], *, pbase=None,
                          would: bool = False) -> None:
    """Name the catalogued items an install's own frontmatter says it needs
    (``core.installplan.prerequisite_lines``, shared with MCP install)."""
    warnings, hint = installplan.prerequisite_lines(entries, pbase=pbase,
                                                    would=would)
    for line in warnings:
        out.warn(line, wrap=True)
    if hint:
        out.info(hint, wrap=True)


def _install_closure(entries: list[dict], *, scope: str = scopes.SCOPE_USER,
                     pbase=None, only_agents: list[str] | None = None,
                     via: str | None = None, also_installed=(),
                     dry_run: bool = False) -> tuple[list[dict], int]:
    """Install the ``requires:`` closure of ``entries`` the caller installs
    itself: ``(dependency entries installed or previewed, failures)``.

    ``boost install`` plans the closure up front; ``boost update`` and
    ``boost bundle install`` install their own items and used to stop there,
    so an upgrade that added a ``requires:`` — or a Boostfile line naming a
    skill with one — left the skill without what it needs, silently. The
    lines are install's own (``installplan.added_line`` /
    ``dependency_warnings``), so the three commands describe a closure in the
    same words.
    """
    pulled, res = installplan.missing_dependencies(
        entries, pbase if scope == scopes.SCOPE_PROJECT else None,
        also_installed=also_installed)
    added = installplan.added_line(res)
    if added:
        out.info(added)
    for line in installplan.dependency_warnings(res):
        out.warn(line, wrap=True)
    where = " at project scope" if scope == scopes.SCOPE_PROJECT else ""
    done: list[dict] = []
    failed = 0
    for dep in pulled:
        label = "%s v%s (%s)%s" % (dep["name"], out.plain(dep.get("version")),
                                   dep["tap"], where)
        if dry_run:
            # The run's policy gate, asked here too: a preview that promised
            # a dependency the run then refuses exited 0 where the run fails.
            why = store.install_policy_refusal(dep, scope=scope, base=pbase)
            if why:
                out.warn("required skill %s would not be installed: %s"
                         % (dep["name"], why), wrap=True)
                failed += 1
                continue
            out.info("would install %s" % label)
            done.append(dep)
            continue
        try:
            res_i = store.install(dep, only_agents=only_agents, scope=scope,
                                  base=pbase, via=via)
        except BoostError as err:
            out.warn("required skill %s was not installed: %s"
                     % (dep["name"], err.message), wrap=True)
            failed += 1
            continue
        out.ok("installed %s" % label)
        _warn_unwritable(res_i)
        _warn_injection(res_i)
        _warn_secrets(res_i)
        done.append(dep)
    return done, failed


# ── install ──────────────────────────────────────────────────────────────

def _preview_skill_copy(e: dict, seen: dict | None, as_skill: bool | None,
                        scope: str) -> None:
    """The dry run's line for a workflow's skill copy, asked the way the run
    decides it, so the two agree."""
    from ..core import workflows
    if scope == scopes.SCOPE_PROJECT or not store.wants_skill_copy(as_skill,
                                                                   seen):
        return
    try:
        raw = (registry.get(e["tap"]).path / e.get("skill_md", "")).read_text(
            encoding="utf-8", errors="replace")
    except (OSError, BoostError):
        return
    slot = workflows.detect_slot(e.get("skill_md", ""))
    desc = workflows.skill_description(slot, frontmatter.parse(raw)[0])
    if desc is None:
        return
    blocker = store.skill_copy_blocker(
        e["name"], seen, workflows.render_skill(e["name"], desc, raw))
    if blocker:
        out.info("  %s" % blocker, wrap=True)
        return
    out.info("  as a skill → %s" % _tilde(store.skill_store_dir(e["name"])))


def _refuse_preview_by_policy(e: dict, scope: str, pbase, seen) -> None:
    """Raise the policy refusal the run would, so a dry run does not promise
    an install the run then refuses."""
    why = store.install_policy_refusal(e, scope=scope, base=pbase,
                                       existing=seen)
    if why:
        raise BoostError(why, hint="inspect with `boost policy list`")


def cmd_install(argv: list[str]) -> int:
    ap = cliparse.parser(prog="boost install",
                                 description="Install a skill from a tap registry")
    ap.add_argument("names", type=util.nonempty_str, nargs="+", metavar="NAME",
                    help="skill name, optionally qualified as tap:skill")
    ap.add_argument("--force", action="store_true",
                    help="reinstall even if already installed or pinned")
    ap.add_argument("--path", type=util.nonempty_str, metavar="P", default=None,
                    help="pick which copy to install when one registry ships "
                         "the name more than once (see the paths that error "
                         "lists); may be a trailing path segment")
    ap.add_argument("--agent", type=util.nonempty_str, action="append", metavar="A",
                    help="link only into this agent (repeatable)")
    cliparse.add_scope_flags(
        ap, scope_help="install into your user config (default) or the "
                       "current repo (project)",
        local_help="into this repo, committable (= --scope project)",
        global_help="into your user config (= --scope user, default)")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would happen without changing anything")
    ap.add_argument("--no-deps", action="store_true",
                    help="install only the named skills, not their `requires:` "
                         "(the wider spellings are reported, never installed)")
    ap.add_argument("--no-mcp", action="store_true",
                    help="don't offer to register MCP servers a skill declares")
    skill_g = ap.add_mutually_exclusive_group()
    skill_g.add_argument("--as-skill", dest="as_skill", action="store_const",
                         const=True, default=None,
                         help="also put a workflow in the skill store, for "
                              "agents that read only skills (default: the "
                              "workflows_as_skills config); remembered")
    skill_g.add_argument("--no-as-skill", dest="as_skill",
                         action="store_const", const=False,
                         help="don't put a workflow in the skill store; "
                              "remembered")
    args = ap.parse_args(argv)
    args.scope = args.scope or scopes.SCOPE_USER
    # Resolved before the dry-run branch, because both sides need it and only
    # one of them used to bind it: the preview returns early, so a `pbase`
    # assigned inside `if args.dry_run:` is unbound by the time the run path
    # reports prerequisites. `None` for every scope but `--local`.
    pbase, pbase_kind = (scopes.project_base()
                         if args.scope == scopes.SCOPE_PROJECT
                         else (None, None))
    if pbase is not None:
        # Before the "starts a new one here" warning below, which would
        # otherwise be the first thing said about an install that is refused.
        scopes.refuse_managed(pbase)
    # Said once, before anything is written, and naming the directory. An
    # unmarked tree has no project root to walk up to, so this call is what
    # decides where the project *is* — and `proj/src` stays a different project
    # from `proj` for every command afterwards. The warning is the difference
    # between that being a decision and being a surprise. It warns and does
    # not redirect, so it fires in both shapes: with an older project above it
    # names that one, and with nothing above it says a new one starts here.
    # The single silent case is a lock at this very directory, where `above`
    # comes back equal to `pbase` — the project being used is the one already
    # here, and there is nothing to tell anybody.
    if pbase is not None and pbase_kind == scopes.BASE_UNMARKED:
        # `project_lock_root` is advisory and decides nothing: it only lets
        # the warning NAME the project the user probably meant. Resolution
        # stays on version control markers alone, because moving the base up
        # to an ancestor lock orphans the rules and workflows recorded below
        # it — see that function for what verification reproduced.
        above = scopes.project_lock_root(pbase)
        if above is not None and above != pbase.resolve():
            out.warn("there is already a boost project at `%s`, and --local "
                     "here starts a second one — cd there if you meant that "
                     "one" % above, wrap=True)
        elif above is None:
            # "between here and your home directory", not "at or above here":
            # the walk stops at `$HOME` without testing it, so a dotfiles repo
            # at `~/.git` — a setup `project_root`'s own docstring calls out —
            # is a marker above this directory that it may not use. Claiming
            # otherwise sent the reader to `~`, where the same command refuses.
            out.warn("nothing between `%s` and your home directory marks a "
                     "project — no git/hg/svn checkout, no "
                     ".boost/skill-lock.json — so --local starts a new one "
                     "here" % pbase, wrap=True)
    only = _check_agents(args.agent)
    multi = len(args.names) > 1
    entries, failed = [], 0
    for n in args.names:
        try:
            entry = catalog.resolve_one(n, path=args.path)
            # The slug every other command will know it by, said out loud:
            # `install c++-helper` copied to `c--helper` without a word. Only
            # a catalog alias is renamed, and only an unsafe name has one.
            bare = catalog.split_name(n)[1]
            if not util.is_safe_component(bare):
                catalog.note_catalogued_as(entry["name"], bare)
            entries.append(entry)
        except BoostError as err:
            if not multi:
                raise
            out.warn("%s: %s" % (n, err.message), stream=sys.stderr)
            failed += 1

    # Grow the request into its `requires:` closure (deps installed first),
    # unless the caller opted out. Only skills carry dependency frontmatter;
    # rules/workflows pass through unchanged. `installplan.plan` is the one
    # plan — `boost browse` and MCP `boost_install` take theirs from it too.
    the_plan = installplan.plan(entries, pbase=pbase, deps=not args.no_deps)
    _print_plan(the_plan)
    entries = the_plan.entries
    # Pulling in dependencies can turn a single-name request into a multi-item
    # install (per-item headings); it must never *lower* multi (e.g. when an
    # unknown co-requested name was dropped), so OR rather than reassign.
    multi = multi or len(entries) > 1

    if args.dry_run:
        from ..core import mcpdecl, mcphost
        # Deliberately NOT filtered by `only`, matching `store.link_agents`'s
        # own reasoning: that list scopes which agents get a *link*, and a
        # native-store agent's access follows from the store, which every
        # install writes however narrow the scope. Filtering made the preview
        # of `install x --agent cursor` drop the "available to … (reads the
        # store directly)" line the run then prints.
        native_targets = list(agents.native_store_agents())
        if args.scope == scopes.SCOPE_PROJECT and pbase is None:
            raise BoostError(
                "there is no project here to install into",
                hint="cd into a repo, or drop --local to install for your user")
        # materializing_agents(base), not enabled_agents(): a rule/workflow
        # only reaches an agent whose file format is known (agents.py), and at
        # project scope the *repo-local* dotdirs (agents_for_scope's project
        # branch), not the user config every other scope writes into.
        mbase = pbase if args.scope == scopes.SCOPE_PROJECT else None
        # Per kind, not one list: a rule and a workflow no longer reach the same
        # agents. Codex's instructions file is known and its slash-command
        # format does not exist, so `_install_workflow` skips it — and a preview
        # that promised it would be wrong about the one thing it exists to
        # predict. See agents.workflow_agents.
        mat_sets = {"rule": agents.materializing_agents(mbase),
                    "workflow": agents.workflow_agents(mbase)}
        offer_mcp = not args.no_mcp and not typedvalue.env_flag("BOOST_NO_MCP_OFFER", unknown=True)
        mcp_hosts = [h for h in mcphost.hosts() if shutil.which(mcphost.cli(h))] \
            or mcphost.hosts()
        for e in entries:
            # The live loop below catches a per-entry refusal, warns and
            # carries on when the request names more than one item. The
            # preview did not, and this is the commit that first gives it
            # something to raise: `install a b --agent codex --dry-run`, with
            # `b` a workflow codex cannot take, printed `a`'s plan and then
            # exited 1 out of the whole command — no plan for anything after
            # `b`, and not even the "dry run — nothing was changed" line —
            # while the run installs `a`, warns about `b` and exits 1. A
            # single name reaches this too, since `expand_dependencies` can
            # raise `multi` on a `requires:` closure.
            try:
                if args.scope == scopes.SCOPE_PROJECT and e.get("kind", "skill") == "skill":
                    # The run's own refusal, ahead of the header: a preview
                    # must not promise a reinstall the run declines.
                    seen = store.check_existing(e, force=args.force,
                                                scope=args.scope)
                    _refuse_preview_by_policy(e, args.scope, pbase, seen)
                    # agents_for_scope(pbase), not enabled_agents(): project scope
                    # copies into each agent's *repo-local* dotdir, which excludes
                    # Antigravity CLI (its layout is two levels under ~/.gemini and
                    # has no known project-local path — see agents.project_agents).
                    # Narrowed through the same core helper the install calls, for
                    # the same reason the rule/workflow branch below does — and
                    # before the header, because the run refuses before it says a
                    # word and a preview that announces an install it is about to
                    # refuse is worse than one that just refuses.
                    chosen = store.narrow_project_agents(
                        agents.agents_for_scope(pbase),
                        store.preserved_agent_scope(only, seen), e["name"],
                        explicit=only is not None)
                    out.info("would %s %s v%s from %s into %s"
                             % ("reinstall" if seen else "install", e["name"],
                                out.plain(e["version"]), e["tap"],
                                _tilde(pbase)))
                    for agent_name, sdir in chosen.items():
                        out.info("  copy  → %s"
                                 % _tilde(scopes.skill_target(
                                     sdir, e["name"], base=pbase,
                                     dotdir=agents.project_dotdir(agent_name, sdir))))
                    if offer_mcp:
                        for row in mcpdecl.registrable(
                                store.declared_mcp_servers(store.source_dir_for(e))):
                            out.info("  mcp   → record %s in %s"
                                     % (row["name"], mcpdecl.SIDECAR))
                    continue
                if e.get("kind") in ("rule", "workflow"):
                    k = e["kind"]
                    # The run's refusals first ("already installed" without
                    # --force, a cross-scope clash even with it), so a record
                    # that is seen here is one --force replaces: a reinstall.
                    seen = store.check_existing(e, force=args.force,
                                                scope=args.scope)
                    _refuse_preview_by_policy(e, args.scope, pbase, seen)
                    verb = "reinstall" if seen else "install"
                    where = "into this repo" if args.scope == "project" else "user config"
                    # The real run's two steps, in its order: replay the lock's
                    # recorded scope, then narrow — so the preview refuses in the
                    # same words at the same point, ahead of the header. Filtering
                    # a list by `only` was a lookalike that got both halves wrong:
                    # `install <workflow> --agent codex --dry-run` printed "(no
                    # enabled agents)" about an agent that is enabled and exited 0,
                    # where the run raises; and a reinstall previewed every agent
                    # while the run narrows to the ones the lock recorded.
                    mat = store.narrow_materializing(
                        mat_sets[k], store.preserved_agent_scope(only, seen),
                        e["name"], k, explicit=only is not None)
                    out.info("would %s %s %s v%s from %s (%s)"
                             % (verb, k, e["name"], out.plain(e["version"]),
                                e["tap"], where))
                    out.info("  materialize → %s" % " · ".join(mat))
                    if k == "workflow":
                        _preview_skill_copy(e, seen, args.as_skill,
                                            args.scope)
                    continue
                # Same refusal as the run ("already installed", "is pinned");
                # past it, a seen record is one --force overwrites.
                seen = store.check_existing(e, force=args.force,
                                            scope=args.scope)
                # The run's refusal, ahead of the header, as the branches above.
                store.refuse_unreachable_skill(only, e["name"])
                _refuse_preview_by_policy(e, args.scope, pbase, seen)
                verb = "reinstall" if seen else "install"
                # The lock's recorded scope, replayed exactly as `store.install`
                # replays it before calling `link_agents` — the same two steps
                # the rule/workflow branch above takes, and left out here for
                # the commonest install shape of all: after `install x --agent
                # cursor`, `install x --force --dry-run` previewed a link into
                # every linking agent while the run relinked cursor alone.
                # `link_agents` filters rather than refusing on an empty set,
                # so this narrows in place instead of calling a core helper.
                scoped = store.preserved_agent_scope(only, seen)
                link_targets = [a for a in agents.linking_agents()
                                if not scoped or a in scoped]
                out.info("would %s %s v%s from %s"
                         % (verb, e["name"], out.plain(e["version"]), e["tap"]))
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
                if offer_mcp:
                    for row in mcpdecl.registrable(
                            store.declared_mcp_servers(store.source_dir_for(e))):
                        out.info("  mcp   → offer to register %s with %s"
                                 % (row["name"], " · ".join(mcphost.label(h)
                                                            for h in mcp_hosts)))
            except BoostError as err:
                if not multi:
                    raise
                out.warn("%s: %s" % (e["name"], err.message), stream=sys.stderr)
                failed += 1
                continue
        _report_prerequisites(entries, pbase=pbase, would=True)
        out.info("dry run — nothing was changed")
        return 1 if failed else 0

    results = []
    for e in entries:
        if multi:
            out.heading("%s v%s (%s)"
                        % (e["name"], out.plain(e["version"]), e["tap"]))
        try:
            if (args.scope != scopes.SCOPE_PROJECT
                    and e.get("kind", "skill") == "skill"):
                store.refuse_unreachable_skill(only, e["name"])
            res = store.install(e, force=args.force, only_agents=only,
                                scope=args.scope, as_skill=args.as_skill)
        except BoostError as err:
            if not multi:
                raise
            out.warn("%s: %s" % (e["name"], err.message), stream=sys.stderr)
            failed += 1
            continue
        _report_result(res, no_mcp=args.no_mcp)
        results.append(res)
    if results:
        _report_prerequisites([e for e in entries
                               if e["name"] in {r.name for r in results}],
                              pbase=pbase)
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
        nxt = None
        if len(results) == 1:
            r0 = results[0]
            if r0.linked:
                lines.append(out.role("%s → %s" % (r0.name, " · ".join(r0.linked)), "muted"))
            nxt = "next: boost info %s" % r0.name
        print(out.panel(lines, title="installed", hue="green"))
        # Below the box, not in it: panel() clips each line to the pane, and a
        # clipped command (`boost info typescript-react-…`) is one that does
        # not run. A command is data, so it is printed whole and unwrapped —
        # overflowing a narrow pane rather than breaking.
        if nxt:
            out.dim("  " + nxt)
    return 1 if failed else 0


# ── uninstall ────────────────────────────────────────────────────────────

def _project_fallback(names: list[str]) -> tuple[list[str], Path | None]:
    """Which of ``names`` a bare ``uninstall`` would remove from the repo, and where.

    Bare uninstall prefers user scope and only falls back to the repo for a name
    the project lock records. That fallback resolves its base the way
    ``install --local`` writes one, so an unmarked directory counts too — and in
    an extracted copy of a repo that carries a committed ``.boost/`` but no
    ``.git``, someone typing ``boost uninstall x`` meaning their user config
    would be deleting files in the cwd. The prompt says so rather than letting
    the success line be the first mention of where.

    It returns the *subset*, not a yes/no, because a batch can be both: "all of
    them" and "these two of the five" are different sentences, and answering
    the second with the first would either claim the whole batch comes out of
    the repo or — the other way round — drop the warning entirely for the
    mixed case, which is the one the reader is least likely to have in mind.
    """
    base = scopes.resolve_base(scopes.SCOPE_PROJECT)
    if base is None:
        return [], None
    here = [n for n in names
            if lockfile.find_any(n) is None and projectlock.get_skill(base, n)]
    return here, (base if here else None)


def _rm_target(base, row: str) -> str:
    """``base/row`` as one shell word for an `rm -rf` hint.

    The real path, not the `~`-tilded one the prose uses: once quoted, a `~`
    no longer expands, and a repo path with a space split in two unquoted.
    """
    return util.shell_arg("%s/%s" % (base, row) if base else row)


def cmd_uninstall(argv: list[str]) -> int:
    ap = cliparse.parser(
        prog="boost uninstall",
        description="Remove an installed skill, rule, or workflow")
    ap.add_argument("names", type=util.nonempty_str, nargs="+", metavar="NAME",
                    help="installed skill, rule or workflow (several allowed)")
    cliparse.add_scope_flags(
        ap, scope_help="remove from your user config or this repo (default: "
                       "user config, then this repo for a name only it has)",
        local_help="remove from this repo (= --scope project)",
        global_help="remove from your user config only (= --scope user)")
    ap.add_argument("--kind", choices=("skill", "rule", "workflow"),
                    default=None,
                    help="which item to remove when a skill, rule or "
                         "workflow share NAME")
    ap.add_argument("-y", "--yes", action="store_true",
                    help="skip the confirmation prompt")
    args = ap.parse_args(argv)
    args.names = [store.installed_name(n, args.scope) for n in args.names]
    if (args.kind not in (None, "skill")
            and args.scope == scopes.SCOPE_PROJECT):
        raise BoostError("--local removes project skills, not a %s"
                         % args.kind,
                         hint="drop --local: a %s installed into a repo is "
                              "recorded in your user lock" % args.kind)
    # Ask only when someone is there to answer. out.confirm() returns its
    # `default` on a non-TTY, so gating on it unconditionally would turn every
    # scripted `boost uninstall x` — CI step, Makefile, Dockerfile — into a
    # silent no-op exiting 1. A pipeline that cannot see the prompt keeps the
    # behaviour it has today; the prompt is a speed bump for humans only.
    if out.stdin_is_tty() and not args.yes:
        what = (args.names[0] if len(args.names) == 1 else
                "%d skills: %s" % (len(args.names), ", ".join(args.names)))
        if args.kind and len(args.names) == 1:
            what = "%s %s" % (args.kind, what)
        if args.scope == scopes.SCOPE_PROJECT:
            from_repo, where = list(args.names), scopes.resolve_base(
                scopes.SCOPE_PROJECT)
        elif args.scope == scopes.SCOPE_USER:
            from_repo, where = [], None
        else:
            from_repo, where = _project_fallback(args.names)
        if where is None:
            prompt = "uninstall %s?" % what
        elif len(from_repo) == len(args.names):
            prompt = "uninstall %s from %s?" % (what, _tilde(where))
        else:
            # Part of the batch comes out of the repo and part out of the user
            # store. Saying "from <repo>" would describe the wrong half, and
            # saying nothing would drop the warning for the case the reader is
            # least likely to expect — so name which ones.
            prompt = "uninstall %s? (%s from %s)" % (
                what, ", ".join(from_repo), _tilde(where))
        # A skill `boost sync` recorded where it found it has no copy outside
        # the store, so this removal is the one that cannot be undone.
        only = [n for n in args.names if n not in from_repo
                and (e := lockfile.get_skill(n)) is not None
                and store.only_copy(n, e)]
        if only:
            prompt += (" The store holds the only copy of %s, so %s deleted "
                       "for good." % (", ".join(only),
                                      "it is" if len(only) == 1 else "they are"))
        if not out.confirm(prompt):
            out.info("cancelled")
            return 1
    removed, failed = 0, 0
    done_kinds: set[str] = set()
    for name in args.names:
        try:
            if args.scope == scopes.SCOPE_PROJECT:
                info = store.uninstall_project(name)
            else:
                # An explicit --global means the user config and nothing
                # else: falling back to the repo would remove what the
                # flag said to leave alone.
                info = store.uninstall(
                    name, project_fallback=args.scope != scopes.SCOPE_USER,
                    kind=args.kind)
        except BoostError as err:
            if len(args.names) == 1:
                raise
            out.warn("%s: %s" % (name, err.message), stream=sys.stderr)
            failed += 1
            continue
        kind = info.get("kind", "skill")
        is_project = info.get("scope") == scopes.SCOPE_PROJECT
        if info["unlinked"]:
            # Only a user-scope *skill* unlinks agent symlinks — a rule is
            # stripped out of each agent's context file and a workflow's
            # rendered command is deleted, so "removed from" is what actually
            # happened for either kind (and for a project-scope skill, whose
            # per-agent copies are files, not links).
            verb = "unlinked ←" if kind == "skill" and not is_project \
                else "removed from"
            out.ok("%s %s" % (verb, " · ".join(info["unlinked"])))
        for path in info.get("kept") or ():
            out.warn("left %s in place: it was edited since boost wrote it"
                     % _tilde(path), wrap=True)
        if is_project:
            refused = info.get("refused") or []
            escaped = info.get("escaped") or []
            redirected = info.get("redirected") or []
            at = _tilde(info.get("base", "this repo"))
            # Only claim a removal that happened, and read it off what came
            # off disk rather than off `unlinked`, which is the *agent* list:
            # a lock row need not name an agent, and gating on the agent list
            # told a user whose row was agentless that nothing had been
            # removed while the directory was gone. An unconditional "removed
            # from <repo>" over an empty removal is the green panel this
            # change exists to stop the user trusting, and this is the same
            # sentence in the other direction. The lock *entry* does go
            # either way, so the summary panel still counts the skill.
            if info.get("removed_count"):
                # Where it actually went, not where a user-scope install
                # would have put it — a project skill never touches the
                # canonical store.
                out.ok("removed from %s" % at)
            elif refused or escaped or redirected:
                out.warn("nothing removed from %s — every path the lock named "
                         "was left alone" % at, wrap=True)
            # A lock row boost will not act on, named rather than swallowed:
            # the row is in a committed file, so a user who sees nothing has
            # no way to learn their lock was edited. Through `out.plain`
            # because the row *is* the attacker-controlled input — a path
            # carrying `\x1b[1A\x1b[2K` would erase the lines above it.
            for row in refused:
                out.warn("left alone: the lock names %s, which is not a path "
                         "boost removes here" % out.plain(row), wrap=True)
            # Worded apart from the above on purpose: this row may well be a
            # path an install writes, with the lie in the filesystem rather
            # than in the string.
            for row in escaped:
                out.warn("left alone: the lock names %s, which resolves "
                         "outside this repo" % out.plain(row), wrap=True)
            # And this one *is* a path an install writes — it is in the
            # derived set by construction, which is why it must not borrow
            # `refused`'s wording: that printed "not a path boost removes
            # here" directly above a list containing the same string. The
            # remedy is a real one, because `rm` follows the committed
            # symlink exactly as the install did.
            for row in redirected:
                out.warn("left alone: the lock names %s, but a symlink inside "
                         "the repo redirects the path to it. boost will not "
                         "delete through a symlink it did not create; "
                         "`rm -rf %s` removes it if it is yours."
                         % (out.plain(row), _rm_target(info.get("base"),
                                                        out.plain(row))),
                         wrap=True)
            if refused:
                # The derived set, not a `<repo>/<dotdir>/skills/<name>`
                # shape: the leaf comes from the agent's `dir`, so the shape
                # told a user with a renamed skills dir that their path was
                # not one an install writes — directly above a shape it
                # matched. And worded as what boost *removes* rather than
                # what an install *writes*, because the set keeps disabled
                # agents on purpose and an install skips them.
                #
                # Gated on `refused` alone. A redirected row is in `expected`
                # by construction, so printing this under one contradicts the
                # line above it; its own message carries its own remedy.
                expected = info.get("expected") or []
                out.info(("boost only removes %s here. The lock entry is gone "
                          "from your working copy; the directory is not, so "
                          "remove it by hand if it is not yours."
                          % ", ".join(expected)) if expected else
                         ("boost cannot derive where this skill installs, so "
                          "every row was left alone; remove the directories "
                          "by hand if they are yours"), wrap=True)
            unregistered = info.get("mcp_unregistered") or []
            if unregistered:
                from ..core import mcpdecl
                out.ok("removed %s from %s"
                       % (_plural(len(unregistered), "MCP server"), mcpdecl.SIDECAR))
            if info.get("mcp_error"):
                from ..core import mcpdecl
                out.warn("%s left unchanged — remove %s's servers by hand"
                         % (mcpdecl.SIDECAR, name), wrap=True)
                out.dim("  %s" % info["mcp_error"])
        elif kind == "skill":
            out.ok("removed %s" % _tilde(store.skill_store_dir(name)))
        # A rule/workflow never had a store dir to begin with — the
        # materialization removal reported above via "unlinked" is the whole
        # story, so there is nothing further to narrate here.
        removed += 1
        done_kinds.add(kind)
    if removed:
        # Name the kind when only one was touched; a mixed run says "items".
        noun = next(iter(done_kinds)) if len(done_kinds) == 1 else "item"
        lines = ["Uninstalled %s" % _plural(removed, noun)]
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
    ("adoptable_store", "skills added outside boost, to record"),
    ("older_copies", "older copies of those, left alone"),
    ("foreign_store", "store dirs copying another tool's skills (--prune removes)"),
    ("not_skill_store", "store dirs that are not skills, left alone"),
    ("unreadable_store", "store dirs boost cannot read, left alone"),
    ("misnamed_store", "store dirs boost cannot record a skill by, left alone"),
    ("workflow_copies", "workflow skill copies the lock has lost, left alone "
                        "(`boost install <workflow>` re-records)"),
    ("rule_blocks", "rule blocks the lock has lost, left alone "
                    "(`boost install <rule>` re-records)"),
    ("plugin_duplicates", "skills Claude Code also loads from a plugin"),
    ("unrecorded_store", "store dirs the lock file has lost"),
    ("missing_materializations", "missing rule/workflow files"),
    ("out_of_scope_links", "linked outside declared scope"),
]

#: Plan keys whose items are ``(skill, agent)`` pairs rather than paths.
_PAIR_KEYS = ("missing_links", "out_of_scope_links")

#: ``unrecorded_store``'s label over a lock that is corrupt or in another
#: schema: sync re-records what a missing lock lost, and nothing over these.
_UNREADABLE_LOCK_LABEL = "store dirs the lock file cannot record, left alone"


def cmd_sync(argv: list[str]) -> int:
    ap = cliparse.parser(
        prog="boost sync",
        description="Reconcile installed skills & symlinks against the lock file")
    ap.add_argument("--diff", action="store_true",
                    help="show the plan without applying it")
    ap.add_argument("--prune", action="store_true",
                    help="also delete store dirs that copy another tool's "
                         "skills, drop boost's Claude Code link to a skill an "
                         "enabled plugin ships identically, and remove links "
                         "outside a declared --agent scope")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("-y", "--yes", action="store_true",
                    help="skip the --prune confirmation prompts")
    ap.add_argument("--rebuild-lock", action="store_true",
                    help="set an unreadable lock file aside (its bytes are "
                         "kept) and re-record the store into a new one")
    args = ap.parse_args(argv)
    if args.rebuild_lock:
        if args.diff:
            ap.error("--rebuild-lock replaces the lock file; drop --diff")
        # The way back from a corrupt lock with no history to roll back to:
        # a missing lock over a populated store is what sync re-records.
        backup = lockfile.set_aside()
        out.info("set the unreadable lock file aside — its bytes are in %s; "
                 "re-recording the store" % _tilde(backup),
                 stream=sys.stderr if args.json else None, wrap=True)
    plan = store.sync_plan()
    # A checkout can be missing skills its project lock records — that is the
    # normal state right after `git clone` — so sync repairs the repo too.
    pplan = store.project_sync_plan()
    # Asked before the repair, which writes a lock where there was none. A
    # lock that is corrupt or in another schema is `boost replay`'s to
    # restore, and it is named whatever the store holds: a schema-v2 lock
    # still lists every skill, so no store dir looked unrecorded and sync
    # said "everything in sync" while doctor and heal exited 1. Both
    # `--json` shapes carry it as ``lock``: None, or the problem
    # (``missing``, ``corrupt``, ``schema``) sync found — or ``older``, a
    # lock with no or an earlier schema version, which sync migrates.
    integ = lockfile.check()
    lock_bad = not integ.ok and integ.problem != "missing"

    if args.diff:
        if args.json:
            print(json.dumps(plan | {"project": pplan, "lock": integ.problem},
                             indent=2))
            return 0
        if lock_bad:
            out.warn("the lock file %s, so sync will record nothing — %s"
                     % (lockfile.fault(integ), lockfile.remedy(integ)),
                     wrap=True)
        # What a run writes into the lock with no plan bucket of its own: an
        # older lock's schema stamp and the hashes rows were installed
        # without. Missing here, `--diff` said "everything in sync" over the
        # writes the next `boost sync` made.
        records = ([lockfile.older_line(integ, dry=True)]
                   if integ.problem == "older" else [])
        records += store.hold_legacy_copies(dry=True)
        records += store.backfill_tap_urls(dry=True)
        records += store.backfill_row_hashes(dry=True)
        for line in records:
            (out.warn if store.is_unrepaired(line) else out.info)(
                line, wrap=True)
        if not any(plan.values()) and not any(pplan.values()):
            if not lock_bad and not records:
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
            if key == "unrecorded_store" and lock_bad:
                label = _UNREADABLE_LOCK_LABEL
            out.heading("%s (%d)" % (label, len(plan[key])))
            for item in plan[key]:
                if key in _PAIR_KEYS:
                    out.info("%s → %s" % (item[0], item[1]))
                elif key == "missing_materializations":
                    out.info("%s %s" % (item[0], item[1]))  # (kind, name)
                elif key == "blocked_links":
                    # (skill, agent, path) — the general str()-of-a-tuple
                    # fallback below prints this verbatim as
                    # "('brainstorming', 'windsurf', '/private/tmp/.../
                    # brainstorming')", which is what the live warning at the
                    # bottom of this command deliberately does not do.
                    name, agent, path = item
                    out.info("%s → %s (%s in the way)"
                             % (name, agent, _tilde(Path(path))))
                elif key in ("workflow_copies", "rule_blocks"):
                    name, path = item
                    out.info("%s — %s" % (name, _tilde(Path(path))))
                elif key == "older_copies":
                    name, owner, path = item
                    out.info("%s — %s (%s)" % (name, _tilde(Path(path)), owner))
                elif key == "foreign_store":
                    name, owner, path, how = item
                    out.info("%s — %s, %s (%s)"
                             % (name, owner, _tilde(Path(path)),
                                "a git repository, which --prune leaves"
                                if store.is_repo_copy(item) else how))
                elif key == "unreadable_store":
                    name, path = item
                    out.info("%s — %s cannot be read" % (name, _tilde(Path(path))))
                elif key == "adoptable_store":
                    # The same per-skill line `heal --dry-run` prints: which
                    # agents the record keeps it to, and which it links.
                    out.info(store.adoption_preview(item), wrap=True)
                elif key == "plugin_duplicates":
                    name, plugin_id, _path, how = item
                    out.info("%s — plugin %s (%s)" % (name, plugin_id, how))
                else:
                    out.info(_tilde(item))
        return 0

    actions = store.sync_apply(plan) + store.project_sync_apply(pplan)
    # Links outside a declared `--agent` scope work and are in use, so sync
    # reports them and stops. Removing one changes which agents can run a
    # skill, which is the same class of decision as deleting a store dir that
    # copies another tool's skill — hence the same explicit `--prune`, and its
    # own confirm so the two are never approved as one.
    oos = plan["out_of_scope_links"]
    if args.prune and oos:
        go = (args.yes or typedvalue.env_flag("BOOST_ASSUME_YES") if args.json else
              args.yes or out.confirm("Remove %s outside their declared scope: %s?"
                          % (_plural(len(oos), "link"),
                             ", ".join("%s → %s" % (n, a) for n, a in oos))))
        if go:
            actions += store.prune_out_of_scope_links(plan)
            oos = []
    # Two more opt-in removals, each with its own confirm stating its cost so
    # neither is approved as part of the other. A copy of another tool's skill
    # is deleted; a skill a plugin already ships loses only Claude Code's link.
    copies = plan["foreign_store"]
    # A store dir holding a git repository is never offered: its history is
    # in no copy, so it is named and kept rather than put to a confirm.
    offer = [r for r in copies if not store.is_repo_copy(r)]
    pruned: list[str] = []
    kept: list[str] = []
    declined_copies = False
    if args.prune:
        kept += ["kept %s: %s" % (_tilde(store.skill_store_dir(r[0])),
                                  store.REPO_KEPT)
                 for r in copies if r not in offer]
    if args.prune and offer:
        if _go(args, _foreign_prompt(offer)):
            for row, why in zip(offer, store.remove_foreign_copies(offer),
                                strict=True):
                if why is None:
                    pruned.append(row[0])
                else:
                    kept.append("kept %s: %s"
                                % (_tilde(store.skill_store_dir(row[0])), why))
        else:
            declined_copies = True
    left = [r for r in copies if r[0] not in pruned]
    same = [r for r in plan["plugin_duplicates"] if store.plugin_serves(r[3])]
    dropped: list[str] = []
    declined_dups = False
    if args.prune and same:
        newer = any(r[3] != foreign.IDENTICAL for r in same)
        if _go(args, "Drop boost's Claude Code link for %s an enabled plugin "
                     "ships %s (Claude Code goes on loading the plugin's "
                     "copy): %s?"
                     % (_plural(len(same), "skill"),
                        "with the same files or in a newer copy" if newer
                        else "with the same files",
                        ", ".join(r[0] for r in same))):
            for row in same:
                ok, line = store.drop_plugin_link(row)
                (actions if ok else kept).append(line)
                if ok:
                    dropped.append(row[0])
        else:
            declined_dups = True
    dups = [r for r in plan["plugin_duplicates"] if r[0] not in dropped]
    # Re-recorded by sync_apply when the lock was merely missing, and a dir it
    # could not record has its own line saying why. Over a lock that is
    # corrupt or in another schema nothing is written, so all of them are
    # left as they were, and the remedy is the lock's.
    unrecorded = plan["unrecorded_store"] if lock_bad else []
    blocked = plan["blocked_links"]
    # A dir that refused a link or a file: sync wrote what it could and says
    # what it could not, rather than "everything in sync" over it.
    stuck = store.unwritable_agent_dirs()
    # A file or a dangling link where a rules/ or commands/ dir belongs. A
    # block the line above already names for a skill link is not named twice.
    named = {Path(p) for _n, _a, p in blocked}
    in_way = [(d, b) for d, b in store.blocked_agent_dirs() if b not in named]
    # A directory where a rule's or workflow's file goes: no dir refuses, so
    # neither line above sees it, and sync said "everything in sync" over it.
    occupied = store.occupied_targets()
    # A repair sync set out to make and could not is a failure, the same as
    # doctor and heal call it: this returned 0 over a blocked link, so a CI
    # step running `boost sync` could not tell the repair had been refused.
    # Advisory states (another tool's copies, out-of-scope links) stay 0.
    # So is a repair sync_apply declined (a policy refusing a restore, a pin
    # over a moved source): its line said so under a "!" while sync exited 0,
    # and heal exits 1 on the same line.
    unrepaired = [a for a in actions if store.is_unrepaired(a)]
    rc = 1 if (blocked or stuck or in_way or occupied or lock_bad
               or unrepaired) else 0
    if args.json:
        # `sync --diff --json` above is indent=2; this printed one unindented
        # line, so the two `--json` shapes of the same command disagreed on
        # style for no reason tied to their content.
        print(json.dumps({"actions": actions, "pruned": pruned, "kept": kept,
                          "foreign_store": left, "plugin_duplicates": dups,
                          "older_copies": plan["older_copies"],
                          "not_skill_store": plan["not_skill_store"],
                          "unreadable_store": plan["unreadable_store"],
                          "misnamed_store": plan["misnamed_store"],
                          "workflow_copies": plan["workflow_copies"],
                          "rule_blocks": plan["rule_blocks"],
                          "unrecorded_store": unrecorded,
                          "out_of_scope_links": oos,
                          "blocked_links": blocked,
                          "unwritable_agent_dirs": [str(d) for d in stuck],
                          "blocked_agent_dirs": [[str(d), str(b)]
                                                 for d, b in in_way],
                          "occupied_targets": [str(t) for t in occupied],
                          "unrepaired": unrepaired,
                          "lock": integ.problem}, indent=2))
        return rc
    for a in actions:
        (out.warn if store.is_unrepaired(a) else out.ok)(a)
    for line in kept:
        out.warn(line, wrap=True)
    if lock_bad:
        out.warn("the lock file %s, so sync records nothing%s — %s"
                 % (lockfile.fault(integ),
                    " and leaves %s as %s: %s"
                    % (_plural(len(unrecorded), "store dir"),
                       "it is" if len(unrecorded) == 1 else "they are",
                       ", ".join(unrecorded)) if unrecorded else "",
                    lockfile.remedy(integ)), wrap=True)
    for name in pruned:
        out.ok("pruned %s" % _tilde(store.skill_store_dir(name)))
    for line in store.older_copy_lines(plan["older_copies"]):
        out.info(line, wrap=True)
    # A decline names what it left rather than the flag the user just ran.
    if declined_copies:
        out.warn("%s copying another tool's skills left in place "
                 "(declined): %s" % (_plural(len(offer), "store dir"),
                                     ", ".join(r[0] for r in offer)), wrap=True)
    elif not args.prune:
        for line in store.foreign_store_lines(left):
            out.warn(line, wrap=True)
    if plan["not_skill_store"]:
        out.info(store.not_skill_line(plan["not_skill_store"]), wrap=True)
    if plan["unreadable_store"]:
        out.warn(store.unreadable_line(plan["unreadable_store"]), wrap=True)
    if plan["misnamed_store"]:
        out.info(out.plain(store.misnamed_line(plan["misnamed_store"])),
                 wrap=True)
    for line in store.workflow_copy_lines(plan["workflow_copies"]):
        out.warn(line, wrap=True)
    for line in store.rule_block_lines(plan["rule_blocks"]):
        out.warn(line, wrap=True)
    if declined_dups:
        out.warn("%s still linked into Claude Code beside a plugin's copy "
                 "(declined): %s" % (_plural(len(same), "skill"),
                                     ", ".join(r[0] for r in same)), wrap=True)
    elif not args.prune:
        for line in store.plugin_duplicate_lines(dups):
            out.warn(line, wrap=True)
    for line in store.plugin_variant_lines(dups):
        out.info(line, wrap=True)
    if oos:
        if args.prune:
            out.warn("%s outside the declared scope (declined): %s"
                     % (_plural(len(oos), "link"),
                        ", ".join("%s → %s" % (n, a) for n, a in oos)))
        else:
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
    for adir in stuck:
        out.warn("agent dir %s — %s, then re-run `boost sync`"
                 % store.unwritable_refusal(str(adir)), wrap=True)
    for adir, block in in_way:
        out.warn("%s — %s, then re-run `boost sync`"
                 % store.link_refusal(str(adir), str(block)), wrap=True)
    for path in occupied:
        out.warn("%s, then re-run `boost sync`" % store.occupied_refusal(path),
                 wrap=True)
    unfixed = left or kept or any(store.plugin_serves(r[3]) for r in dups)
    if (not actions and not pruned and not unfixed and not oos and not blocked
            and not stuck and not in_way and not occupied and not lock_bad
            and not plan["unreadable_store"]):
        out.ok("everything in sync")
    return rc


def _go(args, prompt: str) -> bool:
    """A `--prune` confirm: `--yes` or BOOST_ASSUME_YES skip it, and `--json`
    never prompts, since a question on stdout would break the JSON after it."""
    if args.json:
        return args.yes or typedvalue.env_flag("BOOST_ASSUME_YES")
    return args.yes or out.confirm(prompt)


def _foreign_prompt(rows: list) -> str:
    """The `--prune` confirm for copies of other tools' skills, with its cost.

    Deleting one costs more than it looks: the agents that read the store
    natively lose the skill, and a changed copy — a port, say — loses the
    change. Both are said before the question rather than discovered after.
    """
    differ = sum(1 for r in rows if r[3] == foreign.DIFFERS)
    native = [agents.display_name(a) for a in agents.native_store_agents()]
    costs = []
    if differ:
        costs.append("%s from the original, and those changes go too"
                     % ("it differs" if len(rows) == 1 else "%d differ" % differ))
    if native:
        costs.append("%s read%s %s directly and will stop seeing %s"
                     % (" and ".join(native), "s" if len(native) == 1 else "",
                        _tilde(paths.store_dir()),
                        "it" if len(rows) == 1 else "them"))
    return ("Delete %s that %s another tool's skill%s%s: %s?"
            % (_plural(len(rows), "store dir"),
               "copies" if len(rows) == 1 else "copy",
               "" if len(rows) == 1 else "s",
               " (%s)" % "; ".join(costs) if costs else "",
               ", ".join(r[0] for r in rows)))


# ── update ───────────────────────────────────────────────────────────────

def _show_and_confirm(label: str, diff, name: str) -> bool:
    """Print why an update is risky, show it, and ask. Shared by all kinds."""
    out.warn("%s: upstream update %s" % (label, "; ".join(diff.reasons)))
    print(diff.text)
    return out.confirm("Apply this update to %s?" % name)


def _confirm_risky_update(name: str, entry: dict, base=None,
                          lk: dict | None = None) -> bool:
    """Gate an in-place update behind a visible diff when it is risky.

    Diffs the installed skill against the incoming source. If the change adds
    executable-looking instructions or prose aimed at redirecting the agent, the
    unified diff is printed and the update must be confirmed — so a poisoned
    update is *seen* before it lands. Routine edits apply silently. If the
    source can't be read we fail open and let ``store.install`` surface the real
    error rather than blocking on a phantom diff.

    ``base`` (with its project lock row ``lk``) diffs a project skill's copy in
    the repo instead of the user store, which holds no such skill — or a
    different install that only shares the name.
    """
    try:
        new_tree = updatediff.read_tree(store.source_dir_for(entry))
    except BoostError:
        return True
    current = (store.skill_store_dir(name) if base is None
               else integrity.project_skill_dir(lk or {}, base))
    diff = updatediff.diff_tree(
        updatediff.read_tree(current) if current is not None else {}, new_tree)
    if not diff.risky:
        return True
    return _show_and_confirm(name, diff, name)


def _materialized_sides(kind: str, name: str, lk: dict,
                        new_raw: str) -> list[tuple[str, str, str]]:
    """``(label, installed_text, incoming_text)`` per materialization.

    Rules and workflows keep no copy of the source they were installed from —
    only the artifacts they were materialized into. Those are the honest
    left-hand side anyway: they are the text the agents are loading *right
    now*, and a diff against them is the diff the user actually cares about.

    Each recorded materialization says how it was written, so the incoming half
    is reconstructed the same way: a verbatim rule drop compares raw to raw, a
    CLAUDE.md rule compares managed block to newly rendered block, and a
    workflow compares the rendered file to the same render of the new source —
    which keeps Gemini's TOML comparable with Gemini's TOML.

    *Every* readable one, not the first. Stopping at the first returned the
    CLAUDE.md block, which carries no frontmatter — so a change to the
    frontmatter alone (an injected ``description``, ``alwaysApply: true``)
    was never diffed, and was then copied verbatim into Cursor's and
    Windsurf's rules. Copies with the same before and after (two verbatim
    drops) are listed once, under the first path.

    A materialization that cannot be read back (deleted, unreadable, its
    CLAUDE.md block gone) is diffed from empty, so whatever the update writes
    there is scanned whole; with none recorded at all it falls back to
    ``[(name, "", new_raw)]``.
    """
    from ..core import rules, workflows
    sides: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for m in lk.get("materializations") or []:
        path = m.get("path", "")
        try:
            current = Path(path).read_text(encoding="utf-8",
                                           errors="replace")
        except OSError:
            # Gone or unreadable, it is still rewritten by the update: scan
            # what is about to land there against nothing, never skip it.
            current = ""
        if kind == "rule" and m.get("mode") == rules.MODE_CLAUDE:
            old = rules.read_block(current, name) or ""
            meta, body = frontmatter.parse(new_raw)
            pair = (old, rules.render_claude_body(
                str(meta.get("name") or name), body))
        elif kind == "rule":
            pair = (current, new_raw)
        else:
            pair = (current, workflows.render(
                m.get("agent"), m.get("slot", ""), name, new_raw))
        if pair not in seen:
            seen.add(pair)
            sides.append((_tilde(path), *pair))
    return sides or [(name, "", new_raw)]


def _confirm_risky_materialized(kind: str, name: str, lk: dict,
                                new_raw: str) -> bool:
    """The same gate as `_confirm_risky_update`, for rules and workflows.

    This used to be absent, and the asymmetry ran the wrong way: a skill that
    grew a shell command was gated, while a rule — which is merged into the
    standing instructions the agent reads every session, and which this repo's
    own notes call "more invasive than a skill, not less" — was refreshed in
    place with one line of output and no diff. Every materialization is
    diffed, so the reasons cover whatever reaches any agent.
    """
    sides = _materialized_sides(kind, name, lk, new_raw)
    diff = updatediff.diff_tree({label: old for label, old, _ in sides},
                                {label: new for label, _, new in sides})
    if not diff.risky:
        return True
    return _show_and_confirm("%s %s" % (kind, name), diff, name)


def _hold_update(label: str, name: str, lk: dict, kind: str, old_v: str,
                 new_v: str, discard_edits: bool,
                 allow_downgrade: bool, base=None) -> tuple[bool, bool]:
    """Apply `staleness.update_hold` for one item: ``(held, edited)``.

    A held item is named with the way past it, because each remedy is a
    deliberate act: `boost reinstall` discards one item's edits,
    `--discard-edits` every edited item's this run, and `--allow-downgrade`
    follows a rewound tap. `--force` releases neither; it moves pinned taps.
    ``edited`` lets a released refresh say what it threw away. ``base`` is a
    project skill's repo: its edits are judged there, and the one-item remedy
    is a forced ``--local`` install, since ``reinstall`` reads the user lock.
    """
    edited = integrity.locally_edited(kind, name, lk, base=base)
    redo = ("boost install %s --local --force" % name if base is not None
            else "boost reinstall %s" % name)
    hold = staleness.update_hold(edited, old_v, new_v, discard_edits,
                                 allow_downgrade)
    if hold == staleness.HOLD_LOCAL_EDITS:
        out.warn("%s has local edits — update skipped; `%s` "
                 "discards them, or `boost update --discard-edits` for every "
                 "edited item" % (label, redo), wrap=True)
    elif hold == staleness.HOLD_DOWNGRADE:
        out.warn("%s: upstream is at v%s, behind your v%s — update skipped; "
                 "`boost update --allow-downgrade` downgrades"
                 % (label, out.plain(new_v), out.plain(old_v)), wrap=True)
    return hold is not None, edited


def _refresh_line(label: str, old_v: str, new_v: str, edited: bool,
                  bumped: bool) -> str:
    """The success line for a refresh, saying which way the version moved.

    Both versions are the tap's frontmatter, so they are compared raw and
    printed through :func:`out.plain`."""
    shown_old, shown_new = out.plain(old_v), out.plain(new_v)
    if bumped:
        msg = "upgraded %s v%s → v%s" % (label, shown_old, shown_new)
    elif new_v and util.semver_gt(old_v, new_v):
        msg = "downgraded %s v%s → v%s" % (label, shown_old, shown_new)
    else:
        msg = "refreshed %s v%s (source changed)" % (label,
                                                     shown_new or shown_old)
    return msg + (" — local edits discarded" if edited else "")


def _source_changed_hold(label: str, name: str, lk: dict, tapname: str) -> bool:
    """Warn and return True when ``tapname`` now names another repository.

    The tap's same-named item is not this install's upstream, so refreshing
    from it would replace one item with an unrelated one — and it would do so
    behind the risky-diff gate that `--yes` waives. Never implicit: `boost
    reinstall` is the explicit way to take the new source's copy.
    """
    try:
        tap = registry.get(tapname)
    except BoostError:
        return False
    if not registry.source_changed(lk, tap):
        return False
    recorded = str(lk.get("tap_url") or "")
    # A row older than `tap_url` names no URL to compare: what it knows is
    # that the tap was added again after it was installed.
    was = ("not %s where it was installed" % _tilde(recorded) if recorded
           else "and was tapped again since it was installed, from a source "
                "it did not record")
    out.warn("%s: not updated — tap %s now points at %s, %s; `boost "
             "reinstall %s` takes the new source's copy"
             % (label, tapname, _tilde(tap.url), was, name), wrap=True)
    return True


def _update_materialized(kind: str, installed: dict[str, dict], results,
                         discard_edits: bool = False,
                         allow_downgrade: bool = False, *,
                         index: dict[str, list[dict]],
                         ) -> tuple[int, int, int, int]:
    """Re-materialize installed rules/workflows whose tap source moved.

    Mirrors the skill upgrade loop: for each installed item from a refreshed
    tap, reinstall (force) when the source version bumped or its content sha
    changed — behind the same risky-diff gate the skill loop uses, and behind
    the same pin/quarantine skips: a pinned rule stays put, and refreshing a
    quarantined one would re-materialize the very content quarantine removed.
    An edited or downgraded item is held unless its flag releases it
    (`_hold_update`).
    Returns ``(refreshed, held, pinned, quarantined)`` — the last two count
    pinned and quarantined items whose source did move, so the caller can say
    they were held rather than that everything is up to date. ``held`` also
    counts an update that was attempted and refused (a policy block, a
    declined diff), which is just as much "not up to date".
    ``index`` is the run's :func:`catalog.name_index`, as in ``_update_skill``.
    """
    import hashlib
    n = held = pinned = quarantined = 0
    for name, lk in sorted(installed.items()):
        tapname = lk.get("tap")
        if tapname in (None, "local") or tapname not in results:
            continue
        if _source_changed_hold("%s %s" % (kind, name), name, lk, tapname):
            held += 1
            continue
        pool = index.get(catalog.split_name(name)[1], [])
        matches = [e for e in catalog.find(name, entries=pool)
                   if e["tap"] == tapname and e.get("kind", "skill") == kind]
        if not matches:
            out.warn("%s %s is no longer in tap %s — leaving as-is"
                     % (kind, name, tapname))
            continue
        # The lock's `source_file`, not scan order: one tap can ship a name
        # twice, and `matches[0]` refreshed the copy the user did not pick.
        entry, warning = catalog.select_lock_source(matches, lk)
        entry = cast(dict, entry)             # matches is non-empty above
        if warning:
            out.warn(warning)
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
        if lk.get("quarantined"):
            quarantined += 1
            continue
        if lk.get("pinned"):
            pinned += 1
            continue
        if scopes.stranded(lk):
            # Its repo is gone, and refreshing it would recreate that
            # directory (`store._refuse_stranded_base` refuses the write).
            # Said here, before the risky-diff prompt, so nobody is asked to
            # review a change that cannot be applied -- and only when there
            # is a change, since a stranded row with nothing new is not this
            # command's to report; `boost doctor` names it either way.
            out.warn("%s %s: update skipped — it was installed --local into "
                     "%s, which no longer exists; `boost uninstall %s` drops "
                     "the record" % (kind, name, _tilde(Path(lk["base"])),
                                     name), wrap=True)
            continue
        hold, edited = _hold_update("%s %s" % (kind, name), name, lk, kind,
                                    old_v, str(entry.get("version") or ""),
                                    discard_edits, allow_downgrade)
        if hold:
            held += 1
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
            held += 1
            continue
        try:
            # keep the item where it was installed (user vs a specific repo).
            # A dir that refused the refresh is named here, as for a skill.
            _warn_unwritable(store.install(
                entry, force=True,
                scope=lk.get("scope", "user"), base=lk.get("base"),
                via="update"))
        except BoostError as err:
            out.warn("%s: %s" % (name, err.message), stream=sys.stderr)
            held += 1
            continue
        out.ok(_refresh_line("%s %s" % (kind, name), old_v,
                             str(entry.get("version") or ""), edited, bumped))
        n += 1
    return n, held, pinned, quarantined


def _resync_vectors(moved: list[str]) -> None:
    """Keep prebuilt vectors honest after the taps underneath them move.

    A tap's commit is load-bearing for dense search: `dense.build` marks a tap
    "reused" per commit and `import_shard` refuses a shard built for another
    one. So an update that moves a tap leaves its vectors stale *but present* —
    the failure mode that looks like nothing at all, and the reason auto-
    updating taps in the background would quietly undo a shard import.

    Two outcomes are worth the network: a newer shard exists for the commit the
    tap just moved to, in which case importing it costs a download instead of
    an hour of CPU; or one does not, in which case the honest thing is to say
    the vectors are now stale and name the command that rebuilds them.
    """
    if not moved:
        return
    from ..core import dense, shards
    if not dense.ready():
        return                      # nothing embedded here to invalidate
    try:
        manifest = shards.fetch_manifest()
    except BoostError:
        # Offline, or no manifest published. The vectors are still stale, and
        # saying so without the remedy we could not check for is enough.
        out.info(out.role("prebuilt vectors for %d refreshed tap(s) are now "
                          "stale — `boost reindex --dense` rebuilds them"
                          % len(moved), "muted"))
        return
    commits = rag._tap_commits()
    by_name = {t.name: commits.get(t.safe_name, "")
               for t in registry.list_taps() if t.name in moved}
    # The one `sync` caller that printed nothing while it downloaded: a
    # `boost update` that moved forty taps fetched forty shards in silence.
    results = shards.sync(list(by_name), by_name, manifest=manifest,
                          on_event=_ingest_event)
    got = [r for r in results if r["status"] == "imported"]
    if got:
        out.ok("re-imported prebuilt vectors for %d tap(s)" % len(got))
    left = len(moved) - len(got)
    if left and any(r["status"] == "incompatible" for r in results):
        # Not "yet": a manifest in another space never matches this store,
        # however many weeks go by. Same words as every other refusal, and
        # wrapped before it is coloured (`- 2` pays for `out.info`'s indent).
        msg = ("vectors for %d refreshed tap(s) are now stale, and no "
               "published shard can replace them: %s"
               % (left, shards.remedy(manifest)))
        for line in out.wrap(msg, max(out.term_width() - 2, 20)):
            out.info(out.role(line, "muted"))
    elif left:
        out.info(out.role("%d refreshed tap(s) have no matching shard yet — "
                          "their vectors are stale until "
                          "`boost reindex --dense`" % left, "muted"))


def _ingest_event(tap: str, status: str, detail: str) -> None:
    """Progress for one tap, quiet enough to run over four hundred of them."""
    if status == "downloading":
        out.info(out.role("fetching %s %s" % (tap, detail), "muted"))
    elif status == "moving":
        out.info(out.role("moving %s to %s" % (tap, detail), "muted"))
    elif status == "failed":
        out.info(out.role("%s: failed%s"
                          % (tap, " (%s)" % detail if detail else ""), "muted"))


def _ingest_shards(args) -> int:
    """`boost update --shards`: refresh vectors from the published manifest.

    Its own mode rather than a step of the normal update, because the two move
    taps toward different targets: a plain `boost update` moves each tap to its
    branch HEAD, and this moves each tap to the commit the published vectors
    were built from. Running both in one pass would move every tap twice and
    leave the second answer standing, so the flag replaces the update rather
    than extending it.

    This is the ingestion path for the weekly shard run. It is a no-op on a
    machine that already holds this week's vectors, which is what makes it
    safe to put in a cron line — see the docs.
    """
    from ..core import dense, shards
    taps = registry.list_taps()
    if not taps:
        raise BoostError("no taps configured — nothing to refresh",
                         hint="`boost quickstart` taps the starters and loads "
                              "their vectors in one pass")
    manifest = shards.fetch_manifest()
    why = shards.incompatible(manifest)
    if why:
        # `wrap=True`: this refusal is a sentence, not a label and a
        # path, and it printed at 111 columns with a 173-column hint
        # under it at every pane width.
        raise BoostError("published shards cannot serve this machine — %s"
                         % why, hint=shards.remedy(manifest), wrap=True)
    commits = rag._tap_commits()
    stored = dense.tap_commits()
    # Both maps are keyed by tap name; the two sources are keyed by safe name.
    by_name = {t.name: commits.get(t.safe_name, "") for t in taps}
    built = {t.name: stored.get(t.safe_name, "") for t in taps}
    results = shards.ingest(
        list(by_name), by_name, built=built, manifest=manifest,
        # Progress goes to stdout, which is where the JSON goes: under `--json`
        # the two would interleave into something no parser can read.
        on_event=None if args.as_json else _ingest_event)

    imported = [r for r in results if r["status"] == "imported"]
    current = [r for r in results if r["status"] == "current"]
    failed = [r for r in results if r["status"] == "failed"]
    moved = [r["tap"] for r in results if r.get("moved")]
    # Before the output branch, never inside it: a tap that moved is describing
    # a different tree, so its catalog cache and the keyword index both name
    # entries that may no longer exist. Vectors are not the only thing a commit
    # is load-bearing for, and a `--json` caller is owed the same repair.
    for name in moved:
        catalog.rebuild_tap(registry.get(name))
    if moved:
        # Spinners write to stderr, so this is safe under `--json`.
        with spin.Spinner("rebuilding the keyword index"):
            rag.build()
        complete.refresh_names()
    journal.log("update", "--shards")
    # Nothing landed and nothing was already current: the manifest and this
    # machine have nothing to say to each other, which a cron line should
    # notice rather than read as a quiet success.
    rc = 1 if failed and not imported and not current else 0
    if args.as_json:
        print(json.dumps({"shards": results}, indent=2))
        return rc

    if imported:
        total = sum(int(r.get("chunks") or 0) for r in imported)
        out.ok("imported %s (%s chunk%s)%s"
               % (_plural(len(imported), "shard"), format(total, ","),
                  "" if total == 1 else "s",
                  ", %d moved to a newer commit" % len(moved) if moved else ""))
    if current:
        out.info(out.role("%s already at the published commit"
                          % _plural(len(current), "tap"), "muted"))
    if not imported and not current:
        # Never a tick. Nothing landed, and "imported 0" with a tick reads as a
        # job well done to the one user who most needs to know otherwise.
        out.warn("no published vectors matched your taps")
    unpublished = [r["tap"] for r in results if r["status"] == "unpublished"]
    if unpublished:
        out.info(out.role(
            "%s not in the manifest, left where they are: %s"
            % (_plural(len(unpublished), "tap"), ", ".join(unpublished[:5])
               + (" …" if len(unpublished) > 5 else "")), "muted"))
    for r in failed:
        out.warn("%s: %s" % (r["tap"], r.get("detail") or "failed"))
    if failed:
        out.info("embed those locally with `boost reindex --dense`")
    return rc


def _update_skill(name: str, lk: dict, scope: str, pbase, results,
                  args, *, heads: dict[str, str],
                  index: dict[str, list[dict]]) -> tuple[int, int, int, int]:
    """Refresh one installed skill: ``(upgraded, held, pinned, quarantined)``.

    ``scope``/``pbase`` say which install this row is: a project row is judged
    against its copy in the repo and reinstalled there (``--local --force``),
    and recorded in that repo's lock rather than the user's.

    ``heads`` memoises each tap's HEAD and ``index`` is the catalogue keyed by
    name (:func:`catalog.name_index`), both shared across the whole run: per
    skill, they were a git subprocess and a full ``all_entries`` + linear scan,
    O(installed x catalogue) — 308 skills over 63k entries spent ~9 s there.
    """
    label = name + (" (project)" if scope == scopes.SCOPE_PROJECT else "")
    tapname: str = lk.get("tap") or "local"
    if tapname == "local" or tapname not in results:
        return 0, 0, 0, 0
    if _source_changed_hold(label, name, lk, tapname):
        return 0, 1, 0, 0
    pool = index.get(catalog.split_name(name)[1], [])
    in_tap = [e for e in catalog.find(name, entries=pool)
              if e["tap"] == tapname]
    # A skill row refreshes only from a skill: the name alone also matched a
    # same-named workflow, which was installed beside the untouched skill.
    matches = [e for e in in_tap if e.get("kind", "skill") == "skill"]
    if in_tap and not matches:
        out.warn(staleness.kind_changed_message(
            label, name, tapname, (e.get("kind", "skill") for e in in_tap)),
            wrap=True)
        return 0, 0, 0, 0
    if not matches:
        out.warn("%s is no longer in tap %s — leaving as-is" % (label, tapname))
        return 0, 0, 0, 0
    # The lock's `source_dir`, not scan order: with two same-named copies in
    # one tap (`install --path` picked one), `matches[0]` silently swapped the
    # user's choice for whichever copy scanned first.
    entry, warning = catalog.select_lock_source(matches, lk)
    entry = cast(dict, entry)             # matches is non-empty above
    if warning:
        out.warn("%s: %s" % (label, warning))
    old_v = str(lk.get("version", "0.0.0"))
    new_v = str(entry.get("version", "0.0.0"))
    head, src_sha, exec_changed = "", None, False
    if not util.semver_gt(new_v, old_v):
        if tapname not in heads:
            heads[tapname] = gitutil.head_commit(registry.get(tapname).path)
        head = heads[tapname]
        if head and head != lk.get("commit"):
            try:
                src_sha = store.skill_source_sha(entry)
            except BoostError:
                return 0, 0, 0, 0
            exec_changed = store.source_exec_changed(
                entry, lk, integrity.project_skill_dir(lk, pbase)
                if scope == scopes.SCOPE_PROJECT
                else store.skill_store_dir(name))
    reason = staleness.upstream_reason(old_v, new_v, lk.get("commit", ""),
                                       head, lk.get("sha256", ""), src_sha,
                                       exec_changed)
    if reason is None:
        return 0, 0, 0, 0
    if lk.get("quarantined"):
        # Never refreshed — that would bring back the content quarantine
        # removed — but counted, like a pin, so the run doesn't end on
        # "everything up to date" while `outdated` lists it.
        return 0, 0, 0, 1
    if lk.get("pinned"):
        # Skipped, as `pin` promised — but counted, because `outdated`
        # names this same item and the summary must not contradict it.
        return 0, 0, 1, 0
    hold, edited = _hold_update(label, name, lk, "skill", old_v,
                                str(entry.get("version") or ""),
                                args.discard_edits, args.allow_downgrade,
                                base=pbase)
    if hold:
        return 0, 1, 0, 0
    # A declined diff or a refused install (a policy block) is held back too:
    # both used to end the run on "everything up to date".
    if not _confirm_risky_update(name, entry, base=pbase, lk=lk):
        out.warn("%s: update skipped — review the diff, then `boost update "
                 "--yes` to apply" % label)
        return 0, 1, 0, 0
    try:
        _warn_unwritable(store.install(entry, force=True, via="update",
                                       scope=scope, base=pbase))
    except BoostError as err:
        out.warn("%s: %s" % (label, err.message))
        return 0, 1, 0, 0
    out.ok(_refresh_line(label, old_v, str(entry.get("version") or ""),
                         edited, reason == staleness.VERSION))
    # A new version can declare a new `requires:`; install it as `boost
    # install` would have, in the scope the upgraded skill lives in.
    _install_closure([entry], scope=scope, pbase=pbase, via="update")
    return 1, 0, 0, 0


def cmd_update(argv: list[str]) -> int:
    ap = cliparse.parser(prog="boost update",
                                 description="Sync taps or update installed skills")
    ap.add_argument("tap", type=util.nonempty_str, nargs="?", metavar="TAP", help="refresh only this tap")
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
    ap.add_argument("--force", action="store_true",
                    help="move pinned taps too, clearing their pin")
    ap.add_argument("--discard-edits", action="store_true",
                    help="refresh locally edited skills, rules and workflows "
                         "too, overwriting the edits")
    ap.add_argument("--allow-downgrade", action="store_true",
                    help="follow a tap whose upstream version is now older "
                         "than the installed one")
    ap.add_argument("--shards", action="store_true",
                    help="refresh prebuilt vectors from the published "
                         "manifest, moving taps to the commits it names")
    ap.add_argument("--json", dest="as_json", action="store_true",
                    help="with --shards: print the per-tap result as JSON")
    args = ap.parse_args(argv)
    if args.as_json and not args.shards:
        ap.error("--json is only supported with --shards")
    if args.shards:
        if args.taps_only:
            ap.error("--shards and --taps-only move taps to different commits")
        return _ingest_shards(args)
    results, failures = registry.update(args.tap or None, force=args.force)
    if not results and not failures:
        print(out.empty_state("no taps configured",
                              hint="start with `boost tap --defaults`",
                              wrap=True))
        return 0
    moved = []
    pinned_skips = 0
    heads: dict[str, str] = {}
    for tname, summary in results.items():
        if "skipped" not in summary:
            # Rescan only a tap that moved, or whose cache is missing, from an
            # older CACHE_FORMAT, or scanned at another commit. Rescanning all
            # of them cost a full scan per tap on "already up to date", and the
            # rewrite bumped every cache mtime, so the next search rebuilt the
            # BM25 index too (rag.stale is stat-only).
            tap = registry.get(tname)
            heads[tname] = gitutil.head_commit(tap.path)
            if "→" in summary or not catalog.cache_is_fresh(tap,
                                                            heads[tname]):
                catalog.rebuild_tap(tap)
        else:
            pinned_skips += 1
        # "abc1234 → def5678" is a tap whose tree changed; "already up to date"
        # and "pinned at ..." are not. Only the first invalidates vectors.
        if "→" in summary:
            moved.append(tname)
        out.ok("%s: %s" % (tname, summary))
    _resync_vectors(moved)
    # Report the dead ones by name, after the successes, so a broken upstream
    # reads as one line of bad news rather than as the whole command failing.
    for tname, err in failures.items():
        out.warn("%s: %s" % (tname, err))
    refused = [t for t, e in failures.items() if registry.POLICY_REFUSAL in e]
    # A pin whose commit is gone upstream is a live tap: `untap` is the wrong
    # advice, and `--force` (which works) is the advice.
    unpinnable = [t for t, e in failures.items() if registry.PIN_MISSING in e]
    for tname in unpinnable:
        out.info(out.role(registry.pin_missing_remedy(tname), "muted"))
    # A lock a killed git left in the clone fails every command there, and the
    # tap is fine: `untap` would throw away a healthy clone over one file.
    locked = {t: lock for t, e in failures.items()
              if t not in unpinnable and (lock := gitutil.git_lock_path(e))}
    for tname, lock in locked.items():
        out.info(out.role("%s: %s" % (tname, gitutil.lock_hint(lock)),
                          "muted"))
    if refused:
        out.info(out.role(
            "%d tap%s refused by provenance policy and left on %s last "
            "verified commit — `boost trust verify` shows why"
            % (len(refused), "s" if len(refused) != 1 else "",
               "their" if len(refused) != 1 else "its"), "muted"))
    if len(failures) > len(refused) + len(unpinnable) + len(locked):
        out.info(out.role(
            "%d of %d taps could not be refreshed — the rest are up to date. "
            "Drop a dead one with `boost untap <name>`."
            % (len(failures) - len(refused) - len(unpinnable) - len(locked),
               len(results) + len(failures)),
            "muted"))
    if pinned_skips:
        out.info(out.role(
            "%d tap%s pinned and left alone — `boost update --force` moves "
            "%s too, dropping %s pin%s"
            % (pinned_skips, "s" if pinned_skips != 1 else "",
               "them" if pinned_skips != 1 else "it",
               "their" if pinned_skips != 1 else "its",
               "s" if pinned_skips != 1 else ""), "muted"))
    # A pulled tap can add, drop, or rename catalogue entries, so the
    # completion name cache must not survive an update unrefreshed.
    complete.refresh_names()
    journal.log("update", args.tap or "all")
    if args.taps_only:
        # Same exit-code rule as the end of the full path: non-zero only when
        # nothing was refreshed at all. This early return predates that rule
        # and kept answering 0 with every tap dead — and a cron'd
        # `boost update --taps-only` exists precisely to notice that morning.
        return 1 if refused or (failures and not results) else 0

    # Before any comparison: a row with no `tap_url` is one
    # `registry.source_changed` cannot protect.
    store.backfill_tap_urls()
    upgraded = held = pinned_held = quarantined_held = 0
    # Both locks, so a `--local` skill is refreshed in the repo it lives in —
    # the user lock alone left it at its old version under "everything up to
    # date" while `boost info` said it had an update.
    index = catalog.name_index(catalog.all_entries())
    for name, lk, scope, pbase in integrity.installed_skill_rows():
        n, h, p, q = _update_skill(name, lk, scope, pbase, results, args,
                                   heads=heads, index=index)
        upgraded += n
        held += h
        pinned_held += p
        quarantined_held += q
    # Rules and workflows refresh from the same tap update.
    # Skills installed before boost dated them, so a plugin's copy of the
    # same name can be weighed against them (store.serving_plugin).
    store.backfill_source_dates(results)
    for kind, section in (("rule", lockfile.installed_rules()),
                          ("workflow", lockfile.installed_workflows())):
        n, h, p, q = _update_materialized(
            kind, section, results, discard_edits=args.discard_edits,
            allow_downgrade=args.allow_downgrade, index=index)
        upgraded += n
        held += h
        pinned_held += p
        quarantined_held += q
    if held:
        # Never "everything up to date" over items it just declined to touch.
        out.info(out.role("%d item%s held back — see above"
                          % (held, "s" if held != 1 else ""), "muted"))
    if pinned_held:
        out.info(out.role(
            "%d pinned item%s ha%s an update held back — `boost outdated` "
            "lists %s, `boost unpin <name>` lets one update"
            % (pinned_held, "s" if pinned_held != 1 else "",
               "ve" if pinned_held != 1 else "s",
               "them" if pinned_held != 1 else "it"), "muted"))
    if quarantined_held:
        out.info(out.role(
            "%d quarantined item%s ha%s an update held back — `boost "
            "quarantine --release <name>` lets one update"
            % (quarantined_held, "s" if quarantined_held != 1 else "",
               "ve" if quarantined_held != 1 else "s"), "muted"))
    if not (held or pinned_held or quarantined_held or upgraded):
        if pinned_skips and pinned_skips == len(results) and not failures:
            # Every tap was a pinned skip: nothing was actually checked over
            # the network, which "everything up to date" would misreport as
            # a fresh confirmation rather than the truth — the run never left
            # config.json.
            out.ok("nothing to refresh — all taps pinned")
        else:
            # Don't claim "everything up to date" when some taps were never
            # reached — that is exactly the false all-clear this fix exists
            # to stop.
            out.ok("everything up to date" if not failures
                   else "everything up to date, except the taps above")
    # Non-zero only when nothing was refreshed at all. A partial run did the job
    # it could do, and failing it would put us back to one dead upstream
    # breaking `boost update` for the other 79.
    # A tap refused by provenance policy is the exception: that is a security
    # answer, not a flaky upstream, and a cron'd update must not read it as 0.
    return 1 if refused or (failures and not results) else 0


# ── reinstall ────────────────────────────────────────────────────────────

def _reinstall_held(kind: str, name: str, lk: dict, **source) -> bool:
    """Say so and return True when a pin forbids reinstalling ``name``.

    The decision is `store.reinstall_pin_hold`'s; this only words it, with the
    one command that releases the hold.
    """
    why = store.reinstall_pin_hold(kind, lk, **source)
    if why is None:
        return False
    label = name if kind == "skill" else "%s %s" % (kind, name)
    out.warn("%s: not reinstalled — %s; `boost unpin %s` first to take the "
             "new content" % (label, why, name), wrap=True, stream=sys.stderr)
    return True


def _reinstall_project_skill(name: str, lk: dict, pbase: Path) -> bool:
    """Reinstall one project-scope skill from its tap; True on success."""
    matches = [e for e in catalog.find(name)
               if e["tap"] == lk.get("tap") and e.get("kind", "skill") == "skill"]
    if not matches:
        out.warn(store.source_missing_message(name, name, lk), wrap=True, stream=sys.stderr)
        return False
    entry, warning = catalog.select_lock_source(matches, lk)
    entry = cast(dict, entry)                 # matches is non-empty above
    if warning:
        out.warn(warning)
    if _reinstall_held("skill", name, lk, cat_entry=entry):
        return False
    try:
        res = store.install(entry, force=True, scope=scopes.SCOPE_PROJECT,
                            base=pbase, via="reinstall")
    except BoostError as err:
        out.warn("%s: %s%s" % (name, err.message,
                               " — %s" % err.hint if err.hint else ""),
                 wrap=True, stream=sys.stderr)
        return False
    out.ok("reinstalled %s v%s (this repo)"
           % (name, out.plain(entry.get("version", "0.0.0"))))
    _warn_unwritable(res)
    return True


def cmd_reinstall(argv: list[str]) -> int:
    ap = cliparse.parser(prog="boost reinstall",
                                 description="Reinstall an installed skill, "
                                             "rule or workflow (force)")
    ap.add_argument("names", type=util.nonempty_str, nargs="*", metavar="NAME",
                    help="installed skill, rule or workflow (or pass --all)")
    ap.add_argument("--all", action="store_true",
                    help="reinstall every installed skill, rule and workflow")
    cliparse.add_scope_flags(
        ap, scope_help="reinstall only what is installed in your user config "
                       "or in this repo (default: the user lock as recorded)",
        local_help="what is installed in this repo (= --scope project)",
        global_help="what is installed in your user config (= --scope user)")
    args = ap.parse_args(argv)
    args.names = [store.installed_name(n, args.scope) for n in args.names]
    pbase = None
    if args.scope == scopes.SCOPE_PROJECT:
        pbase = scopes.resolve_base(scopes.SCOPE_PROJECT)
        if pbase is None:
            raise BoostError("not in a project — --local reinstalls what this "
                             "repo has installed",
                             hint="cd into the repo, or drop --local")
    pool = store.reinstall_candidates(args.scope, pbase)
    by_name = {name: (kind, name, entry) for kind, name, entry in reversed(pool)}
    done, failed = 0, 0
    done_kinds: set[str] = set()
    items: list[tuple] = []
    if args.all:
        items = pool
        if not items:
            raise BoostError("nothing to reinstall",
                            hint="nothing installed yet — see `boost list`")
    elif not args.names:
        raise BoostError("nothing to reinstall",
                        hint="name a skill or pass --all")
    else:
        for name in args.names:
            if args.scope is None:
                found = lockfile.find_any(name)
                prow = _project_row(name) if found is None else None
                if prow is not None:
                    # Its scope and base ride on the row, so the install below
                    # rewrites the repo's copy rather than adding a user one.
                    items.append(("skill", name, prow.entry
                                  | {"scope": scopes.SCOPE_PROJECT,
                                     "base": str(prow.base)}))
                    continue
            else:
                hit = by_name.get(name)
                found = (hit[0], hit[2]) if hit else None
            if found is None:
                where = {scopes.SCOPE_PROJECT: " in this repo",
                         scopes.SCOPE_USER: " in your user config"}.get(
                             args.scope or "", "")
                if len(args.names) == 1:
                    raise BoostError("%s is not installed%s" % (name, where),
                                    hint="see what is with `boost list`")
                out.warn("%s is not installed%s — skipped" % (name, where), stream=sys.stderr)
                failed += 1
                continue
            items.append((found[0], name, found[1]))
    quarantined_held = 0
    for kind, name, lk in items:
        refusal = store.quarantine_refusal(name, lk, kind)
        if refusal is not None:
            # Lifting a quarantine is `quarantine --release`'s decision, not
            # a side effect of a reinstall: it threw the held copy away and
            # took the tap's HEAD. `--all` holds it back as `update` does; a
            # named one is refused and named.
            if args.all:
                quarantined_held += 1
            else:
                out.warn("%s — %s" % (refusal.message, refusal.hint),
                         wrap=True, stream=sys.stderr)
                failed += 1
            continue
        if kind != "skill":
            # Rules/workflows always come from a tap (`boost import` is
            # skill-only), so resolve the catalog entry the way
            # _update_materialized does and re-materialize where it was
            # installed (user config vs a specific repo).
            matches = [e for e in catalog.find(name)
                       if e["tap"] == lk.get("tap")
                       and e.get("kind", "skill") == kind]
            if not matches:
                out.warn(store.source_missing_message(
                    "%s %s" % (kind, name), name, lk), wrap=True, stream=sys.stderr)
                failed += 1
                continue
            entry, warning = catalog.select_lock_source(matches, lk)
            entry = cast(dict, entry)         # matches is non-empty above
            if warning:
                out.warn(warning)
            if _reinstall_held(kind, name, lk, cat_entry=entry):
                failed += 1
                continue
            try:
                res = store.install(entry, force=True,
                                    scope=lk.get("scope", "user"),
                                    base=lk.get("base"), via="reinstall")
            except BoostError as err:
                # The hint too: a refusal to recreate a deleted repo is only
                # useful with the `boost uninstall` that clears it.
                out.warn("%s: %s%s" % (name, err.message,
                                       " — %s" % err.hint if err.hint else ""),
                         wrap=True, stream=sys.stderr)
                failed += 1
                continue
            # Success first, then what it skipped: the same order as every
            # other branch, so a `--all` run reads the same line to line.
            out.ok("reinstalled %s %s v%s"
                   % (kind, name, out.plain(entry.get("version", "0.0.0"))))
            _warn_unwritable(res)
            done += 1
            done_kinds.add(kind)
            continue
        row_base = pbase if pbase is not None else lk.get("base")
        if lk.get("scope") == scopes.SCOPE_PROJECT and row_base:
            # A repo's skill: real directories in the repo, recorded in its
            # own lock, so it goes back the way `install --local` put it.
            if not _reinstall_project_skill(name, lk, Path(row_base)):
                failed += 1
                continue
            done += 1
            done_kinds.add("skill")
            continue
        if lk.get("tap") == "local":
            if integrity.self_sourced(name, lk):
                # Its source is its own store dir: "reinstalling" would copy
                # it onto itself, and there is no other copy to restore.
                out.info("%s is kept in the store itself, so there is nothing "
                         "to reinstall it from — skipped" % name, wrap=True)
                continue
            src = store.local_source_dir(lk)
            url = str(lk.get("source_url") or "")
            if src is None and not url:
                out.warn("%s: local source %s is gone — skipped"
                         % (name, _tilde(str(lk.get("source_dir") or ""))), stream=sys.stderr)
                failed += 1
                continue
            if src is not None and _reinstall_held("skill", name, lk, src=src):
                failed += 1
                continue
            # force=True to match the tap branch's `install(..., force=True)`:
            # reinstalling a pinned skill is the point of the command. Policy
            # still applies. The try/except mirrors the tap branch too —
            # without it one policy-blocked skill aborts `--all` mid-run and
            # the remaining names are never attempted.
            try:
                if src is not None:
                    res = store.install_from_path(src, name=name, force=True)
                    how = "local, from %s" % _tilde(src)
                else:
                    # A URL import's clone was deleted when the import
                    # returned; the lock kept the URL so it can be cloned again.
                    res = store.reinstall_from_url(name, lk)
                    commit = str((lockfile.get_skill(name) or {}).get("commit") or "")
                    how = ("from %s at %s" % (url, commit[:7]) if commit
                           else "from %s" % url)
            except BoostError as err:
                out.warn("%s: %s" % (name, err.message), stream=sys.stderr)
                failed += 1
                continue
            store.keep_sideline(name, lk, res)
            out.ok("reinstalled %s (%s)" % (name, how))
            _warn_unwritable(res)
            done += 1
            done_kinds.add("skill")
            continue
        in_tap = [e for e in catalog.find(name) if e["tap"] == lk.get("tap")]
        matches = [e for e in in_tap if e.get("kind", "skill") == "skill"]
        if in_tap and not matches:
            out.warn(staleness.kind_changed_message(
                name, name, str(lk.get("tap")),
                (e.get("kind", "skill") for e in in_tap)), wrap=True)
            failed += 1
            continue
        if not matches:
            out.warn(store.source_missing_message(name, name, lk), wrap=True, stream=sys.stderr)
            failed += 1
            continue
        entry, warning = catalog.select_lock_source(matches, lk)
        entry = cast(dict, entry)             # matches is non-empty above
        if warning:
            out.warn(warning)
        if _reinstall_held("skill", name, lk, cat_entry=entry):
            failed += 1
            continue
        try:
            res = store.install(entry, force=True, via="reinstall")
        except BoostError as err:
            out.warn("%s: %s%s" % (name, err.message,
                                   " — %s" % err.hint if err.hint else ""),
                     wrap=True, stream=sys.stderr)
            failed += 1
            continue
        out.ok("reinstalled %s v%s"
               % (name, out.plain(entry.get("version", "0.0.0"))))
        _warn_unwritable(res)
        done += 1
        done_kinds.add("skill")
    # Name the kind when only one was touched; a mixed run says "items".
    # With nothing done, name what was *attempted*: a refused rule used to
    # tally as "Reinstalled 0 skills".
    tried = done_kinds or {k for k, _, _ in items}
    noun = next(iter(tried)) if len(tried) == 1 else (
        "item" if tried else "skill")
    out.info("Reinstalled %s" % _plural(done, noun))
    if quarantined_held:
        out.info(out.role(
            "%d quarantined item%s held back — `boost quarantine --release "
            "<name>` lets one be reinstalled"
            % (quarantined_held, "s" if quarantined_held != 1 else ""),
            "muted"))
    return 1 if failed else 0


# ── bundle ───────────────────────────────────────────────────────────────

def cmd_bundle(argv: list[str]) -> int:
    ap = cliparse.parser(
        prog="boost bundle",
        description="Export/install skill sets via a Boostfile",
        epilog="Boostfile lines: `tap NAME [URL] [--at SHA]` and `skill "
               "[TAP:]NAME[@VERSION] [--local] [--agent A]... [--pin] "
               "[--commit-pin SHA] [--tag T]...`; `#` starts a comment. "
               "`--at` holds the tap at a commit, as `boost tap --at` does; "
               "the skill options replay `boost install --local/--agent`, "
               "`boost pin [--commit]` and `boost tag +T`. Every option is "
               "optional, so older Boostfiles still install.")
    ap.add_argument("action", choices=("dump", "install"),
                    help="dump installed skills to a Boostfile, or install "
                         "from one")
    ap.add_argument("file", type=util.nonempty_str, nargs="?", metavar="FILE",
                    help="Boostfile (dump: default stdout; "
                         "install: default ./Boostfile, '-' = stdin)")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what install would do, or print what dump "
                         "would write, touching nothing")
    args = ap.parse_args(argv)
    if args.action == "dump":
        return _bundle_dump(args.file, dry_run=args.dry_run)
    return _bundle_install(args.file, args.dry_run)


def _bundle_dump(file: str | None, dry_run: bool = False) -> int:
    _pbase, project = store.project_skills()
    text = _boostfile_text(lockfile.installed(), project=project)
    lines = text.splitlines()
    # What the file cannot reinstall, said on both paths: a local skill is
    # only a comment in it, and rules/workflows are not in it at all.
    notices = []
    n_local = sum(1 for ln in lines if ln.startswith("# local skill"))
    if n_local:
        notices.append("%s written as comments — no tap source to reinstall "
                       "from" % _plural(n_local, "local skill"))
    others = _others_installed()
    if others:
        notices.append("%s not captured — Boostfiles carry skills only" % others)
    if not file or file == "-" or dry_run:
        print(text, end="")
        # stdout IS the Boostfile here; the notices go to stderr so
        # `boost bundle dump > Boostfile` stays a parseable artifact.
        for msg in notices:
            out.warn(msg, stream=sys.stderr)
        if dry_run and file and file != "-":
            # --dry-run promises to touch nothing: the FILE a user names may
            # be a hand-written Boostfile, and overwriting it was the bug.
            out.info("dry run — %s not written" % _tilde(paths.expand(file)),
                     stream=sys.stderr)
        return 0
    dest = paths.expand(file)
    try:
        dest.write_text(text, encoding="utf-8")
    except OSError as e:
        raise BoostError("cannot write %s: %s" % (_tilde(dest), e.strerror or e),
                        hint="check the path exists and is writable") from e
    n_taps = sum(1 for ln in lines if ln.startswith("tap "))
    n_skills = sum(1 for ln in lines if ln.startswith("skill "))
    out.ok("wrote %s (%s, %s)" % (_tilde(dest), _plural(n_taps, "tap"),
                                  _plural(n_skills, "skill")))
    for msg in notices:
        out.warn(msg)
    return 0


def _read_stdin_utf8() -> str:
    """Standard input as UTF-8 text, the way a Boostfile path is read.

    The bytes underneath, not ``sys.stdin.read()``: the text layer decodes
    with the inherited locale codec, so under ``PYTHONIOENCODING=ascii`` a
    Boostfile with one accented comment crashed from stdin while the same
    file by path installed. A closed fd 0 (``<&-``, where Python sets
    ``sys.stdin`` to None) reads as empty — there is nothing there.
    """
    stream = sys.stdin
    if stream is None:
        return ""
    raw = getattr(stream, "buffer", None)
    if raw is None:
        return stream.read()
    data = raw.read()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise BoostError("<stdin> is not UTF-8 text (byte %d)" % e.start,
                         hint="save the Boostfile as UTF-8") from None


def _held_tap(tname: str, turl: str, tat: str, where: str) -> str:
    """How an already-configured tap measures up to a Boostfile ``tap`` line.

    ``"conflict"`` when the line's URL names another repository than the one
    configured under that name — installing its skills from the configured
    one would reproduce a different setup under the same names — ``"drift"``
    when the line pins ``--at`` a commit the clone is not on, else ``"ok"``.
    Each non-ok verdict is said, naming both sides.
    """
    tap = registry.get(tname)
    if turl:
        try:
            want = registry.parse_spec(turl)[1]
        except BoostError:
            want = turl
        if not registry.same_source(tap.url, want):
            out.warn("%s: tap %s is configured as %s, but the Boostfile wants "
                     "%s — not re-tapped, and its skill lines are skipped"
                     % (where, tname, tap.url, want), wrap=True)
            return "conflict"
    if tat:
        head = gitutil.head_commit(tap.path) or tap.pin
        if head != tat:
            out.warn("%s: tap %s is at %s, Boostfile wants --at %s — kept as "
                     "tapped" % (where, tname, head[:7] or "no commit",
                                 tat[:7]), wrap=True)
            return "drift"
    return "ok"


def _apply_line_state(spec: boostfile.SkillLine, kind: str, pbase,
                      where: str) -> bool:
    """Put a just-installed line's pins and tags on its lock row.

    False when the line's ``--commit-pin`` names a commit other than the one
    installed: the pin is then not written, because `boost verify` would
    fail it at once for a cause three steps back (the tap's commit).
    """
    if spec.local:
        if spec.pin:
            store.set_project_pin(pbase, spec.name, True)
        return True
    if not (spec.pin or spec.tags or spec.commit_pin):
        return True
    installed_at: list[str] = []

    def put(row: dict) -> None:
        if spec.pin:
            row["pinned"] = True
        if spec.tags:
            row["tags"] = lockfile.apply_tag_mods(
                list(row.get("tags") or []), ["+" + t for t in spec.tags])[0]
        if spec.commit_pin:
            if row.get("commit") == spec.commit_pin:
                row["commit_pin"] = spec.commit_pin
            else:
                installed_at.append(str(row.get("commit") or ""))
    lockfile.update_entry(kind, spec.name, put)
    if installed_at:
        out.warn("%s: %s: installed at %s, Boostfile commit-pins %s — not "
                 "commit-pinned" % (where, spec.name,
                                    installed_at[0][:12] or "no commit",
                                    spec.commit_pin[:12]), wrap=True)
        return False
    return True


def _bundle_install(file: str | None, dry_run: bool = False) -> int:
    """Apply a Boostfile, or with ``dry_run`` report what applying it would do.

    A bundle install taps registries, installs skills **and materializes rules
    into the agent's own context file** — `boost install` has had a
    ``--dry-run`` all along and the one command that can edit `CLAUDE.md`
    unattended had no way to preview. Every mutation below is therefore
    guarded at its call site rather than by returning early, so the report
    walks the same lines in the same order the real run would.
    """
    if file == "-":
        text, label = _read_stdin_utf8(), "<stdin>"
        shown = label  # one spelling, in the warning and the journal alike
    else:
        path = paths.expand(file or "./Boostfile")
        # Absolute, not as given: pathlib folds `./Boostfile` to `Boostfile`,
        # which made the missing-file error the tautology "no Boostfile at
        # Boostfile". Not resolve(): that would swap a symlinked /tmp for
        # /private/tmp in a path the user never typed.
        shown = _tilde(path.absolute())
        if not path.exists():
            raise BoostError("no Boostfile at %s" % shown,
                            hint="create one with `boost bundle dump Boostfile`")
        if path.is_dir():
            raise BoostError("%s is a directory, not a Boostfile" % shown,
                            hint="point at the Boostfile itself, "
                                 "or use `boost import` for skill directories")
        try:
            text, label = path.read_text(encoding="utf-8"), str(path)
        except OSError as e:
            raise BoostError("cannot read %s: %s" % (shown, e.strerror or e)) from e
        except UnicodeDecodeError as e:
            raise BoostError("%s is not UTF-8 text (byte %d)" % (shown, e.start),
                             hint="save the Boostfile as UTF-8") from None
    # A Boostfile saved by a Windows editor opens with a BOM, which glued itself
    # to the first directive ("\ufeffskill") and failed it as "unrecognised"
    # with the culprit invisible in the message. Stripped after both branches,
    # since stdin carries it just the same.
    text = text.removeprefix(frontmatter.BOM)
    taps_added = installed_n = present = drifted = unresolved = failed = 0
    directives = 0
    installed_kinds: set[str] = set()
    would_tap: set[str] = set()
    would_rules: list[str] = []
    have_taps = {t.name for t in registry.list_taps()}
    # Taps whose Boostfile URL names another repository than the one
    # configured under that name; skill lines qualified with one are refused.
    conflicted: set[str] = set()
    # name -> (kind, lock entry) across every lock section, so a `skill` line
    # naming an already-installed rule/workflow is counted present, not
    # re-installed — and so its tap and version can be held to the line.
    have_installed: dict[str, tuple[str, dict]] = {}
    for kind, section in lockfile.all_installed().items():
        for n, lk in section.items():  # first section wins: skill > rule >
            have_installed.setdefault(n, (kind, lk))  # workflow, as find_any
    # A `skill … --local` line is held against the project lock instead.
    pbase, project = store.project_skills()
    have_project: dict[str, tuple[str, dict]] = {
        n: (lk.get("kind", "skill"), lk) for n, lk in project.items()}

    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        directives += 1
        parts = line.split(None, 2)
        # Every per-line diagnostic names FILE:LINE, so a forty-line Boostfile
        # does not leave the reader hunting for which `skill` line failed.
        where = "%s:%d" % (shown, lineno)
        if parts[0] == "tap" and len(parts) >= 2:
            tname = parts[1]
            try:
                turl, tat = boostfile.parse_tap(parts[2] if len(parts) > 2 else "")
            except BoostError as err:
                out.warn("%s: %s — skipped" % (where, err.message))
                failed += 1
                continue
            if tname in have_taps:
                verdict = _held_tap(tname, turl, tat, where)
                if verdict == "conflict":
                    conflicted.add(tname)
                    failed += 1
                elif verdict == "drift":
                    drifted += 1
                continue
            at_label = " @ %s" % tat[:7] if tat else ""
            if dry_run:
                # Nothing is cloned, so any skill line naming this tap cannot
                # be resolved below — said plainly there rather than guessed.
                # Under the name the real run will use: it names the tap from
                # its URL (`registry.add` -> `parse_spec`), not from this
                # line's NAME, so `tap myalias ./x` is tapped as `x`. A `skill
                # x:…` line defers here as it will install there, and a `skill
                # myalias:…` line misses here as it will miss there — deferring
                # it too exited 0 on a file whose real run exits 1.
                derived = tname
                try:
                    derived = registry.parse_spec(turl or tname)[0]
                except BoostError:
                    # no derivable name: NAME is then all there is to match
                    would_tap.add(tname)
                else:
                    # Already configured under that name, a skill line naming
                    # it resolves now and misses the way the real run will,
                    # so it must not be deferred as "cannot resolve yet".
                    if derived not in have_taps:
                        would_tap.add(derived)
                out.info("would tap %s%s%s" % (tname, "" if derived == tname
                                               else " (as %s)" % derived,
                                               at_label))
                taps_added += 1
                continue
            try:
                tap = registry.add(turl or tname, at=tat or None)
                catalog.rebuild_tap(tap)
            except BoostError as err:
                out.warn("%s: tap %s failed: %s" % (where, tname, err.message))
                failed += 1
                continue
            have_taps.add(tap.name)
            taps_added += 1
            out.ok("tapped %s%s" % (tap.name, at_label))
        elif parts[0] == "skill" and len(parts) >= 2:
            try:
                spec = boostfile.parse_skill(parts[1],
                                             parts[2] if len(parts) > 2 else "")
                only_agents = _check_agents(spec.agents)
            except BoostError as err:
                out.warn("%s: %s — skipped" % (where, err.message))
                failed += 1
                continue
            tapq, sname, sver, local = spec.tap, spec.name, spec.version, spec.local
            if local and pbase is None:
                out.warn("%s: %s is a project-scope skill and there is no "
                         "project directory here — skipped" % (where, sname))
                failed += 1
                continue
            if tapq and any(catalog.tap_matches(t, tapq) for t in conflicted):
                # Resolving it would install from the repository configured
                # under that name, which the tap line above just said is not
                # the one this Boostfile describes.
                out.warn("%s: %s skipped — tap %s is not the repository the "
                         "Boostfile names" % (where, sname, tapq))
                failed += 1
                continue
            here = have_project if local else have_installed
            if sname in here:
                kind_here, lk = here[sname]
                drift = store.lock_drift(lk, tapq, sver)
                # Before the kind check, on purpose: a rule or workflow
                # installed from another tap or at another version is drift
                # just as a skill is, so it counts "differs", not "present".
                if drift:
                    # A Boostfile is a reproducibility contract, so an install
                    # from another tap or at another version is not "already
                    # present". Kept rather than replaced: swapping out what
                    # the user has is not this command's call to make.
                    out.warn("%s: %s: %s — kept as installed" % (where, sname, "; ".join(
                        ("installed from %s, Boostfile wants %s" if field == "tap"
                         else "installed %s, Boostfile wants @%s") % (have, want)
                        for field, have, want in drift)), wrap=True)
                    drifted += 1
                    continue
                if kind_here != "skill":
                    out.info("%s is already installed as a %s — skipped"
                             % (sname, kind_here))
                present += 1
                continue
            matches = catalog.find(sname, tap=tapq or None)
            if not matches:
                if dry_run and (any(catalog.tap_matches(t, tapq)
                                    for t in would_tap)
                                if tapq else would_tap):
                    # Honest rather than optimistic: the tap it would come
                    # from has not been cloned, so whether this resolves is
                    # genuinely unknown until it is. Only then, though — a
                    # line qualified with a tap already present resolves
                    # right now, and misses the way the real run will.
                    out.info("%s — cannot resolve yet; its tap would be "
                             "added by this same file" % sname)
                    unresolved += 1
                    continue
                out.warn("%s: %s not found%s — skipped"
                         % (where, sname, (" in tap %s" % tapq) if tapq else ""))
                failed += 1
                continue
            if len({e["tap"] for e in matches}) > 1:
                # A Boostfile is meant to be reproducible, so guessing which tap
                # `skills:brainstorming` meant is the one thing this must not do.
                out.warn("%s: %s is ambiguous — in %s; qualify it as "
                         "owner/repo:%s"
                         % (where, sname,
                            ", ".join(sorted({e["tap"] for e in matches})),
                            sname))
                failed += 1
                continue
            entry = matches[0]
            if entry["tap"] in conflicted:
                # An unqualified line resolves to a tap all the same, and the
                # one it found is the repository the tap line was refused for.
                out.warn("%s: %s skipped — it resolves to tap %s, which is not "
                         "the repository the Boostfile names"
                         % (where, sname, entry["tap"]))
                failed += 1
                continue
            if sver and str(entry.get("version")) != sver:
                # Installed all the same — the line asked for this skill — but
                # counted as a difference, so the summary does not report a
                # faithful reproduction of a file it did not reproduce.
                out.warn("%s: %s: Boostfile wants @%s, tap has %s — %s that"
                         % (where, sname, sver, out.plain(entry.get("version")),
                            "would install" if dry_run else "installing"))
                drifted += 1
            entry_kind = entry.get("kind", "skill")
            # The line's `requires:` closure first, as `boost install` plans
            # it: the line used to install the skill alone. Items an earlier
            # line installed (or, in a dry run, would have) count as present.
            pulled, dep_failed = _install_closure(
                [entry], scope=scopes.SCOPE_PROJECT if local
                else scopes.SCOPE_USER, pbase=pbase,
                only_agents=only_agents,
                also_installed=list(here) if dry_run else (),
                dry_run=dry_run)
            failed += dep_failed
            for dep in pulled:
                dep_kind = dep.get("kind", "skill")
                if dry_run and dep_kind == "rule":
                    would_rules.append(dep["name"])
                here[dep["name"]] = (dep_kind, dep)
                installed_kinds.add(dep_kind)
                installed_n += 1
            if dry_run:
                # The run's policy gate: a blocklisted line was previewed as
                # "would install" with rc 0, and the run then refused it.
                # Warned in the run's own words, and counted as it counts it.
                why = store.install_policy_refusal(
                    entry, scope=scopes.SCOPE_PROJECT if local
                    else scopes.SCOPE_USER, base=pbase)
                if why:
                    out.warn("%s: %s: %s" % (where, sname, why))
                    failed += 1
                    continue
                out.info("would install %s v%s (%s)%s%s"
                         % (sname, out.plain(entry.get("version")),
                            entry["tap"],
                            "" if entry_kind == "skill"
                            else " [%s]" % entry_kind,
                            " at project scope" if local else ""))
                if entry_kind == "rule":
                    would_rules.append(sname)
                here[sname] = (entry_kind, entry)
                installed_kinds.add(entry_kind)
                installed_n += 1
                continue
            try:
                res = (store.install(entry, scope=scopes.SCOPE_PROJECT,
                                     base=pbase, only_agents=only_agents)
                       if local
                       else store.install(entry, only_agents=only_agents))
            except BoostError as err:
                out.warn("%s: %s: %s" % (where, sname, err.message))
                failed += 1
                continue
            out.ok("installed %s v%s (%s)%s" % (sname,
                                                out.plain(entry.get("version")),
                                                entry["tap"],
                                                " at project scope" if local
                                                else ""))
            _warn_unwritable(res)
            if not _apply_line_state(spec, entry_kind, pbase, where):
                drifted += 1
            here[sname] = (entry_kind, entry)
            installed_kinds.add(entry_kind)
            installed_n += 1
        else:
            out.warn("%s: unrecognised: %s" % (where, line))
            failed += 1
    if not directives:
        # An empty stdin or a comments-only file is not an error, but a bare
        # "Installed 0 skills" reads as "everything was already in place".
        out.warn("nothing to apply: %s has no tap or skill lines" % shown)
    # A "skill NAME" line can resolve to a rule or workflow (`catalog.find`
    # searches every kind) — name the kind when only one was actually
    # installed, the same call `cmd_reinstall` makes, so this summary agrees
    # with what `bundle dump`'s own kind-aware sections would call it. Shared
    # by both paths, so a preview names what the run will.
    noun = next(iter(installed_kinds)) if len(installed_kinds) == 1 else (
        "item" if installed_kinds else "skill")
    differ = "%d %s from the Boostfile" % (drifted,
                                          "differs" if drifted == 1 else "differ")
    if dry_run:
        summary = "would install %s" % _plural(installed_n, noun)
        if taps_added:
            summary += ", add %s" % _plural(taps_added, "tap")
        if present:
            summary += ", %d already present" % present
        if drifted:
            summary += ", " + differ
        if unresolved:
            summary += ", %d unresolved until tapped" % unresolved
        if failed:
            summary += ", %d would fail" % failed
        out.info(summary)
        if would_rules:
            # The reason this flag exists. A rule is materialized into the
            # agent's own context file — the one the user reads every session
            # — so it is the most invasive thing a Boostfile can do and the
            # least visible.
            out.warn("%s would be installed as a rule and edit your agent "
                     "context file (e.g. ~/.claude/CLAUDE.md): %s"
                     % (_plural(len(would_rules), "item"),
                        ", ".join(sorted(would_rules))), wrap=True)
        return 1 if failed else 0
    if taps_added:
        complete.refresh_names()
    journal.log("bundle-install", label, taps=taps_added, skills=installed_n)
    summary = "Installed %s" % _plural(installed_n, noun)
    if taps_added:
        summary += ", added %s" % _plural(taps_added, "tap")
    if present:
        summary += ", %d already present" % present
    if drifted:
        summary += ", " + differ
    if failed:
        summary += ", %d failed" % failed
    out.info(summary)
    return 1 if failed else 0


# ── import ───────────────────────────────────────────────────────────────

def cmd_import(argv: list[str]) -> int:
    ap = cliparse.parser(
        prog="boost import",
        description="Import skills from a GitHub URL or local path")
    ap.add_argument("source", type=util.nonempty_str, metavar="URL_OR_PATH",
                    help="git URL (http(s)://, git@, ssh://) or a local directory")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--name", type=util.nonempty_str, metavar="N",
                       help="skill to pick when several are found (or a rename)")
    group.add_argument("--all", action="store_true", help="import every skill found")
    ap.add_argument("--agent", type=util.nonempty_str, action="append", metavar="A",
                    help="link only into this agent (repeatable)")
    ap.add_argument("-y", "--yes", action="store_true",
                    help="skip the replace-the-only-copy confirmation prompt")
    args = ap.parse_args(argv)
    only = _check_agents(args.agent)
    if args.source.startswith(("http://", "https://", "git@", "ssh://")):
        out.info("cloning %s …" % args.source)
        with store.cloned_source(args.source) as remote:
            return _import_root(remote.root, args.name, args.all, only,
                                args.source, remote=remote, yes=args.yes)
    root = paths.expand(args.source)
    if not root.is_dir():
        raise BoostError("no such directory: %s" % args.source,
                        hint="pass a local path or a git URL")
    return _import_root(root, args.name, args.all, only, args.source,
                        yes=args.yes)


def _warn_import(res: store.InstallResult, narrowed: bool) -> None:
    """What an import changed beyond the files: provenance and stray links.

    ``narrowed`` is whether this run passed ``--agent``. Without it the scope
    is one an earlier run recorded and this one carried forward, and saying
    it was "just declared" sends the reader looking for a flag they never
    passed.
    """
    if res.replaced_tap:
        out.warn("%s was installed from %s — it is a local import now, so "
                 "`boost update` will not refresh it "
                 "(`boost install %s --force` puts the tap's copy back)"
                 % (res.name, res.replaced_tap,
                    util.shell_arg("%s:%s" % (res.replaced_tap, res.name))),
                 wrap=True)
    if res.out_of_scope:
        out.warn("%s is still linked into %s, outside the --agent scope %s "
                 "— `boost sync --prune` removes those links"
                 % (res.name, ", ".join(res.out_of_scope),
                    "just declared" if narrowed else "an earlier run declared"),
                 wrap=True)


def _import_root(root: Path, name: str | None, do_all: bool,
                 only: list[str] | None, display: str,
                 remote: store.RemoteSource | None = None,
                 yes: bool = False) -> int:
    def replacing(dirs: list[tuple[Path, str | None]]) -> bool:
        """Ask before an import overwrites a skill that has no other copy."""
        only_copies = [n for d, r in dirs
                       if store.replaces_only_copy(n := store.import_name(d, r), d)]
        if not only_copies:
            return True
        if yes or out.confirm("the store holds the only copy of %s, and importing "
                       "replaces it for good — continue?"
                       % ", ".join(only_copies)):
            return True
        out.info("cancelled")
        return False

    def one(skill_dir: Path, rename: str | None = None) -> int:
        if not replacing([(skill_dir, rename)]):
            return 1
        res = store.install_from_path(skill_dir, name=rename, only_agents=only,
                                      remote=remote)
        _report_result(res)
        _warn_import(res, only is not None)
        out.info("Imported %s; quality score %d/100" % (res.name, res.score))
        return 0

    if (root / "SKILL.md").exists():
        return one(root, rename=name)
    # import copies SKILL.md dirs: a rule or workflow is one file with no
    # SKILL.md, and offering one crashed every path that read it as a skill.
    entries: list[dict] = []
    others: list[dict] = []
    for e in catalog.scan_dir(root):
        (entries if e.get("kind", "skill") == "skill" else others).append(e)
    other_hint = "rules and workflows install from a tap: `boost tap %s`, " \
        "then `boost install NAME`" % display
    if name and not do_all:
        clash = [e for e in others if e["name"] == name]
        if clash and not any(e["name"] == name for e in entries):
            raise BoostError("%s is a %s, and boost import takes skills"
                             % (name, clash[0]["kind"]), hint=other_hint)
    if not entries:
        raise BoostError("no SKILL.md found under %s" % display,
                         hint=other_hint if others else None)
    if others:
        out.info("skipping %s — boost import takes skills; %s" % (
            ", ".join("%s (%s)" % (e["name"], e["kind"]) for e in others),
            other_hint), wrap=True)

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
        if not replacing([(dir_of(e), None) for e in entries]):
            return 1
        imported, refused = 0, 0
        for e in entries:
            try:
                res = store.install_from_path(dir_of(e), only_agents=only,
                                              remote=remote)
            except BoostError as err:
                out.warn("%s: %s" % (e["name"], err.message))
                refused += 1
                continue
            out.ok("imported %s v%s (score %d/100)" % (res.name,
                                                       out.plain(e["version"]),
                                                       res.score))
            _warn_unwritable(res)
            _warn_injection(res)
            _warn_secrets(res)
            _warn_import(res, only is not None)
            imported += 1
        out.info("Imported %s" % _plural(imported, "skill"))
        return 1 if refused else 0
    out.heading("%d skills in %s" % (len(entries), display))
    # Whole descriptions: `out.table` fits the widest column to the pane and
    # clips it there with an ellipsis, so cutting first only wasted columns.
    # One line each, and no control bytes — this is a foreign repo's frontmatter.
    out.table([(e["name"], "v" + out.plain(e["version"]),
                " ".join(out.plain(e["description"] or "").split()))
               for e in entries],
              whole=(0,))  # the NAME the hint's `--name NAME` takes
    raise BoostError("multiple skills found — pick one or import all",
                    hint="add `--name NAME` or `--all`")


# ── pin / unpin ──────────────────────────────────────────────────────────

def cmd_pin(argv: list[str]) -> int:
    ap = cliparse.parser(prog="boost pin",
                                 description="Pin a skill, rule or workflow to its current version")
    ap.add_argument("name", type=util.nonempty_str, metavar="NAME",
                    help="installed skill, rule or workflow")
    ap.add_argument("--commit", action="store_true",
                    help="also freeze the exact source commit (integrity pin)")
    _add_pin_scope(ap, "pin")
    args = ap.parse_args(argv)
    args.name = store.installed_name(args.name, args.scope)
    row = _pin_target(args.name, args.scope, "pin", commit=args.commit)
    if args.commit and row is not None:
        # `verify` never grades a project row's commit pin, so writing one
        # would promise a check that does not exist.
        raise BoostError("%s is installed at project scope — --commit applies "
                         "to user-scope installs" % args.name,
                         # --local: unscoped is refused when a user copy
                         # shares the name, so the bare form could not run.
                         hint="`boost pin %s --local` holds it at its version"
                              % args.name)
    if row is not None:
        return _set_project_pin(row, True)
    rc = _set_pin(args.name, True)
    # Read after the pin: `set_commit_pin` takes the commit from this row.
    found = lockfile.find_any(args.name)
    if rc == 0 and args.commit and found is not None:
        kind, entry = found
        commit = integrity.set_commit_pin(args.name, entry, kind=kind)
        journal.log("pin-commit", args.name, commit=commit)
        out.ok("commit-pinned %s at %s" % (args.name, commit[:12]))
        out.dim("  `boost verify` fails if the recorded commit ever moves off it", wrap=True)
    return rc


def cmd_unpin(argv: list[str]) -> int:
    ap = cliparse.parser(prog="boost unpin",
                                 description="Allow a pinned skill, rule or workflow to update again")
    ap.add_argument("name", type=util.nonempty_str, metavar="NAME",
                    help="pinned skill, rule or workflow")
    _add_pin_scope(ap, "unpin")
    args = ap.parse_args(argv)
    # Releasing the version pin releases the commit pin with it — a commit pin
    # only makes sense while the skill is otherwise frozen. The commit pin is
    # cleared before `_set_pin` so it takes effect either way, but the dim
    # trailer prints after — it qualifies `_set_pin`'s own "unpinned" line, so
    # printing it first would leave the trailer describing a line that has
    # not appeared yet (mirrors `cmd_pin`'s ok-line-then-trailer order).
    args.name = store.installed_name(args.name, args.scope)
    row = _pin_target(args.name, args.scope, "unpin")
    if row is not None:
        return _set_project_pin(row, False)
    found = lockfile.find_any(args.name)
    cleared_commit_pin = bool(
        found and integrity.clear_commit_pin(args.name, found[1], kind=found[0]))
    rc = _set_pin(args.name, False)
    if cleared_commit_pin:
        out.dim("  released the commit pin too", wrap=True)
    return rc


def _add_pin_scope(ap, verb: str) -> None:
    """``pin``/``unpin``'s ``--scope``/``--local``/``--global``, as install's."""
    cliparse.add_scope_flags(
        ap, scope_help="%s the copy in your user config or in this repo "
                       "(needed when both hold the name)" % verb,
        local_help="the copy installed in this repo (= --scope project)",
        global_help="the copy in your user config (= --scope user)")


def _pin_target(name: str, scope: str | None, verb: str,
                commit: bool = False) -> integrity.InstalledSkill | None:
    """The project row ``pin``/``unpin`` acts on, or None for the user lock.

    Unscoped, a name only this repo holds is the project row, as before. A
    name both scopes hold is refused: acting on the user row alone pinned it
    while `boost update` moved the repo's copy, with nothing said about it.
    ``commit`` is ``pin --commit``, which the hint must keep: dropped, the
    suggested command set a version pin and no commit pin. It offers no
    ``--local`` form then, because ``--commit`` is refused at project scope.
    """
    base, project = integrity.project_skills()
    prow = project.get(name)
    if scope == scopes.SCOPE_PROJECT:
        if base is None:
            raise BoostError("not in a project — --local %ss what this repo "
                             "has installed" % verb,
                             hint="cd into the repo, or drop --local")
        if prow is None:
            raise BoostError("%s is not installed in this repo" % name,
                             hint="see what is with `boost list`")
        return integrity.InstalledSkill(
            name, prow, scopes.SCOPE_PROJECT, base, None)
    if scope == scopes.SCOPE_USER:
        if lockfile.find_any(name) is None:
            raise BoostError("%s is not installed in your user config" % name,
                             hint="see what is with `boost list`")
        return None
    if prow is None:
        return None
    if lockfile.find_any(name) is not None:
        raise BoostError("%s is installed in your user config and in this "
                         "repo — say which to %s" % (name, verb),
                         hint=("`boost %s %s --commit --global` — --commit "
                               "applies to user-scope installs" % (verb, name)
                               if commit else
                               "`boost %s %s --global` or `boost %s %s --local`"
                               % (verb, name, verb, name)))
    return integrity.InstalledSkill(name, prow, scopes.SCOPE_PROJECT, base, None)


def _project_row(name: str) -> integrity.InstalledSkill | None:
    """The current project's skill row for ``name`` — None if it is not one."""
    row = integrity.resolve_skill(name)
    return row if row is not None and row.is_project else None


def _set_project_pin(row: integrity.InstalledSkill, pinned: bool) -> int:
    """:func:`_set_pin` for a skill only the current project's lock holds.

    The flag goes into ``<repo>/.boost/skill-lock.json``, the row
    ``_update_skill`` reads its ``pinned`` from for a project skill.
    """
    label = "%s (project)" % row.name
    version = out.plain(row.entry.get("version", "0.0.0"))
    if bool(row.entry.get("pinned")) == pinned:
        out.info("%s is already %s" % (label, "pinned at v%s" % version
                                       if pinned else "unpinned"))
        return 0
    store.set_project_pin(row.base, row.name, pinned)
    journal.log("pin" if pinned else "unpin", row.name,
                scope=scopes.SCOPE_PROJECT)
    if pinned:
        out.ok("pinned %s at v%s — `boost update` will skip it" % (label, version))
    else:
        out.ok("unpinned %s (v%s) — updates apply again" % (label, version))
    return 0


def _set_pin(name: str, pinned: bool) -> int:
    # All three kinds pin: the flag is persisted on any lock entry and the
    # update loops (skills at cmd_update, rules/workflows at
    # _update_materialized) each honour it. A skill installed `--local` lives
    # in the project lock instead, which the same update loop also reads.
    # A project row never reaches here: `_pin_target` routes it first.
    found = lockfile.find_any(name)
    if not found:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    kind, entry = found
    for other in _shadowed_kinds(name, kind):
        out.warn("a %s named %s is also installed — this pins the %s only"
                 % (other, name, kind))
    label = name if kind == "skill" else "%s %s" % (kind, name)
    version = out.plain(entry.get("version", "0.0.0"))
    if bool(entry.get("pinned")) == pinned:
        out.info("%s is already %s" % (label, "pinned at v%s" % version
                                       if pinned else "unpinned"))
        return 0
    # Flip the flag on the row as it is under the lock: writing back `entry`
    # reverted any tag or reinstall that landed since it was read.
    def flip(row: dict) -> None:
        row["pinned"] = pinned
    if not lockfile.update_entry(kind, name, flip):
        raise BoostError("%s was uninstalled while %s it"
                         % (label, "pinning" if pinned else "unpinning"),
                         hint="see what is with `boost list`")
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
    ap.add_argument("action", choices=("save", "list", "restore"),
                    help="save the current environment, list snapshots, or "
                         "restore one")
    ap.add_argument("arg", type=util.nonempty_str, nargs="?", metavar="LABEL|ID",
                    help="label for save, snapshot id for restore")
    ap.add_argument("--json", action="store_true",
                    help="machine-readable output (list)")
    ap.add_argument("-y", "--yes", action="store_true",
                    help="skip the restore confirmation prompt")
    args = ap.parse_args(argv)
    if args.action == "list" and args.arg:
        ap.error("snapshot list takes no LABEL|ID")
    if args.json and args.action != "list":
        ap.error("--json is only supported with `snapshot list`")
    if args.action == "save":
        return _snapshot_save(args.arg)
    if args.action == "list":
        return _snapshot_list(args.json)
    if not args.arg:
        ap.error("restore needs a snapshot id",
                 hint="see `boost snapshot list`")
    return _snapshot_restore(args.arg, args.yes)


def _snapshot_save(label: str | None) -> int:
    paths.ensure_dirs()
    base = "snap-" + datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    snap_id, serial = base, 1
    while (paths.snapshots_dir() / (snap_id + ".tar.gz")).exists():
        serial += 1
        snap_id = "%s-%d" % (base, serial)
    tar_path = paths.snapshots_dir() / (snap_id + ".tar.gz")
    # With the held copies: their lock rows are in the store, they are not.
    arch = snapshot.archive(paths.store_dir(), tar_path, store.held_copies())
    skill_count = len(lockfile.installed())
    # The home the lock's rule/workflow paths are under, so a restore on
    # another machine can move them onto its own (lockfile.rehome).
    manifest = {"id": snap_id, "label": label or "", "created": util.now_iso(),
                "skills": skill_count, "home": str(paths.home())}
    (paths.snapshots_dir() / (snap_id + ".json")).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    journal.log("snapshot", snap_id, label=label)
    out.ok("saved %s (%s, %s)" % (snap_id, _plural(skill_count, "skill"),
                                  util.human_size(tar_path.stat().st_size)))
    others = _others_installed()
    if others:
        # The lock entry for these IS in the archive (the lock file is a
        # child of store_dir()) -- what's not captured is the materialized
        # file (CLAUDE.md block, rendered command) that lives outside the
        # store, so a restore can only bring one back by re-materializing it
        # from its tap, not by extracting it from this archive.
        out.warn("%s tracked but not archived here — their CLAUDE.md/command "
                "files live outside the skill store" % others)
    if arch.dereferenced:
        out.warn("archived the contents of symlinked %s — a restore brings "
                 "%s back as a copy, not a link"
                 % (", ".join(arch.dereferenced),
                    "it" if len(arch.dereferenced) == 1 else "them"), wrap=True)
    if arch.skipped:
        out.warn("skipped dangling symlink%s %s" % (
            "" if len(arch.skipped) == 1 else "s", ", ".join(arch.skipped)),
                 wrap=True)
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
        # `skills` is a count when the sidecar has one, `None` when it does
        # not — never the placeholder string "?" a JSON consumer of a numeric
        # field would have to special-case.
        snaps.append({"id": snap_id, "created": meta.get("created", ""),
                      "label": meta.get("label", ""),
                      "skills": meta.get("skills"),
                      "size": tar_path.stat().st_size})
    if as_json:
        print(json.dumps(snaps, indent=2))
        return 0
    if not snaps:
        print(out.empty_state("no snapshots yet",
                              hint="create one with `boost snapshot save`",
                              wrap=True))
        return 0
    out.table([(s["id"], util.rel_time(s["created"]) if s["created"] else "?",
                s["label"] or "—",
                s["skills"] if s["skills"] is not None else "?",
                util.human_size(s["size"]))
               for s in snaps],
              headers=("ID", "WHEN", "LABEL", "SKILLS", "SIZE"),
              # The id is the only argument `snapshot restore` accepts, and
              # every id shares a prefix — clipped, they all render as the
              # same unusable stub.
              keep=("ID",))
    return 0


def _snapshot_restore(snap_id: str, yes: bool = False) -> int:
    if not snap_id.startswith("snap-"):
        snap_id = "snap-" + snap_id
    tar_path = paths.snapshots_dir() / (snap_id + ".tar.gz")
    if not tar_path.exists():
        raise BoostError("no snapshot %s" % snap_id,
                        hint="see `boost snapshot list`")
    root = paths.store_dir()
    if not (yes or out.confirm("Restore %s? This replaces the skills in %s"
                               % (snap_id, _tilde(root)))):
        out.info("cancelled")
        return 1
    paths.ensure_dirs()
    # Rules/workflows installed after this snapshot was saved: their lock
    # entries live in the same file the archive is about to replace, but
    # their materializations (CLAUDE.md blocks, rendered commands) are
    # outside the store and untouched by a restore. Capture them before the
    # store is emptied so they can be added back — see
    # store.restore_preserve_newer_lock_sections.
    pre_rules = lockfile.installed_rules().copy()
    pre_workflows = lockfile.installed_workflows().copy()
    pre_rows = lockfile.installed().copy()
    pre_skills = set(pre_rows)
    # Whatever in the store is not a recorded skill — the lock's .corrupt
    # backups, a hand-made dir, a workflow's copy — is carried across the
    # swap; one the archive also holds goes to a named backup, not the bin.
    # A live workflow's copy stays live, as its lock row does.
    carry, set_aside = store.restore_carry_names(pre_rows)
    keep_live = store.workflow_owned_store_names()
    backup_dir = (paths.state_dir() / "restore-kept"
                  / ("%s-%s" % (snap_id,
                                datetime.now(UTC).strftime("%Y%m%d-%H%M%S"))))
    # Extracted into a staging dir and swapped in only once that succeeded,
    # so a corrupt or refused snapshot can never leave an emptied store.
    # The live lock goes into lock history first, as every other lock
    # change's does, so `boost replay rollback` can undo the restore.
    res = snapshot.restore(tar_path, root, snap_id, paths.held_skills_dir(),
                           rehome=store.snapshot_rehomer(snap_id, tar_path),
                           before_swap=lockfile.record_history,
                           carry=carry, keep_live=keep_live,
                           set_aside=set_aside, backup_dir=backup_dir)
    kept = store.restore_preserve_newer_lock_sections(pre_rules, pre_workflows)
    if res.carried:
        out.info("kept %s the snapshot does not cover: %s"
                 % (_plural(len(res.carried), "store item"),
                    ", ".join(res.carried)), wrap=True)
    if res.backed_up:
        out.warn("moved %s the live lock did not record as installed to %s: %s"
                 % (_plural(len(res.backed_up), "store item"),
                    _tilde(backup_dir),
                    ", ".join(p.name for p in res.backed_up)), wrap=True)
    # A snapshot saved before held copies were archived: no copy to hold, so
    # the restore's sync below reinstalls them instead.
    lost = store.unhold_lost_copies()
    if lost:
        out.warn("this snapshot has no copy of sidelined %s — reinstalling "
                 "from %s tap" % (", ".join(lost),
                                  "its" if len(lost) == 1 else "their"),
                 wrap=True)
    # Before anything links: a skill blocklisted since the snapshot was saved
    # is declined here, as `replay rollback` and `install` decline it.
    declined = store.decline_restored_by_policy(pre_skills)
    for line in declined:
        out.warn(line, wrap=True)
    actions = store.sync_apply(store.sync_plan())
    for action in actions:
        out.ok(action)
    journal.log("snapshot-restore", snap_id)
    out.ok("restored %s (%s)" % (snap_id,
                                 _plural(len(lockfile.installed()), "skill")))
    rematerialized = sum(1 for a in actions if a.startswith("re-materialized "))
    kept_n = len(kept["rules"]) + len(kept["workflows"])
    others = _others_installed()
    if others:
        msg = "%s untouched — snapshots cover the skill store only" % others
        extra = []
        if kept_n:
            extra.append("%s installed after this snapshot kept as-is"
                         % _plural(kept_n, "entry"))
        if kept["live"]:
            extra.append("%s kept at the installed version, not the "
                         "snapshot's" % _plural(len(kept["live"]), "entry"))
        if rematerialized:
            extra.append("%s re-materialized from its tap"
                         % _plural(rematerialized, "entry"))
        if extra:
            msg += " (%s)" % "; ".join(extra)
        out.warn(msg)
    # Partial on purpose, and said so in the exit code: a declined skill is
    # what `replay rollback` and `install` fail on too.
    return 1 if declined else 0


# ── export ───────────────────────────────────────────────────────────────

def cmd_export(argv: list[str]) -> int:
    ap = cliparse.parser(
        prog="boost export",
        description="Package skills as shareable zip/tar archives")
    ap.add_argument("names", type=util.nonempty_str, nargs="*", metavar="NAME",
                    help="skills to export (default: all installed)")
    ap.add_argument("-o", "--output", "--out", type=util.nonempty_str, dest="out", metavar="OUT",
                    help="output archive path")
    ap.add_argument("--zip", action="store_true",
                    help="build a .zip instead of .tar.gz")
    ap.add_argument("--force", action="store_true",
                    help="overwrite OUT if it already exists")
    args = ap.parse_args(argv)
    installed = lockfile.installed()
    # Project-scope skills live in the repo's own lock, not the user one —
    # the same walk `boost list` makes, so export packages what list shows.
    pbase, project = store.project_skills()
    names = args.names or sorted(set(installed) | set(project))
    if not names:
        others = _others_installed()
        raise BoostError("no skills installed to export",
                        hint=("%s installed, but export packages skills only"
                              % others) if others
                             else "install some with `boost install`")
    chosen: dict[str, dict] = {}            # user-scope rows
    chosen_project: dict[str, dict] = {}    # project-scope rows
    sources: dict[str, Path] = {}           # name -> directory to package
    for raw in names:
        # `raw` may be tap-qualified (`owner/repo:skill`); resolve to the
        # bare name the lock and the store key on, honoring the qualifier
        # against the installed tap rather than rejecting it outright.
        name, kind, entry = store.resolve_lock_entry(raw)
        qualifier, _, bare = raw.rpartition(":")
        pentry = project.get(bare)
        if pentry and qualifier and not catalog.tap_matches(
                str(pentry.get("tap") or ""), qualifier):
            pentry = None
        if entry is None and pentry is not None:
            pdir = integrity.project_skill_dir(pentry, pbase)
            if pdir is None:
                raise BoostError(
                    "project copy of %s is missing" % bare,
                    hint="repair with `boost install --local %s --force`" % bare)
            chosen_project[bare] = pentry
            sources[bare] = pdir
            continue
        if entry is None:
            raise BoostError("%s is not installed" % raw,
                            hint="see what is with `boost list`")
        if kind != "skill":
            # Same truth _iter_installed tells: it exists, as another kind
            # — a rule/workflow has no store directory to package.
            raise BoostError("%s is a %s — `boost export` applies to skills"
                            % (name, kind),
                            hint="rules and workflows materialize into "
                                 "agent config files; reinstall them "
                                 "from their tap")
        if not store.skill_store_dir(name).is_dir():
            raise BoostError(
                "store dir for %s is missing" % name,
                hint=("repair with `boost reinstall %s`" % name)
                     if entry.get("tap") == "local"
                     else "repair with `boost sync`")
        if pentry is not None:
            # One archive member per name: the user-scope copy is the one
            # packaged, and the user is told the project one was not.
            out.warn("%s is installed at both scopes — exported the user-scope "
                     "copy" % name)
        chosen[name] = entry
        sources[name] = store.skill_store_dir(name)
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    use_zip, format_warning = archive.resolve_export_format(args.out, args.zip)
    if format_warning:
        out.warn(format_warning)
    ext = ".zip" if use_zip else ".tar.gz"
    dest = util.check_path_length(
        paths.expand(args.out) if args.out else Path(
            "boost-skills-%s%s" % (stamp, ext)), what="-o path")
    if dest.exists() and not args.force:
        raise BoostError("%s already exists" % _tilde(dest),
                        hint="pass --force to overwrite, or choose a "
                             "different -o path")
    manifest = _boostfile_text(chosen, via="boost export",
                               project=chosen_project)
    try:
        if use_zip:
            with zipfile.ZipFile(str(dest), "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(archive.boostfile_zipinfo(
                    datetime.now(UTC).timetuple()[:6]), manifest)
                for name, sdir in sources.items():
                    for f in sorted(p for p in sdir.rglob("*") if p.is_file()):
                        zf.write(str(f), arcname="%s/%s" % (name, f.relative_to(sdir).as_posix()))
        else:
            with tarfile.open(str(dest), "w:gz") as tf:
                data = manifest.encode()
                ti = tarfile.TarInfo("Boostfile")
                ti.size = len(data)
                ti.mtime = int(datetime.now(UTC).timestamp())
                ti.mode = 0o644
                tf.addfile(archive.normalize_tar_member(ti), io.BytesIO(data))
                for name, sdir in sources.items():
                    tf.add(str(sdir), arcname=name,
                          filter=archive.normalize_tar_member)
    except OSError as e:
        raise BoostError("cannot write %s: %s" % (_tilde(dest), e.strerror or e),
                        hint="check the output path exists and is writable") from e
    out.ok("exported %s → %s (%s)" % (_plural(len(sources), "skill"),
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

    ``name`` may arrive tap-qualified (``owner/repo:skill``) — exactly what an
    ambiguity hint recommends typing. ``store.skill_store_dir`` rejects that
    string outright (":" is not a safe path component), so the store is
    probed only once ``store.resolve_lock_entry`` confirms the bare name is
    installed *from the named tap*; anything else falls through to
    ``catalog.resolve_one``, which already parses the qualified grammar.
    A skill installed ``--local`` resolves to its project copy
    (:func:`integrity.resolve_skill`).
    """
    # The installed copy either scope holds — a `--local` install's is in
    # the repo — and only then the tap's.
    bare = catalog.split_name(name)[1]
    row = integrity.resolve_skill(name)
    p = None
    if row is not None and row.dir is not None:
        candidate = row.dir / "SKILL.md"
        if candidate.exists():
            p = candidate
    from_store = p is not None
    if p is None:
        entry = catalog.resolve_one(name)   # raises BoostError if unknown
        tap = registry.get(entry["tap"])
        p = tap.path / entry["skill_md"]
        if not p.exists():
            raise BoostError("SKILL.md missing for %s" % bare,
                            hint="refresh the tap with `boost update`")
        # A stale cache may still name a SKILL.md linking out of the clone.
        store.refuse_escape(tap, p, bare)
    meta, body = frontmatter.parse(p.read_text(encoding="utf-8", errors="replace"))
    # Installed, the lock name is the one boost answers to: an import renamed
    # with `--name` may predate the frontmatter rewrite, and the adapt banner
    # (`boost adapt <display> …`) must name something this boost can find.
    display = (bare if from_store
               else str(meta.get("name") or bare).strip() or bare)
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
    ap.add_argument("name", type=util.nonempty_str, help="skill to adapt")
    ap.add_argument("--to", type=util.nonempty_str, metavar="FRAMEWORK", required=True,
                    help="target framework: %s" % ", ".join(adapters.formats()))
    ap.add_argument("--model", type=util.nonempty_str, metavar="M", default=None,
                    help="LLM the exported agent runs on (default: boost's "
                         "ai.model; pass 'none' for the framework's own default)")
    ap.add_argument("-o", "--output", "--out", type=util.nonempty_str, dest="out", metavar="FILE",
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
    # single-Agent render. Subagent discovery only applies to a SKILL.md-rooted
    # skill: a flat `agents/<name>.md` workflow's "directory" is the registry's
    # shared agents/ folder, and every sibling workflow living in it is not a
    # subagent of this one.
    subagents = (adapters.discover_subagents(skill_md.parent, own_file=skill_md)
                 if skill_md.name == "SKILL.md" else [])
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
