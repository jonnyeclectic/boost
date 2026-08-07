---
id: install-path-disambiguation
board: code
section: dx
status: shipped
category: CLI · Install
complexity: S
impact: High
wow: 4
note: the ambiguity error named the paths and no flag could act on them — a dead end
order: 104
owner: loop/efficiency-registries
pr: 483
title: <code>install</code> refused an ambiguous name and offered no way to answer it
---
<code>resolve_one</code> already gets this mostly right. Identical vendored copies collapse to the
shallowest path; genuinely different skills sharing a name inside one registry are
<em>refused</em>, on the sound reasoning that boost cannot pick between two real alternatives on
the user's behalf. The error even printed the candidate paths.

<b>What it did not do is give anyone a way to answer it.</b> The hint said "inspect the paths
above and raise it with the tap", and no syntax existed that could act on them — not
<code>tap:name</code> (same tap, so it re-raises the identical error), not
<code>skills/name</code>, not <code>name@path</code>. The user was told exactly what the choice
was and handed no way to make it. Every path out led back to the same message.

<b>Found by cataloguing two registries where it made every item uninstallable.</b>
<code>DietrichGebert/ponytail</code> ships each of its seven items twice — a canonical
<code>skills/x</code> and an <code>.openclaw/skills/x</code> mirror whose <em>description</em>
differs, which is precisely the "genuinely different, user must choose" branch.
<code>JuliusBrussee/caveman</code> is worse: <code>caveman</code> alone matches four paths. All
21 items across both were reachable by <code>search</code> and <code>info</code>, and
installable by nobody. Catalogued-but-uninstallable is the kind of gap a curation PR creates and
never notices, because the row looks correct.

<code>boost install NAME --path P</code> now filters the candidates. Three details carry the
weight:

<b>An exact <code>rel_dir</code> beats a suffix match.</b> Suffix matching exists so users can
paste a fragment rather than a long vendored prefix, but on its own it makes the canonical case
unresolvable: <code>--path skills/ponytail</code> also matches
<code>.openclaw/skills/ponytail</code>, so naming the exact path the error printed still reported
"ambiguous". Exact-wins fixes the shape the flag exists for. The suffix rule stays
segment-anchored — <code>s/dbg</code> must not be satisfied by <code>not-s/dbg</code>.

<b>A <code>--path</code> that matches nothing is an error even when the name is unique.</b> The
first cut skipped filtering unless there was an ambiguity to resolve, so a typo'd path silently
installed the single match — reporting success for the copy the user was trying to steer away
from. Filtering always turns a typo into a message that lists the real paths.

<b>It cannot resolve a cross-tap collision, by construction.</b> Two taps are two supply chains
and a path is not provenance, so narrowing runs before the existing multi-tap refusal and never
merges two of them. Typosquatting makes that distinction load-bearing, so it is pinned by a test
rather than left to the reading.

Traversal is impossible by design and pinned anyway: <code>--path</code> only <em>filters rows
the catalog already holds</em> and never builds a filesystem path, so
<code>../../etc/passwd</code> can only fail to match. The test exists so a future rewrite cannot
quietly turn the flag into a path constructor.
