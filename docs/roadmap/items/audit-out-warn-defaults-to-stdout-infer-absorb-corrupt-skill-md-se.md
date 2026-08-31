---
id: audit-out-warn-defaults-to-stdout-infer-absorb-corrupt-skill-md-se
board: code
section: dx
status: planned
category: CLI · Bug
complexity: S
impact: High
wow: 2
note: boost infer &gt; SKILL.md writes the AI warning as line 1 of the generated file
order: 222
owner:
pr:
title: "<code>out.warn</code> defaults to stdout: infer/absorb corrupt <code>&gt; SKILL.md</code>; search/explain/context warnings pollute piped stdout"
---
With stderr discarded, four commands still print their warnings on <b>stdout</b>: <code>search --smart 2&gt;/dev/null</code> and <code>explain brainstorming 2&gt;/dev/null</code> begin <code>! AI features need one of `claude` or `gemini` on PATH&hellip;</code>; <code>infer 2&gt;/dev/null</code> prints that warning <em>before</em> the <code>---</code> frontmatter; <code>context apply 2&gt;/dev/null</code> prints <code>! context is disabled &hellip; &mdash; applying anyway</code>. The worst case is data corruption, not noise: <code>boost infer &gt; SKILL.md</code> writes a file whose first line is the warning, and <code>absorb</code>'s stdout carries the <code>==&gt; recurring patterns</code> heading and PATTERN/SEEN table ahead of the SKILL.md payload.

The cause is central: <code>out.warn</code> (<code>boost_cli/core/output.py:221</code>) defaults <code>stream=None</code> &rarr; stdout, and <code>_note_fallback</code> (<code>boost_cli/commands/intelligence.py:47-52</code>) and the explain/context warn calls pass no stream. The stream parameter exists precisely for commands whose stdout is machine-read (the <code>output.py:224</code> docstring), and the <code>--json</code> paths already use it &mdash; <code>search --smart --json 2&gt;/dev/null</code> emits pure parseable JSON. Only the human/text stdout paths are affected, which is what marks this an oversight rather than a design.

Fix, per the verified recommendation: flip <code>out.warn</code>'s default stream to stderr and audit the few callers relying on stdout (JSON paths already pass it explicitly); at minimum pass <code>stream=sys.stderr</code> in <code>_note_fallback</code> and have <code>cmd_infer</code>/<code>cmd_absorb</code> (<code>intelligence.py:859</code>, <code>intelligence.py:1146</code>) route the heading/table to stderr when stdout carries the SKILL.md. Add a test that <code>infer</code> under <code>BOOST_NO_AI</code> writes only frontmatter+body to stdout. No doc changes.

Found by the 2026-08 CLI audit (cluster <code>warnings-on-stdout</code>); repro in the audit log. Verified against source 2026-08-31.
