"""Intelligence commands: distill, simulate, infer, absorb, evolve,
context, focus, impact.

Every command works without AI via honest heuristics (a single warning
notes the fallback); when the AI bridge is available the results get
qualitatively better. Session state lives in ~/.boost/state/.
"""
from __future__ import annotations

import contextlib
import difflib
import fnmatch
import json
import re
import tempfile
import textwrap
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple

from .. import cliparse
from ..core import (
    ai,
    catalog,
    frontmatter,
    gitutil,
    imperative,
    journal,
    lockfile,
    paths,
    registry,
    store,
    util,
)
from ..core import (
    chat as chat_engine,
)
from ..core import output as out
from ..errors import BoostError

# ---------------------------------------------------------------- helpers

_warned_fallback = False


def _note_fallback() -> None:
    """Warn once per invocation that the AI path is unavailable."""
    global _warned_fallback
    if not _warned_fallback:
        out.warn(ai.fallback_note())
        _warned_fallback = True


_tilde = paths.tilde


def _skill_text(name: str) -> Tuple[str, str]:
    """A skill's SKILL.md text -> (text, origin). Installed store preferred."""
    if lockfile.get_skill(name):
        p = store.skill_store_dir(name) / "SKILL.md"
        if p.exists():
            return p.read_text(encoding="utf-8", errors="replace"), "installed"
    entry = catalog.resolve_one(name)
    p = store.source_dir_for(entry) / "SKILL.md"
    return p.read_text(encoding="utf-8", errors="replace"), "tap %s" % entry["tap"]


def _bump_patch(v: str) -> str:
    major, minor, patch = util.semver_tuple(v)
    return "%d.%d.%d" % (major, minor, patch + 1)


def _load_state(fname: str, default: dict) -> dict:
    p = paths.state_dir() / fname
    if not p.exists():
        return json.loads(json.dumps(default))
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return json.loads(json.dumps(default))


def _save_state(fname: str, data: dict) -> None:
    paths.ensure_dirs()
    (paths.state_dir() / fname).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _install_generated(name: str, text: str) -> None:
    """Write a generated SKILL.md to a tempdir and install it as `name`.

    The tempdir is the only copy of a just-generated skill, so a refused install
    must not be allowed to propagate out of the ``with`` block and delete it —
    that would discard an LLM generation the user paid for, with nothing on disk
    to recover. On a refusal, save it beside the cwd and say where it went.
    """
    with tempfile.TemporaryDirectory(prefix="boost-gen-") as td:
        src = Path(td) / name
        src.mkdir()
        (src / "SKILL.md").write_text(text, encoding="utf-8")
        try:
            res = store.install_from_path(src, name=name, tap_label="local")
        except BoostError as err:
            fallback = Path.cwd() / ("%s.SKILL.md" % name)
            fallback.write_text(text, encoding="utf-8")
            out.warn("not installed: %s" % err.message)
            out.info("generated skill saved to %s" % _tilde(fallback))
            return
    out.ok("installed %s → %s" % (name, _tilde(res.dest)))
    if res.linked:
        out.info(out.role("linked into: %s" % ", ".join(res.linked), "muted"))


def _write_generated(dest: Path, text: str) -> bool:
    """Write a generated file, confirming before overwriting. False = declined."""
    if dest.exists() and not out.confirm("overwrite %s?" % _tilde(dest)):
        out.info("aborted — %s left untouched" % _tilde(dest))
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    out.ok("wrote %s" % _tilde(dest))
    return True


def _current_branch(cwd: Optional[Path] = None) -> Optional[str]:
    """Current git branch of cwd, or None when not in a repo / no git."""
    if not gitutil.has_git():
        return None
    proc = gitutil.run(["rev-parse", "--abbrev-ref", "HEAD"],
                       cwd=cwd or Path.cwd(), check=False)
    return proc.stdout.strip() if proc.returncode == 0 else None


# ---------------------------------------------------------------- distill

def cmd_distill(argv: List[str]) -> int:
    ap = cliparse.parser(
        prog="boost distill",
        description="Merge multiple skills into one deduplicated skill")
    ap.add_argument("names", nargs="+", metavar="NAME",
                    help="two or more skills to merge")
    ap.add_argument("-o", "--output", metavar="NEWNAME",
                    help="name for the merged skill (default: <first>-distilled)")
    ap.add_argument("--install", action="store_true",
                    help="install the merged skill instead of writing a file")
    args = ap.parse_args(argv)

    names = list(dict.fromkeys(args.names))
    if len(names) < 2:
        raise BoostError("distill needs at least two distinct skills",
                        hint="e.g. `boost distill tdd-workflow commit-messages`")
    sources = []
    for name in names:
        text, origin = _skill_text(name)
        meta, body = frontmatter.parse(text)
        sources.append({"name": name, "origin": origin, "text": text,
                        "meta": meta, "body": body})
    new = args.output or (names[0] + "-distilled")

    out.heading("distilling %s → %s" % (", ".join(names), new))
    merged = _distill_ai(new, sources) if ai.available() else None
    if merged is None:
        _note_fallback()
        merged = _distill_merge(new, sources)

    if args.install:
        _install_generated(new, merged)
    else:
        dest = Path.cwd() / new / "SKILL.md"
        if not _write_generated(dest, merged):
            return 1
        out.info(out.role("install it with `boost import ./%s`" % new, "muted"))
    journal.log("distill", new, sources=names)
    return 0


