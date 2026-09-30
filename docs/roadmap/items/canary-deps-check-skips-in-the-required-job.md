---
id: canary-deps-check-skips-in-the-required-job
board: code
section: trust
status: shipped
category: CI · Coverage
complexity: S
impact: Med
wow: 2
note: it skipped in all six jobs that run the suite, not the three this card first counted
order: 361
pr: 1009
owner: loop/canary-deps-pyyaml
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

<b>Six jobs, not three.</b> This card first named the required <code>tests</code> job,
<code>sonarcloud</code> and the canary. Asking <code>_harness_jobs()</code> which of them install
PyYAML answered <b>none of the six</b> &mdash; <code>ci.yml</code>'s
<code>tests</code>, <code>patch-coverage</code>, <code>canary</code> and
<code>onnx-inference</code>, <code>floors.yml:lowest</code> and
<code>sonarcloud.yml:sonar-analyze</code> alike. The file guards every venv CI builds by hand and
ran in not one of them.

<b>Shipped:</b> <code>pyyaml</code> declared in <code>requirements/test-tools.in</code>, which
<code>coverage-tools.in</code> already pulls in with <code>-r</code>, so one declaration reaches
both hash-pinned locks; and added to the two jobs that name their distributions on the command
line rather than from a file (<code>ci.yml</code>'s canary and <code>floors.yml:lowest</code>).
The regeneration touched pyyaml lines only &mdash; no unrelated version churn &mdash; and
<code>--check</code> and <code>--audit</code> both pass. It <em>removes</em> a marker:
<code>mutation-tools.txt</code> had <code>pyyaml ; python_full_version != '3.13.*'</code> because
only <code>libcst</code> wanted it there, and the requirement is now unconditional, which is why
<code>platform-pins.lock</code> loses a line in the direction that widens coverage rather than
narrowing it.

<b>And a test, because the declaration is the easy half.</b>
<code>test_every_harness_job_can_import_yaml</code> fails the build if any hand-built venv stops
installing it. Its sibling <code>test_every_harness_job_installs_what_the_suite_imports</code>
cannot catch this and correctly so: it scans for <em>unguarded</em> imports, and an
<code>importorskip</code> is guarded by construction. A guard that switches the whole file off in
every job it guards is the one case where being guarded is the defect.

Kept out of the pull request that found it deliberately &mdash; adding a dependency to the
required gate's hash-pinned install is a choice that gets made and reviewed on its own, per that
script's own docstring, and it is a different defect from "the check only read one job".
