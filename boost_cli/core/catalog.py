"""Skill catalogs: scan tap repos for skill/rule/workflow files -> JSON caches.

A catalog entry (plain dict) has:
  name, description, version, tap, curated,
  kind      -- "skill" | "rule" | "workflow" (defaults to "skill")
  rel_dir   -- item directory relative to the tap repo root
  skill_md  -- path of the defining file relative to the repo root
               (SKILL.md for skills, the .mdc/.cursorrules/.md for others)
  meta      -- full parsed frontmatter

Beyond `SKILL.md` skills, boost also indexes two lighter-weight item kinds
that ship in the same GitHub registries:
  * rules     -- Cursor `.mdc` / `.cursorrules` and Windsurf `.windsurfrules`
  * workflows -- Claude Code slash commands / subagents (Markdown + YAML),
                 recognised by living under a commands/agents/workflows dir
                 or by carrying a subagent-style frontmatter signature.
"""
from __future__ import annotations

import hashlib
import json
import operator
import os
import re
from pathlib import Path

from ..errors import BoostError
from . import frontmatter, gitutil, paths, registry, util

# Bumped whenever a scan starts recording something the previous scan did not,
# so 460 caches on a real machine invalidate on read instead of needing a
# re-tap. `catalogbundle.BUNDLE_FORMAT` and `rag.INDEX_VERSION` self-version for
# the same reason; the tap cache was the one derived artifact that did not, and
# without it there was no way to ship a new entry field at all.
#   1 -- entries carry `content` (see `_content_digest`)
CACHE_FORMAT = 1

KIND_SKILL = "skill"
KIND_RULE = "rule"
KIND_WORKFLOW = "workflow"

# Rule files: Cursor MDC + the legacy single-file rule dotfiles.
RULE_SUFFIXES = {".mdc"}
RULE_FILENAMES = {".cursorrules", ".windsurfrules", ".clinerules"}
# Directory names that mark a Markdown file as a command/agent workflow.
WORKFLOW_DIRS = {"commands", "agents", "subagents", "workflows"}
# Frontmatter keys that betray a Claude Code subagent / slash command even
# when the file sits at a repo root rather than under a workflow dir.
WORKFLOW_META_KEYS = {"tools", "model", "argument-hint", "allowed-tools"}
# Markdown filenames that are documentation, never workflow items.
DOC_STEMS = {"readme", "contributing", "license", "changelog", "security",
             "code_of_conduct", "index", "_index", "authors", "notice"}


def _read(path: Path) -> tuple[dict, str] | None:
    try:
        return frontmatter.parse(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None


def _description(meta: dict, body: str) -> str:
    desc = str(meta.get("description") or "").strip()
    if desc:
        return desc
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:160]
    return ""


def _content_digest(name: str, description: str, body: str) -> str:
    """Content identity for an item: what it *is*, independent of where it sits.

    Deliberately not the file bytes and not the body alone. The text hashed here
    is exactly what :func:`rag.read_body` assembles — ``name``, ``description``,
    then the frontmatter-stripped body — because that is the string boost
    already treats as an item's content everywhere it clusters copies, and two
    identity keys that *nearly* agree are worse than one.

    Measured over a real 460-tap install (60,047 entries), against the two
    alternatives that look reasonable:

        name+description+body   41,051 clusters   0 span >1 name   <- this
        body only               40,372 clusters   259 span >1 name
        name+description        37,668 clusters   2 span >1 name

    Body-only merges 259 clusters that span different names — the
    ``admin-interface-rule`` collision #366 fixed, where one registry ships two
    unrelated rules under one name. Metadata-only over-collapses in the other
    direction: 3,383 clusters of items that share a name and description while
    carrying genuinely different prose. Including all three separates both.

    Truncated to 16 hex chars to match the index, which stores one of these per
    document; the full digest doubles the index for collision odds that are
    already negligible at 60k items.
    """
    text = "%s\n%s\n%s" % (name, description, body)
    return hashlib.sha256(text.strip().encode("utf-8", "replace")).hexdigest()[:16]


