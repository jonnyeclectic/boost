# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: every unattended workflow is watched by the failure alerting.

``ci-failure-issue.yml`` opens a tracking issue when a watched workflow fails on
``main``. Its own header states the rule::

    Any workflow that runs on main and nobody watches belongs here.

It watched two: ``ci`` and ``demo``. Twenty-four run unattended — fourteen on a
cron, ten on a push to ``main`` — so the rule was written down and not applied,
which is the most expensive kind of convention.

Two outages measured this session are exactly what that gap costs:

* ``fuzz`` failed **three scheduled runs out of three** (2026-07-25, 08-01,
  08-08), writing the same libFuzzer reproducer each time. It had found a real
  defect in ``registry.parse_spec`` and been ignored for three weeks.
* ``shards`` failed **both** of its scheduled runs and published zero artifacts,
  which is how a feature reached a state where it had never once worked.

Neither produced a notification, a red badge anyone looks at, or a comment on a
pull request. A cron job's failure is a red square on a page nobody opens.

The list is enforced rather than curated: a new scheduled workflow fails this
test until it is either watched or added to ``EXPECTED_UNWATCHED`` with a
reason. That is the same shape as ``test_action_pin_lockstep``'s parametrised
family check — the convention stays falsifiable instead of decaying the moment
the person who wrote it stops looking.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
ALERT = WORKFLOWS / "ci-failure-issue.yml"

pytestmark = pytest.mark.skipif(
    not ALERT.exists(),
    reason=".github/workflows not reachable (e.g. mutation sandbox)")

#: Unattended workflows deliberately NOT watched, each with its reason.
#: Empty today. An entry here is a claim that a failure is expected noise
#: rather than news, and it should be rare enough to argue about.
EXPECTED_UNWATCHED: dict[str, str] = {}


def workflow_name(text: str, fallback: str) -> str:
    """The workflow's `name:`, which is what `workflow_run` matches on."""
    m = re.search(r"^name:\s*(.+)$", text, re.M)
    return m.group(1).strip().strip("\"'") if m else fallback


def runs_unattended(text: str) -> bool:
    """True for a workflow that runs with nobody waiting on the result.

    A cron run has no author watching by construction. A push to ``main`` runs
    after the pull request's checks are already green and merged, so its failure
    surfaces only on a commit list — which is how ``demo`` failed six runs out
    of six before a manual audit found it.

    ``workflow_run`` is the same situation one step further removed, and it was
    the hole in this guard: such a workflow starts *after* the run that
    triggered it has already reported, so its own result appears on no pull
    request and in no commit's check list. Three were in that blind spot —
    ``release`` (publish.yml, which is what actually uploads to PyPI on every
    merge to main), ``sbom`` and ``mutation-weights-refresh`` — and the rule
    this file enforces, "any workflow that runs on main and nobody watches
    belongs here", covered none of them because the parser only ever looked
    for a cron or a push.
    """
    return bool(re.search(r"^\s*schedule:", text, re.M)
                or re.search(r"^\s*push:", text, re.M)
                or re.search(r"^\s*workflow_run:", text, re.M))


def watched() -> set[str]:
    """The workflow names ci-failure-issue.yml subscribes to."""
    m = re.search(r"workflows:\s*\[([^\]]*)\]", ALERT.read_text(encoding="utf-8"))
    assert m, "could not find the workflows: list in ci-failure-issue.yml"
    return {w.strip().strip("\"'") for w in m.group(1).split(",") if w.strip()}


def unattended() -> dict[str, str]:
    """``{workflow name: file name}`` for every unattended workflow."""
    out = {}
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        name = workflow_name(text, path.stem)
        # The alerting workflow itself is triggered by workflow_run, never by a
        # schedule or a push, and watching itself would be a loop.
        if name == "ci-failure-alert":
            continue
        if runs_unattended(text):
            out[name] = path.name
    return out