def _distill_ai(new: str, sources: List[dict]) -> Optional[str]:
    blocks = "\n\n".join("### SOURCE SKILL: %s\n\n%s" % (s["name"], s["text"])
                         for s in sources)
    reply = ai.ask_author(
        "Merge the following %d skills into ONE skill file.\n"
        "Requirements:\n"
        "- YAML frontmatter with name: %s, a one-line description, "
        "version: 1.0.0, and the union of the source tags\n"
        "- a deduplicated body: keep every distinct rule exactly once under "
        "clear headings, drop redundant or contradictory duplicates\n\n%s"
        % (len(sources), new, blocks),
        system="You are an expert author of SKILL.md files for AI coding "
               "agents. Reply with ONLY the complete merged SKILL.md content.")
    if not reply:
        return None
    text = ai.extract_markdown(reply)
    meta, _ = frontmatter.parse(text)
    return text if meta.get("name") else None


def _distill_merge(new: str, sources: List[dict]) -> str:
    """Mechanical merge: union tags, dedupe exact-duplicate body lines."""
    tags: List[str] = []
    for s in sources:
        for t in s["meta"].get("tags") or []:
            if t not in tags:
                tags.append(t)
    desc = next((str(s["meta"].get("description") or "").strip()
                 for s in sources if s["meta"].get("description")), "")
    meta: dict = {"name": new,
            "description": (desc or "Merged skill") + " (distilled)",
            "version": "1.0.0"}
    if tags:
        meta["tags"] = tags
    seen = set()
    sections = ["# %s\n\nDistilled from: %s."
                % (new, ", ".join(s["name"] for s in sources))]
    for s in sources:
        kept = []
        for raw in s["body"].splitlines():
            key = raw.strip()
            if key:
                if key in seen:
                    continue
                seen.add(key)
            kept.append(raw)
        sections.append("## From %s\n\n%s" % (s["name"], "\n".join(kept).strip()))
    body = re.sub(r"\n{3,}", "\n\n", "\n\n".join(sections))
    return frontmatter.dump(meta) + "\n\n" + body.strip() + "\n"


# ---------------------------------------------------------------- simulate


def cmd_simulate(argv: List[str]) -> int:
    ap = cliparse.parser(
        prog="boost simulate",
        description="Preview how a skill would change Claude's behavior")
    ap.add_argument("name", metavar="NAME")
    ap.add_argument("--task", metavar="TEXT",
                    help="task to simulate (default: a typical coding task)")
    args = ap.parse_args(argv)

    text, origin = _skill_text(args.name)
    task = args.task or "a typical coding task in this repo"
    out.heading("simulating %s  %s" % (args.name, out.role("(%s)" % origin, "muted")))

    if ai.available():
        reply = ai.ask(
            "Here is a skill file that changes how an AI coding agent "
            "behaves:\n\n%s\n\nTask: %s\n\nIn at most 6 bullets total, "
            "contrast the agent's behavior WITHOUT this skill vs WITH this "
            "skill on that task. Be concrete and terse." % (text, task))
        if reply:
            for line in reply.splitlines():
                out.info(line)
            return 0
    _note_fallback()

    meta, body = frontmatter.parse(text)
    out.kv("task", task)
    rules = imperative.imperative_rules(body)
    out.info("Without it: default behavior — none of the rules below are enforced.")
    out.info(out.c("With %s active, Claude would:" % args.name, out.BOLD))
    if rules:
        for rule in rules[:8]:
            out.info("  • " + rule)
        if len(rules) > 8:
            out.info(out.role("  … and %d more rules" % (len(rules) - 8), "muted"))
    else:
        out.info("  • (no imperative rules found in the skill body)")
    desc = str(meta.get("description") or "").strip()
    if desc:
        out.info(out.role('likely triggers when the task involves: "%s"'
                       % desc[:100], "muted"))
    return 0


# ---------------------------------------------------------------- infer

_CONV_RE = re.compile(
    r"^(feat|fix|chore|docs|refactor|test|style|perf|build|ci|revert)"
    r"(\(.+?\))?!?:\s")


def cmd_infer(argv: List[str]) -> int:
    ap = cliparse.parser(
        prog="boost infer",
        description="Generate a SKILL.md from your codebase patterns")
    ap.add_argument("--path", default=".", metavar="DIR",
                    help="codebase to analyze (default: current directory)")
    ap.add_argument("--name", default="project-conventions", metavar="N",
                    help="skill name (default: project-conventions)")
    ap.add_argument("-o", "--output", metavar="FILE", help="write to a file")
    ap.add_argument("--install", action="store_true",
                    help="install the generated skill")
    args = ap.parse_args(argv)

    root = paths.expand(args.path).resolve()
    if not root.is_dir():
        raise BoostError("%s is not a directory" % _tilde(root))
    name = util.slugify(args.name)
    facts = _probe_repo(root)

    text = _infer_ai(name, root, facts) if ai.available() else None
    if text is None:
        _note_fallback()
        text = _infer_template(name, facts)

    if args.install:
        _install_generated(name, text)
        journal.log("infer", name, path=str(root))
    elif args.output:
        if not _write_generated(paths.expand(args.output), text):
            return 1
        journal.log("infer", name, path=str(root))
    else:
        print(text, end="" if text.endswith("\n") else "\n")
    return 0


