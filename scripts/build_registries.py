#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Assemble the curated registry catalog shipped at boost_cli/data/registries.json.

Source data is the researched skill/rule/workflow registries. Each entry is
deduped by owner/repo, classified by type + category, and tagged with
`list_only` when the repo is an awesome-list that mostly links out (so its
scannable item count is far below its advertised total).

`est_items` for the 2026-07 batch is **measured**, not estimated: every repo's
file tree was walked and its skills/rules/workflows counted with the same rules
as `core.catalog.scan_dir`, so the number is a floor (items nested deeper than
the walk are missed) rather than a marketing figure. Rows predating that batch
keep their research estimates except where a re-measure disagreed.

Seven domains are curated end to end and are the useful `--category` values for
`boost tap --catalog`: `ai`, `architecture`, `ui`, `java`, `ecommerce`, `infra`,
`marketing`.
Their coverage floors are enforced by tests/unit/test_registry_categories.py.

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

# Repos that were curated here and have since been deleted or made private.
# They are recorded rather than merely deleted because the catalogue is
# assembled from research batches: a batch written before the repo vanished
# still names it, so dropping the row alone lets the next sweep re-add it from
# the same stale source. Verified with `--verify-live`, which is the runnable
# form of CLAUDE.md's "verify a repo is real before adding it" — a convention
# that six dead rows proved does not enforce itself.
#
# Archived-but-reachable repos are deliberately NOT here. They still clone and
# still ship their items; frozen is not gone.
RETIRED = {
    "MikroJit-Technologies/claude-skills":
        "404 since 2026-08 — the tap that broke `boost update` for every "
        "other tap on the maintainer's machine (see roadmap "
        "one-dead-tap-broke-every-update)",
    "pcliangx/AppGenesisForge":
        "404 since 2026-08 — clone prompts for credentials, which is what "
        "fails the scheduled eval-scale gate on its pinned corpus",
}

