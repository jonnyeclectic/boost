---
id: ambiguous-tap-short-name-resolution
board: code
section: internals
status: planned
category: Bug
complexity: S
impact: High
wow: 3
note:
order: 28
owner:
pr:
title: Ambiguous tap short-name resolution silently picks the wrong tap
---
<code>registry.get(name)</code> matches on full name, safe-name, or trailing path segment and returns
the <em>first</em> hit with no ambiguity check — unlike <code>catalog.resolve_one</code>, which
explicitly errors on a multi-tap ambiguous match. Three of the five default taps end in
<code>/skills</code>, so after <code>boost tap --defaults</code>, <code>boost untap skills</code> or
<code>boost update skills</code> silently resolves to whichever tap sorts first and the others
become unreachable by short name. Raise on an ambiguous short-name match, mirroring
<code>resolve_one</code>.