class TestTheGuardCanActuallySee:
    """Every assertion below is vacuous if the parsing silently breaks."""

    def test_the_watch_list_is_found_and_non_empty(self):
        assert watched(), "parsed an empty watch list"

    def test_unattended_workflows_are_found(self):
        assert len(unattended()) > 5, unattended()

    def test_the_two_original_watchers_are_still_there(self):
        # `demo` is in the list because it failed six of six runs unnoticed.
        # Losing either entry would be a silent regression of that fix.
        assert {"ci", "demo"} <= watched()

    def test_a_known_cron_workflow_is_classified_as_unattended(self):
        assert "fuzz" in unattended(), unattended()

    def test_a_workflow_run_workflow_is_classified_as_unattended(self):
        # The hole this guard had: `release` (publish.yml) is triggered by
        # `workflow_run` alone, so before `runs_unattended` learned that
        # trigger, the one workflow that publishes to PyPI was invisible here.
        assert "release" in unattended(), unattended()

    def test_a_workflow_run_only_trigger_is_recognised(self):
        # Fed the shape directly, so a parser that stops matching fails here
        # rather than silently shrinking the set it is meant to police.
        assert runs_unattended("on:\n  workflow_run:\n    workflows: [ci]\n")


class TestEveryUnattendedWorkflowIsWatched:
    @pytest.mark.parametrize("name", sorted(unattended()))
    def test_it_is_watched_or_documented(self, name):
        if name in EXPECTED_UNWATCHED:
            assert EXPECTED_UNWATCHED[name].strip(), \
                "%s is excluded without a reason" % name
            return
        assert name in watched(), (
            "%s (%s) runs unattended on main but nothing alerts when it fails "
            "— fuzz was red for three scheduled runs and shards for two, both "
            "unnoticed. Add it to ci-failure-issue.yml's `workflows:` list, or "
            "to EXPECTED_UNWATCHED with a reason."
            % (name, unattended()[name]))

    def test_the_exclusion_list_has_no_stale_entries(self):
        # An entry for a workflow that no longer runs unattended is a licence
        # nobody re-examined.
        stale = sorted(set(EXPECTED_UNWATCHED) - set(unattended()))
        assert not stale, stale

    def test_nothing_watched_has_disappeared(self):
        # A watch entry naming a workflow that no longer exists silently
        # watches nothing, and reads as coverage.
        names = {workflow_name(p.read_text(encoding="utf-8"), p.stem)
                 for p in WORKFLOWS.glob("*.yml")}
        assert watched() <= names, sorted(watched() - names)


class TestTheAlertCanStandDown:
    """An alert that cannot close is only half an alert.

    The tracker opened issues, commented on repeats, and never closed one — so
    its own closing line, "close this once CI is green again", was a manual step
    nobody had a reason to take. `visual` stayed open through four consecutive
    green runs, and a list that mixes live outages with fixed ones makes every
    entry in it read as equally suspect.
    """

    def test_a_success_on_main_closes_the_tracker(self):
        text = ALERT.read_text(encoding="utf-8")
        assert "conclusion == 'success'" in text, (
            "nothing reacts to a watched workflow going green, so every "
            "tracker this file opens stays open until someone closes it")
        assert "state: 'closed'" in text

    def test_closing_is_keyed_by_workflow_like_opening(self):
        """A `ci` success must not close a `demo` tracker.

        The opener keys its marker on the workflow name for exactly this
        reason; a closer that matched any `ci-failure` issue would undo that.
        """
        text = ALERT.read_text(encoding="utf-8")
        assert text.count("ci-failure-tracker:${run.name}") >= 2, (
            "the closing half must use the same per-workflow marker the "
            "opening half writes")

    def test_only_main_can_close_it(self):
        """`workflow_run` fires for the default branch, but the opener still
        checks — and an asymmetry here would let a non-main success close a
        tracker for a failure that is still live on main."""
        text = ALERT.read_text(encoding="utf-8")
        assert text.count("head_branch == 'main'") >= 2

    def test_permissions_are_not_granted_workflow_wide(self):
        """`issues: write` at the top reaches every job, including any added
        later. zizmor's excessive-permissions audit fails the build on it."""
        text = ALERT.read_text(encoding="utf-8")
        assert re.search(r"^permissions:\s*\{\}\s*$", text, re.M), \
            "workflow-level permissions must be empty; each job asks for its own"
        assert text.count("issues: write") >= 2