def _make_entry(root: Path, defining_file: Path, kind: str, default_name: str,
                tap_name: str, curated: bool, meta: dict, body: str) -> dict:
    name = str(meta.get("name") or "").strip() or default_name
    # Slugify anything that is not already a safe path component, not just names
    # containing a space: this name becomes a rule/workflow filename, so
    # `../../..` has to be neutralized at index time too, not only at the sinks.
    slug = util.safe_component(name)
    description = _description(meta, body)
    item_dir = defining_file.parent
    return {
        "name": slug,
        "description": description,
        "version": str(meta.get("version") or "0.0.0"),
        "tap": tap_name,
        "curated": curated,
        "kind": kind,
        "rel_dir": item_dir.relative_to(root).as_posix() if item_dir != root else ".",
        "skill_md": defining_file.relative_to(root).as_posix(),
        "meta": meta,
        # Free here and nowhere else: the body is already read, parsed and about
        # to be discarded. `rag` used to re-open all 60k files at index time to
        # recompute exactly this (~14 s on a real install) because the entry did
        # not carry it.
        "content": _content_digest(slug, description, body),
        # Lowercased substring-search blob, flattened once at index time so
        # search() never re-walks the frontmatter per query (see _search_blob).
        "search_blob": _search_blob(slug, description, meta),
    }


def _classify_rule(path: Path) -> bool:
    return path.name in RULE_FILENAMES or path.suffix.lower() in RULE_SUFFIXES


def _classify_workflow(path: Path, meta: dict) -> bool:
    """A Markdown file is a workflow if it lives under a commands/agents/
    workflows directory, or carries subagent/slash-command frontmatter."""
    if path.suffix.lower() != ".md" or path.name == "SKILL.md":
        return False
    if path.stem.lower() in DOC_STEMS:
        return False
    parent_parts = {p.lower() for p in path.parent.parts}
    if parent_parts & WORKFLOW_DIRS:
        return True
    return bool(meta.get("name") and meta.get("description")
                and (WORKFLOW_META_KEYS & set(meta)))


def scan_dir(root: Path, tap_name: str = "local", curated: bool = False) -> list[dict]:
    """Walk `root` and index every skill/rule/workflow into entry dicts.

    Files inside a SKILL.md dir belong to that skill, never re-indexed;
    output is sorted by (skill_md, name) regardless of walk order.
    """
    root = Path(root)
    entries: list[dict] = []
    skill_dirs: set[Path] = set()
    # One top-down walk instead of two rglob passes: prune ignored dirs in place
    # so we never descend into .git/__pycache__, and test skill-dir membership
    # against a set via each dir's own ancestor chain rather than O(files × dirs).
    # Top-down order guarantees a file's governing SKILL.md dir is seen first, and
    # the final entries.sort() normalizes output order regardless of walk order.
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in util.IGNORED]
        here = Path(dirpath)
        # A directory holding a SKILL.md is a skill: index it and remember the
        # dir so its other files are not re-indexed as loose rules/workflows.
        if "SKILL.md" in filenames:
            parsed = _read(here / "SKILL.md")
            if parsed is not None:
                meta, body = parsed
                default = here.name if here != root else root.name
                entries.append(_make_entry(root, here / "SKILL.md", KIND_SKILL,
                                           default, tap_name, curated,
                                           meta, body))
                skill_dirs.add(here)
        # Files inside any skill directory belong to that skill, never re-indexed.
        if here in skill_dirs or any(a in skill_dirs for a in here.parents):
            continue
        for name in filenames:
            path = here / name
            is_rule = _classify_rule(path)
            is_md = path.suffix.lower() == ".md" and path.name != "SKILL.md"
            if not is_rule and not is_md:
                continue
            parsed = _read(path)
            if parsed is None:
                continue
            meta, body = parsed
            if is_rule:
                kind = KIND_RULE
            elif _classify_workflow(path, meta):
                kind = KIND_WORKFLOW
            else:
                continue
            if path.name in RULE_FILENAMES:
                default = path.parent.name if path.parent != root else root.name
            else:
                default = path.stem
            entries.append(_make_entry(root, path, kind, default,
                                       tap_name, curated, meta, body))

    entries.sort(key=operator.itemgetter("skill_md", "name"))
    return entries


