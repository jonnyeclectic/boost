---
id: audit-mcp-register-s-boost-first-consent-names-only-the-registered
board: code
section: dx
status: planned
category: Safety · Bug
complexity: S
impact: High
wow: 2
note: consent screen prints 1 path; disk gains 4 files across claude/gemini/cursor/windsurf
order: 213
owner:
pr:
title: "<code>mcp register</code>'s boost-first consent names one file but writes every agent"
---
After a real Gemini registration (<code>mcp register --host gemini --no-seed</code>, Gemini CLI on
PATH), the boost-first offer prints <em>&ldquo;boost can also add its own rule, `boost-first`, to your
agents' standing instructions:&rdquo;</em> followed by <b>one</b> path,
<code>$HOME/.gemini/GEMINI.md</code>. Then <em>&ldquo;&#10003; installed boost-first&rdquo;</em> — and
on disk: <code>~/.gemini/GEMINI.md</code>, <code>~/.claude/CLAUDE.md</code> (managed block verified),
<code>~/.cursor/rules/boost-first.mdc</code>, <code>~/.windsurf/rules/boost-first.md</code>; lock
materializations <code>[claude-code, windsurf, cursor, gemini]</code>. Verified live. A rule edits a
file the user reads every session — CLAUDE.md's own rule calls it more invasive than a skill — and
here the write reaches Cursor and Windsurf, which the code comment and the shipped
<code>boost-first-rule</code> roadmap card explicitly promise it never reaches. Under
<code>BOOST_ASSUME_YES=1</code> no question is even shown: the env var flips a default-No consent.

The cause is one missing argument: <code>_offer_boost_first</code>
(<code>configuration.py:1611-1671</code>) prints targets filtered by <code>AGENT_FOR_HOST</code> but
calls <code>store.install()</code> with no <code>only_agents</code> (line 1666), so
<code>_install_rule</code> (<code>store.py:820</code>+) materialises into all enabled agents —
although <code>store.install</code> already accepts <code>only_agents</code>
(<code>store.py:524</code>).

Verified fix: pass the printed scope into the install —
<code>store.install(&hellip;, only_agents=[AGENT_FOR_HOST[h] for h in hosts if
AGENT_FOR_HOST.get(h)])</code> — so the write matches the named targets, and add a test pinning
consent-list == lock materializations. Separately, consider whether <code>BOOST_ASSUME_YES</code>
should flip this default-No consent (<code>BOOST_NO_RULE</code> is currently the only guard). Docs:
<code>docs/roadmap/items/boost-first-rule.md</code>, README.md and <code>docs/index.html</code> where
they describe the offer's scope. Found by the 2026-08 CLI audit (cluster
<code>mcp-rule-consent-scope</code>); repro in the audit log.