#: The conclusions that mean "main is green". The opener alerts on everything
#: else, so this set — not a list of failures — is what the gate names.
GREEN = ("success", "skipped", "neutral")

#: Conclusions GitHub can report that are NOT green. Every one must alert.
#: `cancelled` is the one that cost a release; the rest are here so the set is
#: tested as a set rather than as the single case that was observed.
NOT_GREEN = ("failure", "cancelled", "timed_out", "action_required",
             "stale", "startup_failure")


def open_issue_gate() -> str:
    """The `if:` expression guarding the issue-opening job."""
    text = ALERT.read_text(encoding="utf-8")
    m = re.search(r"^  open-issue:\n(.*?)^    runs-on:", text, re.M | re.S)
    assert m, "could not find the open-issue job's header"
    gate = re.search(r"^    if: (.*)\Z", m.group(1), re.M | re.S)
    assert gate, "could not find open-issue's `if:`"
    return gate.group(1)


def names_conclusion(gate: str, conclusion: str) -> bool:
    """True if ``gate`` names ``conclusion`` as a quoted literal.

    Both quotings have to count. The gate holds a JSON array inside a
    single-quoted GitHub string — ``fromJSON('["success", ...]')`` — so the
    conclusions are double-quoted while the surrounding expression uses single
    quotes. A check written for only one of them reports whatever the author
    happened to assume: the negative assertions below passed *vacuously*
    against the real file before this existed, which is the failure mode a
    guard like this is supposed to prevent rather than demonstrate.

    Quoting also keeps ``'failure'`` from matching inside ``startup_failure``.
    """
    return ('"%s"' % conclusion in gate) or ("'%s'" % conclusion in gate)


def strip_js_comments(script: str) -> str:
    """``script`` with whole-line ``//`` comments removed.

    Every assertion about this script is about what it *does*, and prose is
    not behaviour. Twice now a comment explaining a rule contained the token
    the test looked for and made the assertion pass against code that had
    stopped doing the thing: a falsification run found ``noRelease`` still
    "present" with the interpolation deleted, because the comment beside it
    named ``noRelease``. Strip the prose, assert on the code.

    Whole-line only, so a ``//`` inside a string literal survives.
    """
    return "\n".join(line for line in script.splitlines()
                      if not line.lstrip().startswith("//"))


def opener_script() -> str:
    """The github-script body of the issue-OPENING job, comments stripped."""
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load(ALERT.read_text(encoding="utf-8"))
    for step in doc["jobs"]["open-issue"]["steps"]:
        script = (step.get("with") or {}).get("script")
        if script:
            return strip_js_comments(script)
    raise AssertionError("no script found in the open-issue job")


def call_args(script: str, fn: str) -> str:
    """The argument text of ``fn(`` up to its closing ``});``."""
    _, _, tail = script.partition(fn + "(")
    assert tail, "no %s call found" % fn
    return tail.split("});", 1)[0]


