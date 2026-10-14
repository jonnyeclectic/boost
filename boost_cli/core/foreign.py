# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Skills other tools keep on this machine, and whose they are.

boost owns what its lock file records. A store dir the lock does not record
still belongs to someone, and ``boost sync`` used to call every one of them an
"orphan" and offer to delete it. On the machine this was written against, 28
such dirs were three different things: one skill the user had written by hand,
26 of Cursor's built-in skills ported for Codex (16 rewritten "Cursor" ->
"Codex", 10 byte-identical), and one empty dir. Deleting the first loses work;
adopting the second would link a Codex port of Cursor's ``automate`` into
Claude Code. So the question is asked first — who else has a skill by this
name, and where — and this module answers it. It only reads.

Three sources, and the order is the ownership test:

* **Vendor built-ins** (:data:`VENDOR`): a dir an agent manages itself and
  rewrites on update. ``<cursor dir>/../skills-cursor`` holds Cursor's — seen
  beside Cursor's own ``.sync-manifest.json``, which records a
  ``lastSyncedAt`` per skill. ``<codex dir>/.system`` holds the skills Codex
  bundles (``skill-creator``, ``skill-installer``). A store dir named like one
  is a copy or a port of the vendor's skill, whatever its bytes or mtime say.
* **Enabled Claude Code plugins** (:data:`PLUGIN`): a plugin's skill loads in
  Claude Code as ``/<plugin>:<skill>`` *beside* a personal skill of the same
  name, so boost linking its own copy shows the skill twice.
* **Agent skills dirs** (:data:`AGENT`): a real directory the user keeps in an
  agent's own dir, such as ``~/.codex/skills/pr-me``. Unlike the two above it
  is the user's, so which copy is current is a question for the caller.

The plugin facts come from the Claude Code docs, not from reading its bundle:

* where installs are recorded and what a record carries (``scope``,
  ``installPath``, ``version``):
  https://code.claude.com/docs/en/plugins/loading#find-plugins-on-disk
* enabled state, ``"<name>@<marketplace>": true`` under ``enabledPlugins``:
  https://code.claude.com/docs/en/plugins/loading#find-where-a-plugin-is-enabled
* which skills a plugin loads: with no ``.claude-plugin/plugin.json`` "the
  entry is the manifest", and an entry listing ``skills`` loads only those,
  without scanning the default ``skills/`` dir —
  https://code.claude.com/docs/en/plugins/manifest-reference#how-entry-fields-combine-with-plugin-json
  — while a ``plugin.json`` ``skills`` key adds to that scan rather than
  replacing it: https://code.claude.com/docs/en/plugins/components#skills
* both copies load, the plugin's namespaced:
  https://code.claude.com/docs/en/skills#resolve-skills-that-share-a-name

The format of ``installed_plugins.json`` is not documented beyond those three
fields, so everything here reads it defensively: a file that is missing,
corrupt or shaped differently yields no plugins rather than an error, because
``boost doctor`` calls this and must report, not raise.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ..errors import BoostError
from . import agents, jsonstate, paths, util

VENDOR = "vendor"
PLUGIN = "plugin"
AGENT = "agent"

#: The agent that loads Claude Code plugins, as boost's agent table names it.
CLAUDE = "claude-code"

#: How two copies of a skill compare, as plans record it and messages word it.
IDENTICAL = "identical"
DIFFERS = "differs"


@dataclass(frozen=True)
class Counterpart:
    """Another tool's skill that shares a name with a store dir."""
    name: str
    kind: str       #: VENDOR, PLUGIN or AGENT
    owner: str      #: whose it is, worded to follow "from": "Cursor's built-ins"
    path: Path      #: the other copy's skill directory


@dataclass(frozen=True)
class Plugin:
    """An enabled, installed Claude Code plugin."""
    id: str         #: ``<plugin>@<marketplace>``
    path: Path      #: its ``installPath``

    @property
    def name(self) -> str:
        """The plugin's own name: what Claude Code namespaces its skills under."""
        return self.id.split("@", 1)[0]


def _is_skill(path: Path) -> bool:
    # ``os.path``: ``Path.is_file`` raises under a dir with no search bit on
    # Python 3.12 and 3.13, and doctor calls this.
    return os.path.isfile(os.path.join(path, "SKILL.md"))


def _skills_in(root: Path) -> list[tuple[str, Path]]:
    """``(name, dir)`` for each skill directly inside ``root``, by name.

    Dot entries are skipped, so ``~/.codex/skills/.system`` is read as the
    vendor dir it is rather than as a skill called ``.system``. An unreadable
    or missing ``root`` holds nothing.
    """
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return []
    return [(n, root / n) for n in names
            if not n.startswith(".") and _is_skill(root / n)]


