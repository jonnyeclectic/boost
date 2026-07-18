---
id: atomic-corruption-safe-lock-file-writes
board: code
section: internals
status: next
category: Correctness · Robustness
complexity: M
impact: High
wow: 4
note: 
order: 1
owner:
pr:
title: Atomic, corruption-safe lock-file writes
---
<code>read()</code> returns an empty skeleton on <b>any</b> JSON error and <code>write()</code> is a bare <code>write_text</code> at <code>core/lockfile.py:55</code>. An interrupted or concurrent write truncates the lock — the next <code>set_skill()</code> then <b>permanently drops every prior install record</b> while store dirs linger as orphans. Write to a temp file + <code>os.replace()</code>, and tell "empty" apart from "corrupt".
