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
from pathlib import Path

from .. import cliparse
from ..core import ai, catalog, frontmatter, gitutil, journal, lockfile, logs, paths, registry, store, util
from ..core import output as out
from ..errors import BoostError


# ---------------------------------------------------------------- helpers

def _tilde(p) -> str:
    """Show a path with $HOME contracted to ~."""
    s, h = str(p), str(paths.home())
    if s == h:
        return "~"
    if s.startswith(h + os.sep):
        return "~" + s[len(h):]
    return s


def _read(p: Path) -> str:
    try:
        return Path(p).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise BoostError("cannot read %s: %s" % (_tilde(p), e))


def _resolve_skill_md(name: str):
    """Locate a skill's SKILL.md — installed store first, then tap clones.

    Returns (path, lock_entry_or_None, catalog_entry_or_None).
    """
    lock = lockfile.get_skill(name)
    if lock:
        p = store.skill_store_dir(name) / "SKILL.md"
        if p.exists():
            return p, lock, None
    entry = catalog.resolve_one(name)
    return registry.get(entry["tap"]).path / entry["skill_md"], lock, entry


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
    return (out.c("✓ installed", out.GREEN) if installed
            else out.c("✗ not installed", out.RED))


def _print_wrapped(text: str) -> None:
    paras = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    for i, para in enumerate(paras):
        for line in textwrap.wrap(" ".join(para.split()), width=76):
            out.info(line)
        if i < len(paras) - 1:
            print()


# ---------------------------------------------------------------- commands

def cmd_list(argv):
    ap = cliparse.parser(prog="boost list",
                                 description="List installed skills")
    ap.add_argument("--tag", help="only show skills carrying this tag")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    skills = lockfile.installed()
    if args.tag:
        want = args.tag.lstrip("#")
        skills = {n: e for n, e in skills.items() if want in (e.get("tags") or [])}
    if args.json:
        print(json.dumps(skills, indent=2, sort_keys=True))
        return 0
    if not skills:
        print(out.empty_state(
            "no skills installed"
            + (" with tag #%s" % args.tag.lstrip("#") if args.tag else ""),
            hint="boost tap --defaults && boost search <topic>"))
        return 0
    out.heading("installed skills")
    rows = []
    for name in sorted(skills):
        e = skills[name]
        # Aurora-tinted flags — now that table() aligns by visible width,
        # colored cells stay in their column: pinned amber, quarantined pink,
        # tags dim.
        flags = ([out.aurora("pinned", "yellow")] if e.get("pinned") else []) + \
                ([out.aurora("quarantined", "pink")] if e.get("quarantined")
                 else []) + \
                [out.c("#" + t, out.DIM) for t in e.get("tags") or []]
        rows.append((name, e.get("version", "?"), e.get("tap", "?"),
                     "·".join(a.split("-")[0] for a in e.get("agents") or []),
                     " ".join(flags)))
    out.table(rows, headers=("NAME", "VERSION", "TAP", "AGENTS", "FLAGS"))
    print("  " + out.aurora("%d skill%s installed"
                            % (len(rows), "" if len(rows) == 1 else "s"), "cyan"))
    return 0