def vendor_dirs() -> list[tuple[str, Path]]:
    """``(owner, dir)`` for each agent's own built-in skills dir that exists.

    Derived from the agent table, so a relocated agent dir moves its vendor
    dir with it: Cursor's built-ins sit beside its skills dir, Codex's inside
    it. An agent with no row has no vendor dir.
    """
    known = agents.known_agents()
    found = []
    if "cursor" in known:
        found.append(("Cursor's built-ins",
                      known["cursor"]["dir"].parent / "skills-cursor"))
    if "codex" in known:
        found.append(("Codex's built-ins", known["codex"]["dir"] / ".system"))
    return [(owner, d) for owner, d in found if os.path.isdir(d)]


def claude_home() -> Path:
    """The Claude Code configuration dir that reads boost's links.

    The parent of the ``claude-code`` agent's ``skills`` dir — not
    ``$CLAUDE_CONFIG_DIR`` from boost's own environment, which names the
    profile that launched this shell. On the machine this was written on, a
    sync run from a session with ``CLAUDE_CONFIG_DIR=~/.claude-personal``
    would have read that profile's plugins and compared them with links in
    ``~/.claude/skills``, beside which only ``~/.claude``'s plugins load.
    Without a usable agent row it falls back to that variable, then
    ``~/.claude``; a relative ``CLAUDE_CONFIG_DIR`` is ignored, as Claude Code
    itself refuses one (see :func:`mcphost.config_home`).
    """
    try:
        spec = agents.known_agents().get(CLAUDE)
    except BoostError:
        spec = None
    if spec and Path(spec["dir"]).name == "skills":
        return Path(spec["dir"]).parent
    env = os.environ.get("CLAUDE_CONFIG_DIR", "")
    return Path(env) if env and Path(env).is_absolute() else paths.home() / ".claude"


def plugins_root() -> Path:
    """Where Claude Code keeps plugins: ``$CLAUDE_CODE_PLUGIN_CACHE_DIR``, else
    ``<claude home>/plugins``."""
    env = os.environ.get("CLAUDE_CODE_PLUGIN_CACHE_DIR", "")
    return Path(env) if env and Path(env).is_absolute() else claude_home() / "plugins"


def _object(path: Path) -> dict:
    data, _err = jsonstate.read_object(path)
    return data or {}


def enabled_plugins() -> list[Plugin]:
    """User-scope plugins that are both enabled and installed, by id.

    User scope only: boost links a skill into ``~/.claude/skills``, which every
    project sees, and a plugin enabled in one project's settings duplicates it
    only there.
    """
    enabled = _object(claude_home() / "settings.json").get("enabledPlugins")
    installed = _object(plugins_root() / "installed_plugins.json").get("plugins")
    if not isinstance(enabled, dict) or not isinstance(installed, dict):
        return []
    found = []
    for pid in sorted(enabled):
        rows = installed.get(pid)
        if enabled[pid] is not True or not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            where = row.get("installPath")
            if (row.get("scope") == "user" and isinstance(where, str)
                    and os.path.isdir(where)):
                found.append(Plugin(pid, Path(where)))
                break
    return found


def _marketplace_entry(plugin: Plugin) -> dict | None:
    """The plugin's entry in its marketplace's ``marketplace.json``, or None."""
    market = plugin.id.split("@", 1)[1] if "@" in plugin.id else ""
    if not market:
        return None
    where = _object(plugins_root() / "known_marketplaces.json").get(market)
    loc = where.get("installLocation") if isinstance(where, dict) else None
    root = Path(loc) if isinstance(loc, str) else plugins_root() / "marketplaces" / market
    entries = _object(root / ".claude-plugin" / "marketplace.json").get("plugins")
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict) and entry.get("name") == plugin.name:
            return entry
    return None


