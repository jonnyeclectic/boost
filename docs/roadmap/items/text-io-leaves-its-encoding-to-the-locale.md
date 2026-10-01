---
id: text-io-leaves-its-encoding-to-the-locale
board: code
section: compat
status: inflight
category: Portability · Windows
complexity: M
impact: Med
wow: 2
note: 73 reads and writes take the locale's encoding; 910 writes take its line ending
order: 362
owner: loop/text-io-encoding
pr:
title: "73 reads and writes leave the text encoding to the locale, and the Windows jobs are the only thing that notices"
---
<code>Path.read_text()</code>, <code>Path.write_text()</code> and <code>open()</code> in text mode use
<code>locale.getencoding()</code> when no <code>encoding=</code> is given. On Linux and macOS that is UTF-8
and nothing ever goes wrong. On a GitHub <b>Windows</b> runner it is <b>cp1252</b>, so the same file
written by one call and read by another comes back as different text the moment it holds a
character outside Latin-1.

An AST sweep of <code>boost_cli</code>, <code>scripts</code>, <code>tests</code> and <code>evals</code> finds
<b>73</b> such sites &mdash; 72 in the test suite, 1 in <code>boost_cli</code>
(<code>core/journal.py:55</code>, <code>with p.open("a")</code>) and none in <code>scripts</code>. The
test-suite concentration is not the harmless part: a test that writes UTF-8 and reads it back in
cp1252 is exactly the shape that reddened three Windows jobs below.

<b>That figure was 116 in the first draft of this card, and the 43 it lost are the point.</b> An
inflated backlog is not a safe error &mdash; it sizes a sweep nobody can finish and plants a
false-positive the guard will fail on. Thirty of the 43 were <code>tarfile.open(path, "w:gz")</code>,
three <code>os.open</code> (a file descriptor, which has no encoding), two
<code>webbrowser.open(url)</code>, one a urllib response, and seven were binary
<code>Path.open("rb")</code> miscounted because the walker read the mode from the builtin's argument
position rather than <code>Path.open</code>'s. The single most misleading line was the one claiming
17 <code>boost_cli</code> sites "would mis-read a user's own file": sixteen of those seventeen were
not text IO at all.

<b>This is not theoretical, and it already cost a build.</b> #1012 added a <code>drift</code> report
written with <code>encoding="utf-8"</code> containing an em dash, and a test that read it back with a bare
<code>read_text()</code>. Every Linux and macOS job passed; all three
<code>tests (windows-latest, 3.12 / 3.13 / 3.14)</code> jobs failed, on a change that had touched nothing
platform-specific. The failure names neither the encoding nor the character &mdash; it prints two
truncated strings that look identical.

<b>The quieter half is worse than the loud one.</b> A missing encoding on a <em>reader</em> raises
<code>UnicodeDecodeError</code>, which is a subclass of <code>ValueError</code> &mdash; so any
<code>except (OSError, ValueError)</code> around a JSON load swallows it and reports a perfectly good
file as unreadable. <code>mutation_shards._unusable</code> had exactly that shape: on Windows it would
have refused a valid measurement and said "not readable JSON".

<b>Why ruff's <code>PLW1514</code> is not the whole answer.</b> Two reasons, both measured. It is a
<b>preview</b> rule, so <code>ruff check --select PLW1514</code> without <code>--preview</code> checks
nothing at all and prints "All checks passed" &mdash; indistinguishable from a clean tree, and a trap
this card fell into once already. And with <code>--preview</code> it resolves the receiver
syntactically: over <code>origin/main</code> it reports exactly <b>one</b> site,
<code>scripts/mutation_shards.py:718</code>, because it sees <code>path.read_text()</code> where
<code>path = Path(...)</code> is in view; it never saw the <code>md.read_text()</code> off a pytest
<code>tmp_path</code> fixture that actually broke CI. #1012 fixed that one site, so on <code>main</code>
after this merge the rule reports <b>zero</b> while the walker still reports 73 &mdash; which is the
clearest statement of the gap there is. The sweep wants the AST walker in
<code>tests/unit/test_mutation_shards_names_its_encoding.py</code>, whose <code>WATCHED</code> tuple is the
list to grow &mdash; it already pins the two files #1012 owns, so the guard generalises by adding a path
rather than by being rewritten.

<b>Shape of the work.</b> Mechanical but not blind: each site needs a decision between
<code>encoding="utf-8"</code> and <code>read_bytes()</code>/binary mode, and a handful read files boost did
not write (a user's <code>CLAUDE.md</code>, a tapped repo's Markdown) where <code>errors="replace"</code> may
be the honest answer rather than a crash. Land it per-directory so each PR stays reviewable, extending
<code>WATCHED</code> as it goes.

<b>The encoding is only half of what text mode decides.</b> It also translates <code>\n</code> to the
platform separator on write, so a file written with <code>encoding="utf-8"</code> on a Windows runner
still holds CRLF. #1012 hit both, one after the other: naming the encoding turned the three Windows
jobs green on that assertion and straight back to red on the line endings. A sweep that fixes only
the encoding leaves every writer whose output is compared against a string, a hash or another file
still platform-dependent, so this card covers <code>newline="\n"</code> on writers as well &mdash;
readers need nothing, since universal newlines already fold CRLF on the way in.

That second sweep is <b>910</b> writes (857 tests, 32 <code>boost_cli</code>, 21 <code>scripts</code>),
and unlike the encoding it should <em>not</em> be applied everywhere: a write whose bytes nobody
compares is fine as it is. The ones that matter are writers whose output is read back and compared
&mdash; against a string, a hash, a golden file, or the same report printed to a log. Scoping that
subset is the first task of this card, not a mechanical pass.
