---
id: audit-install-findings
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: M
impact: Med
wow: 1
note: "3 of 4 clusters landed; cross-scope-name-block gets a safe refusal, not true coexistence"
order: 273
owner: loop/audit-install-findings
pr: 823
title: "<code>boost install</code>: CLI audit findings (2026-08)"
---
<b>Rule/workflow lock entries are name-keyed across scopes</b> <em>(med)</em>. With the
benchmarking rule at user scope, <code>install benchmarking --local</code> in a project fails
<em>&ldquo;Error: benchmarking is already installed / hint: <code>boost reinstall benchmarking</code>
to force&rdquo;</em> &mdash; the project has no copy, and the hint would reinstall the user one. The
reverse direction blocks too, and skills coexist fine (separate project lock). Worse, the
<code>--force</code> escape overwrites the user-scope lock entry with the project one, orphaning the
user materializations so uninstall can no longer clean them. <code>_install_rule</code>
(<code>store.py:836-839</code>) and <code>_install_workflow</code> (<code>store.py:1074</code>) gate
on a name-only lookup with no scope/base comparison. Fix: key entries by scope (or compare
<code>existing scope/base</code> before raising), word the error &ldquo;already installed at user
scope&rdquo;, and refuse a cross-scope <code>--force</code> overwrite without cleanup. Docs:
README's install-scope section (~301-328) and
<code>docs/roadmap/items/install-scope-user-or-project.md</code>.
(Cluster <code>cross-scope-name-block</code>.)

<br><br><b><code>--path</code> says &ldquo;under path&rdquo; but matches suffix-only</b>
<em>(low)</em>. <code>--path plugins/tdd/skills</code> is refused while the error's own hint lists
<code>plugins/tdd/skills/test-driven-development</code> &mdash; a path that <em>is</em> under it.
Suffix matching is the shipped design (<code>install-path-disambiguation</code>, PR 483); the wording
is the defect. Reword the raise in <code>catalog.py:~502</code> to &ldquo;no copy of X whose path ends
with Y&rdquo; and hint &ldquo;pass a trailing segment of one of: &hellip;&rdquo;.
(Cluster <code>install-path-prefix-match</code>.)

<br><br><b>The MCP offer never shows the runnable command</b> <em>(low)</em>. The server row prints
only <em>demo-echo &nbsp;<code>npx</code></em> though the sidecar declares <code>npx -y
@example/demo-echo-mcp</code> plus env, and on decline the hint is a literal elided
<em><code>claude mcp add &hellip;</code></em>; the full argv only prints when the host CLI is
missing. <code>_offer_mcp</code> renders <code>how</code> from <code>spec['command']</code> alone
(<code>pkg.py:161-164</code>) and <code>mcpdecl.register_argv</code> already exists
(<code>pkg.py:201</code>) &mdash; render command+args, print the joined argv on decline, and indent
the confirm prompt to match its neighbours. (Cluster <code>mcp-offer-command-detail</code>.)

<br><br><b>The typosquat warning prints three times</b> <em>(low)</em>.
<code>install NeoLabHQ/context-engineering-kit:test-driven-development --dry-run</code> prints the
identical <em>&ldquo;closely resembles test-driven-development
(sickn33/antigravity-awesome-skills)&rdquo;</em> warning 3&times;, one per mirror copy in the
look-alike tap. De-duplicate <code>find_confusions</code> on <code>(name.lower(), tap)</code>
(<code>typosquat.py:79-87</code>) so the <code>[:3]</code> slice in <code>_warn_confusions</code>
covers three distinct look-alikes. Found by the 2026-08 CLI audit (cluster
<code>typosquat-warning-dupes</code>); repro in the audit log.

<b>Status (2026-09).</b> Three of the four clusters shipped as described above:
<code>install-path-prefix-match</code> (catalog.py wording), <code>mcp-offer-command-detail</code>
(<code>mcpdecl.command_line</code> renders the full command+args, the decline path prints the real
argv), and <code>typosquat-warning-dupes</code> (<code>find_confusions</code> dedupes on
<code>(name.lower(), tap)</code>). <code>cross-scope-name-block</code> got the <b>narrower</b> of the
fix's own two options: <code>store._check_scope_conflict</code> now refuses a rule/workflow install
whose name collides with an existing lock entry recorded under a <i>different</i> scope/base —
naming the real location ("already installed at user scope") and refusing even under
<code>--force</code>, which closes the silent-corruption half of the bug (a forced cross-scope
install used to overwrite the other scope's lock entry, orphaning its materializations). What is
still missing is the other half: rules and workflows still cannot <i>coexist</i> across scopes the
way skills do, because they share one lock keyed by bare name with no per-location table — skills
got a separate <code>projectlock.py</code> when project scope was added, rules/workflows never did.
Giving them the same treatment (a <code>rules</code>/<code>workflows</code> section in
<code>projectlock.py</code>, wiring <code>_install_rule</code>/<code>_install_workflow</code> and
their uninstall/sync counterparts through it for project scope) is real coexistence but is its own,
larger change, and belongs in its own card rather than folded into a bugfix PR.
