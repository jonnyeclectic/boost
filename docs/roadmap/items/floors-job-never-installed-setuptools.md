---
id: floors-job-never-installed-setuptools
board: code
section: trust
status: shipped
category: CI · Bug
complexity: S
impact: Med
wow: 2
note: the same missing dependency, in the second of six hand-built venvs
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
<code>tests/unit</code> or <code>tests/functional</code> out of it. That is <b>six</b> jobs across
three files (<code>ci.yml</code> tests, patch-coverage, canary and onnx-inference;
<code>floors.yml</code> lowest; <code>sonarcloud.yml</code>), all checked, including the ones
installing from the hash-pinned <code>requirements/*.txt</code> &mdash; those are merely the ones
that are right today, and a lock can lose a pin as easily as a hand-typed line can miss one. The
set is pinned, so a seventh hand-built venv is a decision rather than an inheritance.

<b>Six, and the first draft said five.</b> <code>ci.yml:onnx-inference</code> builds its own venv
and runs one file out of <code>tests/unit</code>, and the path filter compared with
<code>endswith</code>, which a single file does not satisfy &mdash; so the card claimed "the sixth
is covered before it is written" while the sixth was already written and already being dropped.
Finding jobs by shape is only worth something if the shape is the real one.

<b>Attribution by interpreter is the load-bearing half.</b> <code>floors.yml</code> runs
<code>python -m pip install uv</code> on the <em>runner's</em> Python at the top of the same
<code>run:</code> block whose <code>.venv</code> then runs the suite. A scan that unions every
<code>pip install</code> in a job cannot tell "setuptools is on the suite's path" from "setuptools
is on some path" &mdash; so moving the name one line up would have left this check green with the
job still red on the same seventeen imports, which is the exact failure it exists to stop. Each
install is now credited to the interpreter it lands in (<code>.venv/bin</code>,
<code>.venv/Scripts</code> and <code>$VENV_BIN</code> being one), and only the interpreter that
runs pytest counts. Verified by moving <code>setuptools</code> onto the system line: the check
goes red, as it does when the name is deleted outright.

Three more parser holes went with it, each found by writing the input rather than reading the
code: <code>pip install pytest; echo setuptools</code> credited setuptools, because the
stop-token check compared against <code>";"</code> and <code>str.split()</code> never produces a
bare one; a backslash continuation put <code>pytest</code> and its paths on different lines, so a
job spelled that way read as running no tests and was silently excluded from every assertion here;
and only <code>*.yml</code> was globbed. A <code>pip install</code> inside an <code>if</code> is
still credited unconditionally &mdash; nothing here evaluates shell conditions &mdash; so a test
fails the build if a harness job ever starts doing that, rather than letting the check go
one-sided in the dangerous direction.