def cmd_info(argv):
    ap = cliparse.parser(prog="boost info",
                                 description="Show detailed info about a skill")
    ap.add_argument("name")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    name = args.name
    lock = lockfile.get_skill(name)
    if lock:
        matches = catalog.find(name)
        same_tap = [e for e in matches if e["tap"] == lock.get("tap")]
        cat = (same_tap or matches or [None])[0]
    else:
        cat = catalog.resolve_one(name)   # raises if unknown anywhere

    sdir = store.skill_store_dir(name)
    skill_dir = sdir if lock and sdir.is_dir() else None
    if skill_dir is None and cat:
        try:
            skill_dir = store.source_dir_for(cat)
        except BoostError:
            skill_dir = None
    desc = str((cat or {}).get("description") or "")
    meta = {}
    if skill_dir and (skill_dir / "SKILL.md").exists():
        meta, _body = frontmatter.parse(_read(skill_dir / "SKILL.md"))
        desc = desc or str(meta.get("description") or "")
    score = size = files = None
    if skill_dir:
        score, _notes = util.score_skill(skill_dir)
        size, files = util.dir_size(skill_dir), _file_count(skill_dir)

    if args.json:
        print(json.dumps({
            "name": name, "description": desc,
            "installed": lock, "latest": (cat or {}).get("version"),
            "tap": (lock or cat or {}).get("tap"),
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
            out.kv("latest", out.c(latest, out.YELLOW, out.BOLD)
                   + out.c("  (update available)", out.DIM))
    else:
        out.kv("latest", str(cat.get("version", "?")))
    out.kv("tap", (lock or cat).get("tap", "?"))
    if lock and sdir.is_dir():
        out.kv("store", _tilde(sdir))
    src = lock.get("source_dir") if lock else cat.get("rel_dir")
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
    if score is not None:
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
    path, _lock, _cat = _resolve_skill_md(args.name)
    text = _read(path)
    if args.raw or not sys.stdout.isatty():
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
        return 0
    block, body = frontmatter.split(text)
    if block:
        print(out.c("---", out.DIM))
        for line in block.splitlines():
            print(out.c(line, out.DIM))
        print(out.c("---", out.DIM))
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
        rc = subprocess.call(cmd + [str(path)])
    except OSError as e:
        raise BoostError("cannot launch editor %r: %s" % (editor, e),
                        hint="set $VISUAL or $EDITOR to a valid command")
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
    s = re.sub(r"`([^`]+)`", lambda m: out.c(m.group(1), out.CYAN), s)
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
            print(out.c("    " + line, out.DIM))
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
                print(out.c(txt, out.BOLD, out.YELLOW))
                print(out.c("─" * min(len(txt), 60), out.DIM))
            elif level == 2:
                print(out.c(txt, out.BOLD))
            else:
                print(out.c(txt, out.BOLD, out.DIM))
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
    path, lock, cat = _resolve_skill_md(args.name)
    meta, body = frontmatter.parse(_read(path))
    print(out.titlebar("%s · v%s · %s" % (meta.get("name") or args.name,
                                          meta.get("version") or "?",
                                          (lock or cat or {}).get("tap", "local"))))
    print()
    _render_markdown(body)
    return 0


def cmd_explain(argv):
    ap = cliparse.parser(prog="boost explain",
                                 description="Explain what a skill does in plain English")
    ap.add_argument("name")
    args = ap.parse_args(argv)
    path, _lock, _cat = _resolve_skill_md(args.name)
    text = _read(path)
    if ai.available():
        reply = ai.ask(
            "Explain in plain English (4-6 sentences, no markdown) what this "
            "AI coding-agent skill makes the agent do differently and when it "
            "triggers:\n\n" + text,
            system="You summarize agent skills for developers. Be concrete and brief.")
        if reply:
            _print_wrapped(reply)
            return 0
    out.warn(ai.fallback_note())
    meta, body = frontmatter.parse(text)
    desc = str(meta.get("description") or "").strip()
    if desc:
        _print_wrapped(desc)
    headings = re.findall(r"^(#{1,6})\s+(.*)$", body, re.M)
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
        if (re.match(r"(?i)^(always|never|must|do not)\b", stripped)
                or (is_bullet and re.search(r"(?i)\b(always|never)\b", stripped))):
            seen.add(stripped)
            rules.append(stripped)
    if rules:
        print()
        out.info(out.c("Key rules:", out.BOLD))
        for rule in rules[:12]:
            out.info("  • " + rule)
    return 0


def _show_diagnostics(limit):
    lp = logs.log_path()
    if not lp.exists():
        out.info("no diagnostic log yet at %s" % lp)
        return 0
    lines = lp.read_text(encoding="utf-8", errors="replace").splitlines()
    out.heading("diagnostic log — %s" % lp)
    for line in lines[-limit:]:
        out.info(line)
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
    ap.add_argument("-n", "--limit", type=int, default=20, metavar="N",
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
        lock = lockfile.get_skill(args.name)
        if lock:
            tap_name, rel = lock.get("tap", "local"), lock.get("source_dir", ".")
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
    colors = {"install": out.GREEN, "uninstall": out.RED}
    w_time = max(len(util.rel_time(e.get("ts", ""))) for e in events)
    w_user = max(len(e.get("user", "?")) for e in events)
    for e in events:
        action = e.get("action", "?")
        out.info(("%s  %s  %s %s" % (
            util.rel_time(e.get("ts", "")).ljust(w_time),
            e.get("user", "?").ljust(w_user),
            out.c(action, colors.get(action, out.CYAN)),
            e.get("subject", ""))).rstrip())
    return 0


def cmd_home(argv):
    ap = cliparse.parser(prog="boost home",
                                 description="Open a skill's GitHub page in the browser")
    ap.add_argument("name")
    ap.add_argument("--print", dest="print_only", action="store_true",
                    help="print the URL without opening a browser")
    args = ap.parse_args(argv)
    lock = lockfile.get_skill(args.name)
    try:
        entry = catalog.resolve_one(args.name)
        tap_name, rel = entry["tap"], entry["rel_dir"]
    except BoostError:
        if not lock:
            raise
        tap_name, rel = lock.get("tap", "local"), lock.get("source_dir", ".")
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

    if args.name:
        path, _lock, _cat = _resolve_skill_md(args.name)
        meta = frontmatter.parse(_read(path))[0]
        requires = _as_list(meta.get("requires"))
        conflicts = _as_list(meta.get("conflicts"))
        problems = (any(r not in inst for r in requires)
                    or any(c in inst for c in conflicts))
        if args.json:
            print(json.dumps({
                "name": args.name,
                "requires": [{"name": r, "installed": r in inst,
                              "requires": _as_list((_skill_meta(r) or {}).get("requires"))}
                             for r in requires],
                "conflicts": [{"name": c, "installed": c in inst} for c in conflicts],
            }, indent=2))
            return 1 if problems else 0
        out.info(out.c(args.name, out.BOLD))
        if not requires:
            out.info("  requires: " + out.c("(none)", out.DIM))
        for r in requires:
            out.info("  requires: %s %s" % (r, _mark(r in inst)))
            for sub in _as_list((_skill_meta(r) or {}).get("requires")):
                out.info("      ↳ %s %s" % (sub, _mark(sub in inst)))
        if not conflicts:
            out.info("  conflicts: " + out.c("(none)", out.DIM))
        for c_name in conflicts:
            state = (out.c("✗ installed (conflict!)", out.RED) if c_name in inst
                     else out.c("not installed", out.DIM))
            out.info("  conflicts: %s %s" % (c_name, state))
        return 1 if problems else 0

    unmet, pairs, seen = [], [], set()
    for name in sorted(inst):
        meta = _skill_meta(name) or {}
        for r in _as_list(meta.get("requires")):
            if r not in inst:
                unmet.append({"skill": name, "requires": r})
        for c_name in _as_list(meta.get("conflicts")):
            if c_name in inst:
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
                               out.c("conflicts with", out.RED), out.c(b, out.BOLD)))
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
    args, extras = ap.parse_known_args(argv)
    # '-tag' tokens land in extras; re-order the combined pool to match the
    # user's original argv so `-x +x` nets differently from `+x -x`.
    remaining = list(args.mods) + extras
    mods = []
    for tok in argv:
        if tok in remaining:
            mods.append(tok)
            remaining.remove(tok)
    mods += remaining   # anything unmatched keeps parse order (defensive)

    if args.list_all:
        mapping = {}
        for name, e in sorted(lockfile.installed().items()):
            for t in e.get("tags") or []:
                mapping.setdefault(t, []).append(name)
        if args.json:
            print(json.dumps(mapping, indent=2, sort_keys=True))
            return 0
        if not mapping:
            out.info("no tags yet")
            out.info(out.c("hint: boost tag <skill> +mytag", out.DIM))
            return 0
        out.table([("#" + t, ", ".join(mapping[t])) for t in sorted(mapping)],
                  headers=("TAG", "SKILLS"))
        return 0

    if not args.name:
        raise BoostError("skill name required",
                        hint="`boost tag NAME +tag -tag`, or `boost tag --list`")
    entry = lockfile.get_skill(args.name)
    if not entry:
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
    shown = " ".join(out.c("#" + t, out.CYAN) for t in tags) or out.c("(no tags)", out.DIM)
    (out.ok if changed else out.info)("%s  %s" % (args.name, shown))
    return 0
