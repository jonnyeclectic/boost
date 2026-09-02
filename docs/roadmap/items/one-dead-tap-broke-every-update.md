---
id: one-dead-tap-broke-every-update
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: High
wow: 4
note: found on the maintainer's own machine — 80+ taps, one deleted upstream, no updates for any of them
order: 95
owner: loop/update-survives-a-dead-tap
title: one deleted upstream stopped <code>boost update</code> for every other tap
---
<code>registry.update()</code> looped over the configured taps with <b>no error handling at all</b>.
The first tap whose upstream had been deleted, renamed or made private raised, and everything after
it never ran: later taps went unrefreshed, the taps that <i>had</i> already pulled never had their
catalogs rebuilt, and the whole command exited non-zero.

<b>Found by accident, on real data.</b> A test escaped its sandbox and ran <code>boost update</code>
against the maintainer's actual <code>~/.boost</code>, which died on
<code>MikroJit-Technologies/claude-skills</code> — a repo that no longer exists. With 80+ taps
configured, an upstream disappearing is routine rather than an edge case, and one of them was
silently costing every other tap its updates.

<b>The error was unactionable twice over.</b> It named no tap, and it was not even a sentence:
<i>"git -C failed: and the repository exists."</i> That is the last line of git's output, and git
states the cause <i>first</i> and advises after —

<code>fatal: '/nope' does not appear to be a git repository</code> &middot;
<code>fatal: Could not read from remote repository.</code> &middot; <i>(blank)</i> &middot;
<code>Please make sure you have the correct access rights</code> &middot;
<code>and the repository exists.</code>

&mdash; so <code>detail[-1]</code> surfaced the tail of a prose hint and threw away the one line that
names the bad path. <code>gitutil._git_error</code> now prefers the first
<code>fatal:</code>/<code>error:</code> line, git's own convention for the cause, and falls back to
the last non-empty line. That improves <i>every</i> git failure boost reports, not just this one.

<b>The shape of the fix was already in the codebase.</b> The skill-update loop in
<code>cmd_update</code> has caught <code>BoostError</code> per item and carried on with a warning
for a long time; the tap loop was the one place that did not. <code>update()</code> now returns
<code>(results, failures)</code>, and a named tap — <code>boost update sometap</code> — still
raises, because asking about one tap makes its failure the answer to the question asked. Only the
all-taps path is forgiving.

<b>Exit code and wording, both deliberate.</b> A partial run returns <b>0</b>: failing it would put
us back to one dead upstream breaking the command for the other 79. But it must not print a clean
bill of health either, so the closing line becomes <i>"everything up to date, except the taps
above"</i>, and a count plus the fix (<code>boost untap &lt;name&gt;</code>) is printed. Non-zero is
reserved for the case where nothing refreshed at all. Skills belonging to a failed tap are skipped
automatically — the update pass already gates on <code>tapname not in results</code>, so a failed
tap simply never appears there.

<b>Verified by reversion</b>: the git-message test was confirmed to fail with the old
<code>detail[-1]</code> restored, reproducing <i>"git -C failed: and the repository exists."</i>
exactly.

<b>A later audit found a second failure mode for the same deleted-or-private upstream</b>: without
<code>GIT_TERMINAL_PROMPT=0</code>, git fell back to an interactive
<code>"Username for 'https://github.com':"</code> prompt instead of failing at all — on a real
terminal that blocks <code>tap</code>/<code>import</code>/<code>update</code> outright, and in a
sandbox with no tty it died as the unrelated-looking <i>"Device not configured."</i>
<code>gitutil.run</code> now sets the flag, and <code>clone_shallow</code>/<code>pull</code>
translate git's resulting "could not read Username"/"Repository not found"/"Authentication failed"
text into <i>"&lt;spec&gt;: repository not found or private"</i>, so the failures branch above is
actually reached instead of the whole command blocking.
