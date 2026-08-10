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

Nothing raised, so the name travelled — into <code>config.json</code>, through
<code>Tap.safe_name</code>, and eventually into a filesystem call, where it died as
<code>ValueError: lstat: embedded null character in path</code> from inside
<code>posixpath.realpath</code>. That message names neither the tap nor the command, and a
<code>ValueError</code> is not a <code>BoostError</code>, so the CLI's error handling never got to
frame it.

<b>The diagnosis had to be re-done rather than accepted.</b> An automated audit reported this as
"an uncaught-exception bug in <code>boost tap</code>", and running the payload showed
<code>parse_spec</code> returning normally — no exception at all. The real traceback, pulled from the
job log, lands on <code>tests/fuzz/fuzz_registry.py:85</code>: the harness's own containment check
calls <code>os.path.realpath</code> on the derived clone directory, and <i>that</i> is what raised.
So the fuzzer was reporting a genuine defect from a location that made it look like a harness bug —
which is a good argument for reading the traceback rather than the summary.

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
