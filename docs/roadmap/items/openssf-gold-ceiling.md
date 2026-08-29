---
id: openssf-gold-ceiling
board: code
section: health
status: inflight
category: Security · Posture
complexity: M
impact: Med
wow: 3
note: 26% → 61% live; the parser that said "21 criteria" had missed two
order: 8
owner: loop/openssf-gold
pr:
title: OpenSSF gold — how far it goes without a second human
---
Gold sat at <b>26%</b> with eleven criteria unanswered, and the standing assumption was that
gold needs a second person so none of it was worth doing. Half of that was true. Answering the
eleven rather than assuming took gold from 26% to <b>61%</b> live, and every flip was evidence that
already existed or a measurement nobody had taken.
<b>Two were already true and unmeasured.</b> <code>test_statement_coverage90</code> and
<code>test_branch_coverage80</code> read like months of work against a gate that floors
coverage at 80%. Measured, the unit and functional suites alone — no smoke, no BDD — give
<b>95.2% statements and 90.8% branches</b>. Branch coverage had never been switched on, so the
second number did not exist to be checked. Both floors now live in <code>pyproject.toml</code>
(<code>branch = true</code>, <code>fail_under = 90</code>) so the answers stay enforced rather
than asserted — the same failure mode as the <a href="roadmap.html#openssf-best-practices-badge">
key fingerprint no test asserted</a>.
<b>Two were documents.</b> <code>code_review_standards</code> wanted the review requirement
written down; <code>docs/code-review.md</code> now says how review is conducted, what is
checked and what makes a change acceptable — opening with the single-maintainer shape instead
of describing a process the project does not have. <code>security_review</code> wanted a
review inside five years considering the requirements and the boundary, which this quarter's
work <i>was</i>; it is now a dated record with its four findings and their outcomes, two of
which no static analyser produces.
<b>One was a sweep.</b> <code>copyright_per_file</code> and <code>license_per_file</code> put
<code>Copyright the boost contributors.</code> and
<code>SPDX-License-Identifier</code> on <b>314 files</b> — <code>GPL-3.0-only</code> at the
time, <code>Apache-2.0</code> since. Either way the expression is one constant in
<code>scripts/add_spdx_headers.py</code>, and a test fails if it ever stops matching what
<code>LICENSE</code> actually says.
<b>What is left, and why.</b> <code>build_reproducible</code> is Unmet on measurement, not
opinion: with <code>SOURCE_DATE_EPOCH</code> the wheel is bit-identical across builds and the
sdist is not, because setuptools stamps real mtimes and the builder's uid/gid into the tarball
— 54 members differ between builds two seconds apart. <code>hardened_site</code> is Unmet
because GitHub Pages sends no security headers and exposes no way to set them, while github.com
and pypi.org send the full set. The last three — <code>bus_factor</code>,
<code>contributors_unassociated</code>, <code>two_person_review</code> — are a recruiting
problem, and simulating them with a second account would be the one dishonest answer in the
whole exercise.
<b>The count itself was wrong.</b> This card and the badge document both said gold was
<b>21 criteria</b>. It is 23. The parser reading them out of <code>criteria.yml</code> matched
<code>[a-z_0-9]+</code>, so it silently dropped <code>require_2FA</code> and
<code>secure_2FA</code> — the only two gold criterion names containing a capital letter. 21 is
a plausible-looking total, so nothing flagged it; the gap appeared only on the submission form,
where 23 rows were waiting. Same shape as the <a href="roadmap.html#openssf-best-practices-badge">
fingerprint no test asserted</a>: the check ran, returned a believable answer, and was wrong.
