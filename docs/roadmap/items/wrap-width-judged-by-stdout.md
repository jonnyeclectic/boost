---
id: wrap-width-judged-by-stdout
board: code
section: planned
status: inflight
category: CLI · Bug
complexity: S
impact: Low
wow: 1
note: three call sites size a stderr line by stdout — and pane_width, the card's own model, has it too
order: 354
owner: loop/wrap-width-stream
pr: 1000
title: "wrap() sizes a stderr line by stdout's pane"
---
<b>A line now gets its colour from the stream it lands on and its
<em>width</em> from somewhere else.</b> <code>_wrap_lines</code>
(<code>boost_cli/core/output.py:235</code>) folds to
<code>term_width() - lead</code>, and <code>term_width</code>
(<code>:402</code>) takes no stream: it calls
<code>shutil.get_terminal_size</code>, which consults
<code>sys.__stdout__</code>. Right beside it, <code>pane_width(stream)</code>
(<code>:407</code>) does take one, and exists because the same question has a
different answer per stream.

<br><br>So the emitters that write off stdout and wrap — <code>err(wrap=True)</code>
(<code>:318</code>, <code>:327</code>) and <code>warn(stream=sys.stderr,
wrap=True)</code> (<code>:284</code>, reached from <code>catalog.py:346</code>,
<code>journal.py:65</code>, <code>lockfile.py:185</code>,
<code>registry.py:594</code> and <code>complete.py:105</code>) — size a stderr
line by stdout's pane. In a 200-column terminal:
<code>boost install x &gt;out</code> folds the hint on the terminal at 72
columns, because stdout is a file, <code>get_terminal_size</code> raises and
the 80-column fallback applies; <code>boost install x 2&gt;log</code> writes
192-column lines into the log.

<br><br>This is the twin of <code>err-colour-judged-by-stdout</code>, found while
verifying it, and deliberately left out of that PR: it is a width bug, not a
colour one, and it predates the change. <b>Fix sketch:</b> give
<code>term_width</code> (or <code>_wrap_lines</code>) the stream the emitter
is about to write to, the way <code>c()</code>, <code>role()</code> and
<code>aurora()</code> now take one, and have each wrapping emitter pass its
own. Watch the <code>COLUMNS</code> precedence: <code>pane_width</code>
honours an explicit <code>COLUMNS</code> either way, and the wrap path must
keep doing the same or a scripted <code>COLUMNS=100</code> stops applying to
hints. A test wraps one long hint with stdout a TTY and stderr a plain
buffer, and asserts the fold point comes from stderr.

<br><br><b>Measured before claiming, and the fix sketch above is wrong.</b>
<code>pane_width(stream)</code> is not the per-stream model to copy: it uses
its stream only for the <code>isatty()</code> predicate and then takes the
<em>number</em> from <code>term_width()</code> (<code>output.py:422</code>),
so it measured 80 for a 200-column stderr terminal while stdout was a file.
Routing <code>_wrap_lines</code> through it would have left that intact. A
third instance the card missed: <code>spin.progress_clear</code>
(<code>spin.py:98</code>) erases <code>term_width()</code> columns of a line
it just proved is on <code>s</code> &middot; 80 of a 200-column bar.

<br><br>Two numbers here were budgets rather than widths. <code>192</code> is
<code>term_width() - len("  hint: ")</code>; the lead is printed too, so the
lines run to the full pane &mdash; measured 196 for a hint and 199 for a warn
on a 200-column pty. And the proposed test cannot fail: a fake tty (a
<code>StringIO</code> whose <code>isatty()</code> returns True) has no file
descriptor, so broken and fixed both answer 80 &mdash; measured identical fold
points either way. It needs a real <code>os.openpty()</code> with
<code>TIOCSWINSZ</code>.
