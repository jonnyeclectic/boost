"""Skill Information commands — list, info, cat, edit, preview, explain,
log, home, deps, tag.

Read-mostly views over the lock file, the canonical store, and tap catalogs.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import textwrap
import webbrowser
from itertools import chain
from pathlib import Path

from .. import cliparse
from ..core import (
    ai,
    capabilities,
    catalog,
    config,
    faithfulness,
    frontmatter,
    gitutil,
    imperative,
    integrity,
    journal,
    lockfile,
    logs,
    paths,
    projectlock,
    registry,
    rules,
    scopes,
    store,
    util,
)
from ..core import output as out
from ..errors import BoostError

# ---------------------------------------------------------------- helpers

_tilde = paths.tilde


def _read(p: Path) -> str:
    try:
        return Path(p).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise BoostError("cannot read %s: %s" % (_tilde(p), e)) from e


def _for_tap(entry, qualifier):
    """``entry`` unless a ``tap:`` qualifier was given that it does not satisfy.

    A qualifier has to be honored against the *installed* record, not only the
    catalog: with one skill installed from tap A and asked about via
    ``tap-b:skill``, tap A's lock entry is the wrong answer, and reporting it
    would describe another tap's install as this one's.
    """
    if entry and qualifier and not catalog.tap_matches(
            str(entry.get("tap") or ""), qualifier):
        return None
    return entry


def _resolve_skill_md(name: str):
    """Locate a skill's SKILL.md — installed store first, then tap clones.

    ``name`` may be tap-qualified (``owner/repo:skill``). The catalog reads that
    form directly, but the lock file and the canonical store are keyed by the
    bare name — and ``skill_store_dir`` rejects the qualified string outright,
    since it is not a safe path component.

    Returns (path, lock_entry_or_None, catalog_entry_or_None).
    """
    qualifier, bare = catalog.split_name(name)
    lock = _for_tap(lockfile.get_skill(bare), qualifier)
    if lock:
        # The single place skill content is served from — so it is the single
        # place to refuse serving a tree that has drifted from its locked digest
        # (a no-op unless enforcement is switched on).
        integrity.enforce(bare, lock)
        p = store.skill_store_dir(bare) / "SKILL.md"
        if p.exists():
            return p, lock, None
    entry = catalog.resolve_one(name)
    return registry.get(entry["tap"]).path / entry["skill_md"], lock, entry


def _materialized_text(name: str, kind: str, entry: dict):
    """The content an installed rule/workflow actually serves, or None.

    The honest source is the materialized artifact the lock records — that is
    what the agent loads — not the tap copy, which may have moved on since. A
    claude-mode materialization is a managed block inside a shared context
    file, so only the block counts, never the whole file. Mirrors
    ``integrity.enforce`` for the kinds it never covered: "modified" blocks
    only with enforcement switched on, UNLOCKED never blocks. Quarantine
    always errors — the artifacts were removed on purpose, and silently
    serving the tap copy would resurrect what the user suspended.
    """
    if entry.get("quarantined"):
        raise BoostError(
            "%s %s is quarantined — its materialized content was removed"
            % (kind, name),
            hint="release it with `boost quarantine --release %s`" % name)
    if integrity.enforcement_enabled():
        st = integrity.materialized_status(name, entry)
        if st == integrity.STATUS_MODIFIED:
            raise BoostError(
                "%s %s has been modified since install — its materialized "
                "content no longer matches the lock file" % (kind, name),
                hint="inspect with `boost verify %s`, then `boost reinstall "
                     "%s` to restore the locked copy" % (name, name))
        if st == integrity.STATUS_MISSING:
            raise BoostError(
                "%s %s is in the lock file but its materialized artifacts "
                "are gone" % (kind, name),
                hint="`boost sync` to restore them, or `boost reinstall %s`"
                     % name)
    for m in entry.get("materializations") or []:
        try:
            text = Path(m.get("path", "")).read_text(encoding="utf-8")
        except OSError:
            continue
        if m.get("mode") == rules.MODE_CLAUDE:
            block = rules.read_block(text, name)
            if block is not None:
                return block
            continue
        return text
    return None


def _resolve_text(name: str):
    """Content for a named item of any kind -> (text, kind, lock, cat).

    Skills keep :func:`_resolve_skill_md`'s contract (store copy,
    digest-enforced, tap fallback). A rule or workflow serves its
    materialized artifact, falling back to the tap source file when no
    materialization is readable.
    """
    qualifier, bare = catalog.split_name(name)
    found = lockfile.find_any(bare)
    if found is None or found[0] == "skill":
        path, lock, cat = _resolve_skill_md(name)
        return _read(path), "skill", lock, cat
    kind, entry = found
    lock = _for_tap(entry, qualifier)
    if lock is not None:
        text = _materialized_text(bare, kind, lock)
        if text is not None:
            return text, kind, lock, None
    cat = catalog.resolve_one(name)
    return _read(registry.get(cat["tap"]).path / cat["skill_md"]), kind, lock, cat


def _as_list(v) -> list:
    """Normalize a frontmatter value to a list of non-empty strings."""
    if v in (None, "", False):
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [s.strip() for s in str(v).split(",") if s.strip()]


def _skill_meta(name: str):
    """Frontmatter for a named skill — installed store preferred, else tap."""
    p = store.skill_store_dir(name) / "SKILL.md"
    if not p.exists():
        matches = catalog.find(name)
        if not matches:
            return None
        try:
            p = registry.get(matches[0]["tap"]).path / matches[0]["skill_md"]
        except BoostError:
            return None
        if not p.exists():
            return None
    return frontmatter.parse(_read(p))[0]


def _file_count(d: Path) -> int:
    return sum(1 for p in Path(d).rglob("*")
               if p.is_file() and not any(part in util.IGNORED for part in p.parts))


def _mark(installed: bool) -> str:
    return (out.role("✓ installed", "success") if installed
            else out.role("✗ not installed", "danger"))


def _print_wrapped(text: str) -> None:
    paras = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    for i, para in enumerate(paras):
        for line in textwrap.wrap(" ".join(para.split()), width=76):
            out.info(line)
        if i < len(paras) - 1:
            print()


# ---------------------------------------------------------------- commands

def _materialized_agents(entry):
    """Abbreviated agent column for a rule/workflow, from its materializations."""
    agent_names = [m.get("agent", "") for m in entry.get("materializations") or []]
    return "·".join(a.split("-")[0] for a in agent_names)


def _kind_table(heading, items, extra=None):
    """Render an installed rule/workflow table. ``extra`` is an optional
    ``(column, key)`` pair for a per-kind column (e.g. a workflow's slot); the
    count line reuses the heading's trailing noun (`installed rules` -> `rule`)."""
    out.heading(heading)
    headers: tuple = ("NAME", "VERSION", "TAP", "AGENTS")  # `extra` adds a 5th
    rows: list[tuple] = []   # 4 columns, or 5 when `extra` adds one
    for name in sorted(items):
        e = items[name]
        row = [name, e.get("version", "?"), e.get("tap", "?"),
               _materialized_agents(e)]
        if extra:
            row.append(str(e.get(extra[1], "") or ""))
        rows.append(tuple(row))
    if extra:
        headers = (*headers, extra[0])
    out.table(rows, headers=headers)
    noun = heading.split()[-1][:-1]  # "installed rules" -> "rule"
    print("  " + out.aurora("%d %s%s installed"
                            % (len(rows), noun, "" if len(rows) == 1 else "s"),
                            "cyan"))


def cmd_list(argv):
    ap = cliparse.parser(prog="boost list",
                                 description="List installed skills, rules and workflows")
    ap.add_argument("--kind", choices=("skill", "rule", "workflow"), default=None,
                    help="only show installed items of this kind")
    ap.add_argument("--tag", help="only show skills carrying this tag")
    ap.add_argument("--local", action="store_true",
                    help="only the skills installed into this repo")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    skills = lockfile.installed()
    rules = lockfile.installed_rules()
    workflows = lockfile.installed_workflows()
    # Project skills live in the repo's own lock, never the user's — read it
    # separately so a checkout's committed skills show up alongside yours.
    pbase = scopes.project_root()
    project = projectlock.installed(pbase) if pbase is not None else {}
    if args.local:
        skills, rules, workflows = {}, {}, {}
    if args.tag and args.kind not in (None, "skill"):
        # Refuse rather than print an empty table. Tags exist only on skills,
        # so `--kind rule --tag x` can only ever render "no rules installed" —
        # a different and false statement about the machine.
        raise BoostError(
            "--tag applies to skills, and --kind %s excludes them" % args.kind,
            hint="drop --tag, or use `boost list --kind skill --tag %s`"
                 % args.tag.lstrip("#"))
    if args.tag:
        # Tags are a skill-only concept, so --tag narrows to skills.
        want = args.tag.lstrip("#")
        skills = {n: e for n, e in skills.items() if want in (e.get("tags") or [])}
        rules, workflows, project = {}, {}, {}
    if args.kind:
        # Empty the sections not asked for. The --json envelope keeps all four
        # keys either way, so a consumer's data["skills"] never starts raising
        # just because a flag was added.
        if args.kind != "skill":
            skills, project = {}, {}
        if args.kind != "rule":
            rules = {}
        if args.kind != "workflow":
            workflows = {}
    if args.json:
        print(json.dumps({"skills": skills, "rules": rules,
                          "workflows": workflows, "project": project},
                         indent=2, sort_keys=True))
        return 0
    if not skills and not rules and not workflows and not project:
        # Name the kind that was asked for. "no skills installed" in answer to
        # `--kind rule` sends you looking for a skill that was never the point.
        print(out.empty_state(
            "no %ss installed" % (args.kind or "skill")
            + (" with tag #%s" % args.tag.lstrip("#") if args.tag else ""),
            hint="boost tap --defaults && boost search <topic>"))
        return 0
    if skills:
        out.heading("installed skills")
        rows: list[tuple] = []   # 5 columns here, 4 for project skills below
        for name in sorted(skills):
            e = skills[name]
            # Aurora-tinted flags — now that table() aligns by visible width,
            # colored cells stay in their column: pinned amber, quarantined pink,
            # tags dim.
            flags = ([out.aurora("pinned", "yellow")] if e.get("pinned") else []) + \
                    ([out.aurora("quarantined", "pink")] if e.get("quarantined")
                     else []) + \
                    [out.role("#" + t, "muted") for t in e.get("tags") or []]
            rows.append((name, e.get("version", "?"), e.get("tap", "?"),
                         "·".join(a.split("-")[0] for a in e.get("agents") or []),
                         " ".join(flags)))
        out.table(rows, headers=("NAME", "VERSION", "TAP", "AGENTS", "FLAGS"))
        print("  " + out.aurora("%d skill%s installed"
                                % (len(rows), "" if len(rows) == 1 else "s"), "cyan"))
    if project:
        out.heading("project skills (%s)" % paths.tilde(pbase))
        rows = [(name, e.get("version", "?"), e.get("tap", "?"),
                 "·".join(a.split("-")[0] for a in e.get("agents") or []))
                for name, e in sorted(project.items())]
        out.table(rows, headers=("NAME", "VERSION", "TAP", "AGENTS"))
        print("  " + out.role("committed with the repo — %s/%s"
                              % (projectlock.LOCK_DIRNAME,
                                 projectlock.LOCK_FILENAME), "muted"))
    if rules:
        _kind_table("installed rules", rules)
    if workflows:
        _kind_table("installed workflows", workflows, extra=("SLOT", "slot"))
    return 0


def _info_materialized(name: str, kind: str, entry: dict, as_json: bool) -> int:
    """The identity card for an installed rule/workflow — the lock facts.

    No store dir, quality score or file counts here: those describe a skill's
    directory, which these kinds do not have. What matters is what the lock
    records — where it came from and which agent files carry it.
    """
    if as_json:
        print(json.dumps({"name": name, "kind": kind, "installed": entry},
                         indent=2))
        return 0
    out.heading(name)
    badges = [out.badge("installed %s" % kind, "green")]
    if entry.get("pinned"):
        badges.append(out.badge("pinned", "yellow"))
    if entry.get("quarantined"):
        badges.append(out.badge("quarantined", "pink"))
    if entry.get("tap"):
        badges.append(out.badge(str(entry["tap"]), "violet"))
    out.info(" ".join(badges))
    out.kv("kind", kind)
    out.kv("version", str(entry.get("version", "?")))
    out.kv("tap", entry.get("tap", "?"))
    if kind == "workflow" and entry.get("slot"):
        out.kv("slot", str(entry["slot"]))
    if entry.get("scope"):
        out.kv("scope", str(entry["scope"]))
    if entry.get("source_file"):
        out.kv("source", str(entry["source_file"]))
    if entry.get("commit"):
        out.kv("commit", str(entry["commit"])[:9])
    if entry.get("sha256"):
        out.kv("sha256", str(entry["sha256"])[:12])
    ia, ua = entry.get("installed_at"), entry.get("updated_at")
    if ia:
        out.kv("installed", "%s (%s)" % (ia, util.rel_time(ia)))
    if ua and ua != ia:
        out.kv("updated", "%s (%s)" % (ua, util.rel_time(ua)))
    agents = [m.get("agent", "?") for m in entry.get("materializations") or []]
    out.kv("materialized", ", ".join(agents) or "(none)")
    out.kv("pinned", "yes" if entry.get("pinned") else "no")
    out.kv("quarantined", "yes" if entry.get("quarantined") else "no")
    return 0


def cmd_info(argv):
    ap = cliparse.parser(prog="boost info",
                                 description="Show detailed info about a skill")
    ap.add_argument("name")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    # The name may arrive tap-qualified (`owner/repo:skill`) — exactly what the
    # ambiguity error hints at when one name lives in several taps. Split once
    # here: the qualified form is a *catalog* lookup key, while the lock file
    # and the canonical store are keyed by the bare name (and `skill_store_dir`
    # rejects the qualified string, since `owner/repo:skill` is not a safe path
    # component). Everything below this line works from the bare name.
    qualifier, name = catalog.split_name(args.name)
    lock = _for_tap(lockfile.get_skill(name), qualifier)
    if lock is None:
        # An installed rule/workflow is installed — `boost list` shows it, so
        # answering from the catalog (or "unknown") here would deny it exists.
        found = lockfile.find_any(name)
        if found is not None and found[0] != "skill":
            kentry = _for_tap(found[1], qualifier)
            if kentry is not None:
                return _info_materialized(name, found[0], kentry, args.json)
    # A project-scoped skill is installed — just not at user scope. Without this
    # `boost info` would call it "not installed" while it sits in the repo, and
    # the install banner's own "next: boost info <name>" would lead nowhere.
    pbase = scopes.project_root()
    plock = (_for_tap(projectlock.get_skill(pbase, name), qualifier)
             if pbase is not None else None)
    if lock:
        matches = catalog.find(args.name)
        same_tap = [e for e in matches if e["tap"] == lock.get("tap")]
        candidates = same_tap or matches
        cat = candidates[0] if candidates else None
    else:
        cat = catalog.resolve_one(args.name)   # raises if unknown anywhere

    sdir = store.skill_store_dir(name)
    skill_dir = sdir if lock and sdir.is_dir() else None
    if skill_dir is None and plock:
        for m in plock.get("materializations") or []:
            cand = scopes.resolve_in_base(pbase, m.get("path"))
            if cand is not None and cand.is_dir():
                skill_dir = cand
                break
    if skill_dir is None and cat:
        try:
            skill_dir = store.source_dir_for(cat)
        except BoostError:
            skill_dir = None
    desc = str((cat or {}).get("description") or "")
    meta: dict = {}
    skill_text = ""
    if skill_dir and (skill_dir / "SKILL.md").exists():
        skill_text = _read(skill_dir / "SKILL.md")
        meta, _body = frontmatter.parse(skill_text)
        desc = desc or str(meta.get("description") or "")
    declared_caps = sorted(capabilities.declared(meta))
    detected_extra = sorted(capabilities.detect(skill_text)
                            - set(declared_caps)) if skill_text else []
    mcp_servers = store.declared_mcp_servers(skill_dir) if skill_dir else []
    score = size = files = None
    if skill_dir:
        score, _notes = util.score_skill(skill_dir)
        size, files = util.dir_size(skill_dir), _file_count(skill_dir)

    if args.json:
        print(json.dumps({
            "name": name, "description": desc,
            "installed": lock, "project": plock,
            "capabilities": declared_caps, "detected_capabilities": detected_extra,
            "mcp_servers": [r["name"] for r in mcp_servers],
            "latest": (cat or {}).get("version"),
            "tap": (lock or plock or cat or {}).get("tap"),
            "store": str(sdir) if lock and sdir.is_dir() else None,
            "quality": score, "size": size, "files": files,
        }, indent=2))
        return 0

    out.heading(name)
    # Identity-card badges: a scannable status strip beneath the name, echoing
    # the web .badge pills. The detailed kv rows below still carry the specifics.
    badges = []
    if lock:
        badges.append(out.badge("installed", "green"))
        if lock.get("pinned"):
            badges.append(out.badge("pinned", "yellow"))
        if lock.get("quarantined"):
            badges.append(out.badge("quarantined", "pink"))
        latest = str((cat or {}).get("version") or "")
        if cat and latest != str(lock.get("version", "?")):
            badges.append(out.badge("update available", "yellow"))
    elif plock:
        badges.append(out.badge("installed in this project", "green"))
    else:
        badges.append(out.badge("not installed", "cyan"))
    tapname = (lock or cat or {}).get("tap")
    if tapname:
        badges.append(out.badge(str(tapname), "violet"))
    if badges:
        out.info(" ".join(badges))
    if desc:
        lines = textwrap.wrap(desc, width=62)
        out.kv("description", lines[0])
        for ln in lines[1:]:
            print(" " * 16 + ln)
    if lock:
        inst_v = str(lock.get("version", "?"))
        out.kv("version", inst_v)
        latest = str((cat or {}).get("version") or "")
        if cat and latest != inst_v:
            out.kv("latest", out.role(latest, "warn", bold=True)
                   + out.role("  (update available)", "muted"))
    else:
        out.kv("latest", str((cat or {}).get("version", "?")))
    out.kv("tap", (lock or cat or {}).get("tap", "?"))
    if lock and sdir.is_dir():
        out.kv("store", _tilde(sdir))
    src = lock.get("source_dir") if lock else (cat or {}).get("rel_dir")
    if src:
        out.kv("source", _tilde(src))
    if lock:
        if lock.get("commit"):
            out.kv("commit", str(lock["commit"])[:9])
        if lock.get("sha256"):
            out.kv("sha256", str(lock["sha256"])[:12])
        ia, ua = lock.get("installed_at"), lock.get("updated_at")
        if ia:
            out.kv("installed", "%s (%s)" % (ia, util.rel_time(ia)))
        if ua and ua != ia:
            out.kv("updated", "%s (%s)" % (ua, util.rel_time(ua)))
        out.kv("agents", ", ".join(lock.get("agents") or []) or "(none)")
        out.kv("pinned", "yes" if lock.get("pinned") else "no")
        out.kv("quarantined", "yes" if lock.get("quarantined") else "no")
        if lock.get("tags"):
            out.kv("tags", " ".join("#" + t for t in lock["tags"]))
    elif _as_list(meta.get("tags")):
        out.kv("tags", " ".join("#" + t for t in _as_list(meta.get("tags"))))
    if declared_caps:
        out.kv("capabilities", ", ".join(declared_caps))
    if detected_extra:
        # What the content shows but the author didn't declare — the
        # under-declaration signal a reviewer wants to see.
        out.kv("detected", out.role(", ".join(detected_extra) + "  (not declared)",
                                    "warn"))
    if mcp_servers:
        # A skill that needs an MCP server is useless without it, so this belongs
        # next to capabilities: both answer "what does this expect of my setup?"
        out.kv("mcp servers", ", ".join(r["name"] for r in mcp_servers))
    # All three are set together under `if skill_dir` above; naming that here
    # states the invariant instead of leaving it for a reader to reconstruct.
    if score is not None and size is not None and files is not None:
        out.kv("quality", "%d/100" % score)
        out.kv("size", util.human_size(size))
        out.kv("files", str(files))
    return 0


def cmd_cat(argv):
    ap = cliparse.parser(prog="boost cat",
                                 description="Print a skill or rule's contents")
    ap.add_argument("name")
    ap.add_argument("--raw", action="store_true", help="no styling even on a TTY")
    args = ap.parse_args(argv)
    text, _kind, _lock, _cat = _resolve_text(args.name)
    if args.raw or not sys.stdout.isatty():
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
        return 0
    block, body = frontmatter.split(text)
    if block:
        print(out.role("---", "muted"))
        for line in block.splitlines():
            print(out.role(line, "muted"))
        print(out.role("---", "muted"))
        print()
    for line in body.splitlines():
        print(out.c(line, out.BOLD) if re.match(r"^#{1,6} ", line) else line)
    return 0


def cmd_edit(argv):
    ap = cliparse.parser(prog="boost edit",
                                 description="Open a skill's SKILL.md in your editor")
    ap.add_argument("name")
    args = ap.parse_args(argv)
    lock = lockfile.get_skill(args.name)
    if not lock:
        found = lockfile.find_any(args.name)
        if found is not None:
            # Editing opens a skill's store dir; a rule/workflow has none — it
            # materializes into shared agent files (e.g. ~/.claude/CLAUDE.md).
            raise BoostError(
                "%s is a %s — boost edit applies to skills"
                % (args.name, found[0]),
                hint="a %s materializes into shared agent files, not a store "
                     "dir you can open; read it with `boost cat %s`"
                     % (found[0], args.name))
        raise BoostError("%s is not installed" % args.name,
                        hint="install it first, or `boost cat %s` to read the tap copy"
                        % args.name)
    sdir = store.skill_store_dir(args.name)
    path = sdir / "SKILL.md"
    if not path.exists():
        raise BoostError("SKILL.md missing from %s" % _tilde(sdir),
                        hint="repair the store with `boost sync`")
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    cmd = shlex.split(editor) or ["vi"]   # support EDITOR="code -w" etc.
    try:
        rc = subprocess.call([*cmd, str(path)])
    except OSError as e:
        raise BoostError("cannot launch editor %r: %s" % (editor, e),
                        hint="set $VISUAL or $EDITOR to a valid command") from e
    if rc != 0:
        out.warn("editor exited with status %d" % rc)
    sha = util.sha256_dir(sdir)
    if sha != lock.get("sha256"):
        lock["sha256"], lock["updated_at"] = sha, util.now_iso()
        lockfile.set_skill(args.name, lock)
        journal.log("edit", args.name)
        out.warn("local edits diverge from the tap source — boost drift will flag this")
    else:
        out.ok("no changes")
    return 0


def _inline(s: str) -> str:
    s = re.sub(r"`([^`]+)`", lambda m: out.role(m.group(1), "accent"), s)
    return re.sub(r"\*\*([^*]+)\*\*", lambda m: out.c(m.group(1), out.BOLD), s)


def _render_markdown(body: str) -> None:
    """Modest ANSI renderer: headings, fences, lists, inline code/bold."""
    in_fence = prev_blank = False
    for raw in body.splitlines():
        line = raw.rstrip()
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            print(out.role("    " + line, "muted"))
            prev_blank = False
            continue
        if not line:
            if not prev_blank:
                print()
            prev_blank = True
            continue
        prev_blank = False
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level, txt = len(m.group(1)), m.group(2)
            if level == 1:
                print(out.role(txt, "warn", bold=True))
                print(out.role("─" * min(len(txt), 60), "muted"))
            elif level == 2:
                print(out.c(txt, out.BOLD))
            else:
                print(out.role(txt, "muted", bold=True))
            continue
        m = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m:
            print("%s • %s" % (m.group(1), _inline(m.group(2))))
            continue
        print(_inline(line))


def cmd_preview(argv):
    ap = cliparse.parser(prog="boost preview",
                                 description="Render a SKILL.md with rich formatting")
    ap.add_argument("name")
    args = ap.parse_args(argv)
    text, _kind, lock, cat = _resolve_text(args.name)
    meta, body = frontmatter.parse(text)
    print(out.titlebar("%s · v%s · %s" % (meta.get("name") or args.name,
                                          meta.get("version") or "?",
                                          (lock or cat or {}).get("tap", "local"))))
    print()
    _render_markdown(body)
    return 0


_FAITHFULNESS_MIN_KEY = "ai.explain_faithfulness_min"
_FAITHFULNESS_DEFAULT = 0.5


def _faithfulness_threshold() -> float:
    """The minimum faithfulness score an AI explanation must clear (config-tunable).

    Clamped to [0, 1]; a malformed config value falls back to the default rather
    than disabling the guardrail with, say, a negative threshold.
    """
    raw = config.get(_FAITHFULNESS_MIN_KEY, _FAITHFULNESS_DEFAULT)
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return _FAITHFULNESS_DEFAULT
    return min(1.0, max(0.0, val))


def _explanation_is_faithful(reply: str, source: str) -> bool:
    """True if ``reply`` is grounded enough in ``source`` to show as-is."""
    return faithfulness.score(reply, source) >= _faithfulness_threshold()


def cmd_explain(argv):
    ap = cliparse.parser(prog="boost explain",
                                 description="Explain what a skill does in plain English")
    ap.add_argument("name")
    args = ap.parse_args(argv)
    text, _kind, _lock, _cat = _resolve_text(args.name)
    if ai.available():
        reply = ai.ask(
            "Explain in plain English (4-6 sentences, no markdown) what this "
            "AI coding-agent skill makes the agent do differently and when it "
            "triggers:\n\n" + text,
            system="You summarize agent skills for developers. Be concrete and brief.")
        if reply and _explanation_is_faithful(reply, text):
            _print_wrapped(reply)
            return 0
        if reply:
            # The model answered, but the summary named specifics the SKILL.md
            # never does — the shape of a fabricated capability. Refuse to show
            # it and fall through to the grounded extractive summary below.
            out.warn("AI explanation looked ungrounded (%s) — showing the "
                     "extractive summary instead"
                     % ", ".join(faithfulness.ungrounded_terms(reply, text)[:4]))
    else:
        out.warn(ai.fallback_note())
    meta, body = frontmatter.parse(text)
    desc = str(meta.get("description") or "").strip()
    if desc:
        _print_wrapped(desc)
    headings = re.findall(r"^(#{1,6})\s+(.*)$", body, re.MULTILINE)
    if headings:
        print()
        out.info(out.c("Outline:", out.BOLD))
        for hashes, title in headings:
            out.info("  " * len(hashes) + title)
    rules, seen = [], set()
    for line in body.splitlines():
        stripped = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", line).strip()
        if not stripped or stripped in seen:
            continue
        is_bullet = bool(re.match(r"^\s*(?:[-*]|\d+\.)\s", line))
        if (imperative.RULE_RE.match(stripped)
                or (is_bullet and re.search(r"(?i)\b(always|never)\b", stripped))):
            seen.add(stripped)
            rules.append(stripped)
    if rules:
        print()
        out.info(out.c("Key rules:", out.BOLD))
        for rule in rules[:12]:
            out.info("  • " + rule)
    return 0


def _diag_line(line: str) -> str:
    """Render one stored log line for display, whether it is text or JSON.

    ``BOOST_LOG_FORMAT=json`` makes the file JSONL, which is the point — but
    this command is the *human* view of that same file, and raw JSONL is not
    it. Anything that is not a boost log object passes through untouched, so a
    file whose format changed mid-life still reads end to end.
    """
    if not line.startswith("{"):
        return line
    try:
        rec = json.loads(line)
    except ValueError:
        return line
    if not isinstance(rec, dict) or "msg" not in rec:
        return line
    return "%s %-7s %s: %s" % (rec.get("ts", ""), rec.get("level", ""),
                               rec.get("logger", ""), rec["msg"])


def _show_diagnostics(limit):
    lp = logs.log_path()
    if not lp.exists():
        out.info("no diagnostic log yet at %s" % lp)
        return 0
    lines = lp.read_text(encoding="utf-8", errors="replace").splitlines()
    out.heading("diagnostic log — %s" % lp)
    for line in lines[-limit:]:
        out.info(_diag_line(line))
    return 0


def _show_crashes(limit):
    ldir = paths.logs_dir()
    reports = sorted(ldir.glob("crash-*.log"), reverse=True) if ldir.is_dir() else []
    if not reports:
        out.info("no crash reports — nothing has blown up (that boost noticed)")
        return 0
    out.heading("crash reports in %s" % ldir)
    for r in reports[:limit]:
        try:
            first = r.read_text(encoding="utf-8", errors="replace").splitlines()
            summary = next((ln for ln in first if ln.startswith("command:")), "")
        except OSError:
            summary = ""
        out.info("%s  %s" % (r.name, summary))
    out.info("")
    out.dim("  view one with:  cat %s/<name>" % ldir)
    return 0


def cmd_log(argv):
    ap = cliparse.parser(prog="boost log",
                                 description="Git log for a skill, or boost's activity log")
    ap.add_argument("name", nargs="?", help="skill to show upstream history for")
    ap.add_argument("-n", "--limit", type=util.positive_int, default=20, metavar="N",
                    help="max entries (default 20)")
    ap.add_argument("--diagnostics", action="store_true",
                    help="show boost's diagnostic log trail (not skill history)")
    ap.add_argument("--crashes", action="store_true",
                    help="list recent crash reports")
    args = ap.parse_args(argv)
    if args.crashes:
        return _show_crashes(args.limit)
    if args.diagnostics:
        return _show_diagnostics(args.limit)
    if args.name:
        found = lockfile.find_any(args.name)
        if found:
            # A skill records its source dir; rules/workflows record a source
            # file — either is a path git can log for.
            lock = found[1]
            tap_name = lock.get("tap", "local")
            rel = lock.get("source_dir") or lock.get("source_file") or "."
        else:
            entry = catalog.resolve_one(args.name)
            tap_name, rel = entry["tap"], entry["rel_dir"]
        try:
            tap = registry.get(tap_name)
        except BoostError:
            out.info("no upstream history (imported locally)")
            return 0
        if not tap.is_cloned:
            raise BoostError("tap %s is not cloned" % tap.name,
                            hint="run `boost update %s`" % tap.name)
        lines = gitutil.log_for_path(tap.path, rel, args.limit)
        if not lines:
            out.info("no commits touch %s in %s" % (args.name, tap.name))
            return 0
        out.heading("%s — history in %s" % (args.name, tap.name))
        for line in lines:
            out.info(line)
        return 0
    events = journal.events(args.limit)
    if not events:
        out.info("no activity yet")
        return 0
    action_roles = {"install": "success", "uninstall": "danger"}
    w_time = max(len(util.rel_time(e.get("ts", ""))) for e in events)
    w_user = max(len(e.get("user", "?")) for e in events)
    for e in events:
        action = e.get("action", "?")
        out.info(("%s  %s  %s %s" % (
            util.rel_time(e.get("ts", "")).ljust(w_time),
            e.get("user", "?").ljust(w_user),
            out.role(action, action_roles.get(action, "accent")),
            e.get("subject", ""))).rstrip())
    return 0


def cmd_home(argv):
    ap = cliparse.parser(prog="boost home",
                                 description="Open a skill's GitHub page in the browser")
    ap.add_argument("name")
    ap.add_argument("--print", dest="print_only", action="store_true",
                    help="print the URL without opening a browser")
    args = ap.parse_args(argv)
    found = lockfile.find_any(args.name)
    lock = found[1] if found else None
    try:
        entry = catalog.resolve_one(args.name)
        tap_name, rel = entry["tap"], entry["rel_dir"]
    except BoostError:
        if not lock:
            raise
        tap_name = lock.get("tap", "local")
        rel = lock.get("source_dir") or lock.get("source_file") or "."
    try:
        tap = registry.get(tap_name)
    except BoostError:
        out.info(_tilde(rel))   # local import — only a path to show
        return 0
    if not tap.url.startswith(("http://", "https://")):
        out.info(_tilde(Path(tap.url) if rel == "." else Path(tap.url) / rel))
        return 0
    url = tap.url.rstrip("/") + ("" if rel == "." else "/tree/HEAD/" + rel)
    out.info(url)
    if not args.print_only and sys.stdout.isatty():
        webbrowser.open(url)
    return 0


def cmd_deps(argv):
    ap = cliparse.parser(prog="boost deps",
                                 description="Show dependency & conflict relationships")
    ap.add_argument("name", nargs="?", help="skill to inspect (default: check all installed)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    inst = lockfile.installed()
    # `requires:`/`conflicts:` name an installed item, not a kind — a
    # requirement met by an installed rule or workflow is met, and denying it
    # ("✗ not installed" while `boost list` shows it) was the section-blind lie.
    have = set(chain.from_iterable(lockfile.all_installed().values()))

    if args.name:
        text, _kind, _lock, _cat = _resolve_text(args.name)
        meta = frontmatter.parse(text)[0]
        requires = _as_list(meta.get("requires"))
        conflicts = _as_list(meta.get("conflicts"))
        problems = (any(r not in have for r in requires)
                    or any(c in have for c in conflicts))
        if args.json:
            print(json.dumps({
                "name": args.name,
                "requires": [{"name": r, "installed": r in have,
                              "requires": _as_list((_skill_meta(r) or {}).get("requires"))}
                             for r in requires],
                "conflicts": [{"name": c, "installed": c in have} for c in conflicts],
            }, indent=2))
            return 1 if problems else 0
        out.info(out.c(args.name, out.BOLD))
        if not requires:
            out.info("  requires: " + out.role("(none)", "muted"))
        for r in requires:
            out.info("  requires: %s %s" % (r, _mark(r in have)))
            for sub in _as_list((_skill_meta(r) or {}).get("requires")):
                out.info("      ↳ %s %s" % (sub, _mark(sub in have)))
        if not conflicts:
            out.info("  conflicts: " + out.role("(none)", "muted"))
        for c_name in conflicts:
            state = (out.role("✗ installed (conflict!)", "danger") if c_name in have
                     else out.role("not installed", "muted"))
            out.info("  conflicts: %s %s" % (c_name, state))
        return 1 if problems else 0

    unmet: list[dict] = []
    pairs: list[list] = []   # JSON-dumped, so lists rather than tuples
    seen: set = set()
    for name in sorted(inst):
        meta = _skill_meta(name) or {}
        unmet.extend(
            {"skill": name, "requires": r}
            for r in _as_list(meta.get("requires"))
            if r not in have
        )
        for c_name in _as_list(meta.get("conflicts")):
            if c_name in have:
                key = tuple(sorted((name, c_name)))
                if key not in seen:
                    seen.add(key)
                    pairs.append(list(key))
    if args.json:
        print(json.dumps({"unmet": unmet, "conflicts": pairs}, indent=2))
        return 1 if unmet or pairs else 0
    if not inst:
        out.info("no skills installed")
        return 0
    for u in unmet:
        out.info("%s requires %s %s"
                 % (out.c(u["skill"], out.BOLD), u["requires"], _mark(False)))
    for a, b in pairs:
        out.info("%s %s %s" % (out.c(a, out.BOLD),
                               out.role("conflicts with", "danger"), out.c(b, out.BOLD)))
    if not unmet and not pairs:
        out.ok("no unmet requirements or conflicts across %d skill%s"
               % (len(inst), "" if len(inst) == 1 else "s"))
        return 0
    return 1


def cmd_tag(argv):
    ap = cliparse.parser(prog="boost tag",
                                 description="Custom labels for organizing skills")
    ap.add_argument("--list", dest="list_all", action="store_true",
                    help="show every tag and the skills carrying it")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("name", nargs="?", help="installed skill")
    ap.add_argument("mods", nargs="*", help="+tag to add, -tag to remove")
    # A `-tag` removal looks like an option to argparse, which forced the old
    # parse_known_args + argv re-walk. Instead split the literal option strings
    # from operands ourselves: the skill name and its +tag/-tag operands keep
    # their exact argv order with no re-walk, so `-x +x` still nets differently
    # from `+x -x`.
    flag_strings = {"--list", "--json", "-h", "--help"}
    flags = [t for t in argv if t in flag_strings]
    operands = [t for t in argv if t not in flag_strings]
    args = ap.parse_args(flags)
    args.name = operands[0] if operands else None
    mods = operands[1:]

    if args.list_all:
        mapping: dict[str, list[str]] = {}
        for name, e in sorted(lockfile.installed().items()):
            for t in e.get("tags") or []:
                mapping.setdefault(t, []).append(name)
        if args.json:
            print(json.dumps(mapping, indent=2, sort_keys=True))
            return 0
        if not mapping:
            out.info("no tags yet")
            out.info(out.role("hint: boost tag <skill> +mytag", "muted"))
            return 0
        out.table([("#" + t, ", ".join(mapping[t])) for t in sorted(mapping)],
                  headers=("TAG", "SKILLS"))
        return 0

    if not args.name:
        raise BoostError("skill name required",
                        hint="`boost tag NAME +tag -tag`, or `boost tag --list`")
    entry = lockfile.get_skill(args.name)
    if not entry:
        found = lockfile.find_any(args.name)
        if found is not None:
            raise BoostError(
                "%s is a %s — boost tag applies to skills"
                % (args.name, found[0]),
                hint="tags are a skill-only label; rules and workflows are "
                     "governed by pin / quarantine / verify")
        raise BoostError("%s is not installed" % args.name,
                        hint="see what is with `boost list`")
    tags = list(entry.get("tags") or [])
    changed = False
    for tok in mods:
        if not tok or tok[0] not in "+-":
            raise BoostError("cannot parse %r" % tok,
                            hint="prefix tags with + to add or - to remove")
        t = tok[1:].lstrip("#").strip()
        if not t:
            raise BoostError("empty tag in %r" % tok)
        if tok[0] == "+" and t not in tags:
            tags.append(t)
            changed = True
        elif tok[0] == "-" and t in tags:
            tags.remove(t)
            changed = True
    if changed:
        entry["tags"] = sorted(tags)
        tags = entry["tags"]
        lockfile.set_skill(args.name, entry)
        journal.log("tag", args.name, tags=tags)
    if args.json:
        print(json.dumps({"name": args.name, "tags": tags}, indent=2))
        return 0
    shown = " ".join(out.role("#" + t, "accent") for t in tags) or out.role("(no tags)", "muted")
    (out.ok if changed else out.info)("%s  %s" % (args.name, shown))
    return 0
