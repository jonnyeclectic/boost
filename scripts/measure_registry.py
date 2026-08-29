#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Measure a registry repo's item count the way `est_items` is defined.

`scripts/build_registries.py` documents `est_items` as *measured*, not
estimated. The measurement is not simply `len(catalog.scan_dir(repo))`, because
a growing number of registries ship one vendored copy of every item per agent
they support -- `.claude/`, `.cursor/`, `.gemini/`, `.github/`, `.grok/`,
`.trae/`, `plugin/`, ... A raw walk of `pbakaus/impeccable` finds 40 items for
the 6 it actually ships, and quoting 40 would advertise a mirror as a catalog.

So identity is a **content hash**, not a name -- the same rule the eval gate's
ranked list uses, and for the same reason. Keying on the name is wrong in both
directions: it collapses `design-research/commands/test-plan.md` and
`prototyping-testing/commands/test-plan.md`, two different items that share a
name, while a `design-review` subagent and a `/design-review` slash command
really are two items.

Hashing the raw bytes is not enough either, because the mirrors are *rendered*
per agent rather than copied: `pbakaus/impeccable`'s fourteen `SKILL.md` copies
differ only in the dotdir baked into their prose (`node .cursor/skills/...`)
and in per-agent frontmatter keys (`allowed-tools`, `argument-hint`). So the
hash is taken over the body with the frontmatter dropped and agent dotdir
tokens normalized -- which is the same "one render per agent" shape boost
itself emits from `rules.CONTEXT_FILES` and `workflows.render_gemini_command`.
Counts are floors: a mirror that also edits prose still reads as two items.

Usage:
    python3 scripts/measure_registry.py <path-to-clone> [...]
    python3 scripts/measure_registry.py --self-check <clone-root>
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boost_cli.core import catalog, frontmatter

# Rows whose committed est_items were produced by this rule; --self-check
# re-derives them from local clones so the convention stays falsifiable.
SELF_CHECK = {
    "nextlevelbuilder/ui-ux-pro-max-skill": 10,
    # 80 until 2026-08: the old count read `claude-plugin/<pack>/commands/x.md`
    # and `commands/<pack>/x.md` as two commands each.
    "Owl-Listener/ai-design-skills": 62,
    "Owl-Listener/designer-skills": 125,
    "thedaviddias/Front-End-Checklist": 390,
    "bergside/awesome-design-skills": 67,
    # Both render one copy per agent they support; raw walks find 13 and 28.
    # caveman's 21 keeps `commands/*.md` and `src/plugins/opencode/commands/*.md`
    # apart on purpose — they share names but are separately authored prose,
    # which is the "counts are floors" case above, not a mirror. Its `.toml`
    # command twins never enter the count at all: `scan_dir` indexes Markdown.
    "DietrichGebert/ponytail": 7,
    "JuliusBrussee/caveman": 21,
}


# Agent dotdirs and packaging roots that registries render a copy into. The
# token is normalized away before hashing so one skill rendered fourteen ways
# stays one skill.
_AGENT_DIR = re.compile(
    r"\.(?:agents|claude|codex|cursor|gemini|github|grok|kiro|opencode|pi|"
    r"qoder|rovodev|trae-cn|trae|vibe|windsurf)\b"
    r"|\b(?:claude-plugin|plugin)/",
)


def _digest(root: Path, item: dict) -> str:
    """Hash of the item body, blind to which agent it was rendered for."""
    text = (root / item["skill_md"]).read_text(encoding="utf-8", errors="replace")
    _meta, body = frontmatter.parse(text)
    return hashlib.sha256(
        _AGENT_DIR.sub("<agent>", body).encode("utf-8")).hexdigest()


def measure(root: Path) -> dict[str, int]:
    """-> {kind: distinct item count} for a cloned registry repo."""
    seen: set[tuple[str, str]] = set()
    for item in catalog.scan_dir(root, "measure"):
        try:
            seen.add((item["kind"], _digest(root, item)))
        except OSError:
            seen.add((item["kind"], item["skill_md"]))
    counts: dict[str, int] = {}
    for kind, _key in seen:
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def focus_suffix(counts: dict[str, int]) -> str:
    """The `(7 skills, 3 workflows)` tail the focus strings carry."""
    parts = ["%d %ss" % (counts[k], k)
             for k in (catalog.KIND_SKILL, catalog.KIND_RULE,
                       catalog.KIND_WORKFLOW) if counts.get(k)]
    return "(%s)" % ", ".join(parts) if parts else "(no items)"


def _self_check(root: Path) -> int:
    bad = 0
    for name, expected in sorted(SELF_CHECK.items()):
        clone = root / name.replace("/", "__")
        if not clone.is_dir():
            print("  skip %-44s (no clone at %s)" % (name, clone))
            continue
        counts = measure(clone)
        total = sum(counts.values())
        flag = "ok " if total == expected else "BAD"
        if total != expected:
            bad += 1
        print("  %s %-44s %4d  expected %4d  %s"
              % (flag, name, total, expected, focus_suffix(counts)))
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path,
                        help="cloned registry repos to measure")
    parser.add_argument("--self-check", action="store_true",
                        help="treat the single path as a clone root (e.g. "
                             "~/.boost/repos) and re-derive committed counts")
    args = parser.parse_args(argv)

    if args.self_check:
        return _self_check(args.paths[0])

    for path in args.paths:
        counts = measure(path)
        print("%-46s est_items=%-5d %s"
              % (path.name, sum(counts.values()), focus_suffix(counts)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
