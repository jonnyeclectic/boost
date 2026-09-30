---
id: floors-job-never-installed-setuptools
board: code
section: trust
status: shipped
category: CI · Bug
complexity: S
impact: Med
wow: 2
note: the same missing dependency, in the second of three hand-built venvs
order: 360
pr: 1006
title: "The floors job builds its own venv and never put setuptools in it, so main went red on the weekly cron"
---
<code>suite on declared floors (py3.12)</code> resolves the lower bounds <code>pyproject.toml</code>
advertises with <code>uv --resolution lowest-direct</code> and runs the unit and functional suites
against them. It assembles its venv by hand &mdash; <code>python -m venv</code>, then
<code>pip install -e . pytest pytest-cov coverage hypothesis</code> &mdash; and neither half
supplies setuptools: a 3.12+ <code>venv</code> seeds pip alone, and an editable install resolves
the build backend in an <em>isolated</em> environment that leaves nothing behind in
<code>.venv</code>.

<code>tests/unit/test_sdist_contents.py</code> runs setuptools' own MANIFEST matcher
(<code>setuptools._distutils.filelist</code>) rather than building an sdist over the network, so
the job went red on seventeen <code>ModuleNotFoundError</code>. It landed with that file in
<code>633d3ab3</code>; the last green cron was 2026-09-23 and the red one 2026-09-30.

<b>That is the one colour the job cannot afford.</b> Its whole purpose is to answer "does the suite
pass against the floors we advertise", and a red meaning "the harness is incomplete" is
indistinguishable from a red meaning "a declared floor rotted from the outside" &mdash; which is
precisely what the weekly cron exists to catch.

<b>The same fix had already been applied twice, and the check written to prevent a third was
scoped to one job.</b> <code>ci.yml</code>'s free-threaded canary carries <code>setuptools</code>
on its pip line and <code>requirements/test-tools.in</code> declares it, both for this exact
reason. <code>tests/unit/test_canary_deps.py</code> was written alongside them to derive the
suite's unguarded third-party imports and fail if a leg cannot satisfy one &mdash; but it read
<code>jobs["canary"]</code> in <code>ci.yml</code> and nothing else, so it had nothing to say about
the second place the mistake lives.

<b>Shipped:</b> setuptools on the floors pip line, and <code>_harness_jobs()</code> finds the jobs
by shape instead of by name &mdash; any workflow job that builds a venv and then runs
<code>tests/unit</code> or <code>tests/functional</code> out of it. That is five jobs across three
files (<code>ci.yml</code> tests, patch-coverage and canary; <code>floors.yml</code> lowest;
<code>sonarcloud.yml</code>), all checked, including the ones installing from the hash-pinned
<code>requirements/*.txt</code> &mdash; those are merely the ones that are right today, and a lock
can lose a pin as easily as a hand-typed line can miss one. The set is pinned, so a sixth
hand-built venv is a decision rather than an inheritance.
