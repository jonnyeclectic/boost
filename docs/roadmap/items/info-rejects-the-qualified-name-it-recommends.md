---
id: info-rejects-the-qualified-name-it-recommends
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: High
wow: 4
note: fixed — one grammar, split once, and the hint is now a runnable command
order: 71
owner: loop/info-qualified-name
pr: 413
title: <code>boost info</code> rejects the tap-qualified name its own error tells you to type
---
A name carried by more than one tap produces an error whose hint names the way out — and the
way out did not work:

<code>$ boost info differential-review</code><br>
<code>Error: 'differential-review' exists in multiple taps: trailofbits/skills, vibeeval/vibecosystem, lingxling/awesome-skills-cn</code><br>
<code>&nbsp;&nbsp;hint: qualify it, e.g. `trailofbits/skills:differential-review`</code><br>
<code>$ boost info trailofbits/skills:differential-review</code><br>
<code>Error: invalid skill name 'trailofbits/skills:differential-review'</code>

<b>Two consumers, two grammars.</b> <code>cmd_info</code> handed the raw argument to both
<code>catalog.resolve_one</code>, which has understood <code>owner/repo:skill</code> all along
(<code>find()</code> did <code>name.rsplit(":", 1)</code> inline), and
<code>store.skill_store_dir</code>, which validates its argument as a <em>single path
component</em> and so rejected the qualified string outright via
<code>util.is_safe_component</code>. That second call sat <em>outside</em> the
<code>if lock:</code> guard, so it ran on every invocation — meaning the failure had nothing to
do with being installed, and the hint named a command the command itself refused.
<code>boost install</code> was never affected: it works from <code>entry["name"]</code> after
resolving, not from <code>argv</code>.

This is the consumer-side half of
<a href="#ambiguous-tap-short-name-resolution">ambiguous-tap-short-name-resolution</a>. That
item made both <em>resolvers</em> tier their tap matching so an ambiguous short name errors
instead of guessing; it had no reason to look at whether the callers could actually spell the
qualified form it started recommending. Tiering the resolver and rejecting the qualified name
at the caller are individually defensible and jointly a dead end.

<b>Shipped.</b> The <code>tap:skill</code> grammar moves out of <code>find()</code>'s body into
<code>catalog.split_name</code> and <code>catalog.tap_matches</code>, so everything keyed by the
<em>bare</em> name — the lock file, the canonical store — splits it exactly the way
<code>find()</code> does. <code>cmd_info</code> and <code>_resolve_skill_md</code> now split
once: qualified form for catalog lookups, bare name for the lock and the store.
<code>split_name</code> returns <code>None</code> rather than <code>""</code> for an unqualified
name, so <code>find()</code> keeps overriding its <code>tap</code> kwarg only when a qualifier
was really present and its behaviour is unchanged.

A second defect surfaced while fixing the first. Honouring the qualifier only in the catalog
lookup would leave the <em>installed</em> record unfiltered — with a skill installed from one
tap, <code>boost info tap-b:skill</code> would have reported tap A's install as tap B's own.
<code>_for_tap</code> drops a lock entry whose tap the qualifier does not select, the project
lock gets the same treatment, and <code>_resolve_skill_md</code> shares it so
<code>cat</code>/<code>preview</code>/<code>explain</code>/<code>deps</code> follow suit.
<code>edit</code> and <code>tag</code> are deliberately untouched — they act only on installed
items, where the bare name is already unambiguous.

<b>The regression test runs the hint.</b> Rather than assert the fix, it parses the suggested
command out of stderr and executes it, so hint and behaviour cannot drift apart again:
<code>m = re.search(r"qualify it, e\.g\. `([^`]+)`", r.err)</code> then <code>boost("info",
m.group(1))</code>. A <code>rival_tap</code> fixture — a second real git tap also shipping
<code>brainstorming</code> — covers qualifier-selects-the-named-tap, <code>--json</code>
reporting the bare name, finding the installed copy when the tap agrees, and <em>not</em>
reporting another tap's install as this one's. The unit tests target the mutants the gate would
otherwise leave alive: <code>rsplit</code> vs <code>split</code>, the <code>bool(tap_name)</code>
guard, and <code>split("/")[-1]</code> vs <code>[0]</code>. <code>mutmut results</code> lists no
survivors in either new function.