def rebuild_tap(tap: registry.Tap) -> list[dict]:
    """Rescan a cloned tap and rewrite its JSON cache file -> entries.

    Raises BoostError when the tap is not cloned; also drops the
    in-process entry cache so an immediate load sees the rebuild.
    """
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "format": CACHE_FORMAT,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1), encoding="utf-8")
    # Drop the mtime-keyed cache so a rebuild is visible to an immediately
    # following load even when the filesystem mtime granularity is coarse.
    _ENTRY_CACHE.pop(str(tap.cache_file), None)
    return entries


# Entry-set cache, keyed on each tap cache file's (mtime_ns, size) stamp. The
# BM25 index is mtime-cached the same way (rag._load_raw); without this, every
# search reparses every tap cache. Entries are treated read-only by callers, so
# the cached list is shared by reference (matching the index cache). Keying on
# nanosecond mtime + size catches rewrites a bare second-resolution mtime would
# miss.
_ENTRY_CACHE: dict[str, tuple[tuple[int, int], list[dict], bool]] = {}


def _cached_tap(tap: registry.Tap) -> tuple[list[dict], bool] | None:
    """``(skills, is_current)`` for a tap's cache, or ``None`` to force a
    rebuild (file missing, unreadable, or corrupt JSON).

    ``is_current`` says whether the cache was written by this scanner. It is
    reported rather than acted on here because the right response depends on
    something this function cannot see: whether the clone is still on disk to
    rescan. A stale cache is not *wrong* — it is missing fields its consumers
    have since learned to want, and every one of them degrades cleanly without
    them — so discarding it unconditionally would trade a missing digest for
    missing entries, which is the worse failure.
    """
    p = tap.cache_file
    key = str(p)
    try:
        st = p.stat()
    except OSError:
        _ENTRY_CACHE.pop(key, None)
        return None
    stamp = (st.st_mtime_ns, st.st_size)
    cached = _ENTRY_CACHE.get(key)
    if cached is not None and cached[0] == stamp:
        return cached[1], cached[2]
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _ENTRY_CACHE.pop(key, None)
        return None
    skills = data.get("skills", [])
    current = data.get("format") == CACHE_FORMAT
    _ENTRY_CACHE[key] = (stamp, skills, current)
    return skills, current


def load_tap(tap: registry.Tap, rebuild: bool = False) -> list[dict]:
    """Return a tap's entries, from the mtime-keyed cache when fresh.

    `rebuild=True` or a missing/corrupt cache forces a rescan; an
    uncloned tap yields `[]`.

    A cache written by an older scanner is rescanned *when the clone is still
    there to rescan* — that is what backfills a new entry field across every tap
    on a machine (460 of them on a real install) without asking anyone to re-tap.
    When the clone is gone the stale entries are served as they are: consumers
    all degrade cleanly on a missing field, so refusing to answer would cost the
    user their catalogue to buy a digest.
    """
    if not rebuild:
        cached = _cached_tap(tap)
        if cached is not None:
            skills, current = cached
            if current or not tap.is_cloned:
                return skills
    if tap.is_cloned:
        return rebuild_tap(tap)
    return []


def lint_targets(entries: list[dict], tap_root: Path,
                 names: list[str] | None = None,
                 ) -> tuple[list[tuple[str, Path]], list[dict]]:
    """Split tap entries into lintable skills and skipped rule/workflow items.

    `boost lint` scores a SKILL.md directory, so only `skill` entries are
    lintable: rules and workflows are single files with no SKILL.md and
    would every one of them score 0 with a bogus "missing SKILL.md".
    Returns `(targets, skipped)` — `targets` is `(name, item_dir)` per skill
    (an entry with no `kind` counts as a skill, for caches written before
    kinds existed), `skipped` is `{"name", "kind"}` per non-skill entry.
    A non-empty `names` filters both lists, so an explicitly named rule is
    still reported as skipped rather than vanishing.
    """
    wanted = set(names or ())
    targets: list[tuple[str, Path]] = []
    skipped: list[dict] = []
    for entry in entries:
        if wanted and entry["name"] not in wanted:
            continue
        kind = entry.get("kind", KIND_SKILL)
        if kind == KIND_SKILL:
            targets.append((entry["name"],
                            Path(tap_root) / entry.get("rel_dir", ".")))
        else:
            skipped.append({"name": entry["name"], "kind": kind})
    return targets, skipped


