---
id: discover-searches-github-not-a-stale-sample
board: code
section: dx
status: inflight
category: DX · Feature
complexity: M
impact: High
wow: 4
note: an adversarial review of the first draft confirmed 21 defects, two of which would have reddened CI
order: 106
owner: loop/discover-live-github-search
pr:
title: <code>boost discover &lt;query&gt;</code> asks GitHub, instead of filtering whatever <code>boost index</code> happened to sample
---
<b>What was wrong.</b> <code>boost discover react</code> read as a question about GitHub and
was answered by a local cache — one built by <code>boost index</code>, which sampled
<code>filename:SKILL.md</code> with no query at all and kept whatever code search ranked
first. So the command could only ever return a subset of an untargeted draw, and its miss
message — <em>"no indexed skills match 'react'"</em> — read as a verdict on GitHub when it
was a verdict on that cache. The MCP tool <code>boost_discover_github</code> had reached
GitHub live the whole time; only the CLI did not.

<b>What it does now.</b> A query goes to GitHub. <code>--local</code> keeps the offline
path, a bare <code>boost discover</code> still browses the cache for free, and a failure
to reach GitHub falls back rather than erroring. <code>boost index</code> accepts a
positional query so a build can be aimed. Results collapse to one row per repository —
naming a repo worth tapping is the whole point, and code search returns a row per file, so
a registry that mirrors its skills into a directory per agent could otherwise fill the
page with itself.

<b>Two error messages in <code>resolve_one</code> came along.</b> The "closest matches"
hint de-duplicates, because that same mirroring made it render
<code>mempalace, mempalace, mempalace</code> — three of nothing — and it now qualifies with
the tap only when a name genuinely spans registries, which is exactly when the bare name
would not resolve either. And <code>tap:path/to/skill</code> now names the grammar error
instead of fuzzy-guessing: <code>tap:skill</code> picks a <em>registry</em>, so a
path-shaped tail is a misread of the syntax, and the hint hands back the
<code>--path</code> form that works.

<b>An adversarial review of the first draft raised 28 findings and confirmed 21.</b> Worth
recording because two of them would have shipped red, and several were the same shape as
the bug being fixed — a promise the code did not keep.

<b><code>--limit</code> was spent on the wrong unit.</b> It is documented as "max rows",
and a row is a repo, but it was passed through as code search's <code>per_page</code>, so
it bounded <em>files</em>. Collapsing then shrank that further, and the second slice was
provably dead: <code>len(rows) ≤ len(hits) ≤ per_page ≤ limit</code>, so it could never
trim an element. Measured against a mock that honours <code>per_page</code> over a
200-file pool front-loaded the way code search actually ranks:
<code>--limit 25</code> returned <b>1 row</b>, <code>--limit 50</code> returned 3.
The command now fetches the whole 100-hit page and slices to <code>--limit</code>
<em>after</em> collapsing, which is also what makes that second slice load-bearing.

<b><code>--json</code> destroyed the only signal that said which corpus answered.</b> The
fallback warnings were suppressed under <code>--json</code> to keep stdout parseable, so a
script could not distinguish "GitHub has no matches" from "GitHub was never searched" —
and the two answers arrive in <em>different row shapes</em>. Fixed twice over: the notices
go to stderr, so stdout stays clean and the signal survives, and every row in both paths
carries <code>source: github</code> or <code>source: local-index</code>.

<b>The fallback told users to drop a flag they never passed.</b> A miss after falling back
printed "drop <code>--local</code> to search GitHub itself" directly under a warning
saying GitHub could not be reached — contradicting itself, and advising an action the user
could not take. The wording now depends on which of the two paths reached it.

<b>GitHub-supplied text was rendered into a terminal table raw.</b> A repo name or file
path is attacker-chosen; <code>\x1b[1A\x1b[2K</code> moves the cursor up a line and erases
it, so one crafted field can rewrite rows already on screen — including the row naming the
repo the user was about to tap. <code>output.plain()</code> now strips C0/C1 controls at
the point of display, and both the live and cached tables go through it.

<b>Two CI-reddening misses the local run would not have caught.</b>
<code>docs/index.html</code> carries its own copy of the <code>COMMANDS</code> list, gated
by <code>test_docsite_chrome.py</code>, so updating the summary in <code>cli.py</code>
alone fails the suite. And <code>tests/bdd/features/discover.feature</code> still assumed
a query filters the index: one scenario asserted a message that no longer exists, and two
more would have shelled out to <em>real GitHub</em> on any runner that ships
<code>gh</code> — a required check hostage to someone else's rate limit. Every local-index
scenario now pins <code>gh</code> as absent rather than trusting the runner.

<b>And one test that proved only its own formatting.</b> The <code>--path</code> hint was
asserted as a string, never run. Executing it is what revealed that it dropped the tap
qualifier the user had already typed correctly — so the suggested "fix" resolved in the
wrong registry, or failed as cross-tap ambiguous, for precisely the user who needed the
tap. The test now lifts the arguments back out of the hint and feeds them to
<code>resolve_one</code>.