def _listed(value) -> list[str] | None:
    """A manifest's ``skills`` value as a list of paths; None when it has none."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return None


def _resolve_listed(root: Path, rels: list[str]) -> list[tuple[str, Path]]:
    """Skills named by manifest paths, which may name a skill or a dir of them.

    A path that leaves the plugin is ignored: it is not where Claude Code
    loads from, and following it would read a stranger's directory.
    """
    base = os.path.realpath(root)
    found = []
    for rel in rels:
        p = root / rel
        try:
            inside = os.path.commonpath([os.path.realpath(p), base]) == base
        except ValueError:
            inside = False
        if not inside:
            continue
        if _is_skill(p):
            found.append((Path(os.path.normpath(p)).name, p))
        else:
            found.extend(_skills_in(p))
    return found


def plugin_skills(plugin: Plugin) -> dict[str, Path]:
    """``{skill name: dir}`` for the skills Claude Code loads from ``plugin``.

    Exactly the documented rule, because a false positive here makes ``boost
    sync --prune`` drop a link to a skill the plugin does not in fact load:

    * a ``.claude-plugin/plugin.json`` — the default ``skills/`` scan, plus any
      paths its ``skills`` key names;
    * none — the marketplace entry is the manifest. A ``skills`` list loads
      only those paths; no ``skills`` key leaves the default scan.

    The marketplace in use here is the reason for the second branch: every
    plugin's ``source`` is the repo root, so each cached copy holds all 29 of
    the repo's skills while loading the 8 or 14 its entry lists.
    """
    root = plugin.path
    default = _skills_in(root / "skills")
    manifest = root / ".claude-plugin" / "plugin.json"
    if os.path.isfile(manifest):  # noqa: FURB146 - see _is_skill
        extra = _listed(_object(manifest).get("skills")) or []
        found = default + _resolve_listed(root, extra)
    else:
        listed = _listed((_marketplace_entry(plugin) or {}).get("skills"))
        found = default if listed is None else _resolve_listed(root, listed)
    return dict(found)


def plugin_index() -> dict[str, tuple[Plugin, Path]]:
    """``{skill name: (plugin, dir)}`` over every enabled plugin, first by id."""
    index: dict[str, tuple[Plugin, Path]] = {}
    for plugin in enabled_plugins():
        for name, path in plugin_skills(plugin).items():
            index.setdefault(name, (plugin, path))
    return index


def inventory() -> dict[str, list[Counterpart]]:
    """Every other tool's skill on this machine, keyed by name, owners first.

    Within a name the order is :data:`VENDOR`, :data:`PLUGIN`, :data:`AGENT`,
    which is the order a caller should trust them in. An entry that resolves
    into the canonical store is no counterpart, whoever's dir it sits in: in an
    agent's dir it is boost's own link, and anywhere else it is the store copy
    under a second name, not a second copy — deleting "the copy" would delete
    it. Nor is a second path to a directory already listed. Every configured
    agent is walked, enabled or not, because turning an agent off in boost
    does not take its skills off the disk.
    """
    from . import store  # lazily: store imports this module at load time
    found: dict[str, list[Counterpart]] = {}
    seen: set[str] = set()

    def add(c: Counterpart) -> None:
        real = os.path.realpath(c.path)
        if real not in seen and not store.resolves_into_store(c.path):
            seen.add(real)
            found.setdefault(c.name, []).append(c)

    store_root = os.path.realpath(paths.store_dir())
    for owner, d in vendor_dirs():
        for name, p in _skills_in(d):
            add(Counterpart(name, VENDOR, owner, p))
    for name, (plugin, p) in sorted(plugin_index().items()):
        add(Counterpart(name, PLUGIN, "Claude Code plugin %s" % plugin.id, p))
    for agent, spec in agents.known_agents().items():
        if os.path.realpath(spec["dir"]) == store_root:
            continue
        for name, p in _skills_in(spec["dir"]):
            add(Counterpart(name, AGENT, agents.display_name(agent), p))
    return found


def same_content(a: Path, b: Path) -> bool:
    """True when two skill dirs hold the same files, byte for byte.

    :func:`util.sha256_dir` on both sides — the hash the lock file records —
    so "identical" means what ``boost verify`` means by it. Unreadable is not
    identical.
    """
    try:
        return util.sha256_dir(a) == util.sha256_dir(b)
    except OSError:
        return False


def compare(a: Path, b: Path) -> str:
    """:data:`IDENTICAL` or :data:`DIFFERS`, by :func:`same_content`."""
    return IDENTICAL if same_content(a, b) else DIFFERS


def newest_mtime(path: Path) -> float:
    """The latest modification time of any file in a skill dir, 0.0 if none.

    Files, not the directory: a dir's own mtime moves when an entry is added
    or removed, not when ``SKILL.md`` is edited, and an edit is what decides
    which of two copies the user is working on. Symlinks inside are not
    followed (``os.walk``'s default), and ``util.IGNORED`` noise such as
    ``.DS_Store`` does not count.
    """
    best = 0.0
    for top, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in util.IGNORED]
        for f in files:
            if f in util.IGNORED:
                continue
            try:
                best = max(best, os.lstat(os.path.join(top, f)).st_mtime)
            except OSError:
                continue
    return best
