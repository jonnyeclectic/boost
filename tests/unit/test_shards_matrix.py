# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: the `shards` matrix is one job per repository, and nothing else.

``tests/eval/taps.txt`` rows are ``owner/repo <40-char sha> <entry count>``.
``shards.yml`` built its job matrix by stripping comments and splitting the file
on **whitespace**, which does not split it into rows — it splits it into
*fields*. Twenty repositories became **sixty** matrix entries: twenty repos,
twenty commit SHAs and twenty integers, each dispatched to a job that ran
``boost tap`` on it.

That is what the 2026-08-09 run shows — jobs named ``build (18)``,
``build (b29e7cf65e5cb78a5ac33d582270551bc74a14eb)`` and ``build (1616)``
alongside the real ones. Two thirds of the fleet could never do anything but
fail, on a weekly schedule, with nobody watching a cron job.

``scripts/eval_corpus.parse_taps`` already parses this format correctly and is
already tested; the workflow had reimplemented it in one line of shell and got
it wrong. These tests pin the parse, and pin that the workflow keeps using it —
a matrix is only inspectable after it has already spent an hour of runner time,
so the check has to happen here.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TAPS = ROOT / "tests" / "eval" / "taps.txt"
SHARDS = ROOT / ".github" / "workflows" / "shards.yml"
SCRIPT = ROOT / "scripts" / "eval_corpus.py"

pytestmark = pytest.mark.skipif(
    not SHARDS.exists() or not TAPS.exists(),
    reason="workflow/corpus not reachable (e.g. mutation sandbox)")


def load_eval_corpus():
    """Import scripts/eval_corpus.py by path, the way this repo tests scripts/."""
    spec = importlib.util.spec_from_file_location("eval_corpus_shards", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


MOD = load_eval_corpus()

# The one-liner shards.yml used to use, kept as the thing being ruled out.
def naive_whitespace_split(text: str) -> list[str]:
    body = "\n".join(ln for ln in text.splitlines()
                     if ln.strip() and not ln.lstrip().startswith("#"))
    return body.split()


class TestTheOldParseWasWrong:
    """Without this the fix below looks like a stylistic preference."""

    def test_splitting_on_whitespace_multiplies_the_matrix(self):
        naive = naive_whitespace_split(TAPS.read_text(encoding="utf-8"))
        rows = MOD.parse_taps(TAPS.read_text(encoding="utf-8"))
        assert len(naive) > len(rows), (len(naive), len(rows))

    def test_it_produces_entries_that_are_not_repositories(self):
        naive = naive_whitespace_split(TAPS.read_text(encoding="utf-8"))
        junk = [tok for tok in naive if "/" not in tok]
        assert junk, "expected bare SHAs and counts in the naive split"
        # Both kinds, so the failure mode is recorded rather than summarised.
        assert any(re.fullmatch(r"[0-9a-f]{40}", tok) for tok in junk), junk[:5]
        assert any(tok.isdigit() for tok in junk), junk[:5]


class TestTheMatrixIsRepositories:
    def test_every_parsed_entry_is_an_owner_slash_repo(self):
        for repo, _sha, _count in MOD.parse_taps(TAPS.read_text(encoding="utf-8")):
            assert repo.count("/") == 1 and " " not in repo, repo

    def test_no_entry_is_a_bare_sha_or_count(self):
        repos = [r for r, _s, _c in MOD.parse_taps(TAPS.read_text(encoding="utf-8"))]
        assert not [r for r in repos if re.fullmatch(r"[0-9a-f]{40}", r)], repos
        assert not [r for r in repos if r.isdigit()], repos

    def test_the_repositories_are_unique(self):
        # A duplicate would embed the same registry twice — hours, not minutes.
        repos = [r for r, _s, _c in MOD.parse_taps(TAPS.read_text(encoding="utf-8"))]
        assert len(repos) == len(set(repos)), \
            sorted({r for r in repos if repos.count(r) > 1})

    def test_list_repos_prints_exactly_those_names(self):
        # The flag the workflow calls. One name per line, nothing else on it,
        # so a shell `tr '\n' ' '` round-trips without reintroducing the bug.
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = MOD.main(["--list-repos", "--taps", str(TAPS)])
        assert rc == 0
        printed = buf.getvalue().split("\n")
        printed = [ln for ln in printed if ln]
        expected = [r for r, _s, _c in MOD.parse_taps(TAPS.read_text(encoding="utf-8"))]
        assert printed == expected
        assert all(" " not in ln for ln in printed), printed


class TestTheWorkflowUsesTheParser:
    """The parse can be right and the workflow still not call it."""

    @staticmethod
    def _plan_step(code_only: bool = False) -> str:
        text = SHARDS.read_text(encoding="utf-8")
        start = text.index("choose the registries to shard")
        end = text.index("\n  build:", start)
        step = text[start:end]
        if not code_only:
            return step
        # Comments in this step deliberately quote the broken command they
        # replaced — that is the record of why the fix exists, and an assertion
        # that cannot tell prose from a command would force it to be deleted.
        return "\n".join(ln for ln in step.splitlines()
                         if not ln.lstrip().startswith("#"))

    def test_the_plan_step_calls_eval_corpus(self):
        assert "eval_corpus.py" in self._plan_step(), \
            "the matrix must come from the tested parser, not from shell " \
            "field-splitting — that is what produced 60 jobs for 20 repos"

    def test_the_plan_step_asks_for_repository_names_only(self):
        assert "--list-repos" in self._plan_step()

    def test_the_plan_step_no_longer_greps_the_file_directly(self):
        # The exact shape of the bug: reading taps.txt in shell at all means
        # re-deciding what a row is, in the one place it was decided wrong.
        # Code only — the comment above it names the old command on purpose.
        step = self._plan_step(code_only=True)
        assert "taps.txt" not in step, step
