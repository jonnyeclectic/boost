---
id: audit-quickstart-findings
board: code
section: dx
status: planned
category: CLI · Bug
complexity: M
impact: Med
wow: 2
note: without [rag] quickstart taps unpinned at HEAD, and a rerun can never pin them
order: 285
owner:
pr:
title: "boost quickstart: CLI audit findings (2026-08)"
---
<b>Without the <code>[rag]</code> extra, quickstart taps unpinned at HEAD &mdash; and the rerun it promises cannot fix it.</b> <code>cmd_quickstart</code> only fetches the manifest (the source of pins) when <code>want_vectors</code> is true (<code>boost_cli/commands/quickstart.py:145-152</code>), so on a machine without a dense backend the six new taps land with <code>pin: null</code> while the output ends <em>&ldquo;&hellip;install the extra&hellip;, then <code>boost quickstart</code> again&rdquo;</em>. The second run prints <code>&lt;tap&gt; already tapped</code> for all seven (<code>registry.add_many</code> skips existing taps, never re-pins), and once the extra is present <code>shards.sync</code> refuses every mismatched commit: <code>refused (tap is at X, shard is for Y)</code>. That contradicts the module's own docstring &mdash; &ldquo;Pinning is the whole point&rdquo;. Fix: fetch the manifest and pin regardless of <code>dense.have_backend()</code> (pinning is a network-and-config operation, not an embedding one), and on rerun retarget already-tapped registries via <code>shards.ingest</code> instead of skipping them. Update README.md (quickstart section, ~line 145) and docs/semantic-search.md (~line 63).

<b>The <code>[rag]</code> install hint has three different wordings.</b> quickstart says <code>pipx inject boost-skill-cli "boost-skill-cli[rag]"</code> (hard-coded at <code>quickstart.py:175-177</code> and <code>202-204</code>); reindex's <code>embed.fallback_note</code> (<code>boost_cli/core/embed.py:170-179</code>) says unquoted <code>pip install boost-skill-cli[rag]</code>, which fails in zsh (<code>no matches found</code>); doctor and search say quoted <code>pip install 'boost-skill-cli[rag]'</code> via <code>dense.fix_hint()</code>. CLAUDE.md's rule is that doctor and search read one table so they cannot contradict &mdash; these two surfaces bypass it. Fix: have <code>embed.fallback_note()</code> and both quickstart paths call <code>dense.fix_hint()</code>; if pipx wording is wanted, put install-method detection inside <code>fix_hint</code> so every caller inherits it. docs/semantic-search.md is already quoted &mdash; keep it as the reference.

Found by the 2026-08 CLI audit (clusters <code>quickstart-pinning</code>, <code>rag-hint-drift</code>); repro in the audit log.
