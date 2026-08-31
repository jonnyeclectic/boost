---
id: audit-stray-positionals-and-inapplicable-flags-silently-ignored-ac
board: code
section: dx
status: planned
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: import --all --name X imports everything; config get KEY VALUE reads as a confirmed set
order: 238
owner:
pr:
title: "Stray positionals and inapplicable flags silently ignored across <code>import</code>, <code>config</code>, <code>policy</code>, <code>trust</code>, <code>log</code>, <code>schedule</code>, <code>hooks</code>, <code>snapshot</code>"
---
An argparse hygiene gap, uniform across eight commands: optional positionals swallow words the
action never reads, and inapplicable flags are accepted without comment.
<code>import fx/multi --all --name ab-testing</code> imports all three skills &mdash;
<em>&ldquo;Imported 3 skills&rdquo;</em>, exit 0 &mdash; because <code>pkg.py:1389</code> reads
<code>if name and not do_all:</code>, so <code>--name</code> is dropped.
<code>trust list extra1 extra2</code> prints the full listing, exit 0.
<code>schedule status --interval daily</code> exits 0 with the plain status.
<code>config list extra</code>, <code>policy list extra positional</code>,
<code>snapshot list extra-arg</code>, <code>log --diagnostics --crashes NAME</code> and
<code>hooks list SessionStart</code> (all seven rows, unfiltered) all behave as if the extra words
were absent. The worst consequence is the config-get variation: <code>config get ai.enabled
false</code> &mdash; a typo for <code>set</code> &mdash; prints <em>&ldquo;true&rdquo;</em> and
exits 0, so a mistyped <code>set</code> reads as a confirmed set.

No help text blesses ignoring arguments, and sibling commands (<code>conflict extra</code>,
<code>health extra</code>) already reject strays &mdash; the codebase's own convention says error.
Individually low-severity; med as a cluster because <code>import --all --name</code> and
<code>config get KEY VALUE</code> change or misrepresent real outcomes. Verified across
<code>boost_cli/commands/pkg.py:1370-1395</code> and the action parsing in
<code>boost_cli/commands/configuration.py</code> (<code>cmd_config</code>/<code>cmd_policy</code>/<code>cmd_schedule</code>).

Verified fix, one sweep: after <code>parse_args</code>, call <code>p.error()</code> when an action
received a positional or flag it never reads &mdash; <code>config list KEY</code>,
<code>get</code>/<code>unset</code> VALUE, <code>policy list</code>/<code>check</code> strays,
<code>trust list</code>/<code>remove</code> extras, <code>snapshot list</code> arg,
<code>log NAME --diagnostics</code>, and <code>schedule --interval</code> outside
<code>enable</code> (use <code>default=None</code> to detect an explicit flag) &middot; make
<code>import --all</code>/<code>--name</code> a mutually-exclusive group &middot; have
<code>hooks list EVENT</code> filter rather than ignore, matching the user's evident intent.
Regenerate docs/commands.html if help strings gain &ldquo;(enable only)&rdquo;-style annotations.
Found by the 2026-08 CLI audit (cluster <code>stray-args-ignored</code>); repro in the audit log.