class TestEveryNonGreenConclusionIsLoud:
    """The gate keys on the GREEN set negated, not on `failure` alone.

    Two independent gates were keyed on the wrong half of the same enum:
    publish.yml ships only on ``conclusion == 'success'`` and this file alerted
    only on ``conclusion == 'failure'``. A run that concludes ``cancelled``
    satisfies neither — it does not ship and it tells nobody.

    That is not a hypothetical conclusion. It happened on the merge of #1015:
    ``mutation-shard (4)`` reached ``timeout-minutes: 75``, the aggregate job
    failed, the run concluded ``cancelled``, and no release was cut and no
    issue opened. It was found by someone reading per-shard job durations out
    of the Actions API for an unrelated reason.

    A timeout is the designed behaviour of every ``timeout-minutes`` in the
    repo rather than an exotic fault: across 169 measured ``mutation-shard``
    jobs the worst took 72.5 minutes against the 75-minute cap.
    """

    def test_the_gate_names_the_green_set(self):
        gate = open_issue_gate()
        for ok in GREEN:
            assert names_conclusion(gate, ok), (
                "%r is an ordinary non-failure conclusion and must be in the "
                "green set, or every one of them opens an issue" % ok)

    def test_the_gate_is_a_negation_not_an_equality(self):
        gate = open_issue_gate()
        assert "!contains(" in gate, (
            "the gate must name what is EXCLUDED, so a conclusion GitHub adds "
            "later defaults to loud rather than silent")
        assert "conclusion == 'failure'" not in gate, (
            "keying on `failure` is the bug: `cancelled` is not `failure` and "
            "fell through both this alert and publish.yml")

    @pytest.mark.parametrize("conclusion", NOT_GREEN)
    def test_a_non_green_conclusion_is_not_excused(self, conclusion):
        gate = open_issue_gate()
        assert not names_conclusion(gate, conclusion), (
            "%r means main is not green, so it must not appear in the "
            "exclusion set" % conclusion)

    def test_the_green_set_is_disjoint_from_the_non_green_set(self):
        # Guards the test's own data: an entry added to both lists would make
        # the two assertions above contradict each other and one would win.
        assert not set(GREEN) & set(NOT_GREEN)

    @pytest.mark.parametrize("job", ["open-issue", "close-issue"])
    def test_the_job_checks_provenance_not_just_the_branch_name(self, job):
        """`head_branch == 'main'` does not mean "a run on our main".

        ci.yml runs on `pull_request`, so a fork PR opened from a branch
        named `main` produces a ci run whose ``head_branch`` is ``main``.
        publish.yml documents that as verified fact and guards with the
        event+repository pair; sbom.yml and mutation-weights-refresh.yml do
        too. This file was the only ``workflow_run`` consumer without it, and
        widening the conclusion set is what made it bite: a fork PR's
        superseded push concludes ``cancelled``, which the old
        ``== 'failure'`` gate ignored and the new one would not.
        """
        text = ALERT.read_text(encoding="utf-8")
        block = text.split("  %s:" % job, 1)[1].split("runs-on:", 1)[0]
        assert "event != 'pull_request'" in block, (
            "%s does not exclude pull_request-triggered runs" % job)
        assert "head_repository.full_name" in block, (
            "%s does not check the run came from this repository" % job)

    def test_the_guard_does_not_use_push_only(self):
        """`== 'push'` would also be wrong here, in the other direction.

        Three watched workflows — release, sbom, mutation-weights-refresh —
        are themselves `workflow_run`-triggered, so requiring a push would
        stop alerting for all of them while looking stricter.
        """
        text = ALERT.read_text(encoding="utf-8")
        assert "workflow_run.event == 'push'" not in text

    def test_only_a_real_success_stands_the_tracker_down(self):
        """Opening widened; closing must not.

        A ``cancelled`` run says nothing about whether the failure it is
        tracking is fixed, so it must not close the issue. Only ``success``
        may, which is why the closer keeps the equality the opener drops.
        """
        text = ALERT.read_text(encoding="utf-8")
        closer = text.split("  close-issue:", 1)[1]
        assert "conclusion == 'success'" in closer
        assert "!contains(" not in closer.split("runs-on:", 1)[0]

    def test_the_issue_says_which_conclusion_it_was(self):
        """`cancelled` and `failure` want different first moves — rerun the
        job versus read the log — so the body has to distinguish them.

        Scoped to the *script*, not the file. Against the whole text this
        passed vacuously: the gate's own
        ``github.event.workflow_run.conclusion`` contains the substring
        ``run.conclusion``, so the assertion held even with the body's
        conclusion replaced by a hardcoded string. A falsification run caught
        it as the one surviving mutant.
        """
        yaml = pytest.importorskip("yaml")
        doc = yaml.safe_load(ALERT.read_text(encoding="utf-8"))
        scripts = TestNoScriptBodyHoldsAnUnparseableExpression.bodies(doc)
        opener = [s for s in scripts if "issues.create(" in s]
        assert opener, "could not find the issue-opening script"
        assert any("run.conclusion" in s for s in opener), (
            "the issue body never names the conclusion, so every tracker "
            "reads as a test failure even when nothing ran")

    def test_a_non_green_ci_says_the_release_was_skipped(self):
        """publish.yml ships only on `success`, so a non-green `ci` silently
        skips that commit's release. The issue has to say so: "CI is red" and
        "and nothing was published" need different follow-ups.

        Scoped to the opening script and to the *use*, not to the file. As a
        whole-file substring check this passed while the note was computed and
        never concatenated — the string was present, the issue body was not.
        """
        script = opener_script()
        assert "No release was cut" in script, "the note is not written"
        assert "noRelease" in call_args(script, "issues.create"), (
            "`noRelease` is computed but never reaches the issue body — the "
            "string is in the file and absent from what GitHub posts")

    def test_the_repeat_comment_says_the_same_things_as_the_body(self):
        """The second non-green run of a workflow comments instead of opening.

        That path said "Still failing" and dropped the release note, so a
        `cancelled` repeat was reported as a failure and the one actionable
        sentence — rerun to publish — appeared only on the first occurrence.
        """
        script = opener_script()
        assert "Still failing" not in script, (
            "a repeat may be a cancel; the comment must not call it a failure")
        call = call_args(script, "createComment")
        assert "noRelease" in call, (
            "the repeat comment drops the release note the body carries")
        assert "note" in call, "the repeat comment does not carry the note"


