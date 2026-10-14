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
* whether a plugin is enabled — managed ``enabledPlugins`` first, then the
  user's, then ``defaultEnabled``, which the marketplace entry sets over
  ``plugin.json`` and which defaults to true:
  https://code.claude.com/docs/en/settings-reference#enabledplugins,
  https://code.claude.com/docs/en/plugins/manifest-reference#defaultenabled,
  and for where managed files live and how they merge,
  https://code.claude.com/docs/en/managed-settings#delivery-mechanisms
* which skills a plugin loads, and how a marketplace entry combines with
  ``plugin.json``:
  https://code.claude.com/docs/en/plugins/manifest-reference#how-entry-fields-combine-with-plugin-json
  and #standard-layout on the same page
* both copies load, the plugin's namespaced, each under its frontmatter
  ``name``: https://code.claude.com/docs/en/skills#resolve-skills-that-share-a-name

The format of ``installed_plugins.json`` is not documented beyond those three
fields, so everything here reads it defensively: a file that is missing,
corrupt, unreadable or shaped differently yields no plugins rather than an
error, because ``boost doctor`` calls this and must report, not raise.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ..errors import BoostError
from . import agents, frontmatter, jsonstate, paths, util

VENDOR = "vendor"
PLUGIN = "plugin"
AGENT = "agent"

#: The agent that loads Claude Code plugins, as boost's agent table names it.
CLAUDE = "claude-code"

#: How two copies of a skill compare, as plans record it and messages word it.
IDENTICAL = "identical"
DIFFERS = "differs"

#: The fields a marketplace entry may add to a plugin. Beside a
#: ``plugin.json``, an entry that sets ``strict: false`` and declares any of
#: them is a conflict, and the plugin does not load at all.
COMPONENTS = ("commands", "agents", "skills", "hooks", "outputStyles", "themes")


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
    """``path`` as a JSON object; ``{}`` when it is missing or unusable.

    OSError too, which :func:`jsonstate.read_object` lets out: it opens with
    ``Path.exists``, and under a ``~/.claude`` or ``~/.claude/plugins`` with
    no search bit that raises PermissionError on Python 3.12 and 3.13 — which
    took ``boost sync``, ``heal`` and ``doctor`` down at exit 70 on a machine
    with no plugin enabled at all.
    """
    try:
        data, _err = jsonstate.read_object(path)
    except OSError:
        return {}
    return data or {}


def _manifest(root: Path) -> tuple[bool, dict | None]:
    """``(present, data)`` for a plugin's own ``.claude-plugin/plugin.json``.

    ``data`` is None when the file is there and does not read as a JSON
    object: Claude Code cannot load that plugin, so it ships nothing.
    """
    path = root / ".claude-plugin" / "plugin.json"
    if not os.path.isfile(path):  # noqa: FURB146 - see _is_skill
        return False, {}
    try:
        data, err = jsonstate.read_object(path)
    except OSError:
        return True, None
    return True, data if err is None else None


def managed_settings_dir() -> Path:
    """Where Claude Code reads managed settings files on this platform."""
    if sys.platform == "darwin":
        return Path("/Library/Application Support/ClaudeCode")
    if sys.platform == "win32":
        return Path(r"C:\Program Files\ClaudeCode")
    return Path("/etc/claude-code")


def managed_plugin_states() -> dict[str, bool]:
    """``{plugin id: enabled}`` from the managed ``enabledPlugins``.

    ``managed-settings.json`` first, then each ``*.json`` in
    ``managed-settings.d`` in alphabetical order, hidden files skipped, as the
    docs order them. That a later file's answer replaces an earlier one id by
    id is this module's reading: the docs give the file order, not how one
    object-valued key merges. A value that is not a boolean is no answer, as
    Claude Code drops an invalid managed entry and keeps the rest. Policy
    delivered by a server or MDM outranks these files and cannot be read from
    here, so this is the most a local reader can know.
    """
    root = managed_settings_dir()
    drop_in = root / "managed-settings.d"
    try:
        extra = sorted(n for n in os.listdir(drop_in)
                       if n.endswith(".json") and not n.startswith("."))
    except OSError:
        extra = []
    states: dict[str, bool] = {}
    for f in (root / "managed-settings.json", *(drop_in / n for n in extra)):
        value = _object(f).get("enabledPlugins")
        if isinstance(value, dict):
            states.update((k, v) for k, v in value.items() if isinstance(v, bool))
    return states