def _probe_repo(root: Path) -> dict:
    languages, frameworks = _stack_from_discovery(root) or _local_stack(root)
    facts: dict = {
        "languages": languages,
        "frameworks": frameworks,
        "test_dirs": [d for d in ("tests", "test", "spec", "__tests__")
                      if (root / d).is_dir()],
        "formatters": _formatter_configs(root),
    }
    facts["commit_style"] = _commit_style(root)
    return facts


def _stack_from_discovery(root: Path) -> Optional[Tuple[List[str], List[str]]]:
    """Use discovery's shared stack prober when present; normalize its shape."""
    try:
        from ..core.stackprobe import detect_stack
        result = detect_stack(root)
    except Exception:
        return None

    def _names(val) -> List[str]:
        items = []
        for x in (val or []):
            n = x.get("name") if isinstance(x, dict) else x
            if n and str(n) not in items:
                items.append(str(n))
        return items

    if isinstance(result, dict):
        langs = _names(result.get("languages") or result.get("langs"))
        fws = _names(result.get("frameworks") or result.get("stack"))
    elif isinstance(result, (list, tuple, set)):
        langs, fws = _names(result), []
    else:
        return None
    return (langs, fws) if (langs or fws) else None


def _local_stack(root: Path) -> Tuple[List[str], List[str]]:
    langs: List[str] = []
    fws: List[str] = []

    def add(lst: List[str], item: str) -> None:
        if item not in lst:
            lst.append(item)

    def read(p: Path) -> str:
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    if (root / "package.json").exists():
        add(langs, "javascript")
        try:
            pkg = json.loads(read(root / "package.json") or "{}")
        except json.JSONDecodeError:
            pkg = {}
        deps: dict = {}
        for key in ("dependencies", "devDependencies"):
            deps.update(pkg.get(key) or {})
        for fw in ("react", "next", "vue", "svelte", "angular", "express"):
            if fw in deps:
                add(fws, fw)
        if "typescript" in deps or (root / "tsconfig.json").exists():
            add(langs, "typescript")
    if any((root / f).exists() for f in
           ("pyproject.toml", "requirements.txt", "setup.py")):
        add(langs, "python")
        blob = read(root / "pyproject.toml") + read(root / "requirements.txt")
        for fw in ("django", "flask", "fastapi", "pytest"):
            if fw in blob.lower():
                add(fws, fw)
    for marker, lang in (("Cargo.toml", "rust"), ("go.mod", "go"),
                         ("Gemfile", "ruby"), ("pom.xml", "java"),
                         ("build.gradle", "java"), ("composer.json", "php")):
        if (root / marker).exists():
            add(langs, lang)
    return langs, fws


def _formatter_configs(root: Path) -> List[str]:
    found: List[str] = []
    if (root / ".editorconfig").exists():
        found.append(".editorconfig")
    try:
        py = (root / "pyproject.toml").read_text(encoding="utf-8",
                                                 errors="replace")
    except OSError:
        py = ""
    if ((root / "ruff.toml").exists() or (root / ".ruff.toml").exists()
            or "[tool.ruff" in py):
        found.append("ruff")
    if "[tool.black" in py:
        found.append("black")
    if any((root / n).exists() for n in
           (".prettierrc", ".prettierrc.json", ".prettierrc.yaml",
            ".prettierrc.yml", ".prettierrc.js", "prettier.config.js")):
        found.append("prettier")
    if any((root / n).exists() for n in
           (".eslintrc", ".eslintrc.json", ".eslintrc.js", "eslint.config.js")):
        found.append("eslint")
    return found


def _commit_style(root: Path) -> Optional[Tuple[int, int]]:
    """(conventional, total) over the last 20 commit subjects, or None."""
    if not gitutil.has_git():
        return None
    proc = gitutil.run(["log", "-20", "--pretty=%s"], cwd=root, check=False)
    if proc.returncode != 0:
        return None
    subjects = [s for s in proc.stdout.splitlines() if s.strip()]
    if not subjects:
        return None
    return sum(1 for s in subjects if _CONV_RE.match(s)), len(subjects)


def _commit_rule(style: Tuple[int, int]) -> str:
    conv, total = style
    if conv / total >= 0.5:
        return ("Write Conventional Commits (`type(scope): subject`) — "
                "%d of the last %d subjects follow it." % (conv, total))
    return ("Commit subjects are freeform (%d/%d conventional); keep them "
            "short and imperative." % (conv, total))


def _infer_ai(name: str, root: Path, facts: dict) -> Optional[str]:
    listing = ", ".join(sorted(p.name for p in root.iterdir()
                               if not p.name.startswith("."))[:30])
    detected = facts.copy()
    if detected.get("commit_style"):
        detected["commit_style"] = _commit_rule(detected["commit_style"])
    reply = ai.ask_author(
        "Draft a SKILL.md that teaches an AI coding agent THIS repository's "
        "conventions. Detected facts (JSON): %s\nTop-level files: %s\n\n"
        "Requirements: YAML frontmatter with name: %s, description, "
        "version: 1.0.0; a body with concrete, imperative rules grounded in "
        "the detected facts only — do not invent tooling that is not listed."
        % (json.dumps(detected), listing, name),
        system="You are an expert author of SKILL.md files for AI coding "
               "agents. Reply with ONLY the complete SKILL.md content.")
    if not reply:
        return None
    text = ai.extract_markdown(reply)
    meta, _ = frontmatter.parse(text)
    return text if meta.get("name") else None


