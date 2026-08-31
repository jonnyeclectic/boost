---
id: audit-info-stats-explain-render-a-different-smaller-shape-for-rule
board: code
section: dx
status: planned
category: CLI · Bug
complexity: M
impact: Med
wow: 1
note: info --json is 13 keys for a skill, 3 for a rule — and only the rule says its kind
order: 229
owner:
pr:
title: "<code>info</code>/<code>stats</code>/<code>explain</code> render a smaller shape for rules and workflows than for skills"
---
All three item kinds install, but the reporting commands treat two of them as second-class.
<code>info dotnet-build --json</code> (a rule) returns
<code>{"name","kind":"rule","installed":{&hellip;}}</code> &mdash; three keys &mdash; while
<code>info brainstorming --json</code> (a skill) returns thirteen (description, latest, tap, store,
quality, size, files, capabilities, &hellip;) and <b>no <code>kind</code> key at all</b>: the rich envelope
is the one that cannot say what it describes. The human rule card omits the description the catalog
has. A not-installed workflow is worse: <code>info actix-expert</code> prints no kind badge or line and
shows <code>source&nbsp;&nbsp;agents</code> &mdash; the tap's whole <code>agents/</code> directory, not
<code>agents/actix-expert.md</code> &mdash; because the path comes from <code>cat['rel_dir']</code> instead
of <code>cat['skill_md']</code>.

<code>stats dependency-management</code> (a rule) ends at <em>&ldquo;activity 1 installs &middot; 0 updates
&middot; 0 uninstalls&rdquo;</em> with no <em>latest &hellip; (up to date)</em>, <em>description</em> or
<em>upstream</em> section although <code>catalog.find</code> found the entry, and its agents line is
sorted while the skill path prints lock order (<code>discovery.py:1766-1768</code> vs
<code>:1800</code>) &mdash; the separate <code>kind != skill</code> branch at
<code>discovery.py:1754-1775</code> renders a strictly smaller field set. And <code>explain
dependency-management</code> after install <em>loses</em> the description it printed before install, with
<em>Outline:</em> now starting at <code>dependency-management</code> &mdash; the CLAUDE.md managed-block
header, not a real heading.

Fix per the verified recommendation: fold the <code>kind != skill</code> branches of
<code>cmd_stats</code> and <code>cmd_info</code> (<code>boost_cli/commands/info.py:389-544</code>) into the
main path, omitting only store-dir/size facts that truly don't apply; add <code>kind</code> +
<code>description</code> to the skill JSON envelope (<code>info.py:454-465</code>) and the materialized
envelope symmetrically; use <code>cat['skill_md']</code> for a not-installed rule/workflow's source; pick
one (sorted) agents ordering; and have <code>cmd_explain</code> fall back to
<code>cat['description']</code>/the lock's description and strip the <code>#&nbsp;&lt;name&gt;</code> block
header before the heading scan. Found by the 2026-08 CLI audit (cluster info-kind-parity); repro in
the audit log.
