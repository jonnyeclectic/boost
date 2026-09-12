# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost recommend` attributes each suggestion to a stack keyword, so the
keyword has to be one the item actually mentions.

The scorer behind it tests substrings (``t in name``), which is right for a
free-text search box and wrong for a causal claim: the stack vocabulary is full
of short words that live inside unrelated ones. Every False case below is a
line `boost recommend` really printed, or would have.
"""
from __future__ import annotations

import pytest

from boost_cli.core import catalog


class TestMentionsKeyword:
    @pytest.mark.parametrize("text,kw", [
        # The finding as filed: a pasta-recipe skill credited to "ci".
        ("Delicious Italian pasta recipes", "ci"),
        ("Structured ideation & divergent-thinking facilitation", "ci"),
        ("Conventional, atomic commit message discipline", "ci"),
        ("decision records", "ci"),
        # Worse than the one that was reported: boost ships a `trust` command,
        # so a Rust project recommended every skill about trusting a tap.
        ("trust the output of a tap", "rust"),
        # A JavaScript project recommended Java skills.
        ("javascript testing patterns", "java"),
        # "go" is two letters and lives inside half the catalog.
        ("algorithms and data structures", "go"),
        ("django rest framework", "go"),
        ("goals and OKRs", "go"),
    ])
    def test_a_substring_is_not_a_mention(self, text, kw):
        assert catalog.mentions_keyword(text, kw) is False

    @pytest.mark.parametrize("text,kw", [
        ("Set up CI pipelines that fail loudly", "ci"),
        ("ci/cd for monorepos", "ci"),
        ("Rust memory safety without a GC", "rust"),
        ("Java Spring Boot service layout", "java"),
        ("Go concurrency patterns", "go"),
        ("Writing idiomatic Python", "python"),
        # Case and punctuation are boundaries, not mismatches.
        ("PYTHON packaging", "python"),
        ("terraform-modules", "terraform"),
    ])
    def test_a_real_mention_still_counts(self, text, kw):
        assert catalog.mentions_keyword(text, kw) is True

    @pytest.mark.parametrize("text,kw", [
        ("nextjs app router", "next"),
        ("reactjs hooks", "react"),
        ("vuejs composition api", "vue"),
        ("golang concurrency", "go"),
    ])
    def test_the_js_and_lang_suffixes_still_match(self, text, kw):
        """Word boundaries alone would drop these, and they are real matches.

        The alias is one-way and additive: it lets `next` reach `nextjs`, and
        gives `java` no route to `javascript` (which is why that case above
        stays False).
        """
        assert catalog.mentions_keyword(text, kw) is True

    def test_javascript_is_not_reachable_from_java(self):
        """The alias must not undo the fix it sits next to."""
        assert catalog.mentions_keyword("javascript", "java") is False
        assert catalog.mentions_keyword("javascript", "javascript") is True

    @pytest.mark.parametrize("kw", ["", "   ", "-"])
    def test_an_empty_keyword_matches_nothing(self, kw):
        assert catalog.mentions_keyword("anything at all", kw) is False

    def test_a_multi_word_keyword_needs_all_of_its_words(self):
        assert catalog.mentions_keyword("github actions ci", "github actions") is True
        assert catalog.mentions_keyword("github issues", "github actions") is False

    def test_it_reads_the_whole_entry_text(self):
        """`entry_text` is what the scorer indexes: name + description + meta."""
        e = {"name": "ci-pipelines", "description": "", "meta": {}}
        assert catalog.mentions_keyword(catalog.entry_text(e), "ci") is True
        e2 = {"name": "pasta-recipes", "description": "Delicious", "meta": {}}
        assert catalog.mentions_keyword(catalog.entry_text(e2), "ci") is False

    def test_it_prefers_the_cached_blob_over_rebuilding(self):
        """`search_blob` is stamped at scan time and is the string `search`
        ranks on, so a question *about* an entry must read the same one."""
        e = {"name": "x", "description": "y", "meta": {},
             "search_blob": "x y terraform"}
        assert catalog.entry_text(e) == "x y terraform"
        assert catalog.mentions_keyword(catalog.entry_text(e), "terraform") is True

    def test_frontmatter_tags_count_as_a_mention(self):
        """A skill tagged `ci` mentions ci even if its prose never says so."""
        e = {"name": "pipeline-hygiene", "description": "Keep builds green",
             "meta": {"tags": ["ci", "devops"]}}
        assert catalog.mentions_keyword(catalog.entry_text(e), "ci") is True