# --- skills (SKILL.md registries) -------------------------------------------
SKILLS = [
    ("travisvn/awesome-claude-skills", "meta", "Curated awesome-list of Claude Skills, tools, and resources", 60, "high"),
    ("karanb192/awesome-claude-skills", "meta", "Curated list of 50+ verified Claude skills for Code/API/claude.ai", 50, "high"),
    ("ComposioHQ/awesome-claude-skills", "meta", "Curated Claude skills list plus Composio workflow integrations", 40, "high"),
    ("Chat2AnyLLM/awesome-claude-skills", "meta", "Metadata catalog of Claude Code skill source repos via GitHub API", 50, "med"),
    ("BehiSecc/awesome-claude-skills", "meta", "Curated list of Claude Skills", 40, "med"),
    ("JayZeeDesign/awesome-claude-skills", "meta", "Curated awesome-list of Claude skills", 16, "low"),
    ("VoltAgent/awesome-agent-skills", "meta", "1000+ agent skills index from official teams and community", 1000, "high"),
    ("VoltAgent/awesome-openclaw-skills", "meta", "Large aggregated index of OpenClaw/agent skills", 500, "low"),
    ("majiayu000/claude-skill-registry", "meta", "Searchable index of Claude Code skills aggregated from GitHub", 500, "high"),
    ("tech-leads-club/agent-skills", "meta", "Security-validated (Snyk-scanned) skill registry for coding agents", 84, "high"),
    ("gmh5225/awesome-skills", "meta", "Curated agent skills for Claude Code, Codex, Gemini CLI, Copilot", 8, "med"),
    ("heilcheng/awesome-agent-skills", "meta", "Tutorials, guides, and agent skills directories", 40, "med"),
    ("abubakarsiddik31/claude-skills-collection", "general", "Curated collection of official and community-built Claude skills", 40, "med"),
    ("obviousworks/Claude-AI-skills-collection-2026", "general", "Curated collection of official and community Claude skills", 30, "low"),
    ("sickn33/antigravity-awesome-skills", "meta", "Aggregated 1300+ agent skills for Antigravity/Claude Code", 1300, "low"),
    ("alirezarezvani/claude-skills", "general", "362 skills across 18 domains (engineering, marketing, C-level, compliance)", 313, "high"),
    ("jeffallan/claude-skills", "web-dev", "66 full-stack developer skills across 12 categories", 66, "high"),
    ("oaustegard/claude-skills", "general", "Personal collection of Claude skills (codebases, data, media, GitHub)", 50, "high"),
    ("veniceai/skills", "data", "23 skills for the Venice.ai API surface areas", 21, "high"),
    ("LambdaTest/agent-skills", "devops", "60+ test-automation skills across Selenium, Playwright, Appium", 72, "high"),
    ("Orchestra-Research/AI-Research-SKILLs", "data", "98 skills across 23 categories for the AI research lifecycle", 98, "high"),
    ("rampstackco/claude-skills", "web-dev", "103 skills covering full website lifecycle (brand, SEO, dev, ops)", 122, "high"),
    ("vercel-labs/agent-skills", "web-dev", "Vercel official skills: React/Next/RN best practices, deploy, design", 9, "high"),
    ("angular/skills", "web-dev", "Official Angular skills (angular-developer, angular-new-app)", 2, "high"),
    ("huggingface/skills", "data", "27+ Hugging Face ecosystem skills (Hub, training, deployment, Gradio)", 26, "high"),
    ("microsoft/skills", "devops", "175 Azure/Foundry SDK skills across Python, TS, .NET, Java, Rust", 175, "high"),
    ("antfu/skills", "web-dev", "17 skills for the Vue/Vite ecosystem (nuxt, pinia, vitest, unocss)", 17, "high"),
    ("mattpocock/skills", "web-dev", "19 engineering/productivity skills (TDD, code review, spec, research)", 41, "high"),
    ("addyosmani/agent-skills", "devops", "24 lifecycle skills across define/plan/build/verify/review/ship", 24, "high"),
    ("daymade/claude-code-skills", "general", "70+ skill marketplace (docs, GitHub, audio/video, finance, testing)", 70, "high"),
    ("mhattingpete/claude-skills-marketplace", "security", "Skills for forensics, metadata, git, test-fixing, review", 8, "med"),
    ("sanjay3290/ai-skills", "general", "Skills incl. deep-research, postgres, google-workspace, imagen", 8, "med"),
    ("NeoLabHQ/context-engineering-kit", "meta", "Skills: prompt-engineering, software-architecture, subagent-driven-dev", 6, "med"),
    ("coreyhaines31/marketingskills", "marketing", "CRO, copywriting, cold email, SEO, analytics and growth-engineering skills", 50, "high"),
    # `efficiency`: items that exist to make an agent emit less. Filed by item
    # name, not README — both of these read like general coding advice up top.
    # Focus strings describe what the items do and deliberately omit the
    # headline savings: independent paired benchmarks reproduced roughly a
    # fifth of each (ponytail -10.3% cost vs -20% advertised; caveman -8.5%
    # output tokens vs -65%), so quoting the advertised figure would make the
    # catalog a megaphone for a number its own source contradicts.
    ("DietrichGebert/ponytail", "efficiency", "Lazy-senior-dev rule + audit/debt/gain/review skills that cut code written (6 skills, 1 rule)", 7, "high"),
    ("JuliusBrussee/caveman", "efficiency", "Output-compression skill with intensity levels, plus commit/review/compress commands (7 skills, 14 workflows)", 21, "high"),
    ("obra/superpowers-skills", "general", "Community-editable companion skills repo to Superpowers", 30, "med"),
    ("obra/superpowers-lab", "general", "Experimental/evolving Superpowers skills", 15, "med"),
    ("conorluddy/ios-simulator-skill", "web-dev", "Single skill for driving the iOS Simulator", 1, "med"),
    ("lackeyjb/playwright-skill", "devops", "Single model-invoked Playwright browser-automation skill", 1, "med"),
    ("chrisvoncsefalvay/claude-d3js-skill", "data", "Single skill for producing D3.js charts", 1, "med"),
    ("jthack/ffuf_claude_skill", "security", "Single skill wrapping ffuf web fuzzing", 1, "med"),
    ("yusufkaraaslan/Skill_Seekers", "meta", "Tool that converts documentation sites into Claude skills", 5, "med"),
    # Listed in LIST_ONLY since the first batch but never given a row: it ships
    # no scannable item of its own, so est_items is its distinct outbound repo
    # links (267, counted from the README) rather than a file count.
    ("GetBindu/awesome-claude-code-and-skills", "meta", "Awesome-list index of Claude Code skills, plugins and tools (267 repos linked)", 267, "med"),
    # --- RAG / retrieval / vector-search skills (curated 2026-07) ------------
    ("weaviate/agent-skills", "rag", "Official Weaviate skills: agentic RAG, hybrid/semantic search, multimodal PDF, cookbooks", 12, "high"),
    ("pinecone-io/skills", "rag", "Pinecone's official Agent Skills library for building RAG pipelines", 10, "high"),
    ("pinecone-io/pinecone-claude-code-plugin", "rag", "Official Pinecone Claude Code plugin: chunk, embed, retrieve, cite", 6, "high"),
    ("saskinosie/weaviate-claude-skills", "rag", "Connect Claude to local Weaviate: manage collections, ingest, query with RAG", 5, "high"),
    ("OmidZamani/dspy-skills", "rag", "DSPy framework skills for programmatic prompting and RAG optimization", 15, "high"),
    ("osovv/grace-marketplace", "rag", "GRACE: Graph-RAG Anchored Code Engineering agent skill marketplace", 12, "high"),
    ("TakaGoto/rag-learning-academy", "rag", "Multi-agent Claude Code environment for mastering RAG end-to-end", 5, "med"),
    # --- 2026-07 batch: AI, architecture, UI, Java, eCommerce, infra ---
    # ai (49 repos, 807 measured items)
    ("lebsral/DSPy-Programming-not-prompting-LMs-skills", "ai", "AI skills for Claude Code, Cursor, and other coding agents. Build... (95 skills, 1 workflows)", 96, "med"),
    ("air-gapped/skills", "ai", "Claude Code plugin marketplace - 58 installable reference skills... (66 skills)", 66, "med"),
    ("po4yka/llm-wiki-skills", "ai", "Portable Agent Skills for building, operating, evaluating, and... (49 skills, 4 workflows)", 53, "med"),
    ("openai/skills", "ai", "Skills Catalog for Codex (44 skills)", 44, "high"),
    ("Goodnight77/rag-skills", "ai", "A collection of best-practice guides and skill definitions for... (39 skills)", 39, "med"),
    ("elastic/agent-skills", "ai", "Official Elastic Skills (35 skills)", 35, "high"),
    ("litestar-org/litestar-skills", "ai", "Opinionated first-party agent skills, plugins, subagents, slash... (30 skills, 3 workflows)", 33, "high"),
    ("anthropics/claude-plugins-community", "ai", "Community plugin marketplace for Claude Cowork and Claude Code... (30 skills)", 30, "high"),
    ("timwukp/MLOps-agent-skills", "ai", "A comprehensive collection of 25 Agent Skills for MLOps and LLMOps... (28 skills)", 28, "med"),
    ("hsliuustc0106/vllm-omni-skills", "ai", "a collection of skills for vllm-omni (24 skills)", 24, "high"),
    ("deepak-karkala/production-mlops-skills", "ai", "End-to-end MLOps workflows for teams running ML in production - from... (11 skills, 11 workflows)", 22, "med"),
    ("qdrant/skills", "ai", "Agent skills for Qdrant vector search: scaling, performance... (22 skills)", 22, "high"),
    ("langchain-ai/langchain-skills", "ai", "21 skills", 21, "high"),
    ("langchain-ai/skills-benchmarks", "ai", "21 skills", 21, "high"),
    ("anthropics/claude-tag-plugins", "ai", "19 skills, 1 workflows", 20, "high"),
    ("langwatch/skills", "ai", "LangWatch Skills - reusable capabilities for AI agents. Install with... (19 skills)", 19, "high"),
    ("anthropics/skills", "ai", "Public repository for Agent Skills (18 skills)", 18, "high"),
    ("cobusgreyling/agent-skills", "ai", "Personal collection of Agent Skills for AI coding agents (Claude Code... (18 skills)", 18, "med"),
    ("param087/agent-ml-skills", "ai", "Production-grade Machine Learning, Data Science & MLOps skills for AI... (15 skills)", 15, "med"),
    ("datarobot-oss/datarobot-agent-skills", "ai", "Bring DataRobot platform capabilities to your coding agents (14 skills)", 14, "med"),
    ("togethercomputer/skills", "ai", "Skills to help your coding agents use Together AI products (14 skills)", 14, "high"),
    ("Arize-ai/arize-skills", "ai", "Agent skills for Arize - datasets, experiments, and traces via the ax CLI (13 skills)", 13, "high"),
    ("shen-shanshan/vllm-dev-skills", "ai", "A curated collection of Claude Code agent skills that accelerate the... (12 skills)", 12, "med"),
    ("mlflow/skills", "ai", "11 skills", 11, "high"),
    ("pydantic/skills", "ai", "6 skills, 4 workflows", 10, "high"),
    ("itsmostafa/llm-engineering-skills", "ai", "LLM Engineering Claude Skills (9 skills)", 9, "med"),
    ("mongodb/agent-skills", "ai", "Use the official MongoDB Skills with your favorite coding agent to... (8 skills)", 8, "high"),
    ("redis/agent-skills", "ai", "Redis' official collection of agent skills (8 skills)", 8, "high"),
    ("doggy8088/litellm-skills", "ai", "LiteLLM Agent Skills SDK Proxy GatewayRoutingCost... (7 skills)", 7, "med"),
    ("langchain-ai/deepagentsjs", "ai", "The batteries included agent harness (7 skills)", 7, "high"),
    ("lhbsaa/embedded-dev-skill", "ai", "Embedded Development Skill for Pi Coding Agent & OpenCode - ESP32... (7 skills)", 7, "low"),
    ("MLOps-Courses/mlops-coding-skills", "ai", "Agent skills based on the MLOps Coding Course (7 skills)", 7, "med"),
    ("redis/agent-filesystem", "ai", "7 skills", 7, "high"),
    ("replicate/skills", "ai", "A collection of Agent Skills for building AI-powered apps with Replicate (7 skills)", 7, "high"),
    ("cohere-ai/vllm-skills", "ai", "5 skills, 1 rules", 6, "high"),
    ("iktakahiro/python-fastapi-ddd-skill", "ai", "A practical template for Building AI Agent Skills with Python... (6 skills)", 6, "low"),
    ("crewAIInc/skills", "ai", "5 skills", 5, "high"),
    ("togethercomputer/together-storage-claude-skills", "ai", "Claude Code skills for deploying & verifying Together T4 + CS3 over... (4 skills)", 4, "med"),
    ("run-llama/benchmark-claude-pdfs", "ai", "Benchmarks for Claude Code with and without the LiteParse skill, to... (3 skills)", 3, "med"),
    ("run-llama/llamaparse-agent-skills", "ai", "LlamaParse Agent Skills (3 skills)", 3, "med"),
    ("wandb/weave-claude-code", "ai", "Claude Code plugin that traces sessions, tool calls, and subagents to... (3 skills)", 3, "med"),
    ("anthropics/launch-your-agent", "ai", "Claude Code skills that take a founder from idea to a live Claude... (2 skills)", 2, "med"),
    ("Arize-ai/claude-code-otlp-collector", "ai", "OTLP bridge that forwards Claude Code telemetry to Arize (2 skills)", 2, "med"),
    ("comet-ml/opik-skills", "ai", "Agent skills for integrating and instrumenting Opik: LLM observability... (2 skills)", 2, "med"),
    ("langfuse/skills", "ai", "Agent Skills for Langfuse, the open source LLM engineering platform... (2 skills)", 2, "med"),
    ("anthropics/code-migration-kit-with-claude-code", "ai", "Prompts, templates, and scripts for running large-scale language... (1 skills)", 1, "med"),
    ("run-llama/llama-agents", "ai", "Llama Agents + Workflows are an event-driven, async-first, step-based... (1 skills)", 1, "med"),
    ("wandb/skills", "ai", "Official Agent Skills for Weights & Biases Models and Weave (1 skills)", 1, "med"),
    ("wandb/weave-integration-skills", "ai", "AI coding agent skills for integration Weave to exist project (1 skills)", 1, "med"),
    # architecture (12 repos, 279 measured items)
    ("FullFran/Agent-skills-POC", "architecture", "Built to upskill my team on agentic AI - framework-agnostic Agent... (28 skills, 16 workflows)", 44, "med"),
    ("45ck/software-architecture-skills", "architecture", "Software architecture skill pack for architecture views, tradeoffs... (42 skills)", 42, "med"),
    ("l-gevity/l-gevity-skills", "architecture", "The L-GEVITY Software Architecture AI Skills (38 skills)", 38, "med"),
    ("areebahmeddd/test-k8s", "architecture", "Kubernetes and CNCF ecosystem (24 skills, 9 rules, 2 workflows)", 35, "med"),
    ("ronnythedev/dotnet-clean-architecture-skills", "architecture", "27 AI-ready skills for generating production-grade .NET code - Clean... (29 skills)", 29, "high"),
    ("proyecto26/system-design-skills", "architecture", "A divide-and-conquer wiki of system-design skills for Claude Code... (22 skills, 2 workflows)", 24, "med"),
    ("full-stack-skills/ddd-skills", "architecture", "Domain-Driven Design skills - COLA, microservices, hexagonal, clean (21 skills)", 21, "med"),
    ("ericgandrade/claude-superskills", "architecture", "18 Universal AI Skills for Claude Code, GitHub Copilot & 6 more... (18 skills, 1 rules)", 19, "high"),
    ("ForceInjection/domain-driven-design-skills", "architecture", "Domain driven design skills for architect (9 skills)", 9, "med"),
    ("keez97/claude-architecture-skills", "architecture", "7 Claude Code skills for software architecture review (Python, web... (7 skills)", 7, "low"),
    ("renyangY/y-ddd-skills", "architecture", "DDD DDD DDD (6 skills)", 6, "low"),
    ("joeyave/golang-ddd-skills", "architecture", "5 skills", 5, "low"),
    # ui (53 repos, 1513 measured items)
    ("MengTo/Skills", "ui", "Agent skills for designers and builders using Codex, Claude, Cursor... (118 skills)", 118, "high"),
    ("full-stack-skills/t2ui-skills", "ui", "T2UI component skills - 97 TUI components for Pencil MCP (97 skills)", 97, "med"),
    ("ihlamury/design-skills", "ui", "Opinionated UI constraints extracted from the best design systems. Use... (87 skills)", 87, "high"),
    ("syncfusion/maui-ui-components-skills", "ui", "Skills for Syncfusion .NET MAUI components. Enable AI-assisted... (77 skills)", 77, "high"),
    ("ancoleman/ai-design-components", "ui", "Comprehensive UI/UX and Backend component design skills for... (76 skills)", 76, "med"),
    ("BuilderIO/agent-native", "ui", "A framework for building agent-native applications (70 skills, 3 workflows)", 73, "high"),
    ("TheGoat395/Codex-Skills", "ui", "Codex-first Agent Skills library for premium frontend, website... (70 skills, 1 rules)", 71, "high"),
    ("urmzd/dotfiles", "ui", "Cross-platform dotfiles managed by Chezmoi with Homebrew/apt and... (50 skills, 8 workflows)", 58, "med"),
    ("rebyteai-template/rebyte-skills", "ui", "Centralized repository for all eng0 platform template skills (51 skills)", 51, "med"),
    ("oguzhan18/angular-ecosystem-skills", "ui", "45 skills", 45, "med"),
    ("dembrandt/dembrandt-skills", "ui", "Senior-level UX and design-system knowledge, packaged so your AI agent... (40 skills)", 40, "med"),
    ("Dragoon0x/dragoon-skills", "ui", "design intelligence for ai coding agents. one unified cli, 36 commands... (38 skills)", 38, "med"),
    ("Dzakiamriz22/frontend-pack", "ui", "Premium Frontend Skill Pack for OpenCode - shadcn/ui, TailwindCSS... (38 skills)", 38, "med"),
    ("BintzGavin/helios-skills", "ui", "35 skills", 35, "med"),
    ("syncfusion/maui-toolkit-ui-components-skills", "ui", "Skills for Syncfusion Toolkit for .NET MAUI components. Enable... (35 skills)", 35, "med"),
    ("mgifford/accessibility-skills", "ui", "A collection of Claude Skill to mirror... (32 skills, 2 workflows)", 34, "med"),
    ("dylantarre/design-system-skills", "ui", "Design system skills for agentic coding (29 skills)", 29, "low"),
    ("linegel/threejs-complete-set-of-skill", "ui", "25 expert agent skills for ambitious Three.js WebGPU/TSL scenes... (28 skills, 1 workflows)", 29, "med"),
    ("plugin87/ux-ui-agent-skills", "ui", "Turn Claude into a Senior Design Architect - DTCG design tokens, 42... (17 skills, 12 workflows)", 29, "high"),
    ("BuilderIO/builder-agent-native-starter", "ui", "28 skills", 28, "high"),
    ("plugin87/full-stack-design-skills", "ui", "Framework-agnostic UX/UI & frontend curriculum for Claude Code - 15... (25 skills)", 25, "med"),
    ("flitzrrr/frontend-design-skills", "ui", "Opinionated web design skills from curated sources - one install... (22 skills, 2 rules)", 24, "med"),
    ("laguagu/claude-code-nextjs-skills", "ui", "Claude Code skills for AI apps Next.js 16 AI SDK 7 pgvector bun (22 skills, 2 workflows)", 24, "high"),
    ("scottstts/Threejs-Awesome-Graphics-Agent-Skills", "ui", "A three.js agent skills for producing awesome graphics for scenes and... (24 skills)", 24, "high"),
    ("zivtech/accessibility-skills", "ui", "Accessibility Skills (accessibility-skills): AI skills that plan... (15 skills, 9 workflows)", 24, "med"),
    ("manish1803/nextjs-fullstack-skills", "ui", "23 professional Agent Skills (SKILL.md) for Next.js, React, React... (23 skills)", 23, "med"),
    ("thedesignproject/agent-skills", "ui", "A community-driven collection of skills, prompts, and workflows to... (22 skills)", 22, "high"),
    ("southleft/skills-for-figma", "ui", "Open-source agent skills for the native Figma MCP server - design... (18 skills)", 18, "med"),
    ("thongdn-it/react-agent-skills", "ui", "The Ultimate AI Agent Skills Collection for the React Ecosystem (18 skills)", 18, "med"),
    ("BuilderIO/builder-agent-skills", "ui", "Skills for Builder.io (13 skills, 2 workflows)", 15, "high"),
    ("getsentry/sentry-agent-skills", "ui", "15 skills", 15, "med"),
    ("BuilderIO/skills", "ui", "Skills for coding agents (13 skills)", 13, "high"),
    ("vibe-motion/skills", "ui", "agent skills for vibe motion (13 skills)", 13, "high"),
    ("callstackincubator/agent-skills", "ui", "A collection of agent-optimized React Native skills for AI coding... (10 skills, 2 rules)", 12, "high"),
    ("rusel95/ios-agent-skills", "ui", "Production-tested iOS Agent Skills for Claude Code, Codex, and 40+ AI... (12 skills)", 12, "low"),
    ("analogjs/angular-skills", "ui", "Agent Skills for Angular Developers (10 skills)", 10, "high"),
    ("cuellarfr/design-skills", "ui", "UX and design skills for Claude Code - research, critique... (10 skills)", 10, "med"),
    ("dawitlabs/ui-skills", "ui", "Composable Claude Code skills for UI/UX work - color, accessibility... (10 skills)", 10, "low"),
    ("instantX-research/skills", "ui", "Open source skills for Agent (10 skills)", 10, "med"),
    ("mixa354/threejs-skills", "ui", "Master Three.js skills with curated files to enhance your 3D... (10 skills)", 10, "low"),
    ("nextlevelbuilder/ui-ux-pro-max-skill", "ui", "An AI SKILL that provide design intelligence for building professional... (7 skills, 3 workflows)", 10, "high"),
    ("veelenga/preview-skills", "ui", "Reduce cognitive load when reviewing AI agent work (10 skills)", 10, "low"),
    ("bryntum/skills", "ui", "Official Bryntum AI Skills: structured, agent-ready instructions... (9 skills)", 9, "low"),
    ("hueyexe/frontend-agent-skills", "ui", "Agent skills for frontend UX/UI design that actually looks good (9 skills)", 9, "low"),
    ("majidmanzarpour/threejs-game-skills", "ui", "Agent skills for building playable, polished Three.js browser games... (9 skills)", 9, "high"),
    ("greensock/gsap-skills", "ui", "Official AI skills for GSAP. These skills teach AI coding agents how... (8 skills)", 8, "high"),
    ("vuejs-ai/skills", "ui", "Agent skills for Vue 3 development (8 skills)", 8, "high"),
    ("spences10/svelte-claude-skills", "ui", "7 skills", 7, "high"),
    ("Gentleman-Programming/Gentleman.Dots", "ui", "My personal configuration for LazyVim ! (6 skills)", 6, "high"),
    ("stareezy-1/frontend-architecture-skill", "ui", "Six portable, framework-agnostic frontend Agent Skills (SKILL.md) for... (6 skills)", 6, "med"),
    ("BuilderIO/org-agent-starter", "ui", "5 skills", 5, "high"),
    ("withastro/astro-maintainer-skills", "ui", "Various skills for Astro maintainers when developing and maintaining Astro (5 skills)", 5, "high"),
    ("dtran320/claud3", "ui", "Claude Code plugin: D3.js data visualizations using Tufte principles (1 skills)", 1, "low"),
    # java (23 repos, 597 measured items)
    ("jabrena/plinth", "java", "Plinth is an AI-native engineering toolkit for modern Java enterprise... (119 skills, 22 workflows)", 141, "high"),
    ("JetBrains/skills", "java", "Curated agent skills collection verified by JetBrains (129 skills)", 129, "high"),
    ("GDvega/super-android-kotlin-firebase-skill", "java", "A modular Agent Skills repository for Android, Kotlin, Jetpack Compose... (38 skills)", 38, "med"),
    ("heandroro/apm-agents-java", "java", "26 skills, 5 workflows", 31, "med"),
    ("skydoves/compose-performance-skills", "java", "A curated library of Agent Skills focused on Jetpack Compose performance (25 skills)", 25, "high"),
    ("yalishevant/kotlin-backend-agent-skills", "java", "25 skills", 25, "med"),
    ("pluginagentmarketplace/custom-plugin-java", "java", "Java Development Plugin (12 skills, 12 workflows)", 24, "med"),
    ("chrisbanes/skills", "java", "Skills for Kotlin, Jetpack Compose, and Android development (22 skills)", 22, "high"),
    ("yanhaoluo0/AlibabaDevelopmentManualSkills", "java", "SkillsJavaJavaJava (21 skills, 1 rules)", 22, "med"),
    ("mmiani/kotlin-kmp-claude-agent-skills", "java", "Public AI agent skills for Kotlin Multiplatform projects, grounded in... (15 skills, 6 workflows)", 21, "high"),
    ("decebals/claude-code-java", "java", "Reusable AI development infrastructure for Java projects, optimized... (18 skills)", 18, "high"),
    ("Amplicode/spring-skills", "java", "Amplicode Agent Tools (15 skills)", 15, "high"),
    ("javiercamarenatriguero/android-skills", "java", "AI Skills for Android Development focused on best practices and modern... (15 skills)", 15, "med"),
    ("camunda/skills", "java", "Camunda AI Agent skills (13 skills)", 13, "high"),
    ("necatisozer/coding-skills", "java", "Coding standards and best practices for Kotlin, Android, and Compose... (13 skills)", 13, "low"),
    ("ryu-qqq/claude-spring-standards", "java", "AI-powered coding convention enforcement via MCP (Model Context Protocol) (5 skills, 5 workflows)", 10, "low"),
    ("binarywang/WxJava", "java", "Java SDK (5 skills, 1 workflows)", 6, "high"),
    ("Kotlin/kotlin-agent-skills", "java", "A collection of AI agent skills useful for projects using Kotlin language (6 skills)", 6, "high"),
    ("senoritadeveloper01/claude-skills", "java", "A Spring Boot Notes Project built entirely with Claude Code using... (6 skills)", 6, "low"),
    ("spring-ai-community/spring-testing-skills", "java", "SkillsJars for testing Spring applications - curated patterns for JPA... (6 skills)", 6, "high"),
    ("quarkusio/quarkusdev-skills", "java", "Sharable claude skills for the Quarkus Team (5 skills)", 5, "low"),
    ("quarkusio/skills", "java", "Agent skills for developing and maintaining Quarkus applications (3 skills)", 3, "med"),
    ("vaadin/agent-skills", "java", "Agent skills for helping coding agents build, style, test, and secure... (3 skills)", 3, "med"),
    # ecommerce (27 repos, 913 measured items)
    ("finsilabs/awesome-ecommerce-skills", "ecommerce", "178 skills", 178, "med"),
    ("40RTY-ai/shopify-admin-skills", "ecommerce", "Community-maintained AI agent skills for operating Shopify stores... (117 skills)", 117, "high"),
    ("Leooooooow/Awesome-eCommerce-Skills", "ecommerce", "97 skills", 97, "med"),
    ("internet-court/internet-court-skill", "ecommerce", "The trust layer for agent-to-agent commerce - natural-language... (72 skills)", 72, "high"),
    ("navarroido/Woocommerce-skill", "ecommerce", "56 skills", 56, "med"),
    ("furan917/magento-ai-toolkit", "ecommerce", "Collection of Agents and Skills for Magento (28 skills, 12 workflows)", 40, "med"),
    ("appeeky/stripe-skills", "ecommerce", "AI agent skills that make your assistant a full Stripe expert. Covers... (35 skills)", 35, "med"),
    ("maxnorm/magento2-agent-skills", "ecommerce", "A collection of specialized agent skills for Magento 2 development... (30 skills)", 30, "med"),
    ("OrcaQubits/agentic-commerce-skills-plugins", "ecommerce", "Skills & plugins for agentic commerce : UCP, ACP, AP2, A2A, WebMCP... (15 skills, 15 workflows)", 30, "med"),
    ("spree/agent-skills", "ecommerce", "Agent skills for Spree Commerce - works with Claude Code, Codex... (26 skills, 3 workflows)", 29, "high"),
    ("LokiCheckout/loki-checkout-ai-skills", "ecommerce", "AI skills for Loki Checkout (28 skills)", 28, "med"),
    ("hiberus-magento/ai-tools", "ecommerce", "AI-powered skills for Magento 2. This collection extends AI assistants... (16 skills, 7 workflows)", 23, "med"),
    ("Shopify/Shopify-AI-Toolkit", "ecommerce", "Agent plugins/extensions for CLIs and IDEs (21 skills)", 21, "high"),
    ("algolia/skills", "ecommerce", "Algolia skills for AI Agents (18 skills, 2 workflows)", 20, "high"),
    ("biggora/e-commerce-plugin-skills", "ecommerce", "AI skills for e-commerce plugin development (18 skills, 2 workflows)", 20, "med"),
    ("emartos/prestashop-skills", "ecommerce", "A collection of reusable ChatGPT skills for building, reviewing... (20 skills)", 20, "med"),
    ("Shopify/agent-skills", "ecommerce", "Shopify skills for agent collaboration (15 skills)", 15, "high"),
    ("amanamabasiakpan/Claude-Skills-for-eCommerce", "ecommerce", "eCommerce email marketing skill for Claude Code. Complete playbook for... (14 skills)", 14, "low"),
    ("bagisto/agent-skills", "ecommerce", "Bagisto's official collection of agent skills (12 skills)", 12, "high"),
    ("lvsao/shopify-skill-hub", "ecommerce", "Open-Source Shopify Skill Hub for Solopreneurs (12 skills)", 12, "low"),
    ("kgelster/awesome-ecom-skills", "ecommerce", "Shopify agency playbooks as Claude agent skills: catalog cleanup, SEO... (10 skills)", 10, "med"),
    ("magendooro/magento-claude-skills", "ecommerce", "Claude Code skills for Magento 2 / Adobe Commerce - interact with your... (10 skills)", 10, "med"),
    ("dodopayments/skills", "ecommerce", "Agent Skills for Dodo Payments (8 skills)", 8, "med"),
    ("saleor/agent-skills", "ecommerce", "5 skills", 5, "high"),
    ("tuanhaviet22/magento-skills", "ecommerce", "Magento 2 skills (5 skills)", 5, "low"),
    ("PrestaShop/skills", "ecommerce", "Set of skills for AI agents (3 skills)", 3, "med"),
    ("wiebekaai/ecommerce-skills", "ecommerce", "Claude Code skills for ecommerce management tasks (3 skills)", 3, "low"),
    # infra (28 repos, 869 measured items)
    ("MicrosoftDocs/Agent-Skills", "infra", "Curated Agent Skills for Microsoft & Azure - giving AI coding... (191 skills)", 191, "high"),
    ("BagelHole/DevOps-Security-Agent-Skills", "infra", "Agent-ready DevOps, security, infrastructure, and compliance knowledge... (163 skills)", 163, "med"),
    ("chaterm/terminal-skills", "infra", "Public Agent Skills for Terminal and Kubernetes (63 skills)", 63, "high"),
    ("Aidas-dev/k8s-agent-skills", "infra", "Agent skills for Kubernetes cluster operations - Cilium, Talos, Flux... (62 skills)", 62, "med"),
    ("grafana/skills", "infra", "49 skills", 49, "high"),
    ("aws-samples/sample-apex-skills", "infra", "Curated agentic AI skills for AWS platform engineering, delivered... (29 skills, 17 workflows)", 46, "med"),
    ("lgbarn/devops-skills", "infra", "DevOps skills for Claude Code: Terraform/OpenTofu workflows, AWS... (21 skills, 15 workflows)", 36, "med"),
    ("anmolnagpal/devops-skills", "infra", "Multi-tool DevOps skills for Claude Code, Cursor, and Codex... (18 skills, 17 rules)", 35, "med"),
    ("kcns008/cluster-skills", "infra", "A collection of skills for AI coding agents working with Kubernetes... (19 skills, 13 workflows)", 32, "med"),
    ("oci-ai-architects/cline-oci-ai-architect-skills", "infra", "Cline skills, rules, and workflows for AI Architects. Cross-platform... (14 skills, 2 rules, 11 workflows)", 27, "med"),
    ("qwedsazxc78/devops-ai-skill", "infra", "Cross-platform DevOps AI Skill Pack - Horus (IaC) + Zeus (GitOps)... (14 skills, 7 workflows)", 21, "med"),
    ("foxj77/claude-code-skills", "infra", "Claude Code skills for Kubernetes platform engineering, GitOps, and... (19 skills)", 19, "med"),
    ("pulumi/agent-skills", "infra", "15 skills", 15, "high"),
    ("sakiphan/claude-devops-skills", "infra", "11 skills", 11, "low"),
    ("stoleas/ansible-skills", "infra", "Comprehensive Ansible automation skills following Red Hat Communities... (11 skills)", 11, "low"),
    ("NotHarshhaa/devops-skills", "infra", "A collection of reusable DevOps Agent Skills for incident response... (10 skills)", 10, "low"),
    ("thomast1906/github-copilot-skills-terraform", "infra", "Template repository providing specialized GitHub Copilot agents and... (5 skills, 5 workflows)", 10, "med"),
    ("fluxcd/agent-skills", "infra", "Skills to transform AI Agents into GitOps Engineers (6 skills, 2 workflows)", 8, "high"),
    ("leogallego/claude-ansible-skills", "infra", "A collection of Claude Code skills for Ansible automation development... (7 skills)", 7, "med"),
    ("sysdig/skills", "infra", "Sysdig agentic AI skills and plugins (7 skills)", 7, "high"),
    ("ahmedasmar/devops-claude-skills", "infra", "A Claude Code Skills Marketplace for DevOps workflows (6 skills)", 6, "high"),
    ("antoniodiaz02/opencode-devops-skills", "infra", "DevOps Skills Collection for Claude Code and OpenCode - Terraform... (6 skills)", 6, "low"),
    ("openshift/agentic-skills", "infra", "OpenShift Container Platform skills for AI agents and OpenShift (5 skills)", 5, "low"),
    ("kubernetes-sigs/agent-sandbox", "infra", "agent-sandbox enables easy management of isolated, stateful, singleton... (4 skills)", 4, "med"),
    ("minio/skills", "infra", "Official MinIO Agent Skills - install with: npx skills add... (2 skills)", 2, "med"),
    ("LukasNiessen/kubernetes-skill", "infra", "Kubernetes Skill for Claude Code and Codex. LLMs hallucinate a lot... (1 skills)", 1, "med"),
    ("portainer/portainer-skills", "infra", "AI agent skills for Portainer (1 skills)", 1, "med"),
    # security (2 repos, 830 measured items)
    ("mukul975/Anthropic-Cybersecurity-Skills", "security", "817 structured cybersecurity skills for AI agents Mapped to 6... (817 skills)", 817, "high"),
    ("superagent-ai/skills", "security", "A collection of security skills (13 skills)", 13, "high"),
    # general (86 repos, 7249 measured items)
    ("affaan-m/ECC", "general", "The agent harness performance optimization system. Skills, instincts... (281 skills, 243 workflows)", 524, "high"),
    ("vibeeval/vibecosystem", "general", "AI software team for Claude Code - 138 agents, 295 skills, 73 hooks... (299 skills, 6 rules, 138 workflows)", 443, "high"),
    ("j4flmao/agent-skills", "general", "432 skills, 2 rules, 3 workflows", 437, "med"),
    ("asgard-ai-platform/skills", "general", "301 open-source coding agent skills across 22 domains - methodology... (314 skills)", 314, "high"),
    ("nWave-ai/nWave", "general", "AI agents that guide you from idea to working code, with you in... (151 skills, 130 workflows)", 281, "high"),
    ("shinpr/claude-code-workflows", "general", "Production-ready development workflows for Claude Code, powered by... (115 skills, 91 workflows)", 206, "high"),
    ("OneWave-AI/claude-skills", "general", "172 production-ready Claude Code skills for sales, marketing, design... (204 skills)", 204, "high"),
    ("doccker/cc-use-exp", "general", "Claude CodeAntigravityGemini CLICodexCursor  (143 skills, 7 rules, 48 workflows)", 198, "high"),
    ("wanshuiyin/Auto-claude-code-research-in-sleep", "general", "ARIS (Auto-Research-In-Sleep) - Lightweight Markdown-only skills for... (185 skills)", 185, "high"),
    ("rshankras/claude-code-apple-skills", "general", "Claude Code skills for Apple platform development (iOS, macOS, iPadOS)... (183 skills)", 183, "high"),
    ("nexscope-ai/eCommerce-Skills", "general", "E-commerce skills for AI agents - product research, marketing... (162 skills)", 162, "high"),
    ("Owl-Listener/designer-skills", "ui", "Designer Skills Collection: agentic skills, commands, and plugins for... (96 skills, 29 workflows)", 125, "high"),
    ("guanyang/open-agent-hub", "general", "A lightweight, zero-dependency CLI tool to manage and activate... (106 skills, 8 workflows)", 114, "high"),
    ("phuryn/pm-skills", "general", "PM Skills Marketplace: 100+ agentic skills, commands, and plugins... (68 skills, 42 workflows)", 110, "high"),
    ("browser-act/skills", "general", "Browser automation CLI built for AI agents. Break through anti-bot... (103 skills)", 103, "high"),
    ("forcedotcom/sf-skills", "general", "Salesforce's curated collection of agent skills for building... (102 skills)", 102, "high"),
    ("majiayu000/spellbook", "general", "Cross-runtime skills for Claude Code, Codex, and multi-agent workflows (90 skills, 8 workflows)", 98, "high"),
    ("openakita/openakita", "general", "An open-source AI assistant framework with skills and agent architecture (92 skills, 6 rules)", 98, "high"),
    ("google/skills", "general", "Agent Skills for Google products and technologies (96 skills)", 96, "high"),
    ("SpaceZephyr/myskill", "general", "95 skills", 95, "high"),
    ("dpearson2699/swift-ios-skills", "general", "Agent Skills for iOS 26+, Swift 6.3, SwiftUI, and modern Apple frameworks (86 skills)", 86, "high"),
    ("inference-sh/skills", "general", "inference.sh Agent skills for using our API to give your agents access... (86 skills)", 86, "high"),
    ("product-on-purpose/pm-skills", "general", "68 plug-and-play, best-practice product management skills for AI... (69 skills, 17 workflows)", 86, "high"),
    ("zhaoxuya520/reverse-skill", "general", "Reverse Engineering / Authorized Penetration Testing / Security... (83 skills)", 83, "high"),
    # "design" here is prompt/agent design (chain-of-thought-design, guardrail-
    # design, trust-calibration), not interface design -- hence `ai`, not `ui`.
    # est_items was 80: the old count read `claude-plugin/<pack>/commands/x.md`
    # and `commands/<pack>/x.md` as two commands rather than one mirrored pair.
    ("Owl-Listener/ai-design-skills", "ai", "AI Design Skills Collection: agentic skills, commands, and plugins for... (44 skills, 18 workflows)", 62, "high"),
    ("ninehills/skills", "general", "My LLM skills (78 skills)", 78, "high"),
    ("deanpeters/Product-Manager-Skills", "general", "Product Management skills framework built on battle-tested methods for... (70 skills, 6 workflows)", 76, "high"),
    ("jamditis/claude-skills-journalism", "general", "Claude Code skills for journalism, media, and academia - verification... (60 skills, 15 workflows)", 75, "high"),
    ("Houseofmvps/ultraship", "general", "'ULTRASHIP' Claude Code plugin - 39 skills, 33 tools, 11 agents for... (45 skills, 29 workflows)", 74, "high"),
    ("jame581/GodotPrompter", "general", "Agentic skills framework for Godot 4.x. Domain-specific skills for AI... (65 skills, 9 workflows)", 74, "high"),
    ("SamurAIGPT/Generative-Media-Skills", "general", "Multi-modal Generative Media Skills for AI Agents (Claude Code... (73 skills)", 73, "high"),
    ("tradermonty/claude-trading-skills", "general", "Claude Code skills for equity investors and traders - market analysis... (70 skills, 3 workflows)", 73, "high"),
    ("anbeime/skill", "general", "Skills 72 Github Skills Star (72 skills)", 72, "high"),
    ("JasonColapietro/suede-creator-skills", "general", "67 open-source Agent Skills for Claude Code and Codex: Full Send... (67 skills)", 67, "high"),
    ("first-fluke/oh-my-agent", "general", "Portable, vendor-agnostic agent harness for project-specific skills... (33 skills, 33 workflows)", 66, "high"),
    ("wondelai/skills", "general", "Wondel.ai Agent Skills - Business, Marketing, UX & Coding Frameworks... (62 skills, 1 rules)", 63, "high"),
    ("minhnv0807/ai-business-skills", "marketing", "Bilingual VN/global marketing SOP packs: plans, content calendars, campaign briefs, ad copy, reporting", 169, "high"),
    ("LigphiDonk/Oh-my--paper", "general", "A Claude Code plugin that turns your terminal into an autonomous... (35 skills, 26 workflows)", 61, "high"),
    ("AgriciDaniel/claude-ads", "marketing", "Paid-media operations across 12 ad platforms: audits, budgets, creative, landing pages, attribution", 59, "high"),
    ("whawkinsiv/solo-founder-skills", "general", "Skillset optimized for solo, bootstrapped, and non-technical founders... (58 skills, 1 workflows)", 59, "high"),
    ("Aperivue/medsci-skills", "general", "Agent Skills for medical research - literature search... (58 skills)", 58, "high"),
    ("briiirussell/cybersecurity-skills", "general", "Cybersecurity skills for AI coding agents (Claude Code, Cursor, Codex) (29 skills, 29 rules)", 58, "high"),
    ("Pluviobyte/rnskill", "general", "AI Agent Skills (56 skills)", 56, "high"),
    ("SethGammon/Citadel", "general", "The operating layer for Claude Code + OpenAI Codex: persistent project... (49 skills, 7 workflows)", 56, "high"),
    ("Affitor/affiliate-skills", "general", "50 AI agent skills for affiliate marketing. Research trending content... (54 skills)", 54, "high"),
    ("nanocoai/nanoclaw", "general", "A lightweight alternative to OpenClaw that runs in containers for... (54 skills)", 54, "high"),
    ("skydoves/android-testing-skills", "general", "A set of skills for Android testing: Compose UI, AndroidX Test, JVM... (54 skills)", 54, "high"),
    ("AlpacaLabsLLC/skills-for-architects", "general", "Claude Code skills for architecture, real estate, and workplace... (46 skills, 7 workflows)", 53, "high"),
    ("steipete/agent-scripts", "general", "Scripts for agents, shared between my repositories (53 skills)", 53, "high"),
    ("luongnv89/claude-howto", "general", "A visual, example-driven guide to Claude Code - from basic concepts to... (31 skills, 20 workflows)", 51, "high"),
    ("swyxio/skills", "general", "Agent skills for Claude Code and other AI agents (46 skills)", 46, "high"),
    ("AgriciDaniel/claude-seo", "marketing", "Technical and content SEO: audits, backlinks, schema, clustering, local, international and ecommerce", 51, "high"),
    ("diegosouzapw/OmniRoute", "general", "Never stop coding. Free MIT AI gateway: one endpoint, 290+ providers... (45 skills)", 45, "high"),
    ("intellectronica/agent-skills", "general", "@intellectronica's agent skills (44 skills)", 44, "high"),
    ("davidondrej/skills", "general", "access to david ondrej's personal agent skills (42 skills)", 42, "high"),
    ("xuzhougeng/wisp-science", "general", "Open-source, local-first desktop AI research workbench for scientific... (42 skills)", 42, "high"),
    ("besoeasy/open-skills", "general", "Battle-tested skill library for AI agents. Save 98% of API costs with... (40 skills)", 40, "high"),
    ("butterbase-ai/butterbase-skills", "general", "Plugin for Butterbase.ai (40 skills)", 40, "high"),
    ("Eronred/aso-skills", "general", "AI agent skills for App Store Optimization (ASO) and app marketing... (40 skills)", 40, "high"),
    ("Ar9av/obsidian-wiki", "general", "Framework for AI agents to build and maintain a digital brain through... (37 skills, 1 rules, 1 workflows)", 39, "high"),
    ("Ed1s0nZ/CyberStrikeAI", "general", "The system of action for AI-native cybersecurity-where intent becomes... (23 skills, 16 workflows)", 39, "high"),
    ("modiqo/skillspec", "general", "SkillSpec makes agent skills followable, testable, and provable with... (39 skills)", 39, "high"),
    ("mrgoonie/claudekit-skills", "general", "All powerful skills of ClaudeKit.cc! (31 skills, 8 workflows)", 39, "high"),
    ("NTCoding/claude-skillz", "general", "Random Claude skills for common, simple programming tasks (22 skills, 17 workflows)", 39, "high"),
    ("AgriciDaniel/claude-blog", "general", "Claude Code blog skill suite: 30 sub-skills, 5 agents, 5-gate v1.9.0... (33 skills, 5 workflows)", 38, "high"),
    ("jvm-skills/jvm-skills", "general", "36 skills", 36, "high"),
    ("24kchengYe/human-skill-tree", "general", "AI-Powered Skill Tree for Lifelong Human Learning. 30+ skills from... (34 skills)", 34, "high"),
    ("EveryInc/compound-engineering-plugin", "general", "Official Compound Engineering plugin for Claude Code, Codex, Cursor... (32 skills, 1 workflows)", 33, "high"),
    ("microsoft/azure-skills", "general", "Official agent plugin providing skills and MCP server configurations... (33 skills)", 33, "high"),
    ("OthmanAdi/planning-with-files", "general", "Persistent file-based planning for AI coding agents and long-running... (18 skills, 15 workflows)", 33, "high"),
    ("bear2u/my-skills", "general", "32 skills", 32, "high"),
    ("beshuaxian/higgsfield-seedance2-jineng", "general", "Seedance 2.0 Higgsfield | 15 Claude prompt skills for AI video... (30 skills)", 30, "high"),
    ("Dynatrace/dynatrace-for-ai", "general", "Skills, prompts, and instructions for building AI agents on top of... (30 skills)", 30, "high"),
    ("getsentry/skills", "general", "Agent Skills used by the Sentry team for development (28 skills, 2 workflows)", 30, "high"),
    ("zrt-ai-lab/opencode-skills", "general", "OpenCode/Claude Code AI Agent (30 skills)", 30, "high"),
    ("OpenSenseNova/SenseNova-Skills", "general", "Modular SenseNova skills for building AI-powered office assistants and... (29 skills)", 29, "high"),
    ("staskh/trading_skills", "general", "Claude powered advisor system for option traders (28 skills)", 28, "high"),
    ("chujianyun/skills", "general", "WuMing's Claude Skills (26 skills, 1 workflows)", 27, "high"),
    ("quodsoler/unreal-engine-skills", "general", "Unreal Engine C++ skills for AI coding agents. 27 skills covering... (27 skills)", 27, "high"),
    ("Soju06/codex-lb", "general", "Codex/ChatGPT multiple account load balancer & proxy with usage... (17 skills, 10 workflows)", 27, "high"),
    ("Weizhena/Deep-Research-skills", "general", "Structured deep research skill for Claude Code/Open Code/Codex with... (20 skills, 7 workflows)", 27, "high"),
    ("gaasher/Agent-Loop-Skills", "general", "Loop until it's better - drop-in agentic loops (autoresearch... (25 skills)", 25, "high"),
    ("cloudflare/skills", "general", "Skills for teaching agents how to build on Cloudflare (11 skills, 1 rules, 2 workflows)", 14, "high"),
    ("obra/superpowers", "general", "An agentic skills framework & software development methodology that works (14 skills)", 14, "high"),
    ("ReScienceLab/opc-skills", "general", "Agent Skills for Solopreneurs (13 skills)", 13, "high"),
    ("multica-ai/andrej-karpathy-skills", "general", "A single CLAUDE.md file to improve Claude Code behavior, derived from... (1 skills, 1 rules)", 2, "med"),
    # meta (26 repos, 4528 measured items)
    ("composio-community/awesome-codex-skills", "meta", "A curated list of practical Codex skills for automating workflows... (880 skills)", 880, "high"),
    ("github/awesome-copilot", "meta", "Community-contributed instructions, agents, skills, and configurations... (395 skills, 239 workflows)", 634, "high"),
    ("Microck/ordinary-claude-skills", "meta", "An unappealing collection of Claude Skills and resources (416 skills)", 416, "high"),
    ("PramodDutta/qaskills", "meta", "QA Skills Directory QA Skills is a curated directory of... (416 skills)", 416, "high"),
    # Reads like an index, ships a corpus: 390 single-purpose front-end checks
    # (`aria-*`, `accessible-*`, `alt-text`), so it is `ui`, not `meta`.
    ("thedaviddias/Front-End-Checklist", "ui", "The essential checklist for modern web development, for humans and AI... (390 skills)", 390, "high"),
    ("rmyndharis/antigravity-skills", "meta", "A curated collection of Agent Skills for Google Antigravity (306 skills)", 306, "high"),
    ("pproenca/dot-skills", "meta", "A collection of AI agent skills following the Agent Skills open format (207 skills)", 207, "high"),
    ("indranilbanerjee/digital-marketing-pro", "meta", "Open-source AI marketing plugin for agencies & in-house teams - 158... (158 skills, 42 workflows)", 200, "high"),
    ("claude-office-skills/skills", "meta", "A curated collection of practical Claude Skills for real-world office... (137 skills, 1 rules, 6 workflows)", 144, "high"),
    ("mohitmishra786/low-level-dev-skills", "meta", "A curated suite of AI agent skills for systems and low-level... (142 skills)", 142, "high"),
    ("glebis/claude-skills", "meta", "Collection of Claude Code skills for enhanced AI workflows (109 skills)", 109, "high"),
    ("elementalsouls/Claude-BugHunter", "meta", "A Claude Code skill bundle for bug hunting and external red-team work... (82 skills, 15 workflows)", 97, "high"),
    # Every item is a visual style -- `brutalism`, `claymorphism`, `bento`,
    # `editorial` -- which is why the item names, not the blurb, decided it.
    ("bergside/awesome-design-skills", "ui", "List of 67 awesome DESIGN.md and SKILL.md design skill files for... (67 skills)", 67, "high"),
    ("spencerpauly/awesome-cursor-skills", "meta", "A curated list of awesome skills for Cursor (65 skills)", 65, "high"),
    ("SnailSploit/Claude-Red", "meta", "claude-red is a curated library of offensive security skills designed... (58 skills)", 58, "high"),
    ("bobmatnyc/claude-mpm-skills", "meta", "Curated collection of Claude Code skills for intelligent project... (57 skills)", 57, "high"),
    ("nexscope-ai/Amazon-Skills", "meta", "Free AI agent skills for Amazon sellers- keyword research, competitor... (52 skills)", 52, "high"),
    ("samber/cc-skills-golang", "meta", "A collection of Golang agentic skills that works (46 skills)", 46, "high"),
    ("jdrhyne/agent-skills", "meta", "A collection of AI agent skills for Clawdbot, Claude Code, Codex (34 skills)", 34, "high"),
    ("mxyhi/ok-skills", "meta", "Curated AI coding agent skills and AGENTS.md playbooks for Codex... (34 skills)", 34, "high"),
    ("nimrodfisher/data-analytics-skills", "meta", "A comprehensive list of Claude skills for a wide range of data... (33 skills)", 33, "high"),
    ("Prat011/awesome-llm-skills", "meta", "A curated list of awesome LLM and AI Agent Skills, resources and tools... (31 skills)", 31, "high"),
    ("lingxling/awesome-skills-cn", "meta", "Skillscn+7000+Skillsclaude skills (11w+Star) | awesome-openclaw-skills... (29 skills, 1 workflows)", 30, "high"),
    ("Paramchoudhary/ResumeSkills", "meta", "A collection of AI agent skills focused on resume optimization, job... (29 skills)", 29, "high"),
    ("QinghongLin/data2story-skill", "meta", "Data Journalist Agent: Transforming Data into Verifiable Multimodal Story (29 skills)", 29, "high"),
    ("muratcankoylan/Agent-Skills-for-Context-Engineering", "meta", "A comprehensive collection of Agent Skills for context engineering... (22 skills)", 22, "high"),
    # --- end 2026-07 batch ---
    # --- 2026-08 batch: design/taste packs, plus one framework repo ---------
    # est_items measured with scripts/measure_registry.py, which counts an item
    # once however many agents it is rendered for. That matters here more than
    # in earlier batches: these packs ship a copy per agent dotdir, so a raw
    # walk of pbakaus/impeccable reports 40 items for the handful it has.
    ("pbakaus/impeccable", "ui", "The design language that makes your AI harness better at design - shape/critique/polish plus finish-review, asset and documenter subagents, rendered for 14 agents (2 skills, 7 workflows)", 9, "high"),
    ("Leonxlnx/taste-skill", "ui", "Anti-slop design taste: high-end visual direction, brutalist and minimalist UI kits, image-to-code, brand kits (13 skills)", 13, "high"),
    ("alchaincyf/huashu-design", "ui", "Huashu Design - HTML-native design skill: hi-fi prototypes, slides, animation, 20 design philosophies, 5-axis review, MP4 export (1 skills)", 1, "high"),
    # Not a registry by intent: the framework repo ships agent skills next to
    # the product (packages/playwright-core/src/tools/skills) and the Playwright
    # Agents that `playwright init-agents` installs. Tapping it clones the whole
    # framework, so it is worth it for the planner/generator/healer, not as a
    # cheap pull.
    ("microsoft/playwright", "devops", "Official Playwright repo - the agent skills it ships (CLI, trace, component testing) plus the test planner/generator/healer agents (7 skills, 11 workflows)", 18, "high"),
    # --- end 2026-08 batch ---

# --- marketing / CRM / email / outreach (2026-08 sweep) ----------------------
# Registries whose *items* are named `cold-email`, `email-sequence`,
# `crm-integration`, `hubspot-setup`, `apollo-outreach`, `lead-routing`. The
# sweep read item names, never READMEs: every repo here describes itself as
# "skills for Claude Code / Cursor / Codex" first, which is why four of them
# were already carried under `writing` and `general`. Counts are
# `scripts/measure_registry.py` against a fresh clone, so a repo that renders
# one copy per agent is credited once. Ordered by adoption within the batch;
# the CRM rows are the least-starred and the most load-bearing, since they are
# the only coverage the domain has for the CRM half of its own name.
    ("zubair-trabzada/geo-seo-claude", "marketing", "GEO / AI-search optimisation: citability scoring, AI-crawler analysis, schema, brand mentions", 21, "high"),
    ("ericosiu/ai-marketing-skills", "marketing", "Growth experiments, cold outbound, sales pipeline, content ops and revenue intelligence", 27, "high"),
    ("nowork-studio/notfair-plugin", "marketing", "SEO, GEO and Google/Meta ads: keyword research, audits, ad copy, landing pages, analytics", 90, "high"),
    ("aaron-he-zhu/aaron-marketing-skills", "marketing", "Marketing staff across narrative, SEO/GEO, social, email, paid, influencer and launch, with auditor gates", 128, "high"),
    ("zubair-trabzada/ai-marketing-claude", "marketing", "Site audit through to email sequences, ad campaigns, content calendars and client-ready reports", 20, "high"),
    ("zubair-trabzada/ai-sales-team-claude", "marketing", "Sales outreach workflow: ICP, prospecting, qualification, objection handling, follow-up", 19, "high"),
    ("LeoYeAI/openclaw-marketing-skills", "marketing", "Cold email, email sequences, churn prevention, CRO, copywriting and paid ads", 39, "high"),
    ("kostja94/marketing-skills", "marketing", "SEO, content, 40+ page-type generators, paid ads, channel and growth strategy", 172, "high"),
    ("OpenClaudia/openclaudia-skills", "marketing", "SEO, content, email, ads, analytics and growth, including Apollo outreach and backlink audits", 75, "high"),
    ("zapier/gtm-cheat-codes", "marketing", "GTM field guide: campaign planning, cross-CRM opportunity sync, customer proof, lead stewardship", 21, "high"),
    ("Othmane-Khadri/YALC-the-GTM-operating-system", "marketing", "GTM operating system: campaign strategy, multi-touch copywriting sequences, CRM and sequencer adapters", 61, "high"),
    ("Cold-IQ/ColdIQ-s-GTM-Skills", "marketing", "Cold email sequences, ABM messaging, buying signals, list building and deliverability", 90, "high"),
    ("LeadMagic/gtm-skills", "marketing", "CRM setup and hygiene (Salesforce, HubSpot, Attio), enrichment, AI SDR, ABM and lifecycle", 206, "high"),
    ("NEON-Rutger/B2B-revops-skills", "marketing", "B2B RevOps: CRM migration, lead routing, deal desk, pipeline visibility, ICP and forecasting", 38, "high"),
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
    # --- 2026-07 batch: AI, architecture, UI, Java, eCommerce, infra ---
    # ai (1 repos, 2 measured items)
    ("wandb/agentic-support-bot-demo", "ai", "A streamlined guide to experience how Weave works in a typical AI... (2 rules)", 2, "med"),
    # architecture (1 repos, 1 measured items)
    ("ddd-crew/ai-ddd-prompts-and-rules", "architecture", "DDD-related prompts and rules to use with your favourite coding assistants (1 rules)", 1, "low"),
    # ui (1 repos, 14 measured items)
    ("aliarghyani/vue-cursor-rules", "ui", "A collection of Cursor IDE rules tailored for Vue.js (14 rules)", 14, "low"),
    # infra (1 repos, 61 measured items)
    ("sparesparrow/cursor-rules", "infra", "A library of rules for the Cursor IDE, providing organized... (61 rules)", 61, "med"),
    # --- end 2026-07 batch ---
]

# --- workflows (Claude Code commands / subagents) ---------------------------
WORKFLOWS = [
    ("gtmagents/gtm-agents", "marketing", "GTM agents and commands for sales, marketing, customer success and revenue operations", 653, "high"),
    ("aitytech/agentkits-marketing", "marketing", "Marketing-automation commands and agents: campaigns, ads, analytics, content ops", 399, "high"),
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
    # --- 2026-07 batch: AI, architecture, UI, Java, eCommerce, infra ---
    # ai (10 repos, 63 measured items)
    ("anthropics/claude-code", "ai", "Claude Code is an agentic coding tool that lives in your terminal... (33 workflows)", 33, "high"),
    ("anthropics/claude-code-action", "ai", "8 workflows", 8, "high"),
    ("anthropics/claude-agent-sdk-demos", "ai", "Claude Code SDK Demos (5 workflows)", 5, "high"),
    ("anthropics/claude-agent-sdk-python", "ai", "1 skills, 4 workflows", 5, "high"),
    ("comet-ml/opik-claude-code-plugin", "ai", "Log Claude Code sessions to Opik, the open-source LLM observability... (2 skills, 3 workflows)", 5, "high"),
    ("langchain-ai/deepagents", "ai", "The batteries-included agent harness (2 workflows)", 2, "med"),
    ("zenml-io/skills", "ai", "AI coding agent skills for ZenML MLOps workflows - quick wins... (2 workflows)", 2, "med"),
    ("anthropics/claude-agent-sdk-typescript", "ai", "1 workflows", 1, "med"),
    ("anthropics/claude-code-security-review", "ai", "An AI-powered security review GitHub Action using Claude to analyze... (1 workflows)", 1, "med"),
    ("anthropics/cwc-long-running-agents", "ai", "1 workflows", 1, "med"),
    # architecture (2 repos, 21 measured items)
    ("codenamev/ai-software-architect", "architecture", "AI-powered architecture documentation framework with ADRs, reviews... (7 skills, 5 rules, 8 workflows)", 20, "high"),
    ("DavidROliverBA/Daves-Claude-Code-Skills", "architecture", "Reusable Claude Code skills for architecture, diagramming, and... (1 workflows)", 1, "med"),
    # ui (3 repos, 447 measured items)
    ("Community-Access/accessibility-agents", "ui", "Accessibility review agents for Claude Code, GitHub Copilot, and... (111 skills, 268 workflows)", 379, "high"),
    ("pluginagentmarketplace/custom-plugin-nextjs", "ui", "Next.js Development Plugin (18 skills, 24 workflows)", 42, "med"),
    ("klovaaxel/web-a11y-agent-skills", "ui", "Framework-agnostic web accessibility skills and Cursor subagents for... (10 skills, 16 workflows)", 26, "med"),
    # java (3 repos, 50 measured items)
    ("pluginagentmarketplace/custom-plugin-kotlin", "java", "Kotlin Development Plugin (12 skills, 16 workflows)", 28, "med"),
    ("ducpm2303/claude-java-plugins", "java", "Java developer toolkit for Claude Code - skills, agents, hooks, and... (11 workflows)", 11, "med"),
    ("piomin/claude-ai-spring-boot", "java", "Claude Code template for Spring Boot and other staff (included in the... (5 skills, 6 workflows)", 11, "high"),
    # infra (4 repos, 99 measured items)
    ("cloudflare/agents", "infra", "Build and deploy AI Agents on Cloudflare (2 skills, 40 workflows)", 42, "high"),
    ("eclosion-labs/terraform-cursor-plugin", "infra", "Cursor plugin for terraform (17 skills, 24 workflows)", 41, "med"),
    ("glapsfun/cnative-skills", "infra", "Agentic skills for cloud-native tools (1 skills, 13 workflows)", 14, "low"),
    ("docker/claude-plugins", "infra", "2 workflows", 2, "med"),
    # general (25 repos, 2627 measured items)
    ("davepoon/buildwithclaude", "general", "A single hub to find Claude Skills, Agents, Commands, Hooks, Plugins... (763 workflows)", 763, "high"),
    ("xu-xiang/everything-claude-code-zh", "general", "everything-claude-code Claude Code agents, skills, hooks, commands... (81 skills, 194 workflows)", 275, "high"),
    ("athola/claude-night-market", "general", "23 Claude Code plugins: TDD enforcement hooks, git/PR workflows... (15 skills, 194 workflows)", 209, "high"),
    ("zebbern/claude-code-guide", "general", "Claude Code Guide - Setup, Commands, workflows, agents, skills &... (79 skills, 109 workflows)", 188, "high"),
    ("Donchitos/Claude-Code-Game-Studios", "general", "Turn Claude Code into a full game dev studio - 49 AI agents, 72... (73 skills, 83 workflows)", 156, "high"),
    ("Galaxy-Dawn/claude-scholar", "general", "Semi-automated research assistant for academic research and software... (45 skills, 70 workflows)", 115, "high"),
    ("secondsky/claude-skills", "general", "Production-ready skills for Claude Code CLI - Cloudflare, React... (1 skills, 106 workflows)", 107, "high"),
    ("Yeachan-Heo/oh-my-claudecode", "general", "Teams-first Multi-agent orchestration for Claude Code (41 skills, 49 workflows)", 90, "high"),
    ("giuseppe-trisciuoglio/developer-kit", "general", "Modular plugin marketplace for Claude Code and agentic CLIs, with... (82 workflows)", 82, "high"),
    ("nth5693/gemini-kit", "general", "19 AI Agents + 44 Commands for Gemini CLI - Code 10x faster with auto... (15 skills, 58 workflows)", 73, "high"),
    ("sangrokjung/claude-forge", "general", "Supercharge Claude Code with 11 AI agents, 36 commands & 15 skills... (26 skills, 45 workflows)", 71, "high"),
    ("hoangsonww/Claude-Code-Agent-Monitor", "general", "A real-time monitoring dashboard for Claude Code, built with SQLite3... (12 skills, 47 workflows)", 59, "high"),
    ("dsifry/metaswarm", "general", "A self-improving multi-agent orchestration framework for Claude Code... (14 skills, 44 workflows)", 58, "high"),
    ("jezweb/claude-skills", "general", "Skills for Claude Code CLI such as full stack dev Cloudflare, React... (58 workflows)", 58, "high"),
    ("trailofbits/skills", "general", "Trail of Bits Claude Code skills for security research, vulnerability... (44 workflows)", 44, "high"),
    ("syahiidkamil/Software-Engineer-AI-Agent-Atlas", "general", "ATLAS: a senior-engineer layer for Claude Code. Explore with... (20 skills, 21 workflows)", 41, "high"),
    ("alirezarezvani/claude-code-skill-factory", "general", "Claude Code Skill Factory - A powerful open-source toolkit for... (14 skills, 25 workflows)", 39, "med"),
    ("datopian/portaljs", "general", "AI-native framework for building data portals. Scaffold a full portal... (14 skills, 25 workflows)", 39, "high"),
    ("humanlayer/humanlayer", "general", "The best way to get AI coding agents to solve hard problems in complex... (34 workflows)", 34, "high"),
    ("darrenhinde/OpenAgentsControl", "general", "AI agent framework for plan-first development workflows with... (5 skills, 27 workflows)", 32, "high"),
    ("dotnet/skills", "general", "Repository for skills to assist AI coding agents with .NET and C# (5 skills, 26 workflows)", 31, "high"),
    ("centminmod/my-claude-code-setup", "general", "Shared starter template configuration and CLAUDE.md memory bank system... (7 skills, 1 rules, 20 workflows)", 28, "high"),
    ("hnaymyh123-henry/claude-dev-skill", "general", "A Claude Code custom skill that turns Claude into a Tech Lead... (26 workflows)", 26, "high"),
    ("anthropics/financial-services", "general", "8 workflows", 8, "high"),
    ("jeremylongshore/claude-code-plugins-plus-skills", "general", "471 plugins, 3,069 skills, 347 agents for Claude Code. Open-source... (1 workflows)", 1, "med"),
    # meta (7 repos, 1133 measured items)
    ("loulanyue/awesome-claude-notes", "meta", "Community-maintained distribution of reusable AI coding agents... (135 skills, 648 workflows)", 783, "high"),
    ("agentlas-ai/Agentlas-OS", "meta", "Agent OS: keep specialist agents in a hub, spin up a temporary... (48 skills, 2 rules, 62 workflows)", 112, "high"),
    ("composio-community/awesome-claude-plugins", "meta", "A curated list of Plugins that let you extend Claude Code with custom... (23 skills, 38 workflows)", 61, "high"),
    ("anthropics/claude-plugins-official", "meta", "Official, Anthropic-managed directory of high quality Claude Code Plugins (60 workflows)", 60, "high"),
    ("glittercowboy/taches-cc-resources", "meta", "A collection of my favorite custom Claude Code resources to make life... (12 skills, 42 workflows)", 54, "high"),
    ("anthropics/claude-cookbooks", "meta", "A collection of notebooks/recipes showcasing some fun and effective... (4 skills, 11 workflows)", 15, "high"),
    # --- end 2026-07 batch ---
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


def verify_live(names: list[str], token: str | None = None) -> int:
    """Report which of ``names`` no longer resolve on GitHub.

    Deliberately NOT part of `--check` or any required gate. The lesson
    `tests/eval/taps.txt` already records — pin third-party repos, never let
    someone else's push decide whether our build is green — applies here twice
    over: a required check that queries 470 repos would go red the day any one
    of them is deleted, which is a fact about GitHub rather than about this
    commit. Run it when curating, and record what it finds in RETIRED.

    Returns the number of repos that could not be resolved.
    """
    import http.client
    import urllib.error
    import urllib.request

    missing, archived = [], []
    for i, name in enumerate(names, 1):
        req = urllib.request.Request(  # noqa: S310  the https prefix is a literal
            "https://api.github.com/repos/%s" % name,
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "boost-registry-audit"})
        if token:
            req.add_header("Authorization", "token %s" % token)
        try:
            with urllib.request.urlopen(req, timeout=30) as fh:  # noqa: S310  same
                if json.loads(fh.read().decode("utf-8")).get("archived"):
                    archived.append(name)
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 451):
                missing.append(name)
            else:                       # rate limit, transient 5xx — not a verdict
                print("  ? %-50s HTTP %s" % (name, exc.code), file=sys.stderr)
        except (OSError, http.client.HTTPException,
                json.JSONDecodeError) as exc:
            # A truncated response is a fact about the network, not about the
            # repo — 470 sequential requests will hit one, and a sweep that
            # aborts on it reports "clean" for everything it never reached.
            print("  ? %-50s %s" % (name, exc), file=sys.stderr)
        if i % 50 == 0:
            print("  ...%d/%d" % (i, len(names)), file=sys.stderr)

    for name in archived:
        print("archived  %s" % name)
    for name in missing:
        print("MISSING   %s" % name)
    print("%d checked: %d missing, %d archived"
          % (len(names), len(missing), len(archived)), file=sys.stderr)
    return len(missing)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="verify the committed JSON matches a fresh build; exit 1 on drift "
             "(does not write). Used in CI to catch un-regenerated edits.",
    )
    parser.add_argument(
        "--verify-live", action="store_true",
        help="ask GitHub whether every shipped registry still exists and print "
             "the ones that do not. Needs network; never part of a gate. Set "
             "GITHUB_TOKEN to lift the 60/hour anonymous rate limit.",
    )
    args = parser.parse_args(argv)

    payload = build_payload()
    fresh = render(payload)

    if args.verify_live:
        import os
        names = [e["name"] for e in payload["registries"]]
        return 1 if verify_live(names, os.environ.get("GITHUB_TOKEN")) else 0

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
