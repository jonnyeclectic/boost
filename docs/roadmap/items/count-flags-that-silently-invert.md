---
id: count-flags-that-silently-invert
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: Med
wow: 4
note: `serve --port 99999` reached socket.bind and exited 70 with a crash report
order: 317
owner: fix/land-claims-fixes
pr:
title: A scan that stops the bare-int count flag coming back
---
Six count flags accepting <code>0</code> and negatives were fixed one at a time, over two
separate passes. Fixing them individually left nothing behind to stop the seventh, and two more
had already appeared by the time this landed.

<code>serve --port</code> is the shape <code>util.positive_int</code> does not cover: a port
needs a <i>ceiling</i> as well as a floor. Without one an out-of-range number travelled all the
way to <code>socket.bind</code>, which raises <code>OverflowError</code> — not an
<code>OSError</code> boost frames — so a <b>typo</b> exited 70 and wrote a crash report
inviting the reader to file a GitHub issue. New <code>util.port_number</code> bounds it to
1-65535 at parse time, where the error is still about the thing the user typed.

<code>tap --jobs</code> was found by the scan rather than by anyone hitting it. It is fed
straight to a <code>ThreadPoolExecutor</code>, so <code>--jobs 0</code> is a
<code>ValueError</code> out of the pool's constructor and a negative is the same — a crash
where "must be &gt;= 1" was wanted.

<b>The durable half is the scan.</b> An AST pass walks every <code>add_argument</code> in the
command layer and fails on any new bare <code>type=int</code>. One genuinely unbounded option
(<code>--percent</code>, where 0 means "nobody") is exempt <i>with a recorded reason</i>, and a
second test deletes an exemption once its flag is bounded — which is how this pass found that
<code>--min</code> and <code>--timeout</code> had since moved to <code>score_int</code> and
<code>positive_int</code>. The list cannot rot into a blanket suppression.
