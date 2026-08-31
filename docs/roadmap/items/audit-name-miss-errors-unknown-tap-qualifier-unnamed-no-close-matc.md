---
id: audit-name-miss-errors-unknown-tap-qualifier-unnamed-no-close-matc
board: code
section: dx
status: planned
category: CLI · UX
complexity: S
impact: Med
wow: 2
note: a one-letter typo gets no hint while nonsense input gets three suggestions
order: 233
owner:
pr:
title: "Name-miss errors: unknown tap qualifier never named, no close-match hint, tap tokens pollute suggestions"
---
Three gaps in one resolver make name misses unhelpful across <code>install</code>, <code>info</code>,
<code>cat</code>, <code>preview</code>, <code>deps</code>, <code>log</code>, <code>home</code>,
<code>explain</code> and <code>changelog</code>. First: <code>install nosuch/tap:brainstorming</code>
&rarr; <em>"Error: no skill named 'nosuch/tap:brainstorming' in any tap"</em> &mdash; brainstorming
exists and is even installed; the <em>tap</em> is what is unknown, and nothing says so. Second, the
hint inversion: <code>install brainstormng</code> (one letter off) gets <b>no</b> hint, while
<code>definitely-not-a-skill-xyz</code> gets three suggestions &mdash; the hint is BM25
<code>search()</code> over the input, so nonsense sharing a token scores and a near-miss does not.
Third: on a qualified miss the search runs over the <b>whole qualified string</b>, so
<code>log NeoLabHQ/context-engineering-kit:brainstorming</code> suggests
<code>context-engineering</code> items scored on the <em>tap's</em> tokens and never
<code>brainstorm</code>, which that tap ships; the verifier confirmed the same pollution with a valid
tap and a typo'd name. Separately, <code>lint</code>/<code>verify</code>/<code>drift</code>'s
installed-name lookup has the same gap: <code>lint brainstormin</code> &rarr; <em>"not installed:
brainstormin / hint: see what is with <code>boost list</code>"</em> with exactly one skill installed,
one character away.

Verified in source: <code>catalog.resolve_one</code>'s miss branch
(<code>boost_cli/core/catalog.py:486-531</code>) handles only the path-shaped-tail case &mdash; it
never checks the qualifier against <code>registry.list_taps()</code>, builds the hint from
<code>search(name)</code> over the full string, and has no difflib fallback when search is empty;
<code>_common.py:46</code>/<code>:75</code> raise "not installed" with a fixed hint. The fix is two
resolvers: in <code>resolve_one</code>'s miss branch, <code>split_name</code> first &mdash; if the
qualifier matches no configured tap, raise <em>"no tap named 'X'"</em> listing the taps that do ship
the bare name; otherwise run <code>search(bare)</code> (optionally tap-restricted) instead of
<code>search(full)</code>; and add <code>difflib.get_close_matches</code> over catalog names when
search comes back empty. In <code>_common</code>'s not-installed error, append
<code>get_close_matches</code> over <code>lockfile.all_installed()</code> names. No flag or summary
changes, so no doc regeneration. Found by the 2026-08 CLI audit (cluster
<code>name-miss-error-hints</code>); repro in the audit log.
