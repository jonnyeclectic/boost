# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""AI agent targets: where installed skills get symlinked."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from ..errors import BoostError
from . import config, output, paths, typedvalue, util

DISPLAY = {"claude-code": "Claude Code", "windsurf": "Windsurf",
           "cursor": "Cursor", "gemini": "Gemini CLI",
           "antigravity": "Antigravity CLI", "codex": "Codex"}


# Rows already warned about in this process: known_agents runs dozens of
# times per command, and one warning per row is the message.
_WARNED_DIRLESS: set[str] = set()
# ``agents.<name>.<flag>`` keys already warned about, for the same reason.
_WARNED_FLAGS: set[str] = set()

#: The boolean settings of an agent row, with the default each falls back to.
#: Read through :func:`_flag`, never ``bool()``: ``config.json``'s ``agents``
#: section is the one open section users edit by hand, and ``bool("false")``
#: is True — a hand-written ``"enabled": "false"`` linked the agent anyway,
#: and ``"links_skills": "false"`` gave Gemini the duplicate links the flag
#: exists to prevent while doctor said healthy.
FLAG_DEFAULTS: dict[str, bool] = {
    "enabled": True, "links_skills": True, "project_scope": True,
    "skills_only": False, "workflows": True, "dedupes_by_path": False,
}


#: Keys :func:`known_agents` adds that no one sets: worked out from the
#: filesystem, so ``config set`` must not offer them (:data:`config.AGENT_KEYS`).
DERIVED_KEYS = ("store_alias",)


def _read_flag(name: str, key: str, value: Any) -> bool:
    """``value`` read as a boolean, or raise :class:`typedvalue.ValueTypeError`.

    The vocabulary is ``config set``'s (:func:`typedvalue.adapt`): a real
    JSON boolean as-is, and a string such as ``"false"``/``"no"``/``"0"`` read
    as what it says. A JSON ``0``/``1`` is read as its digit.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    return typedvalue.adapt("agents.%s.%s" % (name, key), value,
                            typedvalue.BOOL)


def flag_default(name: str, key: str) -> bool:
    """What ``agents.<name>.<key>`` means when it is left out: the agent's own
    :data:`config.DEFAULTS` row first (gemini's ``links_skills`` is False),
    then :data:`FLAG_DEFAULTS`."""
    defaults: dict[str, dict] = config.DEFAULTS["agents"]  # type: ignore[assignment]
    row = defaults.get(name)
    if isinstance(row, dict) and isinstance(row.get(key), bool):
        return row[key]
    return FLAG_DEFAULTS[key]


def _flag(name: str, spec: dict, key: str) -> bool:
    """One boolean setting of an agent row; junk warns once and reads as
    :func:`flag_default` — what the row would mean with the key left out."""
    if key not in spec:
        return FLAG_DEFAULTS[key]
    default = flag_default(name, key)
    try:
        return _read_flag(name, key, spec[key])
    except typedvalue.ValueTypeError as e:
        dotted = "agents.%s.%s" % (name, key)
        if dotted not in _WARNED_FLAGS:
            _WARNED_FLAGS.add(dotted)
            output.warn("%s — boost reads it as %s; fix it with `boost config "
                        "set %s <true|false>`"
                        % (e, str(default).lower(), dotted),
                        stream=sys.stderr, wrap=True)
        return default


def bad_flags(claim: bool = False) -> list[tuple[str, str, Any]]:
    """``(agent, key, stored value)`` for every agent flag that is not a
    boolean, in ``config.json`` order.

    :func:`known_agents` reads each as its default, with a warning. ``claim``
    is :func:`dirless`'s: a caller that reports them itself (``boost doctor``)
    takes the warning over.
    """
    found = []
    for name, spec in (config.get("agents") or {}).items():
        if not isinstance(spec, dict):
            continue
        for key in FLAG_DEFAULTS:
            if key not in spec:
                continue
            try:
                _read_flag(name, key, spec[key])
            except typedvalue.ValueTypeError:
                found.append((name, key, spec[key]))
    if claim:
        _WARNED_FLAGS.update("agents.%s.%s" % (n, k) for n, k, _v in found)
    return found


def aliases_store(adir: Path) -> bool:
    """True when ``adir`` *is* the canonical store, through a symlink or not.

    ``~/.cursor/skills -> ~/.agents/skills`` already shows that agent every
    installed skill. Treated as a linking agent, every entry in its dir was a
    real directory "not managed by boost", so install, doctor, sync and heal
    each told the user to move or delete it — and each of those paths was the
    store's only copy of the skill. Resolves **both** sides (a macOS ``$HOME``
    under ``/var`` resolves to ``/private/var``), then asks by inode, which is
    what catches a case-insensitive volume spelling the store differently.
    Fails closed: a dir ``resolve()`` refuses is not the store.
    """
    try:
        mine = adir.resolve()
        store = paths.store_dir().resolve()
    except (OSError, RuntimeError):
        return False
    if mine == store:
        return True
    try:
        return os.path.samefile(mine, store)
    except OSError:
        return False


class RelativeAgentDir(BoostError):
    """An agent ``dir`` that expands to a relative path."""


def _row_dir(spec: dict) -> Path | None:
    """The agent row's expanded ``dir``, or None when it names no directory.

    ``Path("")`` is ``.``: a row with no ``dir`` (a mistyped
    ``agents.curosr.enabled``, or an agent enabled before its dir was set)
    used to resolve to the working directory, so `boost install` symlinked the
    skill into whatever directory it ran from and called that agent linked.
    Raises what :func:`paths.expand` raises for an unset ``${VAR}``, and
    :class:`RelativeAgentDir` for a dir that is not absolute once expanded: a
    relative one resolved against the working directory, so each directory
    boost ran from got its own copy of that agent's skills tree. A relative
    dir is refused, not read against ``$HOME``, because ``config set``
    refuses it too (:func:`check_dir`) and a guessed base is a second meaning
    for the same text.
    """
    raw = str(spec.get("dir") or "").strip()
    if not raw:
        return None
    p = paths.expand(raw)
    if p == Path():
        return None
    if not p.is_absolute():
        raise RelativeAgentDir(
            "%r is a relative path, which would resolve against whatever "
            "directory boost runs from" % raw,
            hint="use an absolute path, or one starting with ~ or ${VAR}")
    return p


def check_dir(raw: Any) -> str | None:
    """Why ``raw`` cannot be an agent's ``dir``, or None when it can.

    ``config set agents.<name>.dir`` asks this before saving. Only the
    relative case is refused here: an unset ``${VAR}`` may be set by the time
    boost reads it, and doctor names it if not.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        _row_dir({"dir": raw})
    except RelativeAgentDir:
        return ("an absolute path, or one starting with ~ or ${VAR} — a "
                "relative dir resolves against the working directory")
    except BoostError:
        return None
    return None


