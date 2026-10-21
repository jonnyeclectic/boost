# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The canonical store (~/.agents/skills) and agent symlinks.

install():  copy skill dir from a tap clone -> store, symlink into every
            enabled agent dir, record in the lock file, log to the journal.
"""
from __future__ import annotations

import contextlib
import errno
import operator
import os
import shutil
import stat
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from ..errors import BoostError
from . import (
    agents,
    catalog,
    config,
    foreign,
    gitutil,
    journal,
    lockfile,
    paths,
    policy,
    projectlock,
    registry,
    scopes,
    util,
)


@dataclass
class InstallResult:
    """Outcome of one install: dest, linked agents, conflicts, kind."""
    name: str
    dest: Path
    linked: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    # Agent dirs the link, or a rule or workflow file, could not be written
    # into (a dir restored with the wrong owner, say). Kept apart from
    # `conflicts`: nothing is in the way, the directory itself refuses, and
    # the remedy is different.
    unwritable: list[str] = field(default_factory=list)
    # (agent dir, what blocks it) where something that is not a directory sits
    # at or above the agent's skills, rules or commands dir: a dangling
    # ``~/.claude/skills`` symlink, or a file at ``~/.cursor``. No mode change
    # clears that, so it is kept apart from `unwritable` and worded with
    # `link_refusal`.
    blocked: list[tuple[str, str]] = field(default_factory=list)
    # Agent dirs where the OS refused to make any symlink at all (Windows
    # without Developer Mode, a FAT or exFAT mount): no chmod or move clears
    # it, so it is worded apart, with :func:`symlink_refusal`.
    unlinkable: list[str] = field(default_factory=list)
    # The agents behind `unwritable`, `blocked` and `unlinkable` for a skill: the ones whose
    # dir refused the link. Recorded in the lock as ``refused_agents`` so a
    # later re-install retries them (:func:`preserved_agent_scope`).
    refused: list[str] = field(default_factory=list)
    # Agents that can already use this skill without a symlink because they read
    # the canonical store directly (agents.native_store_agents). Kept apart from
    # `linked` so the lock records only real links, while the install report can
    # still tell the user the skill reached them.
    native: list[str] = field(default_factory=list)
    # Plugins that already put this skill in front of Claude Code — the same
    # files, or a newer copy (:func:`serving_plugin`) — so no Claude Code link
    # was made.
    # Kept out of `refused`: nothing refused, and a refusal is retried by the
    # next reinstall, where this link is meant to stay absent.
    covered: list[str] = field(default_factory=list)
    # A workflow's or rules-dir rule's target paths that already held a file
    # boost did not write (no lock row records the path). Left alone, and recorded apart from the
    # materializations, in the entry's ``foreign``: see :func:`foreign_rows`.
    foreign: list[str] = field(default_factory=list)
    score: int = 0
    upgraded: bool = False
    kind: str = "skill"
    scope: str = "user"   # "user" or "project" — where a rule/workflow landed
    # For rules/workflows the installed content is a single file (or a merged
    # CLAUDE.md block), not a SKILL.md tree — carry the raw source so the caller
    # scans exactly what it installed instead of a non-existent SKILL.md.
    scan_text: str | None = None
    # MCP servers the skill declares (mcpdecl.servers_for rows). Detected here
    # but never acted on: core stays non-interactive, so the command layer owns
    # the offer to register them — same split as `conflicts` and `score`.
    mcp_servers: list[dict] = field(default_factory=list)
    # Names actually written to the project's .mcp.json — not what was
    # declared. The two differ when the file could not be written, and the
    # install report must show the former.
    mcp_recorded: list[str] = field(default_factory=list)
    # Why the project's .mcp.json was left untouched (it exists but does not
    # parse, its mcpServers is not an object, or the write failed), or None.
    mcp_error: str | None = None
    # The tap an import just replaced (`install_from_path` only). Importing over
    # a tapped skill rewrites its lock entry to `local` and so drops the only
    # thing `boost update` refreshes it from; the caller says so.
    replaced_tap: str | None = None
    # Agents still linked outside a declared `--agent` scope after the run
    # (`install_from_path` only). Narrowing links into fewer agents but never
    # removes a link — pruning stays `boost sync --prune`'s decision — so these
    # are exactly what the next `sync --diff` reports as out of scope.
    out_of_scope: list[str] = field(default_factory=list)
    # A workflow's copy in the canonical store (`_skill_copy`): where it was
    # written, or, when it was not, why — a name a skill already holds, a
    # source with no description. Core words the reason; the command prints
    # it.
    skill_copy: Path | None = None
    skill_note: str | None = None
    # Symlinks in the skill's source the copy left out (:func:`_copy_tree`):
    # one leading to nothing, or out of the tap. Core words each; the command
    # prints them.
    skipped_links: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RemoteSource:
    """A git URL `boost import` cloned, and the commit the clone checked out.

    The clone is a temporary directory removed as soon as the import returns,
    so its path is the one thing the lock must not record: `boost info` showed
    it and `boost reinstall` looked for it long after it was gone. The lock
    records this instead — the URL, the commit, and each skill's directory
    inside the repo, which is enough to clone it again.
    """

    url: str
    root: Path
    commit: str


def repo_path(remote: RemoteSource, skill_dir: Path) -> str:
    """``skill_dir`` relative to the clone, POSIX-style; ``.`` for the root.

    A module function, not a ``RemoteSource`` method, on purpose: the mutation
    gate splits this file per top-level function and refuses to split a module
    holding any class with a method (`scripts/mutation_shards.py`), which
    would put the whole of store.py back on the critical path.
    """
    return Path(skill_dir).relative_to(remote.root).as_posix()


@contextlib.contextmanager
def cloned_source(url: str) -> Iterator[RemoteSource]:
    """Clone ``url`` into a temporary directory for the length of the block.

    A full checkout, not a tap's Markdown cone: an import copies whatever the
    repo ships, assets included. The directory is removed on the way out
    whether or not the clone or the install inside the block succeeded.
    """
    tmp = Path(tempfile.mkdtemp(prefix="boost-import-"))
    try:
        root = tmp / "repo"
        gitutil.clone_shallow(url, root, sparse=False)
        yield RemoteSource(url=url, root=root, commit=gitutil.head_commit(root))
    finally:
        with contextlib.suppress(OSError):
            util.rmtree(tmp)


def is_url_import(entry: dict) -> bool:
    """Whether a lock entry is a `boost import` of a git URL.

    Only a fresh clone can restore one, and sync never touches the network, so
    its repair is `boost reinstall` where every other skill's is `boost heal`.
    ``sync``/``heal`` and ``doctor`` both ask here, so they name the same one.
    """
    return entry.get("tap") == "local" and bool(entry.get("source_url"))


def local_source_dir(entry: dict) -> Path | None:
    """The directory a local import can be read again from, else None.

    None for a URL import: its ``source_dir`` is a path inside the repo, and
    read as a local path it would resolve against whatever directory boost
    happens to run in. None for an empty one too, which ``Path`` turns into
    the cwd. Otherwise the recorded directory, if it still holds a SKILL.md.
    """
    raw = str(entry.get("source_dir") or "")
    if not raw or entry.get("source_url"):
        return None
    src = Path(raw)
    # os.path: under a dir with no search bit, Path.is_file raises on 3.12.
    return src if os.path.isfile(src / "SKILL.md") else None  # noqa: FURB146


def reinstall_from_url(name: str, entry: dict) -> InstallResult:
    """Clone a URL import's repo again and reinstall ``name`` from it.

    Reads the recorded path at the repo's current HEAD — the same thing a tap
    skill's reinstall does with the tap's current checkout — and records the
    new commit. ``force`` as for any reinstall: replacing a pinned skill is
    what the command is for. A path that leaves the clone is refused; the lock
    is a file anyone can edit, and ``../`` would otherwise reach whatever sits
    beside the temporary directory.
    """
    url = str(entry.get("source_url") or "")
    rel = str(entry.get("source_dir") or ".")
    with cloned_source(url) as remote:
        src = remote.root / rel
        inside = src.resolve().is_relative_to(remote.root.resolve())
        if not inside or not (src / "SKILL.md").is_file():
            raise BoostError("%s has no SKILL.md at %s" % (url, rel),
                             hint="re-import it from wherever it lives now")
        return install_from_path(src, name=name, force=True, remote=remote)


def skill_store_dir(name: str) -> Path:
    """Resolve ``name`` to its dir under the canonical store.

    Raises BoostError unless the name is a safe path component.
    """
    if not util.is_safe_component(name):
        raise BoostError("invalid skill name %r" % name)
    return paths.store_dir() / name


def read_skill_meta(name: str, skill_dir: Path | None = None
                    ) -> tuple[dict, str] | None:
    """(frontmatter, body) for an installed skill's store copy, or None.

    ``skill_dir`` reads another copy instead — a project skill's, which is
    not in the store (:class:`integrity.InstalledSkill` ``.dir``).

    None on anything that keeps the content from being read honestly: no
    store dir, no ``SKILL.md``, an unreadable file, or an unclosed
    frontmatter fence (:func:`frontmatter.unclosed` — every field would read
    as absent, which is not the same fact as the skill declaring none).
    Callers that use this for policy enforcement (``boost policy check``)
    must treat ``None`` as *not checked*, never as a violation — a store read
    failing is not evidence the skill lacks a version or description.
    """
    from . import frontmatter

    skill_md = (skill_dir if skill_dir is not None
                else skill_store_dir(name)) / "SKILL.md"
    if not skill_md.exists():
        return None
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if frontmatter.unclosed(text):
        return None
    return frontmatter.parse(text)


def resolve_lock_entry(name: str) -> tuple[str, str | None, dict | None]:
    """(bare_name, kind, entry) for a possibly tap-qualified ``name``.

    Splits an ``owner/repo:skill`` qualifier (:func:`catalog.split_name`) and
    looks the *bare* name up across every lock section
    (:func:`lockfile.find_any`) — the lock keys installed items by their bare
    name, and :func:`skill_store_dir` rejects the qualified string outright
    since ``:`` (and ``/``) is not a safe path component. A command that
    probes the store or the lock with the still-qualified string before
    splitting gets "invalid skill name" or "not installed" for the very
    string an ambiguity hint just told it to type.

    When a qualifier is given, it is checked against the entry's own ``tap``
    (:func:`catalog.tap_matches`): an item installed from a *different* tap
    is not this qualifier's answer, so ``kind``/``entry`` come back
    ``(None, None)`` rather than reporting another tap's install under this
    name — the same rule ``commands/info.py``'s ``_for_tap`` applies. A
    caller that also accepts a not-yet-installed name falls through to
    :func:`catalog.resolve_one` in that case, which already parses the
    qualified grammar; a caller that only operates on installed items reports
    "not installed", same as a bare miss.
    """
    qualifier, bare = catalog.split_name(name)
    found = lockfile.find_any(bare)
    if found is None:
        return bare, None, None
    kind, entry = found
    if qualifier and not catalog.tap_matches(str(entry.get("tap") or ""), qualifier):
        return bare, None, None
    return bare, kind, entry


def installed_name(name: str) -> str:
    """The bare lock key a command acting on an installed ``name`` should use.

    ``install`` accepts ``tap:skill`` and every ambiguity hint tells the user
    to type it, but the lock — user and project — keys items by the bare
    name, so a command that probed it with the qualified string answered
    "not installed" about an item ``boost list`` shows. This is the one place
    such a command turns what was typed into the key it looks up.

    An unqualified ``name`` comes back unchanged, and so does — bare — a
    qualified one nothing is installed under: the caller's own lookup then
    reports the miss in its usual words. A qualifier that names a tap the
    installed item did *not* come from raises rather than acting on another
    tap's copy, and so does one that matches only an item the command would
    not reach: a bare name resolves skill-first (:func:`lockfile.find_any`),
    so ``other:x`` selecting the rule ``x`` while a skill ``x`` is installed
    would otherwise uninstall or pin the skill.
    """
    qualifier, bare = catalog.split_name(name)
    if qualifier is None:
        return name
    held = [(kind, section[bare]) for kind, section in lockfile.all_installed().items()
            if bare in section]
    pbase = scopes.resolve_base(scopes.SCOPE_PROJECT)
    project_entry = projectlock.get_skill(pbase, bare) if pbase is not None else None
    if project_entry is not None:
        held.append(("skill", project_entry))
    if not held:
        return bare
    taps = [str(entry.get("tap") or "local") for _kind, entry in held]
    if not any(catalog.tap_matches(t, qualifier) for t in taps):
        raise BoostError(
            "%s is not installed — %s is installed from %s, not %s"
            % (name, bare, ", ".join(dict.fromkeys(taps)), qualifier),
            hint="name it `%s` or `%s:%s`" % (bare, taps[0], bare), wrap=True)
    if not catalog.tap_matches(taps[0], qualifier):
        kind = next(k for (k, _e), t in zip(held, taps, strict=True)
                    if catalog.tap_matches(t, qualifier))
        raise BoostError(
            "%s is ambiguous here — it selects the %s %s, but the %s %s from %s "
            "is the one this command would act on"
            % (name, kind, bare, held[0][0], bare, taps[0]),
            hint="uninstall one of the two first, or see `boost list`", wrap=True)
    return bare


def upstream_source(name: str) -> tuple[str, str, str, str]:
    """``(bare, kind, tap, rel)``: where item ``name`` lives in its tap.

    The installed copy comes first. The lock records exactly which file or
    directory was installed, while the catalog can only guess from a name.
    A registry that ships ``csharp-reviewer`` three times makes
    :func:`catalog.resolve_one` refuse, telling the user to install one copy
    with ``--path`` and retry. Asking the catalog first meant that retry
    failed the same way. Only a name that is not installed, or whose tap
    qualifier names another tap, falls through to the catalog.

    ``rel`` is :func:`catalog.upstream_path`: the defining file for a rule or
    workflow, the directory for a skill. A lock entry with no ``tap`` counts
    as ``local``, an import with no upstream.
    """
    bare, kind, lk = resolve_lock_entry(name)
    if lk is not None:
        # `kind` is always set when an entry is: it names the lock section.
        return (bare, str(kind), str(lk.get("tap") or "local"),
                catalog.upstream_path(lk))
    entry = catalog.resolve_one(name)
    return (bare, str(entry.get("kind") or "skill"), str(entry["tap"]),
            catalog.upstream_path(entry))


def lock_drift(entry: dict, qualifier: str | None,
               version: str | None) -> list[tuple[str, str, str]]:
    """How an installed lock ``entry`` differs from a requested ``tap:name@ver``.

    Returns ``(field, installed, wanted)`` for each of ``"tap"`` and
    ``"version"`` that the request pins and the entry does not satisfy; an
    empty list means the install is what was asked for. A field the request
    leaves out (no qualifier, no ``@version``) is never drift.

    The tap test is :func:`catalog.tap_matches`, the same one
    :func:`resolve_lock_entry` applies, so ``skills:x`` still matches an
    install from ``owner/skills``. The fallbacks mirror what
    ``boost bundle dump`` writes for an entry missing either field — no tap is
    ``local``, no version is ``0.0.0`` — so a Boostfile dumped from this lock
    reads back with no drift at all.
    """
    drift: list[tuple[str, str, str]] = []
    tap = str(entry.get("tap") or "local")
    if qualifier and not catalog.tap_matches(tap, qualifier):
        drift.append(("tap", tap, qualifier))
    have = str(entry.get("version", "0.0.0"))
    if version and have != version:
        drift.append(("version", have, version))
    return drift


def installed() -> dict:
    """Return the lock file's installed skills as {name: entry}.

    Skills only; rules/workflows live in their own lock sections.
    """
    return lockfile.installed()


def has_content() -> bool:
    """True if the canonical store holds any skill at all.

    Independent of the lock file: a store dir survives even when
    ``.skill-lock.json`` goes missing or corrupt, so this is how a caller
    tells a genuinely fresh install (nothing installed, nothing to report)
    apart from one whose lock record vanished out from under a populated
    store (a fault `boost verify`/`drift`/`doctor` must not stay quiet
    about).

    A skill is a dir holding a ``SKILL.md``. Any dir used to count, so
    another tool's bucket in the store (one with no ``SKILL.md``) held `boost
    doctor` at "lock file missing — run `boost sync`" for good: there was
    nothing a lock could have recorded, and nothing sync could record.

    A dir boost cannot look into counts as content: "no SKILL.md" is an answer
    only when the lookup says so. ``os.path.isfile`` says False for a dir
    with no search bit, and a store of those read as empty — which, over a
    missing lock, told `verify` and `drift` there was nothing to check.
    """
    root = paths.store_dir()
    try:
        names = os.listdir(root)
    except OSError:
        return False
    return any(not n.startswith(".") and _may_hold_skill(os.path.join(root, n))
               for n in names)


def _may_hold_skill(d: str) -> bool:
    """True unless ``d`` is known to hold no ``SKILL.md`` file."""
    try:
        return stat.S_ISREG(os.stat(os.path.join(d, "SKILL.md")).st_mode)
    except (FileNotFoundError, NotADirectoryError):
        return False
    except OSError:
        return True


def source_dir_for(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone.

    Clones the tap first if it is only *registered* and not yet cloned — the
    state `boost catalog --import` deliberately leaves a tap in (a bundle
    ships the catalogue, not the repo, precisely so the receiver can search
    before paying for any clone). `catalog --import`'s own hint promises
    "`boost install` clones just the one registry it needs"; without this, a
    tap that was imported rather than tapped raised "source vanished from
    tap" — a message that implies the source *used to* exist, when really it
    was never fetched.

    Materializes the directory next. Taps check out Markdown only, so a skill
    that ships `scripts/` or `assets/` has them in the index and not on disk;
    `_copy_skill` is a copytree, and handed a partial directory it copies what
    is there and reports success. Every consumer of a tap's real files — both
    install paths, `sha256_dir`, `boost info` — comes through here, so this is
    the one place that has to get it right.

    Only a skill has a source directory. A rule or workflow is one file, read
    through ``entry["skill_md"]`` by its own installer, so it is refused here
    before the tap is cloned or widened: `boost info` and `boost deps` ask
    about every not-installed entry, and checking SKILL.md after materializing
    had them write ``/rules/*`` into the sparse cone for a dir they discarded.
    An entry with no ``kind`` (an old cache, or one `quality` builds by hand)
    is a skill.
    """
    kind = entry.get("kind") or catalog.KIND_SKILL
    if kind != catalog.KIND_SKILL:
        raise BoostError("%s is a %s, not a skill: it has no source directory"
                         % (entry["name"], kind))
    tap = registry.get(entry["tap"])
    if not tap.is_cloned:
        gitutil.clone_shallow(tap.url, tap.path)
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    gitutil.materialize(tap.path, entry["rel_dir"])
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    missing = link_targets_to_fetch(tap.path, src)
    if missing:
        gitutil.materialize_paths(tap.path, missing)
    return src


def copy_view_sha(src: Path, within: Path | None) -> str:
    """``sha256_dir`` of what :func:`_copy_tree` puts in the store from ``src``.

    The lock records the hash of the *copy*, so the source side of every
    "did the tap move this skill?" comparison has to hash the same view. A
    raw ``sha256_dir(src)`` reads a link out of the tap as its target's
    bytes, a link install skips by policy, so a skill holding one compared
    unequal forever: `update` re-copied it as "source changed" on every tap
    move and `drift` called it upstream-moved after `update` had nothing to
    do. A tree with no link hashes in place; one with any is staged through
    ``_copy_tree`` itself, so the two cannot disagree about what lands.
    """
    src = Path(src)
    if not any(Path(here, n).is_symlink()
               for here, dirs, names in os.walk(src)
               for n in (*dirs, *names)):
        return util.sha256_dir(src)
    with tempfile.TemporaryDirectory(prefix=util.TEMP_PREFIX) as tmp:
        view = Path(tmp) / "view"
        _copy_tree(src, view, within)
        return util.sha256_dir(view)


def skill_source_sha(entry: dict) -> str:
    """:func:`copy_view_sha` of a catalog entry's tap source.

    Raises ``BoostError`` as :func:`source_dir_for` does. Bounded by the tap
    clone, as a tap install's copy is.
    """
    src = source_dir_for(entry)
    return copy_view_sha(src, registry.get(entry["tap"]).path)


def _inside(path: str, root: str) -> bool:
    """Whether ``path`` is ``root`` or under it (both already normalized)."""
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:      # different drives on Windows
        return False


def link_targets_to_fetch(repo: Path, src: Path) -> list[str]:
    """Repo-relative paths ``src``'s symlinks lead to that are not on disk.

    A tap checks out Markdown and each installed skill's own dir, so a link
    from the skill to a file elsewhere in the tap (``../../shared/helper.py``)
    dangles in the clone though the file exists upstream; copying it then
    fails. Only targets inside ``repo`` are named — a link out of the tap is
    never followed, so there is nothing to fetch for it.
    """
    root = os.path.abspath(repo)
    found: list[str] = []
    for here, dirs, names in os.walk(src):
        dirs[:] = [d for d in dirs if d not in util.IGNORED]
        for n in (*dirs, *names):
            p = Path(here, n)
            if not p.is_symlink():
                continue
            target = os.path.normpath(os.path.join(here, os.readlink(p)))
            if _inside(target, root) and not Path(target).exists():
                found.append(Path(os.path.relpath(target, root)).as_posix())
    return found


#: :func:`link_agents`' default ``updated_at``: read the date from the lock.
FROM_LOCK = "lock"


def link_agents(name: str, only: list[str] | None = None, *,
                keep_theirs: bool = False,
                updated_at: str | None = FROM_LOCK) -> InstallResult:
    """Symlink store/<name> into each linking agent dir. Returns result with
    .linked (agent names), .conflicts (paths that were real files/dirs) and
    .native (agents that read the store directly and needed no link).

    A link that already leads to the store copy is left alone and counts as
    linked, so a dir that refuses writes only refuses a link that needs one:
    a missing link, or one pointing elsewhere.

    Claude Code gets no new link while an enabled plugin ships the same files,
    or a copy newer than boost's (.covered, :func:`serving_plugin`): it
    already lists the plugin's copy, and a link would list the skill a second
    time. That holds for an explicit ``--agent claude-code`` too, since the
    skill is in front of Claude Code either way. ``updated_at`` is when boost's
    copy last changed (:func:`source_updated_at`); an install passes the date
    of what it is about to record, and every other caller the lock's.

    ``keep_theirs`` leaves a symlink that is not boost's (:func:`is_boost_link`)
    where it is, as a conflict, the way a file is left. :func:`unsideline`
    passes it: :func:`sideline` leaves the user's own link alone, and
    relinking replaced it with a link to the store copy."""
    res = InstallResult(name=name, dest=skill_store_dir(name))
    target = skill_store_dir(name)
    # Deliberately NOT filtered by `only`. That list scopes which agents get a
    # *link*, but a native-store agent's access follows from the store itself,
    # which every install writes no matter how narrow the scope — so even
    # `--agent cursor` really does leave the skill visible to Gemini, and
    # saying otherwise would be a lie. Filtering here also silently broke
    # reinstall: `preserved_agent_scope` replays the lock's recorded *links*,
    # which by construction never contain a native agent.
    res.native = list(agents.native_store_agents())
    for agent, adir in agents.linking_agents().items():
        if only and agent not in only:
            continue
        link = adir / name
        # Asked before anything is written, so a covered skill costs Claude
        # Code's dir no mkdir and loses no link it already has: one that leads
        # here stays until `sync --prune` drops it, and `update` changes
        # nothing an agent sees.
        if (agent == foreign.CLAUDE
                and not (os.path.islink(link)  # noqa: FURB146
                         and _already_links(link, target))
                and (hit := serving_plugin(name, _lock_date(name, updated_at)))
                is not None):
            res.covered.append(hit[0].id)
            continue
        try:
            adir.mkdir(parents=True, exist_ok=True)
            if link.is_symlink():
                if _already_links(link, target):
                    # Already right, so there is nothing to write. Re-creating
                    # it anyway needed a writable dir: in one that refuses
                    # writes, the unlink raised PermissionError and a reinstall
                    # printed "not linked" over a link still on disk, still
                    # pointing at the store, and still in the lock's `agents`.
                    agents.remember_link_dir(agent, adir)
                    res.linked.append(agent)
                    continue
                if keep_theirs and not points_into_store(link):
                    res.conflicts.append(str(link))
                    continue
                link.unlink()
            elif link.exists():
                res.conflicts.append(str(link))
                continue
            link.symlink_to(target)
        except PermissionError:
            # One unwritable agent dir used to abort the whole install at
            # exit 70 — after the store copy and the other agents' links, so
            # the lock recorded none of it. Skip the agent and say so; the
            # caller names the remedy.
            #
            # Named by `refuses_writes`, as `_refused_target` names a rule's:
            # a missing skills dir under a read-only `~/.cursor`, or one under
            # a `~/.cursor` with no search bit, is refused by `~/.cursor`, and
            # naming the skills dir handed the user a `chmod` that fails or
            # changes nothing.
            res.unwritable.append(str(paths.refuses_writes(adir) or adir))
            res.refused.append(agent)
            continue
        except OSError as exc:
            # No symlink can be made here at all: every install used to exit
            # 70 from the line above. Skip the agent, as for an unwritable
            # dir; the store copy still reaches the agents that read it
            # directly, and `boost sync` links the rest once links work.
            if symlinks_unsupported(exc):
                res.unlinkable.append(str(adir))
                res.refused.append(agent)
                continue
            # A dangling symlink or a file where the agent dir belongs: the
            # mkdir raises FileExistsError or NotADirectoryError. It escaped
            # here after `_copy_skill` had run, so the install exited 70 with
            # the skill in the store and no lock entry. Skip it the same way.
            # Anything else is not understood, so it stays loud.
            block = paths.refuses_writes(adir)
            if block is None or not paths.in_the_way(block):
                raise
            res.blocked.append((str(adir), str(block)))
            res.refused.append(agent)
            continue
        # So a later uninstall still finds this link after the agent's dir is
        # repointed (:func:`agents.former_link_dirs`).
        agents.remember_link_dir(agent, adir)
        res.linked.append(agent)
    return res


#: What a filesystem or OS that cannot make a symlink at all raises: EINVAL
#: from Windows without Developer Mode (ERROR_PRIVILEGE_NOT_HELD arrives as a
#: plain OSError, not a PermissionError), ENOTSUP/EOPNOTSUPP/ENOSYS from FAT
#: and exFAT mounts. EPERM is left out on purpose: it is a PermissionError,
#: and :func:`link_agents` already reads that as an unwritable agent dir.
_NO_SYMLINK_ERRNOS = frozenset({errno.EINVAL, errno.ENOTSUP,
                                errno.EOPNOTSUPP, errno.ENOSYS})
_ERROR_PRIVILEGE_NOT_HELD = 1314


def symlinks_unsupported(exc: OSError) -> bool:
    """Whether ``exc``, raised making a symlink, means none can be made."""
    if getattr(exc, "winerror", None) == _ERROR_PRIVILEGE_NOT_HELD:
        return True
    return (not isinstance(exc, PermissionError)
            and exc.errno in _NO_SYMLINK_ERRNOS)


def symlink_refusal(adir: str) -> tuple[str, str]:
    """Why a dir from ``res.unlinkable`` refused, and what clears it."""
    return ("this system refused to create a symlink in %s" % paths.tilde(adir),
            "on Windows turn on Developer Mode (Settings > System > For "
            "developers) or use an administrator shell; on a FAT or exFAT "
            "drive keep your home on a filesystem with symlinks")


def _lock_date(name: str, updated_at: str | None) -> str | None:
    """``updated_at``, or the lock's date for ``name`` when it is :data:`FROM_LOCK`."""
    if updated_at != FROM_LOCK:
        return updated_at
    return (lockfile.get_skill(name) or {}).get("source_updated_at")


def source_updated_at(tap_name: str | None, rel_dir: str,
                      rev: str = "HEAD") -> str | None:
    """When a tap skill's files last changed at ``rev``, as :func:`util.now_iso` writes.

    The newest commit touching anything under its source dir — ``SKILL.md``,
    scripts, assets. A tap clone is ``--depth 1``, where that question has
    one answer for every dir, so the clone is deepened first
    (:func:`gitutil.unshallow`: commits and trees only, and once per tap).
    None for the ``local`` tap, a tap that is gone or not cloned, no git, or
    a clone that could not be deepened (offline): the date is what decides
    between boost's copy and a plugin's, and an unknown one decides nothing.
    """
    if not tap_name or tap_name == "local":
        return None
    try:
        tap = registry.get(tap_name)
        if not tap.is_cloned:
            return None
        gitutil.unshallow(tap.path)
        when = gitutil.path_updated_at(tap.path, rel_dir or ".", rev or "HEAD")
    except BoostError:
        return None
    return None if when is None else util.iso_from_epoch(when)


def backfill_source_dates(taps) -> list[str]:
    """Record :func:`source_updated_at` for installed skills that have none.

    For the skills from ``taps`` installed before boost recorded the date:
    ``boost update`` reinstalls only a skill whose source changed, so without
    this the date would reach no skill already on the machine. Read at the
    commit each was installed from, so a pinned skill is dated by the files
    it has. A ``boost import`` row has no tap clone to read and is skipped.
    Returns the names dated.
    """
    wanted = set(taps)
    done = []
    for name, entry in sorted(lockfile.installed().items()):
        if (entry.get("tap") not in wanted or entry.get("source_updated_at")
                or entry.get("source_url")):
            continue
        when = source_updated_at(entry.get("tap"), entry.get("source_dir") or ".",
                                 entry.get("commit") or "HEAD")
        if when is None:
            continue
        def date(row: dict, when: str = when) -> None:
            row["source_updated_at"] = when
        if lockfile.update_skill(name, date):
            done.append(name)
    return done


def _already_links(link: Path, target: Path) -> bool:
    """True if the symlink ``link`` already leads to ``target``.

    Asks about this one skill's store dir, not the store as a whole the way
    :func:`resolves_into_store` does: a link to another skill's copy is wrong
    and must still be replaced.

    **Both sides are resolved**, for the reason :func:`resolves_into_store`
    gives: under macOS's ``/tmp`` or ``/var/folders`` a link written as
    ``/tmp/.../x`` resolves to ``/private/tmp/.../x``, so comparing it against
    a nominal ``target`` never matches. The whole chain is followed, so a link
    that reaches the store through an alias counts too.

    Fails closed: a dangling link, a loop, or a target that is not there is
    not linked, and takes the old unlink-and-recreate path. Only the
    *target*'s strictness carries that: a dangling link resolves leniently to
    a path nothing is at, which cannot equal a store dir that resolved
    strictly, while a store dir that is missing raises and answers False for
    every link at once.
    """
    try:
        have = normalize_link_target(link.resolve())
        want = normalize_link_target(target.resolve(strict=True))
    except (OSError, RuntimeError):
        # RuntimeError: Python 3.12 raises it for a symlink loop, and it is
        # not an OSError (see resolves_into_store).
        return False
    return have == want


def unwritable_refusal(block: str) -> tuple[str, str]:
    """Why a dir from ``res.unwritable`` refused, and the ``chmod`` that clears it.

    One wording for every surface that reports one, so a dir at ``0o600`` is
    called unsearchable and given ``u+wx`` everywhere, not ``u+w`` -- which
    leaves it exactly as stuck -- in the four places that spelled it inline.
    """
    return (paths.not_writable(Path(block), Path(block)),
            "`%s`" % paths.chmod_command(Path(block)))


def link_refusal(adir: str, block: str) -> tuple[str, str]:
    """Why a write in `adir` was refused, and the one step that clears it.

    For a ``res.blocked`` pair. Every surface that reports one words it here,
    so none of them tells the user to ``chmod`` a dangling symlink.
    """
    return (paths.not_writable(Path(adir), Path(block)),
            paths.write_remedy(Path(block)))


def preserved_agent_scope(only_agents: list[str] | None,
                          existing: dict | None) -> list[str] | None:
    """Agent scope for a re-install: the caller's if given, else the lock's.

    ``boost install foo --agent claude-code`` records exactly that subset. But
    ``update`` and ``reinstall`` force-reinstall with ``only_agents=None``, and
    ``link_agents(None)`` fans out to *every* enabled agent — so a deliberate
    narrowing silently became a full install, and the lock entry was rewritten
    to match. Falling back to what the lock already records keeps the scope a
    property of the install rather than of whichever agents happen to be
    enabled the next time something updates.

    An explicit ``only_agents`` still wins, so re-running install with
    ``--agent`` remains the way to widen the scope again. Skills record their
    scope as ``agents``. Rules and workflows replay only a declared
    ``only_agents``: their ``materializations`` rows record what was written,
    and an undeclared install fans out to every agent that takes it. An entry
    written before they recorded the field still replays its rows. An empty
    record means "nothing was linked", not "link nothing", so it falls back to
    every enabled agent — exactly what ``link_agents`` does with ``None``.
    """
    if only_agents is not None:
        return only_agents
    if not existing:
        return None
    # A recorded declaration outranks the link list. Now that ``agents``
    # describes disk, it can legitimately name agents *outside* a narrowing —
    # and replaying it would make `update`/`reinstall` recreate a link the
    # declaration excludes, including one the user had just deleted by hand.
    # `sync` already refuses to do that (``scoped_agents``); these have to
    # agree, or which command you run decides what your agent set is.
    declared = existing.get("only_agents")
    if declared:
        return list(declared)
    recorded = existing.get("agents")
    if recorded is None and "only_agents" in existing:
        # A rule or workflow that records its declaration: its rows say which
        # agents were *written* last time, not which the user asked for.
        # Replaying them froze an install made with no `--agent` to the agents
        # enabled that day: enable cursor afterwards and `sync`, `reinstall`,
        # `update` and `install --force` all skipped it, while doctor called
        # the rule fully materialized. Undeclared means every agent, as
        # `scoped_agents` already says for a skill's links. A row for an agent
        # this run does not write is still carried forward
        # (:func:`_refused_materializations`), so nothing becomes unremovable.
        return None
    if recorded is None:
        # An entry from before rules and workflows recorded ``only_agents``:
        # its rows are the only trace of an `--agent` narrowing, so they are
        # still replayed rather than widened on the next `update`.
        recorded = [m.get("agent")
                    for m in existing.get("materializations") or ()]
        # A workflow agent whose path held the user's own file is kept in
        # scope the way a refused skill link is, and for the same reason:
        # without it the agent dropped out of every later reinstall, update
        # and sync, so moving the file aside never brought the command back.
        # Only beside written agents, as below: none written means every
        # agent already, and narrowing to the foreign ones would strand it.
        if any(recorded):
            recorded += [r.get("agent") for r in foreign_rows(existing)]
    elif recorded:
        # A skill's `agents` is what is linked, so an agent whose dir refused
        # the link was not in it, and replaying it never retried that agent:
        # after the dir was fixed, `install --force` linked everywhere else
        # and said nothing. `refused_agents` is the skill-side twin of a
        # rule's ``unwritable`` row, which keeps the agent in scope the same way.
        #
        # Only beside links. An empty `agents` still means every agent (below):
        # a sideline empties it and leaves the refusals, and narrowing the next
        # `update` to the refused agents alone would strand the skill there.
        recorded = [*recorded, *(existing.get("refused_agents") or ())]
    return list(dict.fromkeys(a for a in recorded if a)) or None


def record_links(entry: dict, res: InstallResult) -> dict:
    """Write a skill's link outcome into its lock `entry`, and return it.

    ``agents`` is what `res` linked; ``refused_agents`` is
    :func:`unrecorded_agents`: the agents whose dir refused, and those whose
    link boost may not look at. Kept so :func:`preserved_agent_scope` retries
    them and so uninstall does not take "not seen" for "not there". Absent,
    not empty, when there are none, so an entry that never met a refusal is
    unchanged.
    """
    entry["agents"] = res.linked
    refused = unrecorded_agents(res.name, res)
    if refused:
        entry["refused_agents"] = refused
    else:
        entry.pop("refused_agents", None)
    return entry


def unseen_agents(name: str) -> list[str]:
    """The linking agents whose ``name`` link boost may not even look at.

    :func:`linked_agents` answers False for these, which is "could not look",
    not "no link": under a dotdir with no search bit the first install's link
    is still there. ``os.lstat`` raises PermissionError there on every Python
    this supports, where ``os.path.islink`` swallows it.
    """
    unseen = []
    for agent, adir in agents.linking_agents().items():
        try:
            os.lstat(adir / name)
        except PermissionError:
            unseen.append(agent)
        except OSError:
            continue
    return unseen


def unrecorded_agents(name: str, res: InstallResult) -> list[str]:
    """What a lock entry's ``refused_agents`` records for ``name``.

    The agents whose dir refused the link this run, and every agent whose link
    boost could not look at, whether or not this run tried it. A narrowed
    relink (``install --force --agent claude-code``) never tries cursor, so
    nothing is refused, and :func:`linked_agents` cannot see cursor's link:
    recording only those two forgot a link still on disk, and uninstall then
    exited 0 and left it dangling into a deleted store.
    """
    return list(dict.fromkeys([*res.refused, *unseen_agents(name)]))


def declared_agent_scope(only_agents: list[str] | None,
                         existing: dict | None) -> list[str] | None:
    """The scope to RECORD in the lock: an explicit narrowing, or the last one.

    Deliberately *not* :func:`preserved_agent_scope`. That one answers "which
    agents should this install link into", and falls back to the lock's
    ``agents`` — which records what happens to be linked right now. Writing
    that back as a declared scope would promote "these were the enabled agents
    at install time" into "the user asked for exactly these", permanently
    freezing a skill out of any agent enabled later. The two questions look
    alike and are not, so they get separate functions.

    Only an explicit ``--agent`` narrows. Absent that, an earlier declaration
    is carried forward so ``update``/``reinstall`` don't drop it, and a skill
    that was never narrowed keeps no scope at all (``None``).
    """
    if only_agents is not None:
        return list(only_agents)
    return (existing or {}).get("only_agents")


def _declared_field(only_agents: list[str] | None,
                    existing: dict | None) -> dict:
    """The ``only_agents`` field a rule or workflow lock write carries.

    Written on a fresh install, an explicit ``--agent`` and any entry that
    already has it. Left off an entry from before the field existed, whose
    rows are still the only record of a narrowing: writing ``None`` there
    would widen it on the next `update` (:func:`preserved_agent_scope`).
    """
    if only_agents is None and existing and "only_agents" not in existing:
        return {}
    return {"only_agents": declared_agent_scope(only_agents, existing)}


def scoped_agents(entry: dict, enabled: dict[str, Path]) -> dict[str, Path]:
    """The enabled agents a locked skill is supposed to be linked into.

    Fails **open**: an entry with no ``only_agents`` — every entry written
    before this field existed — means "not narrowed", so it gets every enabled
    agent. That keeps ``boost sync`` doing its other job, which is linking
    already-installed skills into an agent that was enabled afterwards.
    """
    scope = entry.get("only_agents")
    if not scope:
        return enabled.copy()
    return {a: d for a, d in enabled.items() if a in scope}


def unlink_agents(name: str) -> list[str]:
    """Remove boost's ``name`` link from every linking agent dir.

    Returns the agents unlinked. Only boost's kind of link goes
    (:func:`is_boost_link`): a file, or the user's own link to a checkout,
    is left where it is. Any symlink used to count, so uninstalling a skill
    `boost sync` had recorded beside the user's link took that link too, and
    `focus --clear` then put a link to the store copy in its place. Agents
    that read the canonical store directly never had a link, so there is
    nothing here to reverse for them — uninstalling the store dir is what
    removes the skill from their view.
    """
    removed = []
    # Disabled agents too (:func:`agents.unlinking_agents`): a link left in
    # one dangles into the store dir uninstall deletes next.
    for agent, adir in agents.unlinking_agents().items():
        link = adir / name
        if is_boost_link(link):
            link.unlink()
            removed.append(agent)
    # And the dirs an agent linked into before its dir was repointed: the
    # lock names agents, not paths, so a link made under `~/.cursor/skills`
    # was left dangling once `agents.cursor.dir` moved.
    for agent, adir in agents.former_link_dirs():
        link = adir / name
        if is_boost_link(link):
            link.unlink()
            if agent not in removed:
                removed.append(agent)
    return removed


def sideline(name: str, by: str) -> list[str]:
    """Unlink ``name`` and record *why*, so other commands stop fighting it.

    ``focus``, ``profile use`` and ``context apply`` all set a skill's links
    aside deliberately, and used to do it by calling :func:`unlink_agents`
    alone — leaving the lock's ``agents`` field pointing at links that no
    longer exist. Every reader of that field (``list``, ``doctor``,
    ``sync_plan``) took the stale record at face value: ``doctor`` called the
    gap damage and told the user to run ``boost sync``, and ``sync_apply``
    obeyed, silently re-linking the very skill that was just set aside.

    Recording ``sidelined_by`` closes the loop: it names the mechanism
    responsible (``"focus"``, ``"profile"`` or ``"context"``) so a later
    sideline overwrites an earlier one rather than stacking, and so
    :func:`unsideline` and every consulting reader have one flag to check
    instead of re-deriving "should this be linked" from a disk state that
    lockfile.write() itself does not read.
    """
    removed = unlink_agents(name)

    def aside(entry: dict) -> None:
        entry["sidelined_by"] = by
        # `agents` is defined as the links measured from disk, and the links
        # have just been removed — so leaving the old list had `boost list`
        # keep advertising the skill to agents that could no longer see it.
        # `quarantine` clears it for the same reason; :func:`unsideline`
        # recomputes it, exactly as `quarantine --release` does.
        entry["agents"] = []
    lockfile.update_skill(name, aside)
    return removed


def unsideline(name: str) -> InstallResult:
    """Relink ``name`` and clear any recorded sideline.

    The inverse of :func:`sideline`, used by ``focus --clear``, a skill
    re-entering an active focus/profile/context selection, and ``context
    disable``. Clears the flag regardless of which mechanism set it — only
    one can be true of a skill at a time, and whichever command relinks it is
    the one ending it.

    Only into the agents the install declared (``only_agents``): relinking
    into every agent turned a skill installed ``--agent cursor`` into one
    linked everywhere the moment a `profile use` or `focus --clear` touched it.
    """
    declared = (lockfile.get_skill(name) or {}).get("only_agents") or None
    res = link_agents(name, declared, keep_theirs=True)

    def relinked(entry: dict) -> None:
        # Record the links this just made, since sideline() emptied the list,
        # and the agents that refused, so a later reinstall retries them.
        record_links(entry, res)
        entry.pop("sidelined_by", None)
    lockfile.update_skill(name, relinked)
    return res


def linked_agents(name: str) -> list[str]:
    """The linking agents that currently hold a symlink for ``name``.

    Measured from disk, not inherited from the lock, because this is what the
    lock's ``agents`` field is *defined* to mean. Writing back only the links a
    given run created made ``agents`` record the request instead of the result:
    ``install X --agent cursor --force`` on a skill linked into three agents
    left three symlinks and a lock claiming one, and every reporting surface
    believed the lock.

    Deliberately the same test :func:`unlink_agents` uses, :func:`is_boost_link`,
    so what an install records is exactly what an uninstall will remove. A
    regular file sitting where a link should be is a conflict, not a link, and
    so is the user's own link to a checkout outside the scope an install
    wrote: both are excluded by both.

    ``os.path.islink``, not ``Path.is_symlink``: under an agent dotdir with no
    search bit the latter raises PermissionError on Python 3.12 and 3.13 (3.14
    answers False), and it raised here *after* the store copy, so the install
    exited 70 with the skill in the store and nothing in the lock. A link boost
    may not even look at is not one it can count.
    """
    return [agent for agent, adir in agents.linking_agents().items()
            if is_boost_link(adir / name)
            and misdirected(name, adir / name) is None]


def misdirected(name: str, link: Path) -> Path | None:
    """Where a live boost link for ``name`` leads, when it is not ``name``'s copy.

    None for a link that leads to ``name``'s own store dir, and for anything
    that is not a live boost link (:func:`is_boost_link`): a dangling one is
    stale, and a user's own link is the user's. Containment in the store was
    the only question every check asked, so ``~/.claude/skills/brainstorming
    -> ~/.agents/skills/tdd-workflow`` read as healthy to doctor, heal and
    sync while Claude loaded tdd-workflow under brainstorming's name.

    The answer is the store dir it leads into when there is one, so a message
    can name the skill the agent really gets.
    """
    if not is_boost_link(link) or _dangles(link):
        return None
    target = skill_store_dir(name)
    if _already_links(link, target):
        return None
    # By inode too: on a case-insensitive volume a link to ``~/.Agents/...``
    # is the right copy under a spelling ``resolve()`` keeps.
    with contextlib.suppress(OSError):
        if os.path.samefile(link, target):
            return None
    # The entry's name, unless it is this skill's own: a link into a subdir
    # of its copy is wrong too, and "linked to <its own dir>, not its own
    # store dir" would contradict itself, so that one names the real path.
    entry = _store_entry(link)
    return (paths.store_dir() / entry if entry and entry != name
            else Path(os.path.realpath(link)))


def misdirected_links(name: str) -> list[tuple[str, Path]]:
    """``(agent, where)`` for each linking agent whose ``name`` link is
    :func:`misdirected`."""
    return [(agent, wrong) for agent, adir in agents.linking_agents().items()
            if (wrong := misdirected(name, adir / name)) is not None]


def out_of_scope_agents(name: str, entry: dict,
                        linking: dict[str, Path]) -> list[str]:
    """The agents in ``linking`` holding a boost link for ``name`` outside
    the ``--agent`` narrowing ``entry`` declares, read from disk.

    Empty without a narrowing: :func:`scoped_agents` fails open, so every
    agent is in scope. boost's links only, so the user's own link is not
    offered to ``--prune``. ``sync_plan`` and ``doctor`` both ask this: doctor
    used to read the lock's ``agents`` instead, and missed a link made by hand
    that sync went on to report.
    """
    if not entry.get("only_agents"):
        return []
    in_scope = scoped_agents(entry, linking)
    return [agent for agent, adir in linking.items()
            if agent not in in_scope and is_boost_link(adir / name)]


def refusing_dir(path: Path) -> Path:
    """The directory to make writable so a write under ``path`` can succeed.

    ``path`` itself when it exists; otherwise its nearest existing ancestor,
    which is the one that refused to create it. Naming a missing directory in
    a `chmod u+w` remedy hands the user a command that fails.

    A path boost may not even look at counts as not there: under a parent with
    no search bit, ``exists()`` raises PermissionError on Python 3.12 and 3.13
    (3.14 answers False), and raising here turned the named refusal it was
    wording into exit 70.
    """
    while path.parent != path:
        with contextlib.suppress(PermissionError):
            if path.exists():
                break
        path = path.parent
    return path


def _untouched_materializations(existing: dict | None,
                                linked: list[str]) -> list[dict]:
    """Recorded materializations for agents a run did not write to.

    Rules and workflows rebuild ``materializations`` from scratch on every
    install, so a narrowed re-install used to drop the rows for the agents it
    skipped — while leaving their files exactly where they were. Since
    ``_uninstall_rule`` and ``_uninstall_workflow`` are driven by this list and
    never sweep the agent dirs, those files became unremovable: a managed block
    in ``CLAUDE.md`` or a live slash command that no record claimed and no
    command could reverse.
    """
    # The skill copy is never carried: it names no agent, so it is never in
    # ``linked``, and carrying it appended a second copy of the row on every
    # reinstall. `_install_workflow` decides it afresh each run.
    return [m for m in (existing or {}).get("materializations") or []
            if m.get("agent") not in linked and not lockfile.is_skill_copy(m)]


def materialization_is_written(kind: str, entry: dict, m: dict) -> bool:
    """Whether boost still writes the agent this recorded row names.

    The entry-shaped face of :func:`agents.materialization_is_written`, which
    holds the reasoning: a row is kept on purpose so an uninstall can still
    reverse it, so a check that takes it at face value reports a fault whose
    remedy cannot run. ``sync_plan`` put such a row in
    ``missing_materializations``, ``sync_apply`` repaired it by calling
    ``install``, ``install`` skipped the agent, and the next run found it
    missing again: `boost sync` printed "re-materialized rule X" forever and
    `boost doctor` sat at one issue forever, telling the user to run a
    `boost reinstall` that had already been run and could not help.
    """
    return agents.materialization_is_written(kind, entry.get("base"),
                                             m.get("agent"))


def unmaterialized_agents(kind: str, entry: dict) -> list[str]:
    """The agents boost writes ``kind`` into that ``entry`` has no row for.

    Rows record what an install wrote, so an agent enabled afterwards -- or
    added to the defaults since -- has none, and every check that walks the
    rows found nothing wrong with it: doctor called the rule fully
    materialized and `boost sync` linked the skill beside it and left the
    rule out. An ``unwritable`` row and a workflow's ``foreign`` row count as
    present: each already names the agent, with its own remedy.

    Within a declared ``--agent`` narrowing only, so this never widens one.
    Empty for an entry that records no ``only_agents`` at all: it predates
    the field, its rows are its only record of a narrowing, and reading them
    as gaps would undo one. Empty for an entry with no rows, which predates rows and has
    nothing to compare (:func:`integrity.reaches_no_agent` reads it the same
    way), and for a quarantined or stranded entry, whose artifacts are absent
    on purpose.
    """
    rows = entry.get("materializations") or []
    if (not rows or "only_agents" not in entry or entry.get("quarantined")
            or scopes.stranded(entry)):
        return []
    base = entry.get("base")
    writes = (agents.workflow_agents(base) if kind == "workflow"
              else agents.materializing_agents(base))
    declared = entry.get("only_agents")
    have = {m.get("agent") for m in rows} | {
        r["agent"] for r in foreign_rows(entry)}
    return [a for a in writes
            if a not in have and (not declared or a in declared)]


def unwritten_materializations() -> list[tuple[str, str, str, str]]:
    """``(kind, name, agent, reason)`` for every row boost no longer writes --
    what `boost doctor` names once instead of reporting as rot.

    Quarantined entries are left out. Their artifacts are deliberately gone
    and ``sync_plan`` skips them, so naming one here would print a line whose
    `boost sync` remedy cannot run -- the very failure this list exists to
    end. The ``reason`` is :func:`agents.materialization_skip_reason`, because
    *disabled* is only one of the ways a row stops being written.
    """
    return [(kind, name, m["agent"],
             agents.materialization_skip_reason(kind, entry.get("base"),
                                                m["agent"])
             or agents.REASON_UNKNOWN)
            for kind, section in (("rule", lockfile.installed_rules()),
                                  ("workflow", lockfile.installed_workflows()))
            for name, entry in sorted(section.items())
            # Stranded rows too: their repo is gone, so "which agents does
            # it take" has no answer, and doctor names them on their own.
            if not entry.get("quarantined") and not scopes.stranded(entry)
            for m in entry.get("materializations") or []
            if not materialization_is_written(kind, entry, m)]


def unwritable_agent_dirs() -> list[Path]:
    """The directories that stop boost writing into an agent dir.

    Every linking agent's skills dir, where an install symlinks, and each dir
    a recorded rule or workflow row materializes into: ``~/.cursor/rules``,
    ``~/.cursor/commands``, or ``~/.claude`` itself for the ``CLAUDE.md`` a
    rule merges into. Only the dirs a row names: a skills-only user whose
    ``~/.claude/commands`` is read-only on purpose (another tool manages it)
    has nothing boost would write there, so it is not boost's to report.

    Each is :func:`paths.refuses_writes` of a dir boost writes into: the dir
    itself, or the ancestor that would not let it be created, since a ``chmod``
    on a dir that was never created fails. A missing dir an install can create
    is not reported. Neither is a file or a dangling link in the way, which no
    ``chmod`` clears: that is :func:`blocked_agent_dirs`.

    It used to ask ``is_dir() and not access(W_OK)`` of the dir alone, which
    a missing ``~/.cursor/skills`` under a read-only ``~/.cursor`` fails at the
    first half: install named it, while doctor said healthy and `boost sync`
    "everything in sync". And ``W_OK`` alone passed a ``~/.cursor`` at
    ``0o600``, which is writable and still refuses everything under it.
    """
    dirs = [*agents.linking_agents().values(),
            *(d for d, _refused in _materialized_dirs())]
    found: dict[Path, None] = {}
    for d in dict.fromkeys(dirs):
        block = paths.refuses_writes(d)
        if block is not None and not paths.in_the_way(block):
            found.setdefault(block)
    return list(found)


def blocked_agent_dirs() -> list[tuple[Path, Path]]:
    """``(dir, block)`` for each dir boost writes into that something blocks.

    The dirs :func:`unwritable_agent_dirs` checks, where a file or a dangling
    symlink sits at the dir or above it: a file at ``~/.cursor``, a
    ``~/.cursor/rules`` link that leads nowhere. Neither is a directory, so
    :func:`unwritable_agent_dirs` never sees one, and a row recorded as
    refused for it was reported by nothing. The pair is what
    :func:`link_refusal` words.

    One pair per block: a file at ``~/.cursor`` stops its skills, rules and
    commands dirs alike, and one move clears all three.
    """
    dirs = [*agents.linking_agents().values(),
            *(d for d, _refused in _materialized_dirs())]
    found: dict[Path, Path] = {}
    for d in dict.fromkeys(dirs):
        block = paths.refuses_writes(d)
        if block is not None and paths.in_the_way(block):
            found.setdefault(block, d)
    return [(d, block) for block, d in found.items()]


def _materialized_dirs() -> Iterator[tuple[Path, bool]]:
    """``(dir, refused)`` for each recorded rule or workflow row with a path:
    the dir it writes into, and whether its install was refused there.

    Rows for agents boost no longer writes are left out
    (:func:`materialization_is_written`). A disabled agent's dir is not one
    boost writes into, so an unwritable or blocked one is not boost's to
    report -- and both callers' remedies (`chmod u+w`, then `boost sync`) end
    in a write that would never be attempted.
    """
    for kind, section in (("rule", lockfile.installed_rules()),
                          ("workflow", lockfile.installed_workflows())):
        for entry in section.values():
            for m in entry.get("materializations") or []:
                if m.get("path") and materialization_is_written(kind, entry, m):
                    yield Path(m["path"]).parent, bool(m.get("unwritable"))


def _refused_target(err: OSError, path: Path, unwritable: list[str],
                    blocked: list[tuple[str, str]],
                    conflicts: list[str]) -> bool:
    """File a refused write under ``path`` as `unwritable`, `blocked` or a
    conflict.

    For a rule or workflow target, the same two shapes :func:`link_agents`
    skips for a skills dir. A dir that refuses the write is named for a
    ``chmod``: ``path``'s dir, or its nearest existing ancestor when it was
    never created. A file or a dangling symlink where the dir or a parent
    belongs makes the mkdir raise FileExistsError or NotADirectoryError, and
    no mode change clears it, so it is kept apart and worded with
    :func:`link_refusal`. False for anything else: it is not understood, and
    the caller re-raises it rather than skip an agent in silence.

    ``paths.refuses_writes``, not :func:`refusing_dir`, finds the block:
    ``Path.exists`` follows a dangling link, so it walks past the link to a
    parent that is fine.

    A *directory* at ``path`` itself (``~/.cursor/rules/house.mdc/``) is a
    conflict: the dir is fine, something boost does not own sits where its
    file goes, as a real file at a skill's link path does. The write raised
    IsADirectoryError, which none of the shapes above matched, so the install
    exited 70 after writing the other agents' copies, with no lock entry.
    """
    if isinstance(err, IsADirectoryError) and occupied(path):
        conflicts.append(str(path))
        return True
    if isinstance(err, PermissionError):
        # Not `refusing_dir`: its `exists()` walk raises PermissionError of its
        # own under a parent with no search bit, after the other agents were
        # written. `refuses_writes` asks `lexists`, which answers False there.
        unwritable.append(str(paths.refuses_writes(path.parent) or path.parent))
        return True
    block = paths.refuses_writes(path.parent)
    if block is None or not paths.in_the_way(block):
        return False
    blocked.append((str(path.parent), str(block)))
    return True


def occupied(path: Path) -> bool:
    """A directory sits where a rule's or workflow's *file* belongs.

    Not a symlink to one: a write replaces the link itself, so only a real
    directory stops it. ``os.path``, which answers False for a path it may not
    look at rather than raising.
    """
    return os.path.isdir(path) and not os.path.islink(path)  # noqa: FURB146


def materialization_refused(kind: str, name: str) -> bool:
    """Whether re-materializing `name` would still be refused somewhere.

    True if a row boost writes has its dir refusing writes
    (:func:`paths.refuses_writes`) or a directory at its file path
    (:func:`occupied`): the cases where the install skips that agent, and so
    where :func:`sync_apply` does not claim the repair.
    """
    getter = lockfile.get_rule if kind == "rule" else lockfile.get_workflow
    entry = getter(name) or {}
    for m in entry.get("materializations") or ():
        if not m.get("path") or not materialization_is_written(kind, entry, m):
            continue
        p = Path(m["path"])
        if occupied(p) or paths.refuses_writes(p.parent) is not None:
            return True
    return False


def occupied_refusal(path) -> str:
    """Why a write to `path` was refused by a directory there, and the move
    that clears it. Install, sync, heal and doctor word it alike."""
    return ("%s is a directory boost did not create — move it aside"
            % paths.tilde(path))


def occupied_targets() -> list[Path]:
    """Each recorded rule or workflow file path a directory now occupies.

    Doctor, heal and sync report these by name. No ``chmod`` clears one and no
    dir check sees it -- the dir it is in is fine -- so without this the
    install's warning was the only place it was ever said.
    """
    found: dict[Path, None] = {}
    for kind, entries in (("rule", lockfile.installed_rules()),
                          ("workflow", lockfile.installed_workflows())):
        for entry in entries.values():
            for m in entry.get("materializations") or ():
                p = Path(m.get("path") or "")
                if (m.get("path") and materialization_is_written(kind, entry, m)
                        and occupied(p)):
                    found.setdefault(p)
    return list(found)


def _refused_materializations(existing: dict | None, linked: list[str],
                              refused: list[dict],
                              source_sha: str | None = None,
                              declared: list[str] | None = None
                              ) -> list[dict]:
    """The rows to record beside this run's writes: refused, then untouched.

    An agent whose directory refused the write is still recorded, as a row
    marked ``unwritable``. Rules and workflows derive their re-install scope
    from these rows (:func:`preserved_agent_scope`), so an agent with no row
    silently dropped out of every later `sync`, `reinstall` and `update`: the
    first refusal became permanent. The row keeps it in scope, and
    :func:`sync_plan` reads it as a materialization still to write.

    A refused row replaces that agent's old one. The old file, if any, is
    still on disk at the same path, and the new row still names that path, so
    uninstall removes it.

    An untouched row is marked ``stale`` when ``source_sha`` says the source
    changed: its file is the old version, and it still hashes to its own
    old digest, so every check passed it. `boost update` with windsurf
    disabled recorded v2 over windsurf's v1 copy, and after re-enabling it
    doctor, verify, drift and sync all said in sync. A stale row stays stale
    until a run writes that agent.

    Only within ``declared``, the ``--agent`` narrowing in force: a row for an
    agent outside it is kept so uninstall can remove its file, but no `sync`
    will ever write that agent, so a ``stale`` flag there was a remedy that
    never converged -- doctor said "run `boost sync`", sync re-wrote only the
    narrowed agents, and doctor said it again. Such a row loses the flag.
    """
    done = linked + [r["agent"] for r in refused]
    kept = _untouched_materializations(existing, done)
    changed = bool(existing and source_sha is not None
                   and existing.get("sha256") != source_sha)
    out: list[dict] = []
    for m in kept:
        row = {k: v for k, v in m.items() if k != "stale"}
        if declared and m.get("agent") not in declared:
            out.append(row)
        elif changed or m.get("stale"):
            out.append(row | {"stale": True})
        else:
            out.append(row)
    return refused + out


def _copy_skill(src: Path, dest: Path, *, within: Path | None = None,
                keep_old: list[Path] | None = None) -> list[str]:
    """Copy a skill tree into ``dest`` atomically; return the links skipped.

    Symlinks follow :func:`_copy_tree`: one that stays inside the skill is
    copied as a link, one out of it is copied as what it points at only when
    that is inside ``within`` (the tap clone; anywhere when None, as for a
    local import), and anything else is skipped and named in the returned
    lines.

    The old rmtree-then-copytree left a window where a crash destroyed the
    previous good copy before the new one finished — on a reinstall/upgrade the
    skill would vanish while the lock file still referenced it, so store and
    lock disagreed. Instead stage the full copy in a temp dir on the same
    filesystem, then swap it in with directory renames: the existing copy stays
    untouched until the new one is complete, the failure window shrinks to two
    fast renames, and a failed swap rolls back to the original.

    With ``keep_old`` a list, the moved-aside original is appended to it
    rather than deleted, so a caller whose later step fails can swap it back
    (:func:`_restore_old_copy`); deleting it is then that caller's job.
    """
    dest = Path(dest)
    # Staging needs to *write* next to dest, and a store that cannot be written
    # is an ordinary, fixable condition — a sandboxed shell, a synced folder, a
    # store owned by another user. It used to escape as a raw PermissionError
    # from tempfile.mkdtemp, so boost answered `boost install <skill>` with a
    # stack trace ending in a temp path nobody recognises, and filed a crash
    # report for it. Name the directory instead: that is the whole diagnosis.
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        # util.TEMP_PREFIX, not ``.<name>.tmp``: the name embedded made the
        # staging dir 13 bytes longer than the skill's own, so a name that
        # fits as a store dir could not be staged.
        staged = Path(tempfile.mkdtemp(dir=str(dest.parent),
                                       prefix=util.TEMP_PREFIX))
    except PermissionError as exc:
        raise BoostError(
            "cannot write to the skill store at %s" % dest.parent,
            hint="check that you own the directory and it is writable "
                 "(`ls -ld %s`); a sandboxed shell is the usual cause"
                 % dest.parent) from exc
    except OSError as exc:
        # Not a permissions problem — disk full, read-only mount, name too
        # long. Say which, rather than describing every one of them as denied.
        raise BoostError(
            "cannot stage a copy in %s: %s"
            % (dest.parent, exc.strerror or exc),
            hint="free space or fix the mount, then re-run") from exc
    backup = None
    skipped: list[str] = []
    try:
        try:
            skipped = _copy_tree(Path(src), staged,
                                 None if within is None else Path(within))
        except shutil.Error as exc:
            # A file that vanished or could not be read mid-copy. It reached
            # the crash handler as a repr of every failing path; one path is
            # the diagnosis.
            rows = exc.args[0] if exc.args and isinstance(exc.args[0], list) else []
            first = rows[0][0] if rows and rows[0] else str(exc)
            n = max(len(rows), 1)
            raise BoostError(
                "could not copy %s into the skill store: %d file%s failed"
                % (dest.name, n, "" if n == 1 else "s"),
                hint="first: %s" % first) from None
        # is_symlink() as well as exists(): a dangling symlink is still
        # something in the way that has to be moved aside.
        if dest.exists() or dest.is_symlink():
            backup = staged.with_name(staged.name + ".old")
            os.replace(dest, backup)      # move the old copy aside (atomic)
        os.replace(staged, dest)          # swap the new copy in (atomic)
    except BaseException:
        if backup is not None and not (dest.exists() or dest.is_symlink()):
            os.replace(backup, dest)      # swap-in failed: restore the original
        shutil.rmtree(staged, ignore_errors=True)
        if backup is not None and (backup.exists() or backup.is_symlink()):
            _remove_backup(backup)
        raise
    if backup is not None:
        if keep_old is None:
            _remove_backup(backup)
        else:
            keep_old.append(backup)
    return skipped


def _restore_old_copy(old: Path, dest: Path) -> None:
    """Put the moved-aside original back at ``dest``, the new copy aside.

    Renames only, so an interrupt mid-restore cannot lose both copies: the
    new copy goes to its own ``.new`` name before the old one comes back.
    """
    if os.path.lexists(dest):
        aside = old.with_name(old.name[:-len(".old")] + ".new")
        os.replace(dest, aside)
        try:
            os.replace(old, dest)
        except BaseException:
            # Put the new copy back: install's cleanup deletes ``old`` next,
            # and an empty ``dest`` would lose both copies.
            os.replace(aside, dest)
            raise
        _remove_backup(aside)
    else:
        os.replace(old, dest)


#: The names a skill copy never takes, at any depth (:data:`util.IGNORED`).
_COPY_IGNORE = shutil.ignore_patterns(*sorted(util.IGNORED))


def _copy_tree(src: Path, dst: Path, within: Path | None) -> list[str]:
    """Copy ``src`` to ``dst`` without following a link out of ``within``.

    ``copytree`` with its default ``symlinks=False`` follows every link, so a
    skill's link to ``../../shared/helper.py`` — a file the sparse tap clone
    may not hold — failed the whole install with a raw ``shutil.Error``, and
    a link to ``/etc/passwd`` or ``~/.ssh`` would have copied that into the
    store. Instead:

    * a link that resolves to something inside ``src`` is copied as the link
      it is, so the copy's relative links lead into the copy;
    * one that resolves elsewhere inside ``within`` is copied as its target,
      a file or a directory (whose own links obey the same test);
    * one that leads nowhere, or out of ``within``, is skipped, and the line
      returned says which and why. With ``within`` None there is no bound:
      a local import copies what the user's own links lead to, as it always
      did.
    """
    src_real = os.path.realpath(src)
    root = None if within is None else os.path.realpath(within)
    escaping: list[Path] = []

    def ignore(d: str, names: list[str]) -> set[str]:
        skip = _COPY_IGNORE(d, names).copy()
        for n in names:
            p = Path(d, n)
            if n in skip or not p.is_symlink():
                continue
            # copytree copies a link verbatim, so it stays one only when its
            # spelling leads into the copy too: not absolute (that points back
            # at the tap) and not via the skill dir's own name (``../x/f``),
            # which the store may spell differently.
            spelled = os.readlink(p)
            lexical = os.path.normpath(os.path.join(
                os.path.relpath(d, src), spelled))
            if (Path(spelled).is_absolute()
                    or lexical.split(os.sep)[0] == os.pardir
                    or not p.exists()
                    or not _inside(os.path.realpath(p), src_real)):
                skip.add(n)
                escaping.append(p)
        return skip

    shutil.copytree(src, dst, symlinks=True, ignore=ignore, dirs_exist_ok=True)
    skipped: list[str] = []
    for p in escaping:
        rel = Path(os.path.relpath(p, src)).as_posix()
        target = os.path.realpath(p)
        shown = "%s → %s" % (rel, os.readlink(p))
        if not Path(target).exists():
            skipped.append("%s leads to nothing" % shown)
        elif root is not None and not _inside(target, root):
            skipped.append("%s leads outside the tap" % shown)
        elif Path(target).is_dir():
            if _inside(src_real, target):
                # A link to an ancestor of the skill: copying it copies the
                # skill into itself, without end.
                skipped.append("%s loops back over the skill" % shown)
            else:
                skipped += ["%s/%s" % (rel, s) for s in
                            _copy_tree(Path(target), dst / rel, within)]
        else:
            shutil.copy2(target, dst / rel)
    return skipped


def _remove_backup(backup: Path) -> None:
    """Delete a moved-aside copy, whatever kind of thing it is.

    ``shutil.rmtree`` on a symlink raises, and with ``ignore_errors=True`` it
    fails silently — so when the displaced ``dest`` was a symlink rather than a
    real directory, the ``.boost-XXXXXXXX.old`` staging link was left behind
    forever. Harmless-looking, but it accumulates in the user's agent dirs and
    every one of them is a dangling pointer.
    """
    if backup.is_symlink():
        backup.unlink(missing_ok=True)
    else:
        shutil.rmtree(backup, ignore_errors=True)


def declared_mcp_servers(skill_dir) -> list[dict]:
    """MCP servers an installed skill declares — ``mcpdecl.servers_for`` rows.

    Reads the installed copy's ``SKILL.md`` frontmatter and its bundled
    ``.mcp.json`` sidecar, if either is present. Best-effort by design: an
    unreadable file yields no rows rather than failing an install that has
    otherwise already succeeded.
    """
    from . import frontmatter, mcpdecl
    skill_dir = Path(skill_dir)
    meta: dict = {}
    with contextlib.suppress(OSError):
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8",
                                                  errors="replace")
        meta, _body = frontmatter.parse(text)
    sidecar = None
    with contextlib.suppress(OSError):
        sidecar = (skill_dir / mcpdecl.SIDECAR).read_text(encoding="utf-8",
                                                          errors="replace")
    return mcpdecl.servers_for(meta, sidecar)


def project_mcp_sidecar(base) -> Path:
    """The repo's ``.mcp.json`` — where a project-scoped install records servers.

    The committable file agents already read, which is the whole point of
    project scope over shelling out to ``<host> mcp add``: a registration that
    lives here is reviewable in a diff and arrives with a teammate's clone,
    where one made through a host CLI exists only on the machine that ran it.
    """
    from . import mcpdecl
    return Path(base) / mcpdecl.SIDECAR


def _load_sidecar(path: Path) -> tuple[dict | None, str | None]:
    """``(doc, None)``, ``(None, None)`` if absent, ``(None, error)`` if unusable.

    An existing ``.mcp.json`` that does not parse, is not an object, or holds a
    non-object ``mcpServers`` is *refused*, not rebuilt: the file is rewritten
    whole from the parsed view, so rebuilding a trailing-comma file from an
    empty one silently discarded every server the user had configured. The
    error names the file and the cause (:func:`jsonstate.read_object`'s
    contract, which ``settings.json`` and ``config.json`` already follow), and
    callers write nothing while it is set. Not raising keeps the other half of
    the old contract: by the time this runs the skill is already on disk, so a
    damaged file must not turn a completed install into a traceback.
    """
    from . import jsonstate, mcpdecl
    doc, err = jsonstate.read_object(path)
    if err is not None:
        return None, err
    if doc is not None:
        problem = mcpdecl.sidecar_problem(doc)
        if problem is not None:
            return None, "%s: %s" % (path, problem)
    return doc, None


def _write_sidecar(path: Path, doc: dict) -> bool:
    """Write the sidecar as indented JSON. False if it could not be written.

    Best-effort on the way OUT as well as in. ``_load_sidecar`` already refuses
    to turn a corrupt file into a traceback, but the write is the half that runs
    *after* the skill is materialized, the lock is written and the journal is
    logged — so an unwritable ``.mcp.json`` (read-only checkout, a root-owned
    file, a full disk) would crash an install that had already succeeded. The
    caller reports what was actually recorded rather than what was declared, so
    a failure here is visible instead of silent.
    """
    import json
    try:
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
        return True
    except OSError:
        return False


def record_project_mcp(base, rows, skill: str,
                       ) -> tuple[list[str], str | None]:
    """Record ``skill``'s declared MCP servers -> ``(added, error)``.

    Never overwrites a server already present — one the user configured by hand,
    or one another skill declared first — and never creates the file for a skill
    that declares nothing registrable, so a repo gains an ``.mcp.json`` only
    when there is genuinely something in it. ``error`` is set, and the file left
    byte-for-byte as it was, when an existing ``.mcp.json`` cannot be read as
    one (see :func:`_load_sidecar`), and when the write itself fails. So
    ``([], None)`` for a registrable declaration means every server was
    already in the file.
    """
    from . import mcpdecl as _decl
    if not _decl.registrable(rows):
        return [], None
    path = project_mcp_sidecar(base)
    existing, err = _load_sidecar(path)
    if err is not None:
        return [], err
    doc, added = _decl.merge_into(existing, rows, skill)
    if added and not _write_sidecar(path, doc):
        # Nothing was recorded; do not claim otherwise.
        return [], "%s: could not be written" % path
    return added, None


def register_project_mcp(base, rows, skill: str) -> list[str]:
    """:func:`record_project_mcp`'s names alone."""
    return record_project_mcp(base, rows, skill)[0]


def _project_declarers(base) -> tuple[dict[str, str], bool]:
    """``({server: skill}, complete)`` over the skills the project lock holds.

    Each remaining skill's declarations are read from its installed copy —
    every materialization is tried, and each lock path goes through
    :func:`scopes.resolve_in_base`, because the lock is committed input. When
    several skills declare one server the alphabetically first owns it.
    ``complete`` is False when some entry has no readable copy on this machine
    (a teammate's clone that never ran ``boost sync``): what it declares is
    then unknown.
    """
    from . import scopes
    owners: dict[str, str] = {}
    complete = True
    for name, entry in sorted(projectlock.installed(base).items()):
        dirs = [scopes.resolve_in_base(base, m.get("path") or "")
                for m in (entry or {}).get("materializations") or []
                if isinstance(m, dict)]
        found = next((d for d in dirs
                      if d is not None and (d / "SKILL.md").is_file()), None)
        if found is None:
            complete = False
            continue
        for row in declared_mcp_servers(found):
            owners.setdefault(row["name"], name)
    return owners, complete


def forget_project_mcp(base, skill: str) -> tuple[list[str], str | None]:
    """Remove the servers boost recorded for ``skill`` -> ``(removed, error)``.

    Marker-keyed entries only, so a hand-configured server is never touched,
    and reference-counted by declaration: a server another skill still in the
    project lock declares stays, re-marked to that skill, so the last
    declarer's uninstall is the one that removes it. Call this after the
    skill's own lock row is gone. When some remaining skill's declarations
    cannot be read, nothing is removed — a leaked entry is recoverable, and a
    teammate's server deleted from a committed file is not.

    Writes nothing when nothing changes, which keeps an uninstall from
    rewriting — and reformatting — a file it has no claim on, and nothing at
    all over an unreadable file (``error`` says why).
    """
    from . import mcpdecl as _decl
    path = project_mcp_sidecar(base)
    existing, err = _load_sidecar(path)
    if err is not None:
        return [], err
    if existing is None:
        return [], None
    keep, complete = _project_declarers(base)
    if not complete:
        return [], None
    doc, removed = _decl.strip_owned(existing, skill, keep)
    # Compare the servers, not the documents: ``strip_owned`` always sets the
    # key, so a file with no (or a null) ``mcpServers`` would otherwise be
    # rewritten — and reformatted — by an uninstall that owns nothing in it.
    if doc[_decl.SERVERS_KEY] == (existing.get(_decl.SERVERS_KEY) or {}):
        return removed, None
    if not _write_sidecar(path, doc):
        return [], "%s: could not be written" % path
    return removed, None


def unregister_project_mcp(base, skill: str) -> list[str]:
    """:func:`forget_project_mcp`'s names alone."""
    return forget_project_mcp(base, skill)[0]


def _enforce_capability_policy(name: str, source_md: Path) -> None:
    """Raise if the item's declared/detected capabilities are denied by policy.

    Runs on the item's own source Markdown (a skill's ``SKILL.md``, or a rule's
    or workflow's source file) before anything is materialized — a skill, rule
    or workflow is alike a bundle of instructions the agent will execute (a
    rule is merged into a context file read every session; a workflow becomes
    a slash command or subagent run verbatim), and least-privilege means the
    user's policy can refuse any of them for a capability they don't grant. A
    no-op unless the policy names a denied capability.
    """
    from . import frontmatter
    try:
        raw = source_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    meta, _body = frontmatter.parse(raw)
    caps = policy.check_capabilities(meta, raw)
    if caps:
        raise BoostError(
            "policy blocks installing %s: %s" % (name, "; ".join(caps)),
            hint="relax it with `boost policy` (denied_capabilities), or "
                 "install a skill that needs less")


def _resolve_base(scope: str, base) -> Path | None:
    """Directory a project-scoped install materializes under (the repo), or None
    for user scope.

    Delegates to :func:`scopes.resolve_base`, which walks up for the nearest
    project root — running this from ``src/deep/nested`` must write into the
    repo, not scatter a ``.claude/`` three directories down.
    """
    return scopes.resolve_base(scope, base)


def _require_project_base(scope: str, base, what: str) -> Path | None:
    """``_resolve_base``, but a project scope that resolves to nothing is fatal.

    ``resolve_base`` returns ``None`` for project scope in ``$HOME`` with no
    repo above it. Passing that through would quietly materialize into the
    user's own config while the CLI reported "this repo" — the two scopes
    silently becoming one place, which is the outcome the split exists to
    prevent. Refuse instead.
    """
    resolved = _resolve_base(scope, base)
    if scope == scopes.SCOPE_PROJECT and resolved is None:
        raise BoostError(
            "there is no project here to install %s into" % what,
            hint="cd into a repo, or drop --local to install for your user")
    if scope == scopes.SCOPE_PROJECT:
        # A store dir, a tap clone or a bare repo has no project marker, so
        # the unmarked fallback would claim it; writing there corrupts it.
        scopes.refuse_managed(resolved)
    return resolved


def _refuse_stranded_base(scope: str, base, kind: str, name: str) -> None:
    """Refuse to re-materialize a rule or workflow into a repo that is gone.

    An explicit ``base`` reaches ``_install_rule``/``_install_workflow`` from
    a lock record (``reinstall``, ``update``, ``sync``), never from a fresh
    ``install --local``, which resolves the cwd. When that directory no
    longer exists the repo was deleted, and writing into it recreated it --
    a ``.cursor/`` and a ``CLAUDE.local.md`` in a folder the user removed --
    while the command reported a repair. :func:`scopes.stranded` is the same
    question asked of the row; this is its write-side half.

    Rules and workflows only. A project *skill* is recorded in the repo's own
    lock, so no record of one can outlive the repo it names.
    """
    if scope == scopes.SCOPE_PROJECT and scopes.stranded(
            {"scope": scope, "base": base}):
        raise BoostError(
            "%s %s was installed into %s, which no longer exists"
            % (kind, name, paths.tilde(Path(base))),
            # Ordered, not "or": the record is what blocks the reinstall
            # (`_check_scope_conflict` refuses a second row under the name),
            # so `install --local` in a new checkout only runs after it goes.
            hint="`boost uninstall %s` drops the record; then, to have it in "
                 "a new checkout, run `boost install %s --local` there"
                 % (name, name), wrap=True)


def _lock_location(entry: dict) -> str:
    """Describe where a rule/workflow lock ``entry`` lives, for an error message."""
    if entry.get("scope") == scopes.SCOPE_PROJECT:
        base = entry.get("base")
        return "project scope (%s)" % base if base else "project scope"
    return "user scope"


def _check_scope_conflict(name: str, existing: dict | None, scope: str,
                          resolved_base: Path | None, force: bool) -> None:
    """Refuse a name collision across install scopes before it corrupts state.

    Rule/workflow lock entries are keyed by bare name with no per-scope
    storage (unlike skills, which get their own project lock) — so a name
    already recorded under a *different* scope/base is never "the same
    install, seen twice". Letting ``force`` through in that case would
    overwrite one scope's lock entry with the other's, orphaning the first
    scope's materializations with nothing left in the lock to uninstall them.
    Refuse the cross-scope case outright, ``force`` or not; only a same-scope,
    same-base match falls through to the ordinary already-installed check.
    """
    if not existing:
        return
    if scopes.stranded(existing):
        # Checked before the scope comparison: a stranded row can never be
        # "the same install" (its base is gone, a fresh one resolves the cwd),
        # and the generic refusal below said "uninstall it there first" about
        # a directory that no longer exists. The record is the whole
        # obstacle, and `boost uninstall` drops it from anywhere.
        raise BoostError(
            "%s was installed --local into %s, which no longer exists"
            % (name, paths.tilde(Path(existing["base"]))),
            hint="`boost uninstall %s` drops that record, then re-run this "
                 "install" % name, wrap=True)
    requested_base = str(resolved_base) if resolved_base is not None else None
    if existing.get("scope", "user") == scope and existing.get("base") == requested_base:
        if not force:
            raise BoostError("%s is already installed" % name,
                            hint="`boost reinstall %s` to force" % name)
        return
    if existing.get("scope", "user") == scope == scopes.SCOPE_PROJECT:
        # Same scope, another repo. Calling that "a different scope" sent the
        # user looking for a scope mismatch that was not there: the limit is
        # the one-row-per-name lock, so a rule or workflow can be --local in
        # one repo per machine (a skill, with a lock in each repo, cannot hit
        # this).
        raise BoostError(
            "%s is already installed --local in %s, and a %s can be installed "
            "--local into only one repo per machine"
            % (name, paths.tilde(Path(existing["base"]))
               if existing.get("base") else "another repo",
               existing.get("kind") or "rule or workflow"),
            hint="`boost uninstall %s` from that repo first; --force cannot "
                 "move it" % name, wrap=True)
    raise BoostError(
        "%s is already installed at %s" % (name, _lock_location(existing)),
        hint="uninstall it there first — a different scope cannot force-overwrite it")


def _count_others(installed: dict, name: str) -> int:
    """How many skills ``installed`` holds besides ``name``: the count an
    install of ``name`` is weighed against for ``max_skills``."""
    return len(installed) - (1 if name in installed else 0)


def refuse_case_collision(name: str, recorded: dict, where: str = "") -> None:
    """Refuse ``name`` when ``recorded`` holds a skill it differs from only
    by case.

    On a case-insensitive filesystem (macOS, Windows) ``Foo`` and ``foo`` are
    one store dir and one link per agent, so installing the second wrote over
    the first: ``--force`` replaced Foo's files with foo's, the lock recorded
    both as healthy, and uninstalling either deleted the dir both rows name.
    Refused on every filesystem, and whatever ``force`` says, so the answer
    does not depend on which machine asks — and ``--force`` is never the hint,
    because what it would replace is a different skill.
    """
    folded = name.casefold()
    other = next((k for k in recorded if k != name and k.casefold() == folded),
                 None)
    if other is not None:
        raise BoostError(
            "%s differs only by case from %s, which is already installed%s; "
            "on a case-insensitive filesystem they would share one store dir"
            % (name, other, where),
            hint="`boost uninstall %s` first if %s should replace it"
                 % (other, name),
            wrap=True)


def check_existing(entry: dict, *, force: bool = False, scope: str = "user",
                   base=None, kind: str | None = None) -> dict | None:
    """The lock record an install of ``entry`` would replace, or its refusal.

    Every "already installed" / "is pinned" / cross-scope refusal the install
    paths make about what is *already there*, in one place, so that
    ``install --dry-run`` asks the very same question before it prints a plan.
    The preview used to read the lock itself and call any hit an "upgrade",
    exiting 0 where the run it described refused with exit 1.

    ``kind`` defaults to the entry's own; ``scope``/``base`` are what
    :func:`install` is called with. Returns the existing record (``None`` for a
    fresh install); a returned record therefore means ``force`` let it through.
    """
    kind = kind or entry.get("kind", "skill")
    name = util.check_item_name(entry["name"], kind)
    if kind in ("rule", "workflow"):
        resolved_base = _require_project_base(scope, base, "%s %s" % (kind, name))
        _refuse_stranded_base(scope, base, kind, name)
        existing = (lockfile.get_rule if kind == "rule"
                    else lockfile.get_workflow)(name)
        _check_scope_conflict(name, existing, scope, resolved_base, force)
        return existing
    if scope == scopes.SCOPE_PROJECT:
        resolved_base = _require_project_base(scope, base, name)
        if resolved_base is None:         # _require_project_base already raised
            raise BoostError("there is no project here to install %s into" % name)
        refuse_case_collision(name, projectlock.installed(resolved_base),
                              " in this project")
        existing = projectlock.get_skill(resolved_base, name)
        if existing and not force:
            raise BoostError(
                "%s is already installed in this project (v%s)"
                % (name, existing.get("version")),
                # Not `reinstall --local`: reinstall has no scope flag (it
                # would exit 2), and bare `reinstall` reads the user lock only,
                # so it answers "not installed" for the very skill this is about.
                hint="`boost install %s --local --force` to force" % name)
        return existing
    refuse_case_collision(name, lockfile.installed())
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("%s is already installed (v%s)" % (name, existing.get("version")),
                        hint="`boost reinstall %s` to force, `boost update` to upgrade" % name)
    return existing


def _require_writable(name: str) -> None:
    """Refuse an install before its first write if its record cannot be kept.

    The lock file lives in the store, so an install that cannot write there
    can copy a skill, link it, or merge a rule into ``~/.claude/CLAUDE.md``
    and then fail at the record: files on disk that `boost uninstall` and
    `boost sync` never see. Asking first costs one ``access`` call, and names
    the directory to fix rather than a temp path deep in a traceback.

    The store only. An agent dir that refuses is that agent's problem: the
    install skips it and records the skip (:func:`link_agents`,
    :func:`_refused_target`), so the agents that can be written are, and
    `boost sync` writes the rest once the dir allows it.
    """
    d = paths.store_dir()
    block = paths.refuses_writes(d)
    if block is not None:
        raise BoostError("cannot install %s: %s"
                         % (name, paths.not_writable(d, block)),
                         hint="%s, then re-run" % paths.write_remedy(block))


def _refuse_unrecorded(name: str, existing: dict | None, force: bool,
                       retry: str | None = None) -> str | None:
    """Refuse to copy over a store dir the lock file does not record.

    Such a dir is a skill the user put in the store by hand, another tool's
    copy, or one a lost lock forgot, and :func:`_copy_skill` replaces it
    whole — for the first, deleting the only copy there is. Nothing that
    installs knew to look: ``existing`` is ``None`` for every one of them,
    which reads exactly like a fresh install. ``force`` is the user saying
    to replace it anyway, and ``retry`` names the command that does.

    Returns the workflow whose skill copy a forced install is taking over,
    for the caller to disown with :func:`_drop_skill_copy_row` once every
    other refusal has passed. Dropping it here would let a later refusal
    (policy, capability, an unwritable store) leave the copy unowned, and
    `boost sync` would then adopt it and link it beside the workflow.
    """
    owner = None if existing else skill_copy_owner(name)
    if owner is not None:
        if force:
            # The user asked for the skill. The workflow keeps its own files
            # and loses only its copy, and its next install finds a skill by
            # this name and skips the copy rather than writing over it.
            return owner
        raise BoostError("%s is already in the store at %s, as the skill copy "
                         "of workflow %s" % (name, paths.tilde(
                             skill_store_dir(name)), owner),
                         hint=("%s replaces it; the workflow keeps its own "
                               "files" % retry if retry else
                               "`boost install %s --force --no-as-skill` takes "
                               "the copy out of the store" % owner),
                         wrap=True)
    if existing or force:
        return None
    dest = skill_store_dir(name)
    if not os.path.lexists(dest):
        return None
    if lockfile.check().problem in ("corrupt", "schema"):
        hint = ("the lock file cannot be read — `boost replay` restores the "
                "lock that knows whose it is")
    else:
        hint = "`boost sync` says whose it is, and records it if it is yours"
        if retry:
            hint += "; %s replaces it" % retry
    raise BoostError("%s is already in the store at %s, and the lock file "
                     "does not record it" % (name, paths.tilde(dest)),
                     hint=hint, wrap=True)


def _refuse_self_installing(entry: dict) -> None:
    """Refuse to half-copy an item whose repo installs itself.

    Checked before the kind dispatch because the property belongs to the repo,
    not the item: every kind it ships has the same missing build step. Naming
    the upstream command is the whole point — a refusal that only says "no"
    leaves the user exactly where `boost install` pretending would have.
    """
    cmd = config.self_installing_command(entry.get("tap") or "")
    if not cmd:
        return
    raise BoostError(
        "%s comes from %s, which installs itself — boost would copy its "
        "Markdown and leave a skill that cannot run"
        % (entry.get("name", "?"), entry.get("tap", "?")),
        hint="run the registry's own installer: %s" % cmd, wrap=True)


def record_rebuilt(name: str, row: dict) -> None:
    """Write skill ``name``'s rebuilt ``row``, carrying the user state of the
    row as it is *under the lock*.

    An install's ``existing`` row is read by :func:`check_existing` before a
    copy that can take seconds, and carrying ``tags`` and ``pinned`` from it
    dropped a `boost tag` or `pin` landed meanwhile. ``row`` holds the derived
    fields; ``installed_at``, ``pinned``, ``tags`` and
    :func:`carried_user_state` come from the held row here, at the write.
    """
    def put(lock: dict) -> None:
        held = lock["skills"].get(name) or {}
        new = row.copy()
        new["installed_at"] = held.get("installed_at", row["installed_at"])
        new["pinned"] = bool(held.get("pinned"))
        new["tags"] = held.get("tags", [])
        new.update(carried_user_state(held))
        lock["skills"][name] = new
    lockfile.mutate(put)


def carried_user_state(existing: dict | None) -> dict:
    """The user-set lock fields a re-install must carry that it does not rebuild.

    Every lock builder below recomputes an entry from scratch, so a field it
    does not name is dropped. Audited, the fields split three ways:

    * **user state, carried** — ``installed_at``, ``pinned``, ``tags``,
      ``only_agents`` (via :func:`declared_agent_scope`), a workflow's
      ``as_skill``, and ``commit_pin``, which is the one this returns. Each
      builder carried the others by name and none carried ``commit_pin``, so
      ``boost reinstall`` of a commit-pinned item erased the integrity pin
      without a word and ``boost verify`` went on passing.
    * **derived, rebuilt** — ``version``, ``tap``, ``source_*``, ``commit``,
      ``sha256``, ``updated_at``, ``agents``, ``refused_agents``,
      ``source_updated_at``, ``materializations``, a workflow's ``foreign``.
    * **reset on purpose** — ``quarantined`` (the content was just put back)
      and ``sidelined_by`` (the install relinks, and ``agents`` is measured
      from disk, so keeping the flag would describe links that exist).
    """
    pin = (existing or {}).get("commit_pin")
    return {"commit_pin": pin} if pin else {}


def project_carried_state(existing: dict | None) -> dict:
    """The user-set fields a project skill's rebuilt lock row must carry.

    :func:`carried_user_state` for the project lock: ``pinned`` (which
    ``boost pin`` writes there) plus a ``commit_pin``. Only set flags are
    carried, so an unpinned row stays free of a ``pinned: false`` key.
    """
    carried = carried_user_state(existing)
    if (existing or {}).get("pinned"):
        carried["pinned"] = True
    return carried


def set_project_pin(base, name: str, pinned: bool) -> dict | None:
    """Set or clear ``pinned`` on ``name``'s row in ``base``'s project lock.

    Returns the row as written, or ``None`` when the project lock has no
    such skill. Releasing a version pin releases a commit pin with it, the
    same rule ``boost unpin`` applies at user scope.
    """
    if projectlock.get_skill(base, name) is None:
        return None     # checked unlocked first, so a miss creates nothing
    written: list[dict] = []

    def edit(lock: dict) -> bool:
        # Re-read under the lock: another process may have dropped the row,
        # or added others that a stale copy written back would erase.
        entry = lock["skills"].get(name)
        if entry is None:
            return False
        if pinned:
            entry["pinned"] = True
        else:
            entry.pop("pinned", None)
            entry.pop("commit_pin", None)
        written.append(entry)
        return True
    projectlock.mutate(base, edit)
    return written[0] if written else None


def project_skills(start=None) -> tuple[Path | None, dict]:
    """``(base, skills)`` for the project the cwd (or ``start``) is in.

    The same walk ``boost list`` makes: :func:`scopes.resolve_base` for the
    project root, then that root's own ``.boost/skill-lock.json``. ``base`` is
    ``None`` — and ``skills`` empty — where no project directory applies
    (``$HOME`` is never one), so a caller can tell "no project" from "a
    project with nothing installed".
    """
    pbase = scopes.resolve_base(scopes.SCOPE_PROJECT, start=start)
    if pbase is None:
        return None, {}
    return pbase, projectlock.installed(pbase)


def reapply_recorded_holds(name: str, want: dict) -> bool:
    """Put a recorded skill row's holds back onto its freshly installed row.

    ``replay rollback`` reinstalls a removed skill from its tap, and an
    install of a name with no lock row starts from nothing: the ``pinned``
    flag and the ``commit_pin`` the user set are not carried, because there
    is no existing row to carry them from (:func:`carried_user_state`). This
    writes both back from ``want`` — the row the snapshot recorded.

    Returns True when the recorded commit pin no longer matches the commit
    just installed, i.e. ``boost verify`` will now flag the skill; the pin is
    restored regardless, since dropping it would make ``verify`` pass on a
    commit the user never accepted.
    """
    pinned = bool(want.get("pinned"))
    commit_pin = want.get("commit_pin")
    if not (pinned or commit_pin):
        return False
    row = lockfile.get_skill(name)
    if row is None:
        return False
    if pinned:
        row["pinned"] = True
    if commit_pin:
        row["commit_pin"] = commit_pin
    lockfile.set_skill(name, row)
    return bool(commit_pin) and row.get("commit") != commit_pin


def install(entry: dict, force: bool = False,
            only_agents: list[str] | None = None,
            scope: str = "user", base=None,
            via: str | None = None,
            as_skill: bool | None = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict.

    ``scope`` is ``"user"`` (default — the canonical store, symlinked into the
    agent's user config dirs) or ``"project"`` (real directories inside the
    current repo). Every kind honors it.

    ``via`` names the caller for the journal entry (e.g. ``"protocol"`` for a
    one-click install), the same way a tap's journal entry already can — see
    ``registry.add``'s ``via=`` kwarg to ``journal.log``. ``None`` means an
    ordinary ``boost install``, and is dropped from the event like any other
    ``None``-valued field (``journal.log``).

    ``as_skill`` is a workflow's ``--as-skill``/``--no-as-skill``; ``None``
    replays what the lock recorded, else follows ``workflows_as_skills``. Any
    other kind ignores it.
    """
    scopes.check_scope(scope)
    _refuse_self_installing(entry)
    if scope != scopes.SCOPE_PROJECT:
        # Before anything is copied or linked: lockfile.write refuses a
        # corrupt lock too, but by then the files would be on disk unrecorded.
        lockfile.refuse_corrupt()
    kind = entry.get("kind", "skill")
    if kind == "rule":
        return _install_rule(entry, force=force, only_agents=only_agents,
                             scope=scope, base=base, via=via)
    if kind == "workflow":
        return _install_workflow(entry, force=force, only_agents=only_agents,
                                 scope=scope, base=base, via=via,
                                 as_skill=as_skill)
    if kind != "skill":
        raise BoostError(
            "%s is a %s, which boost does not know how to install" % (entry["name"], kind),
            hint="known kinds: skill, rule, workflow")
    if scope == scopes.SCOPE_PROJECT:
        return _install_project_skill(entry, force=force, only_agents=only_agents,
                                      base=base, via=via)
    name = entry["name"]
    existing = check_existing(entry, force=force, kind="skill")

    # An upgrade or reinstall replaces a skill already counted, so it adds
    # none: at exactly max_skills, `boost update` declined every upgrade.
    violations = policy.check_install(
        entry, _count_others(lockfile.installed(), name))
    if violations:
        raise BoostError("policy blocks installing %s: %s" % (name, "; ".join(violations)),
                        hint="inspect with `boost policy list`")

    disowned = _refuse_unrecorded(name, existing, force,
                                  retry="`boost install %s --force`" % name)
    src = source_dir_for(entry)
    _enforce_capability_policy(name, src / "SKILL.md")
    dest = skill_store_dir(name)
    _require_writable(name)
    if disowned:
        _drop_skill_copy_row(disowned)
    tap = registry.get(entry["tap"])
    # Dated before linking: it is what decides whether a plugin's copy of the
    # same name is newer, and so whether Claude Code gets boost's link. And
    # dated before copying: on a shallow tap this is a network fetch of up to
    # a minute, and a Ctrl-C in it used to leave a store copy no lock row
    # recorded, which the rerun then refused to touch.
    dated = source_updated_at(entry["tap"], entry.get("rel_dir", "."))
    fresh = not dest.exists()
    old: list[Path] = []
    try:
        res = _copy_link_record(entry, name, src, dest, tap, existing,
                                only_agents, dated, keep_old=old)
    except BaseException:
        # Nothing recorded it, so nothing else would ever clean it up: undo a
        # fresh install whole, so a plain rerun starts from where it began.
        if fresh and lockfile.get_skill(name) is None:
            with contextlib.suppress(OSError):
                unlink_agents(name)
            with contextlib.suppress(OSError):
                util.rmtree(dest)
        # An upgrade whose new row never landed swaps the old copy back. Left
        # in place, the new copy no longer matched the row's sha256, so every
        # later `update`, `verify` and `drift` called it a local edit.
        elif old and lockfile.get_skill(name) == existing:
            with contextlib.suppress(OSError):
                _restore_old_copy(old[0], dest)
        raise
    finally:
        for b in old:
            if os.path.lexists(b):
                _remove_backup(b)
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"), via=via)
    return res


def _copy_link_record(entry: dict, name: str, src: Path, dest: Path, tap,
                      existing: dict | None, only_agents: list[str] | None,
                      dated: str | None, *,
                      keep_old: list[Path] | None = None) -> InstallResult:
    """:func:`install`'s copy, link and lock-row steps, in that order."""
    skipped = _copy_skill(src, dest, within=tap.path, keep_old=keep_old)
    res = link_agents(name, only=preserved_agent_scope(only_agents, existing),
                      updated_at=dated)
    res.skipped_links = skipped
    res.upgraded = existing is not None
    res.score, _ = util.score_skill(dest)
    res.mcp_servers = declared_mcp_servers(dest)

    now = util.now_iso()
    record_rebuilt(name, {
        "version": entry.get("version", "0.0.0"),
        "tap": entry["tap"],
        # Where the tap came from, so a drift hint can re-tap it after
        # `untap` drops the config row: the name alone is not a spec.
        "tap_url": tap.url,
        "source_dir": entry.get("rel_dir", "."),
        "commit": gitutil.head_commit(tap.path),
        "sha256": util.sha256_dir(dest),
        # record_rebuilt carries the held one, with pinned/tags/commit_pin.
        "installed_at": now,
        "updated_at": now,
        "quarantined": False,
        # `agents` is what IS linked; `only_agents` is what the user ASKED for.
        # sync needs the second: it links a skill into every enabled agent, and
        # without a record of the request it cannot tell a deliberate `--agent`
        # narrowing from a skill that simply predates a newly enabled agent.
        #
        # Read back off disk rather than taken from `res.linked`, which is only
        # what THIS run linked. A narrowing re-install (`--agent cursor
        # --force`) links cursor and *skips* the others without unlinking them,
        # so recording res.linked made `agents` describe the request while the
        # other symlinks lived on — a divergence no boost command could see.
        "agents": linked_agents(name),
        "only_agents": declared_agent_scope(only_agents, existing),
        # The agents whose dir refused the link, so `install --force` retries
        # them once the dir is fixed (preserved_agent_scope), and those whose
        # link could not be looked at, so uninstall does not forget it.
        **({"refused_agents": refused} if (refused := unrecorded_agents(name, res))
           else {}),
        **({"source_updated_at": dated} if dated else {}),
    })
    return res


