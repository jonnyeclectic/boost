---
id: err-colour-judged-by-stdout
board: code
section: dx
status: shipped
category: CLI · Bug
complexity: S
impact: Low
wow: 1
note: fixed — c() takes the stream it is painting for, and err, heading and a table's header cells pass theirs, so each line is coloured by where it lands
order: 331
owner: loop/err-colour-stream
pr: 996
title: "out.err() judges colour by stdout while writing to stderr"
---
<b>Every <code>Error:</code> line asks stdout whether to colour a line it writes to stderr.</b>
<code>out.err</code> (<code>boost_cli/core/output.py:267</code> and <code>:271</code>) paints with
<code>c()</code>, which takes no stream and calls <code>use_color()</code>, so the answer is
<code>sys.stdout.isatty()</code>. Every <code>BoostError</code> reaches the user through it
(<code>cli.py:398</code>), as do the unknown-command and unknown-option errors.

<br><br><b>Measured</b> through a real pty (Python <code>pty.fork</code>, <code>BOOST_COLOR</code> /
<code>NO_COLOR</code> / <code>CLICOLOR_FORCE</code> unset), <code>boost bundle install nosuch</code> on
<code>loop/bundle-audit</code> (<code>err()</code> is unchanged from origin/main). With stdout on
the terminal and <code>2&gt;log</code>, the log holds
<code>\x1b[31m\x1b[1mError: \x1b[0mno Boostfile at …/nosuch\n\x1b[2m  hint: create one with `boost bundle dump Boostfile`\x1b[0m\n</code>
&mdash; five escape sequences written into a file. With stdout to a file and stderr on the
terminal (<code>&gt;out</code>), the terminal gets <code>Error: no Boostfile at …/nosuch</code> with
no colour at all.
Each case gets what the other one should. <code>out.warn(stream=…)</code> had the same bug; the
bundle audit fixed it by passing the stream through to <code>role()</code>, and left
<code>err</code> out of scope. A grep for <code>c(</code> on a <code>file=sys.stderr</code> line
in <code>boost_cli</code> finds only these two.

<br><br><b>Fix:</b> give <code>c()</code> a <code>stream=</code> keyword forwarded to
<code>use_color</code>, and pass <code>sys.stderr</code> from both calls in <code>err</code>. Test it
the way <code>tests/unit/test_output.py::TestWarnColourFollowsItsStream</code> tests
<code>warn</code>: with stdout a TTY and stderr a plain buffer, no <code>\x1b[</code> in stderr;
with the two swapped, the <code>Error:</code> prefix is coloured.

<br><br><b>Shipped.</b> <code>c()</code> now takes a keyword-only
<code>stream=</code> forwarded to <code>use_color</code> — the rule
<code>role()</code> already followed — and the emitters that write off stdout
pass theirs. Fixing only the two <code>err</code> calls this card names would
have left the bug in two more places, both found by grepping every
<code>c(</code> against the <code>file=</code> it is printed to:
<code>heading(msg, stream=…)</code> painted <em>both</em> halves by stdout
(<code>role</code> was called with no stream, and the bold message through
<code>c</code>) although the parameter exists so a report header can follow
its content off stdout; and <code>table()</code> asked
<code>use_color(stream)</code> for the dim <code>│</code> separator while its
bold header cells asked stdout, so one row could carry both answers — plain
separators framing escape-coded headers written into a file, or coloured
separators framing plain headers on a terminal. Five call sites in all, and
reverting any one of them fails a test: the new classes assert both
directions (terminal stream while stdout is a file, and the reverse) the way
<code>TestWarnColourFollowsItsStream</code> does for <code>warn</code>.