def _infer_template(name: str, facts: dict) -> str:
    desc = "Working conventions for this repository"
    if facts["languages"]:
        desc += " (%s)" % ", ".join(facts["languages"][:3])
    meta = {"name": name, "description": desc, "version": "1.0.0",
            "tags": ["conventions", "project"]}
    lines = ["# %s" % name.replace("-", " ").title(), "",
             "How to work in this repository. Generated by `boost infer` from",
             "detected project patterns — review before relying on it.", ""]
    if facts["languages"] or facts["frameworks"]:
        lines += ["## Stack", ""]
        if facts["languages"]:
            lines.append("- Languages: %s" % ", ".join(facts["languages"]))
        if facts["frameworks"]:
            lines.append("- Frameworks: %s" % ", ".join(facts["frameworks"]))
        lines.append("")
    if facts["test_dirs"]:
        lines += ["## Testing", "",
                  "- Tests live in %s — add new tests there and mirror the "
                  "source layout." % ", ".join("`%s/`" % d
                                               for d in facts["test_dirs"]),
                  ""]
    if facts["formatters"]:
        lines += ["## Formatting", "",
                  "- Respect the configured formatters: %s. Run them before "
                  "committing." % ", ".join(facts["formatters"]), ""]
    if facts["commit_style"]:
        lines += ["## Commits", "", "- " + _commit_rule(facts["commit_style"]), ""]
    if len(lines) <= 5:
        lines += ["## Conventions", "",
                  "- No strong conventions detected; edit this file with "
                  "your own rules.", ""]
    return frontmatter.dump(meta) + "\n\n" + "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------- absorb

_TRIVIAL = {"yes", "no", "ok", "okay", "continue", "go ahead", "sounds good",
            "thanks", "thank you", "sure", "yep", "do it", "looks good",
            "please continue", "try again"}


def cmd_absorb(argv: List[str]) -> int:
    ap = cliparse.parser(
        prog="boost absorb",
        description="Turn recurring chat-history patterns into a skill")
    ap.add_argument("--history", metavar="PATH",
                    help="history .jsonl file or directory of them")
    ap.add_argument("--limit", type=int, default=5, metavar="N",
                    help="max patterns to absorb (default: 5)")
    ap.add_argument("--install", action="store_true",
                    help="install the generated skill")
    args = ap.parse_args(argv)

    if args.history:
        src = paths.expand(args.history)
        if not src.exists():
            raise BoostError("no history at %s" % _tilde(src))
    else:
        src = paths.home() / ".claude" / "history.jsonl"
        if not src.exists():
            src = paths.home() / ".claude" / "projects"
        if not src.exists():
            out.info("no chat history found under ~/.claude — nothing to absorb")
            out.info(out.role("point at a .jsonl file or directory with "
                           "--history PATH", "muted"))
            return 0
    files = [src] if src.is_file() else sorted(src.rglob("*.jsonl"))
    if not files:
        out.info("no .jsonl history files under %s" % _tilde(src))
        return 0

    patterns = _recurring_patterns(files, args.limit)
    if not patterns:
        out.info("no recurring patterns in %d history file(s) — absorb needs "
                 "the same request 3+ times" % len(files))
        return 0

    name = "absorbed-patterns"
    out.heading("recurring patterns from %d history file(s)" % len(files))
    out.table([(p, "%dx" % n) for p, n in patterns],
              headers=("PATTERN", "SEEN"))
    print()

    text = _absorb_ai(name, patterns) if ai.available() else None
    if text is None:
        _note_fallback()
        text = _absorb_template(name, patterns)
    if args.install:
        _install_generated(name, text)
    else:
        print(text, end="" if text.endswith("\n") else "\n")
    return 0


def _recurring_patterns(files: List[Path], limit: int) -> List[Tuple[str, int]]:
    counts: Counter = Counter()
    for f in files:
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            for text in _user_texts(obj):
                for sent in _norm_sentences(text):
                    counts[sent] += 1
    hits = [(s, n) for s, n in counts.items()
            if n >= 3 and 4 <= len(s.split()) <= 30
            and len(s) >= 15 and s not in _TRIVIAL]
    hits.sort(key=lambda x: (-x[1], x[0]))
    return hits[:limit]


def _user_texts(obj) -> List[str]:
    """Best-effort user-message text from one history event."""
    if not isinstance(obj, dict):
        return []
    node = obj["message"] if isinstance(obj.get("message"), dict) else obj
    role = node.get("role") or node.get("type") or obj.get("type") or obj.get("role")
    if role != "user":
        return []
    content = node.get("content", obj.get("content"))
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        return [str(item.get("text") or "") for item in content
                if isinstance(item, dict) and item.get("type") == "text"]
    return []