def dirless(claim: bool = False) -> list[str]:
    """Configured agents whose row names no directory, in ``config.json`` order.

    :func:`known_agents` leaves these out, with a warning, rather than resolve
    them to the cwd. ``claim`` is for a caller that reports them itself
    (``boost doctor``), so the warning is not printed beside its own line.
    """
    names = []
    for name, spec in (config.get("agents") or {}).items():
        try:
            if _row_dir(spec) is None:
                names.append(name)
        except BoostError:
            continue  # an unresolvable dir is check()'s to report
    if claim:
        _WARNED_DIRLESS.update(names)
    return names


def known_agents() -> dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool, "links_skills": bool}} per agent.

    A row with no ``dir`` is skipped, with a warning (:func:`_row_dir`). A
    row whose dir is the canonical store (:func:`aliases_store`) is read as a
    native-store agent — ``links_skills`` False, ``store_alias`` True — so
    nothing links into it, unlinks from it, or sweeps it.
    """
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        try:
            adir = _row_dir(spec)
        except RelativeAgentDir as e:
            # check() keys the error by name for doctor; a command that stops
            # here has only this line, so it names the key to edit.
            raise BoostError("agents.%s.dir: %s" % (name, e.message),
                             hint=e.hint) from e
        if adir is None:
            if name not in _WARNED_DIRLESS:
                _WARNED_DIRLESS.add(name)
                output.warn("agents.%s has no dir, so boost skips it — set one "
                            "with `boost config set agents.%s.dir <dir>`, or "
                            "remove the row with `boost config unset agents.%s`"
                            % (name, name, name), stream=sys.stderr, wrap=True)
            continue
        alias = aliases_store(adir)
        out[name] = {
            "dir": adir,
            "enabled": _flag(name, spec, "enabled"),
            # Defaults True: an agent only reads the canonical store if it
            # implements the Agent Skills standard's `~/.agents/skills` path,
            # which most do not, so the symlink is the safe assumption.
            "links_skills": (_flag(name, spec, "links_skills")
                             and not alias),
            # The dir resolves to the canonical store: the agent reads every
            # installed skill already. See :func:`aliases_store`.
            "store_alias": alias,
            # Defaults True: nearly every agent reads a repo-local copy of its
            # own dotdir, so a project install lands in `<repo>/.claude/skills`
            # and its siblings. False marks an agent whose project layout boost
            # does not know — see :func:`project_agents`.
            "project_scope": _flag(name, spec, "project_scope"),
            # Defaults False: most agents take all three kinds. True marks an
            # agent where only the skills surface is known — see
            # :func:`materializing_agents`.
            "skills_only": _flag(name, spec, "skills_only"),
            # Defaults True. False marks an agent whose *rules* surface is
            # verified but whose slash-command format is not, so it takes rules
            # and skills but no workflows — a finer cut than `skills_only`,
            # which turns both off. See :func:`workflow_agents`.
            "workflows": _flag(name, spec, "workflows"),
            # Defaults False: assume an agent shown the same skill through two
            # of its discovery tiers will complain about it, because Gemini CLI
            # does. True marks one that collapses them instead — see
            # :func:`dedupes_by_path`.
            "dedupes_by_path": _flag(name, spec, "dedupes_by_path"),
            # Defaults "": derive the repo-local dotdir from the user dir, as
            # every agent with a fixed path can. A non-empty value declares it
            # — see :func:`project_dotdir`.
            "project_dir": str(spec.get("project_dir", "")),
        }
    return out


def check() -> list[tuple[str, BoostError]]:
    """Every configured agent whose ``dir`` cannot be resolved, with the error.

    :func:`known_agents` raises on the first such row, which is right for the
    commands that would write somewhere: :func:`paths.expand` refuses an unset
    ``${VAR}`` precisely so a mistyped dir cannot install into ``./skills``.
    It is wrong for ``boost doctor``, whose job is to name a broken config —
    one bad row made it exit 1 having printed nothing past the lock check. So
    this asks the same question row by row, without raising, and keys each
    failure by agent name: the error from ``expand`` names the variable, not
    the ``agents.<name>.dir`` key the user has to edit. ``config.json`` order,
    so two runs list them the same way.
    """
    bad = []
    for name, spec in (config.get("agents") or {}).items():
        try:
            _row_dir(spec)
        except BoostError as e:
            bad.append((name, e))
    return bad


def project_dotdir(agent: str, skills_dir) -> str:
    """The repo-local directory name `agent` uses under a project base.

    Normally derived: ``~/.claude/skills`` -> ``.claude``, so an agent someone
    added by hand in ``config.json`` lands in the project under the name it
    uses at home. That derivation assumes the user dir is a fixed path, and
    Codex's is not — its default is ``${CODEX_HOME:-~/.codex}/skills``. Under a
    relocated ``CODEX_HOME=/opt/codexhome`` the derivation yields ``codexhome``,
    so `boost install --local` would write ``<repo>/codexhome/skills/<name>``
    and report success. Codex's project skill root is the literal
    ``<project>/.codex/skills`` whatever ``CODEX_HOME`` says, so that copy is
    somewhere it never reads; and the *project* lock is a committed file, so
    the row records a repo-relative path that one machine's environment
    invented. The spec therefore declares the name, and this returns the
    declared one whenever there is one.

    A declared value is a path segment boost joins under the project base, and
    ``config.json`` is user-editable, so it is checked rather than trusted: one
    component, no separator, no ``.``/``..``. A value that fails goes back to
    the derived name instead of escaping the repo — `scopes.ensure_in_base`
    would catch an escape at install time, but as a crash at the end of a
    command rather than a name that makes sense, and the sweeps that walk
    project roots never reach that check at all.
    """
    declared = (known_agents().get(agent) or {}).get("project_dir") or ""
    if declared in ("", ".", "..") or "/" in declared or "\\" in declared:
        return Path(skills_dir).parent.name
    return declared


def enabled_agents() -> dict[str, Path]:
    """{name: dir Path} for just the agents whose "enabled" flag is true."""
    return {n: s["dir"] for n, s in known_agents().items() if s["enabled"]}


def linking_agents() -> dict[str, Path]:
    """The enabled agents that need a skill *symlinked* into their own dir.

    Most agents do: they only look inside their own config directory, so a
    skill is invisible until boost links it there. Gemini CLI and Codex are the
    exceptions — both discover ``~/.agents/skills`` directly, which is exactly
    :func:`paths.store_dir`. Linking for them would put the same skill in two of
    their discovery tiers, and since the ``.agents`` alias out-ranks
    ``.gemini/skills`` within Gemini's user tier, the copy boost linked could
    never win — it would only make Gemini log a "Skill conflict detected" line
    per skill, every session. Codex collapses the pair silently instead (see
    :func:`dedupes_by_path`), so there the cost is redundant work rather than
    noise; not linking is right either way.

    So this is the set to iterate for anything symlink-shaped that *writes*
    (link, coverage checks); unlink and the stale-link sweeps take the wider
    :func:`unlinking_agents`, which adds disabled agents and nothing else — including the sweep in
    :func:`store.sync_plan`, whose only ownership test is ``points_into_store``:
    over a native-store agent's skills dir it would delete links boost never
    created. What materializes *into* an agent's dotdir is a different set again
    (:func:`materializing_agents` for rules, :func:`workflow_agents` for
    workflows), because those have no canonical store to be read from.
    """
    return {n: s["dir"] for n, s in known_agents().items()
            if s["enabled"] and s["links_skills"]}


def unlinking_agents() -> dict[str, Path]:
    """Every agent that links skills, *enabled or not*: the set to remove from.

    :func:`linking_agents` is the set boost writes links into. Removal and the
    broken-link sweeps need the wider one, because disabling an agent stops
    new links without taking the old ones away: uninstalling a skill while
    cursor was disabled left ``~/.cursor/skills/<name>`` dangling into the
    deleted store dir, where Cursor still read it and doctor never looked.
    A native-store agent (``links_skills: false``) stays out, for the reason
    :func:`linking_agents` gives — boost never linked there.
    """
    return {n: s["dir"] for n, s in known_agents().items() if s["links_skills"]}


def link_dirs_path() -> Path:
    """Where boost records every skills dir it has linked into."""
    return paths.state_dir() / "link-dirs.json"


def remember_link_dir(agent: str, adir: Path) -> None:
    """Record that boost linked into ``adir`` for ``agent``.

    The lock records a skill's agents by name, and every removal walks each
    agent's *current* dir. Repoint ``agents.cursor.dir`` and the links made
    under the old one were reachable by nothing: uninstall reported cursor
    unlinked over a link left dangling in ``~/.cursor/skills``, and doctor,
    heal, sync and clean all looked only in the new dir. Best effort: a state
    dir that refuses the write costs only this record.
    """
    import json
    seen = _remembered_link_dirs()
    key = str(adir)
    if key in seen.get(agent, ()):
        return
    seen.setdefault(agent, []).append(key)
    try:
        f = link_dirs_path()
        f.parent.mkdir(parents=True, exist_ok=True)
        # Atomic: a torn file reads back as empty and the next write would
        # drop every dir recorded before it.
        util.atomic_write_text(
            f, json.dumps(seen, indent=2, sort_keys=True) + "\n")
    except OSError:
        return


def _remembered_link_dirs() -> dict[str, list[str]]:
    import json
    try:
        data = json.loads(link_dirs_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(a): [str(d) for d in ds if isinstance(d, str)]
            for a, ds in data.items() if isinstance(ds, list)}


def former_link_dirs() -> list[tuple[str, Path]]:
    """``(agent, dir)`` for skills dirs boost may have linked into before.

    The dirs :func:`remember_link_dir` recorded, and each linking agent's
    default dir from ``config.DEFAULTS`` (links made before the record
    existed), less every dir :func:`unlinking_agents` already walks. A dir
    that is now a native-store agent's is left out, for the reason
    :func:`linking_agents` gives: boost never links there, so what it holds
    belongs to someone else.

    A dir that resolves to the store itself (:func:`aliases_store`) is left
    out too: a sweep there walks the store.
    """
    known = known_agents()
    current = {str(d) for d in unlinking_agents().values()}
    native = {str(s["dir"]) for s in known.values() if not s["links_skills"]}
    found: dict[str, str] = {}
    defaults: dict[str, dict] = config.DEFAULTS["agents"]  # type: ignore[assignment]
    for agent, spec in defaults.items():
        if spec.get("links_skills", True) and spec.get("dir"):
            found.setdefault(str(paths.expand(spec["dir"])), agent)
    for agent, dirs in _remembered_link_dirs().items():
        for d in dirs:
            found.setdefault(d, agent)
    # A dir that is the store holds the store's own skills, never a link.
    return [(agent, Path(d)) for d, agent in found.items()
            if d not in current and d not in native
            and not aliases_store(Path(d))]


def remembered_native_dirs() -> list[tuple[str, Path]]:
    """``(agent, dir)`` for a native-store agent's dir boost once linked into.

    :func:`former_link_dirs` and :func:`unlinking_agents` leave native-store
    dirs out because boost never links there -- true of a dir boost never
    linked into, false of one :func:`remember_link_dir` recorded for that very
    agent before its ``links_skills`` was flipped off. The links made then
    stay: uninstall left ``~/.windsurf/skills/<name>`` dangling into the store
    dir it had just deleted, and doctor called that "0 broken links".

    Kept apart from :func:`sweep_dirs` on purpose. A native dir is where other
    tools link into the store too (:func:`store.duplicate_discovery`), so the
    readers of this list remove only a link to one named skill's store dir, or
    one that dangles into the store, never a live link named for no skill.
    """
    remembered = _remembered_link_dirs()
    return [(n, s["dir"]) for n, s in known_agents().items()
            if not s["links_skills"] and str(s["dir"]) in remembered.get(n, ())
            and not aliases_store(s["dir"])]


def materialization_target(kind: str, name: str, entry: dict,
                           m: dict) -> Path | None:
    """Where the agent's *current* dir puts row ``m`` of rule/workflow
    ``name``, or None when there is no such place to compare against.

    A row records the path it was written to, and the agent's dir can move
    after that (``agents.cursor.dir``). None for a row of an agent boost no
    longer writes (:func:`materialization_is_written` names those), a
    project-scope row, a workflow's store copy, a workflow row with no
    ``slot``, and a name the target functions refuse.
    """
    from . import rules, workflows
    agent = m.get("agent")
    # User scope only. A project row's place is the repo's own layout,
    # committed with it; repointing a dir under $HOME is no reason for sync
    # to rewrite files in someone's repo.
    if (not agent or entry.get("base") is not None
            or m.get("slot") == workflows.SLOT_SKILL):
        return None
    writes = workflow_agents() if kind == "workflow" else materializing_agents()
    skills_dir = writes.get(agent)
    if skills_dir is None:
        return None
    try:
        if kind == "workflow":
            if not m.get("slot"):
                return None
            return workflows.workflow_target(skills_dir, m["slot"], name,
                                             agent=agent)
        return rules.rule_target(agent, skills_dir, name)[1]
    except BoostError:
        return None


def relocated_to(kind: str, name: str, entry: dict, m: dict) -> Path | None:
    """The path row ``m`` now belongs at, when the agent's dir moved away
    from where it was written; None when it is where the agent reads.

    Every check that read the rows asked only whether the recorded file was
    there, and after a repointed ``agents.cursor.dir`` it was -- in the dir
    Cursor no longer reads. doctor called the rule fully materialized, verify
    said ok and sync moved nothing.
    """
    want = materialization_target(kind, name, entry, m)
    if want is None or not m.get("path"):
        return None
    have = os.path.normcase(os.path.normpath(str(m["path"])))
    if have == os.path.normcase(os.path.normpath(str(want))):
        return None
    # The same file by another spelling is not a move: a $HOME of /tmp/x
    # at install and /private/tmp/x now (macOS) named every row moved, and
    # sync then rewrote them all on every run.
    if (os.path.normcase(os.path.realpath(have))
            == os.path.normcase(os.path.realpath(str(want)))):
        return None
    return want


def sweep_dirs() -> list[Path]:
    """Every skills dir a broken-link sweep walks: each linking agent's
    current dir, enabled or not, then :func:`former_link_dirs`."""
    return [*unlinking_agents().values(),
            *(d for _agent, d in former_link_dirs())]


def project_agents() -> dict[str, Path]:
    """Enabled agents whose *project* layout boost actually knows.

    Project scope is derived from the agent's own dotdir
    (``scopes.agent_root``: ``<repo>/.claude/skills/…``), which holds for every
    agent whose skills dir is one level under a dotdir. Antigravity CLI's is
    two — ``~/.gemini/antigravity-cli/skills`` — so the derivation would create
    a dotless ``<repo>/antigravity-cli/`` that nothing reads, and boost would
    report a coverage it does not have. Its documented project location is
    inside ``~/.gemini/config/projects/``, which is not a repo-local directory
    at all; until that is verified against the CLI, the honest answer is to
    leave it out of project scope rather than invent a path for it.
    """
    return {n: s["dir"] for n, s in known_agents().items()
            if s["enabled"] and s["project_scope"]}


def agents_for_scope(base) -> dict[str, Path]:
    """Enabled agents for user scope (``base is None``) or project scope."""
    return enabled_agents() if base is None else project_agents()


def materializing_agents(base=None) -> dict[str, Path]:
    """Agents a *rule* or *workflow* may be written into.

    A skill is a directory boost symlinks; a rule and a workflow are files
    boost writes in a format the agent has to already read — a context file at
    a known path, or a slash command in a known dir and syntax. So this set is
    narrower than :func:`agents_for_scope`: an agent whose rule and workflow
    formats have not been verified is skills-only, and writing a plausible file
    into its config tree would claim a coverage that does not exist.

    Antigravity CLI is the current case. Its rules arrive anyway, through the
    ``gemini`` agent, which already writes the ``~/.gemini/GEMINI.md`` it reads.
    """
    return {n: d for n, d in agents_for_scope(base).items()
            if not known_agents()[n]["skills_only"]}


def workflow_agents(base=None) -> dict[str, Path]:
    """Agents a *workflow* may be written into: :func:`materializing_agents`
    minus those with no verified slash-command format.

    Rules and workflows are not one surface. An agent can document exactly
    where its standing instructions live and still have no user-installable
    command format at all, and `skills_only` cannot express that — it turns
    both off, which would under-claim a surface boost has verified.

    Codex CLI is the case. Its instructions file is `AGENTS.md`
    (:data:`rules.CONTEXT_FILES`), but 0.156.1 ships no `prompts/` or
    `commands/` directory, no command subcommand, and its plugin importer
    *rewrites* a Claude `commands/*.md` into a `SKILL.md` on disk rather than
    running it as a command. A Markdown file dropped in `~/.codex/commands/`
    would be installed, reported, and never loaded.

    Windsurf is the second: it documents workflows only under
    `.windsurf/workflows/` and `~/.codeium/windsurf/global_workflows/`, not
    the `commands/`/`agents/` slots boost writes (see :data:`config.DEFAULTS`).
    """
    return {n: d for n, d in materializing_agents(base).items()
            if known_agents()[n]["workflows"]}


def materialization_is_written(kind: str, base, agent) -> bool:
    """Whether boost still writes ``agent`` for a row of ``kind`` at ``base``.

    A rule or workflow records one materialization row per agent it was
    written into, and ``store._refused_materializations`` carries the
    untouched ones forward on purpose: a rule's row is what makes its managed
    context-file block removable later, since ``store._uninstall_rule`` is
    record-driven. Change that agent's config afterwards and the row is still
    there, still naming a file, and nothing will ever write it again --
    ``install`` writes only :func:`materializing_agents` for a rule and the
    narrower :func:`workflow_agents` for a workflow.

    Every check that reads those rows has to ask this first or it reports a
    fault whose remedy cannot run. It lives here rather than in ``store``
    because it is a question about the write sets and nothing else, so the
    readers that must not import ``store`` -- ``integrity`` among them -- can
    still ask it.

    A row from before rows carried an ``agent`` is answered ``True``: without
    the name there is nothing to test, and reporting a real gap is better than
    silently dropping one. ``base`` is the row's own scope, so a project rule
    is judged against :func:`project_agents` rather than the user-scope set.
    """
    if not agent:
        return True
    writes = (workflow_agents(base) if kind == "workflow"
              else materializing_agents(base))
    return agent in writes


#: The reasons :func:`materialization_skip_reason` can give, as constants so
#: a reader can branch on one without matching prose. They split three ways
#: below, and that split is what ``boost doctor`` words its remedy from -- so
#: it lives here beside the ladder that produces them rather than in the
#: command layer, where a new reason could be added and silently miss its
#: classification.
REASON_UNCONFIGURED = "is not configured"
REASON_SKILLS_ONLY = "takes skills only"
REASON_NO_COMMAND_FORMAT = "has no slash-command format"
REASON_DISABLED = "is disabled"
REASON_NO_PROJECT_SCOPE = "has no project scope"
REASON_UNKNOWN = "is not written"

#: The reasons a config edit reverses: flip the flag, run ``boost sync``, and
#: the row is written.
CONFIG_REASONS = (REASON_DISABLED, REASON_NO_PROJECT_SCOPE)

#: The reasons that also name a config flag and where flipping it is the
#: wrong move. :data:`config.DEFAULTS` says why for each: Antigravity's rule
#: and workflow formats are unverified, and Codex 0.156.1 has no
#: user-installable command format at all -- so ``skills_only: false`` or
#: ``workflows: true`` buys a file the agent silently never loads, which is
#: worse than the stale record it replaced.
WITHDRAWN_REASONS = (REASON_SKILLS_ONLY, REASON_NO_COMMAND_FORMAT)

#: Neither: ``REASON_UNCONFIGURED`` names an agent this boost has never heard
#: of, and ``REASON_UNKNOWN`` is the fallback for a refusal the ladder could
#: not word. Named so the three groups are a partition a test can check --
#: ``boost doctor`` words its remedy from the split, so a reason added to the
#: ladder and to none of these would be classified by silence.
UNREMEDIED_REASONS = (REASON_UNCONFIGURED, REASON_UNKNOWN)


def materialization_skip_reason(kind: str, base, agent) -> str | None:
    """Why :func:`materialization_is_written` refuses, or ``None`` if it does
    not -- a verb phrase to complete "the agent ...".

    Set membership stays the single authority; this only words the answer, and
    falls back to a generic phrase rather than contradicting it. Wording it
    from the agent's own flags matters because *disabled* is only one of the
    reasons: an agent can be enabled and still refuse a row for having no
    verified slash-command format (``codex``), no rule format at all
    (``skills_only``), or no project scope. Saying "disabled agent" for those
    sends the user to re-enable something that is already on.

    **Order is by remedy, not by flag.** More than one reason can hold at
    once, and the caller shows one, so the one shown has to be the one whose
    remedy is real. The two reasons in :data:`CONFIG_REASONS` are reversible
    and are therefore reported *last*: ``antigravity`` is both
    ``skills_only`` and ``project_scope: False``, so ordering scope first
    told a user with a project rule to give it project scope -- after which
    the row is still unwritten, with a new reason, because a skills-only
    agent takes no rule at any scope. The permanent reason is the true one.
    """
    if materialization_is_written(kind, base, agent):
        return None
    spec = known_agents().get(agent)
    if spec is None:
        return REASON_UNCONFIGURED
    if spec["skills_only"]:
        return REASON_SKILLS_ONLY
    if kind == "workflow" and not spec["workflows"]:
        return REASON_NO_COMMAND_FORMAT
    if not spec["enabled"]:
        return REASON_DISABLED
    if base is not None and not spec["project_scope"]:
        return REASON_NO_PROJECT_SCOPE
    return REASON_UNKNOWN


def dedupes_by_path() -> set[str]:
    """Agents that collapse two discovery entries resolving to the same file.

    The assumption everywhere else is Gemini CLI's behaviour: show it one skill
    through two tiers and it logs a "Skill conflict detected" line per skill per
    session, which is what :func:`store.duplicate_discovery` exists to warn
    about. Codex CLI de-duplicates by *resolved* path instead — a symlink in
    `~/.codex/skills` pointing at a store skill is listed exactly once, under
    the canonical path, with no warning (verified against 0.156.1 via
    `codex debug prompt-input` and the app-server's `skills/list`). Reporting
    that as an issue would be a false positive, so these agents are skipped.

    It is deliberately not a reason to start linking: see the `codex` entry in
    :data:`config.DEFAULTS`.
    """
    return {n for n, s in known_agents().items()
            if s["enabled"] and s["dedupes_by_path"]}


def native_store_agents() -> dict[str, Path]:
    """Enabled agents that read the canonical store without a symlink.

    The complement of :func:`linking_agents` within :func:`enabled_agents` —
    reported at install time so "linked → a · b · c" never reads as "and not
    the agent you actually use".
    """
    return {n: s["dir"] for n, s in known_agents().items()
            if s["enabled"] and not s["links_skills"]}


def display_name(agent: str) -> str:
    """`claude-code` -> "Claude Code"; unknown names pass through unchanged."""
    return DISPLAY.get(agent, agent)
