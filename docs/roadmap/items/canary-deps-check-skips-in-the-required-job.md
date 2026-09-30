---
id: canary-deps-check-skips-in-the-required-job
board: code
section: trust
status: planned
category: CI · Coverage
complexity: S
impact: Med
wow: 2
note: the test that keeps CI's venvs honest does not run in the job most people read
order: 361
pr:
title: "test_canary_deps.py needs PyYAML, which the required tests job does not install — so it only runs inside the mutation gate"
---
<code>tests/unit/test_canary_deps.py</code> opens with
<code>yaml = pytest.importorskip("yaml")</code>, because it reads the workflow files to check that
every job assembling its own venv installs what the suite then imports. PyYAML is pinned in
<code>requirements/lint-tools.txt</code> and <code>requirements/mutation-tools.txt</code> and in
neither <code>test-tools.txt</code> nor <code>coverage-tools.txt</code>.

So in CI's required <code>tests</code> job &mdash; the 90% coverage gate, the leg a contributor
actually reads &mdash; the whole file <b>skips</b>. Same for <code>sonarcloud</code> and for the
free-threaded canary, the very leg it was written to protect.

<b>It is still enforced, in an odd place.</b> <code>setup.cfg</code> sets
<code>pytest_add_cli_args_test_selection = tests/unit/</code> and copies <code>.github/</code> into
<code>mutants/</code>, and <code>mutation-tools.txt</code> pins PyYAML &mdash; so the file runs in
the mutation gate's baseline, and a failure there fails a required check. But it reports as
<code>mutation gate: `mutmut run` failed to execute</code> with every shard red and nothing naming
the workflow file, which is the failure mode <code>setup.cfg</code>'s own comments call out three
separate times as a confusing way to learn about a missing file.

<b>The fix is one line in a declaration and one regenerated lock:</b> add <code>pyyaml</code> to
<code>requirements/test-tools.in</code> with the reason, run
<code>python3 scripts/lock_toolchain.py</code>, commit both. Kept out of the pull request that
found it deliberately &mdash; adding a dependency to the required gate's hash-pinned install is a
choice that gets made and reviewed on its own, per that script's own docstring, and it is a
different defect from "the check only read one job".
