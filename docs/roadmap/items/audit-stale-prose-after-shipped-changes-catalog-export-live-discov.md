---
id: audit-stale-prose-after-shipped-changes-catalog-export-live-discov
board: code
section: dx
status: planned
category: Docs · Drift
complexity: S
impact: Low
wow: 1
note: a documented command that exits 2, 463 vs 464 in eight places, a GPL rule over Apache files
order: 244
owner:
pr:
title: "Stale prose after shipped changes: <code>catalog --export</code>, live discover, 464 count, Apache-2.0"
---
Four patches of prose describe the repo as it was before a shipped change, each verified against the current
tree. <b>A documented command that does not run:</b> <code>docs/security-design.md:35</code> says
<em>a <code>boost catalog export</code> tarball</em>; running it prints <code>Error: one of the arguments
--export --import --show is required</code> and exits 2 &mdash; the flag is <code>--export</code>.
<b>Pre-live-search discover:</b> <code>docs/index.html:877</code> (<em><code>boost discover</code> indexes
10,000+ skills across GitHub</em>) and <code>:940</code> (<em>build the GitHub-wide index &hellip; browse it with
<code>boost discover</code></em>) predate the shipped change that made a query hit GitHub Code Search live; the
index now only backs bare <code>discover</code> and <code>--local</code>, exactly as the command's own help says.

<b>A hard-coded count, off by one and spreading:</b> README:151, <code>semantic-search.md:64</code> and
<code>quickstart.py:39</code> say <code>--catalog</code> taps <b>463</b> registries;
<code>registries.json</code> holds <b>464</b> non-list_only rows of 487, and <code>quickstart --dry-run
--catalog</code> on the 20-tap fixture prints <code>would tap 445 registries</code> (445&nbsp;+&nbsp;19 already
tapped&nbsp;=&nbsp;464). Verification found more copies than the auditor: README:211,
<code>quickstart.py:65</code> and CLAUDE.md:183&ndash;184 and :500. <b>A licence rule contradicting every
file:</b> CLAUDE.md:276 still says headers open with <code>SPDX-License-Identifier: GPL-3.0-only</code>, but
every source file greps to <code>Apache-2.0</code>, LICENSE is the Apache License 2.0, and
<code>scripts/add_spdx_headers.py</code> already writes Apache-2.0 &mdash; the CLAUDE.md paragraph (and its
<code>-only</code>&rarr;<code>-or-later</code> example) is the sole stale statement.

Fix as one doc-only PR: <code>security-design.md:35</code> &rarr; <code>boost catalog --export</code>; rewrite
the two <code>index.html</code> sentences to live-GitHub-search plus <code>boost index</code>/<code>--local</code>;
replace the literal 463 with <em>every catalogued registry</em> (or 464) in README.md:151/211,
<code>semantic-search.md:64</code>, <code>quickstart.py:39/65</code> and CLAUDE.md:183/500 &mdash; a number
<code>scripts/build_registries.py</code> changes should not be hard-coded in prose; and correct the CLAUDE.md
licence paragraph to Apache-2.0. <code>security-design.md</code> and <code>semantic-search.md</code> are already
in <code>prose-lint.yml</code>'s vale list, so no lint wiring is needed; <code>docs/commands.html</code> is
untouched (no parser changes). Found by the 2026-08 CLI audit (cluster stale-prose-docs); repro in the audit log.