class TestNoScriptBodyHoldsAnUnparseableExpression:
    """An empty ``${{ }}`` in a run or script body goes unaudited by zizmor.

    Measured while writing the change above. A comment inside this file's
    ``github-script`` body that mentioned an empty expression — to explain why
    the script avoids interpolation — made zizmor emit ``couldn't parse
    expression`` from six audits: template_injection, overprovisioned_secrets,
    unredacted_secrets, obfuscation, secrets_outside_env and unsound_ternary.

    **What that does and does not cost, measured rather than assumed.** An
    earlier draft of this docstring said it disabled those six audits "for the
    whole file", and that is false. Planting a real finding — a
    ``github.event.…head_commit.message`` interpolated into a ``run:`` — in two
    copies of this file, one clean and one carrying an empty expression, zizmor
    reported the template-injection in **both** (2 findings each). So the rest
    of the file is still analysed; what is lost is the unparseable expression
    itself, which no audit inspects, plus six warning lines that are easy to
    scroll past because the run still ends in "No findings to report".

    Worth preventing on those terms: a span that silently opts out of SAST is
    a bad place for a mistake to hide, even when its neighbours are covered.

    The scope is the body, not the file, and that was measured three ways:

    * in a YAML ``#`` comment  -> 0 parse warnings (zizmor does not read them)
    * in a ``script:`` body    -> 6
    * in a ``run:`` body, even behind a shell ``#`` -> 6

    So the rule is "no empty expression inside a body zizmor hands to its
    expression parser", which is every ``run:`` and every ``script:``. Three
    workflows mention ``${{ }}`` in ordinary YAML comments and are fine; a
    file-wide check would have failed them for nothing.

    **Known limit.** This catches one spelling. Any expression zizmor cannot
    parse costs the same six warnings, and enumerating those is a parser's job,
    not a regex's. The empty one is pinned because it is the one a comment
    explaining the rule naturally produces — which is exactly how it got here.
    """

    @staticmethod
    def bodies(doc) -> list[str]:
        """Every ``run:`` and ``with: script:`` string in a parsed workflow."""
        out = []
        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in ("run", "script") and isinstance(value, str):
                        out.append(value)
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)
        walk(doc)
        return out

    @pytest.mark.parametrize(
        "path", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name)
    def test_no_body_holds_an_empty_expression(self, path):
        yaml = pytest.importorskip("yaml")
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        for body in self.bodies(doc):
            assert not re.search(r"\$\{\{\s*\}\}", body), (
                "%s has an empty `${{ }}` in a run/script body. zizmor fails "
                "to parse it, skips six audits for the whole file, and still "
                "reports success." % path.name)

    def test_the_guard_can_actually_see_a_body(self):
        """Vacuous if the walker finds nothing.

        Checked across every workflow, not just this one. Against ALERT alone
        the guard proved only that two ``script:`` bodies parse — and ALERT has
        no ``run:`` at all, so the half of the rule that covers shell steps was
        never exercised by the thing meant to prove the walker works.
        """
        yaml = pytest.importorskip("yaml")
        total = 0
        for path in sorted(WORKFLOWS.glob("*.yml")):
            total += len(self.bodies(
                yaml.safe_load(path.read_text(encoding="utf-8"))))
        assert total > 50, (
            "the walker found %d bodies across %d workflows — it is not "
            "reading them" % (total, len(list(WORKFLOWS.glob("*.yml")))))

    def test_the_walker_finds_both_kinds_of_body(self):
        """`run:` and `script:` are different keys and both must be walked."""
        yaml = pytest.importorskip("yaml")
        doc = yaml.safe_load("""
jobs:
  a:
    steps:
      - run: echo shell
      - uses: actions/github-script@v9
        with:
          script: console.log('js')
""")
        found = self.bodies(doc)
        assert any("echo shell" in b for b in found), found
        assert any("console.log" in b for b in found), found

    def test_the_pattern_matches_the_shape_that_broke_it(self):
        assert re.search(r"\$\{\{\s*\}\}", "// mentions ${{ }} here")
        assert re.search(r"\$\{\{\s*\}\}", "x ${{}} y")
        # A real expression is not an empty one and must not be flagged.
        assert not re.search(r"\$\{\{\s*\}\}", "${{ github.sha }}")


