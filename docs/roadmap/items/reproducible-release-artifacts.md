---
id: reproducible-release-artifacts
board: code
section: pipeline
status: shipped
category: Security · Reproducibility
complexity: M
impact: Med
wow: 3
note: wheel + sdist now bit-identical; setuptools#2133 has no native fix
order: 128
owner: loop/repro
pr:
title: Reproducible release builds — the sdist half nobody's setuptools does for you
---
<code>build_reproducible</code> was Unmet on measurement: with <code>SOURCE_DATE_EPOCH</code> set,
two builds of the same commit produced a <b>bit-identical wheel</b> and a <b>differing
sdist</b>. <code>setuptools</code> writes each tar member's real build-time mtime, and the
builder's <code>uid</code>/<code>gid</code>/user name, into the sdist with no environment
variable to override either &mdash; 54 members differed between builds two seconds apart on the
same machine, and a build on another machine would have differed in the ownership fields too.

<b>The upstream knob doesn't exist.</b> <a href="https://github.com/pypa/setuptools/issues/2133">
pypa/setuptools#2133</a> has asked for <code>SOURCE_DATE_EPOCH</code> support in sdist since 2020;
it is still open, with no fix in the version this project pins. The one PyPI package that already
patches it, <code>setuptools-reproducible</code>, does so by replacing
<code>build-backend</code> entirely &mdash; and its dependency closure could not be hash-pinned
the way the rest of boost's toolchain is, because <code>[build-system].requires</code> is a bare
PEP&nbsp;508 requirement string with no hash field. So the fix is a small, stdlib-only
post-processing step instead: <code>scripts/normalize_sdist.py</code> clamps every member's
mtime, zeroes uid/gid, blanks uname/gname, and resets the gzip container's own header
timestamp, run in <code>publish.yml</code> between <code>python -m build</code> and
<code>twine check</code> &mdash; so nothing is ever attested un-normalized.

<b>The wheel had a real gap too, not just the sdist.</b> <code>publish.yml</code> never set
<code>SOURCE_DATE_EPOCH</code> at all before this &mdash; the "bit-identical wheel" measurement
only held in a controlled local test where the variable was exported by hand. The actual release
pipeline was building an unreproducible wheel as well, and nothing had noticed.

<b>The toolchain that determines the bytes is now pinned twice.</b>
<code>requirements/release-tools.txt</code> hash-pins the outer <code>build</code>/
<code>twine</code> install (<code>publish.yml</code> used to run
<code>pip install build twine</code> unpinned, so last month's toolchain was not recoverable
from the repository). But <code>python -m build</code> resolves <code>setuptools</code> and
<code>setuptools-scm</code> fresh into an isolated build environment regardless of what the
outer install has &mdash; that's the part that actually produces the artifact bytes &mdash; so
<code>pyproject.toml</code>'s <code>[build-system].requires</code> is now exact-pinned
(<code>setuptools==83.0.0</code>, <code>setuptools-scm==10.2.1</code>) rather than left as
<code>&gt;=64</code>/<code>&gt;=8</code>. No hash field exists at that layer; exact-pinning is
the strongest promise PEP 508 allows there.

<b>Falsifiable, not asserted.</b> <code>scripts/check_reproducible.py</code> builds the project
twice with the same <code>SOURCE_DATE_EPOCH</code>, runs the same sdist fix the release pipeline
runs, and diffs the results by sha256 &mdash; <code>--skip-normalize</code> reruns without the fix
to show the gap it closes. Degrades to exit&nbsp;2 ("could not check") rather than exit&nbsp;0
when <code>build</code> isn't installed, matching how boost's own CI controls have failed
silently before: a check that can't run must never read as a pass.

<code>docs/openssf-badge.md</code>'s <code>build_reproducible</code> row now reads <b>Met</b>;
<code>docs/verifying-releases.md</code> carries the re-run measurement and how to rebuild from a
git tag (the sdist itself carries no <code>.git</code> history, so <code>SOURCE_DATE_EPOCH</code>
has to come from a checkout, not the tarball).
