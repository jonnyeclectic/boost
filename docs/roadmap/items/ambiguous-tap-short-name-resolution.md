---
id: ambiguous-tap-short-name-resolution
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: High
wow: 3
note:
order: 28
owner: loop/tap-name-ambiguity
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
<b>Shipped.</b> <code>registry.get()</code> is now tiered — exact <code>owner/repo</code>, then <code>safe_name</code>, then the bare repo tail — and refuses a short name that matches more than one tap instead of taking the first. Two corrections while fixing it: there is no <i>sort</i>, the winner was whichever came first in <code>config.json</code>; and the fix was <b>half a fix</b> as originally scoped. <code>catalog.find()</code> carried an independent, untiered <code>tap in (e["tap"], tail)</code> membership test, so with both taps configured <code>angular/skills:brainstorming</code> also matched <code>microsoft/skills</code>, and <code>boost bundle apply</code> took <code>matches[0]</code> — silently installing from the wrong tap, verbatim the defect this item exists to fix. Fixing only <code>registry.get</code> would have left the CLI self-contradictory: <code>boost untap skills</code> erroring while a Boostfile silently guessed. Both resolvers are tiered now and <code>bundle apply</code> refuses an ambiguous entry rather than picking one.
