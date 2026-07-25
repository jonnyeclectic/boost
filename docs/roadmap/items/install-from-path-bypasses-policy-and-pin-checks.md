---
id: install-from-path-bypasses-policy-and-pin-checks
board: code
section: trust
status: planned
category: Security · Bug
complexity: S
impact: High
wow: 3
note: code-scan finding
order: 9
owner:
pr:
title: <code>install_from_path</code> bypasses pin &amp; policy checks
---
<code>boost import</code>, <code>boost migrate --from-skills-cli</code>, <code>boost rename</code>,
and the local-install paths behind the AI <code>distill</code>/<code>evolve</code> commands all
route through <code>store.install_from_path()</code>, which never calls
<code>policy.check_install()</code> and never checks <code>existing.get("pinned")</code> the way
<code>store.install()</code> does. Any of those commands can silently overwrite a pinned skill, or
one that <code>blocked_skills</code>/<code>allowed_taps</code>/<code>max_skills</code>/<code>pin_only</code>
policy would otherwise refuse. Route <code>install_from_path</code> through the same
pinned/existing/policy gates as <code>install()</code>.
