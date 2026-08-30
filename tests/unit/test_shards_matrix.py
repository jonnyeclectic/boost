# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the `shards` matrix is built by tested code, not by shell.

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

The matrix is now *packed* rather than one-job-per-repo, because the scope grew
to the 463-registry catalogue and GitHub caps a matrix at 256 jobs. That moved
the eval-corpus parse one level down — `shard_plan.py --scope eval` calls it —
so these tests follow it there rather than lapsing. What must not come back is
the shape of the original bug: the workflow deciding for itself what a row of
`taps.txt` is.
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
        start = text.index("- id: pick")
        end = text.index("\n  build:", start)
        step = text[start:end]
        if not code_only:
            return step
        # Comments in this step deliberately quote the broken command they
        # replaced — that is the record of why the fix exists, and an assertion
        # that cannot tell prose from a command would force it to be deleted.
        return "\n".join(ln for ln in step.splitlines()
                         if not ln.lstrip().startswith("#"))

    def test_the_plan_step_calls_the_planner(self):
        assert "shard_plan.py" in self._plan_step(), \
            "the matrix must come from tested Python, not from shell " \
            "field-splitting — that is what produced 60 jobs for 20 repos"

    def test_the_eval_scope_still_goes_through_the_tested_parser(self):
        # One level down now, but it must still be the parser rather than a
        # second opinion about what a row of taps.txt is.
        plan = (ROOT / "scripts" / "shard_plan.py").read_text(encoding="utf-8")
        assert "eval_corpus.py" in plan
        assert "--list-repos" in plan

    def test_the_plan_step_never_splits_a_list_in_shell(self):
        # `printf '%s\n' $repos` relies on word-splitting that does not survive
        # quoting, and produced a ONE-entry matrix holding all 20 repos.
        step = self._plan_step(code_only=True)
        assert "printf '%s" not in step, step

    def test_the_matrix_cannot_exceed_githubs_job_ceiling(self):
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        import shard_plan
        # A matrix over the cap fails the run before a job starts, so the
        # planner refuses rather than letting the workflow discover it.
        assert shard_plan.MAX_MATRIX_JOBS == 256
        assert shard_plan.DEFAULT_JOBS <= shard_plan.MAX_MATRIX_JOBS

    def test_the_plan_step_no_longer_greps_the_file_directly(self):
        # The exact shape of the bug: reading taps.txt in shell at all means
        # re-deciding what a row is, in the one place it was decided wrong.
        # Code only — the comment above it names the old command on purpose.
        step = self._plan_step(code_only=True)
        assert "taps.txt" not in step, step