def _install_project_skill(entry: dict, force: bool = False,
                           only_agents: list[str] | None = None,
                           base=None, via: str | None = None) -> InstallResult:
    """Materialize a skill into the repo itself, once per enabled agent.

    Unlike a user install there is no canonical store and no symlink. Each agent
    gets a real copy at ``<repo>/.claude/skills/<name>`` so the tree can be
    committed and a teammate's ``git clone`` brings the skill with it — a
    symlink pointing into *this* machine's ``~/.agents/skills`` would arrive
    dangling. The cost is duplication across agent dirs, which is the right
    trade: repos are cheap, and a checked-in file that only works on the author's
    laptop is worse than no file at all.

    The record goes in the project's own lock, never the user's.
    """
    from . import gitutil
    name = entry["name"]
    resolved_base = _require_project_base(scopes.SCOPE_PROJECT, base, name)
    if resolved_base is None:             # _require_project_base already raised
        raise BoostError("there is no project here to install %s into" % name)
    # Before anything is copied: projectlock.write refuses a corrupt lock too,
    # but by then the copies would be on disk unrecorded.
    projectlock.refuse_corrupt(resolved_base)

    existing = check_existing(entry, force=force, scope=scopes.SCOPE_PROJECT,
                              base=resolved_base, kind="skill")

    violations = policy.check_install(
        entry, _count_others(projectlock.installed(resolved_base), name))
    if violations:
        raise BoostError("policy blocks installing %s: %s" % (name, "; ".join(violations)),
                        hint="inspect with `boost policy list`")

    src = source_dir_for(entry)
    _enforce_capability_policy(name, src / "SKILL.md")
    explicit_agents = only_agents is not None
    only_agents = preserved_agent_scope(only_agents, existing)
    # agents_for_scope, not enabled_agents: project scope puts each agent under
    # a repo-local dotdir, and Antigravity's user layout is two levels deep with
    # no known project path, so it is excluded rather than given an invented
    # `<repo>/antigravity-cli/`. The dotdir itself comes from
    # agents.project_dotdir rather than from this dir, because a dir that can
    # move at runtime must not move the repo path — see that function.
    targets = [(agent, scopes.skill_target(
                    skills_dir, name, base=resolved_base,
                    dotdir=agents.project_dotdir(agent, skills_dir)))
               for agent, skills_dir in narrow_project_agents(
                   agents.agents_for_scope(resolved_base), only_agents, name,
                   explicit=explicit_agents).items()]

    # Refuse to write through a symlink that leaves the repo. An agent dir like
    # ``.claude/skills`` is committed, so a hostile clone can ship it as a
    # symlink to ``~/.ssh`` and the copy below would land on the far side.
    # Checked for every target up front — before existence, force, or any write
    # — so a single escaping dir aborts the whole install rather than writing
    # part of it outside the project first.
    #
    # And refuse to write through a symlink that stays *inside* it. A committed
    # ``<repo>/.cursor -> config/cursor`` is an ordinary layout, not an attack,
    # but it is byte-identical on disk to ``.claude/skills -> ../src``, so
    # ``uninstall_project`` will not delete through it — and writing a copy
    # that uninstall cannot reach orphaned it and dropped the lock row anyway.
    # ``scopes.ensure_spelled`` asks the same question uninstall asks, so the
    # two halves cannot disagree about a row; see it for the options weighed.
    for _agent, dest in targets:
        scopes.ensure_in_base(resolved_base, dest)
        scopes.ensure_spelled(resolved_base, dest)

    # Refuse to clobber a directory boost did not put there. In user scope the
    # store is boost's alone, but here the destination is inside someone's repo
    # — a same-named hand-written skill is a real possibility, and overwriting
    # it would destroy uncommitted work with no warning.
    if not existing:
        squatters = [str(d) for _agent, d in targets if d.exists()]
        if squatters and not force:
            raise BoostError(
                "%s already exists in this project and boost did not install it: %s"
                % (name, ", ".join(sorted(squatters))),
                hint="move it aside, or `boost install %s --local --force` to "
                     "overwrite it" % name)

    materializations: list[dict] = []
    linked: list[str] = []
    # `narrow_project_agents` above refuses an empty set, so there is always a
    # first target — the result fields below (`sha256`, `dest`, the score, the
    # MCP scan) all read one real directory and used to be reachable with None.
    first: Path = targets[0][1]
    within = registry.get(entry["tap"]).path
    skipped: list[str] = []
    for agent, dest in targets:
        skipped = _copy_skill(src, dest, within=within)
        # Relative, because this record is committed and read on machines where
        # the absolute path does not exist.
        materializations.append(
            {"agent": agent, "path": scopes.relative_to_base(resolved_base, dest)})
        linked.append(agent)

    # A filtered reinstall (`--force --agent cursor`) refreshes only the agents
    # it names. Carrying the untouched ones forward keeps the lock describing
    # everything that is actually on disk — dropping them would leave real
    # directories in the repo that no record claims, so uninstall would skip
    # them and sync would call them orphans.
    kept = _untouched_materializations(existing, linked)
    materializations.extend(kept)
    all_agents = linked + [m["agent"] for m in kept if m.get("agent")]

    now = util.now_iso()
    tap = registry.get(entry["tap"])
    projectlock.set_skill(resolved_base, name, {
        "kind": "skill",
        "version": entry.get("version", "0.0.0"),
        "tap": entry["tap"],
        "tap_url": tap.url,
        "source_dir": entry.get("rel_dir", "."),
        "commit": gitutil.head_commit(tap.path),
        "sha256": util.sha256_dir(first),
        "scope": scopes.SCOPE_PROJECT,
        "installed_at": (existing or {}).get("installed_at", now),
        "updated_at": now,
        "agents": all_agents,
        "materializations": materializations,
    # A forced re-install (`boost reinstall`) of a pinned project skill must
    # leave it pinned: the row is rebuilt from scratch, and a flag it does not
    # name is a pin `boost update` silently stops honouring.
    } | project_carried_state(existing))
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"),
                scope=scopes.SCOPE_PROJECT, via=via)

    res = InstallResult(name=name, dest=first, kind="skill")
    res.skipped_links = skipped
    res.linked = linked
    res.upgraded = existing is not None
    res.scope = scopes.SCOPE_PROJECT
    res.score, _ = util.score_skill(first)
    res.mcp_servers = declared_mcp_servers(first)
    # Project scope registers into the repo's own .mcp.json rather than leaving
    # it to the command layer's `<host> mcp add` offer, which is user-scoped and
    # would put a machine-wide registration behind a --scope project install.
    # Recorded here so it lands with the skill and reverses with it.
    res.mcp_recorded, res.mcp_error = record_project_mcp(
        resolved_base, res.mcp_servers, name)
    return res


