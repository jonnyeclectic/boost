---
id: codex-hooks-timeout-units-are-unestablished
board: code
section: planned
status: shipped
category: Compat · Research
complexity: M
impact: Low
wow: 2
note: Codex has hooks shaped like Claude's, and the two fields that differ were unverified — now measured, and the file is `hooks.json`…
order: 345
owner: loop/codex-hooks
pr: 981
title: Codex hooks are shaped like Claude's, and the two fields that differ are unverified
---
<b>Found while adding Codex as an agent target.</b> Codex CLI 0.156.1 reads a <code>[hooks]</code>
table keyed by event name, whose value is the same <code>matcher</code> plus
<code>hooks: [{type, …}]</code> block Claude Code and Gemini CLI use. That similarity is the trap
<code>core/hookhost.py</code> was written for: the block shape being identical is what makes the real
differences easy to ship wrong.
<b>What is not established.</b> <em>Timeout units</em> — Claude's are seconds and Gemini's are
milliseconds, so a 10 is either ten seconds or ten milliseconds and nothing observed so far says which
Codex means. <em>Event names</em> — a wrong spelling writes a config that parses, never fires, and
reports nothing; a <code>CLAUDE_TO_CODEX</code> map needs each of the ten Claude events resolved
against the real CLI, including the ones that must map to <code>None</code>. And the
<code>prompt</code> and <code>agent</code> hook types parse but are reported "not supported yet", so
boost must refuse them and say why rather than writing them.
<b>Fix direction.</b> Establish both against a real Codex release the way <code>hookhost.py</code>
establishes Gemini's — its shipped docs, the event list in its bundled JS, and an observed run — then
add the host and name the sources at the top of the file. Until then boost should keep writing no
Codex hooks at all: a hook config that silently never fires is worse than none.
<b>Measured, and two of this card's own premises were wrong.</b> Against codex-cli 0.156.1, four
sources — the schemas <code>codex app-server generate-json-schema</code> emits, the
<code>hooks/src/**</code> strings in the shipped binary, observed <code>app-server</code>
<code>hooks/list</code> runs against throwaway <code>CODEX_HOME</code>s, and the 23 draft-07 schemas
the binary embeds for the hook stdout protocol. <em>The file is <code>hooks.json</code></em>, not the
<code>[hooks]</code> table this card assumed: <code>$CODEX_HOME/hooks.json</code> at user scope and
<code>&lt;project&gt;/.codex/hooks.json</code> at project scope, in <b>exactly</b> Claude's
<code>{"hooks": {…}}</code> shape. A <code>[hooks]</code> table in <code>config.toml</code> is the
alternative representation, and both at once load both plus a warning. So boost writes JSON and needs
no TOML writer. <em>Timeout is <code>timeout</code>, in seconds</em> — Claude's units, not Gemini's;
<code>timeoutSec</code> is the wire spelling only and as a config key is ignored, falling back to
600 s. <em>Events are twelve, PascalCase, matched exactly</em>, and an unknown or wrong-case key is
silently <b>dropped</b>, not "accepted" — no hook, no warning, no error — which is why
<code>translate()</code> refuses for Codex where it warns-and-adds for Gemini. Codex has no
<code>Notification</code>; it adds <code>PermissionRequest</code>, <code>PostCompact</code> and
<code>Interrupt</code>. One thing this card feared is not a risk: a hook boost writes starts
<b>untrusted</b> and Codex says so at startup ("1 hook is new or changed", "Hooks need review"), so it
does not fire silently — it asks.
