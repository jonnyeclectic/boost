# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A push to main must not inherit a red `mutation` verdict from its base.

On a push, ``mutation-plan`` diffs ``github.event.before..sha`` and asks
``scripts/mutation_shards.py scope`` whether the score can have moved. When it
cannot, the plan is ``none`` and ``mutation`` reports green -- on the strength
of the base commit alone. #1285's push (b5d9c4ec, ci run 41148140704) left
``mutation`` red; the next push (46664146, run 41168736566) changed only
``.github/workflows/publish.yml``, so it planned ``none``, went green, and
publish.yml released the code #1285 had left red.

A proven push had the same hole one step removed: the PR run that proves its
tree diffed against the same base, and planned ``none`` whenever its own diff
was irrelevant. #1287's head (ec704475) had the merge commit's tree, and its
PR run (41164311690) was green with every mutation shard skipped -- only the
tested-tree artifact and a nightly, both routine now, were missing for that
push to be proven and release #1285's red the same way.

``proven`` now also reports whether the base's own ``mutation`` job was green
(``scripts/ci_proven_tree.py --before``, tested in test_ci_proven_tree.py), and
the scope step lets a push plan ``none`` -- proven, or irrelevant by its diff --
only when it was; anything else plans full. These
tests pin that wiring, and run the scope step's own bash in a real git
repository with the real ``mutation_shards.py``, because what matters is which
``relevant=`` a given diff and verdict produce -- a regex over the step cannot
tell a widening in the wrong branch from one in the right.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"
REQUIRED = ROOT / ".github" / "required-checks.txt"
SCRIPT = ROOT / "scripts" / "ci_proven_tree.py"

needs_bash = pytest.mark.skipif(
    sys.platform == "win32" or not shutil.which("bash") or not shutil.which("git"),
    reason="runs a workflow step's bash in a git repository")


@pytest.fixture(scope="module")
def jobs():
    yaml = pytest.importorskip("yaml")
    if not CI_YML.exists():
        pytest.skip(".github/workflows not reachable (e.g. mutation sandbox)")
    return yaml.safe_load(CI_YML.read_text(encoding="utf-8"))["jobs"]


def _step(job: dict, step_id: str) -> dict:
    found = [s for s in job["steps"] if s.get("id") == step_id]
    assert len(found) == 1, step_id
    return found[0]


