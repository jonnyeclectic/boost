---
id: completions-install-could-eat-your-rc-file
board: code
section: dx
status: shipped
category: Bug
complexity: S
impact: High
wow: 4
note: two runs of a "no-op" command deleted the lines between two markers
order: 113
owner: fix/completions-malformed-block
pr: 523
title: <code>completions --install</code> could delete the config between its own markers
---
Found by asking a plain question — <em>is <code>boost completions</code>
idempotent?</em> — and testing the answer rather than reading the docstring. For
every ordinary input it is: seven paths reach a fixed point on the second run,
and the managed block is replaced in place rather than appended. Three states
were not ordinary, and each is reachable from one hand-edit of a shell rc file.

<b>A start marker with no end deleted user config.</b> <code>_merge_rc</code>
paired the first start marker with the next end marker found <em>anywhere</em>
after it. With an orphan start above real config, run one appended a second
block, and run two matched the orphan start against that new block's end and
removed everything in between — the user's own lines — while printing
<code>✓ wired boost completions into ~/.zshrc</code>. It converged, to a file
with the user's aliases gone.

<b>The inverse function already refused this exact input</b>, ten lines below:
<code>_strip_rc</code> carried the comment <em>"no end marker: malformed, leave
the file untouched."</em> So the state was recognised and only the writer failed
to handle it. That asymmetry is the whole bug, and it is why this was worth
fixing rather than filing: the reasoning was already in the file.

<b>Uninstall had the same hole from the mirror precondition.</b>
<code>_strip_rc</code> was safe only while the orphan start was the sole marker.
Put a well-formed block below it and uninstall paired the orphan with that
block's end: an rc file of <code>export A=1</code> plus four user lines came
back as <code>export A=1</code> alone.

<b>Two blocks made uninstall lie.</b> It removed the first and left the second,
so boost reported <em>removed</em> while the shell went on sourcing
completions — the same shape as the <code>sync</code> defect in
<code>#515</code>, a command reporting success for work it declined to do.

<b>The fix is one scan with the right invariant:</b> a block must close before
the next one opens. Testing only for a missing end marker is the original bug in
a new place, which the first draft of this fix reproduced and a test caught.
Install now collapses to exactly one block, uninstall removes every block, and
both refuse an unclosed one by name instead of guessing. An orphan
<em>end</em> marker stays harmless and is pinned as such, so a later
"tighten the parser" change cannot start rejecting a file that works.

<b><code>--dry-run</code> makes it answerable before it is written.</b>
<code>boost completions --install --dry-run</code> prints the exact +/- lines
and touches nothing, and it raises on the malformed file too — a validation that
only reports the safe cases is not a validation. Plan and apply are one code
path (<code>plan_install</code> → <code>apply</code>), so the preview cannot
disagree with the write, and a test pins that equality. Applying a no-op change
now also leaves the file's mtime alone rather than rewriting identical bytes.

<b>Verified exhaustively, not just by example.</b> A property test enumerates
every arrangement of up to four fragments — user line, stray start, stray end,
real block — and asserts three invariants over all 672 orderings: a user line
boost does not own is never lost, a successful uninstall never leaves a block,
and a refusal never modifies the file. Against the pre-fix code the same test
reports <b>220 violations</b> (198 of the second, 22 of the first); against the
fix, zero. It runs in 0.38s.

That sweep also corrected its own first draft. Its initial invariant counted
every user line, and flagged 16 "failures" that were the managed block behaving
exactly as conda, nvm and rbenv do — content between the markers is boost's to
replace. The real invariant is about lines boost does <em>not</em> own, and the
reference parser has to resolve the orphan-start ambiguity the way the fix does
rather than the way the bug did, or it under-reports the data loss it exists to
catch.

An rc file is the user's own hand-written config and the worst file boost owns
an edit to, which is what moves this from tidy-up to High impact. The old tests
covered only the well-formed path — a double install leaving one marker — so
none of the three states had a failing test to find them.
