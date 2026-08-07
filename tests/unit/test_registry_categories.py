"""Curation guarantees for the bundled registry catalog's focus domains.

``boost tap --catalog --category <slug>`` is only worth offering if every
advertised domain actually has registries behind it, so the six focus domains
below are contract, not incident: AI engineering, architecture, UI, Java/Spring,
eCommerce, and container/cluster infrastructure.

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
# copy of each item per agent they support. Raw `scan_dir` walks find 13 and 28.
EFFICIENCY_MEASURED = {
    "DietrichGebert/ponytail": (7, 13),
    "JuliusBrussee/caveman": (21, 28),
}

# `pbakaus/impeccable` vendors one copy of each item into every agent dir it
# supports (`.claude/`, `.cursor/`, `.gemini/`, `.github/`, `.grok/`, …), so a
# naive walk reports this many items for the handful it actually ships.
IMPECCABLE_MIRRORED_WALK = 40

# The batch this file was written for: the six focus domains together must carry
# at least this many estimated *scannable* items (list-only index repos excluded).
FOCUS_SCANNABLE_FLOOR = 5000

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

    def test_repo_names_are_case_unique(self, builder):
        """GitHub is case-insensitive on owner/repo, the payload dedupe is not:
        two rows differing only in case would ship as two registries."""
        names = [r[0].lower() for tup in (builder.SKILLS, builder.RULES,
                                          builder.WORKFLOWS) for r in tup]
        dupes = sorted({n for n in names if names.count(n) > 1})
        assert not dupes, "case-colliding repo names: %s" % dupes
