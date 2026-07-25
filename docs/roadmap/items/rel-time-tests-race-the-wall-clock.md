---
id: rel-time-tests-race-the-wall-clock
board: code
section: health
status: planned
category: Flaky test
complexity: S
impact: Med
wow: 2
note: caught red on CI, 3.14
order: 37
owner:
pr:
title: <code>rel_time</code> tests race the wall clock and flake on a loaded runner
---
<code>TestRelTime</code> builds its input with
<code>iso_ago(n) = (now() - n).strftime("%Y-%m-%dT%H:%M:%SZ")</code>, which
<b>truncates sub-second precision</b>, then asserts on
<code>util.rel_time()</code> calling <code>now()</code> a second time. The elapsed
delta is therefore <code>n + frac(first_now) + runtime</code>, and
<code>rel_time</code> floors it — so whenever
<code>frac(first_now) + runtime &ge; 1.0</code> the bucket is one higher than the
test expects. Observed failing on <code>tests (ubuntu-latest, 3.14)</code>:
<code>assert '31s ago' == '30s ago'</code>.
The off-by-one cases are the mild ones. <code>iso_ago(59)</code> and
<code>iso_ago(59 * 60)</code> sit <b>directly on a bucket boundary</b>, so the same
race flips <code>"59s ago"</code> to <code>"1m ago"</code> and
<code>"59m ago"</code> to <code>"1h ago"</code> — a different unit, not a
neighbouring number. Every assertion in the class shares the window; it is
narrow on a quiet machine and widens with runner load, which is why it reads as
random redness rather than a broken test.
Fix by giving the test a fixed clock — monkeypatch
<code>util.datetime</code> (or inject a <code>now</code> seam into
<code>rel_time</code>) so both reads come from one frozen instant, and the
boundary cases become exact rather than probabilistic. Freezing is preferable to
widening the assertions: the boundaries are precisely the behaviour worth pinning.
