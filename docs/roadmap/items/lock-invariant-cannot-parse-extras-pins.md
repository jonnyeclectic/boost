---
id: lock-invariant-cannot-parse-extras-pins
board: code
section: health
status: shipped
category: Latent bug
complexity: S
impact: Med
wow: 2
note: <code>pkg[extra]==x</code> reads as unpinned
order: 16
owner: loop/lock-invariant-extras
pr: 306
title: The lock invariant can't parse <code>name[extra]==version</code>, so a valid pin fails the gate
---
<code>tests/unit/test_toolchain_lock.py</code> (added with the lock-stability fix, #248)
asserts every requirement is pinned with <code>==</code>. Its regex is
<code>(?P&lt;name&gt;[A-Za-z0-9][A-Za-z0-9._-]*)(?P&lt;spec&gt;==[^\s;\\]+)?</code> — and the
name class has <b>no <code>[</code> or <code>]</code></b>. So against
<code>coverage[toml]==7.15.2</code> the name matches <code>coverage</code>, the spec then
fails to match because the next character is <code>[</code>, and <code>spec</code> comes
back <code>None</code>. The test reports <i>"coverage is not pinned with == in
test-tools"</i> about a line that is pinned exactly.
Latent today — nothing in <code>requirements/*.txt</code> currently carries an extra — but
<code>uv</code>/pip-tools emit <code>name[extra]==version</code> routinely, so the first
legitimate extras-bearing pin will block the gate with a message that points at the wrong
thing. Fix by allowing an optional extras group in the name, e.g.
<code>[A-Za-z0-9._-]*(?:\[[^\]]+\])?</code>, and add both forms to the test's own cases.
Found the honest way: Dependabot #253 (hypothesis) regenerated the lock and tripped this
assertion. That PR is genuinely bad for an <b>unrelated</b> reason — it collapses
<code>coverage==7.10.7 ; python&lt;'3.10'</code> and
<code>coverage==7.15.2 ; python&gt;='3.10'</code> into a single
<code>coverage[toml]==7.15.2</code>, and 7.15.2 requires Python &ge;3.10, so it silently
drops the 3.9 leg this project promises. The gate <b>correctly refused</b> it. But it
refused for the wrong reason, and that is the part worth fixing: the same message will one
day reject a lock that is perfectly fine. See
<a href="#pytest-tmpdir-cve-blocked-by-py39-floor">the pytest card</a> — collapsing a
marker-split pin is the recurring shape here, and is worth its own assertion.