def _norm_sentences(text: str) -> List[str]:
    sents = []
    for chunk in re.split(r"[.!?\n]+", text):
        s = re.sub(r"[^a-z0-9\s']", " ", chunk.lower())
        s = re.sub(r"\s+", " ", s).strip()
        if s:
            sents.append(s)
    return sents


def _absorb_ai(name: str, patterns: List[Tuple[str, int]]) -> Optional[str]:
    listing = "\n".join("- (seen %dx) %s" % (n, p) for p, n in patterns)
    reply = ai.ask_author(
        "These requests recur in a developer's AI chat history:\n%s\n\n"
        "Write ONE SKILL.md named %s that codifies them as standing rules "
        "so they never need to be repeated. YAML frontmatter with name, "
        "description, version: 1.0.0; body of concrete imperative rules."
        % (listing, name),
        system="You are an expert author of SKILL.md files for AI coding "
               "agents. Reply with ONLY the complete SKILL.md content.")
    if not reply:
        return None
    text = ai.extract_markdown(reply)
    meta, _ = frontmatter.parse(text)
    return text if meta.get("name") else None


def _absorb_template(name: str, patterns: List[Tuple[str, int]]) -> str:
    meta = {"name": name,
            "description": "Recurring instructions from your chat history, "
                           "codified as standing rules",
            "version": "1.0.0", "tags": ["habits", "workflow"]}
    body = ["# Absorbed Patterns", "",
            "These requests came up repeatedly in chat history (%d recurring "
            "patterns). Treat them as standing instructions:" % len(patterns),
            ""]
    body += ["- %s %s" % (p.capitalize() + ".", "(seen %dx)" % n)
             for p, n in patterns]
    return frontmatter.dump(meta) + "\n\n" + "\n".join(body) + "\n"


# ---------------------------------------------------------------- evolve

def cmd_evolve(argv: List[str]) -> int:
    ap = cliparse.parser(
        prog="boost evolve",
        description="Iteratively improve a skill from feedback")
    ap.add_argument("name", metavar="NAME")
    ap.add_argument("--feedback", required=True, metavar="TEXT",
                    help="what should change, in plain English")
    ap.add_argument("--apply", action="store_true",
                    help="write the revision to the installed skill")
    args = ap.parse_args(argv)

    entry = lockfile.get_skill(args.name)
    if not entry:
        raise BoostError("%s is not installed — evolve works on installed "
                        "skills" % args.name,
                        hint="install it first with `boost install %s`" % args.name)
    skill_md = store.skill_store_dir(args.name) / "SKILL.md"
    if not skill_md.exists():
        raise BoostError("%s has no SKILL.md in the store" % args.name,
                        hint="repair with `boost sync`")
    old = skill_md.read_text(encoding="utf-8", errors="replace")
    old_meta, _ = frontmatter.parse(old)
    old_ver = str(old_meta.get("version") or "0.0.0")

    out.heading("evolving %s  %s" % (args.name, out.role("(v%s)" % old_ver, "muted")))
    new = _evolve_ai(old, old_ver, args.feedback) if ai.available() else None
    if new is None:
        _note_fallback()
        new = _evolve_append(old, old_ver, args.feedback)
    _print_diff(old, new)
    new_meta, _ = frontmatter.parse(new)
    new_ver = str(new_meta.get("version") or old_ver)

    if not args.apply:
        out.info(out.role("re-run with --apply to write these changes", "muted"))
        return 0
    skill_md.write_text(new, encoding="utf-8")
    entry["sha256"] = util.sha256_dir(store.skill_store_dir(args.name))
    entry["updated_at"] = util.now_iso()
    entry["version"] = new_ver
    lockfile.set_skill(args.name, entry)
    journal.log("evolve", args.name, version=new_ver)
    out.ok("evolved %s → v%s" % (args.name, new_ver))
    return 0


def _evolve_ai(old: str, old_ver: str, feedback: str) -> Optional[str]:
    reply = ai.ask_author(
        "Revise this SKILL.md based on user feedback. Keep everything that "
        "still holds, integrate the feedback as concrete rules, and bump the "
        "patch version (current: %s).\n\nFEEDBACK: %s\n\nSKILL.md:\n\n%s"
        % (old_ver, feedback, old),
        system="You are an expert author of SKILL.md files for AI coding "
               "agents. Reply with ONLY the complete revised SKILL.md content.")
    if not reply:
        return None
    text = ai.extract_markdown(reply)
    meta, body = frontmatter.parse(text)
    if not meta.get("name"):
        return None
    if not util.semver_gt(str(meta.get("version") or ""), old_ver):
        meta["version"] = _bump_patch(old_ver)
        text = frontmatter.dump(meta) + "\n\n" + body.strip() + "\n"
    return text


def _evolve_append(old: str, old_ver: str, feedback: str) -> str:
    """Heuristic revision: feedback appended as a dated rules section."""
    meta, body = frontmatter.parse(old)
    meta["version"] = _bump_patch(old_ver)
    bullets = [s.strip().rstrip(".")
               for s in re.split(r"(?<=[.!?])\s+|\n+|;\s*", feedback)
               if s.strip()]
    section = ("## Feedback (%s)\n\n" % util.now_iso()[:10]
               + "\n".join("- %s." % b for b in bullets))
    return (frontmatter.dump(meta) + "\n\n" + body.strip()
            + "\n\n" + section + "\n")


