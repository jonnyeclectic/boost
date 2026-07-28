"""Unit tests: the CodeQL job id is half of a code-scanning analysis key.

GitHub identifies a code-scanning configuration by ``<workflow path>:<job id>``.
That makes the job id load-bearing in a way nothing in the file hints at:
renaming it does not *move* the configuration, it **forks** it. The old key stays
on record as a configuration present on the default branch, no future run ever
refreshes it, and code-scanning merge protection then reports

    1 configuration not found
    .github/workflows/codeql.yml:<old job id>

on every pull request — conclusion ``neutral``, forever.

This is not hypothetical. #259 ("ci(release-safety): make the required-check list
config-as-code") renamed this job ``analyze`` -> ``codeql-analyze`` on
2026-07-27. The last ``:analyze`` analysis landed 20 seconds after that merge and
never refreshed, stranding 247 of them on ``refs/heads/main``. Every PR from #264
onward reported ``neutral``, and because the branch ruleset carries a
``code_scanning`` rule, that neutral blocked **100% of merges** — with all
required status checks green, which is what made it so hard to read. It looked
like a rule that rejected docs-only PRs; it was a rule that could never be
satisfied by anything.

The job id is also a required status-check context (``.github/required-checks.txt``,
enforced by scripts/check_required_checks.py), so a rename already had one guard.
That guard passed: the context list was updated in the same commit. Only the
invisible half — the analysis key — broke.

So this pins the id. If you genuinely need to rename the job, the rename is not
finished until the stale configuration is deleted from the default branch
(Security -> Code scanning -> any alert -> Affected branches -> main ->
Configurations analyzing -> delete the old key; or DELETE
/repos/{owner}/{repo}/code-scanning/analyses/{id}?confirm_delete=true, walking
``next_analysis_url`` to the end of the set).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "codeql.yml"

# Both halves of the analysis key GitHub records for this repo's CodeQL setup.
# Changing either one strands the configuration these names describe.
EXPECTED_WORKFLOW = ".github/workflows/codeql.yml"
EXPECTED_JOB_ID = "codeql-analyze"


def _parse_workflow():
    """Reuse the repo's own stdlib workflow parser (no YAML dep in the lint set)."""
    script = ROOT / "scripts" / "check_required_checks.py"
    spec = importlib.util.spec_from_file_location("check_required_checks_for_key",
                                                  script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.parse_workflow(WORKFLOW)


class TestAnalysisKeyIsStable:
    def test_the_workflow_lives_where_the_key_says_it_does(self):
        assert WORKFLOW.is_file()
        assert WORKFLOW.relative_to(ROOT).as_posix() == EXPECTED_WORKFLOW

    def test_the_codeql_job_id_is_pinned(self):
        _, _, jobs = _parse_workflow()
        assert EXPECTED_JOB_ID in jobs, (
            "the CodeQL job id changed to %r. That forks the code-scanning "
            "configuration: GitHub keeps '%s:%s' on record as present on the "
            "default branch, nothing refreshes it, and merge protection reports "
            "'1 configuration not found' -> neutral on every PR from now on. "
            "Delete the stale configuration before landing the rename."
            % (sorted(jobs), EXPECTED_WORKFLOW, EXPECTED_JOB_ID))

    def test_exactly_one_job_produces_the_key(self):
        # A second job in this file would add a second configuration, and every
        # one of them has to keep reporting or merge protection goes neutral
        # again. Adding one is a deliberate act, not a drive-by edit.
        _, _, jobs = _parse_workflow()
        assert list(jobs) == [EXPECTED_JOB_ID], sorted(jobs)


class TestTheGuardActuallyParses:
    """A parser that silently stops matching would make the pin vacuous."""

    def test_parser_finds_jobs_at_all(self):
        _, _, jobs = _parse_workflow()
        assert jobs, "parsed no jobs out of codeql.yml — the guard is not checking anything"

    def test_workflow_still_runs_on_pull_request(self):
        # The key is only ever exercised on PRs; a workflow that stopped
        # triggering there would strand the configuration just as effectively.
        on_pr, _, _ = _parse_workflow()
        assert on_pr != "none", "codeql.yml no longer runs on pull_request"
