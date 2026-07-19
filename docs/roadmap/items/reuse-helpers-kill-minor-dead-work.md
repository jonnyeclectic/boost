---
id: reuse-helpers-kill-minor-dead-work
board: code
section: shipped
status: shipped
category: Tech-debt
complexity: S
impact: Low
wow: 1
note: helper dedup + double-parse removed
order: 20
owner: loop/reuse-user-helper
pr: 126
title: Reuse helpers; kill minor dead work
---
Shipped in <b>#126</b>. The byte-identical <code>_user()</code> getpass helper —
copy-pasted three times across <code>core/journal.py</code>,
<code>commands/configuration.py</code> and <code>commands/team.py</code> — is now a
single public <code>core/util.user()</code> the three call sites delegate to
(covered incl. the getpass-raises fallback). <code>cmd_simulate</code> also parsed
the same frontmatter <em>twice</em> (<code>_, body = …</code> then
<code>meta, _ = …</code>); collapsed to one
<code>meta, body = frontmatter.parse(text)</code>.
<code>cmd_migrate</code>'s two-agent validation is intentionally left as-is —
its first-fail wording differs from <code>_check_agents</code>' collect-all
message, so routing it through the helper would change user-facing errors.
