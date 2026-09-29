---
id: err-colour-judged-by-stdout
board: code
section: dx
status: shipped
category: CLI · Bug
complexity: S
impact: Low
wow: 1
note: fixed — every painter takes the stream it is painting for, and all nine call sites that write off stdout pass theirs, so each line is coloured by where it lands
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

<br><br><b>And the sweep this card describes cannot find all of them.</b> It
greps one painter (<code>c(</code>) against one write idiom
(<code>file=</code>), so it is blind to <code>stream.write(out.c(…))</code>,
<code>out.info(out.role(…), stream=…)</code> and
<code>stream.write(out.aurora(…))</code> alike. The grep that finds them is
over every painter — <code>c(</code>, <code>role(</code>,
<code>aurora(</code> — against every write target — <code>file=</code>,
<code>.write(</code>, <code>stream=</code> — and it finds four more:
<code>cliparse.py:60</code> writes a <code>DIM</code>-painted usage block to
<code>sys.stderr</code> and asked stdout, which is on the most common error
path of all (every argparse rejection in every subcommand) and which fixing
<code>err</code> alone made <em>internally inconsistent</em> — a red
<code>Error:</code> above an unpainted usage;
<code>commands/discovery.py:947</code> paints a hint with a bare
<code>role()</code> and prints it to stderr right under a <code>warn</code>
that already followed the stream, so the two lines of one notice disagreed;
and <code>spin.py:47</code> and <code>:77</code> paint with
<code>aurora()</code> and write to <code>self.stream</code>. The spinner pair
can never <em>leak</em> — <code>active()</code> prints nothing at all to a
non-TTY — but it drops the colour the other way round:
<code>boost search --smart q &gt; results.txt</code> animates on the terminal
stderr while <code>color_level(sys.stdout)</code> is 0, so the braille frame
draws plain. Nine call sites in all.

<br><br><b>Out of scope, same shape:</b> <code>_wrap_lines</code>
(<code>output.py:235</code>) calls <code>term_width()</code>, which takes no
stream and consults <code>sys.__stdout__</code>, while
<code>pane_width(stream)</code> right beside it does take one. So
<code>err(wrap=True)</code> and <code>warn(stream=sys.stderr, wrap=True)</code>
now colour a line by where it lands and still <em>size</em> it by somewhere
else: in a 200-column terminal, <code>boost install x &gt;out</code> folds the
hint at 72 columns and <code>2&gt;log</code> writes 192-column lines into the
log. It predates this card and is a width bug rather than a colour one, so it
wants its own item.

<br><br><b>A tenth call site, and it is the standard library's.</b> Python
3.14 taught <code>argparse</code> to paint its own usage and help, defaulting
to <code>ArgumentParser(color=True)</code> and deciding by calling
<code>_colorize.can_colorize()</code> — whose <code>file</code> defaults to
<b>stdout</b>, for text <code>BoostArgumentParser.error()</code> writes to
stderr. Exactly this card's bug, arriving from under the floor on a version
bump. It is worse than a leak here because the two paints nest: boost wraps
the usage in one <code>out.c(..., DIM)</code> span, and argparse's own reset
after <code>usage: </code> ends the dim two words in. So
<code>__init__</code> now defaults <code>color=False</code> on 3.14+, next to
the <code>formatter_class</code> default but <i>not</i> for the same reason:
argparse forwards this one down explicitly, filling <code>add_parser</code>'s
kwargs from the parent (3.14's <code>argparse.py:1252</code>) and stamping
<code>action._color</code> at <code>:1979</code>, so a sub-parser inherits
<code>False</code> rather than re-defaulting it. It sits in
<code>__init__</code> because <code>add_parser</code> builds through
<code>type(self)</code>, which is the one door every parser comes through.
Boost paints this text itself, against the stream it is written to; argparse
must not paint it first. It surfaced as a red mutation gate: on
3.14 the assertion that a redirected stderr carries no escape at all read
<code>'Error: the ...ame\x1b[0m\n'</code> — argparse's green
<code>name</code> at the end of the usage it had just coloured by the wrong
stream.
