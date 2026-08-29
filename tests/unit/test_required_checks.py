# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: scripts/check_required_checks.py — the required-check drift gate.

The gate's whole job is to fail when the required-status-check list stops
matching reality, so the tests drive it against synthetic workflow trees rather
than only asserting that the real repo currently passes — a gate that can only
say "yes" is the failure mode this file exists to prevent.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_required_checks.py"


def load(monkeypatch, root: Path):
    """Import the gate with its ROOT/WORKFLOWS/CONFIG pointed at ``root``."""
    spec = importlib.util.spec_from_file_location("check_required_checks", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "ROOT", root)
    monkeypatch.setattr(mod, "WORKFLOWS", root / ".github" / "workflows")
    monkeypatch.setattr(mod, "CONFIG", root / ".github" / "required-checks.txt")
    return mod


def workflow(root: Path, name: str, jobs: str, on_pr: bool = True,
             pr_filter: str = "", merge_group: bool = True) -> None:
    """Write a synthetic workflow.

    ``pr_filter`` is extra YAML nested under the ``pull_request:`` trigger (a
    ``paths:`` or ``types:`` block), used to build the conditionally-triggered
    workflows that must never be requireable.

    ``merge_group`` defaults to True so that every case written before the
    queue rule existed still exercises what it was written to exercise: with
    the opposite default they would all fail on the new rule instead, and the
    trigger cases would stop testing triggers.
    """
    d = root / ".github" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    trigger = "on:\n  push:\n" + ("  pull_request:\n" + pr_filter if on_pr else "")
    if merge_group:
        trigger += "  merge_group:\n"
    (d / name).write_text("name: %s\n%s\njobs:\n%s" % (name[:-4], trigger, jobs),
                          encoding="utf-8")


def config(root: Path, body: str) -> None:
    (root / ".github").mkdir(parents=True, exist_ok=True)
    (root / ".github" / "required-checks.txt").write_text(body, encoding="utf-8")


