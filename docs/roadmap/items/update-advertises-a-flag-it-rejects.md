---
id: update-advertises-a-flag-it-rejects
board: code
section: internals
status: shipped
category: Bug
complexity: XS
impact: Med
wow: 3
note: the only escape from the security gate was a flag the parser refused
order: 94
owner: loop/update-yes-flag
title: <code>boost update</code> told you to run a flag it then rejected
---
Decline the risky-update confirmation and <code>boost update</code> printed the way out:
<i>"update skipped — review the diff, then <code>boost update --yes</code> to apply"</i>. Doing
exactly that produced <code>Error: unrecognized arguments: --yes</code>.

<b>Why it mattered more than a typo.</b> That gate is a <i>security</i> feature: it fires when an
incoming update adds executable-looking instructions — shell commands, pipe-to-shell, a shebang — so
a poisoned update is seen before it lands. Declining is therefore the careful user's path, and the
message is the only thing telling them how to proceed afterwards. The instruction was a dead end,
so the sole documented escape from the gate did not exist, and the remaining options were to
re-run and answer the prompt interactively or to reach for <code>BOOST_ASSUME_YES</code> — which is
strictly worse, since it approves <i>every</i> prompt rather than this one.

<b>The fix is one <code>add_argument</code>, and deliberately nothing else.</b>
<code>out.confirm()</code> already honours <code>--yes</code>/<code>-y</code> by reading
<code>sys.argv</code> directly, so the behaviour was wired the whole time — every other command that
prompts (<code>install</code>, <code>uninstall</code>, <code>tap</code>, <code>bmad</code>) declares
the flag, and <code>update</code> was the one that forgot. Declaring it makes the printed advice
true rather than adding a new code path. <code>docs/commands.html</code> is generated from the
parsers, so the flag documents itself.

<b>Found by taking the advice literally</b> — running the exact string the CLI prints — rather than
by reading the parser. The regression test does the same thing: it declines the gate, asserts the
message, then runs the command that message names and asserts the upgrade lands. It was confirmed
to fail without the fix, with the original <code>unrecognized arguments</code> error.

Two traps that shaped the test. It drives the <i>real</i> <code>out.confirm()</code> instead of
patching it, because the suite sets <code>BOOST_ASSUME_YES=1</code> — leaving that set would
auto-approve and the test would pass whether or not <code>--yes</code> did anything. And it must
never call <code>monkeypatch.undo()</code> to shed that env var: the <code>sandbox</code> fixture's
<code>HOME</code> lives on the same monkeypatch, so undoing drops the test out of its sandbox and
onto the developer's real <code>~/.boost</code>. The first draft did exactly that and spent four
minutes pulling real tap clones over the network before failing.
