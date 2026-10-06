---
id: writers-whose-bytes-are-compared-do-not-pin-their-newline
board: code
section: compat
status: inflight
category: Portability · Windows
complexity: M
impact: Med
wow: 2
note: 917 text writes take the platform line ending; only the compared ones are bugs
order: 363
owner: loop/pin-compared-newlines
pr:
title: "917 text writes leave the line ending to the platform, and only some of them are bugs"
---
Text mode decides two things, and naming the encoding fixes one of them. It also translates
<code>\n</code> to the platform separator <em>on write</em>, so a file written with
<code>encoding="utf-8"</code> on a GitHub <b>Windows</b> runner still holds CRLF. The sibling card
<code>text-io-leaves-its-encoding-to-the-locale</code> closed the encoding half across 414 files; this
is the other half, and it is deliberately not the same kind of sweep.

<b>#1012 hit both, one after the other, and the first fix hid the second.</b> Naming the encoding
turned the three <code>tests (windows-latest, 3.1x)</code> jobs green on the assertion that had failed
&mdash; and the next run put them straight back to red on the line endings of the same line. Two
platform defects in one call, and no way to see the second until the first was gone.

<b>The count is 917, and a blanket pass would be wrong.</b> 858 in <code>tests</code>, 32 in
<code>boost_cli</code>, 21 in <code>scripts</code>, 6 in <code>evals</code>. Most of those writes
produce files whose line endings nothing ever compares, so pinning
<code>newline="\n"</code> on all of them is 917 edits of which the overwhelming majority are churn
and none is a fix &mdash; and churn in a diff is what makes the real change unreviewable. Readers need
nothing at all: universal newlines already fold CRLF to LF on the way in, which is why the guard that
ships with the encoding card walks <em>writers only</em>.

<b>So the work is the scoping, not the edit.</b> The subset that matters is writers whose output is
read back and compared &mdash; against a string, a hash, a golden file, or the same report printed to a
log beside it. Three shapes are known to qualify and are a good place to start the inventory:
a file written here and read back by an assertion in the same test; anything hashed or diffed
(<code>fingerprint</code>, the generated-file <code>--check</code> gates, golden fixtures); and
anything a <em>second</em> process parses line by line, which is how
<code>$GITHUB_OUTPUT</code> got onto the list. <code>scripts/mutation_shards.py</code> is already
pinned and already guarded by <code>TestTheScriptPinsItsNewlines</code> &mdash; extending that guard a
scoped set at a time, with the reason each set is in it, is the shape this should take.

<b>What would make it falsifiable.</b> A Windows job that asserts byte equality, not string
equality: today a round trip on Linux passes whether the newline is pinned or not, which is exactly
the class of test the encoding card's own verification pass caught twice. The AST walker
(<code>unpinned_newline</code> in <code>tests/unit/test_text_io_names_its_encoding.py</code>) is the
platform-independent half and already exists; what it cannot tell you is which of the 917 are bugs.