def _print_diff(old: str, new: str) -> None:
    diff = difflib.unified_diff(old.splitlines(), new.splitlines(),
                                fromfile="a/SKILL.md", tofile="b/SKILL.md",
                                lineterm="")
    for line in diff:
        if line.startswith(("+++", "---")):
            print(out.c(line, out.BOLD))
        elif line.startswith("@@"):
            print(out.role(line, "accent"))
        elif line.startswith("+"):
            print(out.role(line, "success"))
        elif line.startswith("-"):
            print(out.role(line, "danger"))
        else:
            print(line)


# ---------------------------------------------------------------- context

_CONTEXT_STATE = "context.json"
_CONTEXT_DEFAULT = {"enabled": False, "rules": []}


def cmd_context(argv: List[str]) -> int:
    ap = cliparse.parser(
        prog="boost context", description="Branch-aware skill activation")
    sub = ap.add_subparsers(dest="action",
                            metavar="status|enable|disable|map|unmap|apply")
    sp = sub.add_parser("status", help="show rules, enabled flag & branch")
    sp.add_argument("--json", action="store_true")
    sub.add_parser("enable", help="turn on branch-aware activation (runs apply)")
    sub.add_parser("disable", help="turn it off and relink all mapped skills")
    sp = sub.add_parser("map", help="map a branch pattern to skills")
    sp.add_argument("pattern", help="fnmatch branch pattern, e.g. 'feature/*'")
    sp.add_argument("skills", help="comma-separated skill names")
    sp = sub.add_parser("unmap", help="remove a branch pattern rule")
    sp.add_argument("pattern")
    sub.add_parser("apply", help="link/unlink mapped skills for this branch")
    args = ap.parse_args(argv)

    state = _load_state(_CONTEXT_STATE, _CONTEXT_DEFAULT)
    action = args.action or "status"

    if action == "status":
        return _context_status(state, getattr(args, "json", False))
    if action == "map":
        skills = [s.strip() for s in args.skills.split(",") if s.strip()]
        if not skills:
            raise BoostError("no skills given",
                            hint="e.g. `boost context map 'feature/*' tdd-workflow`")
        missing = [s for s in skills if not lockfile.get_skill(s)]
        rules = [r for r in state["rules"] if r.get("pattern") != args.pattern]
        rules.append({"pattern": args.pattern, "skills": skills})
        state["rules"] = rules
        _save_state(_CONTEXT_STATE, state)
        journal.log("context", args.pattern, op="map", skills=skills)
        out.ok("mapped %s → %s" % (args.pattern, ", ".join(skills)))
        if missing:
            out.info(out.role("not installed yet: %s" % ", ".join(missing), "muted"))
        return 0
    if action == "unmap":
        rules = [r for r in state["rules"] if r.get("pattern") != args.pattern]
        if len(rules) == len(state["rules"]):
            raise BoostError("no rule for pattern %r" % args.pattern,
                            hint="see rules with `boost context status`")
        state["rules"] = rules
        _save_state(_CONTEXT_STATE, state)
        journal.log("context", args.pattern, op="unmap")
        out.ok("unmapped %s" % args.pattern)
        return 0
    if action == "enable":
        state["enabled"] = True
        _save_state(_CONTEXT_STATE, state)
        journal.log("context", "enable")
        out.ok("branch-aware activation enabled")
        if not state["rules"]:
            out.warn("no rules configured — add one with "
                     "`boost context map 'feature/*' skill1,skill2`")
            return 0
        return _context_apply(state)
    if action == "disable":
        restored = 0
        inst = lockfile.installed()
        for name in sorted(_mentioned_skills(state)):
            entry = inst.get(name)
            if entry and not entry.get("quarantined") and store.link_agents(name).linked:
                restored += 1
        state["enabled"] = False
        _save_state(_CONTEXT_STATE, state)
        journal.log("context", "disable", restored=restored)
        out.ok("branch-aware activation disabled — %d skill(s) relinked" % restored)
        return 0
    # apply
    if not state.get("enabled"):
        out.warn("context is disabled (`boost context enable`) — applying anyway")
    return _context_apply(state)


def _mentioned_skills(state: dict) -> set:
    return {s for r in state.get("rules", []) for s in r.get("skills", [])}


def _context_status(state: dict, as_json: bool) -> int:
    branch = _current_branch()
    if as_json:
        print(json.dumps({"enabled": bool(state.get("enabled")),
                          "branch": branch, "rules": state.get("rules", [])}))
        return 0
    out.heading("branch-aware skill activation")
    out.kv("enabled", "yes" if state.get("enabled") else "no")
    out.kv("branch", branch or "(not in a git repository)")
    rules = state.get("rules", [])
    if not rules:
        out.info("no rules — add one with `boost context map 'feature/*' skill1,skill2`")
        return 0
    rows = [(r.get("pattern", "?"), ", ".join(r.get("skills", [])),
             "*" if branch and fnmatch.fnmatch(branch, r.get("pattern", "")) else "")
            for r in rules]
    out.table(rows, headers=("PATTERN", "SKILLS", "MATCH"))
    return 0


