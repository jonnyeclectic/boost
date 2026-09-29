---
id: wrap-width-judged-by-stdout
board: code
section: planned
status: inflight
category: CLI · Bug
complexity: S
impact: Low
wow: 1
note: a wrapped stderr line is folded to stdout's width — the colour-stream fix's twin, one layer down
order: 354
owner: loop/wrap-width-stream
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
