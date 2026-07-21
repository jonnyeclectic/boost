#!/usr/bin/env python3
"""Assemble the curated registry catalog shipped at boost_cli/data/registries.json.

Source data is the researched skill/rule/workflow registries (2026-07). Each
entry is deduped by owner/repo, classified by type + category, and tagged with
`list_only` when the repo is an awesome-list that mostly links out (so its
scannable item count is far below its advertised total).

Run:    python3 scripts/build_registries.py            # regenerate the JSON
Verify: python3 scripts/build_registries.py --check    # fail if it has drifted
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEST = Path(__file__).resolve().parent.parent / "boost_cli" / "data" / "registries.json"

# Repos that are index/awesome READMEs — they *point at* many items but ship
# few or no scannable item files themselves. Kept for discovery, flagged so
# count math stays honest.
LIST_ONLY = {
    "travisvn/awesome-claude-skills", "karanb192/awesome-claude-skills",
    "ComposioHQ/awesome-claude-skills", "Chat2AnyLLM/awesome-claude-skills",
    "GetBindu/awesome-claude-code-and-skills", "BehiSecc/awesome-claude-skills",
    "JayZeeDesign/awesome-claude-skills", "VoltAgent/awesome-agent-skills",
    "VoltAgent/awesome-openclaw-skills", "majiayu000/claude-skill-registry",
    "gmh5225/awesome-skills", "heilcheng/awesome-agent-skills",
    "sickn33/antigravity-awesome-skills", "yusufkaraaslan/Skill_Seekers",
    "hesreallyhim/awesome-claude-code", "hesreallyhim/a-list-of-claude-code-agents",
    "subinium/awesome-claude-code", "jqueryscript/awesome-claude-code",
    "rahulvrane/awesome-claude-agents", "ichoosetoaccept/awesome-windsurf",
    "hao-ji-xing/awesome-cursor", "johnlindquist/get-rules",
    "langgptai/awesome-claude-prompts",
}

# --- skills (SKILL.md registries) -------------------------------------------
SKILLS = [
    ("travisvn/awesome-claude-skills", "meta", "Curated awesome-list of Claude Skills, tools, and resources", 60, "high"),
    ("karanb192/awesome-claude-skills", "meta", "Curated list of 50+ verified Claude skills for Code/API/claude.ai", 50, "high"),
    ("ComposioHQ/awesome-claude-skills", "meta", "Curated Claude skills list plus Composio workflow integrations", 40, "high"),
    ("Chat2AnyLLM/awesome-claude-skills", "meta", "Metadata catalog of Claude Code skill source repos via GitHub API", 50, "med"),
    ("BehiSecc/awesome-claude-skills", "meta", "Curated list of Claude Skills", 40, "med"),
    ("JayZeeDesign/awesome-claude-skills", "meta", "Curated awesome-list of Claude skills", 30, "low"),
    ("VoltAgent/awesome-agent-skills", "meta", "1000+ agent skills index from official teams and community", 1000, "high"),
    ("VoltAgent/awesome-openclaw-skills", "meta", "Large aggregated index of OpenClaw/agent skills", 500, "low"),
    ("majiayu000/claude-skill-registry", "meta", "Searchable index of Claude Code skills aggregated from GitHub", 500, "high"),
    ("tech-leads-club/agent-skills", "meta", "Security-validated (Snyk-scanned) skill registry for coding agents", 50, "high"),
    ("gmh5225/awesome-skills", "meta", "Curated agent skills for Claude Code, Codex, Gemini CLI, Copilot", 50, "med"),
    ("heilcheng/awesome-agent-skills", "meta", "Tutorials, guides, and agent skills directories", 40, "med"),
    ("abubakarsiddik31/claude-skills-collection", "general", "Curated collection of official and community-built Claude skills", 40, "med"),
    ("obviousworks/Claude-AI-skills-collection-2026", "general", "Curated collection of official and community Claude skills", 30, "low"),
    ("sickn33/antigravity-awesome-skills", "meta", "Aggregated 1300+ agent skills for Antigravity/Claude Code", 1300, "low"),
    ("alirezarezvani/claude-skills", "general", "362 skills across 18 domains (engineering, marketing, C-level, compliance)", 362, "high"),
    ("jeffallan/claude-skills", "web-dev", "66 full-stack developer skills across 12 categories", 66, "high"),
    ("oaustegard/claude-skills", "general", "Personal collection of Claude skills (codebases, data, media, GitHub)", 50, "high"),
    ("veniceai/skills", "data", "23 skills for the Venice.ai API surface areas", 23, "high"),
    ("LambdaTest/agent-skills", "devops", "60+ test-automation skills across Selenium, Playwright, Appium", 60, "high"),
    ("Orchestra-Research/AI-Research-SKILLs", "data", "98 skills across 23 categories for the AI research lifecycle", 98, "high"),
    ("rampstackco/claude-skills", "web-dev", "103 skills covering full website lifecycle (brand, SEO, dev, ops)", 103, "high"),
    ("vercel-labs/agent-skills", "web-dev", "Vercel official skills: React/Next/RN best practices, deploy, design", 8, "high"),
    ("angular/skills", "web-dev", "Official Angular skills (angular-developer, angular-new-app)", 2, "high"),
    ("huggingface/skills", "data", "27+ Hugging Face ecosystem skills (Hub, training, deployment, Gradio)", 27, "high"),
    ("microsoft/skills", "devops", "175 Azure/Foundry SDK skills across Python, TS, .NET, Java, Rust", 175, "high"),
    ("antfu/skills", "web-dev", "17 skills for the Vue/Vite ecosystem (nuxt, pinia, vitest, unocss)", 17, "high"),
    ("mattpocock/skills", "web-dev", "19 engineering/productivity skills (TDD, code review, spec, research)", 19, "high"),
    ("addyosmani/agent-skills", "devops", "24 lifecycle skills across define/plan/build/verify/review/ship", 24, "high"),
    ("daymade/claude-code-skills", "general", "70+ skill marketplace (docs, GitHub, audio/video, finance, testing)", 70, "high"),
    ("mhattingpete/claude-skills-marketplace", "security", "Skills for forensics, metadata, git, test-fixing, review", 8, "med"),
    ("sanjay3290/ai-skills", "general", "Skills incl. deep-research, postgres, google-workspace, imagen", 8, "med"),
    ("NeoLabHQ/context-engineering-kit", "meta", "Skills: prompt-engineering, software-architecture, subagent-driven-dev", 6, "med"),
    ("coreyhaines31/marketingskills", "writing", "Marketing and growth-focused agent skills", 10, "med"),
    ("obra/superpowers-skills", "general", "Community-editable companion skills repo to Superpowers", 30, "med"),
    ("obra/superpowers-lab", "general", "Experimental/evolving Superpowers skills", 15, "med"),
    ("conorluddy/ios-simulator-skill", "web-dev", "Single skill for driving the iOS Simulator", 1, "med"),
    ("lackeyjb/playwright-skill", "devops", "Single model-invoked Playwright browser-automation skill", 1, "med"),
    ("chrisvoncsefalvay/claude-d3js-skill", "data", "Single skill for producing D3.js charts", 1, "med"),
    ("jthack/ffuf_claude_skill", "security", "Single skill wrapping ffuf web fuzzing", 1, "med"),
    ("yusufkaraaslan/Skill_Seekers", "meta", "Tool that converts documentation sites into Claude skills", 5, "med"),
    # --- RAG / retrieval / vector-search skills (curated 2026-07) ------------
    ("weaviate/agent-skills", "rag", "Official Weaviate skills: agentic RAG, hybrid/semantic search, multimodal PDF, cookbooks", 12, "high"),
    ("pinecone-io/skills", "rag", "Pinecone's official Agent Skills library for building RAG pipelines", 10, "high"),
    ("pinecone-io/pinecone-claude-code-plugin", "rag", "Official Pinecone Claude Code plugin: chunk, embed, retrieve, cite", 6, "high"),
    ("saskinosie/weaviate-claude-skills", "rag", "Connect Claude to local Weaviate: manage collections, ingest, query with RAG", 5, "high"),
    ("OmidZamani/dspy-skills", "rag", "DSPy framework skills for programmatic prompting and RAG optimization", 15, "high"),
    ("osovv/grace-marketplace", "rag", "GRACE: Graph-RAG Anchored Code Engineering agent skill marketplace", 12, "high"),
    ("TakaGoto/rag-learning-academy", "rag", "Multi-agent Claude Code environment for mastering RAG end-to-end", 5, "med"),
]

# --- rules (Cursor .mdc / .cursorrules / Windsurf) --------------------------
RULES = [
    ("PatrickJS/awesome-cursorrules", "meta", "Canonical curated collection of .cursorrules/.mdc by framework/language/domain", 170, "high"),
    ("sanjeed5/awesome-cursor-rules-mdc", "meta", "LLM-generated .mdc rules for hundreds of libraries plus a generator", 879, "high"),
    ("pontusab/directories", "meta", "Backing repo for cursor.directory; Cursor & Windsurf rules and MCPs", 400, "high"),
    ("SchneiderSam/awesome-windsurfrules", "meta", "Curated global_rules.md and .windsurfrules files for Windsurf", 120, "med"),
    ("balqaasem/awesome-windsurfrules", "meta", "Collection of .windsurfrules and global_rules files for Windsurf", 120, "med"),
    ("JhonMA82/awesome-clinerules", "meta", "Curated list of .cursorrules files (Cline-adapted fork)", 150, "med"),
    ("tugkanboz/awesome-cursorrules", "meta", "Curated list of .cursorrules files for Cursor AI, MDC format", 120, "med"),
    ("nedcodes-ok/cursorrules-collection", "general", "110+ tested .mdc and .cursorrules files with validation tooling", 110, "high"),
    ("ivangrynenko/cursorrules", "backend", "Cursor rules for PHP, Python, JS and Drupal with OWASP focus", 25, "med"),
    ("LessUp/awesome-cursorrules-zh", "meta", "Chinese curated collection of 132+ Cursor rules across 32 domains", 132, "high"),
    ("matank001/cursor-security-rules", "security", "Security-focused Cursor rules for safe development workflows", 20, "med"),
    ("BlueBirdBack/godot-cursorrules", "framework", "Godot 4.4 game-development coding-standard cursor rules", 10, "low"),
    ("blefnk/awesome-cursor-rules", "frontend", "Modern frontend rules for Next.js, React, TypeScript", 20, "med"),
    ("flyeric0212/cursor-rules", "general", "Curated collection of Cursor rule files across languages/frameworks", 40, "med"),
    ("Aaronontheweb/dotnet-cursor-rules", "framework", ".mdc files defining Cursor rules specific to .NET projects", 15, "med"),
    ("jesseoue/cursor-rules", "web-dev", "36 production-ready MDC rules for Next.js, React, TS, Drizzle, Shadcn", 36, "high"),
    ("survivorforge/cursor-rules", "web-dev", "39+ framework-specific .cursorrules for React, Next.js, Python, Node", 39, "med"),
    ("pekral/cursor-rules", "framework", "PHP and Laravel Cursor rules for standards, testing, conventions", 12, "med"),
    ("Qwertic/cursorrules", "general", "A collection of .cursorrules files", 20, "low"),
    ("quintonwall/cursorrules", "general", "Collection of cursor rules files for different languages", 15, "low"),
    ("DVC2/cursor_prompts", "general", "Curated advanced .mdc rules for agent behavior, memory, workflows", 15, "low"),
    ("johnlindquist/get-rules", "meta", "CLI that downloads .mdc rule files for Cursor", 30, "low"),
    ("digitalchild/cursor-best-practices", "general", "Best-practices and example rule files for Cursor AI editor", 10, "low"),
    ("hao-ji-xing/awesome-cursor", "meta", "Curated collection of tools and resources for Cursor", 25, "low"),
    ("ichoosetoaccept/awesome-windsurf", "meta", "Awesome resources for the Windsurf editor including rules", 30, "low"),
]

# --- workflows (Claude Code commands / subagents) ---------------------------
WORKFLOWS = [
    ("wshobson/agents", "agents", "203 subagents, 175 skills, 109 commands from one Markdown source", 200, "high"),
    ("wshobson/commands", "commands", "57 production-ready slash commands (15 workflows, 42 tools)", 57, "high"),
    ("VoltAgent/awesome-claude-code-subagents", "agents", "100+ specialized subagents across dev, infra, quality, data, meta", 116, "high"),
    ("hesreallyhim/awesome-claude-code", "meta", "Hand-picked list of Claude Code commands, agents, hooks, skills", 200, "med"),
    ("davila7/claude-code-templates", "general", "CLI + registry with 600+ agents, 200+ commands, MCPs, hooks", 800, "high"),
    ("qdhenry/Claude-Command-Suite", "commands", "216+ slash commands, 54 AI agents, 12 skills for dev workflows", 216, "high"),
    ("0xfurai/claude-code-subagents", "agents", "100+ production-ready domain-specialist development subagents", 100, "high"),
    ("rahulvrane/awesome-claude-agents", "agents", "Community collection of Claude Code subagents", 40, "med"),
    ("vijaythecoder/awesome-claude-agents", "agents", "Orchestrated subagent dev team powered by Claude Code", 24, "med"),
    ("rohitg00/awesome-claude-code-toolkit", "general", "135 agents, 42 commands, 35 skills, 176+ plugins, hooks, rules", 200, "med"),
    ("aiwonglab/claude_code_agents", "agents", "Production-ready subagents for Claude Code", 50, "med"),
    ("lst97/claude-code-sub-agents", "agents", "33 specialized AI subagents for full-stack development", 33, "high"),
    ("chusri/claude-code-agents", "agents", "75 production-ready domain-specialist subagents", 75, "med"),
    ("dl-ezo/claude-code-sub-agents", "agents", "35 specialized subagents for end-to-end software development", 35, "high"),
    ("iannuttall/claude-agents", "agents", "Custom subagents to copy into project .claude/agents/ directory", 12, "med"),
    ("talknerdytome-labs/claude-agents", "agents", "Production-ready growth marketing subagents for Claude Code", 20, "low"),
    ("hesreallyhim/a-list-of-claude-code-agents", "meta", "Community-submitted index of Claude Code subagents", 10, "med"),
    ("danielrosehill/Claude-Slash-Commands", "commands", "Personal collection of Claude Code slash commands", 30, "med"),
    ("hikarubw/claude-commands", "commands", "6 custom slash commands for daily dev workflows", 6, "high"),
    ("brennercruvinel/CCPlugins", "commands", "24 slash commands for dev workflow, code quality, analysis", 24, "high"),
    ("Comfy-Org/comfy-claude-prompt-library", "commands", "70+ Claude Code commands/prompts for agentic coding", 70, "high"),
    ("davepoon/claude-code-subagents-collection", "general", "BuildWithClaude hub of skills, agents, commands, hooks, plugins", 100, "med"),
    ("langgptai/awesome-claude-prompts", "general", "Curated Claude prompt collection for coding and general use", 50, "med"),
    ("steipete/agent-rules", "general", "20+ rule/command files for Claude Code and Cursor agents", 20, "med"),
    ("kasperjunge/agent-resources-legacy", "general", "Installable collection of Claude Code skills, commands, subagents", 30, "low"),
    ("ChrisWiles/claude-code-showcase", "general", "Example config with hooks, skills, agents, commands, Actions", 20, "low"),
    ("subinium/awesome-claude-code", "meta", "Curated list of tools, skills, plugins, MCP servers for Claude Code", 80, "med"),
    ("jqueryscript/awesome-claude-code", "meta", "Curated list of tools, integrations, frameworks for Claude Code", 80, "low"),
]

PRIORITY = {"skill": 3, "workflow": 2, "rule": 1}


def rows(pairs, typ):
    for name, category, focus, est, conf in pairs:
        yield {
            "name": name,
            "url": "https://github.com/" + name,
            "type": typ,
            "category": category,
            "focus": focus,
            "est_items": est,
            "confidence": conf,
            "list_only": name in LIST_ONLY,
            "curated": True,
        }


def build_payload() -> dict:
    """Assemble the registries payload from the SKILLS/RULES/WORKFLOWS tuples.

    Pure function of the source tuples — no I/O — so both the writer and the
    ``--check`` verifier render byte-for-byte identical output.
    """
    by_name: dict = {}
    for entry in list(rows(SKILLS, "skill")) + list(rows(RULES, "rule")) + \
            list(rows(WORKFLOWS, "workflow")):
        prev = by_name.get(entry["name"])
        if prev is None:
            by_name[entry["name"]] = entry
            continue
        # keep the more authoritative type; merge the other into also_types
        keep, drop = (prev, entry) if PRIORITY[prev["type"]] >= PRIORITY[entry["type"]] \
            else (entry, prev)
        also = set(keep.get("also_types", [])) | {drop["type"]}
        keep["also_types"] = sorted(also)
        keep["est_items"] = max(keep["est_items"], drop["est_items"])
        by_name[keep["name"]] = keep

    entries = sorted(by_name.values(), key=lambda e: (e["type"], e["name"].lower()))
    scannable = [e for e in entries if not e["list_only"]]
    return {
        "generated_note": "Curated skill/rule/workflow registries for boost. "
                          "est_items are research estimates; verify by tapping. "
                          "list_only repos are index/awesome lists that link out.",
        "count": len(entries),
        "est_items_total": sum(e["est_items"] for e in entries),
        "est_items_scannable": sum(e["est_items"] for e in scannable),
        "registries": entries,
    }


def render(payload: dict) -> str:
    """Serialize a payload to the exact on-disk representation."""
    return json.dumps(payload, indent=2) + "\n"


def _summary(payload: dict) -> None:
    entries = payload["registries"]
    scannable = [e for e in entries if not e["list_only"]]
    print("registries: %d  (scannable %d, list-only %d)"
          % (len(entries), len(scannable), len(entries) - len(scannable)))
    print("est items total: %d   scannable: %d"
          % (payload["est_items_total"], payload["est_items_scannable"]))
    by_type: dict = {}
    for e in entries:
        by_type.setdefault(e["type"], [0, 0])
        by_type[e["type"]][0] += 1
        by_type[e["type"]][1] += e["est_items"]
    for typ, (n, est) in sorted(by_type.items()):
        print("  %-9s %3d repos  ~%d items" % (typ, n, est))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="verify the committed JSON matches a fresh build; exit 1 on drift "
             "(does not write). Used in CI to catch un-regenerated edits.",
    )
    args = parser.parse_args(argv)

    payload = build_payload()
    fresh = render(payload)

    if args.check:
        current = DEST.read_text(encoding="utf-8") if DEST.exists() else ""
        if current != fresh:
            print(
                "ERROR: %s is out of date — regenerate it with\n"
                "    python3 scripts/build_registries.py\n"
                "and commit the result (see CONTRIBUTING.md)." % DEST,
                file=sys.stderr,
            )
            return 1
        print("%s is up to date." % DEST)
        return 0

    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(fresh, encoding="utf-8")
    print("wrote %s" % DEST)
    _summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