def _context_apply(state: dict) -> int:
    branch = _current_branch()
    if branch is None:
        out.info("not inside a git repository — nothing to apply")
        return 0
    rules = state.get("rules", [])
    matched = [r for r in rules if fnmatch.fnmatch(branch, r.get("pattern", ""))]
    active = {s for r in matched for s in r.get("skills", [])}
    inst = lockfile.installed()
    linked, unlinked, missing = [], [], []
    for name in sorted(_mentioned_skills(state)):
        entry = inst.get(name)
        if not entry:
            missing.append(name)
            continue
        if entry.get("quarantined"):
            continue
        if name in active:
            if store.link_agents(name).linked:
                linked.append(name)
        elif store.unlink_agents(name):
            unlinked.append(name)
    out.kv("branch", branch)
    out.kv("matched", ", ".join(r["pattern"] for r in matched) or "(no patterns)")
    if linked:
        out.ok("active: " + ", ".join(linked))
    if unlinked:
        out.info("sidelined: " + ", ".join(unlinked))
    if not linked and not unlinked:
        out.info("nothing to change")
    if missing:
        out.info(out.role("mapped but not installed: %s" % ", ".join(missing), "muted"))
    if linked or unlinked:
        journal.log("context", branch, op="apply",
                    linked=linked or None, unlinked=unlinked or None)
    return 0


# ---------------------------------------------------------------- focus

_FOCUS_STATE = "focus.json"


def cmd_focus(argv: List[str]) -> int:
    ap = cliparse.parser(
        prog="boost focus",
        description="Temporarily prioritize skills for a work session")
    ap.add_argument("skills", nargs="*", metavar="SKILL",
                    help="skills to focus on")
    ap.add_argument("--clear", action="store_true",
                    help="end the session and relink everything")
    ap.add_argument("--status", action="store_true", help="show current focus")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    state_path = paths.state_dir() / _FOCUS_STATE
    if args.clear:
        if args.skills:
            raise BoostError("--clear takes no skill arguments")
        restored = 0
        for name, entry in sorted(lockfile.installed().items()):
            if entry.get("quarantined"):
                continue
            if store.link_agents(name).linked:
                restored += 1
        if state_path.exists():
            state_path.unlink()
        journal.log("focus", "clear", restored=restored)
        out.ok("focus cleared — %d skill(s) restored" % restored)
        return 0

    if args.status or not args.skills:
        state = _load_state(_FOCUS_STATE, {})
        if args.json:
            print(json.dumps({"active": state.get("active", []),
                              "since": state.get("since")}))
            return 0
        if state.get("active"):
            out.info("⌁ focus: %s  %s"
                     % (", ".join(state["active"]),
                        out.role("(since %s)" % util.rel_time(state.get("since", "")), "muted")))
            out.info(out.role("end it with `boost focus --clear`", "muted"))
        else:
            out.info("no focus session — start one with `boost focus SKILL...`")
        return 0

    names = list(dict.fromkeys(args.skills))
    inst = lockfile.installed()
    for name in names:
        entry = inst.get(name)
        if not entry:
            raise BoostError("%s is not installed — focus works on installed "
                            "skills" % name, hint="see `boost list`")
        if entry.get("quarantined"):
            raise BoostError("%s is quarantined" % name,
                            hint="release it first with `boost quarantine`")
    sidelined = 0
    for name, entry in sorted(inst.items()):
        if name in names or entry.get("quarantined"):
            continue
        if store.unlink_agents(name):
            sidelined += 1
    for name in names:
        store.link_agents(name)
    _save_state(_FOCUS_STATE, {"active": names, "since": util.now_iso()})
    journal.log("focus", ",".join(names))
    out.info("⌁ focus: %s %s"
             % (", ".join(names),
                out.role("(other %d skills sidelined)" % sidelined, "muted")))
    return 0


# ---------------------------------------------------------------- impact