class TestPassing:
    def test_matching_list_passes(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "# comment\n\nlint\n")
        mod = load(monkeypatch, tmp_path)
        assert mod.main([]) == 0
        assert "no ambiguity" in capsys.readouterr().out

    def test_matrix_leg_resolves_to_its_job(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", "  tests:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "tests (ubuntu-latest, 3.9)\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_reusable_workflow_prefix_resolves(self, tmp_path, monkeypatch):
        workflow(tmp_path, "osv.yml", "  scan-pr:\n    uses: ./x.yml\n")
        config(tmp_path, "scan-pr / osv-scan\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_explicit_name_overrides_the_job_id(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml",
                 "  lint:\n    name: Lint everything\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "Lint everything\n")
        assert load(monkeypatch, tmp_path).main([]) == 0


class TestDrift:
    def test_required_name_with_no_job_fails(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\nmutation\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "'mutation'" in capsys.readouterr().err

    def test_job_that_does_not_run_on_pr_cannot_be_required(self, tmp_path, monkeypatch, capsys):
        # A nightly-only job can never gate a PR, so requiring it would block
        # every merge forever.
        workflow(tmp_path, "nightly.yml", "  slow:\n    runs-on: ubuntu-latest\n",
                 on_pr=False)
        config(tmp_path, "slow\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "pull_request" in capsys.readouterr().err

    def test_renamed_job_is_caught(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", "  lint-v2:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 1


class TestAmbiguity:
    def test_duplicate_check_name_across_workflows_fails(self, tmp_path, monkeypatch, capsys):
        # The real bug: `lint` existed in three workflows, so branch protection
        # could not require it unambiguously.
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "markdownlint.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "ambiguous" in err and "ci.yml" in err and "markdownlint.yml" in err

    def test_ambiguity_is_reported_even_when_not_required(self, tmp_path, monkeypatch):
        # A collision is a latent trap whether or not the name is required today.
        workflow(tmp_path, "a.yml", "  audit:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "b.yml", "  audit:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 1

    def test_same_name_in_one_workflow_is_not_a_collision(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml",
                 "  lint:\n    runs-on: ubuntu-latest\n  tests:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\ntests\n")
        assert load(monkeypatch, tmp_path).main([]) == 0


class TestConditionalTriggers:
    """A check that runs on only *some* PRs must never be requireable.

    This is the failure that actually bricks a repository: GitHub creates no
    check run at all for a workflow whose `paths:` filter does not match, so
    branch protection waits forever for a status that is never coming. The
    first version of the committed list required four path-filtered checks
    (validate, markdown-lint, theme-lint, vale) and the gate passed it, because
    it only looked for the string `pull_request:` and never at what narrowed it.
    """

    PATHS = "    paths:\n      - \"docs/**.html\"\n"
    LABELED = "    types: [labeled]\n"

    def test_path_filtered_job_cannot_be_required(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "html-validate.yml",
                 "  validate:\n    runs-on: ubuntu-latest\n", pr_filter=self.PATHS)
        config(tmp_path, "validate\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "only runs on SOME pull requests" in err
        # The message must name the culprit, or nobody can act on it.
        assert "html-validate.yml" in err

    def test_paths_ignore_is_a_filter_too(self, tmp_path, monkeypatch):
        workflow(tmp_path, "docs.yml", "  docs:\n    runs-on: ubuntu-latest\n",
                 pr_filter="    paths-ignore:\n      - \"**.md\"\n")
        config(tmp_path, "docs\n")
        assert load(monkeypatch, tmp_path).main([]) == 1

    def test_label_gated_job_cannot_be_required(self, tmp_path, monkeypatch, capsys):
        # `types: [labeled]` never fires on opened/synchronize, so an ordinary
        # PR produces no run — same deadlock, different mechanism.
        workflow(tmp_path, "fuzz.yml", "  fuzz:\n    runs-on: ubuntu-latest\n",
                 pr_filter=self.LABELED)
        config(tmp_path, "fuzz\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "only runs on SOME pull requests" in capsys.readouterr().err

    def test_types_list_covering_the_normal_events_is_still_requireable(self, tmp_path, monkeypatch):
        # Narrowing `types:` is only disqualifying when it drops the events every
        # PR actually emits; spelling them out explicitly must stay allowed.
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n",
                 pr_filter="    types: [opened, synchronize, reopened]\n")
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_block_style_types_are_parsed(self, tmp_path, monkeypatch):
        workflow(tmp_path, "eval.yml", "  faithfulness:\n    runs-on: ubuntu-latest\n",
                 pr_filter="    types:\n      - labeled\n")
        config(tmp_path, "faithfulness\n")
        assert load(monkeypatch, tmp_path).main([]) == 1

    def test_a_filtered_job_nobody_requires_is_not_a_problem(self, tmp_path, monkeypatch):
        # Path-filtered workflows are fine and useful — they just cannot gate.
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "visual.yml", "  sweep:\n    runs-on: ubuntu-latest\n",
                 pr_filter=self.PATHS)
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_filtered_matrix_leg_is_caught(self, tmp_path, monkeypatch):
        # The matrix-leg spelling must not smuggle a filtered job past the gate.
        workflow(tmp_path, "floors.yml", "  lowest:\n    runs-on: ubuntu-latest\n",
                 pr_filter="    paths:\n      - \"pyproject.toml\"\n")
        config(tmp_path, "lowest (3.9)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1

    def test_filtered_and_missing_are_reported_differently(self, tmp_path, monkeypatch, capsys):
        # "exists but cannot gate" and "does not exist" need different fixes.
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "visual.yml", "  sweep:\n    runs-on: ubuntu-latest\n",
                 pr_filter=self.PATHS)
        config(tmp_path, "lint\nsweep\nghost\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "'sweep' only runs on SOME pull requests" in err
        assert "'ghost' is not a job that runs on pull_request" in err


class TestPullRequestState:
    """Direct coverage of the trigger classifier."""

    def test_unfiltered(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        assert mod.pull_request_state(["on:", "  push:", "  pull_request:"]) == mod.PR_ALWAYS

    def test_absent(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        assert mod.pull_request_state(["on:", "  schedule:"]) == mod.PR_NONE

    def test_paths_filtered(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        assert mod.pull_request_state(
            ["on:", "  pull_request:", "    paths:", "      - \"docs/**\""]
        ) == mod.PR_FILTERED

    def test_a_later_siblings_paths_key_does_not_leak_in(self, tmp_path, monkeypatch):
        # `paths:` under a *different* trigger must not taint pull_request —
        # the block ends where the indentation returns to a sibling key.
        mod = load(monkeypatch, tmp_path)
        assert mod.pull_request_state(
            ["on:", "  pull_request:", "  push:", "    paths:", "      - \"docs/**\""]
        ) == mod.PR_ALWAYS


class TestMergeQueue:
    """A required check must report on the queue's ref, not just on the PR.

    The merge queue evaluates required checks against gh-readonly-queue/*. A
    workflow without `merge_group:` never reports there, so the check stays
    pending forever and nothing in the queue can land. It is invisible until
    someone flips the Settings toggle, which is exactly why it is a gate.
    """

    def test_required_check_without_merge_group_fails(self, tmp_path, monkeypatch,
                                                      capsys):
        workflow(tmp_path, "codeql.yml",
                 "  codeql-analyze:\n    runs-on: ubuntu-latest\n",
                 merge_group=False)
        config(tmp_path, "codeql-analyze\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        # Names the check AND the file to edit: an error that says only
        # "deadlock" sends you looking through 20-odd workflows.
        assert "'codeql-analyze'" in err
        assert "codeql.yml" in err
        assert "merge_group:" in err

    def test_adding_the_trigger_fixes_it(self, tmp_path, monkeypatch):
        workflow(tmp_path, "codeql.yml",
                 "  codeql-analyze:\n    runs-on: ubuntu-latest\n",
                 merge_group=True)
        config(tmp_path, "codeql-analyze\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_a_matrix_leg_resolves_through_its_job(self, tmp_path, monkeypatch):
        # The required entry is `tests (ubuntu-latest, 3.9)` but the trigger
        # lives on the `tests` job. Asserting BOTH directions, so a rule that
        # simply never fires on matrix legs cannot pass this pair.
        workflow(tmp_path, "ci.yml", "  tests:\n    runs-on: ubuntu-latest\n",
                 merge_group=True)
        config(tmp_path, "tests (ubuntu-latest, 3.9)\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_a_matrix_leg_without_the_trigger_still_fails(self, tmp_path,
                                                          monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", "  tests:\n    runs-on: ubuntu-latest\n",
                 merge_group=False)
        config(tmp_path, "tests (ubuntu-latest, 3.9)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "ci.yml" in capsys.readouterr().err

    def test_reusable_workflow_prefix_resolves(self, tmp_path, monkeypatch):
        # `scan-pr / osv-scan` is the real shape: the required name is
        # "caller / job", and the trigger is on the caller.
        workflow(tmp_path, "osv.yml", "  scan-pr:\n    uses: ./x.yml\n",
                 merge_group=True)
        config(tmp_path, "scan-pr / osv-scan\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_an_unrequired_workflow_needs_no_trigger(self, tmp_path, monkeypatch):
        # The rule applies to REQUIRED checks only. Advisory path-filtered
        # workflows (vale, markdown-lint, ...) must not be dragged in.
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n",
                 merge_group=True)
        workflow(tmp_path, "prose.yml", "  vale:\n    runs-on: ubuntu-latest\n",
                 merge_group=False)
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_detector_reads_the_trigger_not_the_word(self, tmp_path, monkeypatch):
        # `merge_group` appearing in a comment or as a job id is not a trigger.
        # Without this, the gate passes on a workflow that only mentions it.
        mod = load(monkeypatch, tmp_path)
        assert mod.has_merge_group(["on:", "  merge_group:"]) is True
        assert mod.has_merge_group(["on:", "  push:"]) is False
        assert mod.has_merge_group(["on:", "  # merge_group: someday"]) is False
        assert mod.has_merge_group(["on:", "    merge_group:"]) is False


class TestRefusesToPassVacuously:
    def test_no_workflow_files_is_an_error(self, tmp_path, monkeypatch):
        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        config(tmp_path, "lint\n")
        with pytest.raises(SystemExit, match="no workflow files"):
            load(monkeypatch, tmp_path).main([])

    def test_parsing_zero_jobs_is_an_error_not_a_pass(self, tmp_path, monkeypatch):
        # If the parser stops matching, the gate must fail loudly rather than
        # report "no problems found".
        d = tmp_path / ".github" / "workflows"
        d.mkdir(parents=True)
        (d / "ci.yml").write_text("name: ci\non:\n  pull_request:\n", encoding="utf-8")
        config(tmp_path, "lint\n")
        with pytest.raises(SystemExit, match="parsed 0 jobs"):
            load(monkeypatch, tmp_path).main([])

    def test_empty_config_is_an_error(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "# only comments\n\n")
        with pytest.raises(SystemExit, match="lists no checks"):
            load(monkeypatch, tmp_path).main([])

    def test_missing_config_is_an_error(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        with pytest.raises(SystemExit, match="missing"):
            load(monkeypatch, tmp_path).main([])


class TestPrintApi:
    def test_payload_requires_checks_but_not_reviews(self, tmp_path, monkeypatch, capsys):
        import json
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main(["--print-api"]) == 0
        out = capsys.readouterr().out
        payload = json.loads(out[out.index("{"):])
        assert payload["required_status_checks"]["contexts"] == ["lint"]
        assert payload["required_status_checks"]["strict"] is True
        # Reviews stay off on purpose: parallel loop/* branches self-merge, and
        # requiring a second reviewer would deadlock every one of them.
        assert payload["required_pull_request_reviews"] is None


class TestRulesetIsTheOtherHalf:
    """`main` is protected twice, and this gate only ever saw one of them.

    The classic branch protection and the repository ruleset are independent
    objects with independent lists. Applying `--print-api` updates the classic
    one and leaves the ruleset exactly as it was, which is how the ruleset came
    to be missing `bdd`, `evals` and `onnx-inference` while this script reported
    the config clean — it was comparing the file against the *workflows*, and
    the workflows were fine.

    The asymmetry is what made that expensive. Classic protection sets
    `enforce_admins: false`, so it does not bind the identity that merges here;
    the ruleset carries `bypass_actors: []`, so it binds everyone. The three
    checks absent from the ruleset were therefore the three nothing enforced.
    """

    def _mod(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        return load(monkeypatch, tmp_path)

    def test_drift_reports_missing_and_extra(self, tmp_path, monkeypatch):
        m = self._mod(tmp_path, monkeypatch)
        missing, extra = m.drift(["a", "b", "c"], ["b", "z"])
        assert missing == ["a", "c"] and extra == ["z"]

    def test_drift_ignores_order(self, tmp_path, monkeypatch):
        # GitHub returns contexts in its own order; a different sort is not drift.
        m = self._mod(tmp_path, monkeypatch)
        assert m.drift(["a", "b"], ["b", "a"]) == ([], [])

    def test_the_ruleset_rule_is_not_the_classic_payload(self, tmp_path, monkeypatch):
        # The two API shapes differ in ways a human retyping them gets wrong:
        # a ruleset names each context as an object carrying the producing app,
        # and spells `strict` differently. Pinning it here is what stops the
        # translation step being done from memory.
        m = self._mod(tmp_path, monkeypatch)
        rule = m.ruleset_rule(["lint", "bdd"])
        assert rule["type"] == "required_status_checks"
        p = rule["parameters"]
        assert p["strict_required_status_checks_policy"] is True
        assert p["required_status_checks"] == [
            {"context": "lint", "integration_id": m.ACTIONS_APP_ID},
            {"context": "bdd", "integration_id": m.ACTIONS_APP_ID},
        ]

    def test_ruleset_rule_names_github_actions_as_the_producer(self, tmp_path, monkeypatch):
        # Without integration_id any app could satisfy a check by name, which is
        # a weaker gate than the one required-checks.txt describes.
        m = self._mod(tmp_path, monkeypatch)
        assert m.ACTIONS_APP_ID == 15368

    def test_a_ruleset_with_no_status_check_rule_is_distinguishable(self, tmp_path, monkeypatch):
        # "requires nothing" and "requires a drifted list" are different faults
        # and get different messages; collapsing them to an empty list hides the
        # louder one.
        m = self._mod(tmp_path, monkeypatch)
        assert m.ruleset_contexts({"rules": [{"type": "deletion"}]}) == (False, [])
        has, ctx = m.ruleset_contexts({"rules": [
            {"type": "required_status_checks",
             "parameters": {"required_status_checks": [{"context": "lint"}]}}]})
        assert has is True and ctx == ["lint"]

    # ---- verify_remote, driven against a stubbed API ------------------------

    def _stub(self, m, monkeypatch, *, classic, ruleset_ctx, has_rule=True,
              enforcement="active", includes=("refs/heads/main",)):
        rules = [{"type": "deletion"}]
        if has_rule:
            rules.append({"type": "required_status_checks", "parameters": {
                "required_status_checks": [{"context": c} for c in ruleset_ctx]}})
        detail = {"id": 1, "name": "main", "enforcement": enforcement,
                  "conditions": {"ref_name": {"include": list(includes)}},
                  "rules": rules}

        def fake(path, token):
            if path.endswith("/protection"):
                return {"required_status_checks": {"contexts": list(classic)}}
            if path.endswith("/rulesets"):
                return [{"id": 1}]
            return detail
        monkeypatch.setattr(m, "_api", fake)

    def test_it_catches_the_real_regression(self, tmp_path, monkeypatch):
        # The exact production state: classic correct, ruleset short by three.
        m = self._mod(tmp_path, monkeypatch)
        want = ["lint", "bdd", "evals", "onnx-inference"]
        self._stub(m, monkeypatch, classic=want, ruleset_ctx=["lint"])
        problems = m.verify_remote(want, "t")
        assert len(problems) == 1
        assert "ruleset" in problems[0]
        for name in ("bdd", "evals", "onnx-inference"):
            assert name in problems[0]

    def test_it_stays_quiet_when_both_agree(self, tmp_path, monkeypatch):
        m = self._mod(tmp_path, monkeypatch)
        want = ["lint", "bdd"]
        self._stub(m, monkeypatch, classic=want, ruleset_ctx=list(reversed(want)))
        assert m.verify_remote(want, "t") == []

    def test_it_catches_classic_drift_too(self, tmp_path, monkeypatch):
        m = self._mod(tmp_path, monkeypatch)
        want = ["lint", "bdd"]
        self._stub(m, monkeypatch, classic=["lint"], ruleset_ctx=want)
        problems = m.verify_remote(want, "t")
        assert len(problems) == 1 and "classic" in problems[0]

    def test_a_ruleset_that_gates_nothing_is_loud(self, tmp_path, monkeypatch):
        m = self._mod(tmp_path, monkeypatch)
        want = ["lint"]
        self._stub(m, monkeypatch, classic=want, ruleset_ctx=[], has_rule=False)
        problems = m.verify_remote(want, "t")
        assert any("gates nothing" in p for p in problems)

    def test_no_active_ruleset_is_reported_rather_than_passing(self, tmp_path, monkeypatch):
        # Silence here would read as "the rulesets agree" — the exact shape of
        # invisibility this whole check exists to remove.
        m = self._mod(tmp_path, monkeypatch)
        want = ["lint"]
        self._stub(m, monkeypatch, classic=want, ruleset_ctx=want,
                   enforcement="disabled")
        assert any("no active ruleset" in p for p in m.verify_remote(want, "t"))

    def test_a_ruleset_for_another_branch_is_not_mistaken_for_main(self, tmp_path, monkeypatch):
        m = self._mod(tmp_path, monkeypatch)
        want = ["lint"]
        self._stub(m, monkeypatch, classic=want, ruleset_ctx=["something-else"],
                   includes=("refs/heads/release",))
        problems = m.verify_remote(want, "t")
        # It must not grade main against a release ruleset...
        assert not any("disagrees" in p and "ruleset" in p for p in problems)
        # ...but must still say main has no ruleset covering it.
        assert any("no active ruleset" in p for p in problems)

    def test_the_default_branch_alias_counts_as_main(self, tmp_path, monkeypatch):
        # GitHub writes `~DEFAULT_BRANCH` rather than a literal ref when the
        # ruleset was created through the UI's default-branch option.
        m = self._mod(tmp_path, monkeypatch)
        want = ["lint"]
        self._stub(m, monkeypatch, classic=want, ruleset_ctx=want,
                   includes=("~DEFAULT_BRANCH",))
        assert m.verify_remote(want, "t") == []

    def test_verify_remote_without_a_token_skips_rather_than_passes(
            self, tmp_path, monkeypatch, capsys):
        m = self._mod(tmp_path, monkeypatch)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        assert m.main(["--verify-remote"]) == 0
        assert "skipped" in capsys.readouterr().out

    def test_print_ruleset_emits_the_rule(self, tmp_path, monkeypatch, capsys):
        import json
        m = self._mod(tmp_path, monkeypatch)
        assert m.main(["--print-ruleset"]) == 0
        out = capsys.readouterr().out
        rule = json.loads(out[out.index("{"):])
        assert rule["parameters"]["required_status_checks"][0]["context"] == "lint"

    def test_print_api_now_says_it_is_only_half(self, tmp_path, monkeypatch, capsys):
        # The old output invited exactly the mistake that caused this: it read
        # as though applying it made protection correct.
        m = self._mod(tmp_path, monkeypatch)
        assert m.main(["--print-api"]) == 0
        assert "--print-ruleset" in capsys.readouterr().out


class TestRealRepo:
    def test_the_committed_config_matches_the_real_workflows(self):
        import subprocess
        import sys
        r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
