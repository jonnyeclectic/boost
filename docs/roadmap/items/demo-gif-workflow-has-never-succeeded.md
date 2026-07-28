---
id: demo-gif-workflow-has-never-succeeded
board: code
section: docsite
status: shipped
category: Bug
complexity: S
impact: Low
wow: 2
note: 3 runs, 3 failures, 0 PRs opened
order: 52
owner: loop/fix-demo-recorder
pr: 294
title: <code>demo.yml</code> has failed every run since it landed — vhs-action cannot install ffmpeg
---
<code>demo.yml</code> re-records <code>docs/demo.gif</code> with
<code>charmbracelet/vhs-action</code> and opens a PR when the recording changes. It exists
because "a generated artifact whose regeneration is manual is one nobody regenerates".
All <b>3 of its 3 runs</b> since 2026-07-26 failed at the recording step with the annotation
<code>Failed to install ffmpeg</code>, so the follow-on "open a PR" step was skipped every
time and it has never produced a single PR.

The net effect is worse than not having it: <code>demo.gif</code> is exactly as stale as
before, but the repo now looks covered. Same class as the LangGraph conformance leg — a leg
that has never passed since the day it was added. A secondary annotation on the same runs
flags that vhs-action v2.1.0 targets Node 20, now deprecated and force-run on Node 24.

Options: install ffmpeg explicitly before the action runs, pin a runner image that carries
it, switch to a maintained recorder, or delete the workflow and regenerate the GIF by hand.
Whichever is chosen, the workflow should fail loudly rather than sit red indefinitely — a
scheduled job nobody reads is how this went unnoticed for its whole lifetime.