def cmd_impact(argv: List[str]) -> int:
    ap = cliparse.parser(
        prog="boost impact",
        description="Measure a skill's influence on code quality")
    ap.add_argument("name", nargs="?", metavar="NAME",
                    help="one skill (default: all installed)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    inst = lockfile.installed()
    if args.name:
        if args.name not in inst:
            raise BoostError("%s is not installed" % args.name,
                            hint="see `boost list`")
        names = [args.name]
    else:
        names = sorted(inst)
        if not names:
            if args.json:
                print(json.dumps({"note": _IMPACT_NOTE, "skills": []}))
            else:
                out.info("no skills installed — nothing to measure")
            return 0

    in_repo = False
    if gitutil.has_git():
        proc = gitutil.run(["rev-parse", "--is-inside-work-tree"],
                           cwd=Path.cwd(), check=False)
        in_repo = proc.returncode == 0 and proc.stdout.strip() == "true"

    rows, data = [], []
    for name in names:
        entry = inst[name]
        since = entry.get("installed_at") or ""
        commits, files = _repo_activity(since) if in_repo else (None, None)
        events = len(journal.events(subject=name))
        rows.append((name, util.rel_time(since) if since else "?",
                     "—" if commits is None else str(commits), str(events)))
        data.append({"skill": name, "installed_at": since or None,
                     "commits_since": commits, "files_touched": files,
                     "events": events})

    if args.json:
        print(json.dumps({"note": _IMPACT_NOTE, "skills": data}))
        return 0
    out.heading("impact" + ((" of %s" % args.name) if args.name else ""))
    out.table(rows, headers=("SKILL", "INSTALLED", "COMMITS SINCE", "EVENTS"))
    if args.name and in_repo and data[0]["files_touched"] is not None:
        out.kv("files touched", data[0]["files_touched"])
    if args.name:
        if ai.available():
            reply = ai.ask(
                "In one cautious paragraph (under 80 words), assess what can "
                "and cannot be concluded about this AI-coding skill's impact "
                "from correlational data only: %s. Do not overclaim."
                % json.dumps(data[0]))
            if reply:
                print()
                print(textwrap.indent(textwrap.fill(reply, width=76), "  "))
        else:
            _note_fallback()
    out.dim("  " + _IMPACT_NOTE)
    return 0


_IMPACT_NOTE = "correlation, not causation — commits since install in this repo"


def _repo_activity(since: str) -> Tuple[Optional[int], Optional[int]]:
    """(commit count, unique files touched) in cwd's repo since a date."""
    if not since:
        return None, None
    commits = files = None
    proc = gitutil.run(["rev-list", "--count", "--since=" + since, "HEAD"],
                       cwd=Path.cwd(), check=False)
    if proc.returncode == 0:
        with contextlib.suppress(ValueError):
            commits = int(proc.stdout.strip() or 0)
    proc = gitutil.run(["log", "--name-only", "--since=" + since,
                        "--pretty=format:"], cwd=Path.cwd(), check=False)
    if proc.returncode == 0:
        files = len({ln.strip() for ln in proc.stdout.splitlines() if ln.strip()})
    return commits, files


def _print_reply(reply: chat_engine.Reply, show_sources: bool) -> None:
    """Render one answer: the prose, then where it came from.

    Citations are not decoration here. The next thing a user does with an answer
    is install code that runs inside their agent, so every recommendation has to
    be checkable against a real catalogue entry.
    """
    for line in reply.text.splitlines():
        out.info(line)
    if show_sources and reply.skills:
        out.info("")
        out.info(out.role("sources · ranked by %s" % reply.engine, "muted"))
        for cite in chat_engine.citations(reply.skills):
            out.info(out.role("  %s  %s  (%s)"
                              % (cite["name"], cite["kind"], cite["tap"]), "muted"))
    if reply.source == "extractive" and not reply.grounded:
        # The model answered and was rejected. Saying so beats silently showing
        # a downgraded answer that looks identical to a confident one.
        out.warn("the AI reply named something outside the retrieved skills — "
                 "showing the grounded matches instead")


def cmd_chat(argv: List[str]) -> int:
    """Ask about skills in plain language; answers are grounded in retrieval."""
    ap = cliparse.parser(
        prog="boost chat",
        description="Ask about skills in plain language")
    ap.add_argument("question", nargs="*", metavar="QUESTION",
                    help="ask once and exit; omit for an interactive session")
    ap.add_argument("-k", "--limit", type=int, default=chat_engine.TOP_K,
                    metavar="N", help="candidate skills to consider (default %d)"
                                      % chat_engine.TOP_K)
    ap.add_argument("--no-sources", action="store_true",
                    help="hide the citation block under each answer")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="machine-readable answer (implies one-shot)")
    args = ap.parse_args(argv)

    if not registry.list_taps():
        raise BoostError("no taps configured — nothing to chat about",
                        hint="add the recommended registries with `boost tap --defaults`")

    question = " ".join(args.question).strip()
    if args.as_json:
        if not question:
            raise BoostError("--json needs a question",
                            hint='try: boost chat --json "how do I review a diff?"')
        reply = chat_engine.answer(question, k=args.limit)
        print(json.dumps({
            "question": question,
            "answer": reply.text,
            "engine": reply.engine,
            "source": reply.source,
            "grounded": reply.grounded,
            "skills": chat_engine.citations(reply.skills),
        }))
        return 0

    if question:
        _print_reply(chat_engine.answer(question, k=args.limit), not args.no_sources)
        return 0

    return _chat_session(args)


def _chat_session(args) -> int:
    """The interactive loop. Kept separate so cmd_chat stays a dispatcher.

    History is bounded by chat_engine.HISTORY_TURNS — this is a lookup
    assistant, and a long transcript encourages answering from the conversation
    rather than from what retrieval actually returned.
    """
    if not ai.available():
        # Worth saying up front rather than letting every answer look terse for
        # an unexplained reason.
        out.info(out.role("no AI configured — answers are the grounded matches "
                          "themselves (%s)" % ai.fallback_note(), "muted"))
    out.info(out.role("ask about skills; blank line or Ctrl-D to exit", "muted"))
    history: List[chat_engine.Turn] = []
    while True:
        try:
            question = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            out.info("")
            return 0
        if not question:
            return 0
        reply = chat_engine.answer(question, history=history, k=args.limit)
        out.info("")
        _print_reply(reply, not args.no_sources)
        history.append(chat_engine.Turn(question, reply.text))
        for follow in chat_engine.suggest_followups(reply.skills)[:2]:
            out.info(out.role("  try: %s" % follow, "muted"))
