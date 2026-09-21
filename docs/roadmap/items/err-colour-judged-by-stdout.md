---
id: err-colour-judged-by-stdout
board: code
section: dx
status: planned
category: CLI · Bug
complexity: S
impact: Low
wow: 1
note: boost … 2&gt;log on a terminal writes escape codes into the log, while boost … &gt;out prints the error line plain
order: 331
owner:
pr:
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