def _user_install(pid: str, rows) -> Plugin | None:
    """``pid``'s user-scope install among its ``installed_plugins.json`` rows.

    An ``installPath`` must be absolute. Claude Code writes absolute ones, and
    a relative one would be read against wherever boost was started, so a
    tap checkout in the working directory could pass for a plugin.
    """
    for row in rows if isinstance(rows, list) else ():
        where = row.get("installPath") if isinstance(row, dict) else None
        if (isinstance(where, str) and os.path.isabs(where)
                and row.get("scope") == "user" and os.path.isdir(where)):
            return Plugin(pid, Path(where))
    return None


def _enabled(plugin: Plugin, states: list[dict]) -> bool:
    """Whether Claude Code runs ``plugin``: the first boolean answer wins.

    ``states`` holds the managed and then the user ``enabledPlugins``; a
    managed ``true`` cannot be turned off by the user and a managed ``false``
    blocks the plugin everywhere. A plugin no settings name falls back to
    ``defaultEnabled``, the marketplace entry's over ``plugin.json``'s, and
    that defaults to true.
    """
    for state in states:
        value = state.get(plugin.id)
        if isinstance(value, bool):
            return value
    _present, manifest = _manifest(plugin.path)
    for source in (_marketplace_entry(plugin) or {}, manifest or {}):
        value = source.get("defaultEnabled")
        if isinstance(value, bool):
            return value
    return True


def enabled_plugins() -> list[Plugin]:
    """User-scope plugins that are both installed and enabled, by id.

    User scope only: boost links a skill into ``~/.claude/skills``, which every
    project sees, and a plugin enabled in one project's settings duplicates it
    only there. Enabled is decided by :func:`_enabled`, so a plugin installed
    with no ``enabledPlugins`` row counts — it starts enabled by default.
    """
    installed = _object(plugins_root() / "installed_plugins.json").get("plugins")
    if not isinstance(installed, dict):
        return []
    user = _object(claude_home() / "settings.json").get("enabledPlugins")
    states = [managed_plugin_states(), user if isinstance(user, dict) else {}]
    found = []
    for pid in sorted(installed):
        plugin = _user_install(pid, installed[pid])
        if plugin is not None and _enabled(plugin, states):
            found.append(plugin)
    return found


def _marketplace_entry(plugin: Plugin) -> dict | None:
    """The plugin's entry in its marketplace's ``marketplace.json``, or None."""
    market = plugin.id.split("@", 1)[1] if "@" in plugin.id else ""
    if not market:
        return None
    where = _object(plugins_root() / "known_marketplaces.json").get(market)
    loc = where.get("installLocation") if isinstance(where, dict) else None
    root = (Path(loc) if isinstance(loc, str) and os.path.isabs(loc)
            else plugins_root() / "marketplaces" / market)
    entries = _object(root / ".claude-plugin" / "marketplace.json").get("plugins")
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict) and entry.get("name") == plugin.name:
            return entry
    return None


def _source_is_root(entry: dict) -> bool:
    """True when a marketplace entry's ``source`` is the marketplace root."""
    src = entry.get("source")
    return isinstance(src, str) and (
        src == "." or (src.startswith("./") and os.path.normpath(src) == "."))