def all_entries() -> list[dict]:
    """Return the entries of every configured tap, concatenated."""
    out: list[dict] = []
    for tap in registry.list_taps():
        out.extend(load_tap(tap))
    return out


def kind_counts() -> dict[str, int]:
    """Per-kind entry counts across every configured tap.

    The same reads :func:`all_entries` does, one tap's cache at a time, without
    the concatenation. A caller that only wants the size of the corpus should
    not have to materialise it: the MCP ``boost_doctor`` handler took
    ``len(all_entries())``, which builds a 71,655-element list on a real
    install to produce one integer.

    An entry with no ``kind`` counts as a skill, the way it renders everywhere
    else. An unrecognised kind gets its own key rather than being dropped, so
    ``sum(kind_counts().values())`` equals ``len(all_entries())`` for any cache
    — including one written before a kind existed.
    """
    counts: dict[str, int] = {KIND_SKILL: 0, KIND_RULE: 0, KIND_WORKFLOW: 0}
    for tap in registry.list_taps():
        for entry in load_tap(tap):
            kind = entry.get("kind") or KIND_SKILL
            counts[kind] = counts.get(kind, 0) + 1
    return counts


def split_name(name: str) -> tuple[str | None, str]:
    """Split a possibly tap-qualified name into ``(tap, bare_name)``.

    ``'owner/repo:skill'`` -> ``('owner/repo', 'skill')``; an unqualified name
    -> ``(None, name)``. The single place the ``tap:skill`` grammar is spelled
    out, so a caller that must look the name up somewhere keyed by the *bare*
    name — the lock file, the canonical store — splits it exactly the way
    :func:`find` does. ``None`` rather than ``""`` for the unqualified case, so
    a caller can tell "no qualifier given" from the degenerate ``":skill"``.
    """
    if ":" in name:
        tap, bare = name.rsplit(":", 1)
        return tap, bare
    return None, name


def tap_matches(tap_name: str, qualifier: str) -> bool:
    """True when ``qualifier`` selects the single tap ``tap_name``.

    The one-candidate form of :func:`find`'s tap filter — an exact
    ``owner/repo`` or the bare repo tail. Not a substitute for find's tiering,
    which picks the *best* tap among several; here there is only one to accept
    or reject, so the two tiers collapse into one test.
    """
    return bool(tap_name) and qualifier in (tap_name, tap_name.split("/")[-1])


