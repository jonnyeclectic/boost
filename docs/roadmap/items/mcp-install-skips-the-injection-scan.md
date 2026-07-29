---
id: mcp-install-skips-the-injection-scan
board: code
section: trust
status: shipped
category: Security · Content
complexity: S
impact: High
wow: 4
note: the one install path with no human watching was the one not scanning
order: 2
owner: fix/mcp-install-scan
pr: 327
title: The MCP <code>boost_install</code> tool skipped the injection scan the CLI runs
---
<code>prompt-injection-scanning-of-skill-markdown</code> shipped the scanner and
<code>secret-and-pii-scanning-of-installed-skills</code> shipped its sibling, but both were
wired up in the <b>command layer</b> &mdash; <code>pkg._warn_injection</code> and
<code>pkg._warn_secrets</code>, called from <code>_report_result</code>. So they ran on exactly
one path: <code>boost install</code>.

The MCP tool did not call them. <code>_tool_install</code> resolved an entry, called
<code>store.install</code>, and reported <em>"installed &hellip; quality score: 70/100"</em> &mdash;
no scan, no warning, whatever the Markdown contained.

<b>That is the path that needed it most.</b> On the CLI a human is watching a terminal and chose
the skill by name. Over MCP, an agent picked the skill and installed it <em>on its own</em>, and
since <code>mcp-check-skills-before-starting-a-task</code> the server's own instructions actively
push it to do that at the start of every task. The content it installs becomes instructions that
agent then follows. A skill carrying <em>"ignore previous instructions"</em> was delivered silently
to the one consumer that cannot notice.

<b>Fixed by moving the behaviour, not by adding a second call site.</b> The scan now lives in
<code>core/installscan.py</code> &mdash; content resolution (SKILL.md for skills,
<code>scan_text</code> for rules/workflows), both scanners, worst-first ordering, the detail cap
and the exact headline wording. <code>pkg.py</code> renders reports through
<code>output.warn</code>; the MCP tool folds the same reports into its reply text and names the
file to read, with an explicit instruction to disregard anything in it that redirects the agent
from the user's task. Advisory on both paths, as before &mdash; it warns, it never blocks.

Putting it in <code>core/</code> is what makes it stick: the CLI wiring was correct and still left
a hole, because "remember to call two helpers" is not a property a new front end inherits.
<code>core/</code> is also what the mutation gate targets, so the logic is now covered by a gate
the command layer never was.