class TestTheQuotingHelperIsNotTheWeakLink:
    """``names_conclusion`` decides every assertion above, both directions."""

    @pytest.mark.parametrize("gate", [
        'fromJSON(\'["success", "skipped"]\')',
        "conclusion == 'success'",
    ])
    def test_it_sees_either_quoting(self, gate):
        assert names_conclusion(gate, "success")

    def test_it_does_not_match_an_unquoted_substring(self):
        # `startup_failure` must not read as `failure` being excused.
        assert not names_conclusion('fromJSON(\'["startup_failure"]\')',
                                    "failure")

    def test_it_is_false_for_something_absent(self):
        assert not names_conclusion('fromJSON(\'["success"]\')', "cancelled")


class TestTheCommentStripperIsNotTheWeakLink:
    """``strip_js_comments`` is what stops prose standing in for behaviour."""

    def test_it_removes_a_whole_line_comment(self):
        assert "noRelease" not in strip_js_comments("  // about noRelease\n x")

    def test_it_keeps_the_code_beside_it(self):
        out = strip_js_comments("// gone\nconst a = 1;")
        assert "const a = 1;" in out

    def test_it_does_not_touch_a_slash_inside_a_string(self):
        line = "const u = 'https://example.test/x';"
        assert line in strip_js_comments(line)

    def test_the_real_script_still_has_its_code_after_stripping(self):
        script = opener_script()
        assert "issues.create(" in script
        assert "const note =" in script