def find(name: str, tap: str | None = None) -> list[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    qualifier, bare = split_name(name)
    if qualifier is not None:
        tap, name = qualifier, bare
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        # Same tiering as registry.get: a qualified owner/repo beats a bare
        # repo tail, so `angular/skills:x` never picks up `microsoft/skills:x`.
        # Without this the two resolvers disagreed — `boost untap skills`
        # errored on the ambiguity while `boost bundle apply` with
        # `skills:brainstorming` silently took matches[0] from whichever tap
        # sorted first.
        exact = [e for e in matches if e["tap"] == tap]
        matches = exact or [e for e in matches
                            if e["tap"].split("/")[-1] == tap]
    return matches


def _identity(entry: dict) -> str:
    """What a user could actually use to tell two candidates apart.

    Deliberately the *displayed* metadata — name, description, version and
    frontmatter — not the file bytes, which a catalog entry does not carry.
    That is the honest test for "this prompt is unanswerable": if two rows
    render identically everywhere boost shows them, asking the user to choose
    between them cannot succeed.
    """
    return json.dumps([entry.get("name", ""), entry.get("description", "") or "",
                       str(entry.get("version", "")), entry.get("meta") or {}],
                      sort_keys=True, default=str)


def _canonical(matches: list[dict]) -> dict:
    """The shallowest copy, ties broken lexicographically.

    Registries vendor their own skills into plugin bundles, so the top-level
    `skills/x` is the original and `plugins/pack/skills/x` is the copy. Sorting
    makes the pick deterministic: resolving on dict order would install a
    different directory from one run to the next.
    """
    return min(matches, key=lambda e: (str(e.get("rel_dir", "")).count("/"),
                                       str(e.get("rel_dir", ""))))


def _by_path(matches: list[dict], path: str) -> list[dict]:
    """Narrow candidates to those whose ``rel_dir`` is (or ends with) ``path``.

    Suffix rather than equality because the paths this disambiguates are the
    ones a registry vendored deep — `plugins/pack-claude/skills/dbg` — and the
    user is copying out of an error message. Matching on a trailing segment
    lets `--path skills/dbg` work without pasting the whole prefix. It stays a
    *segment* match: `s/dbg` must not be satisfied by `.../not-s/dbg`.
    """
    want = path.strip("/")
    exact = [e for e in matches
             if str(e.get("rel_dir", "")).strip("/") == want]
    if exact:
        # An exact rel_dir beats a suffix hit, or naming the canonical
        # `skills/x` would stay "ambiguous" against the mirror
        # `.openclaw/skills/x` that also ends with it — leaving the shape this
        # flag exists for unresolvable by the very path the error printed.
        return exact
    return [e for e in matches
            if str(e.get("rel_dir", "")).strip("/").endswith("/" + want)]


def _suggestions(scored, limit: int = 3) -> list[str]:
    """Distinct, typeable labels for a "closest matches" hint.

    Bare names alone could render the same word several times — a registry that
    mirrors one skill into a directory per agent scores every copy — which
    offers the user three of nothing. Collapse by name, and qualify with the tap
    only when one name genuinely spans more than one registry, since that is the
    case where the bare name would not resolve either.

    ``limit`` is applied *after* collapsing, and that ordering is the point.
    De-duplicating a pre-sliced top-3 shrinks the hint to one suggestion in
    exactly the mirrored-registry case this function exists for; taking the
    first ``limit`` distinct labels instead keeps three real alternatives on
    screen. Callers pass the whole scored list.
    """
    taps_for: dict[str, set] = {}
    for e, _ in scored:
        taps_for.setdefault(e["name"], set()).add(e.get("tap", ""))
    labels: list[str] = []
    for e, _ in scored:
        nm = e["name"]
        label = ("%s:%s" % (e.get("tap", "?"), nm)
                 if len(taps_for[nm]) > 1 else nm)
        if label not in labels:
            labels.append(label)
            if len(labels) >= limit:
                break
    return labels


def resolve_one(name: str, path: str | None = None) -> dict:
    """Find exactly one entry or raise with a helpful hint.

    ``path`` answers the one-tap ambiguity below. It deliberately cannot
    resolve a *cross-tap* collision: two taps are two supply chains, and a
    path is not provenance.
    """
    matches = find(name)
    if path and matches:
        # Filter even when the name is already unique: a `--path` that matches
        # nothing is a typo, and silently ignoring it installs something the
        # user believes they just ruled out. Narrowing never merges two taps,
        # so the cross-tap refusal below still fires on what survives.
        narrowed = _by_path(matches, path)
        if not narrowed:
            raise BoostError(
                "no skill named %r under path %r" % (name, path),
                hint="paths for %r: %s" % (name, ", ".join(
                    sorted(str(e.get("rel_dir", "?")) for e in matches))))
        matches = narrowed
    if not matches:
        qualifier, bare = split_name(name)
        if qualifier is not None and "/" in bare:
            # `tap:skill` selects a *registry*, so a path-shaped tail is the
            # grammar being misread rather than a missing skill — and the
            # fuzzy hint below cannot say so. Name the confusion and hand back
            # the command that works.
            #
            # The qualifier is carried into the suggestion rather than dropped.
            # It is the half the user got right, and without it the suggested
            # command means something different: a leaf name that exists in two
            # taps resolves elsewhere or raises cross-tap ambiguity, so the
            # "fix" would fail for the user who most needed the tap.
            raise BoostError(
                "no skill named %r — after ':' boost expects a skill name, "
                "not a path" % bare,
                hint="`tap:skill` picks the registry; to pick a copy inside "
                     "one, use --path: `boost install %s:%s --path %s`"
                     % (qualifier, bare.rsplit("/", 1)[-1], bare))
        # The whole scored list, not a pre-sliced top 3 — see _suggestions:
        # slicing first collapses to one suggestion exactly when a registry
        # mirrors a skill per agent, which is the case it exists to handle.
        scored = search(name)
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(_suggestions(scored))
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        # `name` may already be tap-qualified; hints must re-qualify the BARE
        # name or they emit `t:t:x`, which can never resolve.
        bare = name.rsplit(":", 1)[-1]
        # Order-preserving, so the first tap named stays the one the hint
        # suggests. Sorting here would silently change the existing message.
        taps = list(dict.fromkeys(e["tap"] for e in matches))
        if len(taps) == 1:
            # One tap holding the same name several times. If the rows are
            # indistinguishable it is a vendored copy and there is nothing to
            # choose between them, so choose.
            if len({_identity(e) for e in matches}) == 1:
                return _canonical(matches)
            # Genuinely different skills sharing a name inside one registry:
            # boost cannot pick, and telling the user to "qualify by tap" is
            # advice that reproduces this very error. Name the paths instead.
            paths = ", ".join(sorted(str(e.get("rel_dir", "?")) for e in matches))
            raise BoostError(
                "%r matches %d different skills in %s: %s"
                % (bare, len(matches), taps[0], paths),
                hint="that registry ships one name twice — pick one with "
                     "`--path <one of the above>`, and raise it with the tap")
        # Several taps, one thing. Registries mirror each other constantly, so
        # the common cross-tap collision is N byte-identical copies of one
        # skill — and the within-tap branch above already decided that
        # indistinguishable candidates are boost's problem to resolve, not the
        # user's. Applying the same judgement here removes a dead end (a
        # mirrored skill could not be installed unqualified at all) without
        # touching the genuine-ambiguity error, which still fires whenever the
        # copies actually differ.
        best = _same_thing(matches)
        if best is not None:
            return best
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(taps)),
            hint="qualify it, e.g. `%s:%s`" % (taps[0], bare))
    return matches[0]


