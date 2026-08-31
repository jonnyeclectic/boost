---
id: boost-first-carried-the-losing-trigger
board: code
section: dx
status: shipped
category: Interop · Adoption
complexity: M
impact: High
wow: 4
note: the rule shipped the one trigger boost had already measured as losing, and no revision of it could ever reach a machine that had installed it
order: 107
owner: loop/boost-first-observable-trigger
pr: 491
pr: 491
title: <code>boost-first</code> carried the trigger that had already fired and lost — and could never be updated
---
<b>Two defects, and the second is why the first survived.</b> Reported from a live session:
the rule was installed, materialized into <code>claude-code</code>, and sitting in the agent's
context for the whole conversation — and the agent still built a subsystem, a generator script
and a test file without calling either boost tool.

<b>What the rule actually said.</b> Measured across boost's three agent-facing surfaces, by
phrase, against the evaluated constants rather than the source (these strings are concatenated
across literals, so grepping the file lies):

Each row is <em>trigger</em> &middot; <code>INSTRUCTIONS</code> &middot; <code>boost_search</code>
description &middot; <b>the rule</b>:
<em>the task <b>has a name</b> you could say out loud</em> &middot; yes &middot; yes &middot;
<b>NO</b>. &nbsp;
<em>touches <b>more than one file</b></em> &middot; yes &middot; no &middot; <b>NO</b>. &nbsp;
<em>something that <b>outlives this session</b></em> &middot; yes &middot; no &middot; <b>NO</b>. &nbsp;
<em>ask again when a small task <b>turns out to be a large one</b></em> &middot; yes &middot; no
&middot; <b>NO</b>. &nbsp;
<em>the lock-in list (<b>new project or subsystem…</b>)</em> &middot; no &middot; yes &middot;
yes. &nbsp;
<em>the defeater (<b>one kind of three</b>)</em> &middot; yes &middot; yes &middot; yes.

The rule carried <b>exactly one</b> trigger — and it is the one <code>core/mcp.py</code> already
documents as having failed. The forensics in that file are unambiguous: a Gemini CLI session
paraphrased "a new project or subsystem, an architecture decision, environment and tooling
config" back when asked, and had <em>still</em> skipped the call. #479 answered that two ways —
a defeater for the veto, and triggers that are properties of the <b>request</b> rather than a
judgement about work not yet done, because "deciding a task is non-trivial takes judgement while
'this turn looks small' is free, and every turn looks small when it opens."

<b>The rule took the defeater and left the triggers behind.</b> It shipped in #480, after #479,
carrying the losing half on its own. That matters more here than on any other surface: Gemini CLI
never delivers server <code>instructions</code> in interactive mode and starts no MCP servers at
all in an untrusted folder, so on the host where the failure was measured this file is the
<em>only</em> boost text in context — and it was the one surface with no observable trigger on it.

<b>A natural experiment worth recording.</b> In the reporting session two standing instructions
sat within a few lines of each other in the same global <code>CLAUDE.md</code>. The Snyk one was
followed; this one was not. Position did not distinguish them — trigger shape did. Snyk's fires on
a fact the agent can observe ("did I write code?") <em>after</em> writing, when it is already
reviewing. boost's asked it to classify a task's nature <em>before</em> starting, at the moment it
is least oriented. So the fix is not louder wording, and deliberately not: editing only a
description moves call rates &gt;10x (EMNLP 2025), which is exactly why every boost surface stays
invitational and the coercion ban is test-pinned.

<b>What it says now.</b> The two request-readable signals, the cheapest name test, and the
re-entry clause, all worded as their siblings word them — plus one new clause, because the failure
mode was never a refused check but one that was never visibly considered: <em>say which way it
went, name the call you made or the reason you skipped it.</em> A disclosure obligation rather
than an order to search — naming the reason you skipped is a complete answer, and the skip list
stays exactly as wide as it was.

<b>The second defect: none of that could have reached anyone.</b>
<code>ensure_tap()</code> has exactly one caller — the <code>boost mcp register</code> offer — and
that offer never runs twice. So the copy under <code>~/.boost/repos/boost__builtin/</code> is
written once, at accept time, and never again. <code>boost update</code> then reached for git
against a directory that is not a clone (<code>is_cloned</code> is false, so it took the
<em>clone</em> branch and handed git the <code>builtin:boost</code> sentinel as a URL), the tap
landed in <code>failures</code>, and every downstream loop skips a tap that is not in
<code>results</code>.

Measured on a sandbox HOME holding the older rule, after both <code>boost update</code> and
<code>boost sync</code>: wheel <b>NEW</b>, tap copy <b>OLD</b>, CLAUDE.md <b>OLD</b>, GEMINI.md
<b>OLD</b>. A rule fixed in the wheel was unreachable on every machine that already had it — and
<code>boost update</code> additionally printed "1 of 1 taps could not be refreshed" on every run,
advising <code>boost untap</code> for a tap behaving exactly as designed.

<b>The fix is one branch.</b> A tap whose URL carries the <code>builtin:</code> scheme refreshes
by re-copying package data instead of pulling. Everything downstream already worked:
<code>_update_materialized</code> hashes file <em>content</em> rather than consulting a git HEAD,
so landing the tap in <code>results</code> is the whole change. Verified end to end — wheel, tap
copy, CLAUDE.md and GEMINI.md all move together, and the module docstring's claim that the rule
"tracks boost's version rather than drifting once written" is finally true of
<code>boost update</code> and not merely of a call nothing makes twice.

<b>And a parity test, which is the part that outlives the wording.</b> Six load-bearing phrases
are now pinned on both the rule and <code>INSTRUCTIONS</code>, failing in either direction. A
phrase added to one and not the other is precisely how the rule came to ship a trigger its
siblings had already retired.

<b>One suspicion measured and dropped.</b> <code>store.source_dir_for</code> requires a
<code>SKILL.md</code>, which suggested every installed <em>rule</em> was silently skipped by
<code>boost update</code>. Built a real git tap with a rule in it, changed it upstream, ran the
command: "refreshed rule driftrule v0.0.0 (source changed)". Rules from a git tap update
correctly — <code>_update_materialized</code> never calls that function. The bug was only ever
the builtin tap.