def project_materialized(name: str, base) -> tuple[str, dict] | None:
    """The user-lock rule or workflow row ``base``'s project owns — or None.

    The two kinds a project lock cannot hold, looked up where they actually
    live. Ownership is :func:`scopes.owns`, the same predicate ``list --local``
    filters with, so the command that shows a row and the command that removes
    it cannot disagree about whose it is.

    **Ownership is tested before the name is resolved anywhere else.**
    ``lockfile.find_any`` would be the obvious lookup and is the wrong one
    here: it answers with the first *section* that holds the name, so a
    user-scope skill called ``x`` outranks a project rule called ``x`` that
    this repo owns, and ``--local`` would refuse to remove the row it can see
    in ``list --local``. Rules before workflows only to fix an order; a name
    in both sections is already ambiguous for bare ``uninstall``, which
    resolves it the same way.

    No ``base is None`` short-circuit, deliberately: :func:`scopes.owns`
    answers ``False`` for it, so a guard here would be a branch no input can
    reach — a falsification pass deleted one and every test still passed,
    which is the definition of a line that is not doing anything. The cost of
    leaving it out is two dict lookups on a path that then returns None.
    """
    for kind, get in (("rule", lockfile.get_rule),
                      ("workflow", lockfile.get_workflow)):
        row = get(name)
        if row and scopes.owns(row, base):
            return kind, row
    return None


def _not_in_this_project(name: str) -> BoostError:
    """``uninstall --local``'s refusal, worded from where the item really is.

    One sentence covered three states. It is **true** in all three — a rule
    in the user's own config really is not installed in this project — and
    useless in two, because it reports the one fact the reader already has
    and withholds the one they need. Its hint sends them to ``boost list
    --local``, which correctly shows nothing, so the message and the remedy
    agree with each other and not with the machine. Each branch now names the
    scope it found and the command that removes it from there, because the
    item *is* removable and only the flag naming where it lives was not.

    **No ``base`` parameter**, though the caller has one resolved. Every
    branch is decided by :func:`lockfile.find_any`, which searches the user
    lock as a whole and answers with the first *section* holding the name.
    That is wider than what ``--local`` just rejected:
    :func:`project_materialized` put ``scopes.owns`` only to the rules and
    workflows sections, so a row this reports can be a **skill** no ownership
    test has seen. Which is right for a message whose whole job is to say
    where the item is *instead* — the row's own ``scope`` decides the wording,
    and a user-scope skill is named as one. A parameter nothing reads is one
    no test can pin — a mutation of it is unkillable by construction — so it
    is not taken.
    """
    found = lockfile.find_any(name)
    if found is not None:
        kind, row = found
        if row.get("scope") == scopes.SCOPE_PROJECT:
            # Owned by some other checkout — `owns` already said not this one.
            # The recorded base is named: it is the user's own lock, and a
            # reader who cannot see which repo has it cannot act on this.
            return BoostError(
                "%s is a %s installed in %s, not in this project"
                % (name, kind, row.get("base") or "another project"),
                hint="remove it from there, or with `boost uninstall %s`"
                     % name)
        return BoostError(
            "%s is a %s installed at user scope, not in this project" % (name, kind),
            hint="remove it with `boost uninstall %s` (no --local)" % name)
    # Genuinely absent. Byte-identical to what this raised before — the one
    # state where naming where the item is instead is no help, because it is
    # nowhere.
    return BoostError("%s is not installed in this project" % name,
                      hint="see what is with `boost list --local`")


