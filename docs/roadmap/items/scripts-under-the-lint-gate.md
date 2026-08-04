---
id: scripts-under-the-lint-gate
board: code
section: internals
status: shipped
owner: loop/scripts-lint
pr: 471
category: Tech-debt
complexity: M
impact: Med
wow: 1
note: 291 findings across 28 files, measured — most are the same UP sweep the package just finished
order: 99
title: bring <code>scripts/</code> under the ruff gate
---
<code>make lint</code> runs <code>ruff check boost_cli tests evals</code> — and <code>scripts/</code>,
the 28 build-and-gate tools that decide whether every PR merges, is not in the list. Nothing that
lints the product lints the gatekeepers.

<b>Why it bit, twice in one day.</b> The <code>zip(strict=)</code> audit enforced B905 across the
linted trees, and an adversarial review immediately found two more <code>zip()</code> sites in
<code>scripts/</code> that the rule cannot guard — one of them (<code>eval_explain.py</code> pairing
ragas scores with samples by position) exactly the silent-misattribution shape the audit existed to
kill. They were fixed by hand, but the next <code>zip()</code> added to <code>scripts/</code> gets
no intent check, and the same blindness applies to every rule the gate enforces.

<b>Measured, not guessed:</b> running the current rule set over <code>scripts/</code> today finds
<b>291</b> violations — ~277 are the mechanical UP typing sweep the rest of the repo just finished
(<code>List</code> → <code>list</code> and friends), plus a handful of real ones (a
<code>raise ... from</code> miss, collapsible ifs, stale <code>noqa</code>s). So the shape is: one
mechanical pass like the pep585 sweep, a short judgement pass over the rest, then add
<code>scripts</code> to the Makefile line and CI so it stays clean. Some rules may deserve
per-directory ignores (scripts legitimately print, exit, and parse argv) — decide those in the PR
rather than globally.
