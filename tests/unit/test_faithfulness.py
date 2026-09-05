# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: core/faithfulness.py — the runtime grounding check for explain."""
from __future__ import annotations

from boost_cli.core import faithfulness as f

SOURCE = """---
name: jira-integration
description: Create and update Jira issues from the agent.
---
Use the `jira` CLI. Always run `jira issue create` with --project set.
Never edit issues in the Closed state. Reads config from ~/.jira/config.yml.
"""


# ── salient_terms ────────────────────────────────────────────────────────

def test_backtick_spans_are_salient_and_split():
    terms = f.salient_terms("run `jira issue create` now")
    assert {"jira", "issue", "create"} <= terms


def test_code_shaped_tokens_are_salient():
    terms = f.salient_terms("pass --project and read ~/.jira/config.yml at v1.2")
    assert "--project" in terms
    assert "~/.jira/config.yml" in terms or "config.yml" in "".join(terms)
    assert "v1.2" in terms


def test_acronyms_are_salient_but_common_caps_are_not():
    terms = f.salient_terms("The MCP hub is OK and I use it")
    assert "mcp" in terms
    assert "ok" not in terms and "i" not in terms and "the" not in terms


def test_plain_prose_has_no_salient_terms():
    # Ordinary words must never be salient, or every paraphrase would be flagged.
    assert f.salient_terms("this helps the agent do its job more consistently") == set()


def test_midsentence_capitalized_words_are_salient():
    # A fabricated technology name reads as plain English to the acronym and
    # code-shape checks — only its capitalization, away from a sentence
    # boundary, marks it as a specific, checkable claim.
    terms = f.salient_terms("It provisions Kubernetes clusters with Terraform.")
    assert "kubernetes" in terms
    assert "terraform" in terms


def test_sentence_initial_capitalization_is_not_salient():
    # "Kubernetes" opening a sentence is indistinguishable from an ordinary
    # word placed there by chance — only a later, non-initial appearance (or
    # a stop-listed common word) should be exempt, so this alone must not be.
    assert f.salient_terms("Kubernetes runs the cluster.") == set()


def test_a_capword_repeated_both_initially_and_midsentence_is_still_salient():
    # The first mention opens a sentence and would be exempt alone, but the
    # second mention mid-sentence is exactly the fabricated-specific signal —
    # a model must not get a free pass by capitalizing a name at position 0
    # once and using it normally elsewhere.
    terms = f.salient_terms("Kubernetes is complex. It relies on Kubernetes pods.")
    assert "kubernetes" in terms


def test_stop_capwords_are_never_salient_even_midsentence():
    # Words like "This"/"It" are common regardless of position; only genuine
    # sentence-initial exemption plus the stop-list should suppress them, and
    # a stray "if it were That" reads as ordinary follow-on prose either way.
    assert f.salient_terms("The agent notes that This or That applies.") == set()


# ── score ────────────────────────────────────────────────────────────────

def test_a_grounded_summary_scores_one():
    summary = ("The agent creates Jira issues with the `jira` CLI, always "
               "passing --project, and never touches Closed issues.")
    assert f.score(summary, SOURCE) == 1.0


def test_a_fabricated_summary_scores_low():
    summary = ("Integrates with the `gh-slack` bridge and deploys via "
               "`kubectl apply` to the K8S cluster.")
    assert f.score(summary, SOURCE) < 0.5


def test_a_summary_with_no_specifics_is_trusted():
    # Nothing checkable to be wrong about → 1.0, never a spurious fallback.
    assert f.score("It makes the agent more careful and consistent.", SOURCE) == 1.0


def test_an_empty_summary_scores_zero():
    # Nothing to show — must trip the fallback, not pass as faithful.
    assert f.score("", SOURCE) == 0.0
    assert f.score("   \n  ", SOURCE) == 0.0


def test_partial_grounding_is_a_fraction():
    # One grounded salient term (jira), one invented (`kubectl`) -> 0.5.
    summary = "Uses `jira` and also `kubectl`."
    assert f.score(summary, SOURCE) == 0.5


def test_fabricated_proper_nouns_score_low_even_with_no_code_shapes():
    # The audit repro: a summary invented entirely in plain, grammatical
    # English — no backticks, no flags, no ALL-CAPS acronyms — used to score
    # 1.0 because salient_terms() had nothing that looked "code-shaped" to
    # catch. The fabrications are proper nouns instead, so they must count.
    summary = ("This skill provisions Kubernetes clusters with Terraform and "
               "migrates PostgreSQL schemas through Flyway. It triggers "
               "whenever the agent sees a Dockerfile.")
    assert f.score(summary, SOURCE) < 0.5


def test_one_grounded_backtick_term_no_longer_whitelists_other_fabrication():
    # Previously a single grounded term made salient_terms() non-empty, and
    # every unrelated fabrication in the same reply still had to be caught by
    # the (empty, for plain-English proper nouns) code/acronym checks — so a
    # reply mixing one real backtick with fabricated proper nouns scored 1.0.
    summary = ("Uses `jira` and also provisions Kubernetes clusters with "
               "Terraform.")
    assert f.score(summary, SOURCE) < 0.5


def test_punctuation_normalized_term_still_grounds():
    # Source says `jira issue create`; a summary writing `jira-issue-create`
    # must not be called invented just for the hyphens.
    assert f.score("run `jira-issue-create`", SOURCE) == 1.0


# ── ungrounded_terms ─────────────────────────────────────────────────────

def test_ungrounded_terms_lists_only_the_invented_ones():
    summary = "Uses `jira` and the `gh-slack` bridge with --project."
    bad = f.ungrounded_terms(summary, SOURCE)
    assert "gh-slack" in bad
    assert "jira" not in bad and "--project" not in bad


def test_ungrounded_terms_empty_for_a_grounded_summary():
    assert f.ungrounded_terms("run `jira` with --project", SOURCE) == []