def _listed(value) -> list[str] | None:
    """A manifest's ``skills`` value as a list of paths; None when it has none."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return None


def _resolve_listed(root: Path, rels: list[str]) -> list[Path]:
    """The skill dirs that manifest ``skills`` paths name, in order.

    A path names one skill (a dir holding ``SKILL.md``) or a dir of them. One
    that leaves the plugin is ignored: Claude Code does not load it, and
    following it would read a stranger's directory.
    """
    base = os.path.realpath(root)
    found: list[Path] = []
    for rel in rels:
        p = root / rel
        try:
            inside = os.path.commonpath([os.path.realpath(p), base]) == base
        except ValueError:
            inside = False
        if not inside:
            continue
        if _is_skill(p):
            found.append(p)
        else:
            found.extend(d for _n, d in _skills_in(p))
    return found


def skill_name(path: Path, fallback: str) -> str:
    """The ``name`` a skill dir's ``SKILL.md`` declares, else ``fallback``.

    What Claude Code lists a skill under. A file that cannot be read, or
    whose frontmatter fence never closes, declares nothing.
    """
    try:
        text = (path / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return fallback
    if frontmatter.unclosed(text):
        return fallback
    name = frontmatter.parse(text)[0].get("name")
    return name.strip() if isinstance(name, str) and name.strip() else fallback


def plugin_skills(plugin: Plugin) -> dict[str, Path]:
    """``{skill name: dir}`` for the skills Claude Code loads from ``plugin``.

    The documented rules, because a false positive here hides a skill: boost
    stops linking its own copy into Claude Code, and ``boost sync --prune``
    drops the link it has. A false negative costs a duplicate listing, so
    where a rule is unclear this errs towards fewer:

    * the default ``skills/`` scan, plus the paths every ``skills`` key names
      — ``plugin.json``'s, and the marketplace entry's, which Claude Code
      appends to a ``plugin.json`` or reads as the manifest when there is none;
    * except that an entry whose ``source`` is the marketplace root and which
      lists ``skills`` loads only those, with no default scan. That is the
      layout that prompted this: each plugin's source is the repo root, so
      each cached copy holds all 29 of the repo's skills and loads the 8 or 14
      its entry lists;
    * a ``plugin.json`` that does not parse, or one beside an entry that sets
      ``strict: false`` and declares a component, loads nothing;
    * a plugin with a root ``SKILL.md``, no ``skills/`` and no ``skills`` key
      loads as one skill.

    Each skill is keyed by the name Claude Code gives it: the frontmatter
    ``name`` without a leading ``<plugin>:``, else the dir name, else for a
    skill at the plugin root the plugin's own name. The first dir to claim a
    name keeps it.
    """
    root = plugin.path
    present, manifest = _manifest(root)
    entry = _marketplace_entry(plugin) or {}
    if manifest is None or (present and entry.get("strict") is False
                            and any(k in entry for k in COMPONENTS)):
        return {}
    own = _listed(manifest.get("skills"))
    added = _listed(entry.get("skills"))
    if added is not None and _source_is_root(entry):
        dirs = _resolve_listed(root, [*added, *(own or [])])
    else:
        dirs = [d for _n, d in _skills_in(root / "skills")]
        dirs += _resolve_listed(root, [*(own or []), *(added or [])])
        if (own is added is None and _is_skill(root)
                and not os.path.isdir(root / "skills")):  # noqa: FURB146
            dirs = [root]
    declared = manifest.get("name")
    namespace = declared if isinstance(declared, str) else plugin.name
    base = os.path.realpath(root)
    found: dict[str, Path] = {}
    for d in dirs:
        fallback = (namespace if os.path.realpath(d) == base
                    else Path(os.path.normpath(d)).name)
        name = skill_name(d, fallback)
        found.setdefault(name.removeprefix(namespace + ":"), d)
    return found


def plugin_index() -> dict[str, tuple[Plugin, Path]]:
    """``{skill name: (plugin, dir)}`` over every enabled plugin, first by id."""
    index: dict[str, tuple[Plugin, Path]] = {}
    for plugin in enabled_plugins():
        for name, path in plugin_skills(plugin).items():
            index.setdefault(name, (plugin, path))
    return index


def leans_on_store(path: Path) -> bool:
    """True when anything inside ``path`` is a symlink that leads into the store.

    A real dir of per-file links into a store copy — what GNU Stow or a
    hand-made link farm leaves — hashes the same as that copy, because
    :func:`util.sha256_dir` follows links. It is the store copy seen from
    elsewhere, not a second copy, and deleting "the copy" would leave it a dir
    of dangling links.
    """
    from . import store  # lazily, as in inventory
    for top, dirs, files in os.walk(path):
        for entry in (*dirs, *files):
            p = Path(top) / entry
            if os.path.islink(p) and store.resolves_into_store(p):  # noqa: FURB146
                return True
    return False


def inventory(names: Iterable[str] | None = None) -> dict[str, list[Counterpart]]:
    """Every other tool's skill on this machine, keyed by name, owners first.

    ``names`` narrows it to those names, so a caller asking about three store
    dirs does not walk every skill on the machine. Within a name the order is
    :data:`VENDOR`, :data:`PLUGIN`, :data:`AGENT`, which is the order a caller
    should trust them in. An entry that resolves into the canonical store is
    no counterpart, whoever's dir it sits in: in an agent's dir it is boost's
    own link, and anywhere else it is the store copy under a second name, not
    a second copy — deleting "the copy" would delete it. The same goes for a
    real dir that links into the store file by file (:func:`leans_on_store`),
    and for a second path to a directory already listed. Every configured
    agent is walked, enabled or not, because turning an agent off in boost
    does not take its skills off the disk.
    """
    from . import store  # lazily: store imports this module at load time
    wanted = None if names is None else set(names)
    found: dict[str, list[Counterpart]] = {}
    seen: set[tuple] = set()

    def add(c: Counterpart) -> None:
        if wanted is not None and c.name not in wanted:
            return
        key = _identity(c.path)
        if (key in seen or store.resolves_into_store(c.path)
                or leans_on_store(c.path)):
            return
        seen.add(key)
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
    identical, and that includes a dir the hash cannot list: its walk skips
    one without a word, so a store copy whose extra files sat in an
    unreadable subdir hashed the same as the copy it was compared with
    (:func:`unreadable` asks first).
    """
    if unreadable(a) is not None or unreadable(b) is not None:
        return False
    try:
        return util.sha256_dir(a) == util.sha256_dir(b)
    except OSError:
        return False


