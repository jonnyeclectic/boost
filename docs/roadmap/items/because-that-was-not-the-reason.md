---
id: because-that-was-not-the-reason
board: code
section: health
status: shipped
category: Bug
complexity: M
impact: Med
wow: 5
note: A `.github/workflows/` directory made `boost recommend` suggest a pasta-recipe skill "because: ci"
order: 316
owner: fix/land-claims-fixes
pr:
title: Three commands that denied what was on the disk in front of them
---
Each of these is boost contradicting something the user can see, and each was confirmed by an
independent verifier that tried to refute it first.

<b><code>boost recommend</code> printed a reason that was not one.</b> Every row carries a
<code>because: &lt;keyword&gt;</code> column — a causal claim about why this skill suits this
project. It was scored on substrings, and the stack vocabulary is short words that live inside
longer unrelated ones, so a project whose only signal was a <code>.github/workflows/</code>
directory was told to install a pasta-recipe skill <i>because: ci</i> — matching the letters
inside "recipes". The reported case was the mildest one. <code>rust</code> matched "trust", of
which boost ships an entire command; <code>java</code> matched "javascript", so a JavaScript
project was recommended Java skills; <code>go</code> matched "algorithms", "django" and "goals".
False attribution was the common case, not the edge.

The fix stays out of <code>catalog.search</code>, which is deliberately substring-based (a user
typing <i>docker</i> wants <i>dockerfile</i> back) and is a scored engine in the eval baseline.
Word matching is applied where the causal claim is actually made. A one-way suffix alias keeps
<code>next</code> reaching <code>nextjs</code> and <code>go</code> reaching <code>golang</code>,
while giving <code>java</code> no route back to <code>javascript</code>.

<b><code>boost bmad personas</code> called seven installed personas "not installed".</b> It
defaulted to the global scope, so after a project install it read the wrong directory and
denied files that were sitting on disk — contradicting <code>boost bmad status</code> run a
moment later in the same directory. Its own <code>--help</code> says the default should be
project. Flipping it would only have moved the false statement to the global install, which is
the more common one, so the command now reports <b>both</b> scopes when none is named — exactly
what <code>bmad status</code> has always done, and a shape that cannot be wrong about either.

<b><code>boost context</code> denied it was in a git repository while standing in one.</b>
<code>git rev-parse</code> resolves HEAD to a <i>commit</i>, so it fails on a repo between
<code>git init</code> and its first commit with the same exit code it gives outside a repo. The
two states were indistinguishable, so <code>context status</code> reported "(not in a git
repository)" and <code>context apply</code> declined to act — in a directory the user had just
initialised. <code>git symbolic-ref</code> reads the ref HEAD points at without requiring it to
exist yet, and still fails outside a repo, so the genuinely-not-a-repo answer is unchanged.

Two further candidates in the same batch were <b>refuted</b> and left alone:
<code>boost home</code>'s slot-level URL and <code>tap --dry-run</code>'s scope are both
imprecise rather than false, and neither <code>--help</code> nor the command table promises what
the finder assumed.
