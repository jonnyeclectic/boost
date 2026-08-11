---
id: unwatched-crons-hid-a-real-fuzz-crash
board: code
section: pipeline
status: shipped
category: Build · Bug
complexity: M
impact: High
wow: 5
note: the fuzzer found a real crash and was right for three weeks — 24 unattended workflows, 2 watched
order: 108
owner: fix/parse-spec-control-chars
pr:
title: The fuzzer found a real crash and nobody was listening
---
<code>fuzz.yml</code> runs libFuzzer over <code>registry.parse_spec</code> weekly. It has failed
<b>three scheduled runs out of three</b> — 2026-07-25, 08-01 and 08-08 — writing the same minimised
reproducer each time. It was right every time, and nobody looked for three weeks.

<b>The crash.</b> Ten bytes, <code>/\0\0\0\0\0\0\0\0A</code>. <code>parse_spec</code> accepted them
and returned a perfectly well-formed pair:

<code>('/\0…A', 'https://github.com//\0…A')</code>

Nothing raised, so the name travelled — into <code>config.json</code> and through
<code>Tap.safe_name</code> into a clone path built around a NUL byte.

<b>The diagnosis was re-done twice, and both corrections matter.</b> An automated audit first
reported this as "an uncaught-exception bug in <code>boost tap</code>". Running the payload showed
<code>parse_spec</code> returning normally, and the real traceback — from the job log — lands on
<code>tests/fuzz/fuzz_registry.py:85</code>, where the harness's own containment check calls
<code>os.path.realpath</code>. An adversarial re-check then killed the rest of the product claim, and
it is worth stating plainly because the first draft of this card got it wrong:

<b>A NUL can never reach the CLI at all.</b> <code>execve</code> refuses an argument containing one
(<code>ValueError: embedded null byte</code>), so <code>boost tap $'/\0…A'</code> is not a command
that can be run. And in-process the product does <i>not</i> crash either:
<code>pathlib</code> swallows the error, so <code>Tap.path.exists()</code> simply returns
<code>False</code>. Only <code>os.path.realpath</code> raises — and the sole caller of that is the
fuzz harness.

So the honest case for the fix is not "the CLI crashes". It is three narrower things.
<b>First</b>, other control characters are <i>not</i> execve-blocked — <code>\x1b</code> survives
<code>argv</code> intact, so an escape sequence in a tap name reaches the CLI and is echoed by every
surface that prints a tap list. <b>Second</b>, a NUL-bearing name yields a path whose
<code>exists()</code> is permanently <code>False</code> — silently wrong beats loudly broken only
until someone has to debug it. <b>Third</b>, and largest: the harness died on its <b>1,322nd</b>
unit, so the run recorded <code>new_units_added: 0</code> and
<code>average_exec_per_sec: 0</code> — <b>the registry parser has had no fuzz coverage at all since
the workflow was added on 2026-07-24</b>, while still costing a runner slot every Saturday.

<b>Fixed at the parse boundary.</b> A control character cannot appear in a GitHub
<code>owner/repo</code>, in a git URL, or in a usable directory name, so rejecting them turns nothing
legitimate away — and it converts an arbitrary later <code>ValueError</code> into the documented
<code>BoostError</code> rejection path, which the fuzz harness already handles and the CLI already
renders with a hint. <code>\x1b</code> matters for a second reason: an escape sequence in a name is
echoed back by every surface that prints a tap list. Verified by running the real harness over the
exact reproducer, which now passes.

<b>The reason it stayed hidden is the more valuable half.</b>
<code>ci-failure-issue.yml</code> opens a tracking issue when a watched workflow fails on
<code>main</code>, and its own header states the rule: <i>"Any workflow that runs on main and nobody
watches belongs here."</i> It watched <b>two</b>. <b>Twenty-four</b> ran unattended — fourteen on a
cron. The rule was written down and not applied, which is the most expensive kind of convention,
and it is the same blind spot that let <code>shards</code> fail both its scheduled runs and publish
zero artifacts.

All twenty-six are watched now, and the list is <b>enforced rather than curated</b>:
<code>tests/unit/test_failure_alerting_covers_unattended.py</code> fails the build when a workflow
runs unattended and is neither watched nor listed in an <code>EXPECTED_UNWATCHED</code> map with a
reason. A new scheduled workflow therefore cannot quietly join the blind spot — the same shape as
the action-pin lockstep guard, where the convention stays falsifiable instead of decaying the moment
the person who wrote it stops looking.
