---
id: concurrency-probe-measured-a-race-not-the-pool
board: code
section: trust
status: inflight
category: Tests · Flake
complexity: S
impact: Med
wow: 2
note: assert 1 &gt; 1 on macOS/3.14 against a thread pool that was working correctly
order: 357
owner: loop/flaky-concurrency-probe
pr:
title: "The <code>add_many</code> concurrency probe measured a race, not the pool"
---
<code>test_it_actually_runs_concurrently</code> counted the peak number of fake clones in flight and
asserted it exceeded one. The fake clone is one <code>mkdir</code> and a small write, so the window
in which two of them overlap is microseconds wide &middot; on a loaded runner each worker finished
before the next was scheduled, the peak stayed at 1, and the required <code>tests (macos-latest,
3.14)</code> check failed with <code>assert 1 &gt; 1</code> against a <code>ThreadPoolExecutor</code>
that was doing exactly its job. Observed on PR #998, where it blocked a merge for a defect that did
not exist.

<b>The failure said the wrong thing, which is the part that matters.</b> "This is serial" and "this
was too fast to catch overlapping" are different diagnoses, and the second wastes whoever reads it.
A required check that can fail for a reason unrelated to the change also trains the next person to
re-run rather than read &middot; which is how a real regression gets waved through.

A <code>threading.Barrier(jobs)</code> inverts the dependency. Every worker blocks until
<code>jobs</code> of them have arrived, so the assertion stops being about timing: a pool of four
trips the barrier and the call returns, and a pool narrower than four <em>cannot</em> &mdash; the
first worker waits for peers that will never come and the barrier times out. Slower hardware makes
the test <em>more</em> reliable rather than less, which is the opposite of the property it had.
Paired with <code>test_the_concurrency_probe_fails_when_the_pool_is_serial</code>, which drives
<code>add_many</code> at <code>jobs=1</code> so the probe's own ability to fail is itself asserted,
and verified by hand against a <code>max_workers=1</code> executor: it fails with "the pool never
had 4 clones in flight".
