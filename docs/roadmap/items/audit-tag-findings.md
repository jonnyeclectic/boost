---
id: audit-tag-findings
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: S
impact: Med
wow: 2
note: "tag brainstorming --verbose exits 0 as a remove of '-verbose'; +x -x writes lock + journal"
order: 294
owner: loop/tag-arg-parsing
pr: 735
title: "boost tag: CLI audit findings (2026-08)"
---
<b><code>boost tag</code> swallows unknown flags and misreads them as operands.</b> <code>tag brainstorming --verbose</code> prints the current tags and exits 0 — the flag is consumed as a removal of the tag <code>-verbose</code>; <code>tag --verbose</code> gives <em>"Error: --verbose is not installed"</em> (the flag becomes a skill name); verification found a third hole: <code>tag brainstorming --list</code> silently discards the skill-name operand and lists <b>all</b> tags. Cause: <code>cmd_tag</code>'s manual split (<code>boost_cli/commands/info.py:988-993</code>) whitelists only <code>--list</code>/<code>--json</code>/<code>-h</code>/<code>--help</code>; every other <code>--x</code> token falls through as an operand. Every sibling command rejects unknown options with <em>"unrecognized arguments"</em> exit 2.

<b>And the mutation path has no before/after check.</b> <code>tag brainstorming -nosuch</code> removes a tag that was never present — silent, exit 0; <code>tag brainstorming +x -x</code> prints &#10003; and writes the lock plus a journal event for a net no-op (<code>changed</code> is set per-token at <code>info.py:1027-1041</code>, never compared to the before set); <code>"+with space"</code> is accepted as <code>#with space</code>; <code>+Design</code> and <code>#design</code> coexist. The shipped roadmap item <code>robust-tag-argument-parsing</code> (PR 94) built this manual split — these are residual holes in it, not a duplicate.

Fix in <code>cmd_tag</code>: hand any token starting with <code>--</code> (or <code>-letter</code> that is not a tag operand) to argparse so it errors; compute <code>changed = sorted(tags) != sorted(before)</code>; print a one-line notice for removing an absent tag; reject whitespace in tags; document or fold case; error when a name is given with <code>--list</code>. Regenerate <code>docs/commands.html</code> if the help text gains the tag grammar.

Found by the 2026-08 CLI audit (cluster <code>tag-arg-parsing</code>); repro in the audit log.