def _same_thing(matches: list[dict]) -> dict | None:
    """The copy to install when every candidate is the same content, else None.

    Returns None unless *every* candidate carries a digest and they all agree.
    A missing digest is an unknown, never a match: assuming two unknowns equal
    would silently install one skill when the user asked about another, which is
    strictly worse than the error it would be replacing.

    Ranked by :func:`rag.source_rank` — the user's own ``curated`` flag first,
    the shipped registry confidence second — which exists for exactly this
    decision and is what `dedupe_by_content` already uses to choose between
    identical bodies in search results. Ties break on ``(tap, rel_dir)`` so the
    pick cannot vary between runs.
    """
    digests = {e.get("content") for e in matches}
    if len(digests) != 1 or not next(iter(digests)):
        return None
    # Local import: `rag` imports this module, so the edge only exists at call
    # time. Same shape as `store.install`'s deferred `gitutil` import.
    from . import rag
    return min(matches, key=lambda e: (rag.source_rank(e),
                                       str(e.get("tap", "")),
                                       str(e.get("rel_dir", ""))))


def _meta_text(meta) -> str:
    """Lowercased, space-joined flatten of a frontmatter dict for substring
    search. Cheaper than ``json.dumps(meta).lower()`` — which built and threw
    away a JSON string on every entry of every query just to substring-match —
    while matching the same words (tags, keys, scalar values)."""
    parts: list[str] = []

    def walk(v) -> None:
        if isinstance(v, dict):
            for k, val in v.items():
                parts.append(str(k))
                walk(val)
        elif isinstance(v, (list, tuple)):
            for val in v:
                walk(val)
        elif v is not None:
            parts.append(str(v))

    walk(meta or {})
    return " ".join(parts).lower()


def _search_blob(name: str, description: str, meta) -> str:
    """The full lowercased substring-search text for an entry: its name,
    description and flattened frontmatter. Built once at index time and cached
    on the entry as ``search_blob`` so search() never rebuilds it per query."""
    # `or ""` is load-bearing despite the `str` annotation: search() calls this
    # with e.get("description", ""), which yields None when the key holds None.
    return " ".join([name.lower(), (description or "").lower(), _meta_text(meta)])  # noqa: FURB143


def search(query: str, entries: list[dict] | None = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        # Precomputed at index time; fall back for older caches / entries
        # constructed without a blob (e.g. tests passing raw dicts).
        blob = e.get("search_blob")
        if blob is None:
            blob = _search_blob(e["name"], e.get("description", ""),
                                e.get("meta", {}))
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored
