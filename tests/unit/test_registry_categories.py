# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Curation guarantees for the bundled registry catalog's focus domains.

``boost tap --catalog --category <slug>`` is only worth offering if every
advertised domain actually has registries behind it, so the seven focus domains
below are contract, not incident: AI engineering, architecture, UI, Java/Spring,
eCommerce, container/cluster infrastructure, and marketing/CRM.

The floors are deliberately set below the committed numbers — ordinary additions
never trip them, but deleting a domain's repos, renaming a category slug, or
regenerating from a truncated source tuple does. Shape invariants that apply to
every row (type, url, focus, est_items) live in ``test_config.py``; this module
owns the *coverage* half and the source-tuple invariants the generator upholds.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from boost_cli.core import config

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "build_registries.py"

# slug -> (minimum repos, human name). Slugs are the user-facing --category
# values, so a rename here is a breaking change to a documented flag.
FOCUS = {
    "ai": (8, "AI engineering (RAG, evals, tracing, serving)"),
    "architecture": (5, "software architecture"),
    "ui": (8, "UI, visualization, and TUI"),
    "java": (5, "Java / Spring Boot"),
    "ecommerce": (5, "eCommerce platforms"),
    "infra": (8, "containers, clusters, and networking"),
    "marketing": (14, "marketing, CRM, email campaigns, and customer outreach"),
    "backend": (30, "backend services, databases, APIs, and durable execution"),
}

# Repos whose whole reason to exist is visual/UI design work, pinned by name.
# The 2026-08 sweep that filed them scored the *names of the items they ship*,
# never their READMEs, and that is why they are pinned: nothing in
# `bergside/awesome-design-skills`'s prose says UI, but its 67 items are called
# `brutalism`, `claymorphism`, `bento` and `editorial`; `Front-End-Checklist`
# reads like an index but ships 390 `aria-*`/`accessible-*` checks. Both sat in
# `meta` until the item names were read.
UI_PINNED = {
    "pbakaus/impeccable",
    "Leonxlnx/taste-skill",
    "nextlevelbuilder/ui-ux-pro-max-skill",
    "alchaincyf/huashu-design",
    "Owl-Listener/designer-skills",
    "thedaviddias/Front-End-Checklist",
    "bergside/awesome-design-skills",
}

# The counter-example, and the reason the sweep reads item names rather than
# repo names: this one's "design" is *AI* design — `chain-of-thought-design`,
# `guardrail-design`, `prompt-versioning`, `trust-calibration`. Any rule keyed
# on the repo name would file it `ui`; it belongs to `ai`.
AI_NOT_UI = "Owl-Listener/ai-design-skills"

# The same trap, in the other direction: this one's "architecture" is
# buildings. It ships `nyc-dob-permits`, `epd-parser`, `ffe-spec-book` and
# `occupancy-calculator`, and `architecture` here means *software*
# architecture (FOCUS). No category fits AEC or real estate, so the pin is
# only that it stays out of the one its name suggests.
BUILDINGS_NOT_SOFTWARE = "AlpacaLabsLLC/skills-for-architects"

# And the self-description trap: nWave calls itself a framework, but
# `framework` holds language/framework coding-standard rule packs (.NET,
# Godot, PHP/Laravel). Its items are an agent methodology — `nw-product-owner`,
# `nw-software-crafter`, `nw-lane-orchestrator`, each role with a `-reviewer`
# twin — the same shape as obra/superpowers and SethGammon/Citadel in `meta`.
METHODOLOGY_NOT_FRAMEWORK = "nWave-ai/nWave"

# Token-efficiency registries: repos whose items exist to make an agent emit
# *less* — less code, or fewer output tokens. Both were filed by reading item
# names (`ponytail-audit`, `ponytail-debt`, `ponytail-gain`; `caveman-compress`,
# `caveman-stats`), never the README, which is why they are pinned. Each has a
# README that reads like general-purpose coding advice, and `general` is where
# a keyword scorer would drop them — losing the one axis they share.
EFFICIENCY_PINNED = {
    "DietrichGebert/ponytail",
    "JuliusBrussee/caveman",
}

# Measured with `scripts/measure_registry.py`, not walked: both repos render a
# copy of each item per agent they support. Raw `scan_dir` walks find 13 and 43.
# caveman was (21, 28) until it shipped 16 more skills; re-measured 2026-11-07.
EFFICIENCY_MEASURED = {
    "DietrichGebert/ponytail": (7, 13),
    "JuliusBrussee/caveman": (35, 43),
}

# `pbakaus/impeccable` vendors one copy of each item into every agent dir it
# supports (`.claude/`, `.cursor/`, `.gemini/`, `.github/`, `.grok/`, …), so a
# naive walk reports this many items for the handful it actually ships.
IMPECCABLE_MIRRORED_WALK = 40

# The batch this file was written for: the seven focus domains together must carry
# at least this many estimated *scannable* items (list-only index repos excluded).
FOCUS_SCANNABLE_FLOOR = 5000

# Marketing/CRM registries, pinned by name. The 2026-08 sweep that filed them
# scored the *names of the items they ship*: `cold-email`, `email-sequence`,
# `crm-integration`, `hubspot-setup`, `apollo-outreach`, `lead-routing`. Four of
# them were already in the catalog under `writing` or `general` — categories a
# README-keyed scorer lands on, because every one of these repos describes
# itself as "skills for AI agents" before it says what the skills do. Filed
# there, `boost tap --catalog --category marketing` returned nothing at all.
MARKETING_PINNED = {
    "coreyhaines31/marketingskills",
    "minhnv0807/ai-business-skills",
    "AgriciDaniel/claude-ads",
    "AgriciDaniel/claude-seo",
}

# The user-facing promise of the domain is four sub-domains, not one, and the
# rank-by-stars cut kept dropping the CRM half: the CRM registries are the
# smallest and least-starred of the batch (42 and 45 stars against 45,374 for
# the top marketing pack), so a purely popularity-ordered top-20 covers
# marketing and email and silently ships a `marketing` category with no CRM in
# it. Each sub-domain therefore names the registry that carries it.
MARKETING_SUBDOMAIN = {
    "crm": "LeadMagic/gtm-skills",              # salesforce/hubspot/attio setup
    "revops": "NEON-Rutger/B2B-revops-skills",  # crm-migration, lead-routing
    "cold-outreach": "Cold-IQ/ColdIQ-s-GTM-Skills",   # cold-email sequences
    "campaigns": "zapier/gtm-cheat-codes",      # cross-crm-opportunity-sync
}

# Measured with `scripts/measure_registry.py` against a fresh clone, not
# inherited from the row that was already there. Both stale counts were the
# repo's own README figure from an earlier release — `marketingskills` had
# grown 10 -> 50 items and `ai-business-skills` 62 -> 169 — so re-filing a row
# without re-measuring it would have carried a two-release-old number into a
# domain advertised as measured.
MARKETING_MEASURED = {
    "coreyhaines31/marketingskills": 50,
    "minhnv0807/ai-business-skills": 169,
}

# Rows refiled on 2026-11-07 by the names of the items they ship, each with
# the count `scripts/measure_registry.py` gave on a sparse clone taken that
# day. An item with no category of its own inherits its row's, so a row filed
# by its README or its fame mislabels every item in it.
RECATEGORISED = {
    # 17 of its 20 items are documents and design: docx, pdf, pptx, xlsx,
    # canvas-design, algorithmic-art, brand-guidelines, theme-factory. Only
    # claude-api, mcp-builder and skill-creator are AI. Filed `ai`, it
    # answered `search "fine-tune an LLM with LoRA" --category ai` with
    # brand-guidelines and algorithmic-art.
    "anthropics/skills": ("general", 20),
    # awq-quantization, deepspeed, fine-tuning-with-trl, llama-factory, dspy.
    "Orchestra-Research/AI-Research-SKILLs": ("ai", 98),
    # huggingface-llm-trainer, trl-training, huggingface-vision-trainer.
    "huggingface/skills": ("ai", 26),
    # aks-* and azure-* SDK clients; 148 of 232 names start with azure-.
    "microsoft/skills": ("infra", 231),
    # tdd, code-review, grill-me, handoff, writing-*: no web framework at all.
    "mattpocock/skills": ("general", 40),
    # spec, plan, build, test, review, ship: a lifecycle, not CI/CD.
    "addyosmani/agent-skills": ("general", 38),
    # Generative media models, filed with replicate and elevenlabs.
    "fal-ai-community/skills": ("ai", 36),
    # context-compression, memory-systems, multi-agent-patterns: the
    # Owl-Listener/ai-design-skills precedent.
    "muratcankoylan/Agent-Skills-for-Context-Engineering": ("ai", 24),
    # These three were filed `workflow`, which is an item kind: `tap --catalog
    # --category workflow` and `--type workflow` were one word naming two
    # different sets. Each is an agent methodology, like nWave in `meta`.
    "rsmdt/the-startup": ("meta", 50),
    "shinpr/claude-code-workflows": ("meta", 66),
    "garrytan/gstack": ("meta", 72),
}

# Starred rows whose est_items was off by more than 10% on 2026-11-07, each
# re-measured with `scripts/measure_registry.py` on a sparse clone that day.
# The undercounts ran up to 15x (anthropics/financial-services said 8 and
# ships 124), the overcounts up to 13x (taste-skill said 13 and ships 1).
# JuliusBrussee/caveman (21 -> 35) is pinned in EFFICIENCY_MEASURED.
STARRED_MEASURED = {
    "affaan-m/ECC": 1586,
    "alirezarezvani/claude-skills": 754,
    "anthropics/claude-plugins-official": 108,
    "anthropics/financial-services": 124,
    "davila7/claude-code-templates": 1725,
    "Donchitos/Claude-Code-Game-Studios": 172,
    "EveryInc/compound-engineering-plugin": 56,
    "github/awesome-copilot": 717,
    "google/skills": 187,
    "jeffallan/claude-skills": 77,
    "microsoft/playwright": 21,
    "PatrickJS/awesome-cursorrules": 256,
    "qdhenry/Claude-Command-Suite": 321,
    "trailofbits/skills": 139,
    "VoltAgent/awesome-claude-code-subagents": 166,
    "wshobson/agents": 428,
}

# Rows that failed the ★ rule beside CURATED when re-measured on 2026-11-07,
# with the count measured then. The reasons are recorded in CURATED itself.
UNSTARRED = {
    "anthropics/claude-code": 3,        # its stars are the product's
    "Leonxlnx/taste-skill": 1,          # 1 item, under the rule's 5
    "composio-community/awesome-codex-skills": 880,  # a vendor MCP funnel
}

_SLUG = re.compile(r"^[a-z][a-z0-9-]*$")


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_registries", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def catalog():
    return config.load_registry_catalog()


@pytest.fixture(scope="module")
def builder():
    if not _SCRIPT.exists():
        pytest.skip("repo-root scripts/ not reachable (e.g. mutation sandbox)")
    return _load_builder()


class TestFocusCoverage:
    @pytest.mark.parametrize("slug", sorted(FOCUS))
    def test_category_has_enough_registries(self, catalog, slug):
        floor, label = FOCUS[slug]
        rows = [e for e in catalog if e.get("category") == slug]
        assert len(rows) >= floor, (
            "category %r (%s) has %d registries, expected >= %d"
            % (slug, label, len(rows), floor))

    @pytest.mark.parametrize("slug", sorted(FOCUS))
    def test_category_is_tappable_without_include_lists(self, catalog, slug):
        """`tap --catalog --category X` drops list_only repos, so each domain
        needs real, scannable registries left after that filter."""
        rows = [e for e in catalog
                if e.get("category") == slug and not e["list_only"]]
        assert rows, "category %r has only list-only repos" % slug
        assert sum(e["est_items"] for e in rows) > 0

    def test_focus_domains_carry_the_batch_estimate(self, catalog):
        scannable = sum(e["est_items"] for e in catalog
                        if e.get("category") in FOCUS and not e["list_only"])
        assert scannable >= FOCUS_SCANNABLE_FLOOR, (
            "focus-domain scannable estimate fell to %d, floor is %d"
            % (scannable, FOCUS_SCANNABLE_FLOOR))

    def test_every_category_slug_is_flag_safe(self, catalog):
        bad = sorted({e["category"] for e in catalog
                      if not _SLUG.match(e.get("category") or "")})
        assert not bad, "category slugs unusable as --category values: %s" % bad


class TestDesignDomain:
    """`ui` is the domain most easily lost to keyword scoring, so pin it."""

    @pytest.mark.parametrize("name", sorted(UI_PINNED))
    def test_design_pack_is_filed_under_ui(self, catalog, name):
        row = next((e for e in catalog if e["name"] == name), None)
        assert row is not None, "%s dropped out of the catalog" % name
        assert row["category"] == "ui", (
            "%s is a visual-design pack but is filed %r; `tap --catalog "
            "--category ui` would miss it" % (name, row["category"]))

    def test_ai_design_skills_is_not_mistaken_for_ui(self, catalog):
        row = next((e for e in catalog if e["name"] == AI_NOT_UI), None)
        assert row is not None, "%s dropped out of the catalog" % AI_NOT_UI
        assert row["category"] == "ai", (
            "%s ships prompt/agent-design skills, not interface design; "
            "filing it %r is the repo-name trap" % (AI_NOT_UI, row["category"]))

    def test_skills_for_architects_is_not_software_architecture(self, catalog):
        name = BUILDINGS_NOT_SOFTWARE
        row = next((e for e in catalog if e["name"] == name), None)
        assert row is not None, "%s dropped out of the catalog" % name
        assert row["category"] != "architecture", (
            "%s ships AEC and real-estate skills (zoning, permits, EPDs), not "
            "software architecture; `tap --catalog --category architecture` "
            "would mix them in with the DDD packs" % name)

    def test_nwave_is_filed_with_the_agent_methodologies(self, catalog):
        name = METHODOLOGY_NOT_FRAMEWORK
        row = next((e for e in catalog if e["name"] == name), None)
        assert row is not None, "%s dropped out of the catalog" % name
        assert row["category"] == "meta", (
            "%s is an agent-methodology suite like obra/superpowers, but is "
            "filed %r; `framework` is language coding-standard rule packs"
            % (name, row["category"]))

    def test_playwright_is_carried_as_a_skill_registry(self, catalog):
        """The framework repo ships real SKILL.md items under
        packages/playwright-core, so it is a registry, not just a dependency."""
        row = next((e for e in catalog if e["name"] == "microsoft/playwright"),
                   None)
        assert row is not None, "microsoft/playwright is not in the catalog"
        assert row["type"] == "skill"
        assert row["category"] == "devops"
        assert not row["list_only"]

    def test_mirrored_repos_are_counted_once_per_distinct_item(self, catalog):
        """est_items must not be the raw walk: a repo that vendors a copy of
        each item per agent dir would otherwise advertise 6x what it ships."""
        row = next((e for e in catalog if e["name"] == "pbakaus/impeccable"),
                   None)
        assert row is not None
        assert row["est_items"] < IMPECCABLE_MIRRORED_WALK // 2, (
            "est_items %d looks like the mirrored walk (%d), not the distinct "
            "item count" % (row["est_items"], IMPECCABLE_MIRRORED_WALK))


class TestFiledByItemNames:
    """A row's category is the one its items carry when they declare none."""

    @pytest.mark.parametrize("name", sorted(RECATEGORISED))
    def test_row_is_filed_by_the_items_it_ships(self, catalog, name):
        row = next((e for e in catalog if e["name"] == name), None)
        assert row is not None, "%s dropped out of the catalog" % name
        assert row["category"] == RECATEGORISED[name][0], (
            "%s is filed %r; its item names say %r"
            % (name, row["category"], RECATEGORISED[name][0]))

    @pytest.mark.parametrize("name", sorted(RECATEGORISED))
    def test_refiled_row_was_re_measured(self, catalog, name):
        """Moving a row's category is not a reason to trust its old count."""
        row = next((e for e in catalog if e["name"] == name), None)
        assert row is not None
        assert row["est_items"] == RECATEGORISED[name][1], (
            "%s est_items %d != the measured %d — re-run "
            "scripts/measure_registry.py against a fresh clone"
            % (name, row["est_items"], RECATEGORISED[name][1]))

    def test_anthropics_skills_is_not_filed_as_ai(self, catalog):
        """The default tap a newcomer meets first; its documents and art
        skills must not answer an AI-engineering filter."""
        row = next(e for e in catalog if e["name"] == "anthropics/skills")
        assert row["category"] != "ai"

    def test_no_category_is_an_item_kind(self, catalog):
        """`--type` filters on kind; a category spelled like a kind makes
        `--category workflow` and `--type workflow` disagree silently."""
        kinds = {"skill", "rule", "workflow"}
        assert sorted(e["name"] for e in catalog
                      if e.get("category") in kinds) == []


class TestStarRule:
    """The ★ is what a newcomer reads as "most popular and most capable"."""

    @pytest.mark.parametrize("name", sorted(STARRED_MEASURED))
    def test_starred_row_carries_its_measured_count(self, catalog, name):
        row = next((e for e in catalog if e["name"] == name), None)
        assert row is not None, "%s dropped out of the catalog" % name
        assert row["curated"], "%s lost its star" % name
        assert row["est_items"] == STARRED_MEASURED[name], (
            "%s est_items %d != the measured %d — re-run "
            "scripts/measure_registry.py against a fresh clone"
            % (name, row["est_items"], STARRED_MEASURED[name]))

    @pytest.mark.parametrize("name", sorted(UNSTARRED))
    def test_a_row_that_fails_the_rule_is_not_starred(self, catalog, name):
        row = next((e for e in catalog if e["name"] == name), None)
        assert row is not None, "%s dropped out of the catalog" % name
        assert not row["curated"], "%s fails the ★ rule" % name
        assert row["est_items"] == UNSTARRED[name]

    def test_no_starred_row_ships_fewer_than_five_items(self, catalog):
        """The rule's own floor, checked against the count the row ships."""
        defaults = {str(d["name"]) for d in config.DEFAULT_TAPS}
        assert sorted(e["name"] for e in catalog
                      if e["curated"] and e["name"] not in defaults
                      and e["est_items"] < 5) == []


class TestEfficiencyDomain:
    """`efficiency` is a small domain that reads like `general`, so pin it.

    Both repos are among the most-starred agent-skill registries in existence
    (~97k each), and both advertise savings their own independent benchmarks
    do not support — ponytail measured -10.3% cost against -20% advertised,
    caveman -8.5% output tokens against -65%. The catalog carries them because
    they exist and are installable, so `focus` must describe what the items
    *do*, never repeat a marketing multiplier.
    """

    @pytest.mark.parametrize("name", sorted(EFFICIENCY_PINNED))
    def test_pack_is_filed_under_efficiency(self, catalog, name):
        row = next((e for e in catalog if e["name"] == name), None)
        assert row is not None, "%s dropped out of the catalog" % name
        assert row["category"] == "efficiency", (
            "%s ships token/code-reduction items but is filed %r; "
            "`tap --catalog --category efficiency` would miss it"
            % (name, row["category"]))

    @pytest.mark.parametrize("name", sorted(EFFICIENCY_PINNED))
    def test_est_items_is_measured_not_walked(self, catalog, name):
        """Both vendor one render per agent, so the raw walk overcounts."""
        measured, walked = EFFICIENCY_MEASURED[name]
        row = next((e for e in catalog if e["name"] == name), None)
        assert row is not None
        assert row["est_items"] == measured, (
            "%s est_items %d != the measured %d (raw walk finds %d) — "
            "re-run scripts/measure_registry.py"
            % (name, row["est_items"], measured, walked))

    @pytest.mark.parametrize("name", sorted(EFFICIENCY_PINNED))
    def test_focus_carries_no_advertised_multiplier(self, catalog, name):
        """Neither repo's headline number survived independent measurement, so
        the catalog must not quote one back at the user."""
        row = next((e for e in catalog if e["name"] == name), None)
        assert row is not None
        assert not re.search(r"\b(?:54|65|75|94)\s*%", row["focus"]), (
            "%s focus quotes an advertised saving that independent paired "
            "benchmarks did not reproduce: %r" % (name, row["focus"]))

    @pytest.mark.parametrize("name", sorted(EFFICIENCY_PINNED))
    def test_pack_is_scannable_not_list_only(self, catalog, name):
        """Both ship real items; neither is an index that only links out."""
        row = next((e for e in catalog if e["name"] == name), None)
        assert row is not None
        assert not row["list_only"], \
            "%s ships scannable items and must not be flagged list_only" % name


class TestMarketingDomain:
    """`marketing` is the domain most easily lost to *self-description*.

    `ui` is pinned because a keyword scorer reads the repo name; this one is
    pinned because the repos describe themselves in agent-vocabulary ("345
    skills for Claude Code, Codex, Cursor") long before they say the skills are
    cold-email sequences and CRM hygiene. Four of them sat in `writing` and
    `general` for exactly that reason.
    """

    @pytest.mark.parametrize("name", sorted(MARKETING_PINNED))
    def test_pack_is_filed_under_marketing(self, catalog, name):
        row = next((e for e in catalog if e["name"] == name), None)
        assert row is not None, "%s dropped out of the catalog" % name
        assert row["category"] == "marketing", (
            "%s ships marketing/CRM items but is filed %r; `tap --catalog "
            "--category marketing` would miss it" % (name, row["category"]))

    @pytest.mark.parametrize("area,name", sorted(MARKETING_SUBDOMAIN.items()))
    def test_every_advertised_subdomain_has_a_registry(self, catalog, area, name):
        row = next((e for e in catalog if e["name"] == name), None)
        assert row is not None, (
            "%s is the %s registry of the marketing domain and is gone; the "
            "category still advertises %s" % (name, area, area))
        assert row["category"] == "marketing"
        assert not row["list_only"], (
            "%s must be scannable — it is the only %s coverage the domain has"
            % (name, area))

    @pytest.mark.parametrize("name", sorted(MARKETING_MEASURED))
    def test_recategorised_rows_were_re_measured(self, catalog, name):
        """Moving a row's category is not a reason to trust its old count."""
        row = next((e for e in catalog if e["name"] == name), None)
        assert row is not None
        assert row["est_items"] == MARKETING_MEASURED[name], (
            "%s est_items %d != the measured %d — re-run "
            "scripts/measure_registry.py against a fresh clone"
            % (name, row["est_items"], MARKETING_MEASURED[name]))

    def test_domain_is_not_a_pile_of_index_repos(self, catalog):
        """Marketing attracts awesome-lists; the domain must ship real items."""
        rows = [e for e in catalog if e["category"] == "marketing"]
        scannable = [e for e in rows if not e["list_only"]]
        assert len(scannable) >= 14, (
            "only %d of %d marketing registries are scannable"
            % (len(scannable), len(rows)))
        assert sum(e["est_items"] for e in scannable) >= 1800


class TestSourceTuples:
    """Invariants on the SKILLS/RULES/WORKFLOWS rows themselves."""

    def test_rows_are_well_formed(self, builder):
        for tup, label in ((builder.SKILLS, "SKILLS"), (builder.RULES, "RULES"),
                           (builder.WORKFLOWS, "WORKFLOWS")):
            for row in tup:
                name, category, focus, est, conf = row
                assert name.count("/") == 1 and " " not in name, \
                    "%s: %r is not owner/repo" % (label, name)
                assert _SLUG.match(category), \
                    "%s: %r has bad category %r" % (label, name, category)
                assert focus.strip(), "%s: %r has an empty focus" % (label, name)
                assert isinstance(est, int) and est >= 1, \
                    "%s: %r has est_items %r" % (label, name, est)
                assert conf in ("high", "med", "low"), \
                    "%s: %r has confidence %r" % (label, name, conf)

    def test_no_repo_is_listed_twice_within_a_tuple(self, builder):
        for tup, label in ((builder.SKILLS, "SKILLS"), (builder.RULES, "RULES"),
                           (builder.WORKFLOWS, "WORKFLOWS")):
            names = [r[0] for r in tup]
            dupes = sorted({n for n in names if names.count(n) > 1})
            assert not dupes, "%s lists these twice: %s" % (label, dupes)

    def test_list_only_names_all_exist(self, builder):
        known = {r[0] for tup in (builder.SKILLS, builder.RULES,
                                  builder.WORKFLOWS) for r in tup}
        orphans = sorted(builder.LIST_ONLY - known)
        assert not orphans, (
            "LIST_ONLY names no longer in any tuple (dead entries): %s" % orphans)

    def test_retired_repos_are_gone_from_every_source_tuple(self, builder):
        """A repo verified dead upstream must not be advertised again.

        The catalogue is assembled from research batches, and a batch written
        before a repo was deleted still names it. Removing the row is therefore
        not the fix on its own — the next sweep re-adds it from the same stale
        source. `RETIRED` is the record that survives the sweep.
        """
        known = {r[0] for tup in (builder.SKILLS, builder.RULES,
                                  builder.WORKFLOWS) for r in tup}
        back = sorted(known & set(builder.RETIRED))
        assert not back, (
            "retired repos are back in the source tuples: %s — they 404 on "
            "GitHub, so every `boost tap` of them fails" % back)
        assert not (builder.LIST_ONLY & set(builder.RETIRED)), \
            "LIST_ONLY still names a retired repo"

    def test_retired_repos_are_gone_from_the_shipped_catalog(self, catalog, builder):
        """The generated payload is what a user actually taps from."""
        shipped = {e.get("name") for e in catalog}
        back = sorted(shipped & set(builder.RETIRED))
        assert not back, "registries.json still ships retired repos: %s" % back

    def test_every_renamed_row_is_a_row_and_no_former_name_is(self, builder):
        """`formerly` is how a tap of the old name is told apart from a new
        repository; a former name that is still a row would be both."""
        known = {r[0].lower() for tup in (builder.SKILLS, builder.RULES,
                                          builder.WORKFLOWS) for r in tup}
        assert sorted(n for n in builder.FORMERLY
                      if n.lower() not in known) == []
        olds = [o for olds in builder.FORMERLY.values() for o in olds]
        assert all(o.count("/") == 1 for o in olds), olds
        assert sorted(o for o in olds if o.lower() in known) == []

    def test_the_shipped_catalog_carries_formerly(self, catalog, builder):
        shipped = {e["name"]: e["formerly"] for e in catalog
                   if "formerly" in e}
        assert shipped == {n: list(o) for n, o in builder.FORMERLY.items()}

    def test_every_retired_repo_records_why(self, builder):
        """A bare name is unfalsifiable later; the reason is what makes it
        checkable against GitHub again in a year."""
        for name, reason in builder.RETIRED.items():
            assert name.count("/") == 1, "%r is not owner/repo" % name
            assert reason.strip(), "%s is retired with no reason given" % name

    def test_repo_names_are_case_unique(self, builder):
        """GitHub is case-insensitive on owner/repo, the payload dedupe is not:
        two rows differing only in case would ship as two registries."""
        names = [r[0].lower() for tup in (builder.SKILLS, builder.RULES,
                                          builder.WORKFLOWS) for r in tup]
        dupes = sorted({n for n in names if names.count(n) > 1})
        assert not dupes, "case-colliding repo names: %s" % dupes
