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
