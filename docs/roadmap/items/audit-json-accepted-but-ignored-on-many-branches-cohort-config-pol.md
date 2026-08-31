---
id: audit-json-accepted-but-ignored-on-many-branches-cohort-config-pol
board: code
section: dx
status: planned
category: CLI · Bug
complexity: M
impact: Med
wow: 1
note: seven commands take --json, then print "✓ set ai.enabled = true" prose with exit 0
order: 231
owner:
pr:
title: "--json accepted but ignored: <code>cohort</code>/<code>config</code>/<code>policy</code> set, <code>focus</code>, <code>profile</code>, <code>replay rollback</code>, <code>who</code> empty state"
---
The mirror image of the missing-<code>--json</code> sweep: these parsers <em>accept</em>
<code>--json</code>, then whole branches print human text to stdout and exit 0 &mdash; a script
that asked for JSON gets unparseable prose and no error. Verified live on every member:
<code>cohort apply --json</code> &rarr; <em>"==&gt; cohort everyone &hellip; applied: 0 installed,
1 already present"</em> (create/delete too) &middot; <code>config set ai.enabled true --json</code>
&rarr; <em>"&#10003; set ai.enabled = true"</em> (unset too; only list/get honour the flag) &middot;
<code>policy set/unset --json</code> &rarr; the same &#10003; line &middot;
<code>focus brainstorming --json</code> &rarr; <em>"&#8977; focus: brainstorming (other 1 skills
sidelined)"</em>, and <code>--clear --json</code> likewise &mdash; only <code>--status</code> emits
JSON &middot; <code>profile save/use/delete --json</code> &rarr; <em>"&#10003; saved profile daily
(2 skills)"</em> &middot; <code>replay rollback &lt;id&gt; --json</code> &rarr; the human rollback
transcript &middot; <code>who --json</code> on an empty journal &rarr; <em>"&#9675; no journal
activity yet&hellip;"</em> where <code>pulse --json</code> prints <code>[]</code> in the same state.
<code>update --json</code> without <code>--shards</code> prints tap prose the same way, though its
help does say <em>"with --shards"</em> &mdash; accept-and-ignore rather than an undocumented lie.

Every one of the six unqualified commands advertises a bare <em>"machine-readable output"</em> help
string, so the contract is broken silently: exit 0, wrong content. The fix is one pattern across the
seven: each action either emits a small JSON object under <code>--json</code> (action, key/name,
outcome lists; <code>who</code>/<code>focus</code> empty states emit <code>{}</code> /
<code>[]</code>) or the parser rejects the combination with a usage error naming the actions the flag
supports &mdash; and each <code>--json</code> help string gets qualified the way
<code>update</code>'s and <code>schedule</code>'s already are. Sites:
<code>boost_cli/commands/team.py:69-300</code>, <code>intelligence.py:945-1050</code>,
<code>configuration.py</code>, <code>pkg.py</code>. Help strings change, so regenerate
<code>docs/commands.html</code>. Found by the 2026-08 CLI audit (cluster
<code>json-flag-ignored</code>); repro in the audit log.
