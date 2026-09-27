---
id: free-threaded-canary-warns-about-nothing
board: code
section: pipeline
status: shipped
category: CI · Bug
complexity: S
impact: Medium
wow: 2
note: the 3.14t early-warning leg has been red on a missing setuptools, so a real no-GIL regression would not change its colour
order: 350
owner: loop/canary-setuptools
pr: 979
title: The free-threaded canary is red for a missing <code>setuptools</code>, so it warns about nothing
---
<b>Found while reading CI on an unrelated PR.</b> <code>canary (3.14t free-threaded)</code> exists as
an early-warning leg: a GIL-removal regression should surface there before a user on 3.14t hits it on
release day. It is <code>continue-on-error: true</code> on purpose &mdash; a signal, not a gate &mdash;
and that is exactly what lets it rot unnoticed. Nothing about a red canary stops a merge, so nothing
about a red canary gets read.
<br><br>
<b>It was failing, and not for a no-GIL reason.</b> Seventeen failures and errors, all in one file and
all one cause: <code>ModuleNotFoundError: No module named 'setuptools'</code> out of
<code>tests/unit/test_sdist_contents.py</code>, which imports
<code>setuptools._distutils.filelist</code> to run setuptools' own MANIFEST matcher rather than
building an sdist over the network. The canary builds its venv by hand &mdash;
<code>pip install pytest pytest-cov coverage hypothesis</code> then <code>-e .</code> &mdash; and two
things have to be true at once for that to be enough, neither of which is: a modern <code>venv</code>
seeds pip alone, and <code>pip install -e .</code> resolves the build backend in an <i>isolated</i>
build environment that leaves nothing behind in <code>.venv</code>. Reproduced on the real interpreter,
Python 3.14.7: <code>python3 -m venv x</code> then <code>x/bin/pip list</code> prints
<code>pip</code> and nothing else, and the file goes from <b>7 failed, 10 errors</b> to
<b>17 passed</b> on <code>pip install setuptools</code> alone. The main matrix never saw it because
<code>make venv</code> installs the hash-pinned <code>requirements/*.txt</code>.
<br><br>
<b>Why it matters even though the leg cannot block a merge.</b> A red canary is indistinguishable from
a red canary. The one on every PR today is an environment gap, so the day a free-threaded regression
lands the leg goes from red to red and nobody looks. An allow-failure check earns its place by being
green; the colour <i>is</i> the signal, and this one had been spending it on something else.
<br><br>
<b>The fix, and the part that keeps it fixed.</b> <code>setuptools</code> joins that leg's install list
&mdash; it is a test dependency there, exactly as it is for the matrix, and not a build one.
<code>tests/unit/test_canary_deps.py</code> then derives, from the suite itself, the third-party
modules it imports <b>unguarded</b>, and fails if the canary's <code>pip install</code> line is missing
one. The classification is the load-bearing half, because the convention it enforces already exists and
setuptools was the one exception to it: <code>yaml</code> is behind
<code>pytest.importorskip</code>, <code>mutmut</code> behind a <code>try</code>, and
<code>sqlite_vec</code> behind a whole-file <code>pytestmark = pytest.mark.skipif(not
_vec_loadable(), &hellip;)</code> &mdash; which guards a <i>deferred</i> import (no test in the file
runs to call the helper) but would not guard a module-level one, since a marker is consulted after
collection. A module in neither the distribution map nor the repo-local set is a hard error rather
than a silent pass: a new test dependency gets classified by the person adding it.
