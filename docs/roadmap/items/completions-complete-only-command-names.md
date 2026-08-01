---
id: completions-complete-only-command-names
board: code
section: dx
status: shipped
category: CLI · DX
complexity: M
impact: High
wow: 4
note: arguments and flags now complete; verified in real bash and zsh, not just asserted
order: 79
owner:
pr:
title: <code>boost completions</code> completes command names and nothing else
---
<b><code>boost install &lt;TAB&gt;</code> should offer skill names. It does not, and what it offers
instead is different in each shell.</b> boost is a package manager, so completing an installable
name is the single highest-value completion it could ship &mdash; and it is the one that is wrong in
the most confusing way.

<b>Measured against the generated scripts</b> (79 commands, <code>docs/commands.html</code> as the
flag inventory):

all three shells complete <b>79 of 79</b> command names and <b>0</b> flags, and for
<code>boost install &lt;TAB&gt;</code> <code>bash</code> re-offers the 79 command names,
<code>zsh</code> offers <b>local filenames</b>, and <code>fish</code> offers nothing.

<b>The command-name half genuinely works</b> &mdash; all three emit exactly the 79 names in
<code>cli.COMMANDS</code>, verified equal as a set, and zsh and fish carry the one-line summaries.
Nothing below is a regression; it is scope that was never built.

<b>Each shell fails structurally, not by accident.</b> bash emits
<code>complete -W "&lt;79 names&gt;" boost</code> with no <code>-F</code> function, and a
<code>-W</code> wordlist is position-independent by definition &mdash; bash offers the same list at
argument 1 and argument 5, so after <code>boost install</code> it re-offers command names. zsh
guards on <code>(( CURRENT == 2 ))</code> and falls through to <code>_files</code>, which is why it
proposes the contents of your working directory where a skill name belongs &mdash; the most
misleading of the three, because it looks like a real answer. fish registers every completion under
<code>__fish_use_subcommand</code>, so it has nothing to say past the first word.

<b>The flag surface is entirely absent.</b> <code>docs/commands.html</code> documents <b>82 distinct
long flags</b>; the completion scripts contain zero. <code>boost search --&lt;TAB&gt;</code>
completes nothing in all three shells.

<b>The tests pass and prove the wrong thing, which is why this survived.</b> Four tests in
<code>TestCompletions</code> assert the emitted text &mdash; that the wordlist equals
<code>COMMANDS</code>, that there are 79 zsh entries, that fish emits 79 lines. Every one is about
what the generator <em>prints</em>; none is about what a shell would <em>propose</em>. A test suite
can be green and thorough about the wrong layer.

<b>Suggested shape: one completer in Python, three thin shims.</b> Add a hidden
<code>boost __complete &lt;words&gt;</code> that takes the current argv and returns candidates, and
reduce each shell script to a delegation (<code>-F</code> for bash, <code>_boost</code> calling it
for zsh, a function for fish). That puts the logic in <code>core/</code> where the mutation gate
reaches it and where it can be unit-tested in Python, instead of triplicating context rules across
three shell dialects that cannot share a test. It also lets candidates be <em>dynamic</em>:
installed skills for <code>uninstall</code>, catalog names for <code>install</code> and
<code>info</code>, tap names for <code>untap</code>, profiles for <code>profile</code>.

<b>Two constraints worth stating before anyone starts.</b> Completion runs on every keystroke-ish
TAB, so the candidate path must not pay catalog-scan cost &mdash; it needs the cached catalog, and a
budget (target &lt;100&nbsp;ms) measured rather than assumed. And <code>__complete</code> must never
fail loudly: a completer that prints a traceback into the user's prompt is worse than one that
returns nothing, so it should exit 0 with empty output on any error.

<b>Shipped as <code>core/complete.py</code> plus a hidden <code>boost __complete</code>, with the
three shell scripts reduced to shims that call it.</b> Verified by driving <b>real bash and real
zsh</b> rather than by asserting on emitted text &mdash; which is precisely the gap that let this
survive: <code>boost install &lt;TAB&gt;</code> now offers the catalogue,
<code>boost uninstall &lt;TAB&gt;</code> offers what is installed, <code>boost untap &lt;TAB&gt;</code>
offers configured taps, and <code>boost search --&lt;TAB&gt;</code> offers that command's own flags
(previously <b>zero</b> in every shell).

<b>A measurement decided the architecture.</b> Completion fires on a keystroke, and
<code>catalog.all_entries()</code> costs <b>423&nbsp;ms</b> for 71,655 entries &mdash; four times
over the &lt;100&nbsp;ms budget this card set, before interpreter start. A flat names cache answers
the same question in <b>1.9&nbsp;ms</b>, a <b>220&times;</b> difference, and a test asserts the
completion path never calls <code>all_entries()</code> at all. Without that number the obvious
implementation would have shipped a TAB that visibly stalls.

<b>Driving a real shell found a bug that no unit test would have.</b> The zsh shim passed
<code>${words[1,$CURRENT]}</code> unquoted, and zsh <em>drops an empty trailing word</em> &mdash; so
<code>boost install &lt;TAB&gt;</code> arrived as two words and completed <em>command names</em>,
reproducing the exact defect this card exists to fix, in the new code. <code>"${(@)...}"</code>
preserves it. Bash never showed this because <code>"${COMP_WORDS[@]:0:…}"</code> already preserves
empty elements. A test now pins the quoting.

<b>The layering got stricter, not looser.</b> <code>completions</code> used to import
<code>COMMANDS</code> out of <code>cli.py</code> &mdash; the single upward edge the import-linter
contract allowlisted. The registry is now passed into <code>core.complete</code> as data, so the
allowlist entry is <b>gone</b> and <code>boost_cli</code> has no exceptions to its
<code>cli&nbsp;&rarr;&nbsp;commands&nbsp;&rarr;&nbsp;core</code> rule at all. <code>__complete</code>
is deliberately <em>not</em> a row in <code>COMMANDS</code>: that list generates
<code>docs/commands.html</code>, <code>--help</code> and the command counts, and plumbing belongs in
none of them &mdash; so the count stays 79.

<b>The old tests were replaced, not extended.</b> Four tests asserted that the bash wordlist equalled
<code>COMMANDS</code> and that zsh emitted 79 entries. All four passed for years while the feature
was broken, because each asked what the generator <em>printed</em> rather than what a shell would
<em>propose</em>. The replacements pin behaviour and the shim contract.