def project_skill_targets(base, name: str) -> set[Path]:
    """Every path a project install of ``name`` could legally have written.

    :func:`_install_project_skill` writes exactly
    ``<base>/<dotdir>/<skills dir>/<name>``, once per agent, so the legal set is
    small and *derivable* — which is the point. :func:`uninstall_project` reads
    its paths out of a committed lock file and so must decide "is this mine?"
    from the agent table rather than from the record being checked.

    Built from :func:`agents.known_agents` filtered on ``project_scope``, and
    deliberately **not** on ``enabled``. An agent turned off after the install
    still has its directory in the repo, and a legal-set that forgot it would
    turn ``uninstall`` into a command that silently leaves real directories
    behind — trading a delete bug for an orphan bug. Disabling an agent stops
    boost writing there; it does not stop boost cleaning up what it wrote.

    Derived from *this* machine's config, which has a cost worth stating: the
    project lock is committed and read on other people's machines, so any drift
    between the config that wrote a row and the config that reads it refuses a
    directory a real install wrote. An agent deleted from ``config.json``, one
    hand-added on a teammate's machine but not here, one whose ``dir`` was
    renamed since — all three leave the copy in the repo rather than removing
    it. That is deliberate and it is the fail-closed direction: the user is
    told which row was skipped *and* what boost removes here, so the drift is
    on screen and the directory can go by hand. The other way round, boost
    deletes a path it can no longer explain — and the alternative that would
    cover drift (checking the path's *shape* rather than deriving it) reads the
    dotdir back out of the lock, which is the attacker-controlled input this
    whole function exists not to trust.
    """
    out: set[Path] = set()
    for agent, spec in agents.known_agents().items():
        if not spec.get("project_scope"):
            continue
        skills_dir = spec["dir"]
        try:
            out.add(scopes.skill_target(
                skills_dir, name, base=base,
                dotdir=agents.project_dotdir(agent, skills_dir)))
        except BoostError:
            # An unusable skill name is the *caller's* problem to report, not
            # a reason for the legal set to be wrong. Nothing matches it.
            return set()
    return out


def uninstall_project(name: str, base=None) -> dict:
    """Remove a project-scoped skill: its per-agent copies and its lock entry.

    Every recorded path is re-derived and checked against the set of paths an
    install could have produced (:func:`project_skill_targets`) — the lock is a
    committed file anyone with merge rights can edit, so a path out of it is
    input, not truth.

    Containment inside the project was the whole guard and is not enough:
    ``{"path": "src/core"}`` is inside the base, so it passed, and the repo's
    own source tree was removed under a command the user typed with boost
    having already said the path was safe. Being *inside the project* is the
    weaker property; being *a path this install writes* is the real one, and
    it is derivable.

    Derivable, and then checked twice, because a path is a string and a place.
    The string must be in the derived set, and the walk to it must not be
    redirected by a committed symlink at an ancestor — ``.claude/skills -> src``
    makes the legal spelling denote ``src/<name>``, so a set-membership test
    alone passes it *by construction*. The first revision of this change
    shipped with exactly that open. :func:`scopes.parent_matches_spelling` is
    the second half.

    Rows boost will not act on come back in three lists, because the remedy
    differs. ``refused`` is a contained row that is not one of the paths an
    uninstall removes here. ``escaped`` is one containment stopped outright —
    absolute, climbing out with ``..``, or sitting on a symlink that resolves
    out of the repo — which may well be a path an install writes, with the lie
    in the filesystem rather than in the string. ``redirected`` is the third
    and the quiet one: a row *in* the derived set whose walk is bent by a
    committed symlink at an ancestor. None is deleted and all three are
    reported; an escaped row used to be dropped in silence, and a redirected
    one used to be reported as ``refused``, which printed "not a path boost
    removes here" directly above a list containing that exact string.

    A ``redirected`` row is one install no longer writes. It used to: install
    gated on :func:`scopes.ensure_in_base` alone, which is containment only,
    so ``boost install --local`` wrote straight through an in-repo
    ``<repo>/.cursor -> config/cursor`` and recorded the row it spelled.
    Uninstall will not delete through that redirect, because a committed
    symlink is input: the benign layout and the attack
    (``.claude/skills -> ../src``) are byte-identical on disk, and no test
    distinguishes the intent behind them. Install now refuses the same rows
    (:func:`scopes.ensure_spelled`, the same predicate), so one reaches here
    only from a lock written before that, or a symlink committed after the
    install — ``boost doctor`` names both. The copy is left behind and the
    message says so by path.

    The lock entry goes in all four cases (see the ``refused`` note in the
    body), so the command still exits 0 on an all-refused run. That is also
    why a redirected row does not hold the entry open: an attacker commits a
    redirect as easily as a doctored path, so keeping it would be the same
    denial of service by another route. ``uninstall`` has no ``--json``, so
    the warning lines are the whole signal a caller gets.

    **A rule or workflow gets none of those guards, and that is correct.**
    A project lock holds a ``skills`` key and nothing else, so an
    ``install --local`` of the other two kinds materializes into the repo but
    records itself in the *user* lock tagged ``scope``/``base``. Everything
    above exists because the project lock is a **committed** file that anyone
    with merge rights can edit — a path out of it is input. The user lock is
    not committed; it is the same file bare ``boost uninstall`` has always
    read, and :func:`_uninstall_rule` / :func:`_uninstall_workflow` are the
    same functions it has always called. So the fall-through adds no path
    boost could not already be asked to delete, and re-deriving a legal set
    for it would be ceremony over a threat that is not there.

    What ``--local`` does is **narrow** eligibility, never widen it:
    :func:`scopes.owns` admits only a row this repo claims, so a user-scope
    rule and another checkout's rule both stay put. Before this,
    ``list --local`` printed the rule and ``uninstall --local`` answered "not
    installed in this project" — so the flag that performed the install could
    not undo it, and said something false while refusing.
    """
    resolved_base = _resolve_base(scopes.SCOPE_PROJECT, base)
    if resolved_base is not None:
        # A corrupt lock reads as empty: say so, not "not installed here".
        projectlock.refuse_corrupt(resolved_base)
    entry = projectlock.get_skill(resolved_base, name) if resolved_base else None
    if not entry:
        owned = project_materialized(name, resolved_base)
        if owned is not None:
            owned_kind, owned_entry = owned
            return (_uninstall_rule if owned_kind == "rule"
                    else _uninstall_workflow)(name, owned_entry)
        raise _not_in_this_project(name)
    removed: list[str] = []
    refused: list[str] = []
    redirected: list[str] = []
    escaped: list[str] = []
    gone = 0
    legal = project_skill_targets(resolved_base, name)
    for m in entry.get("materializations") or []:
        row = str(m.get("path"))
        path = scopes.resolve_in_base(resolved_base, m.get("path"))
        if path is None:
            # Empty, absolute, climbing out with `..` — or spelled legally and
            # sitting on a symlink that resolves out of the repo, which
            # `contains` catches because it resolves. Containment already
            # stopped the delete; what was missing is saying so. This was the
            # one doctored row that produced *no* output at all, under a
            # change whose whole argument is that a silent survival teaches
            # the user nothing. Kept apart from `refused` because the two need
            # different words: this row may well be a path an install writes,
            # with the lie in the filesystem rather than in the string.
            escaped.append(row)
            continue
        # Identity, in two parts, because a path is a string *and* a place.
        #
        # The string must be one an install writes, compared **unresolved**,
        # and that is load-bearing rather than incidental: resolving both
        # sides reopens the hole this function closes. The legal path is
        # itself a repo path, so a commit can make `.claude/skills/<name>` a
        # *symlink* to `src/core` and file a row of `src/core`; both sides
        # then resolve to `<base>/src/core`, the row is accepted, and the
        # source tree is deleted again. Resolving is strictly weaker in the
        # benign direction too — a user's own `<repo>/my-link ->
        # .claude/skills/<name>` starts matching, and boost unlinks an alias
        # it never created.
        #
        # And the walk to it must not be redirected, which comparing strings
        # cannot tell on its own. `<repo>/.claude/skills` committed as a
        # symlink to `src` leaves the row `.claude/skills/<name>` *equal to
        # the legal path by construction* while denoting `src/<name>`:
        # `is_dir()` follows the ancestor happily and `rmtree` takes the
        # victim, which is this card's bug one component up. The leaf is
        # honest and the ancestor is not, so the leaf-only check sees nothing.
        # `scopes.parent_matches_spelling` walks the parent for real.
        #
        # Pinned by `test_a_legal_path_symlinked_at_an_in_repo_target_stays_a_
        # string`, `test_a_users_own_symlink_to_the_skill_dir_is_refused` and
        # `test_a_symlinked_skills_dir_does_not_redirect_the_delete`.
        #
        # The two halves fail differently and are reported differently. A row
        # outside the derived set is not a path an uninstall writes here. A row
        # *in* the set whose walk is redirected is the opposite — it is in
        # `expected` by construction, so folding it into `refused` printed "not
        # a path boost removes here" directly above a list containing that
        # exact string.
        if path not in legal:
            refused.append(row)
            continue
        if not scopes.parent_matches_spelling(resolved_base, row):
            redirected.append(row)
            continue
        # `resolve_in_base` checks containment against the *resolved* path but
        # returns the unresolved one, so a materialization recorded as a
        # symlink arrives here as a symlink. A link out of the project was
        # already refused above; one that stays inside is unlinked rather than
        # handed to `rmtree`, which refuses a link as its argument.
        #
        # The guard stays "a link or a directory" rather than becoming
        # `remove_path`'s "anything that is there". The old `is_dir()` skipped
        # a materialization naming a plain FILE, and `remove_path` would
        # delete it: `boost uninstall --local` reads these paths out of the
        # project lock, so widening what it will delete off a lock entry is a
        # separate question that has its own card, and this change — read the
        # link rather than through it — must not decide it by accident. A link
        # is still removed whatever it points at, because the link is boost's
        # and unlinking it leaves the target untouched.
        if not (path.is_symlink() or path.is_dir()):
            continue          # absent, or a plain file we did not create
        if not util.remove_path(path):
            continue          # vanished between the check and the call
        gone += 1
        # `removed` is the *agent* list, and a lock row need not name one. The
        # delete above is not gated on `agent` and must not be: an agentless
        # row at a legal path is still the skill's own directory. So the count
        # of what came off disk is tracked separately — gating the caller's
        # "removed from <repo>" line on the agent list told a user whose lock
        # had an agentless row that nothing had been removed, while the
        # directory was gone.
        if m.get("agent"):
            removed.append(m["agent"])
    projectlock.remove_skill(resolved_base, name)
    # Reverse exactly what the install recorded. Marker-keyed entries only, so a
    # server the user configured by hand — or one another skill still needs —
    # survives. Without this a skill tried once keeps launching its server for
    # every project that clones the repo.
    unregistered, mcp_error = forget_project_mcp(resolved_base, name)
    journal.log("uninstall", name, scope=scopes.SCOPE_PROJECT)
    return {"name": name, "unlinked": removed, "entry": entry,
            # How many paths actually came off disk, which `unlinked` does not
            # answer — see the `gone` note in the body.
            "removed_count": gone,
            "refused": refused,
            # In the legal set, but an ancestor of the row is a symlink, so the
            # walk to it is redirected. Its own list because the remedy is the
            # opposite of `refused`'s: this *is* a path boost writes, and the
            # spelling the user is shown still removes it by hand, since `rm`
            # follows the ancestor the way the install did.
            "redirected": redirected,
            # Rows the containment check stopped. Separate from `refused`
            # because the remedy differs: a refused row is not a path an
            # install writes, where an escaped one may be exactly that with a
            # symlink under it that leaves the repo.
            "escaped": escaped,
            # What an install writes *here*. The refusal message used to spell
            # the shape out as `<repo>/<agent dotdir>/skills/<name>`, which
            # hardcodes a leaf that comes from `spec["dir"]` — so for a renamed
            # skills dir it told the user their path was "not a path a project
            # install writes" directly above a shape that path matched. Naming
            # the derived set instead is true under any config, and it is what
            # puts config drift on screen.
            "expected": sorted(scopes.relative_to_base(resolved_base, p)
                               for p in legal),
            "mcp_unregistered": unregistered, "mcp_error": mcp_error,
            "kind": "skill",
            "scope": scopes.SCOPE_PROJECT, "base": str(resolved_base)}


def project_sync_plan(base=None) -> dict[str, list]:
    """Compare the project lock against what is actually on disk.

    Returns ``{missing, orphaned}``: lock entries whose directory is gone, and
    skill directories under the project's agent dirs that no lock entry claims.
    A teammate who clones the repo has the files but may be missing one an
    ``update`` added, so this is the repair list for a shared checkout.
    """
    plan: dict[str, list] = {"missing": [], "orphaned": []}
    resolved_base = _resolve_base(scopes.SCOPE_PROJECT, base)
    # No lock file means this directory does not use project scope at all. Bail
    # before the orphan scan, or every repo with a hand-written
    # ``.claude/skills/`` would be told it has "unclaimed" directories and
    # `boost sync` could never report a clean tree.
    if resolved_base is None or not projectlock.exists(resolved_base):
        return plan
    lock = projectlock.installed(resolved_base)
    for name, entry in lock.items():
        for m in entry.get("materializations") or []:
            path = scopes.resolve_in_base(resolved_base, m.get("path"))
            if path is None or not path.is_dir():
                plan["missing"].append((name, m.get("agent", "?")))
    # project_agents, and the declared dotdir: the scan must look exactly where
    # the install writes. Walking enabled_agents() reached `<repo>/antigravity-cli`,
    # a path project install never writes, and deriving the dotdir would miss
    # a relocated Codex's real `<repo>/.codex` — reporting nothing while a copy
    # sat there unreferenced.
    for agent, skills_dir in agents.project_agents().items():
        root = (scopes.agent_root(skills_dir, resolved_base,
                                  agents.project_dotdir(agent, skills_dir))
                / Path(skills_dir).name)
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if child.is_dir() and child.name not in lock:
                plan["orphaned"].append(str(child))
    return plan


def project_sync_apply(plan: dict[str, list], base=None) -> list[str]:
    """Re-materialize the project skills :func:`project_sync_plan` found missing.

    Orphans are reported but never deleted: an unclaimed directory in someone's
    repo is far more likely to be a hand-written skill than boost's litter, and
    a package manager that silently removes files it did not write is one nobody
    should run in their working tree.
    """
    actions: list[str] = []
    resolved_base = _resolve_base(scopes.SCOPE_PROJECT, base)
    if resolved_base is None:
        return actions
    # Group by skill, but keep WHICH agents are missing: these directories are
    # committed files a team edits in place, so repairing one agent must not
    # re-copy over the others. Re-installing the whole skill would silently
    # revert a teammate's edit to a file they had checked in.
    wanted: dict[str, list] = {}
    for name, agent in plan.get("missing", []):
        wanted.setdefault(name, []).append(agent)
    for name in sorted(wanted):
        entry = projectlock.get_skill(resolved_base, name) or {}
        tap_name = entry.get("tap")
        cat_entry, warning = _project_source(name, entry)
        if warning:
            actions.append(warning)
        if cat_entry and not _project_restorable(entry, cat_entry):
            actions.append(_project_moved(name))
            continue
        if cat_entry:
            try:  # noqa: FURB107 - per-item resilience in a loop (see PERF203)
                _restore_project_copies(resolved_base, name, entry, cat_entry,
                                        wanted[name])
                actions.append("re-materialized %s from %s" % (name, tap_name))
                continue
            except BoostError:
                pass
        actions.append(_project_gone(name))
    if actions:
        journal.log("sync", "%d project fixes" % len(actions))
    return actions


def _project_moved(name: str) -> str:
    return ("%s's tap source has moved since the project lock was written%s"
            "(`boost install --local %s --force` takes the new content and "
            "updates the lock)" % (name, _DECLINED_MARK, name))


def _project_restorable(entry: dict, cat_entry: dict) -> bool:
    """Whether the tap can still hand back what the project lock records.

    A repair restores the committed lock; it never moves it. Re-installing
    from the tap's HEAD did: one missing ``.cursor`` copy came back at the
    new version beside an untouched ``.claude`` copy at the old one, the lock
    was rewritten to the new commit, and `boost verify` then failed the copy
    nobody had touched. True when the tap still sits on the locked commit,
    or its source for this skill hashes to the locked ``sha256`` (the tap
    moved, this skill did not). The commit check comes first because it
    costs no materialize.
    """
    from . import gitutil
    locked_commit = entry.get("commit")
    if locked_commit and gitutil.head_commit(
            registry.get(cat_entry["tap"]).path) == locked_commit:
        return True
    locked_sha = entry.get("sha256")
    return bool(locked_sha) and _skill_source_sha(cat_entry) == locked_sha


def _project_policy_violations(resolved_base: Path, name: str,
                               cat_entry: dict) -> list[str]:
    """The install policy gate, applied to a sync repair.

    The install a repair replaced applied it, so a skill or tap blocklisted
    since the lock was written must not come back through `boost sync` — and
    the dry run asks the same question, so it does not promise a restore the
    run then refuses.
    """
    return policy.check_install(
        cat_entry, _count_others(projectlock.installed(resolved_base), name))


def _restore_project_copies(resolved_base: Path, name: str, entry: dict,
                            cat_entry: dict, missing: list) -> None:
    """Copy ``cat_entry``'s source back to the recorded paths ``missing``.

    Writes the directories and nothing else: no lock row (it already says
    what is there), no ``.mcp.json`` (the install registered it), and only
    the agents named, because the other copies are committed files a team
    edits in place. Every destination is checked before the first copy, the
    same two checks a project install makes. Raises :class:`BoostError`
    when there is nothing it may write.
    """
    violations = _project_policy_violations(resolved_base, name, cat_entry)
    if violations:
        raise BoostError("policy blocks restoring %s: %s"
                         % (name, "; ".join(violations)))
    src = source_dir_for(cat_entry)
    _enforce_capability_policy(name, src / "SKILL.md")
    dests: list[Path] = []
    for m in entry.get("materializations") or []:
        if m.get("agent", "?") not in missing:
            continue
        dest = scopes.resolve_in_base(resolved_base, m.get("path"))
        if dest is None or dest.is_dir():
            continue
        scopes.ensure_in_base(resolved_base, dest)
        scopes.ensure_spelled(resolved_base, dest)
        dests.append(dest)
    if not dests:
        raise BoostError("no recorded copy of %s to restore" % name)
    within = registry.get(cat_entry["tap"]).path
    for dest in dests:
        _copy_skill(src, dest, within=within)


def _project_gone(name: str) -> str:
    return "%s%s — run `boost update` or reinstall" % (name, _PROJECT_GONE_MARK)


def _project_source(name: str, entry: dict) -> tuple[dict | None, str | None]:
    """The catalog entry a project lock row would be restored from.

    Shared by :func:`project_sync_apply` and :func:`project_sync_preview`, so a
    dry run decides "restorable" exactly as the run does: `heal --dry-run`
    promised to re-materialize a copy whose tap was gone, exited 0, and the run
    then reported the source gone and exited 1.
    """
    tap_name = entry.get("tap")
    if not tap_name or tap_name == "local":
        return None, None
    try:
        from . import catalog
        matches = [e for e in catalog.find(name)
                   if e["tap"] == tap_name and e.get("kind", "skill") == "skill"]
        return catalog.select_lock_source(matches, entry)
    except BoostError:
        return None, None


def project_sync_preview(plan: dict[str, list], base=None) -> list[str]:
    """What :func:`project_sync_apply` would do with ``plan``, writing nothing.

    A copy with no resolvable source gets the same unrepaired line the run
    prints, so :func:`is_unrepaired` marks it and a dry run fails over it too.
    """
    lines: list[str] = []
    resolved_base = _resolve_base(scopes.SCOPE_PROJECT, base)
    if resolved_base is None:
        return lines
    wanted: dict[str, list] = {}
    for name, agent in plan.get("missing", []):
        wanted.setdefault(name, []).append(agent)
    for name in sorted(wanted):
        entry = projectlock.get_skill(resolved_base, name) or {}
        cat_entry, warning = _project_source(name, entry)
        if warning:
            lines.append(warning)
        if cat_entry and not _project_restorable(entry, cat_entry):
            lines.append(_project_moved(name))
        elif cat_entry and not _project_policy_violations(
                resolved_base, name, cat_entry):
            lines.append("would re-materialize project skill %s → %s from %s"
                         % (name, ", ".join(wanted[name]), entry.get("tap")))
        else:
            lines.append(_project_gone(name))
    return lines


def narrow_project_agents(scoped: dict, only_agents, name: str,
                          *, explicit: bool) -> dict:
    """Apply an ``--agent`` narrowing to a project-scope skill's agent set.

    The skill-shaped twin of :func:`narrow_materializing`, extracted so the
    live install and `install --dry-run` refuse in the same words at the same
    point. They did not: the preview printed its "would install … into <repo>"
    header with zero ``copy →`` lines and exited 0 where the run raised, which
    is the one thing a preview must not do.

    ``scoped`` is `agents.agents_for_scope(base)` — agent name to its
    repo-local skills dir. Returns the kept subset, in the caller's order.
    """
    kept = {a: d for a, d in scoped.items() if not only_agents or a in only_agents}
    if not kept:
        # Same provenance problem `narrow_materializing` has, at the third
        # replay site. `preserved_agent_scope` has already turned a *recorded*
        # scope into `only_agents` by the time this runs, so the old "no
        # enabled agents" was wrong twice over: an agent narrowed away is
        # usually enabled, and attributing the narrowing to nothing at all left
        # the user with no way to tell a flag they typed from one the lock
        # replayed for them.
        known = agents.known_agents()
        if only_agents:
            listed = ", ".join(sorted(only_agents))
            why = ("--agent " + listed) if explicit \
                else "its recorded agents (%s)" % listed
            # The same `no_surface` split `narrow_materializing` makes, for the
            # same reason: at project scope the usual cause is `project_scope:
            # False` — an agent that is enabled and whose user-scope layout has
            # no repo-local equivalent — and telling that user to enable it
            # names a setting that is already true and would change nothing.
            no_surface = [n for n in only_agents
                          if n in known and known[n]["enabled"]]
            widen = ("widen with `boost install %s --local --force "
                     "--agent <name>`" % name)
            # No `no_surface` means every named agent is *disabled*, and then
            # widening is the wrong first move: `narrow_materializing` says
            # "enable one …, or widen …" on that same input, and the twins
            # disagreeing on one shape is how a user learns to distrust both.
            # The widen clause stays either way — a recorded scope is a thing
            # the user may never have typed.
            hint = ("%s has no repo-local skills path, so %s"
                    % (", ".join(sorted(no_surface)), widen)) if no_surface \
                else ("enable one with `boost config set "
                      "agents.<name>.enabled true`, or %s" % widen)
        else:
            why = "no enabled agent takes a project-scope skill"
            # Un-narrowed, so every candidate was dropped by the scope itself.
            # If some are enabled, enabling is not the remedy either. "at user
            # scope" rather than "without `--local`" because `--local` is an
            # alias for `--scope project`, and naming one spelling tells half
            # the users to drop a flag they did not pass.
            live = [n for n, spec in known.items() if spec["enabled"]]
            hint = ("no enabled agent has a repo-local skills path (%s) — "
                    "install at user scope instead" % ", ".join(sorted(live))
                    if live
                    else "enable one with "
                         "`boost config set agents.<name>.enabled true`")
        raise BoostError("no agent left to install %s into: %s" % (name, why),
                        hint=hint)
    return kept


def narrow_materializing(targets: dict, only_agents, name: str, kind: str,
                          *, explicit: bool) -> dict:
    """Apply an ``--agent`` narrowing to a rule/workflow target set, or refuse.

    An empty intersection is not an empty install: everything after the loop
    still runs, so `boost install <workflow> --agent codex` wrote a lock row
    with zero materializations, exited 0, and printed "(no enabled agents)"
    about an agent that is enabled. Nothing downstream could see it either —
    `sync_plan` asks ``any(... for m in materializations)`` and `any([])` is
    False, so doctor called the phantom fully materialized and uninstall
    removed nothing.

    `--agent` names a *known* agent, which is the only thing `_check_agents`
    can check; whether that agent takes this kind is per-kind and resolved
    here. So the error says which of the two it is.

    ``explicit`` is keyword-only and has no default on purpose. It defaulted to
    True, which is the very wording this argument exists to suppress, and both
    call sites pass it — so the default was a wrong answer waiting for a third
    caller to forget the argument, and it would have been wrong silently.

    ``explicit`` is False when the narrowing came from the lock rather than the
    command line. `preserved_agent_scope` replays a recorded scope before this
    runs, so the two are indistinguishable by the time the guard fires, and
    disabling the one agent a rule was installed for made `boost update` report
    ``--agent codex`` at a user who had typed no such flag. It still refuses —
    returning ``{}`` is what wrote the phantom row this guard exists to stop —
    but it says where the narrowing came from and how to widen it.

    The refusal is ``not kept``, not ``only_agents and not kept``: an empty
    target set is a phantom row whichever way it got empty. Guarding only the
    narrowing left the *config* route open — every rule-capable agent disabled,
    or every candidate ``skills_only``, or (for a workflow) every candidate
    ``workflows: false`` — where ``only_agents`` is None, the loop body never
    runs, and `set_rule`/`set_workflow` still write ``materializations: []``
    and exit 0. `_install_project_skill` has guarded its un-narrowed case since
    it was written; these two had not.
    """
    kept = {n: d for n, d in targets.items()
            if not only_agents or n in only_agents}
    if not kept:
        if not only_agents:
            raise BoostError(
                "no agent left to install %s %s into: no enabled agent takes a %s"
                % (kind, name, kind),
                hint="enable one with `boost config set agents.<name>.enabled true`")
        known = agents.known_agents()
        no_surface = [n for n in only_agents
                      if n in known and known[n]["enabled"]]
        listed = ", ".join(sorted(only_agents))
        hint = ("%s cannot take a %s — see `boost config get agents`"
                % (", ".join(sorted(no_surface)), kind) if no_surface
                else "enable one with `boost config set agents.<name>.enabled true`")
        if not explicit:
            hint += ", or widen with `boost install %s --force --agent <name>`" % name
        raise BoostError(
            "no agent left to install %s %s into: %s"
            % (kind, name, ("--agent " + listed) if explicit
               else "its recorded agents (%s)" % listed), hint=hint)
    return kept


def _refuse_shared_rule_file(name: str, path: Path) -> None:
    """Refuse a rules-dir file that is another installed rule's file.

    Two names that differ only by case (``alpha``, ``ALPHA``) map to one file
    on a case-insensitive filesystem, and a symlinked rules dir can alias two
    paths the same way. The second install wrote over the first rule's file,
    and uninstalling it deleted that file while the first rule's lock row
    still named it. Checked before any agent is written, so the refusal
    leaves every file and the lock as they were. Context-file rows are not
    compared: every rule shares ``CLAUDE.md`` and owns only its block there.
    """
    from . import rules
    if not os.path.lexists(path):
        return
    for other, entry in lockfile.installed_rules().items():
        if other == name:
            continue
        for m in entry.get("materializations") or ():
            if m.get("mode") == rules.MODE_CLAUDE or not m.get("path"):
                continue
            try:
                same = os.path.samefile(path, m["path"])
            except OSError:
                continue
            if same:
                raise BoostError(
                    "cannot install rule %s: %s is rule %s's file"
                    % (name, paths.tilde(path), other),
                    hint="the two names collide on this filesystem; "
                    "uninstall %s first, or keep it and skip %s"
                    % (other, name))


def _context_file_created(name: str, path: Path, prior: dict) -> bool:
    """Whether boost, not the user, made the context file at ``path``.

    Recorded on the row so uninstall deletes a file that its strip leaves
    empty only when boost created it; a file the user made, even an empty
    one, stays. A re-install finds the file it created already there, so the
    answer is carried from this rule's own row, and from any other rule's
    row at the same path, whose block is what made the file exist.
    """
    from . import rules
    if not os.path.lexists(path):
        return True
    if (prior.get(str(path)) or {}).get("created") is True:
        return True
    for other, entry in lockfile.installed_rules().items():
        if other == name:
            continue
        for m in entry.get("materializations") or ():
            if (m.get("mode") == rules.MODE_CLAUDE and m.get("created") is True
                    and m.get("path") == str(path)):
                return True
    return False


