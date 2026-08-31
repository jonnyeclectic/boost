---
id: delay-true-defeats-the-log-suppress
board: code
section: planned
status: inflight
owner: loop/log-suppress-delay-true
category: Health · Robustness
complexity: S
impact: Medium
wow: 2
note: the suppress guards construction; delay=True moves the failure to emit
order: 130
title: A best-effort log handler prints a traceback over every command's output
---
<code>logs.configure</code> says what it means to do &mdash; <em>&ldquo;File handler &mdash; always
DEBUG, best-effort (never break the CLI over a log)&rdquo;</em> &mdash; and wraps the handler in
<code>contextlib.suppress(OSError)</code> to guarantee it. The guarantee does not hold, and the
reason is one keyword inside the block: <code>with contextlib.suppress(OSError):</code> &middot;
<code>paths.logs_dir().mkdir(parents=True, exist_ok=True)</code> &middot;
<code>fh = logging.handlers.RotatingFileHandler(log_path(), maxBytes=MAX_BYTES,
backupCount=BACKUP_COUNT, encoding="utf-8", <b>delay=True</b>)</code>.

<code>delay=True</code> means the file is <b>not opened during construction</b>. It is opened on the
first <code>emit()</code>, inside <code>shouldRollover</code> &mdash; which happens later, on a
different stack, outside the <code>suppress</code>. So the <code>OSError</code> the block exists to
swallow is relocated to exactly where nothing is catching it. <code>logging.raiseExceptions</code>
is left at its default <code>True</code>, so Python's logging module prints
<code>--- Logging error ---</code> and a full traceback to stderr instead.

<b>Observed on a real machine</b>, with the log at <code>rw-r--r--</code> owned by the invoking user
and the directory writable, under a harness whose filesystem policy did not include
<code>~/.boost/logs</code>. Every <code>boost</code> command emitted <b>two</b> tracebacks &mdash;
one from <code>log_invocation</code> at <code>cli.py:311</code> and one from
<code>log_completion</code> at <code>cli.py:343</code> &mdash; roughly thirty lines of Python
internals wrapped around the fifteen lines of search results the user actually asked for. The
command itself returned <code>rc=0</code>. Nothing was broken except the output.

<b>Two things to get right.</b> First, catching the error is not the same as reporting it: a handler
that silently swallows every write means a user whose diagnostics have been dead for months learns
nothing, which is the failure <code>doctor</code>'s log check already exists to prevent. The right
shape is to fail <em>quietly per emit</em> and let <code>doctor</code> stay the surface that says
so &mdash; it already reports <code>&ldquo;diagnostic log &hellip; is not writable &mdash; every
invocation is failing to record&rdquo;</code>, which was accurate the whole time this was spewing
tracebacks. Second, <code>logging.raiseExceptions</code> is a <b>module-global</b>: boost sets it
for every library in the process, so flipping it wholesale is louder than it looks. Overriding
<code>handleError</code> on boost's own handler is the scoped version of the same fix.

<b>Worth checking while here</b>: whether <code>doctor</code>'s writability check and the handler
agree about what &ldquo;writable&rdquo; means. The check passed (<code>&#10003; diagnostic log at
~/.boost/logs/boost.log</code>) in the same session where the handler was failing on every emit,
because the two ask different questions &mdash; one about the path's mode bits, the other about
what an <code>open()</code> actually returns. A health check that reports green while the thing it
checks fails on every invocation is the more expensive half of this card.