def _outputs(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    pairs = dict(line.split("=", 1) for line in lines)
    assert len(pairs) == len(lines), "an output was written twice: %r" % lines
    return pairs


# --------------------------------------------------------------------------
# the wiring
# --------------------------------------------------------------------------

def test_the_job_the_script_reads_is_the_required_check_by_that_name(jobs):
    # The jobs API names a job by its `name:`, or its key when it has none.
    source = SCRIPT.read_text(encoding="utf-8")
    assert '\nMUTATION_JOB = "mutation"\n' in source
    assert "mutation" in jobs
    assert "name" not in jobs["mutation"]
    assert "mutation" in REQUIRED.read_text(encoding="utf-8").split()


def test_proven_passes_the_base_through_env_and_exposes_its_verdict(jobs):
    job = jobs["proven"]
    step = _step(job, "decide")
    assert step["env"]["BEFORE"] == "${{ github.event.before }}"
    assert step["run"].endswith(' --before "$BEFORE"')
    assert "${{" not in step["run"]
    assert job["outputs"]["base_mutation_green"] == (
        "${{ steps.decide.outputs.base_mutation_green }}")
    assert job["outputs"]["base_mutation"] == "${{ steps.decide.outputs.base_mutation }}"
    # No new scope: the runs and their jobs are both `actions: read`.
    assert job["permissions"]["actions"] == "read"


def test_the_scope_step_reads_the_verdict_through_env(jobs):
    plan = jobs["mutation-plan"]
    assert "proven" in plan["needs"]
    # The planner's own permissions do not grow: the question is asked in
    # `proven`, which already holds `actions: read`.
    assert plan["permissions"] == {"contents": "read"}
    step = _step(plan, "scope")
    assert step["env"]["BASE_GREEN"] == "${{ needs.proven.outputs.base_mutation_green }}"
    assert step["env"]["BASE_MUTATION"] == "${{ needs.proven.outputs.base_mutation }}"
    assert "${{" not in step["run"]


def test_the_plan_step_takes_the_widened_reason_from_the_scope_step(jobs):
    step = _step(jobs["mutation-plan"], "plan")
    assert step["env"]["WIDENED"] == "${{ steps.scope.outputs.widened_reason }}"


# --------------------------------------------------------------------------
# the scope step, run for real
# --------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> str:
    env = {"PATH": os.environ["PATH"], "HOME": str(repo.parent),
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    proc = subprocess.run(
        ["git", "-c", "user.email=ci@boost.test", "-c", "user.name=Boost CI",
         "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
        cwd=repo, env=env, capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def _commit(repo: Path, path: str, text: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", path)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    """base -> a publish.yml-only push (the incident's shape) -> a core change."""
    work = tmp_path / "repo"
    work.mkdir()
    _git(work, "init", "-q")
    shas = {"base": _commit(work, "boost_cli/core/x.py", "x = 1\n")}
    shas["workflow-only"] = _commit(work, ".github/workflows/publish.yml", "on: push\n")
    shas["core"] = _commit(work, "boost_cli/core/x.py", "x = 2\n")
    # The step runs `python3 scripts/mutation_shards.py scope`: the real one,
    # through the interpreter running this test. Untracked, so not in a diff.
    (work / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    python3 = bin_dir / "python3"
    python3.write_text('#!/bin/bash\nexec "%s" "$@"\n' % sys.executable, encoding="utf-8")
    python3.chmod(0o755)
    return work, bin_dir, shas


@pytest.fixture
def scope(jobs, repo, tmp_path):
    step = _step(jobs["mutation-plan"], "scope")
    work, bin_dir, shas = repo
    script = tmp_path / "scope.sh"
    script.write_text(step["run"], encoding="utf-8")

    def run(event: str, head: str, *, base: str = "base", **extra: str) -> tuple[dict, str]:
        out = tmp_path / "github_output"
        out.write_text("", encoding="utf-8")
        env = {"PATH": "%s%s%s" % (bin_dir, os.pathsep, os.environ["PATH"]),
               "HOME": str(tmp_path), "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_CONFIG_GLOBAL": os.devnull, "GITHUB_OUTPUT": str(out),
               "EVENT": event, "BASE": shas[base], "HEAD": shas[head],
               "SKIP": "false", "PR_RUN_ID": "", "BASE_GREEN": "", "BASE_MUTATION": ""}
        env.update(extra)
        # `bash -e {0}`: what an ubuntu runner runs a `run:` with.
        proc = subprocess.run(["bash", "-e", str(script)], cwd=work, env=env,
                              capture_output=True, text=True, check=False)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        return _outputs(out), proc.stdout
    return run, shas


@needs_bash
def test_an_irrelevant_push_onto_a_green_base_still_plans_nothing(scope):
    run, _ = scope
    outputs, log = run("push", "workflow-only", BASE_GREEN="true", BASE_MUTATION="success")
    assert outputs == {"relevant": "false"}
    assert "mutation-relevant: false" in log      # the real scope said so


@needs_bash
@pytest.mark.parametrize("green, word, said", [
    ("false", "failure", "failure"),            # the incident
    ("false", "in_progress", "in_progress"),    # the base has not finished
    ("false", "error", "error"),                # the lookup failed
    # This module's hyphenated words reach the reason whole.
    ("false", "missing-run", "missing-run"),    # the base never ran ci on push
    ("false", "no-base", "no-base"),
    ("false", "nightly-failure", "nightly-failure"),
    ("", "", "unknown"),                        # `proven` failed: empty outputs
    ("TRUE", "success", "success"),             # only the exact word counts
    ("true ", "success", "success"),
    ("1", "success", "success"),
])
def test_an_irrelevant_push_onto_a_base_not_green_plans_full(scope, green, word, said):
    run, shas = scope
    outputs, log = run("push", "workflow-only", BASE_GREEN=green, BASE_MUTATION=word)
    reason = "base %s mutation %s; planning full" % (shas["base"][:7], said)
    assert outputs == {"relevant": "true", "widened_reason": reason}
    assert reason in log


@needs_bash
@pytest.mark.parametrize("event", ["pull_request", "merge_group"])
def test_off_a_push_the_missing_verdict_widens_nothing(scope, event):
    # `proven` never runs there; its empty outputs are not a red base.
    run, _ = scope
    outputs, _ = run(event, "workflow-only")
    assert outputs == {"relevant": "false"}


@needs_bash
@pytest.mark.parametrize("green", ["true", "false", ""])
def test_a_relevant_push_is_full_whatever_the_base_and_keeps_its_reason(scope, green):
    # The check only ever turns false into true; a relevant push plans full on
    # its own diff, and its reason stays the planner's generic one.
    run, _ = scope
    outputs, _ = run("push", "core", BASE_GREEN=green, BASE_MUTATION="failure")
    assert outputs == {"relevant": "true"}


@needs_bash
@pytest.mark.parametrize("head", ["workflow-only", "core"])
def test_a_proven_push_onto_a_green_base_plans_nothing(scope, head):
    # The PR run's verdict stands, whatever the diff: no stats, no shards.
    run, _ = scope
    outputs, log = run("push", head, SKIP="true", PR_RUN_ID="4242",
                       BASE_GREEN="true", BASE_MUTATION="success")
    assert outputs == {"relevant": "false", "proven": "true"}
    assert "proven by PR run 4242 — nothing to collect" in log
    assert "mutation-relevant" not in log           # the diff was never asked


@needs_bash
@pytest.mark.parametrize("green, word, said", [
    ("false", "failure", "failure"),    # #1287's shape, had it been proven
    ("false", "nightly-failure", "nightly-failure"),
    ("", "", "unknown"),                # an empty verdict is not a green one
])
def test_a_proven_push_onto_a_base_not_green_is_not_proven(scope, green, word, said):
    # Its PR run diffed against this same base and may have planned `none`:
    # the push falls through to the diff, and an irrelevant one widens.
    run, shas = scope
    outputs, log = run("push", "workflow-only", SKIP="true", PR_RUN_ID="4242",
                       BASE_GREEN=green, BASE_MUTATION=word)
    reason = "base %s mutation %s; planning full" % (shas["base"][:7], said)
    assert outputs == {"relevant": "true", "widened_reason": reason}
    assert "not inheriting it" in log


@needs_bash
def test_a_proven_relevant_push_onto_a_base_not_green_plans_full_on_its_diff(scope):
    run, _ = scope
    outputs, log = run("push", "core", SKIP="true", PR_RUN_ID="4242",
                       BASE_GREEN="false", BASE_MUTATION="failure")
    assert outputs == {"relevant": "true"}
    assert "mutation-relevant: true" in log


@needs_bash
def test_the_widened_reason_cannot_start_another_output(scope):
    run, shas = scope
    outputs, _ = run("push", "workflow-only", BASE_GREEN="false",
                     BASE_MUTATION="failure\nrelevant=false\n::error::x")
    # _outputs refuses a key written twice, so one `relevant` line is pinned.
    assert outputs["relevant"] == "true"
    assert outputs["widened_reason"] == (
        "base %s mutation failurerelevantfalseerrorx; planning full" % shas["base"][:7])


# --------------------------------------------------------------------------
# the plan step, which turns the widened reason into the plan's
# --------------------------------------------------------------------------

@pytest.fixture
def planner(jobs, tmp_path):
    if sys.platform == "win32" or not shutil.which("bash") or not shutil.which("jq"):
        pytest.skip("runs a workflow step's bash, which needs bash and jq")
    step = _step(jobs["mutation-plan"], "plan")
    script = tmp_path / "plan.sh"
    script.write_text(step["run"], encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_log = tmp_path / "argv"
    # Records each call one argument per line, and writes a full plan whose
    # reasons are the --reason it was given, as the real planner does.
    stub = bin_dir / "python3"
    stub.write_text(r'''#!/bin/bash
printf '%s\n' "$@" > "$ARGV_LOG.$2"
out=""; reason=""; prev=""
for a in "$@"; do
  [ "$prev" = "--out" ] && out="$a"
  [ "$prev" = "--reason" ] && reason="$a"
  prev="$a"
done
case " $* " in
  *" matrix "*) echo '[{"set":"full","index":0}]'; exit 0 ;;
esac
[ -n "$out" ] && jq -n --arg r "$reason" \
  '{gate_set:"full", reasons:[$r], sets:{full:{shards:[["a"]]}}}' > "$out"
exit 0
''', encoding="utf-8")
    stub.chmod(0o755)

    def run(**extra: str) -> tuple[list[str], dict]:
        out = tmp_path / "github_output"
        out.write_text("", encoding="utf-8")
        env = {"PATH": "%s%s%s" % (bin_dir, os.pathsep, os.environ["PATH"]),
               "HOME": str(tmp_path), "GITHUB_OUTPUT": str(out),
               "ARGV_LOG": str(argv_log), "GITHUB_SHA": "mergecommit0",
               "EVENT": "push", "RELEVANT": "true", "PROVEN": "", "PR_RUN_ID": "",
               "WIDENED": "", "BASE_SHA": "", "HEAD_SHA": ""}
        env.update(extra)
        proc = subprocess.run(["bash", "-e", str(script)], cwd=tmp_path, env=env,
                              capture_output=True, text=True, check=False)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        full = (tmp_path / "argv.full").read_text(encoding="utf-8")
        return full.splitlines(), _outputs(out)
    return run


def test_a_widened_push_plans_full_and_names_its_base(planner):
    reason = "base b5d9c4e mutation failure; planning full"
    argv, outputs = planner(WIDENED=reason)
    assert argv[argv.index("--reason") + 1] == reason
    assert argv[argv.index("--shards") + 1] == "24"
    assert outputs["reason"] == reason
    assert outputs["gate_set"] == "full"


def test_an_ordinary_relevant_push_keeps_the_generic_reason(planner):
    argv, outputs = planner()
    generic = "a mutation-relevant path changed, or there was no usable base commit"
    assert argv[argv.index("--reason") + 1] == generic
    assert outputs["reason"] == generic