def _install_rule(entry: dict, force: bool = False,
                  only_agents: list[str] | None = None,
                  scope: str = "user", base=None,
                  via: str | None = None) -> InstallResult:
    """Materialize a rule into each enabled agent's native format.

    Cursor/Windsurf/Cline get a verbatim file drop in their ``rules/`` dir
    (frontmatter preserved — it is native rule metadata); Claude Code has no
    rules folder, so the rule merges into ``CLAUDE.md`` as an idempotent managed
    block. With ``scope="project"`` these land under the repo (and Claude uses
    ``CLAUDE.local.md``). Every materialization is recorded so ``uninstall``
    reverses exactly what was written.
    """
    import hashlib

    from . import frontmatter, gitutil, rules
    name = entry["name"]
    # Cheap precondition, checked before any tap or filesystem work: if there
    # is nowhere to put this, say so immediately. Also needed ahead of the
    # existing-install check below, which compares against this scope/base.
    resolved_base = _require_project_base(scope, base, "rule %s" % name)
    existing = check_existing(entry, force=force, scope=scope, base=base,
                              kind="rule")
    explicit_agents = only_agents is not None
    only_agents = preserved_agent_scope(only_agents, existing)

    violations = policy.check_install(entry, len(lockfile.installed()))
    if violations:
        raise BoostError("policy blocks installing %s: %s" % (name, "; ".join(violations)),
                        hint="inspect with `boost policy list`")

    tap = registry.get(entry["tap"])
    src = tap.path / entry.get("skill_md", "")
    if not src.is_file():
        raise BoostError("source for rule %s vanished from tap %s" % (name, tap.name),
                        hint="run `boost update %s`" % tap.name)
    _enforce_capability_policy(name, src)
    raw = src.read_text(encoding="utf-8", errors="replace")
    meta, body = frontmatter.parse(raw)
    claude_body = rules.render_claude_body(str(meta.get("name") or name), body)

    # The lock is what makes any write below undoable, so a store that
    # refuses it stops the install before the first one. A target dir that
    # refuses is that agent's problem only: it is skipped and recorded.
    _require_writable(name)
    materializations: list[dict] = []
    linked: list[str] = []
    unwritable: list[str] = []
    blocked: list[tuple[str, str]] = []
    conflicts: list[str] = []
    refused: list[dict] = []
    foreign: list[str] = []
    foreign_record: list[dict] = []
    prior = {m.get("path"): m for m in (existing or {}).get("materializations")
             or () if isinstance(m, dict)}
    targets = narrow_materializing(agents.materializing_agents(resolved_base),
                                    only_agents, name, "rule",
                                    explicit=explicit_agents)
    # A damaged block in any context file stops the install before the first
    # write. merge_block refuses it too, but mid-loop, after earlier agents'
    # files had landed with no lock row to undo them.
    for agent, skills_dir in targets.items():
        mode, path = rules.rule_target(
            agent, skills_dir, name, base=resolved_base,
            dotdir=agents.project_dotdir(agent, skills_dir))
        # Containment first: reading through an escaping symlink would name
        # a file outside the repo in the refusal and send the user to fix it.
        if resolved_base is not None:
            scopes.ensure_in_base(resolved_base, path)
        if mode != rules.MODE_CLAUDE:
            _refuse_shared_rule_file(name, path)
            continue
        try:
            text = util.read_user_text(path)
        except OSError:
            continue  # absent, or refused: the write loop handles both
        rules.require_well_formed(text, name, path)
    for agent, skills_dir in targets.items():
        mode, path = rules.rule_target(
            agent, skills_dir, name, base=resolved_base,
            dotdir=agents.project_dotdir(agent, skills_dir))
        # Project scope writes into the repo, so a committed agent dir could be
        # a symlink escaping it (see scopes.ensure_in_base). User scope writes
        # into the user's own ~/.claude, which they control — nothing to guard.
        if resolved_base is not None:
            scopes.ensure_in_base(resolved_base, path)
        # A rules dir is the user's as much as boost's: a file there that no
        # row of this rule records is theirs, as for a workflow's command.
        # A context file is shared by design and takes a managed block.
        if mode != rules.MODE_CLAUDE and _foreign_target(path, raw, set(prior)):
            foreign.append(str(path))
            foreign_record.append({"agent": agent, "mode": mode,
                                   "path": str(path)})
            continue
        created = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if mode == rules.MODE_CLAUDE:
                created = _context_file_created(name, path, prior)
                current = util.read_user_text(path) if path.exists() else ""
                # A context file is the user's: write through a symlink to
                # it and keep its mode (see util.write_user_file).
                util.write_user_file(
                    path, rules.merge_block(current, name, claude_body),
                    base=resolved_base)
                # Hash what `rules.read_block` will read back (the stripped
                # body), so `boost verify` can tell an edited block from ours.
                written = claude_body.strip("\n")
            else:
                util.atomic_write_text(path, raw)
                written = raw
        except OSError as err:
            if not _refused_target(err, path, unwritable, blocked,
                                   conflicts):
                raise
            refused.append({"agent": agent, "mode": mode, "path": str(path),
                            "unwritable": True})
            continue
        row = {"agent": agent, "mode": mode, "path": str(path),
               "sha256": hashlib.sha256(written.encode("utf-8")).hexdigest()}
        if created is not None:
            row["created"] = created
        materializations.append(row)
        linked.append(agent)

    # Carry forward the agents this run did not touch — the same reason the
    # project-scope skill path does it, but the stakes are higher here. A
    # rule's materialization is a managed block inside a file the user reads
    # every session (~/.claude/CLAUDE.md); dropping the record does not drop
    # the block, and `_uninstall_rule` is record-driven, so an unrecorded block
    # could never be removed by any boost command again.
    materializations.extend(_refused_materializations(
        existing, linked, refused,
        source_sha=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        declared=declared_agent_scope(
            only_agents if explicit_agents else None, existing)))
    # As for a workflow: an agent this run did not try keeps its foreign row.
    tried = {*linked, *(r["agent"] for r in refused),
             *(r["agent"] for r in foreign_record)}
    foreign_record += [r for r in foreign_rows(existing)
                       if r["agent"] not in tried]

    now = util.now_iso()
    lockfile.set_rule(name, {
        "kind": "rule",
        "version": entry.get("version", "0.0.0"),
        "tap": entry["tap"],
        "tap_url": tap.url,
        "source_file": entry.get("skill_md", ""),
        "commit": gitutil.head_commit(tap.path),
        "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "scope": scope,
        "base": str(resolved_base) if resolved_base is not None else None,
        "installed_at": (existing or {}).get("installed_at", now),
        "updated_at": now,
        # Same governance contract as a skill entry: a pin survives a forced
        # reinstall, quarantine does not — the reinstall just re-materialized
        # the content, so a surviving flag would be a lie.
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        **carried_user_state(existing),
        "materializations": materializations,
        # What the user asked for, beside what was written: the rows above
        # cannot say which, and :func:`preserved_agent_scope` replays this.
        **_declared_field(only_agents if explicit_agents else None, existing),
        **({"foreign": foreign_record} if foreign_record else {}),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"), via=via)

    res = InstallResult(
        name=name,
        dest=Path(materializations[0]["path"]) if materializations else paths.store_dir(),
        kind="rule", scan_text=raw)
    res.foreign = foreign
    res.linked = linked
    res.unwritable = unwritable
    res.blocked = blocked
    res.conflicts = conflicts
    res.upgraded = existing is not None
    res.scope = scope
    return res


def _removal_refused(name: str, path: Path) -> BoostError:
    """The named refusal for a removal under ``path`` that its dir forbids.

    Worded like every other refusal: a dotdir with no search bit is "not
    searchable" and needs ``u+wx``, where ``u+w`` changed nothing.
    """
    block = refusing_dir(path.parent)
    return BoostError("cannot uninstall %s: %s"
                      % (name, paths.not_writable(block, block)),
                      hint="`%s`, then uninstall again"
                      % paths.chmod_command(block))


@contextlib.contextmanager
def _refused_removal(name: str, path: Path):
    """Turn a locked agent dir into a named refusal, before the lock is touched.

    Uninstall removes what the lock records and then drops the record. A dir
    that refuses the removal used to escape as exit 70; raising here keeps
    the record, so running uninstall again after the `chmod` finishes it.
    """
    try:
        yield
    except PermissionError:
        raise _removal_refused(name, path) from None


def _remove_all_or_nothing(name: str, plan: list[tuple[Path, str | None]],
                           base=None) -> int:
    """Apply an uninstall's removals, or none of them. Returns how many files.

    ``plan`` holds ``(path, new_text)`` for each file to change: ``None`` to
    delete it, text to rewrite it -- ``""`` included, which empties a context
    file the user made rather than deleting it. Every dir is checked before the
    first change, because a refusal part-way left some agents' files gone and
    the lock still naming them, so a `boost sync` in between wrote them back.
    The per-file guard stays, for what ``os.access`` cannot foresee.

    Two rows can name one file (two enabled agents whose dirs resolve to one
    path), so the plan is de-duplicated on the resolved dir, not the resolved
    file, and a file already gone counts as removed.

    The count is **files**, after that de-duplication, and never ``len(plan)``.
    On the default agent table the two agree — a project rule measures five
    rows at five distinct paths, because ``rules.CONTEXT_FILES`` gives each
    context-file agent its own name there (``CLAUDE.local.md``,
    ``GEMINI.md``, ``AGENTS.md``) and Cursor and Windsurf take a rules dir
    each. They diverge on exactly what the de-duplication is for: two agents
    configured at one dir, or a dotdir that is a symlink to another, which
    ``path.parent.resolve()`` collapses. ``len(plan)`` would then tell the
    user boost removed a file it removed once. The caller reports "removed
    from <repo>" off this, the way :func:`uninstall_project` reports it off
    paths that came off disk rather than off the agent list.
    """
    once: dict[Path, tuple[Path, str | None]] = {}
    for path, text in plan:
        # The leaf resolves too: `GEMINI.md -> AGENTS.md` is one file.
        once.setdefault(Path(os.path.realpath(path.parent / path.name)),
                        (path, text))
    for path, text in once.values():
        if not os.access(str(path.parent), os.W_OK):
            raise _removal_refused(name, path)
        if text is not None or path.is_symlink():
            # A committed link re-pointed out of the repo is refused here,
            # before any file changes, not by the write part-way through.
            with _refused_removal(name, path):
                util.user_file_target(path, base)
    for path, text in once.values():
        with _refused_removal(name, path):
            if text is not None or path.is_symlink():
                # Rewritten in place through any link, so the user's link
                # survives uninstall; a linked file emptied stays, empty.
                util.write_user_file(path, text or "", base=base)
            else:
                path.unlink(missing_ok=True)
    return len(once)


def _present(path: Path) -> bool:
    """Whether a recorded file is there to remove, asked the same way on every
    Python.

    ``os.lstat`` raises PermissionError under a parent with no search bit, and
    the caller's :func:`_refused_removal` turns that into a named refusal.
    ``Path.exists`` and ``is_file`` raise there on 3.12 and 3.13 but answer
    False on 3.14, where uninstall then planned nothing, dropped the lock row
    and reported success over a file it never removed. A directory at the path
    is not a file boost wrote, so it is not one to remove.
    """
    try:
        st = os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return False
    return not stat.S_ISDIR(st.st_mode)


def _uninstall_rule(name: str, rule: dict) -> dict:
    """Reverse every materialization recorded for an installed rule."""
    from . import rules
    removed: list[str] = []
    plan: list[tuple[Path, str | None]] = []
    kept: list[str] = []
    for m in rule.get("materializations", []):
        path = Path(m.get("path", ""))
        with _refused_removal(name, path):
            if m.get("mode") == rules.MODE_CLAUDE:
                if _present(path) and path.exists():
                    text = util.read_user_text(path)
                    # A damaged block refuses the whole uninstall, before the
                    # lock is touched: strip_block declines to guess, and
                    # dropping the row anyway reported the rule removed while
                    # its text stayed live and no command could reach it.
                    rules.require_well_formed(text, name, path)
                    stripped = rules.strip_block(text, name)
                    # No block of ours (a refused write): no rewrite. An
                    # empty result is deleted only when the row says boost
                    # created the file; one the user made, even empty, stays.
                    # A row from before ``created`` was recorded keeps it.
                    if stripped != text:
                        plan.append((path, None if not stripped
                                     and m.get("created") is True
                                     else stripped))
            elif _present(path):
                # As for a workflow's file: one edited since boost wrote it
                # is the user's now. A row with no sha is removed as before.
                if m.get("sha256") and _file_sha(path) != m["sha256"]:
                    kept.append(str(path))
                    continue
                plan.append((path, None))
        if m.get("agent"):
            removed.append(m["agent"])
    gone = _remove_all_or_nothing(name, plan, base=rule.get("base"))
    lockfile.remove_rule(name)
    journal.log("uninstall", name)
    res = _materialized_result(name, removed, rule, "rule", gone)
    if kept:
        res["kept"] = kept
    return res


def quarantine_skill(name: str, entry: dict) -> tuple[list[str], dict[str, Path]]:
    """Withhold skill ``name`` from every agent that links it; keep the store.

    Returns ``(removed, blocked)``: the agents unlinked, and each agent whose
    link is, or may be, still there, mapped to the dir that has to change.
    :func:`unlink_agents` cannot say the second half. ``os.path.islink``
    answers False under a dotdir with no search bit, so quarantine reported
    "links removed" while the cursor link stayed on disk; and a link in a
    read-only skills dir raised mid-loop, exit 70, with some links gone and
    the lock still saying linked and not quarantined.

    Every agent is tried, and a blocked one does not stop the rest: refusing
    the whole quarantine, as uninstall refuses, would leave every agent
    loading the skill instead of one. The lock records the skill quarantined
    with the blocked agents in ``refused_agents``, which ``boost doctor``
    reads to keep naming them (the uninstall guard already reads the empty
    ``agents`` as every agent), and running quarantine again after the
    `chmod` finishes the job. Persists ``entry``; logs only a new quarantine, so a
    re-run does not reset ``quarantine --list``'s SINCE.
    """
    removed: list[str] = []
    blocked: dict[str, Path] = {}
    for agent, adir in agents.linking_agents().items():
        link = adir / name
        try:
            st = os.lstat(link)
        except PermissionError:
            blocked[agent] = refusing_dir(link.parent)
            continue
        except OSError:
            continue
        if not stat.S_ISLNK(st.st_mode):
            continue
        try:
            link.unlink()
        except PermissionError:
            blocked[agent] = refusing_dir(link.parent)
            continue
        removed.append(agent)
    fresh = not entry.get("quarantined")
    entry["quarantined"] = True
    entry["agents"] = []
    if blocked:
        entry["refused_agents"] = list(blocked)
    else:
        entry.pop("refused_agents", None)
    lockfile.set_skill(name, entry)
    if fresh:
        journal.log("quarantine", name)
    return removed, blocked


def quarantine_materialized(kind: str, name: str, entry: dict) -> list[str]:
    """Remove every recorded materialization of a rule/workflow, stashing it.

    The counterpart of skill quarantine's "store intact, links removed". These
    kinds have no store copy — the materialization IS the only artifact — so
    what gets removed is stashed on the lock entry and
    :func:`release_materialized` restores it byte-for-byte. Restoring from the
    stash rather than the tap matters: the tap may have moved (or vanished)
    since, and a release must never be a covert update.

    Persists the entry (``quarantined`` + ``quarantine_stash``) and returns the
    agents whose artifacts were removed.
    """
    from . import rules
    # Prior stash contents win over a fresh None: re-running after an
    # interrupted quarantine must never overwrite a saved copy with "the
    # artifact was already gone".
    prior = {m.get("path"): m.get("content")
             for m in entry.get("quarantine_stash") or []}
    prior_full_text = {m.get("path"): m.get("full_text")
                       for m in entry.get("quarantine_stash") or []}
    stash: list[dict] = []
    affected: list[str] = []
    for m in entry.get("materializations") or []:
        path = Path(m.get("path", ""))
        content: str | None = None
        full_text: str | None = None
        if m.get("mode") == rules.MODE_CLAUDE:
            if path.exists():
                # The whole file, not just the block: release_materialized
                # needs it to restore the block at its original position
                # rather than re-appending at end-of-file.
                full_text = util.read_user_text(path)
                content = rules.read_block(full_text, name)
                if content is not None:
                    # A file the removal will rewrite is checked against the
                    # repo now, before the stash is persisted or any file
                    # changes: refused by the write itself, it left earlier
                    # agents' files gone mid-loop.
                    util.user_file_target(path, entry.get("base"))
        elif path.is_file():
            content = path.read_text(encoding="utf-8")
        if content is None:
            content = prior.get(m.get("path"))
        if full_text is None:
            full_text = prior_full_text.get(m.get("path"))
        stash.append({**m, "content": content, "full_text": full_text})
        if m.get("agent"):
            affected.append(m["agent"])
    # Persist the stash BEFORE removing anything. A crash mid-removal then
    # leaves a lock that already says quarantined-with-stash — release still
    # restores, and re-running quarantine finishes the removal. The reverse
    # order could remove an artifact whose only copy died with the crash.
    entry["quarantined"] = True
    entry["quarantine_stash"] = stash
    lockfile.set_entry(kind, name, entry)
    for m in entry.get("materializations") or []:
        path = Path(m.get("path", ""))
        if m.get("mode") == rules.MODE_CLAUDE:
            if path.exists():
                text = util.read_user_text(path)
                if rules.read_block(text, name) is not None:
                    stripped = rules.strip_block(text, name)
                    if stripped or path.is_symlink():
                        util.write_user_file(path, stripped,
                                             base=entry.get("base"))
                    else:
                        path.unlink()  # file held only our block
        elif path.is_file():
            path.unlink()
            if lockfile.is_skill_copy(m):
                _rmdir_quietly(path.parent)
    journal.log("quarantine", name)
    return affected


def stale_quarantine_artifacts(name: str, entry: dict) -> bool:
    """True when a quarantined rule/workflow still has artifacts on disk.

    That is the signature of an interrupted quarantine (the stash persisted,
    the removal pass did not finish) — re-running
    :func:`quarantine_materialized` completes it without touching the stash.
    """
    from . import rules
    for m in entry.get("materializations") or []:
        p = Path(m.get("path", ""))
        if m.get("mode") == rules.MODE_CLAUDE:
            try:
                if p.exists() and rules.read_block(
                        p.read_text(encoding="utf-8"), name) is not None:
                    return True
            except OSError:
                continue
        elif p.is_file():
            return True
    return False


def release_materialized(kind: str, name: str, entry: dict,
                         skipped: list[str] | None = None) -> list[str]:
    """Restore what :func:`quarantine_materialized` removed, byte-for-byte.

    A stash record whose ``content`` is None (the artifact was already gone at
    quarantine time) is skipped — there is nothing truthful to restore.
    Persists the entry and returns the agents restored. A skill copy whose
    store dir something else took meanwhile is not restored, and its path is
    appended to ``skipped`` for the caller to name.
    """
    from . import rules
    # The stash names absolute paths under the row's base, so releasing a
    # `--local` row whose repo was deleted would recreate that repo exactly
    # the way `reinstall` did.
    _refuse_stranded_base(entry.get("scope", scopes.SCOPE_USER),
                          entry.get("base"), kind, name)
    # A damaged block in any context file refuses the release before the
    # first restore — merge_block would refuse it mid-loop, after earlier
    # agents' files were written with the entry still marked quarantined.
    for m in entry.get("quarantine_stash") or []:
        if m.get("content") is None or m.get("mode") != rules.MODE_CLAUDE:
            continue
        path = Path(m.get("path", ""))
        # And a link out of the repo, which the write would refuse just as
        # late.
        util.user_file_target(path, entry.get("base"))
        try:
            text = util.read_user_text(path)
        except OSError:
            continue  # absent: the restore writes it fresh
        rules.require_well_formed(text, name, path)
    restored: list[str] = []
    for m in entry.get("quarantine_stash") or []:
        content = m.get("content")
        if content is None:
            continue
        path = Path(m.get("path", ""))
        if lockfile.is_skill_copy(m) and not _stashed_copy_is_ours(path,
                                                                  content):
            # Something took the store dir while the workflow was held: a
            # skill installed by that name, or a dir the user made. The copy
            # is a convenience and never worth their file; the workflow
            # forgets it, and its next install says why there is none.
            entry["materializations"] = [
                r for r in entry.get("materializations") or ()
                if not lockfile.is_skill_copy(r)]
            if skipped is not None:
                skipped.append(str(path.parent))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if m.get("mode") == rules.MODE_CLAUDE:
            current = util.read_user_text(path) if path.exists() else ""
            full_text = m.get("full_text")
            # Byte-for-byte only holds when the surrounding text is exactly
            # what quarantine left behind — write the stashed file back
            # whole, restoring the block at its original position instead of
            # re-appending it. Any other surrounding text (the user edited
            # the file, or the stash predates this field) falls back to
            # merge_block's append.
            if full_text is not None and rules.strip_block(full_text, name) == current:
                util.write_user_file(path, full_text, base=entry.get("base"))
            else:
                util.write_user_file(
                    path, rules.merge_block(current, name, content),
                    base=entry.get("base"))
        else:
            util.atomic_write_text(path, content)
        if m.get("agent"):
            restored.append(m["agent"])
    entry["quarantined"] = False
    entry.pop("quarantine_stash", None)
    lockfile.set_entry(kind, name, entry)
    journal.log("release", name)
    return restored


def _foreign_target(path: Path, rendered: str, owned: set) -> bool:
    """Whether ``path`` holds a file boost did not write and must not replace.

    A workflow lands at a fixed name in a dir the user also writes their own
    slash commands into, so ``~/.claude/commands/<name>.md`` can already be
    theirs. Writing over it destroyed it, and because the lock then recorded
    the path, uninstall deleted what was left. A path a lock row records is
    boost's; a file there with the very text this run would write is adopted,
    since nothing is lost either way. Anything else is refused.

    ``force`` does not override this: ``update`` and ``reinstall`` always pass
    it (:func:`preserved_agent_scope`), so honouring it here would let every
    update overwrite a file that a moved source now collides with. The path
    is recorded in the entry's ``foreign`` (:func:`foreign_rows`), so once
    the user moves their file aside `boost sync` writes it. ``owned`` is
    built from ``materializations`` alone, so that record never makes the
    path boost's. A directory at the path is not
    this check's business: the write raises IsADirectoryError and
    :func:`_refused_target` words it.
    """
    if str(path) in owned or not os.path.lexists(path) or occupied(path):
        return False
    return path.is_symlink() or _file_sha(path) != _text_sha(rendered)


def foreign_rows(entry: dict | None) -> list[dict]:
    """A workflow entry's ``foreign`` record: the agents it did not write
    because the user's own file held the path, as ``{agent, slot, path}``.

    Kept apart from ``materializations`` on purpose. Every reader of those
    rows takes the path for boost's: uninstall deletes it, quarantine stashes
    it, ``boost info`` and the update risk diff read it as the installed text,
    and the next install treats it as owned and writes over it. None of that
    may happen to the user's file. The record exists for three readers only:
    :func:`preserved_agent_scope` keeps the agent in re-install scope,
    :func:`sync_plan` asks for a write once the path is free, and ``boost
    doctor`` says so.
    """
    return [r for r in (entry or {}).get("foreign") or ()
            if isinstance(r, dict) and r.get("agent") and r.get("path")]


def _freed_foreign(entry: dict, kind: str = "workflow") -> list[dict]:
    """The ``foreign`` rows whose path no longer holds anything: free to write.

    ``lexists``, not ``isfile``: a dangling symlink of the user's is still
    theirs, and the install refuses it again, so flagging it would turn every
    `boost sync` into a repair that never lands. Rows for an agent boost no
    longer writes are left out, as for materializations.
    """
    return [r for r in foreign_rows(entry)
            if not os.path.lexists(r["path"])
            and materialization_is_written(kind, entry, r)]


def _retire_moved(name: str, existing: dict | None, linked: list[str],
                  materializations: list[dict]) -> list[dict]:
    """Remove the files a re-install stopped writing; the rows to keep.

    For an agent this run wrote to, an old row at a path the new run did not
    write (a slot change) names a file nothing will record once the list is
    rebuilt. It is removed while it is still what boost wrote. An edited one
    is the user's now and stays, and its row is returned so uninstall still
    reaches it and ``boost verify`` still reports the edit. An agent this run
    did *not* write keeps its rows through :func:`_untouched_materializations`,
    so its old command survives a refused new write.
    """
    new_paths = {m["path"] for m in materializations}
    kept: list[dict] = []
    for m in (existing or {}).get("materializations") or ():
        if (lockfile.is_skill_copy(m) or m.get("agent") not in linked
                or m.get("path") in new_paths):
            continue
        path = Path(m.get("path", ""))
        with _refused_removal(name, path):
            if not _present(path):
                continue
            if m.get("sha256") and _file_sha(path) != m["sha256"]:
                kept.append(m)
                continue
            path.unlink()
    return kept


def _install_workflow(entry: dict, force: bool = False,
                      only_agents: list[str] | None = None,
                      scope: str = "user", base=None,
                      via: str | None = None,
                      as_skill: bool | None = None) -> InstallResult:
    """Materialize a workflow (slash command / subagent) into each enabled agent.

    A verbatim Markdown drop into the agent's ``commands/`` or ``agents/`` dir —
    the slot derived from the source path — with no transformation. With
    ``scope="project"`` the drop lands under the repo (``<repo>/.claude/…``).
    Every drop is recorded so ``uninstall`` removes exactly the files it wrote.
    """
    import hashlib

    from . import gitutil, workflows
    name = entry["name"]
    resolved_base = _require_project_base(scope, base, "workflow %s" % name)
    existing = check_existing(entry, force=force, scope=scope, base=base,
                              kind="workflow")
    explicit_agents = only_agents is not None
    only_agents = preserved_agent_scope(only_agents, existing)

    violations = policy.check_install(entry, len(lockfile.installed()))
    if violations:
        raise BoostError("policy blocks installing %s: %s" % (name, "; ".join(violations)),
                        hint="inspect with `boost policy list`")

    tap = registry.get(entry["tap"])
    source_rel = entry.get("skill_md", "")
    src = tap.path / source_rel
    if not src.is_file():
        raise BoostError("source for workflow %s vanished from tap %s" % (name, tap.name),
                        hint="run `boost update %s`" % tap.name)
    _enforce_capability_policy(name, src)
    raw = src.read_text(encoding="utf-8", errors="replace")
    slot = workflows.detect_slot(source_rel)

    # As for rules: the store refuses the whole install, a target dir only
    # its own agent.
    _require_writable(name)
    materializations: list[dict] = []
    linked: list[str] = []
    unwritable: list[str] = []
    blocked: list[tuple[str, str]] = []
    conflicts: list[str] = []
    refused: list[dict] = []
    foreign: list[str] = []
    foreign_record: list[dict] = []
    # From ``materializations`` only: a ``foreign`` row names the user's file.
    owned = {m.get("path") for m in (existing or {}).get("materializations")
             or () if not lockfile.is_skill_copy(m)}
    # workflow_agents, not materializing_agents: an agent can have a verified
    # rules surface and no slash-command format at all (Codex), and installing
    # into a directory it never reads would report a command that does not
    # exist. See agents.workflow_agents.
    targets = narrow_materializing(agents.workflow_agents(resolved_base),
                                    only_agents, name, "workflow",
                                    explicit=explicit_agents)
    for agent, skills_dir in targets.items():
        path = workflows.workflow_target(
            skills_dir, slot, name, base=resolved_base, agent=agent,
            dotdir=agents.project_dotdir(agent, skills_dir))
        # Project scope writes into the repo; a committed agent dir could be a
        # symlink escaping it (see scopes.ensure_in_base). User scope writes into
        # the user's own ~/.claude, which they control — nothing to guard.
        if resolved_base is not None:
            scopes.ensure_in_base(resolved_base, path)
        rendered = workflows.render(agent, slot, name, raw)
        if _foreign_target(path, rendered, owned):
            foreign.append(str(path))
            foreign_record.append({"agent": agent, "slot": slot,
                                   "path": str(path)})
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            util.atomic_write_text(path, rendered)
        except OSError as err:
            if not _refused_target(err, path, unwritable, blocked,
                                   conflicts):
                raise
            refused.append({"agent": agent, "slot": slot, "path": str(path),
                            "unwritable": True})
            continue
        materializations.append({
            "agent": agent, "slot": slot, "path": str(path),
            "sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest()})
        linked.append(agent)

    # A path this run no longer writes for an agent it did write (the source
    # moved from commands/ to agents/): the old file is a live slash command
    # that no row would claim once the list is rebuilt.
    materializations.extend(_retire_moved(name, existing, linked,
                                          materializations))
    # As for rules: an unrecorded materialization is a live slash command that
    # `_uninstall_workflow` — driven by this list — can never remove.
    materializations.extend(_refused_materializations(
        existing, linked, refused,
        source_sha=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        declared=declared_agent_scope(
            only_agents if explicit_agents else None, existing)))
    # An agent this run did not try (a narrowed `--agent`) keeps its foreign
    # row, as it keeps its materialization; one it tried is decided afresh.
    tried = {*linked, *(r["agent"] for r in refused),
             *(r["agent"] for r in foreign_record)}
    foreign_record += [r for r in foreign_rows(existing)
                       if r["agent"] not in tried]
    # Last, always: `boost info` and update's risk diff read the first
    # readable row as "the" installed text, and that is an agent's file.
    copy_row, copy_note = _skill_copy(name, slot, raw, existing, as_skill,
                                      scope)
    if copy_row is not None:
        materializations.append(copy_row)

    now = util.now_iso()
    lockfile.set_workflow(name, {
        "kind": "workflow",
        "slot": slot,
        "version": entry.get("version", "0.0.0"),
        "tap": entry["tap"],
        "tap_url": tap.url,
        "source_file": source_rel,
        "commit": gitutil.head_commit(tap.path),
        "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "scope": scope,
        "base": str(resolved_base) if resolved_base is not None else None,
        "installed_at": (existing or {}).get("installed_at", now),
        "updated_at": now,
        # Same governance contract as a skill entry: a pin survives a forced
        # reinstall, quarantine does not.
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        **carried_user_state(existing),
        "materializations": materializations,
        # What the user asked for, beside what was written: the rows above
        # cannot say which, and :func:`preserved_agent_scope` replays this.
        **_declared_field(only_agents if explicit_agents else None, existing),
        # Only an explicit `--as-skill`/`--no-as-skill` is recorded, and then
        # it sticks through update, reinstall and sync. Absent means "follow
        # `workflows_as_skills`", so turning the config off reaches entries
        # installed while it was on — recording the resolved value would
        # have frozen every one of them at True.
        **({"as_skill": as_skill} if as_skill is not None
           else {"as_skill": existing["as_skill"]}
           if existing and isinstance(existing.get("as_skill"), bool)
           else {}),
        **({"foreign": foreign_record} if foreign_record else {}),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"), via=via)

    res = InstallResult(
        name=name,
        dest=Path(materializations[0]["path"]) if materializations else paths.store_dir(),
        kind="workflow", scan_text=raw)
    res.linked = linked
    res.unwritable = unwritable
    res.blocked = blocked
    res.conflicts = conflicts
    res.foreign = foreign
    res.upgraded = existing is not None
    res.scope = scope
    res.skill_copy = Path(copy_row["path"]).parent if copy_row else None
    res.skill_note = copy_note
    return res


# --------------------------------------------------------------------------
# A workflow's skill copy: the same procedure, reachable from the store
# --------------------------------------------------------------------------
# A subagent rendered into ~/.claude/agents is invisible to an agent that reads
# only skills — Codex has no workflow format at all (config.DEFAULTS) and reads
# ~/.agents/skills directly. So a workflow also gets
# ``<store>/<name>/SKILL.md``, recorded as one more materialization row
# (``slot: "skill"``, ``agent: None``) on the workflow's own lock entry. Being
# a row is what makes update refresh it, uninstall and quarantine remove it,
# `boost verify` hash it and `boost sync` rewrite it when it goes missing,
# with no second code path for any of them.
#
# It is never linked. The agents boost links skills into already get the
# workflow's own file, and a link would show them the procedure twice.
# Antigravity takes no workflow and so gets neither — not linking it there is
# the cost of one rule for every linking agent. Gemini reads the store
# natively and gets its own agent file too; nothing boost writes can hide a
# store dir from it.
#
# User scope only. Project scope has no canonical store — a project skill is
# a real dir per agent (`_install_project_skill`) — so the equivalent would be
# a per-agent design of its own, and is not attempted.
#
# Recognised through the lock, and with the lock lost through the disk
# (:func:`workflow_copy_evidence`): a store dir whose SKILL.md is exactly what
# a workflow file in an agent's dir renders to. Without that, a lost lock made
# `boost heal` adopt the copy as a local skill and link it into every agent,
# beside the workflow's own file. Known limit: a Gemini-only workflow's TOML
# command cannot be rendered back, so it is no evidence.


def _copy_row(entry: dict | None) -> dict | None:
    """The skill-copy row on a workflow's lock ``entry``, or None."""
    return next((m for m in (entry or {}).get("materializations") or ()
                 if lockfile.is_skill_copy(m)), None)


def workflow_owned_store_names() -> set[str]:
    """Store dirs that are a workflow's skill copy, by name.

    Recorded on the workflow, not in the ``skills`` section, so every check
    that asks "does the lock record this store dir?" with the skills section
    alone would call it a hand-added skill — and `boost sync` would adopt it
    and link it into every agent, the duplicate the copy exists to avoid.
    This reads the lock; :func:`workflow_copy_evidence` asks the disk, for
    when the lock is gone.
    """
    return {Path(m["path"]).parent.name
            for entry in lockfile.installed_workflows().values()
            if (m := _copy_row(entry)) is not None and m.get("path")}


def workflow_copy_evidence(name: str) -> Path | None:
    """The workflow file store/``name`` is the skill copy of, or None.

    The on-disk answer to :func:`workflow_owned_store_names`, for a lock that
    no longer records the workflow: an agent's ``agents/<name>.md`` or
    ``commands/<name>.md`` that renders (:func:`workflows.render`, the skill
    slot) to exactly the store dir's ``SKILL.md``. Exactly, not by name: a
    real skill named like a workflow is the user's, and is recorded as one.
    """
    from . import workflows
    if not util.is_safe_component(name):
        return None
    try:
        have = (skill_store_dir(name) / "SKILL.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    for agent, skills_dir in agents.enabled_agents().items():
        for slot in (workflows.SLOT_AGENTS, workflows.SLOT_COMMANDS):
            target = workflows.workflow_target(skills_dir, slot, name,
                                               agent=agent)
            if target.suffix != workflows.DEFAULT_EXT:
                continue
            try:
                raw = target.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if workflows.render(None, workflows.SLOT_SKILL, name, raw) == have:
                return target
    return None


def orphaned_workflow_copies(lock: dict) -> list[tuple[str, str]]:
    """``(name, workflow file)`` for each store dir that is a workflow's
    skill copy no lock entry records (:func:`workflow_copy_evidence`)."""
    owned = workflow_owned_store_names()
    return [(n, str(p)) for n in _store_dirs()
            if n not in lock and n not in owned
            and (p := workflow_copy_evidence(n)) is not None]


def workflow_copy_lines(rows: list[tuple[str, str]]) -> list[str]:
    """One line per :func:`orphaned_workflow_copies` row, with its remedy."""
    return ["%s is the skill copy of the workflow at %s, which the lock does "
            "not record — `boost install %s` re-records both; it is not "
            "adopted as a skill" % (paths.tilde(skill_store_dir(n)),
                                    paths.tilde(p), n) for n, p in rows]


def orphaned_rule_blocks(recorded: dict | None = None
                         ) -> list[tuple[str, str]]:
    """``(rule, context file)`` for each managed rule block in an enabled
    agent's user-scope context file (``~/.claude/CLAUDE.md`` and the like)
    that no rule lock entry by that name records.

    The marker is boost's own (:data:`rules.BLOCK_START`), so a block is
    evidence on disk the way a workflow's skill copy is
    (:func:`orphaned_workflow_copies`). Without a record no command removes
    it — `boost uninstall` answers "not installed" — and the agent reads it
    every session, so an all-clear over one is false. ``recorded`` is the
    rules half of the lock; a file drop into a rules dir carries no marker
    and is not looked for.
    """
    from . import rules
    if recorded is None:
        recorded = lockfile.installed_rules()
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for agent, skills_dir in agents.enabled_agents().items():
        if agent not in rules.CONTEXT_FILES:
            continue
        target = rules.rule_target(agent, skills_dir, "x")[1]
        key = os.path.realpath(target)
        if key in seen:
            continue
        seen.add(key)
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        found.extend((n, str(target)) for n in rules.block_names(text)
                     if n not in recorded)
    return found


def rule_block_lines(rows: list[tuple[str, str]]) -> list[str]:
    """One line per :func:`orphaned_rule_blocks` row, with its remedy."""
    return ["%s carries the block of rule %s, which the lock does not record "
            "— no boost command removes it until `boost install %s` "
            "re-records it, or delete the block by hand"
            % (paths.tilde(Path(p)), n, n) for n, p in rows]


def skill_copy_owner(name: str) -> str | None:
    """The workflow whose skill copy is the store dir ``name``, or None."""
    for wname, entry in lockfile.installed_workflows().items():
        m = _copy_row(entry)
        if m is not None and Path(m.get("path", "")).parent.name == name:
            return wname
    return None


def _drop_skill_copy_row(workflow: str) -> None:
    """Forget a workflow's skill copy without touching the file.

    From the quarantine stash too: a release replays the stash, and a copy
    left there would be written back over whatever took the dir meanwhile.
    """
    entry = lockfile.get_workflow(workflow)
    if not entry:
        return
    for key in ("materializations", "quarantine_stash"):
        if key in entry:
            entry[key] = [m for m in entry.get(key) or ()
                          if not lockfile.is_skill_copy(m)]
    lockfile.set_workflow(workflow, entry)


def _stashed_copy_is_ours(path: Path, content: str) -> bool:
    """Whether a release may write a stashed skill copy back to ``path``.

    Not when the lock records a skill by that name, and not over anything in
    the dir but the very text stashed — an interrupted quarantine leaves
    that, and rewriting it changes nothing.
    """
    if lockfile.get_skill(path.parent.name):
        return False
    if not os.path.lexists(path.parent):
        return True
    return (not os.path.islink(path.parent)
            and _file_sha(path) == _text_sha(content)
            and {c.name for c in path.parent.iterdir()} == {path.name})


def wants_skill_copy(as_skill: bool | None, existing: dict | None) -> bool:
    """Whether a workflow install should write its skill copy.

    The explicit flag, else the one an earlier install recorded, else the
    ``workflows_as_skills`` config.
    """
    if as_skill is not None:
        return as_skill
    recorded = (existing or {}).get("as_skill")
    if isinstance(recorded, bool):
        return recorded
    return bool(config.get("workflows_as_skills", True))


def _text_sha(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_sha(path: Path) -> str | None:
    try:
        return _text_sha(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None


def skill_copy_blocker(name: str, existing: dict | None,
                       text: str | None = None) -> str | None:
    """Why the store dir ``name`` cannot take this workflow's copy, or None.

    A skill the lock records by that name, or anything else already there
    that is not this workflow's own copy, wins: the copy is a convenience and
    is never worth a file the user or another tool put there.

    ``text`` is the copy about to be written. A dir holding only a SKILL.md
    that is already exactly that is this workflow's copy whatever the lock
    says — the one a lost lock left behind — and is claimed, so the
    `boost install` doctor names for it re-records it.
    """
    if not util.is_safe_component(name):
        return "%r is not a name the skill store can hold" % name
    if lockfile.get_skill(name):
        return ("a skill named %s is already installed — the workflow is "
                "not written to the skill store" % name)
    dest = skill_store_dir(name)
    own = _copy_row(existing)
    if (os.path.lexists(dest)
            and (own is None or Path(own.get("path", "")).parent != dest)
            and not (text is not None and _holds_only(dest, text))):
        return ("%s is already in the skill store and is not this workflow's "
                "— left alone" % paths.tilde(dest))
    return None


def _holds_only(sdir: Path, text: str) -> bool:
    """Whether ``sdir`` is a real dir holding one file, a SKILL.md of ``text``."""
    try:
        if sdir.is_symlink() or os.listdir(sdir) != ["SKILL.md"]:
            return False
        return (sdir / "SKILL.md").read_text(encoding="utf-8") == text
    except (OSError, UnicodeDecodeError):
        return False


def _remove_skill_copy(m: dict) -> tuple[bool, str | None]:
    """Remove one recorded copy if it is still what boost wrote.

    ``(removed, kept)``: an edited copy is the user's now and stays, and
    ``kept`` names it. The dir goes too once it is empty — leaving it would
    leave a store dir with no SKILL.md, which sync names as not a skill.
    """
    path = Path(m.get("path", ""))
    if not _present(path):
        _rmdir_quietly(path.parent)
        return False, None
    if _file_sha(path) != m.get("sha256"):
        return False, str(path)
    path.unlink(missing_ok=True)
    _rmdir_quietly(path.parent)
    return True, None


def _rmdir_quietly(d: Path) -> None:
    """Remove ``d`` if it is an empty store dir; leave anything else."""
    with contextlib.suppress(OSError):
        if d.parent == paths.store_dir():
            d.rmdir()


def _skill_copy(name: str, slot: str, raw: str, existing: dict | None,
                as_skill: bool | None, scope: str
                ) -> tuple[dict | None, str | None]:
    """Write (or retire) the workflow's skill copy: ``(row, note)``.

    ``row`` is what to record, None when there is no copy after this run.
    ``note`` says why there is none, or what happened to an old one, when
    that is worth telling the user.
    """
    from . import frontmatter, workflows
    own = _copy_row(existing)
    if scope == scopes.SCOPE_PROJECT:
        return None, ("not written to the skill store: --as-skill is user "
                      "scope only" if as_skill else None)
    if not wants_skill_copy(as_skill, existing):
        if own is None:
            return None, None
        removed, kept = _remove_skill_copy(own)
        if kept:
            # Still recorded: unowned, the dir is a hand-added skill to
            # `boost sync`, which adopts it and links it into every agent —
            # beside the workflow's own file. A later run retires it once it
            # is back to what boost wrote; uninstall leaves it either way.
            return own, ("left %s in place: it was edited since boost wrote "
                         "it" % paths.tilde(kept))
        return None, ("removed its copy from the skill store" if removed
                      else None)
    meta, _ = frontmatter.parse(raw)
    desc = workflows.skill_description(slot, meta)
    if desc is None:
        no_desc = ("not written to the skill store: it has no description, "
                   "and a skill host picks skills by theirs")
        if own is not None:
            _removed, kept = _remove_skill_copy(own)
            if kept:
                return own, "%s; left the edited %s in place" % (
                    no_desc, paths.tilde(kept))
        return None, no_desc
    text = workflows.render_skill(name, desc, raw)
    blocker = skill_copy_blocker(name, existing, text)
    if blocker:
        return None, blocker
    dest = skill_store_dir(name) / "SKILL.md"
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        util.atomic_write_text(dest, text)
    except OSError as err:
        # The agents' files are written; a store that refuses one file is not
        # worth failing the install over. A copy already on disk stays
        # recorded, so uninstall can still remove it.
        return own, ("not written to the skill store: %s"
                     % (err.strerror or err))
    return ({"agent": None, "slot": workflows.SLOT_SKILL, "path": str(dest),
             "sha256": _text_sha(text)}, None)


def _installed_raw(entry: dict) -> str | None:
    """The source text a workflow was installed from, or None if it is gone.

    Only text whose sha256 is the one the lock recorded, so a backfill writes
    the procedure that is installed, never a newer one the tap has moved to —
    which would be the covert update a pin exists to prevent. The tap's file
    is asked first; then the agents' own files, which are verbatim for every
    agent but Gemini (:func:`workflows.render`), so a tap that moved still
    leaves one copy of the installed text on disk.
    """
    want = entry.get("sha256")
    if not want:
        return None
    candidates: list[Path] = []
    with contextlib.suppress(BoostError):
        candidates.append(registry.get(entry.get("tap") or "").path
                          / entry.get("source_file", ""))
    candidates += [Path(m["path"]) for m in entry.get("materializations") or ()
                   if m.get("path") and not lockfile.is_skill_copy(m)
                   and not m.get("unwritable")]
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _text_sha(text) == want:
            return text
    return None


#: A rule/workflow file with no recorded hash that :func:`backfill_row_hashes`
#: could not record: it no longer holds what boost writes, or its source is
#: gone. Not a repair, so :func:`is_unrepaired` names it.
_NOT_VOUCHED_MARK = " with no recorded hash that boost cannot vouch for — "


def _expected_row_text(kind: str, name: str, entry: dict, m: dict,
                       raw: str) -> tuple[str, str | None]:
    """``(what boost writes for row m, what the row's file holds now)``.

    The same text each install hashes: a rule's verbatim file or the stripped
    body of its managed block (what `rules.read_block` reads back), and a
    workflow's per-agent render. The second is None when it cannot be read.
    """
    from . import frontmatter, rules, workflows
    try:
        on_disk: str | None = Path(m.get("path", "")).read_text(
            encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        on_disk = None
    if kind == "rule":
        if m.get("mode") == rules.MODE_CLAUDE:
            meta, body = frontmatter.parse(raw)
            want = rules.render_claude_body(str(meta.get("name") or name),
                                            body).strip("\n")
            return want, (rules.read_block(on_disk, name)
                          if on_disk is not None else None)
        return raw, on_disk
    slot = m.get("slot") or entry.get("slot") or workflows.detect_slot(
        entry.get("source_file", ""))
    return workflows.render(m.get("agent"), slot, name, raw), on_disk


def _unhashed_rows(kind: str, entry: dict) -> list[dict]:
    """The rows of a rule/workflow entry written before rows carried a hash.

    Only rows whose file is there and that name an agent boost still writes:
    a missing file is re-materialized by sync (which records its hash), and
    a row for a disabled agent is a record `boost verify` does not grade.
    """
    return [m for m in entry.get("materializations") or ()
            if isinstance(m, dict) and not m.get("sha256")
            and not m.get("unwritable") and not lockfile.is_skill_copy(m)
            and agents.materialization_is_written(kind, entry.get("base"),
                                                  m.get("agent"))
            and os.path.isfile(m.get("path", ""))]  # noqa: FURB146


def backfill_row_hashes(dry: bool = False) -> list[str]:
    """Record the hash of each rule/workflow file installed before rows had one.

    Rules and workflows installed before per-row hashes recorded
    ``{agent, mode|slot, path}`` and nothing to compare, so `boost verify`
    failed them as "missing lock fields: materialization sha256" through
    every update, sync and heal, and only a reinstall cleared it. A row's
    hash is stamped only when its file still holds exactly what boost writes
    for the installed source (:func:`_installed_raw`, the text whose sha256
    the lock recorded): a file edited since is the user's, and hashing it
    would bless the edit as boost's. Those, and items whose installed source
    is gone, are named with the reinstall that records them. One lock write
    for the lot. Returns one line per item, in the tense of ``dry``.
    """
    # Only a lock sync may write: :func:`lockfile.write` stamps the current
    # schema, so stamping rows into a newer one (which `refuse_corrupt` lets
    # through) rewrote a v4 lock as v3 under the line saying sync records
    # nothing. An "older" lock is ok, and is migrated before this runs.
    if not lockfile.check().ok:
        return []
    lines: list[str] = []
    stamps: dict[tuple[str, str], dict[str, str]] = {}
    for kind, section in (("rule", "rules"), ("workflow", "workflows")):
        for name, entry in sorted(lockfile.read()[section].items()):
            rows = _unhashed_rows(kind, entry)
            if (not rows or entry.get("quarantined")
                    or scopes.stranded(entry)):
                continue
            raw = _installed_raw(entry)
            got: dict[str, str] = {}
            if raw is not None:
                for m in rows:
                    want, have = _expected_row_text(kind, name, entry, m, raw)
                    if have is not None and have == want:
                        got[m["path"]] = _text_sha(want)
            if got:
                stamps[(section, name)] = got
                lines.append("%s the hash of %s %s's %s" % (
                    "would record" if dry else "recorded", kind, name,
                    "file" if len(got) == 1 else "%d files" % len(got)))
            left = len(rows) - len(got)
            if left:
                lines.append(
                    ("%s %s has %s" + _NOT_VOUCHED_MARK
                     + "`boost reinstall %s` rewrites and records %s")
                    % (kind, name,
                       "a file" if left == 1 else "%d files" % left,
                       name, "it" if left == 1 else "them"))
    if dry or not stamps:
        return lines

    def stamp(lock: dict) -> bool:
        changed = False
        for (section, name), got in stamps.items():
            for m in lock[section].get(name, {}).get("materializations") or ():
                sha = got.get(m.get("path", "")) if isinstance(m, dict) else None
                if sha is not None and not m.get("sha256"):
                    m["sha256"] = sha
                    changed = True
        return changed
    lockfile.mutate(stamp)
    return lines


def _backfill_candidates() -> list[tuple[str, dict, str]]:
    """``(name, entry, source text)`` for each installed workflow an install
    would give a skill copy today and that has none.

    The same conditions :func:`_skill_copy` writes under: user scope, live
    (not quarantined, not stranded), wanted (:func:`wants_skill_copy`), with a
    description, and with nothing else at its store dir. A workflow whose
    installed text cannot be found is left out — `boost update` writes its
    copy from the tap.
    """
    from . import frontmatter, workflows
    out = []
    for name, entry in sorted(lockfile.installed_workflows().items()):
        if (entry.get("scope", scopes.SCOPE_USER) == scopes.SCOPE_PROJECT
                or entry.get("quarantined") or scopes.stranded(entry)
                or _copy_row(entry) is not None
                or not wants_skill_copy(None, entry)
                or skill_copy_blocker(name, entry)):
            continue
        raw = _installed_raw(entry)
        if raw is None:
            continue
        slot = entry.get("slot") or workflows.detect_slot(
            entry.get("source_file", ""))
        if workflows.skill_description(slot, frontmatter.parse(raw)[0]):
            out.append((name, entry, raw))
    return out


def workflows_without_skill_copy() -> list[str]:
    """Installed workflows `boost heal --as-skill` would give a skill copy."""
    return [name for name, _entry, _raw in _backfill_candidates()]


def backfill_skill_copies(dry: bool = False) -> list[str]:
    """Write the skill copy of every workflow installed without one.

    For workflows installed before the copy existed, or while
    ``workflows_as_skills`` was off. Writes only the copy and its row: the
    agents' files are already what the lock says, and reinstalling to get one
    file would rewrite them from whatever the tap holds now. Returns one line
    per workflow, in the tense of ``dry``.
    """
    from . import workflows
    lines = []
    for name, entry, raw in _backfill_candidates():
        dest = skill_store_dir(name)
        if dry:
            lines.append("would write workflow %s's skill copy to %s"
                         % (name, paths.tilde(dest)))
            continue
        slot = entry.get("slot") or workflows.detect_slot(
            entry.get("source_file", ""))
        row, note = _skill_copy(name, slot, raw, entry, None,
                                scopes.SCOPE_USER)
        if row is None:
            lines.append("workflow %s: %s" % (name, note))
            continue
        entry["materializations"] = [*(entry.get("materializations") or ()),
                                     row]
        lockfile.set_workflow(name, entry)
        lines.append("wrote workflow %s's skill copy to %s"
                     % (name, paths.tilde(dest)))
    return lines


def _uninstall_workflow(name: str, workflow: dict) -> dict:
    """Remove every file dropped for an installed workflow.

    Its skill copy goes only while it is still what boost wrote: the store is
    where a user edits skills, and an edited copy is theirs now. The result's
    ``kept`` names any left in place.
    """
    removed: list[str] = []
    plan: list[tuple[Path, str | None]] = []
    copies: list[dict] = []
    kept: list[str] = []
    for m in workflow.get("materializations", []):
        path = Path(m.get("path", ""))
        if lockfile.is_skill_copy(m):
            copies.append(m)
            continue
        # An agent's file gets the copy's test: one the user edited since
        # boost wrote it is theirs, and deleting it lost the edit in silence.
        # A row with no recorded sha (an older lock, a refused write) has
        # nothing to compare and is removed as before.
        with _refused_removal(name, path):
            if _present(path):
                if m.get("sha256") and _file_sha(path) != m["sha256"]:
                    kept.append(str(path))
                    continue
                plan.append((path, None))
        if m.get("agent"):
            removed.append(m["agent"])
    for m in copies:
        path = Path(m.get("path", ""))
        with _refused_removal(name, path):
            if _present(path):
                if _file_sha(path) == m.get("sha256"):
                    plan.append((path, None))
                else:
                    kept.append(str(path))
    gone = _remove_all_or_nothing(name, plan)
    for m in copies:
        if m.get("path") not in kept:
            _rmdir_quietly(Path(m.get("path", "")).parent)
    lockfile.remove_workflow(name)
    journal.log("uninstall", name)
    res = _materialized_result(name, removed, workflow, "workflow", gone)
    if kept:
        res["kept"] = kept
    return res


def _materialized_result(name: str, removed: list[str], entry: dict,
                         kind: str, gone: int) -> dict:
    """The uninstall result for a rule or workflow, scope carried through.

    ``scope`` and ``base`` come off the lock entry rather than off how the
    caller got here, because both callers reach the same row: bare
    ``boost uninstall`` and ``boost uninstall --local`` remove one
    ``--local`` rule by the same two functions. Reporting the repo only on
    the flagged path would make the same removal describe itself two ways.

    A user-scope entry has neither key and gets neither, so ``cmd_uninstall``
    reads ``scope`` as absent and prints exactly what it printed before.

    **Both keys or neither**, and a ``base`` that names a directory is
    required for it. A lock is a file on disk, so a row can say
    ``scope: project`` and record no usable directory —
    :func:`scopes.owned_by` already treats that shape as real and drops it,
    because a row that claims no directory is claimed by none. Carrying
    ``scope`` without one would put the key in the dict with that value,
    where the caller's ``info.get("base", "this repo")`` default can never
    fire: ``paths.tilde`` is ``str(p)``, so ``None`` prints as *removed from
    None* and a hand-edited ``{"base": {}}`` prints as *removed from {}* —
    over a removal that worked.

    The test is :func:`scopes.names_a_directory`, the same one ownership is
    decided with, rather than a truthiness check beside it. Measured, the two
    agree on every *falsy* base — ``None``, ``""``, ``{}``, ``0`` are dropped
    either way — and differ on exactly two things, both of which a lock can
    hold and an install cannot write: a **truthy** non-string, which would
    print *removed from 17*, and a **relative** path, which names a different
    repo depending on where the reader is standing. The relative case is the
    one that carries the difference in practice, so it is the one the test
    turns on.
    """
    res = {"name": name, "unlinked": removed, "entry": entry, "kind": kind,
           "removed_count": gone}
    if (entry.get("scope") == scopes.SCOPE_PROJECT
            and scopes.names_a_directory(entry.get("base"))):
        res["scope"] = scopes.SCOPE_PROJECT
        res["base"] = entry["base"]
    return res


def _import_meta(src_dir: Path) -> dict:
    """The frontmatter of the SKILL.md a local install reads its name from."""
    from . import frontmatter
    meta, _ = frontmatter.parse((Path(src_dir) / "SKILL.md").read_text(
        encoding="utf-8", errors="replace"))
    return meta


def import_name(src_dir: Path, name: str | None = None) -> str:
    """The name :func:`install_from_path` installs ``src_dir`` under."""
    return name or str(_import_meta(src_dir).get("name") or Path(src_dir).name)


def replaces_only_copy(name: str, src_dir: Path) -> bool:
    """Whether installing ``src_dir`` as ``name`` overwrites the only copy of it.

    A skill :func:`only_copy` describes has nowhere to be put back from, so
    replacing it with another dir — `boost import` under the same name —
    loses it as surely as uninstalling it does, and gets the same question
    first. ``src_dir`` being that store dir replaces nothing:
    :func:`install_from_path` refuses it on its own.
    """
    entry = lockfile.get_skill(name)
    return (entry is not None and only_copy(name, entry)
            and not foreign.same_dir(Path(src_dir), skill_store_dir(name)))


def _rename_frontmatter(skill_md: Path, name: str, meta: dict) -> bool:
    """Make the store copy's frontmatter ``name`` agree with the lock name.

    ``boost import DIR --name beta`` of a skill whose frontmatter says
    ``name: alpha`` used to rename only the store dir and the lock key: the
    agent still listed it as ``alpha`` (agents go by the frontmatter name) and
    ``boost adapt beta`` printed a banner command for an ``alpha`` that boost
    had no record of. Only the one line changes (``frontmatter.splice_field``),
    and only in the copy — the source is the user's. Returns whether it wrote.
    """
    from . import frontmatter
    if str(meta.get("name") or "") == name:
        return False
    # bytes, not text: a text read would translate CRLF on the way in
    raw = skill_md.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    revised = frontmatter.splice_field(text, "name", name)
    if revised == text:     # no frontmatter block to carry a name
        return False
    util.atomic_write_text(skill_md, revised)   # newline="\n": verbatim
    return True


def install_from_path(src_dir: Path, name: str | None = None,
                      tap_label: str = "local",
                      only_agents: list[str] | None = None,
                      force: bool = False,
                      remote: RemoteSource | None = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`).

    ``remote`` names the clone ``src_dir`` sits in when the import came from a
    URL: the lock then records the URL, the commit and the path inside the
    repo, never the temporary clone. Without it the directory is recorded
    absolute, so a relative ``boost import ./x`` can be reinstalled from
    anywhere rather than only from the directory it was imported in.

    Enforces the same pin, policy and capability gates as ``install``. It used
    to enforce none of them, so every local path in — ``import``, ``create
    --install``, ``distill/infer/absorb --install`` — was a way
    around a blocklist, ``pin_only``, ``max_skills`` and ``denied_capabilities``.

    Deliberately *not* adopted from ``install``: its "already installed" refusal.
    This is the re-import path (``boost reinstall`` on a local skill), so that
    gate would break the function's main use.
    """
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    lockfile.refuse_corrupt()       # before the copy, as in `install`
    meta = _import_meta(src_dir)
    name = util.check_item_name(name or str(meta.get("name") or src_dir.name))
    refuse_case_collision(name, lockfile.installed())
    existing = lockfile.get_skill(name)
    # Refuse before `dest` is touched, so a rejected install leaves nothing
    # half-copied over an existing skill.
    if foreign.same_dir(src_dir, skill_store_dir(name)):
        # Copying a dir onto itself stages it without `.git` and swaps that in,
        # so the "copy" deletes the history it was made from. `boost reinstall`
        # of a skill `boost sync` recorded where it found it is the usual way here.
        raise BoostError(
            "%s is %s's own dir in the store, so there is nothing to copy it "
            "from" % (paths.tilde(src_dir), name),
            hint=("it is installed already, and edits there are live"
                  if existing else
                  "`boost sync` records a skill put in the store by hand"))
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    disowned = _refuse_unrecorded(name, existing, force)
    violations = policy.check_install(
        {"name": name, "tap": tap_label,
         "version": str(meta.get("version") or "0.0.0"),
         "description": meta.get("description")},
        # Re-importing a skill that is already counted must not trip max_skills.
        _count_others(lockfile.installed(), name))
    if violations:
        raise BoostError("policy blocks installing %s: %s" % (name, "; ".join(violations)),
                        hint="inspect with `boost policy list`")
    _enforce_capability_policy(name, src_dir / "SKILL.md")
    dest = skill_store_dir(name)
    _require_writable(name)
    if disowned:
        _drop_skill_copy_row(disowned)
    fresh = not os.path.lexists(dest)
    try:
        # A URL import is bounded by its clone, as a tap install is by its
        # tap; a path import copies what the user's own links lead to.
        skipped = _copy_skill(src_dir, dest,
                              within=remote.root if remote else None)
        _rename_frontmatter(dest / "SKILL.md", name, meta)
        # An import records no date, so the one a tap install left in the
        # lock must not stand for these files.
        res = link_agents(name,
                          only=preserved_agent_scope(only_agents, existing),
                          updated_at=None)
    except BaseException:
        # As in install(): nothing recorded a fresh copy, so nothing else
        # would ever clean it up — a refused link left an unrecorded store
        # dir that the rerun then refused to touch.
        if fresh and lockfile.get_skill(name) is None:
            with contextlib.suppress(OSError):
                unlink_agents(name)
            with contextlib.suppress(OSError):
                util.rmtree(dest)
        raise
    res.skipped_links = skipped
    res.score, _ = util.score_skill(dest)
    res.mcp_servers = declared_mcp_servers(dest)
    prior_tap = (existing or {}).get("tap")
    res.replaced_tap = prior_tap if prior_tap != tap_label else None
    linked = linked_agents(name)
    declared = declared_agent_scope(only_agents, existing)
    if declared:
        res.out_of_scope = [a for a in linked if a not in declared]
    now = util.now_iso()
    record_rebuilt(name, {
        "version": str(meta.get("version") or "0.0.0"),
        "tap": tap_label,
        "source_dir": (repo_path(remote, src_dir) if remote
                       else str(src_dir.absolute())),
        "source_url": remote.url if remote else "",
        "commit": remote.commit if remote else "",
        "sha256": util.sha256_dir(dest),
        # record_rebuilt carries the held one, with pinned/tags/commit_pin.
        "installed_at": now,
        "updated_at": now,
        # `pinned` and `tags` are record_rebuilt's: a re-import once wrote a
        # hardcoded False, which silently CLEARED an existing pin.
        "quarantined": False,
        # What is on disk, not what this run linked — see install().
        "agents": linked,
        # `boost import --agent ...` narrows the same way `install` does, so it
        # has to record the same declaration — otherwise the links are narrow
        # but sync sees no scope and widens them right back.
        "only_agents": declared,
        **({"refused_agents": refused} if (refused := unrecorded_agents(name, res))
           else {}),
    })
    journal.log("import", name, source=remote.url if remote else str(src_dir))
    return res


def existing_skill_owner(name: str) -> str | None:
    """Tap label of the skill already installed as ``name``, else None.

    For the generated-install paths (``create``/``distill``/``infer``/``absorb``
    ``--install``) to warn before silently replacing an *unpinned* install and
    flipping its lock provenance to ``local`` — the loss ``list`` would
    otherwise never show. ``install_from_path``'s own gate only refuses a
    *pinned* name (its docstring: that refusal is deliberately not extended to
    the unpinned case, since this is also the re-import path for ``boost
    import`` / ``boost reinstall``). Callers that generate a brand-new skill,
    rather than re-importing an existing one, use this to catch that gap
    themselves.
    """
    existing = lockfile.get_skill(name)
    return existing.get("tap") if existing else None


def _check_store_removable(name: str) -> None:
    """Refuse a skill uninstall the store directory would stop halfway.

    Deleting the copy needs the store itself writable, and so does the lock
    file that lives in it. Under a read-only ``~/.agents/skills`` the links
    went, then ``SKILL.md``, then the rmtree failed on the directory and
    uninstall crashed at exit 70 with the lock row still in place. The same
    refusal as :func:`_require_writable`, asked before anything is removed.
    """
    d = paths.store_dir()
    block = paths.refuses_writes(d)
    if block is not None:
        raise BoostError("cannot uninstall %s: %s"
                         % (name, paths.not_writable(d, block)),
                         hint="%s, then re-run" % paths.write_remedy(block))


def _check_links_removable(name: str, entry: dict) -> None:
    """Refuse a skill uninstall that would leave one of its links behind.

    :func:`unlink_agents` skips a link it cannot see, which is right for
    ``sideline``. Uninstall is different: it deletes the store dir next, so a
    link it skipped is left dangling into a deleted store. Under a dotdir with
    no search bit that is exactly what happened, while uninstall reported
    success and exited 0. Checking first, before anything is removed, keeps
    the store and the lock entry, so uninstalling again after the `chmod`
    finishes the job.

    A link of boost's it *can* see is checked whatever the lock says, because
    :func:`unlink_agents` removes every visible one and would otherwise stop
    on a read-only dir halfway through. A link it cannot see is checked for
    every agent the lock records as linked *or refused*: a forced relink run
    while the dotdir was unsearchable moves that agent into
    ``refused_agents`` and leaves the first install's link on disk, unseen.
    Every lock write that rewrites ``agents`` records such an agent there,
    tried or not (:func:`unrecorded_agents`), so a narrowed relink that never
    tries it cannot drop it from both fields.
    An empty ``agents`` means every agent, as in
    :func:`preserved_agent_scope`: ``sideline`` and ``quarantine`` empty it
    after an :func:`unlink_agents` that skipped the unseen link, which is
    still on disk. The cost is conservative: an agent refused at its first
    install, and so never linked, still blocks uninstall until its dotdir is
    searchable, and so does any unsearchable dotdir for a sidelined or
    quarantined skill, and any agent unsearchable when the entry was last
    written, which :func:`unrecorded_agents` records whether or not that run
    tried it. An agent a non-empty lock entry does not name never blocks, so
    a dir locked down after that write blocks only where a link is recorded.
    """
    linked = entry.get("agents") or ()
    recorded = ({*linked, *(entry.get("refused_agents") or ())} if linked
                else set(agents.unlinking_agents()))
    for agent, adir in agents.unlinking_agents().items():
        link = adir / name
        try:
            os.lstat(link)
        except PermissionError:
            if agent in recorded:
                raise _removal_refused(name, link) from None
            continue
        except OSError:
            continue
        # Only a link uninstall will remove can stop it halfway.
        if is_boost_link(link) and not os.access(adir, os.W_OK | os.X_OK):
            raise _removal_refused(name, link)


def uninstall(name: str, *, project_fallback: bool = True) -> dict:
    """Uninstall ``name`` whatever its kind (skill, rule, workflow).

    Reverses everything the install wrote and drops the lock entry;
    returns {name, unlinked, entry, kind}. Raises BoostError if not installed.
    The ``kind`` is what tells a caller like ``cmd_uninstall`` whether
    ``unlinked`` names agent *symlinks* (skill) or agent *materializations*
    (rule/workflow) — those are removed from entirely different places, and a
    caller that assumes "skill" for all three narrates a store directory that
    a rule or workflow never had.

    ``name`` may be tap-qualified (:func:`installed_name`). With
    ``project_fallback=False`` (``uninstall --global``) nothing in a repo is
    removed: a skill only the current repo has, and a rule or workflow the
    user lock records at project scope, are refused rather than removed.
    """
    name = installed_name(name)
    entry = lockfile.get_skill(name)
    if not entry:
        rule = lockfile.get_rule(name)
        workflow = None if rule else lockfile.get_workflow(name)
        rec = rule or workflow
        if (rec and not project_fallback
                and rec.get("scope") == scopes.SCOPE_PROJECT):
            # A rule or workflow `install --local` put in a repo is recorded
            # in the *user* lock, so the lookup above finds it — but its files
            # are in that repo, which `--global` said to leave alone.
            raise BoostError(
                "%s is not installed in your user config" % name,
                hint="it was installed into %s — `boost uninstall --local %s` "
                     "from there" % (paths.tilde(Path(str(rec.get("base") or
                                                          "a repo"))), name))
        if rule:
            return _uninstall_rule(name, rule)
        if workflow:
            return _uninstall_workflow(name, workflow)
        # Nothing at user scope — but the caller may be standing in a repo that
        # has it installed locally, and "X is not installed" would be a plain
        # falsehood there. Only ever acts on a name the project lock records.
        # `resolve_base`, not `project_root`: `install --local` writes with the
        # former, so asking the latter here refused to remove what install had
        # just put in an unmarked directory.
        pbase = scopes.resolve_base(scopes.SCOPE_PROJECT)
        in_repo = pbase is not None and bool(projectlock.get_skill(pbase, name))
        if in_repo and project_fallback:
            return uninstall_project(name, base=pbase)
        raise BoostError("%s is not installed" % name,
                        hint=("only this repo has it — `boost uninstall "
                              "--local %s`" % name) if in_repo
                        else "see what is with `boost list`")
    _check_links_removable(name, entry)
    _check_store_removable(name)
    # The row goes first: a lock that refuses the write (full disk, immutable
    # file) then fails before anything is deleted, rather than after the copy
    # and its links are gone with the row still claiming them.
    lockfile.remove_skill(name)
    try:
        removed_links = unlink_agents(name)
        util.remove_path(skill_store_dir(name))
    except BaseException:
        lockfile.set_skill(name, entry)
        raise
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry, "kind": "skill"}


def strip_extended_prefix(text: str) -> str:
    """Drop Windows' ``\\\\?\\`` extended-length prefix from a raw path string.

    Since 3.8, `os.readlink()` on Windows returns the reparse point's
    substitution path, which typically carries that prefix — so boost's own
    link into the store reads back as
    ``\\\\?\\C:\\Users\\...\\.agents\\skills\\x``. Compared by path components
    that is a *different drive* from ``C:\\Users\\...``, and every Windows leg
    of the matrix went red on exactly this. The check it replaced was a
    substring test, which the prefix sailed straight through; comparing
    properly is what exposed it.
    """
    if text.startswith("\\\\?\\UNC\\"):
        return "\\\\" + text[len("\\\\?\\UNC\\"):]
    if text.startswith("\\\\?\\"):
        return text[len("\\\\?\\"):]
    return text


def normalize_link_target(path: Path) -> str:
    """A comparable string form of a `readlink()` result.

    Normalizes separators and case as well as the prefix: Windows paths
    compare case-insensitively, and POSIX `normcase` is a no-op.
    """
    return os.path.normcase(os.path.normpath(strip_extended_prefix(str(path))))


def points_into_store(link: Path) -> bool:
    """True if `link`'s target lands inside boost's canonical store.

    Reads the raw `readlink()` target rather than `resolve()`, because the
    links this has to judge are usually broken — `resolve()` cannot tell us
    where a dangling link was aiming. A relative target is resolved against
    the link's own directory, and containment is decided by `commonpath`
    (the same guard `scopes.contains` uses): a substring test on the store
    path also matches siblings like `~/.agents/skills-backup`, which boost
    does not own either.

    Everything boost deletes under an agent's skills dir is gated on this.
    A user's own broken symlink sitting in `~/.claude/skills` is not ours.
    Fails closed — an unreadable link is not boost's to delete.
    """
    try:
        target = link.readlink()
    except OSError:
        return False
    if not target.is_absolute():
        target = link.parent / target
    target_s = normalize_link_target(target)
    root_s = normalize_link_target(paths.store_dir())
    try:
        # ValueError for paths with no common root — on Windows, two different
        # drives — which means "outside", not "crash out of the delete guard".
        return os.path.commonpath([target_s, root_s]) == root_s
    except ValueError:
        return False


def is_boost_link(link: Path) -> bool:
    """True if ``link`` is boost's kind of link: a symlink into the store.

    Dangling or not, boost may replace or remove one. Anything else at a link
    path — a file, a dir, the user's own link to a checkout or a volume —
    belongs to whoever put it there. One predicate, so adoption, sync, prune,
    uninstall and sideline agree on what is boost's: they disagreed, and a
    link adoption had called "not boost's to replace" was re-pointed by the
    next sync once it dangled, and removed by `--prune` and `uninstall`.
    """
    return os.path.islink(link) and points_into_store(link)  # noqa: FURB146


def resolves_into_store(path: Path) -> bool:
    """True if ``path``'s fully resolved real location sits inside the store.

    The companion to :func:`points_into_store`, and deliberately not the same
    question. That one reads a single ``readlink()`` because it judges *broken*
    links, where there is nothing to resolve. This one judges live ones, and
    has to follow the whole chain: the shape that prompted it is
    ``~/.gemini/skills/x -> ../../.claude/skills/x -> ~/.agents/skills/x``,
    where one hop lands in another agent's dir and reads as foreign. Only the
    second hop reaches the store.

    **Both sides are resolved.** Comparing a resolved target against a nominal
    ``store_dir()`` is the bug `_resolve_as_far_as_it_exists` documents in
    ``commands/quality.py``: a $HOME under macOS's ``/var/folders`` resolves to
    ``/private/var/...``, so a genuine hit never prefix-matches. Containment is
    `commonpath`, not `startswith`, so ``~/.agents/skills-backup`` stays out.

    Fails closed — a symlink loop, or anything else ``resolve()`` refuses to
    answer, is not in the store as far as this is concerned.

    A path the strings put outside is asked again by inode (:func:`_under`):
    on a case-insensitive volume a link to ``~/.Agents/skills/x`` leads into
    the store, and ``resolve()`` keeps the case it was given. Read as another
    tool's copy, the store's only copy of a skill was a copy of itself, and
    ``--prune`` deleted it.
    """
    try:
        target = path.resolve(strict=True)
        root = paths.store_dir().resolve()
        target_s = normalize_link_target(target)
        root_s = normalize_link_target(root)
    except (OSError, RuntimeError):
        # RuntimeError is not redundant: on Python 3.12 `resolve(strict=True)`
        # raises RuntimeError("Symlink loop from ...") for a cycle, and
        # RuntimeError is NOT an OSError subclass. 3.13+ raises OSError for the
        # same input. Catching only OSError made "fails closed" true on the
        # newer interpreters and false on the oldest supported one — the test
        # passed locally on 3.14 and failed in CI on 3.12.
        return False
    with contextlib.suppress(ValueError):
        if os.path.commonpath([target_s, root_s]) == root_s:
            return True
    return _under(target, root)


def _under(target: Path, root: Path) -> bool:
    """True if ``target`` or one of its parents is ``root``, by inode."""
    try:
        want = root.stat()
    except OSError:
        return False
    for p in (target, *target.parents):
        try:
            st = p.stat()
        except OSError:
            continue
        if (st.st_dev, st.st_ino) == (want.st_dev, want.st_ino):
            return True
    return False


@dataclass(frozen=True)
class DuplicateDiscovery:
    """One skill a native-store agent can reach through two discovery tiers.

    ``path`` is the entry inside the agent's own skills dir; ``target`` is
    where it really leads, inside the canonical store the agent already reads
    natively.
    """
    agent: str
    name: str
    path: Path
    target: Path


def duplicate_discovery() -> list[DuplicateDiscovery]:
    """Entries in a native-store agent's skills dir that lead into the store.

    A `links_skills: false` agent reads :func:`paths.store_dir` directly, so
    anything in its own skills dir that resolves back into the store is the
    same skill offered twice. Gemini CLI answers that with a "Skill conflict
    detected" line per skill, every session — the symptom this detects.

    Not every such agent pays that cost: one that de-duplicates by resolved
    path collapses the two entries silently, so there is nothing to warn about
    and it is skipped (:func:`agents.dedupes_by_path`).

    Boost does not create these: it stopped linking into a native-store agent,
    and `sync_plan` never asks for such a link. Another installer's copy is far
    likelier, and the warning costs the user the same either way — so the test
    is **topology, not ownership**. Nothing here deletes: see
    :func:`remove_duplicate_discovery`, which is opt-in because removing
    another tool's file on a hunch is worse than the warning.

    A missing agent dir is the normal case (boost never creates one for a
    native-store agent) and yields nothing rather than an error. The store root
    itself is skipped: a link to ``~/.agents/skills`` is the Agent Skills
    alias, not a skill discovered twice.
    """
    found: list[DuplicateDiscovery] = []
    store_root = paths.store_dir()
    collapses = agents.dedupes_by_path()
    for agent, adir in agents.native_store_agents().items():
        # An agent that de-duplicates by resolved path shows the skill once and
        # says nothing, so there is no symptom to report. See
        # agents.dedupes_by_path.
        if agent in collapses:
            continue
        if not adir.is_dir():
            continue
        for entry in sorted(adir.iterdir()):
            if not resolves_into_store(entry):
                continue
            target = entry.resolve()
            if target == store_root.resolve():
                continue
            found.append(DuplicateDiscovery(
                agent=agent, name=entry.name, path=entry, target=target))
    return sorted(found, key=lambda d: (d.agent, d.name))


def remove_duplicate_discovery(dup: DuplicateDiscovery) -> bool:
    """Delete one duplicate discovery path. True if it was removed.

    Re-gated against the filesystem rather than trusting the report that
    produced ``dup``: boost did not put this file here, so the two facts that
    make deleting it safe — it is a symlink, and it still leads into the store —
    are checked again at the moment of deletion. Anything else (a real
    directory, a link that has since been repointed, an entry already gone) is
    refused with False rather than an exception, so a caller sweeping a list
    reports what it skipped instead of dying half way.
    """
    path = Path(dup.path)
    if not path.is_symlink() or not resolves_into_store(path):
        return False
    try:
        path.unlink()
    except OSError:
        return False
    return True


def restore_preserve_newer_lock_sections(
        pre_rules: dict, pre_workflows: dict) -> dict[str, list[str]]:
    """After a lock file has been replaced wholesale (snapshot restore),
    re-add rule/workflow entries that were installed live but are absent from
    the just-restored lock.

    A snapshot only archives the skill store (which is where the lock file
    itself lives), never the agent context files a rule's or workflow's
    materialization writes into (``CLAUDE.md``, a rendered slash command,
    ...). Restoring an *older* snapshot therefore drops any rule/workflow
    installed since — its lock entry vanishes with the rest of the archived
    lock, but its materialized file is untouched on disk, so the block
    becomes orphaned: still present, no longer traceable, and impossible to
    ``boost uninstall``.

    Filling the gap rather than overwriting the section outright preserves
    the other, already-correct direction: an entry the snapshot *did* carry
    that was later uninstalled comes back through the normal archived lock
    contents, and :func:`sync_plan`/:func:`sync_apply` re-materializes it
    from its tap same as any other missing materialization. Only names
    genuinely absent from the restored lock are filled in here.

    ``pre_rules``/``pre_workflows`` must be captured by the caller *before*
    the store is emptied for extraction. Returns the names actually kept, per
    section, so the caller can report what changed; writes the lock only when
    there is something to add back.
    """
    kept: dict[str, list[str]] = {"rules": [], "workflows": []}

    def keep(lock: dict) -> bool:
        for section, pre in (("rules", pre_rules), ("workflows", pre_workflows)):
            for name, entry in pre.items():
                if name not in lock[section]:
                    lock[section][name] = entry
                    kept[section].append(name)
        return bool(kept["rules"] or kept["workflows"])
    lockfile.mutate(keep)
    return kept


def lock_vouches(integ: lockfile.Integrity | None = None) -> bool:
    """Whether the lock file can say which store dirs and links are boost's.

    It can when it parses, and when it is missing over an empty store — that
    is a fresh install with nothing to disown. It cannot when it is missing
    over a populated store, corrupt, or written in another schema:
    :func:`lockfile.installed` collapses all three into an empty record, and
    reading that as "nothing is installed" turned `boost sync` — the command
    `boost doctor` prescribes for exactly this state — into an uninstaller that
    removed every live link of an intact install with green ticks and exit 0.
    ``integ`` is a :func:`lockfile.check` the caller already made.

    "Empty" is any dir at all, not :func:`has_content`'s skills: with no lock,
    a link into another tool's bucket in the store (``synced/foo``) is not
    boost's to call stale, and the narrower test swept it. A store boost
    cannot list cannot be called empty either.
    """
    if integ is None:
        integ = lockfile.check()
    if integ.ok:
        return True
    if integ.problem != "missing":
        return False
    root = paths.store_dir()
    try:
        names = os.listdir(root)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return not any(not n.startswith(".")
                   and os.path.isdir(os.path.join(root, n))  # noqa: FURB146
                   for n in names)


def _store_dirs() -> list[str]:
    """Every dir in the store, by name, sorted. A dot entry is boost's own
    (the lock file, ``.trash``) and is never listed."""
    root = paths.store_dir()
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return []
    return [n for n in names if not n.startswith(".")
            and os.path.isdir(os.path.join(root, n))]


def unrecorded_store_dirs(lock: dict) -> list[str]:
    """The store dirs ``lock`` does not record, by name.

    Candidates, not verdicts: whose each one is depends on what else is on the
    machine (:func:`classify_unrecorded`), and whether a lock may be read as
    "none of these are boost's" at all is :func:`lock_vouches`. A name boost
    could not record is :func:`misnamed_store_dirs`'s, not this list's.

    A workflow's skill copy is recorded too, on the workflow
    (:func:`workflow_owned_store_names`), and is not a candidate; nor is one
    the lock has lost, told by the workflow file beside it
    (:func:`workflow_copy_evidence`, :func:`orphaned_workflow_copies`).
    """
    owned = workflow_owned_store_names()
    return [n for n in _store_dirs()
            if n not in lock and n not in owned and util.is_safe_component(n)
            and workflow_copy_evidence(n) is None]


def misnamed_store_dirs() -> list[str]:
    """The store dirs whose name boost cannot record a skill under.

    A name that is not a safe path component (:func:`util.is_safe_component`)
    can never be a lock key, and every path into the store goes through
    :func:`skill_store_dir`, which refuses one. Listed with the other store
    dirs, a Finder duplicate — ``brainstorming copy`` — stopped `boost doctor`
    three checks in and made `sync`, `heal` and the MCP doctor exit with an
    error. Kept apart, it is a note: boost records nothing by that name and
    removes nothing.
    """
    return [n for n in _store_dirs() if not util.is_safe_component(n)]


def classify_unrecorded(names: list[str]) -> dict[str, list]:
    """Sort store dirs no lock entry records by whose they are.

    Returns ``{adoptable_store, older_copies, foreign_store, not_skill_store,
    unreadable_store}``:

    * ``adoptable_store`` — a skill nothing else on this machine claims: one
      written or copied in by hand, or left by another installer. Plain
      ``boost sync`` records it as a local skill and links it out.
    * ``older_copies`` — ``(skill, owner, path)``: a copy in another agent's
      dir that an adoptable skill is newer than. Named, never touched.
    * ``foreign_store`` — ``(skill, owner, path, "identical" | "differs")``: a
      copy of another tool's skill. Only ``boost sync --prune`` removes it.
    * ``not_skill_store`` — a dir with no ``SKILL.md``. Named, never touched.
    * ``unreadable_store`` — ``(skill, path)``: a dir holding ``path``, which
      boost cannot read (:func:`foreign.unreadable`), or one that would be
      adopted while ``path``, a vendor dir that may hold a skill by its name,
      cannot be looked in (:func:`foreign.hidden_vendor_skill`). Whose it is
      cannot be told and it is not recorded; its hash would skip what it
      cannot list, so it is named with that path and never touched.

    These were one bucket, "orphaned store dirs", and ``sync --prune`` deleted
    every dir in it. On the machine this was written against that was 28
    dirs: a skill the user wrote, 26 ports of Cursor's built-in skills, and
    ``synced`` — another tool's sync bucket, a ``manifest.json`` and nine
    skills it keeps in step with an account. Only the ports were copies, and
    16 of those had been rewritten for Codex.

    Ownership is decided before content or time, in :func:`foreign.inventory`
    order. A vendor's built-in or an enabled plugin's skill owns its name: a
    store dir named like one is a copy or a port of it whatever its bytes or
    mtime say, and adopting it would link a Codex port of Cursor's skill into
    Claude Code. A plugin's skill is matched by the store copy's ``SKILL.md``
    name as well as its dir name, since a ``cp -r`` keeps the plugin's dir
    name and Claude Code lists the skill under the other. A copy in an agent's
    own dir is the user's, so it owns the name only when it holds the same
    bytes or is at least as new by file times (:func:`foreign.newest_mtime`).
    That is a heuristic, since a copy that did not preserve times looks new,
    so all it decides is which of the two plain ``boost sync`` records; the
    other copy is named, and only ``--prune`` removes a store copy.

    A store entry that is a second path to one of those skills — a link the
    user made so that the agents reading the store see a skill kept
    elsewhere — is in no bucket. It is not a copy, so ``--prune`` must not
    unlink it, and it is that tool's skill, so boost does not record it.
    "Second path" is decided by inode (:func:`foreign.same_dir`), since a
    case-insensitive volume spells one dir several ways.

    A dir holding a git repository (:func:`foreign.holds_repo`) is never
    identical to anything: the hash does not see ``.git``, and the history
    in it is in no copy. It can still be named like another tool's skill,
    and ``--prune`` still leaves it (:func:`is_repo_copy`).
    """
    buckets: dict[str, list] = {"adoptable_store": [], "older_copies": [],
                                "foreign_store": [], "not_skill_store": [],
                                "unreadable_store": []}
    if not names:
        return buckets
    readable = []
    for name in names:
        sdir = skill_store_dir(name)
        # Looked at before anything is read: a dir with no search bit has no
        # SKILL.md as far as ``os.path.isfile`` can tell, and was called "not
        # a skill" for it. ``os.path`` throughout because ``Path.is_file``
        # raises under such a dir on Python 3.12 and 3.13, and doctor runs this.
        if not os.access(sdir, os.R_OK | os.X_OK):
            buckets["unreadable_store"].append((name, str(sdir)))
        elif not os.path.isfile(sdir / "SKILL.md"):  # noqa: FURB146
            buckets["not_skill_store"].append(name)
        elif (bad := foreign.unreadable(sdir)) is not None:
            buckets["unreadable_store"].append((name, str(bad)))
        else:
            readable.append(name)
    if not readable:
        return buckets
    named = {n: foreign.skill_name(skill_store_dir(n), n) for n in readable}
    found = foreign.inventory([*readable, *named.values()])
    for name in readable:
        sdir = skill_store_dir(name)
        theirs = found.get(name, [])
        if named[name] != name:
            theirs = theirs + [c for c in found.get(named[name], [])
                               if c.kind == foreign.PLUGIN]
        if any(foreign.same_dir(c.path, sdir) for c in theirs):
            continue
        repo = foreign.holds_repo(sdir)
        owned = [c for c in theirs if c.kind != foreign.AGENT]
        if owned:
            # The identical one when there is one: removing the store copy
            # then loses nothing, and the confirm says what it costs.
            same_owner = None if repo else next(
                (c for c in owned if foreign.same_content(sdir, c.path)), None)
            c = same_owner or owned[0]
            buckets["foreign_store"].append(
                (name, c.owner, str(c.path),
                 foreign.IDENTICAL if same_owner else foreign.DIFFERS))
            continue
        same = [] if repo else [c for c in theirs
                                if foreign.same_content(sdir, c.path)]
        if same:
            buckets["foreign_store"].append(
                (name, same[0].owner, str(same[0].path), foreign.IDENTICAL))
            continue
        mine = foreign.newest_mtime(sdir)
        times = {c.path: foreign.newest_mtime(c.path) for c in theirs}
        newer = [c for c in theirs if times[c.path] >= mine]
        if newer:
            c = max(newer, key=lambda c: times[c.path])
            buckets["foreign_store"].append(
                (name, c.owner, str(c.path), foreign.DIFFERS))
            continue
        hidden = foreign.hidden_vendor_skill(name)
        if hidden is not None:
            buckets["unreadable_store"].append((name, str(hidden)))
            continue
        buckets["older_copies"].extend((name, c.owner, str(c.path)) for c in theirs)
        buckets["adoptable_store"].append(name)
    return buckets


def _plugin_hits(name: str, index: dict) -> list[tuple[foreign.Plugin, Path]]:
    """The enabled plugins' skills store/``name`` may be another copy of.

    Looked up by the dir name, then by the store copy's ``SKILL.md`` name,
    which is what :func:`foreign.plugin_skills` keys a skill by: a ``cp -r``
    of a plugin's skill keeps the plugin's dir name, while Claude Code lists
    the skill under its frontmatter name.
    """
    hits: list[tuple[foreign.Plugin, Path]] = []
    for key in dict.fromkeys((name, foreign.skill_name(skill_store_dir(name), name))):
        hits.extend(index.get(key, ()))
    return hits


def covering_plugin(name: str, index: dict | None = None
                    ) -> tuple[foreign.Plugin, Path] | None:
    """The enabled plugin that ships the same files as store/``name``, or None.

    Claude Code loads a plugin's skill as ``/<plugin>:<skill>`` and a linked
    one as ``/<skill>`` (sources in :mod:`foreign`), so a link to a skill a
    plugin already ships makes Claude Code list it twice, and the model reads
    the same description twice. Only the same bytes count: two skills that
    share a name are both worth having. ``index`` is a
    :func:`foreign.plugin_index` the caller already read.
    """
    if index is None:
        index = foreign.plugin_index()
    if not index:
        return None
    sdir = skill_store_dir(name)
    return next((hit for hit in _plugin_hits(name, index)
                 if foreign.same_content(sdir, hit[1])), None)


def plugin_serves(how: str) -> bool:
    """True when the plugin's copy is the one Claude Code should list.

    ``how`` is a :func:`plugin_coverage` verdict: the same files, or a copy
    the dates show is newer than boost's. Then boost makes no Claude Code
    link, `sync` and `doctor` count none missing, and ``sync --prune`` drops
    the one boost has. Every other verdict keeps boost's link.
    """
    return how == foreign.IDENTICAL or foreign.split_how(how)[0] == foreign.NEWER_IN_PLUGIN


def _weigh(sdir: Path, hits: list[tuple[foreign.Plugin, Path]],
           updated_at: str | None) -> tuple[foreign.Plugin, Path, str]:
    """``(plugin, its copy, how)``: which of ``hits`` to weigh store copy ``sdir`` against.

    The one with the same files, whichever comes first. Otherwise, with a
    date for boost's copy, the newest copy a plugin ships that is newer than
    it, else the first plugin, by id, with the verdict
    :func:`foreign.newest_copy` gives it (:func:`foreign.dated_how`). With
    no date for boost's copy nothing is dated, and it reads
    :data:`foreign.DIFFERS` as before.
    """
    same = next((h for h in hits if foreign.same_content(sdir, h[1])), None)
    if same is not None:
        return (*same, foreign.IDENTICAL)
    boost_at = util.epoch_from_iso(updated_at)
    if boost_at is None:
        return (*hits[0], foreign.DIFFERS)
    weighed = []
    for plugin, theirs in hits:
        when, source = foreign.plugin_skill_updated_at(plugin, theirs)
        how = foreign.dated_how(foreign.newest_copy(boost_at, when, source), source)
        weighed.append((plugin, theirs, how, when or 0.0))
    newer = [w for w in weighed if plugin_serves(w[2])]
    plugin, theirs, how, _when = (max(newer, key=operator.itemgetter(3)) if newer
                                  else weighed[0])
    return plugin, theirs, how


def serving_plugin(name: str, updated_at: str | None, index: dict | None = None
                   ) -> tuple[foreign.Plugin, Path, str] | None:
    """The enabled plugin whose copy of ``name`` Claude Code should list, or None.

    :func:`covering_plugin`'s, or one whose copy is newer than boost's, which
    changed last at ``updated_at`` (:func:`source_updated_at`). The third
    value is the verdict (:func:`plugin_serves`). Boost cannot turn a plugin
    off — Claude Code's settings are never written — so when two copies
    differ, the way to show only the newer is to withhold boost's link when
    it is the older.
    """
    if index is None:
        index = foreign.plugin_index()
    hits = _plugin_hits(name, index) if index else []
    if not hits:
        return None
    found = _weigh(skill_store_dir(name), hits, updated_at)
    return found if plugin_serves(found[2]) else None


def plugin_coverage(lock: dict, index: dict | None = None
                    ) -> dict[str, tuple[str, str, str]]:
    """``{skill: (plugin id, plugin's copy, how)}`` for each skill in ``lock``
    whose scope takes in Claude Code that a plugin also ships.

    ``how`` is "identical", "differs", or for a different skill whose dates
    say which copy is newer a :func:`foreign.dated_how` verdict (:func:`_weigh`
    picks the plugin). The ones :func:`plugin_serves` accepts keep boost from
    linking the skill into Claude Code: `sync` creates no such link and
    reports none missing or blocked. The rest are notes. Left out: a
    quarantined or sidelined skill, which has no link to weigh, and a store
    copy without its ``SKILL.md``, which has nothing to compare.
    """
    linking = agents.linking_agents()
    if foreign.CLAUDE not in linking:
        return {}
    if index is None:
        index = foreign.plugin_index()
    if not index:
        return {}
    found = {}
    for name in sorted(lock):
        entry = lock[name]
        if (entry.get("quarantined") or entry.get("sidelined_by")
                or foreign.CLAUDE not in scoped_agents(entry, linking)):
            continue
        sdir = skill_store_dir(name)
        if not os.path.isfile(sdir / "SKILL.md"):  # noqa: FURB146
            continue
        hits = _plugin_hits(name, index)
        if not hits:
            continue
        plugin, theirs, how = _weigh(sdir, hits, entry.get("source_updated_at"))
        found[name] = (plugin.id, str(theirs), how)
    return found


def covered_skills(coverage: dict[str, tuple[str, str, str]]) -> set[str]:
    """The skills in ``coverage`` (:func:`plugin_coverage`) whose plugin's copy
    Claude Code should list (:func:`plugin_serves`): the ones boost makes no
    Claude Code link for."""
    return {n for n, (_p, _t, how) in coverage.items() if plugin_serves(how)}


def left_to_plugin(name: str, agent: str, link: Path, covered: set[str]) -> bool:
    """True when ``agent``'s missing or blocked ``link`` to ``name`` is no fault.

    It is Claude Code's, for a skill an enabled plugin ships with the same
    files (``covered``, :func:`covered_skills`), and boost's link is not
    already there: :func:`link_agents` makes none, so `sync` must not offer to
    and `doctor` must not report one missing. A link already there is
    :func:`plugin_duplicates`' to report.
    """
    return (agent == foreign.CLAUDE and name in covered
            and not (os.path.islink(link)  # noqa: FURB146
                     and _already_links(link, skill_store_dir(name))))


def plugin_duplicates(lock: dict | None = None,
                      coverage: dict | None = None) -> list[tuple[str, str, str, str]]:
    """``(skill, plugin id, plugin's copy, "identical" | "differs")`` for each
    skill boost links into Claude Code that an enabled plugin also loads.

    Only while boost's link is there and leads to the store copy: that link is
    what makes Claude Code list the skill twice, and the one thing ``sync
    --prune`` may remove (:func:`drop_plugin_link`). A covered skill gets no
    new link (:func:`link_agents`), so a row is a link made before the plugin
    shipped the skill, or before boost looked. ``coverage`` is a
    :func:`plugin_coverage` the caller already read.
    """
    if lock is None:
        lock = lockfile.installed()
    if coverage is None:
        coverage = plugin_coverage(lock)
    adir = agents.linking_agents().get(foreign.CLAUDE)
    if adir is None:
        return []
    found = []
    for name, (plugin_id, theirs, how) in coverage.items():
        link = adir / name
        if (os.path.islink(link)  # noqa: FURB146
                and _already_links(link, skill_store_dir(name))):
            found.append((name, plugin_id, theirs, how))
    return found


def sort_unrecorded(lock: dict, integ: lockfile.Integrity | None = None
                    ) -> dict[str, list]:
    """The :func:`sync_plan` buckets for the store dirs ``lock`` does not record.

    What they can mean depends on the lock file (``integ``, a
    :func:`lockfile.check` the caller already made):

    * it parses — :func:`classify_unrecorded` says whose each one is;
    * it is missing — the same, except that a dir boost may have installed is
      queued in ``unrecorded_store`` for :func:`recover_unrecorded`: one
      nothing else claims, and a copy of another tool's skill that an agent's
      link into the store still leads to, since boost links only what it
      installed. Every dir used to be queued, so a lost lock re-recorded a
      copy of Cursor's built-in as boost's and the next sync linked it into
      every agent, beside Cursor's own. With a lock, the same dir is a copy;
    * it is corrupt or in another schema — nothing it says can be read, so
      every dir is ``unrecorded_store``, which sync never writes over.

    ``misnamed_store`` (:func:`misnamed_store_dirs`) is answered whatever the
    lock says. ``rule_blocks`` (:func:`orphaned_rule_blocks`) is answered
    unless the lock is unreadable, when every block would look unrecorded.
    """
    if integ is None:
        integ = lockfile.check()
    names = unrecorded_store_dirs(lock)
    out: dict[str, list] = {"adoptable_store": [], "older_copies": [],
                            "foreign_store": [], "not_skill_store": [],
                            "unreadable_store": [], "unrecorded_store": [],
                            "misnamed_store": misnamed_store_dirs(),
                            "workflow_copies": orphaned_workflow_copies(lock),
                            "rule_blocks": []}
    if not integ.ok and integ.problem != "missing":
        out["unrecorded_store"] = names
        return out
    out["rule_blocks"] = orphaned_rule_blocks()
    out.update(classify_unrecorded(names))
    if integ.ok:
        return out
    linking = agents.linking_agents()
    linked = [r for r in out["foreign_store"]
              if any(os.path.islink(d / r[0])
                     and _already_links(d / r[0], skill_store_dir(r[0]))
                     for d in linking.values())]
    out["unrecorded_store"] = sorted([*out["adoptable_store"], *(r[0] for r in linked)])
    out["foreign_store"] = [r for r in out["foreign_store"] if r not in linked]
    out["adoptable_store"] = []
    return out


#: Plan buckets that name something boost leaves alone by design. They are
#: reported and never counted as issues: counting them would hold every health
#: surface red on a state no boost command will change.
INFORMATIONAL = ("older_copies", "not_skill_store", "misnamed_store")


def plan_issues(plan: dict[str, list]) -> int:
    """How many problems a :func:`sync_plan` holds: one per item.

    That is the MCP doctor's count. `boost doctor` raises one issue per check
    line instead, and one line can name several items, so the two totals
    differ whenever a line does.

    A plugin duplicate is one only when the plugin's copy is the one to list
    (:func:`plugin_serves`): identical, or newer than boost's. Then boost's
    link adds nothing current and ``sync --prune`` can drop it. Otherwise
    boost's link is kept, so that one is a note.
    """
    return sum(len(v) for k, v in plan.items()
               if k not in (*INFORMATIONAL, "plugin_duplicates")) + sum(
        1 for d in plan.get("plugin_duplicates", ()) if plugin_serves(d[3]))


def sync_plan() -> dict[str, list]:
    """Compare lock file <-> store <-> agent symlinks.

    Returns {missing_store, missing_links, blocked_links, stale_links, ...}
      missing_store:  lock entries whose store dir is gone
      missing_links:  (skill, agent) pairs that should be linked but aren't,
                      and that sync *can* create — including a live boost
                      link into another skill's store dir (:func:`misdirected`)
      blocked_links:  (skill, agent, path) where something that is not a boost
                      symlink occupies the link path — sync will not clobber it
      stale_links:    paths in agent dirs that are broken/unmanaged symlinks
      adoptable_store, older_copies, foreign_store, not_skill_store,
      unreadable_store:
                      store dirs not present in the lock file, sorted by whose
                      they are (:func:`classify_unrecorded`)
      misnamed_store: store dirs whose name boost cannot record a skill under
                      (:func:`misnamed_store_dirs`) — reported, never touched
      workflow_copies: (name, workflow file) for a workflow's skill copy no
                      lock entry records (:func:`orphaned_workflow_copies`) —
                      never adopted as a skill; `boost install` re-records
      rule_blocks:    (rule, context file) for a managed rule block no lock
                      entry records (:func:`orphaned_rule_blocks`) — never
                      stripped; `boost install` re-records
      plugin_duplicates: skills boost links into Claude Code that an enabled
                      plugin also loads (:func:`plugin_duplicates`)
      unrecorded_store: store dirs the lock file has lost, or cannot be read
                      about (:func:`sort_unrecorded`) — never pruned,
                      re-recorded by :func:`sync_apply` when the lock is
                      merely missing
      out_of_scope_links: (skill, agent) pairs linked outside a declared
                      ``--agent`` narrowing — reported, never auto-removed

    ``blocked_links`` exists because lumping it into ``missing_links`` made
    ``boost sync`` promise a repair it could never perform. ``link_agents``
    refuses to delete a real file or directory it does not own (right), records
    it in ``.conflicts`` — and ``sync_apply`` dropped that on the floor, so the
    command printed "everything in sync" while ``boost doctor`` went on
    reporting the same skill unlinked and prescribing ``boost sync``. Seen for
    real where another installer had written ``~/.claude/skills/hyperframes``
    as a directory: a closed loop with no exit.
    """
    lock = lockfile.installed()
    integ = lockfile.check()
    vouches = lock_vouches(integ)
    # A skill an enabled plugin ships with the same files gets no Claude Code
    # link (`link_agents`), so a missing or blocked one is no repair to make:
    # reporting it had `boost sync` recreate the duplicate `--prune` dropped.
    coverage = plugin_coverage(lock)
    covered = covered_skills(coverage)
    # An agent whose skills dir has a file or a dangling link in the way:
    # `link_agents` skips it, so listing its links as missing made `boost
    # sync` print "everything in sync" over the repair it had just skipped.
    # Its links are blocked, by what is in the way.
    in_the_way = {a: b for a, d in agents.linking_agents().items()
                  if (b := paths.refuses_writes(d)) is not None
                  and paths.in_the_way(b)}
    plan: dict[str, list] = {"missing_store": [], "missing_links": [],
            "blocked_links": [], "stale_links": [], "adoptable_store": [],
            "older_copies": [], "foreign_store": [], "not_skill_store": [],
            "unreadable_store": [], "misnamed_store": [],
            "workflow_copies": [], "rule_blocks": [],
            "plugin_duplicates": [], "unrecorded_store": [],
            "missing_materializations": [], "out_of_scope_links": []}
    for name, entry in lock.items():
        sdir = skill_store_dir(name)
        # A directory with no SKILL.md counts as missing, not as healthy. The
        # check used to be `is_dir()` alone, and the gap was reachable: an
        # interrupted copy, a partial rsync or a user deleting the file leaves
        # the directory behind. `boost edit` and `boost evolve` both refuse such
        # a skill with the hint "repair the store with `boost sync`" — and sync
        # would answer "everything in sync", change nothing, and send the reader
        # back to the same error. The remedy named the step they had just run.
        #
        # `missing_store` is the right bucket rather than a new one: its repair
        # is already "reinstall this skill from its tap", which is exactly what
        # a gutted directory needs, and reusing it means sync_apply needs no
        # change at all.
        #
        # This used to `continue` here, which skipped agent-link classification
        # for the entry entirely — so a foreign file already occupying a link
        # path went unreported until a *second* `sync` noticed the repair had
        # not actually relinked that agent. The classification below reads
        # only the agent dir, never the store, so running it costs nothing
        # even while the store copy is still missing — see the `missing_store`
        # check further down, which still lets it feed `blocked_links` but
        # keeps it out of `missing_links`: `sync_apply` repairs a missing
        # store by reinstalling from the tap, which relinks every non-blocked
        # agent as one step, and that reinstall runs *after* this plan is
        # built, so a `missing_links` entry here would have `sync_apply` try
        # to link a store directory that does not exist yet.
        missing_store = not sdir.is_dir() or not (sdir / "SKILL.md").is_file()
        if missing_store:
            plan["missing_store"].append(name)
        if entry.get("quarantined"):
            continue
        # A deliberate sideline (`focus`, `profile use`, `context apply`)
        # unlinks on purpose and records it in `sidelined_by` — so the missing
        # links below are not damage to repair. Without this check `sync`
        # relinked every sidelined skill, undoing the switch it was never told
        # about.
        if entry.get("sidelined_by"):
            continue
        # Only the agents this skill was installed for. Walking every enabled
        # agent made `boost sync` a second path to the scope leak that
        # `preserved_agent_scope` closed on the install side: it reported a
        # missing_link for each agent outside the narrowing, and sync_apply
        # dutifully linked them, undoing `install --agent` in one command.
        # linking_agents, not enabled_agents: an agent that reads the canonical
        # store has no link to be missing, and reporting one would make `boost
        # sync` create the very duplicate `links_skills: false` exists to avoid.
        linking = agents.linking_agents()
        in_scope = scoped_agents(entry, linking)
        for agent, adir in in_scope.items():
            link = adir / name
            if left_to_plugin(name, agent, link, covered):
                continue
            if agent in in_the_way:
                plan["blocked_links"].append(
                    (name, agent, str(in_the_way[agent])))
                continue
            # boost's kind of link is boost's to replace even when it
            # dangles. A live link leads somewhere, whoever's it is. Anything
            # else is someone else's and stays put: a dangling link of the
            # user's — a checkout on an unmounted volume — counted as boost's,
            # and sync swapped it for a link to the store copy.
            # ``os.path``: under a dotdir with no search bit ``Path.is_symlink``
            # raises on Python 3.12 and 3.13, and `boost sync`, `heal` and
            # `doctor` all exited 70 on it.
            # A live link into another skill's store dir is boost's, and
            # wrong: the agent loads that skill under this one's name. It is
            # a missing link, which `link_agents` repairs by replacing it.
            if os.path.islink(link) and os.path.exists(link):  # noqa: FURB141
                if not missing_store and misdirected(name, link) is not None:
                    plan["missing_links"].append((name, agent))
                continue
            if os.path.lexists(link) and not is_boost_link(link):
                plan["blocked_links"].append((name, agent, str(link)))
            elif not missing_store:
                plan["missing_links"].append((name, agent))
        # The other direction, which nothing checked: a link that exists in an
        # agent the declaration excludes. The loop above is narrowed to the
        # declared set, and the stale-link sweep below keys on the skill *name*
        # being absent from the lock — so a live, boost-owned link outside a
        # narrowing fell between the two and no command could see it. Only
        # meaningful when a narrowing was declared; without one `scoped_agents`
        # fails open and every agent is in scope by definition.
        # boost's links only: the user's own link where adoption left it is
        # the user's, and `--prune` removed it as out of scope.
        plan["out_of_scope_links"].extend(
            (name, agent) for agent in out_of_scope_agents(name, entry, linking))
    plan.update(sort_unrecorded(lock, integ))
    plan["plugin_duplicates"] = plugin_duplicates(lock, coverage)
    plan["stale_links"] = stale_links(lock, vouches)
    return _plan_materializations(plan)


def stale_links(lock: dict, vouches: bool) -> list[str]:
    """Paths in agent dirs that ``boost sync`` and ``heal`` remove as stale.

    A boost link (:func:`points_into_store`) that dangles, or — while the lock
    can vouch — one named for no installed skill. One function so ``doctor``
    reports exactly what heal will remove: it counted the dangling ones only,
    called a live ``~/.claude/skills/ghost -> ~/.agents/skills/x`` healthy,
    and the next heal deleted it.
    """
    found: list[str] = []
    # A live link into a store dir the lock does not record leads to that
    # dir, whoever's it is, so it is not stale: the sweep used to exempt only
    # the skills sync was about to record, and removed the links into a copy
    # of Cursor's skill, another tool's bucket or a misnamed dir one line
    # above the lines saying those dirs were left alone. One into a dir
    # `--prune` deletes dangles afterwards, and the next sync sweeps it.
    unrecorded = {n for n in _store_dirs() if n not in lock}
    # linking_agents, not enabled_agents: boost only ever creates a symlink in
    # an agent it links for, so a link in a native-store agent's skills dir was
    # put there by something else — and the sweep's only ownership test is
    # `points_into_store`, which such a link passes. `boost sync` would have
    # deleted another tool's files without `--prune-duplicates` ever being
    # typed. Same "topology, not ownership" line as duplicate_discovery, which
    # reports those entries and removes nothing. Disabled agents are swept
    # too (`unlinking_agents`): boost linked there while they were enabled.
    # Former dirs too: an agent whose dir was repointed left its old links.
    for adir in agents.sweep_dirs():
        if not os.path.isdir(adir):  # noqa: FURB146
            continue
        # Ownership first, for broken links too: the old test short-circuited
        # on `not link.exists()`, so any dangling symlink a user happened to
        # keep in ~/.claude/skills was swept up by `boost sync`.
        #
        # "Not in the lock" means "not installed" only while the lock can
        # vouch. Without that guard a missing lock made every live link
        # into an intact store look stale, and sync removed them all.
        found.extend(
            str(link) for link in adir.iterdir()
            if (link.is_symlink() and points_into_store(link)
                and (_dangles(link)
                     or (vouches and link.name not in lock
                         and _store_entry(link) not in unrecorded))))
    return found


def _plan_materializations(plan: dict[str, list]) -> dict[str, list]:
    """Fill ``plan["missing_materializations"]`` and return ``plan``."""
    # Rules/workflows don't live in the store — they materialize into agent dirs.
    # A materialization whose file (or CLAUDE.md block) is gone can be repaired
    # by re-materializing from the tap, same as a missing skill store dir.
    for name, entry in lockfile.installed_rules().items():
        # A quarantined rule's materializations are ABSENT BY DESIGN — the
        # stash holds them. Repairing here would re-arm what quarantine
        # disarmed, making `boost sync` an accidental release.
        #
        # A stranded one's are absent because its repo was deleted, and
        # "repairing" it recreated that repo (`scopes.stranded`). `install`
        # now refuses the write, so listing it here would only turn every
        # `boost sync` into a failure line; doctor names it with its remedy.
        if entry.get("quarantined") or scopes.stranded(entry):
            continue
        if any(m.get("unwritable") or m.get("stale")
               or not _rule_materialization_ok(name, m)
               for m in entry.get("materializations") or []
               if materialization_is_written("rule", entry, m)) \
                or _freed_foreign(entry, "rule") \
                or unmaterialized_agents("rule", entry):
            plan["missing_materializations"].append(("rule", name))
    for name, entry in lockfile.installed_workflows().items():
        if entry.get("quarantined") or scopes.stranded(entry):
            continue
        if any(m.get("unwritable") or m.get("stale")
               or not os.path.isfile(m.get("path", ""))
               for m in entry.get("materializations") or []
               if materialization_is_written("workflow", entry, m)) \
                or _freed_foreign(entry) \
                or unmaterialized_agents("workflow", entry):
            plan["missing_materializations"].append(("workflow", name))
    return plan


def _dangles(link: Path) -> bool:
    """True when the symlink ``link`` is known to lead nowhere.

    Known, not presumed: ``exists()`` answers False for a target boost may not
    look at, and under a store with no search bit every live link read as a
    broken one for the sweep to remove. A loop leads nowhere too: ``ELOOP``,
    or on Windows ERROR_CANT_RESOLVE_FILENAME (1921), which Python does not
    map to ``ELOOP``.
    """
    try:
        link.stat()
    except (FileNotFoundError, NotADirectoryError):
        return True
    except OSError as err:
        return (err.errno == errno.ELOOP
                or getattr(err, "winerror", None) == 1921)
    return False


def _store_entry(link: Path) -> str | None:
    """The store dir ``link`` leads into, by name, or None if none."""
    try:
        rel = os.path.relpath(os.path.realpath(link),
                              os.path.realpath(paths.store_dir()))
    except ValueError:
        return None
    head = rel.split(os.sep, 1)[0]
    return None if head in (os.curdir, os.pardir) else head


def _rule_materialization_ok(name: str, m: dict) -> bool:
    """True if a rule materialization is still present: a file drop must exist,
    and a Claude rule's CLAUDE.md must still carry its managed block."""
    from . import rules
    p = Path(m.get("path", ""))
    if m.get("mode") == rules.MODE_CLAUDE:
        try:
            return p.exists() and ("boost:rule:%s start" % name) in \
                p.read_text(encoding="utf-8")
        except OSError:
            return False
    # ``os.path``: ``Path.is_file`` raises under a dotdir with no search bit on
    # Python 3.12 and 3.13, and `boost sync` exited 70 on a rule there.
    return os.path.isfile(p)  # noqa: FURB146


def prune_out_of_scope_links(plan: dict[str, list]) -> list[str]:
    """Remove the links :func:`sync_plan` found outside a declared scope.

    Kept out of :func:`sync_apply` on purpose. Everything sync_apply does is
    either additive or removes something already broken, so `boost sync` and
    `boost heal` are safe to run blind. These links are neither broken nor
    unowned — they work, and an agent is using them — so deleting one changes
    which agents can run a skill. That is a decision, and it belongs behind the
    same explicit opt-in as deleting a store dir that copies another tool's
    skill (`--prune`).
    """
    removed = []
    linking = agents.linking_agents()
    for name, agent in plan.get("out_of_scope_links", []):
        adir = linking.get(agent)
        if adir is None:      # disabled between plan and prune
            continue
        link = adir / name
        # Asked again: the confirm before this can wait as long as it likes.
        if is_boost_link(link):
            link.unlink()
            entry = lockfile.get_skill(name)
            if entry:
                entry["agents"] = [a for a in entry.get("agents") or []
                                   if a != agent]
                lockfile.set_skill(name, entry)
            removed.append("unlinked %s → %s (outside declared scope)"
                           % (name, agent))
    if removed:
        journal.log("sync-prune", "%d links" % len(removed))
    return removed


def _skill_source_sha(cat_entry: dict) -> str | None:
    """sha256 of a catalog entry's tap source directory, or None if unreadable."""
    try:
        return skill_source_sha(cat_entry)
    except BoostError:
        return None


def _source_text_sha(tap_name: str, cat_entry: dict) -> str | None:
    """sha256 of a rule/workflow's tap source text, or None if unreadable."""
    import hashlib
    try:
        src = registry.get(tap_name).path / cat_entry.get("skill_md", "")
        return hashlib.sha256(src.read_text(
            encoding="utf-8", errors="replace").encode("utf-8")).hexdigest()
    except (OSError, BoostError):
        return None


def _pinned_repair_blocked(entry: dict, source_sha: str | None) -> bool:
    """True when repairing ``entry`` from its tap would bypass a pin.

    sync repairs by re-installing from the tap's CURRENT content. For an
    unpinned entry that is the point of `boost sync`; for a pinned one whose
    source has moved it would be the covert update the pin exists to prevent —
    the same guard the update loops apply, on the repair path. An unreadable
    source fails closed: better to leave a pinned item broken and say so than
    to guess.
    """
    if not entry.get("pinned"):
        return False
    return source_sha is None or source_sha != entry.get("sha256")


def _pin_blocks_repair(entry: dict, source_sha) -> bool:
    """:func:`_pinned_repair_blocked`, with the sha computed only if it matters.

    ``source_sha`` is a *callable*. Hashing a tap source goes through
    :func:`source_dir_for`, which calls ``gitutil.materialize`` — a
    ``sparse-checkout add``, i.e. a write and sometimes a network fetch. The
    eager call was harmless on the apply path (the install materializes anyway)
    and is not on the preview path, where it would make `heal --dry-run` widen
    a clone's cone. An unpinned entry can never be blocked, so it never needs
    the answer.
    """
    if not entry.get("pinned") and not entry.get("commit_pin"):
        return False
    if moved_off_commit_pin(entry, entry.get("tap")) is not None:
        return True
    return bool(entry.get("pinned")) and _pinned_repair_blocked(
        entry, source_sha())


def moved_off_commit_pin(entry: dict, tap_name: str | None) -> str | None:
    """The tap HEAD a re-install would record over ``entry``'s commit pin.

    ``None`` when there is no commit pin, or the tap still sits on it. A
    re-install records the tap's *current* commit, so installing anything
    else would move the item off the commit ``boost pin --commit`` froze —
    even with byte-identical content, `boost verify` then fails. An unreadable
    tap answers ``""``, which still blocks: fail closed, as the sha guard does.
    """
    pin = entry.get("commit_pin")
    if not pin:
        return None
    try:
        head = gitutil.head_commit(registry.get(str(tap_name)).path)
    except BoostError:
        head = ""
    return None if head == pin else head


def reinstall_candidates(scope: str | None,
                         base=None) -> list[tuple[str, str, dict]]:
    """What ``boost reinstall`` addresses at ``scope``, as ``(kind, name, entry)``.

    ``None`` is the user lock as recorded, whatever scope each row names (the
    behaviour before ``reinstall`` took a scope flag). ``"user"`` keeps only
    the rows recorded at user scope. ``"project"`` is the repo at ``base``: its
    own lock's skills, plus the rules and workflows the user lock records as
    installed into that repo. Kinds come in lock-section order and names
    sorted within each, so ``--all`` output is stable.
    """
    found: list[tuple[str, str, dict]] = []
    for kind, section in lockfile.all_installed().items():
        if kind == "skill" and scope == scopes.SCOPE_PROJECT:
            # A repo's skills live in its own lock, never in the user one.
            if base is not None:
                found.extend(("skill", name, {**entry,
                                              "scope": scopes.SCOPE_PROJECT})
                             for name, entry in sorted(
                                 projectlock.installed(base).items()))
            continue
        for name, entry in sorted(section.items()):
            at = entry.get("scope", scopes.SCOPE_USER)
            # scopes.owns, not a local resolve(): it is the predicate
            # `uninstall --local` and `list --local` use, and it refuses a
            # relative `base`, which resolve() would read against the cwd and
            # so hand every repo the same row.
            if (scope is None or scope == at == scopes.SCOPE_USER
                    or (scope == scopes.SCOPE_PROJECT
                        and scopes.owns(entry, base))):
                found.append((kind, name, entry))
    return found


def reinstall_pin_hold(kind: str, lk: dict, cat_entry: dict | None = None,
                       src: Path | None = None) -> str | None:
    """Why ``boost reinstall`` must not touch ``lk``, or ``None`` if it may.

    Reinstall exists to put the *same* content back, which a pin allows. What
    a pin forbids is the move: re-installing a pinned item whose source has
    changed since (the tap moved, `boost update` skipped it) used to install
    the new version under the old pin, and a commit-pinned one recorded a
    commit nobody pinned. The same guard `boost sync` applies to repair.
    ``cat_entry`` is the tap source, ``src`` a local one.
    """
    if not lk.get("pinned") and not lk.get("commit_pin"):
        return None
    if cat_entry is not None:
        head = moved_off_commit_pin(lk, cat_entry.get("tap"))
        if head is not None:
            return ("commit-pinned at %s, and %s is now at %s"
                    % (str(lk["commit_pin"])[:12], cat_entry.get("tap"),
                       head[:12] or "an unreadable commit"))
        sha = (_skill_source_sha(cat_entry) if kind == "skill"
               else _source_text_sha(str(cat_entry.get("tap")), cat_entry))
    elif src is not None:
        sha = _local_source_sha(src)
    else:
        return None
    if lk.get("pinned") and _pinned_repair_blocked(lk, sha):
        return ("pinned at v%s, and its source has changed since"
                % lk.get("version", "0.0.0"))
    return None


@dataclass(frozen=True)
class StoreRepair:
    """The branch `sync_apply` will take for one missing skill, rule or workflow.

    Both the repair and its preview read this, so they cannot disagree about
    *which* repair happens — the defect it exists to close was `heal --dry-run`
    printing "would restore X from its tap (or drop it from the lock)" on a
    state where the live run demonstrably reinstalls, offering an alternative
    that never fired. Tense is still each caller's business; the decision is not.

    ``preview`` is a prediction, not a promise: an install can still fail (a
    tap clone removed between the two calls), and a failed install falls
    through to the drop. That residue is the honest kind — it names the branch
    the run will *attempt*, rather than listing both and committing to neither.
    """

    action: str                     #: local | tap | declined | drop
    preview: str
    applied: str
    warning: str | None = None
    cat_entry: dict | None = None   #: what a "tap" repair installs
    src: Path | None = None         #: what a "local" repair installs from
    scope: str = "user"             #: where a rule/workflow re-materializes
    base: str | None = None


_NOT_REMATERIALIZED = " was not re-materialized: "


def is_unrepaired(action: str) -> bool:
    """True for a :func:`sync_apply` line that reports a repair it did *not*
    make, so callers print it as a warning rather than under a check mark."""
    return any(mark in action for mark in (
        _NOT_REMATERIALIZED, _NOT_LINKED_MARK, _NOT_RECORDED_MARK,
        _DECLINED_MARK, _NOT_CLONED_MARK, _PROJECT_GONE_MARK,
        _NOT_VOUCHED_MARK))


#: A pin that blocks a repair. Missing from :func:`is_unrepaired` until it was
#: added, so `heal` printed the decline under a ✓ and exited 0 over a skill
#: still missing, and `doctor` went on prescribing `heal`.
_DECLINED_MARK = " — repair declined "
#: A project skill :func:`project_sync_apply` could not re-materialize. `heal`
#: repairs project copies through it now, and must not exit 0 over one.
_PROJECT_GONE_MARK = " is missing from the project but its source is gone"
#: A URL import's store dir, which sync never re-clones -- also a decline.
_NOT_CLONED_MARK = "'s store dir is missing — `boost reinstall "


_DROPPED = "dropped %s from lock (store dir missing, source gone)"
_GONE = ("%s %s has a missing materialization but its source is gone — "
         "run `boost update` or reinstall")


def _declined(label: str, where: str, name: str) -> str:
    return ("%s is pinned and its %s source has moved%s"
            "(`boost unpin %s`, then `boost reinstall %s` to accept the new "
            "content)" % (label, where, _DECLINED_MARK, name, name))


def _lock_source(name: str, tap_name: str, entry: dict,
                 kind: str | None = None) -> tuple[dict | None, str | None]:
    """The catalog entry a repair would reinstall ``name`` from, and a warning.

    ``(None, None)`` when the tap cannot answer, which both callers treat as a
    source that is gone.
    """
    from . import catalog
    try:
        matches = [e for e in catalog.find(name) if e["tap"] == tap_name
                   and (kind is None or e.get("kind", "skill") == kind)]
        return catalog.select_lock_source(matches, entry)
    except BoostError:
        return None, None


def plan_missing_store(name: str) -> StoreRepair:
    """How `sync` will repair `name`, whose store dir is gone. Read-only."""
    entry = lockfile.get_skill(name) or {}
    tap_name = entry.get("tap")
    if is_url_import(entry):
        # A URL import can be repaired only by cloning its repo again, and sync
        # never touches the network. Dropping the entry instead would throw
        # away the one record of where the skill came from, so keep it and
        # name the command that can.
        msg = ("%s%s%s` clones it again from %s"
               % (name, _NOT_CLONED_MARK, name, entry["source_url"]))
        return StoreRepair("declined", msg, msg)
    if tap_name == "local":
        src = local_source_dir(entry)
        if src is not None:
            if _pin_blocks_repair(entry, lambda: _local_source_sha(src)):
                msg = _declined(name, "local", name)
                return StoreRepair("declined", msg, msg)
            return StoreRepair(
                "local", src=src,
                preview="would reinstall %s from local source %s" % (name, src),
                applied="reinstalled missing %s from local source %s" % (name, src))
    elif tap_name:
        cat_entry, warning = _lock_source(name, tap_name, entry)
        if cat_entry:
            if _pin_blocks_repair(entry, lambda: _skill_source_sha(cat_entry)):
                msg = _declined(name, "tap", name)
                return StoreRepair("declined", msg, msg, warning=warning)
            return StoreRepair(
                "tap", cat_entry=cat_entry, warning=warning,
                preview="would reinstall %s from %s" % (name, tap_name),
                applied="reinstalled missing %s from %s" % (name, tap_name))
    return StoreRepair(
        "drop",
        preview="would drop %s from the lock (store dir missing, source gone)" % name,
        applied=_DROPPED % name)


def plan_missing_materialization(kind: str, name: str) -> StoreRepair:
    """How `sync` will repair a rule/workflow whose files are gone. Read-only."""
    getter = lockfile.get_rule if kind == "rule" else lockfile.get_workflow
    entry = getter(name) or {}
    tap_name = entry.get("tap")
    if tap_name and tap_name != "local":
        cat_entry, warning = _lock_source(name, tap_name, entry, kind=kind)
        if cat_entry:
            if _pin_blocks_repair(
                    entry, lambda: _source_text_sha(tap_name, cat_entry)):
                msg = _declined("%s %s" % (kind, name), "tap", name)
                return StoreRepair("declined", msg, msg, warning=warning)
            # The lock's scope/base, so a project rule repairs into its repo,
            # not wherever sync happens to run.
            return StoreRepair(
                "tap", cat_entry=cat_entry, warning=warning,
                scope=entry.get("scope", "user"), base=entry.get("base"),
                preview="would re-materialize %s %s from %s" % (kind, name, tap_name),
                applied="re-materialized %s %s from %s" % (kind, name, tap_name))
    # One sentence in both tenses because it has only one: this branch repairs
    # nothing, it reports. A "would ..." here would invent an action.
    return StoreRepair("drop", preview=_GONE % (kind, name),
                       applied=_GONE % (kind, name))


def _local_source_sha(src: Path) -> str | None:
    """sha256 of a local skill's source directory, or None if unreadable."""
    try:
        return util.sha256_dir(src)
    except OSError:
        return None


def sync_preview(plan: dict[str, list]) -> list[str]:
    """What :func:`sync_apply` would report, without applying any of it.

    Only the buckets whose repair *branches* live here; `missing_links` and
    `stale_links` do one unconditional thing each and stay with their caller,
    which filters them against the links it has already reported.
    """
    lines = []
    integ = lockfile.check()
    if integ.problem == "older":
        lines.append(lockfile.older_line(integ, dry=True))
    # `sync_apply` re-records only while the lock file is *missing* — a corrupt
    # one is left for `boost replay` — and only a dir that still has a
    # SKILL.md. The preview used to say "would re-record" either way.
    if plan.get("unrecorded_store") and lockfile.check().problem == "missing":
        for name in plan["unrecorded_store"]:
            if (skill_store_dir(name) / "SKILL.md").is_file():
                lines.append("would re-record %s, which the lock file has lost"
                             % name)
            else:
                lines.append("would leave %s unrecorded (no SKILL.md to record)"
                             % name)
    lines += [_adoption_preview(name) for name in plan.get("adoptable_store", [])]
    repairs = [plan_missing_store(name) for name in plan.get("missing_store", [])]
    for kind, name in plan.get("missing_materializations", []):
        repair = plan_missing_materialization(kind, name)
        # `sync_apply` reports no repair while a dir still refuses one of the
        # writes, and the caller names that dir instead; "would re-materialize"
        # here was a promise the run then did not make.
        if repair.action == "tap" and materialization_refused(kind, name):
            if repair.warning:
                lines.append(repair.warning)
            continue
        repairs.append(repair)
    for repair in repairs:
        if repair.warning:
            lines.append(repair.warning)
        lines.append(repair.preview)
    lines += backfill_row_hashes(dry=True)
    return lines


def _adoption_preview(name: str) -> str:
    """What :func:`adopt_unrecorded` will do with ``name``, worded ahead of it.

    It names an agent whose link something else is in the way of, since the
    run will leave that agent unlinked; saying "and link it" alone promised a
    link the run then refused.
    """
    _linked, _unseen, narrowed = _adoption_scope(name)
    scope = scoped_agents({"only_agents": narrowed}, agents.linking_agents())
    blocked = _in_the_way(name, scope)
    head = "would record %s, which boost did not install" % name
    if not blocked:
        return head + ", and link it"
    why = "; ".join("not into %s: %s is in the way" % (a, paths.tilde(p))
                    for a, p in blocked.items())
    if len(blocked) < len(scope):
        return "%s, and link it (%s)" % (head, why)
    return "%s, and leave it unlinked (%s)" % (head, why)


def recover_unrecorded(name: str) -> str | None:
    """Re-record one store dir the lock has lost; return how, or None.

    Called while the lock file is missing over a populated store, so writing a
    record cannot overwrite a newer or merely unreadable lock. The store copy
    is authoritative and is never replaced: re-installing would have been the
    obvious repair, and it silently discards any edits made to the store copy.

    A dir whose content is byte-identical to exactly one tapped source is
    recorded as installed from that tap, the record a fresh install would have
    written. Anything else — edited, or from a tap no longer tapped — is
    recorded as a local skill whose source is the store dir itself, so nothing
    is lost and nothing is left unrecorded: a dir left out would read as an
    orphan the moment this pass creates a lock, and the next sync would remove
    its links, the defect this function exists to close.

    A dir holding a file boost may not read is left unrecorded, and the line
    returned says which file (:func:`is_unrepaired`). So is a workflow's skill
    copy (:func:`workflow_copy_evidence`): it is the workflow's, not a skill.
    """
    if (wf := workflow_copy_evidence(name)) is not None:
        return _workflow_copy_refusal(name, wf)
    try:
        how = _record_unrecorded(name, "recover")
    except OSError as err:
        return _not_recorded(name, err)
    return None if how is None else "re-recorded %s %s" % (name, how)


def adopt_unrecorded(name: str) -> list[str]:
    """Record a skill nothing else claims and link it out; return the lines.

    The plain-`sync` answer for a skill put in ``~/.agents/skills`` by hand
    (:func:`classify_unrecorded`). It used to be an "orphaned store dir" that
    only ``sync --prune`` acted on, by deleting it — the user's own work, for
    the price of answering yes. Recorded as a local skill whose source is its
    store dir (:func:`_record_unrecorded`), then linked into the agents its
    scope takes in.

    Linked only where nothing is in the way. Whatever already holds the name
    in an agent's dir — a real dir, a file, or a symlink that does not lead
    into the store, such as one to the user's own checkout — is not boost's,
    so it is named and left exactly as it is. Any symlink used to count as
    boost's to replace, which re-pointed Claude Code from the user's checkout
    to the store copy while the line beside it said that copy was left alone.

    A skill the lock has recorded since the plan was made is not recorded
    again: something installed it in the meantime, and that record wins. One
    holding a file boost may not read is not recorded, and says so, so the
    rest of the sync still runs.
    """
    if lockfile.get_skill(name) is not None:
        return []
    if (wf := workflow_copy_evidence(name)) is not None:
        return [_workflow_copy_refusal(name, wf)]
    try:
        how = _record_unrecorded(name, "adopt")
    except OSError as err:
        return [_not_recorded(name, err)]
    entry = lockfile.get_skill(name)
    if how is None or entry is None:
        return []
    lines = ["recorded %s %s" % (name, how)]
    scope = scoped_agents(entry, agents.linking_agents())
    blocked = _in_the_way(name, scope)
    todo = [a for a in scope if a not in blocked]
    # Never `only=[]`: `link_agents` reads an empty list as every agent.
    if todo:
        before = set(entry.get("agents") or ())
        res = link_agents(name, only=todo)
        lockfile.set_skill(name, record_links(entry, res))
        lines += ["linked %s → %s" % (name, a) for a in res.linked if a not in before]
        lines += [_NOT_LINKED % (name, paths.tilde(c)) for c in res.conflicts]
    lines += [_NOT_LINKED % (name, paths.tilde(p)) for p in blocked.values()]
    return lines


#: An adoption's link that something not boost's is in the way of, worded
#: around a marker ``is_unrepaired`` recognises so it prints as a warning.
_NOT_LINKED_MARK = " was not linked: "
_NOT_LINKED = ("%s" + _NOT_LINKED_MARK + "%s is in the way and is not boost's "
               "to replace — to link boost's copy, move or delete it, then "
               "re-run `boost sync`")

#: A store dir sync could not record, worded the same way.
_NOT_RECORDED_MARK = " was not recorded: "


def _workflow_copy_refusal(name: str, wf: Path) -> str:
    """The line for a store dir left unrecorded as a workflow's skill copy."""
    return ("%s%sit is the skill copy of the workflow at %s — `boost install "
            "%s` re-records both" % (name, _NOT_RECORDED_MARK, paths.tilde(wf),
                                    name))


def _not_recorded(name: str, err: OSError) -> str:
    """The line for a store dir boost could not read all of."""
    return ("%s%s%s is unreadable — make it readable, then re-run `boost sync`"
            % (name, _NOT_RECORDED_MARK,
               paths.tilde(err.filename or skill_store_dir(name))))


def _in_the_way(name: str, scope: dict[str, Path]) -> dict[str, Path]:
    """``{agent: path}`` for each of ``scope``'s ``name`` links something
    other than boost's kind of link holds.

    Boost's kind is a symlink into the store, dangling or not, and boost may
    replace it. Anything else there belongs to whoever put it there.
    """
    found = {}
    for agent, adir in scope.items():
        link = adir / name
        if os.path.lexists(link) and not is_boost_link(link):
            found[agent] = link
    return found


def _adoption_scope(name: str) -> tuple[list[str], list[str], list[str] | None]:
    """``(linked, unseen, only_agents)`` for a store dir about to be recorded.

    What is on disk is the scope: a skill linked into fewer agents than link
    was narrowed, and recording no narrowing would have the next sync link it
    everywhere behind the user's back. Only boost's kind of link counts,
    a symlink into the store: a user's link to their own checkout says which
    copy that agent runs, not which agents this one is for. An agent whose
    link could not be looked at is not evidence of a narrowing, so it counts
    as in scope.
    """
    linking = agents.linking_agents()
    linked = [a for a, d in linking.items()
              if os.path.islink(d / name) and points_into_store(d / name)]  # noqa: FURB146
    unseen = unseen_agents(name)
    seen = {*linked, *unseen}
    narrowed = sorted(seen) if linked and seen != set(linking) else None
    return linked, unseen, narrowed


def _record_unrecorded(name: str, why: str) -> str | None:
    """Write a lock record for one unrecorded store dir; return how, or None.

    ``why`` is ``"recover"`` for a lock that lost the skill and ``"adopt"`` for
    one that never had it. A lost skill came from some tap, so a copy that is
    byte-identical to exactly one tapped source gets that tap's record, the
    one a fresh install would have written. A copy matching several gets
    the local record, and its line names the `boost install <tap>:` that
    picks one; one matching none is just a local skill.

    An adopted skill is always a local one. Matching it means hashing every
    same-named catalogue entry's source, and each hash materializes that entry
    in its clone — a `sparse-checkout add`, often a fetch — so plain `boost
    sync` widened 87 clones' cones over a skill named like a popular one, and
    left them widened. Offering `boost reinstall` there would be a trap
    besides: it overwrites the user's own skill.

    None when the dir no longer holds a ``SKILL.md``. An ``OSError`` — a file
    in it boost may not read — reaches the caller, which words it.
    """
    sdir = skill_store_dir(name)
    if not os.path.isfile(sdir / "SKILL.md"):  # noqa: FURB146
        return None
    have = util.sha256_dir(sdir)
    matches = [] if why == "adopt" else [
        e for e in catalog.find(name)
        if e.get("kind", "skill") == "skill" and _skill_source_sha(e) == have]
    linked, unseen, narrowed = _adoption_scope(name)
    now = util.now_iso()
    record: dict[str, object]
    if len(matches) == 1:
        cat = matches[0]
        tap = registry.get(cat["tap"])
        record = {"version": cat.get("version", "0.0.0"), "tap": cat["tap"],
                  "tap_url": tap.url,
                  "source_dir": cat.get("rel_dir", "."),
                  "commit": gitutil.head_commit(tap.path)}
        # Dated as install dates it: the store copy is that tap's files.
        if dated := source_updated_at(cat["tap"], cat.get("rel_dir", ".")):
            record["source_updated_at"] = dated
        how = "from %s" % cat["tap"]
    else:
        # The shape `import_local` writes for a skill with no tap behind it.
        record = {"version": "0.0.0", "tap": "local", "source_dir": str(sdir),
                  "commit": ""}
        # A reinstall would re-read the store dir itself, so the way back to
        # a tap's copy is naming the tap.
        how = ("as a local skill (its content matches more than one tapped "
               "source; `boost install <tap>:%s --force` replaces it with "
               "that tap's copy)" % name
               if why == "recover" and matches else "as a local skill")
    record.update({"sha256": have, "installed_at": now, "updated_at": now,
                   "pinned": False, "quarantined": False, "agents": linked,
                   "only_agents": narrowed, "tags": []})
    if unseen:
        # Recorded so uninstall refuses rather than strands a link it cannot see.
        record["refused_agents"] = unseen
    lockfile.set_skill(name, record)
    journal.log(why, name, how=record["tap"])
    return how


def only_copy(name: str, entry: dict) -> bool:
    """True when uninstalling skill ``name`` would delete the skill itself.

    A local skill whose recorded source is its own store dir — what `boost
    sync` writes for a skill put in ``~/.agents/skills`` by hand, or for one a
    lost lock had — or whose source is gone. Every other skill can be put
    back from a tap, a URL or a directory; this one has no copy anywhere else.
    The commands that uninstall as a side effect of something else (`replay
    rollback`, `profile use --prune`) leave it, and the ones that ask say so.
    """
    if entry.get("tap") != "local" or entry.get("source_url"):
        return False
    src = local_source_dir(entry)
    return src is None or os.path.realpath(src) == os.path.realpath(skill_store_dir(name))


def _still_a_copy(row: tuple, lock: dict, fresh: dict[str, list]) -> str | None:
    """Why ``row``'s store dir must stay, or None if it is still a copy.

    ``fresh`` is :func:`classify_unrecorded` asked again, just now.
    """
    name, _owner, other, how = row
    sdir, theirs = skill_store_dir(name), Path(other)
    if not os.path.lexists(sdir):
        return "it is already gone"
    if name in lock:
        return "boost has recorded it since"
    if foreign.holds_repo(sdir):
        return REPO_KEPT
    if not os.path.isfile(theirs / "SKILL.md"):  # noqa: FURB146
        return "the copy it duplicates, %s, is gone" % paths.tilde(other)
    if resolves_into_store(theirs):
        return ("%s now leads back into the store, so it is not a second copy"
                % paths.tilde(other))
    if foreign.leans_on_store(theirs):
        return ("%s links into the store file by file, so deleting this would "
                "empty it" % paths.tilde(other))
    if any(r[0] == name for r in fresh["unreadable_store"]):
        return "part of it cannot be read now, so what it holds cannot be told"
    if name in fresh["not_skill_store"]:
        return "it no longer holds a SKILL.md"
    if name in fresh["adoptable_store"]:
        return "it is now newer than %s" % paths.tilde(other)
    now = next((r for r in fresh["foreign_store"] if r[0] == name), None)
    if now is None:
        return "it is no longer a copy of %s" % paths.tilde(other)
    if now[2] != other:
        return "it is now a copy of %s instead" % paths.tilde(now[2])
    if how == foreign.IDENTICAL and now[3] != foreign.IDENTICAL:
        return "it has changed since it matched %s" % paths.tilde(other)
    # Last, so every reason above keeps its own words, and by inode: the same
    # dir under another spelling (a case alias on APFS, a firmlink) is
    # trivially "identical" to itself, and deleting "the copy" deleted the
    # only one.
    if foreign.same_dir(sdir, theirs):
        return "%s is this same dir under another name" % paths.tilde(other)
    return None


def remove_foreign_copies(rows: list) -> list[str | None]:
    """Delete the store dirs ``rows`` called other tools' copies.

    ``rows`` are :func:`classify_unrecorded`'s ``foreign_store``. Returns, row
    by row, None for a dir that is gone or why it was kept. What made each one
    a copy is decided again at the point of deletion, because a confirm can
    sit unanswered for as long as the user likes, and a wrong answer here
    deletes the last copy of something:

    * the lock still does not record it, and can still be read — an install
      in another shell would have made it boost's, and a lock that no longer
      parses cannot say either way;
    * the other copy is still a skill, and neither is nor leans on the store
      copy, where deleting this would delete it too. A vendor that dropped
      the skill on update leaves this as the only copy;
    * asked afresh, it is still a copy of that same skill: not a dir that has
      lost its ``SKILL.md``, and not one edited since into the newest copy —
      the mtime rule that made an agent's copy the owner holds no longer;
    * a copy the confirm called identical still is, so an edit made since is
      not lost under the word "identical". One that differed and has come to
      match is a copy all the same.
    """
    integ = lockfile.check()
    if not integ.ok and integ.problem != "missing":
        unreadable = ("the lock file cannot be read, so boost cannot tell "
                      "whether it is boost's — restore the lock with "
                      "`boost replay`")
        return [unreadable for _row in rows]
    lock = lockfile.installed()
    fresh = classify_unrecorded([r[0] for r in rows if r[0] not in lock
                                 and os.path.lexists(skill_store_dir(r[0]))])
    kept: list[str | None] = []
    for row in rows:
        why = _still_a_copy(row, lock, fresh)
        if why is None:
            # Per row, because the result is: one dir that refuses the delete
            # (a subdir made unreadable since the check) used to end the run
            # at exit 70 with no word on the rows already removed.
            try:
                util.remove_path(skill_store_dir(row[0]))
            except OSError as err:
                why = ("deleting it stopped at %s: %s — what is left is "
                       "still there" % (paths.tilde(err.filename or row[0]),
                                        err.strerror or err))
            else:
                journal.log("prune", row[0], copy_of=row[2])
        kept.append(why)
    return kept


#: Why ``--prune`` leaves a store dir holding a git repository.
REPO_KEPT = ("it is a git repository, and its history is in no copy — move "
             "or delete it yourself")


def is_repo_copy(row: tuple) -> bool:
    """True when a ``foreign_store`` row's store dir holds a git repository.

    Such a row is still named — the dir shares a name with another tool's
    skill — but ``--prune`` never offers it (:func:`foreign.holds_repo`).
    """
    return foreign.holds_repo(skill_store_dir(row[0]))


def remove_foreign_copy(row: tuple) -> str | None:
    """:func:`remove_foreign_copies` for one row."""
    return remove_foreign_copies([row])[0]


def drop_plugin_link(row: tuple) -> tuple[bool, str]:
    """Remove boost's Claude Code link to a skill a plugin ships the same files of.

    Returns ``(dropped, line)``. Only that link goes: the skill stays
    installed, linked into the other agents in its scope, and in the store
    for the agents that read it there. The lock needs no word that the link is
    not coming back, because :func:`link_agents` makes no Claude Code link
    while an enabled plugin ships the same files, so the scope is left as it
    was — and if the plugin is disabled, or changes the skill, the next `boost
    sync` links it again. Narrowing ``only_agents`` instead, as this once did,
    froze the skill out of every agent enabled later, and had no answer for a
    skill scoped to Claude Code alone: an empty scope means every agent.

    All of it is checked again here, because a confirm can sit unanswered for
    as long as the user likes: the skill is still installed, an enabled plugin
    still ships the same files — one that has updated may have changed the
    skill, and then they are two skills sharing a name — and the link is still
    boost's, one leading to the store copy. Claude Code's settings are never
    written, so disabling the plugin stays the user's other way out.
    """
    name, plugin_id, _theirs, how = row
    entry = lockfile.get_skill(name)
    linking = agents.linking_agents()
    if entry is None or foreign.CLAUDE not in linking:
        return False, "kept %s: it is no longer linked into Claude Code" % name
    hit = serving_plugin(name, entry.get("source_updated_at"))
    if hit is None:
        enabled = any(p.id == plugin_id for p in foreign.enabled_plugins())
        return False, ("kept %s → %s: %s" % (
            name, foreign.CLAUDE,
            "plugin %s is no longer enabled" % plugin_id if not enabled
            else "it no longer matches the copy in plugin %s" % plugin_id
            if how == foreign.IDENTICAL
            else "plugin %s's copy is no longer the newer one" % plugin_id))
    link = linking[foreign.CLAUDE] / name
    if not (os.path.islink(link) and _already_links(link, skill_store_dir(name))):
        return False, ("left %s alone: %s is no longer boost's link"
                       % (name, paths.tilde(link)))
    try:
        link.unlink()
    except OSError:
        return False, ("kept %s → %s: %s refuses the unlink"
                       % (name, foreign.CLAUDE, paths.tilde(link.parent)))
    entry["agents"] = [a for a in entry.get("agents") or () if a != foreign.CLAUDE]
    refused = [a for a in entry.get("refused_agents") or () if a != foreign.CLAUDE]
    if refused:
        entry["refused_agents"] = refused
    else:
        entry.pop("refused_agents", None)
    lockfile.set_skill(name, entry)
    journal.log("sync-prune", name, plugin=hit[0].id, how=hit[2])
    if hit[2] == foreign.IDENTICAL:
        return True, ("unlinked %s → %s (Claude Code loads the same files from "
                      "plugin %s)" % (name, foreign.CLAUDE, hit[0].id))
    return True, ("unlinked %s → %s (Claude Code loads plugin %s's newer copy, "
                  "by %s)" % (name, foreign.CLAUDE, hit[0].id,
                              foreign.date_words(foreign.split_how(hit[2])[1])))


def _names(items: list[str], limit: int = 5) -> str:
    return ", ".join(items[:limit]) + (", …" if len(items) > limit else "")


def foreign_store_lines(rows: list) -> list[str]:
    """One line per owner for `sync` and `heal`: whose copies these are.

    A dir holding a git repository gets its own line, since `--prune`, which
    the others name, leaves it (:func:`is_repo_copy`).
    """
    repos = [r for r in rows if is_repo_copy(r)]
    by_owner: dict[tuple[str, str], list] = {}
    for name, owner, other, how in rows:
        if (name, owner, other, how) in repos:
            continue
        by_owner.setdefault((owner, str(Path(other).parent)), []).append((name, how))
    lines = []
    for (owner, where), items in by_owner.items():
        differ = sum(1 for _n, how in items if how == foreign.DIFFERS)
        lines.append("%s %s from %s (%s), not boost's%s — remove with "
                     "`boost sync --prune`"
                     % (_names([n for n, _h in items], 8),
                        "copies a skill" if len(items) == 1 else "copy skills",
                        owner, paths.tilde(where),
                        "" if not differ else " (%s from the original)"
                        % ("changed" if len(items) == 1
                           else "%d of them changed" % differ)))
    lines += ["%s is named like a skill from %s (%s), but it is a git "
              "repository, so `boost sync --prune` leaves it — move or delete "
              "it yourself if it is a copy"
              % (name, owner, paths.tilde(other)) for name, owner, other, _h in repos]
    return lines


def unreadable_line(rows: list) -> str:
    """One line for store dirs holding something boost cannot read.

    ``rows`` are ``(skill, path)`` (``unreadable_store``). Each names the path
    that could not be read, which is what the user has to fix: the dir
    itself, or one file or subdir deep inside it.
    """
    if len(rows) == 1:
        name, where = rows[0]
        return ("%s: %s cannot be read, so boost cannot tell whose it is or "
                "record it — make it readable, then re-run `boost sync`"
                % (name, paths.tilde(where)))
    return ("%d store dirs cannot be recorded: boost cannot read what says whose "
            "they are (%s) — make those readable, then re-run `boost sync`"
            % (len(rows), _names(["%s: %s" % (n, paths.tilde(w)) for n, w in rows])))


def plugin_duplicate_lines(rows: list) -> list[str]:
    """Lines for the ``rows`` whose plugin's copy Claude Code should list
    (:func:`plugin_serves`): one per plugin for identical copies, then one per
    skill a plugin ships a newer copy of, naming how that is known."""
    by_plugin: dict[str, list[str]] = {}
    for name, plugin_id, _p, how in rows:
        if how == foreign.IDENTICAL:
            by_plugin.setdefault(plugin_id, []).append(name)
    return ["%s %s twice in Claude Code — plugin %s ships the same files; "
            "`boost sync --prune` drops boost's Claude Code link"
            % (_names(names, 8), "shows" if len(names) == 1 else "show", plugin_id)
            for plugin_id, names in by_plugin.items()] + plugin_newer_lines(rows)


def plugin_newer_lines(rows: list) -> list[str]:
    """A line for each of ``rows`` whose plugin ships a newer copy than boost's."""
    return ["%s shows twice in Claude Code — plugin %s ships a newer copy "
            "(by %s); `boost sync --prune` drops boost's older Claude Code link"
            % (name, plugin_id, foreign.date_words(foreign.split_how(how)[1]))
            for name, plugin_id, _p, how in rows
            if how != foreign.IDENTICAL and plugin_serves(how)]


def plugin_variant_lines(rows: list) -> list[str]:
    """A line for each of ``rows`` whose plugin ships a different skill that
    boost keeps its link beside: one boost's copy is newer than, or one whose
    dates decide nothing.

    Boost never writes Claude Code's settings, so for an older plugin copy it
    names the way the user can turn it off rather than doing it.
    """
    lines = []
    for name, plugin_id, _p, how in rows:
        verdict, source = foreign.split_how(how)
        if how == foreign.IDENTICAL or plugin_serves(how):
            continue
        if verdict == foreign.NEWER_IN_BOOST:
            lines.append("%s shows twice in Claude Code — boost's copy is newer "
                         "than plugin %s's (by %s), which still loads; boost "
                         "leaves Claude Code's plugin settings alone — to list "
                         "only boost's, disable %s with `/plugin` in Claude "
                         "Code, which turns off all of its skills"
                         % (name, plugin_id, foreign.date_words(source), plugin_id))
        else:
            lines.append("%s shows twice in Claude Code — plugin %s ships a "
                         "different skill by that name; both left as they are"
                         % (name, plugin_id))
    return lines


def older_copy_lines(rows: list) -> list[str]:
    """Lines naming the copies an adopted skill was newer than."""
    return ["%s: the copy in %s (%s) is older by file times — left alone"
            % (name, paths.tilde(other), owner) for name, owner, other in rows]


def misnamed_line(names: list[str]) -> str:
    """One line for store dirs whose name boost cannot record a skill under.

    Built from the store root, never :func:`skill_store_dir`, which refuses
    exactly these names.
    """
    if len(names) == 1:
        return ("%s: boost cannot record a skill by that name (only letters, "
                "digits, '.', '_' and '-') — left alone"
                % paths.tilde(paths.store_dir() / names[0]))
    return ("%d dirs in %s have names boost cannot record a skill by (%s) — "
            "left alone" % (len(names), paths.tilde(paths.store_dir()),
                            _names(names)))


def not_skill_line(names: list[str]) -> str:
    """One line for store dirs that hold no ``SKILL.md``."""
    if len(names) == 1:
        return ("%s holds no SKILL.md, so it is not a skill — left alone"
                % paths.tilde(skill_store_dir(names[0])))
    return ("%d dirs in %s hold no SKILL.md, so they are not skills (%s) — "
            "left alone" % (len(names), paths.tilde(paths.store_dir()),
                            _names(names)))


def sync_apply(plan: dict[str, list]) -> list[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    # A lock with no schema version, or an earlier one, still says what is
    # installed: it is recorded as the current schema here, so the command
    # doctor prescribes for it is the one that clears it.
    migrated = lockfile.migrate()
    if migrated:
        actions.append(migrated)
    # First, so every re-recorded skill is in the lock before anything else
    # runs; and only when the lock is *missing* — a corrupt or other-schema
    # lock is left for `boost replay`, never overwritten.
    if plan.get("unrecorded_store") and lockfile.check().problem == "missing":
        for name in plan["unrecorded_store"]:
            how = recover_unrecorded(name)
            actions.append(how or "left %s unrecorded (no SKILL.md to record)" % name)
    for name in plan.get("adoptable_store", []):
        actions.extend(adopt_unrecorded(name))
    for name, agent in plan["missing_links"]:
        res = link_agents(name, only=[agent])
        if agent in res.linked:
            actions.append("linked %s → %s" % (name, agent))
    for path in plan["stale_links"]:
        p = Path(path)
        if p.is_symlink():
            p.unlink()
            # `--diff` shows this same path tilde-contracted (`_tilde` in
            # commands/pkg.py); the raw absolute string here made the two
            # views of one path disagree in the exact case a user compares
            # them — planned vs. applied.
            actions.append("removed stale link %s" % paths.tilde(path))
    for name in plan["missing_store"]:
        # The branch is decided in one place, so `sync_preview` words the same
        # decision rather than re-deriving (and mis-deriving) it.
        repair = plan_missing_store(name)
        if repair.warning:
            actions.append(repair.warning)
        if repair.action == "declined":
            actions.append(repair.applied)
            continue
        try:  # noqa: FURB107 - per-item resilience in a loop (see PERF203)
            if repair.src is not None:
                install_from_path(repair.src, name=name, force=True)
                actions.append(repair.applied)
                continue
            if repair.cat_entry is not None:
                install(repair.cat_entry, force=True)
                actions.append(repair.applied)
                continue
        except BoostError:
            # The one place the preview can be wrong, and deliberately: a
            # source readable a moment ago is gone now, so the run falls
            # through to the drop.
            pass
        lockfile.remove_skill(name)
        actions.append(_DROPPED % name)
    for kind, name in plan.get("missing_materializations", []):
        mat = plan_missing_materialization(kind, name)
        if mat.warning:
            actions.append(mat.warning)
        if mat.action == "declined":
            actions.append(mat.applied)
            continue
        if mat.cat_entry is None:
            actions.append(_GONE % (kind, name))
            continue
        try:  # noqa: FURB107 - per-item resilience in a loop (see PERF203)
            res = install(mat.cat_entry, force=True, scope=mat.scope,
                          base=mat.base)
        except BoostError as err:
            # The source is there; the install said why it stopped (a store
            # that refuses the lock, say). Reporting `_GONE` here sent the
            # user to `boost update` for a problem in ~/.agents/skills.
            why = err.message + (" — %s" % err.hint if err.hint else "")
            actions.append("%s %s%s%s"
                           % (kind, name, _NOT_REMATERIALIZED, why))
            continue
        # A directory still refusing the write is not a repair, so it is not
        # reported as one; the caller names the dir itself
        # (`unwritable_agent_dirs`, `blocked_agent_dirs`), with its remedy.
        if not res.unwritable and not res.blocked and not res.conflicts:
            actions.append(mat.applied)
    # After the re-materializations above, which record their own hashes.
    actions.extend(backfill_row_hashes())
    if actions:
        journal.log("sync", "%d fixes" % len(actions))
    return actions