def same_dir(a: Path, b: Path) -> bool:
    """True when two paths are one directory, by device and inode.

    Strings cannot answer it: on a case-insensitive volume — APFS, the macOS
    default — ``~/.Agents/skills/x`` is ``~/.agents/skills/x``, and so is
    ``/System/Volumes/Data/Users/...`` through its firmlink, while
    ``realpath`` leaves all three spelled as they were. A path that cannot be
    looked at is not the same as anything.
    """
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _identity(path: Path) -> tuple:
    """A key that is equal for two paths to one directory (:func:`same_dir`)."""
    try:
        st = path.stat()
    except OSError:
        return ("path", os.path.realpath(path))
    return ("inode", st.st_dev, st.st_ino)


def holds_repo(path: Path) -> bool:
    """True when a skill dir holds git metadata — a ``.git`` dir or file — at any depth.

    :func:`util.sha256_dir` skips ``.git``, so a store dir that is the user's
    clone hashes the same as a plain copy of its working tree, and was called
    an identical copy that ``--prune`` could delete with its history,
    branches and stash. Nothing a copy holds stands in for those, so a dir
    holding one is never a copy (:func:`store.classify_unrecorded`).
    """
    return any(".git" in dirs or ".git" in files
               for _top, dirs, files in os.walk(path))


def unreadable(path: Path) -> Path | None:
    """The first entry in a skill dir boost cannot read, or None.

    A dir it cannot list, or a regular file it cannot open: what
    :func:`util.sha256_dir` would either skip in silence or fail on. Entries
    the hash ignores (``util.IGNORED``) are not looked at, and nothing is
    read — a file is opened and closed, non-blocking, so a FIFO cannot hang
    the walk. A link is followed the way the hash follows it: to a file, but
    not into a directory.
    """
    stack = [str(path)]
    while stack:
        top = stack.pop()
        try:
            with os.scandir(top) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError:
            return Path(top)
        for e in entries:
            if e.name in util.IGNORED:
                continue
            try:
                if e.is_dir(follow_symlinks=False):
                    stack.append(e.path)
                elif e.is_file():
                    os.close(os.open(e.path, os.O_RDONLY | os.O_NONBLOCK))
            except OSError:
                return Path(e.path)
    return None


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
