---
id: sweep-died-at-launch-not-at-a-page
board: code
section: pipeline
status: shipped
category: CI · Bug
complexity: S
impact: High
wow: 4
note: a comment in the sibling file predicted this exact failure
order: 114
owner: fix/visual-sweep-single-process
pr: 524
title: The <code>sweep</code> gate died at browser launch, not at a page
---
Every <code>sweep</code> run failed from 2026-08-15 onward — on <code>main</code>
and on every branch — and the failure was not a visual regression at all. Chrome
died during the CDP startup handshake, before a single page loaded:

<code>TargetCloseError: Protocol error (Target.setAutoAttach): Target closed</code>
out of <code>ChromeLauncher.launch</code>.

<b>The trigger was the environment, and the evidence is an A/B on identical
trees.</b> <code>#515</code>'s own PR run passed on 2026-08-13 at 17:22; the
byte-identical squash-merge failed on 2026-08-15 at 22:10. Same content, opposite
result, two days apart — the <code>ubuntu-latest</code> runner image bumped
Chrome underneath it. Nothing in the repo changed;
<code>visual_check.mjs</code> had carried the same flags since <code>#209</code>.

<b>The sibling file predicted it, in a comment, by name.</b>
<code>a11y_check.mjs</code> was fixed earlier to scope <code>--single-process</code>
to the <code>chrome-headless-shell</code> binary, and its comment recorded why the
other half of the directory was still exposed: <em>"visual_check.mjs already
passes the flag … <code>--single-process</code> is a debug-only flag there whose
interaction with new headless nothing in this repo exercises."</em> That is
exactly the interaction that broke.

<b>Two candidate causes, both addressed, because the CI path cannot be
reproduced locally.</b> <code>--single-process</code> is debug-only and
unsupported against full Chrome; and <code>headless: "shell"</code> asks for the
old headless mode, which Chrome removed from the main binary and now ships only
as the separate <code>chrome-headless-shell</code> executable. Both are now
conditioned on the same predicate the a11y harness uses, so against
<code>/usr/bin/google-chrome</code> the sweep launches in new headless with
neither flag — the shape <code>a11y_check.mjs</code> has been driving on this
runner all along. Keyed on the <em>binary</em> rather than on
<code>process.platform</code>: a macOS run pointed at full Chrome must not
inherit a flag meant for the shell.

<b>What was verified, and what was not.</b> The harness runs end to end and
passes <b>10 pages × 5 widths clean</b> against a downloaded
<code>chrome-headless-shell</code> 152 — which also proves the docs pages
themselves were never the problem. The flag selection was evaluated directly for
four binary paths. The <em>CI</em> path is not locally reproducible and this card
says so rather than implying otherwise: full Chrome cannot start under this macOS
sandbox at all, aborting with <code>The browser is already running for
&lt;fresh profile dir&gt;</code> from ProcessSingleton — a different error from
CI's, so it is interference, not a reproduction. CI is the verifier.

<b>The ratchet.</b> <code>tests/unit/test_visual_harness_flags.py</code> fails
the build if either harness hands a sandbox-only flag to a full Chrome, and if
the two stop agreeing on the predicate. The bug here was not the flag — it was
that one file was fixed and the other was not, and the only thing recording that
was a comment. A comment cannot fail a build.
