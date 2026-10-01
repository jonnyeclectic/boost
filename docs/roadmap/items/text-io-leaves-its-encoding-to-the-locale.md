---
id: text-io-leaves-its-encoding-to-the-locale
board: code
section: compat
status: shipped
category: Portability · Windows
complexity: M
impact: Med
wow: 2
note: all 73 encoded; the guard is repo-wide over 414 files; the newline half is its own card
order: 362
owner: loop/text-io-encoding
pr: 1015
title: "73 reads and writes left the text encoding to the locale, and the Windows jobs were the only thing that noticed"
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
<em>syntactically</em>, which over this repo means it sees almost nothing: run against the
pre-sweep tree it reports <b>0</b> sites to the walker's <b>73</b>. It flags
<code>p.read_text()</code> only where <code>p = Path(...)</code> is in view, and all 73 are a
<code>tmp_path / "x"</code> fixture, a chained call or a parameter &mdash; including the
<code>md.read_text()</code> that actually broke CI. 0 against 73 is the clearest statement of the gap
there is, and the reason the rule was not simply switched on. Turning it on also means turning
<code>preview</code> on in <code>pyproject.toml</code>, which changes how every other selected rule
behaves; one rule, for 0 of the 73, is not that trade.

<b>What shipped.</b> All 73 sites name <code>encoding="utf-8"</code>, and the guard
&mdash; renamed <code>tests/unit/test_text_io_names_its_encoding.py</code>, since it is no longer about
the shard planner &mdash; walks every root holding Python rather than a <code>WATCHED</code> list of two:
<code>boost_cli</code>, <code>boost_langchain</code>, <code>evals</code>, <code>scripts</code>,
<code>tests</code> and <code>noxfile.py</code>, <b>414</b> files. Its <code>EXEMPT</code> set is empty and
documented to stay empty: a call that should not be flagged is a bug in <code>_is_file_open</code> or
<code>_mode</code>, where fixing it covers every file, not an entry that mutes one. The
<code>./boost</code> launcher is the one deliberate omission &mdash; it is a bash shim that
<code>ast.parse</code> cannot read and that opens no files.

<b>The single <code>boost_cli</code> site was the interesting one.</b>
<code>journal.log</code> appended to the pulse feed with <code>p.open("a")</code> while
<code>journal.events</code> read it back with <code>encoding="utf-8"</code>. That asymmetry is latent
rather than live: <code>json.dumps</code> defaults to <code>ensure_ascii=True</code>, so every byte
written today is ASCII and cp1252 agrees with UTF-8 about all of them. What makes it worth fixing is
the reader's <code>errors="replace"</code>, which would turn the first byte they ever disagreed about
into U+FFFD without raising &mdash; a feed that silently loses a character rather than failing. A
round-trip test cannot show any of this on Linux, so the test watches the argument reaching
<code>Path.open</code> instead of the bytes on disk; dropping the keyword and misspelling the codec
both fail it.

<b>The encoding is only half of what text mode decides.</b> It also translates <code>\n</code> to the
platform separator on write, so a file written with <code>encoding="utf-8"</code> on a Windows runner
still holds CRLF. #1012 hit both, one after the other: naming the encoding turned the three Windows
jobs green on that assertion and straight back to red on the line endings. A sweep that fixes only
the encoding leaves every writer whose output is compared against a string, a hash or another file
still platform-dependent, so this card covers <code>newline="\n"</code> on writers as well &mdash;
readers need nothing, since universal newlines already fold CRLF on the way in.

That second sweep is <b>917</b> writes on the tree this change ships (858 <code>tests</code>, 32
<code>boost_cli</code>, 21 <code>scripts</code>, 6 <code>evals</code>; 916 on <code>origin/main</code>,
and the 910 this card first quoted was the same count taken before <code>evals</code> was in the walk)
and is <b>deliberately not in this change</b>, because unlike the encoding it
must <em>not</em> be applied everywhere: a write whose bytes nobody compares is fine as it is, so a
blanket pass would be 917 edits of which most are churn and none is a fix. Scoping the subset that
is read back and compared is work of its own, and it has its own card &mdash;
<code>writers-whose-bytes-are-compared-do-not-pin-their-newline</code>. The newline walker
(<code>unpinned_newline</code>) ships here beside the encoding one, still scoped to
<code>scripts/mutation_shards.py</code>, which is the one file whose writers are already known to be
byte-compared.
