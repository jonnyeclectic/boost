---
id: codex-hooks-timeout-units-are-unestablished
board: code
section: planned
status: planned
category: Compat · Research
complexity: M
impact: Low
wow: 2
note: Codex has a `[hooks]` table shaped like Claude's and Gemini's, and the two fields that differ are unverified…
order: 345
owner:
pr:
title: Codex hooks are shaped like Claude's, and the two fields that differ are unverified
---
<b>Found while adding Codex as an agent target.</b> Codex CLI 0.156.1 reads a <code>[hooks]</code>
table keyed by event name, whose value is the same <code>matcher</code> plus
<code>hooks: [{type, …}]</code> block Claude Code and Gemini CLI use. That similarity is the trap
<code>core/hookhost.py</code> was written for: the block shape being identical is what makes the real
differences easy to ship wrong.
<b>What is not established.</b> <em>Timeout units</em> — Claude's are seconds and Gemini's are
milliseconds, so a 10 is either ten seconds or ten milliseconds and nothing observed so far says which
Codex means. <em>Event names</em> — unknown event keys are <b>silently accepted</b>, so a wrong
spelling writes a config that parses, never fires, and reports nothing; a
<code>CLAUDE_TO_CODEX</code> map needs each of the ten Claude events resolved against the real CLI,
including the ones that must map to <code>None</code>. And the <code>prompt</code> and
<code>agent</code> hook types parse but are reported "not supported yet", so boost must refuse them
and say why rather than writing them.
<b>Fix direction.</b> Establish both against a real Codex release the way <code>hookhost.py</code>
establishes Gemini's — its shipped docs, the event list in its bundled JS, and an observed run — then
add the host and name the sources at the top of the file. Until then boost should keep writing no
Codex hooks at all: a hook config that silently never fires is worse than none.
