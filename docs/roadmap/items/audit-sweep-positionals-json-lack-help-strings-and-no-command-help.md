---
id: audit-sweep-positionals-json-lack-help-strings-and-no-command-help
board: code
section: dx
status: planned
category: CLI · UX
complexity: M
impact: Med
wow: 1
note: exactly one epilog= exists in all of boost_cli; ~30 commands ship bare positionals
order: 241
owner:
pr:
title: "Sweep: positionals/<code>--json</code> lack help strings and no command help shows examples (~30 cmds)"
---
Across roughly thirty commands the help screens end at the options table with undocumented arguments.
Observed verbatim: <code>help cohort</code> prints <code>{list,create,delete,status,apply}</code> with no help
string for the action; <code>test --help</code> shows <code>positional arguments:</code> then <code>NAME</code>
with nothing after it; <code>conflict --help</code> and <code>attest --help</code> each list <code>--json</code>
with an empty help line; <code>edit</code>/<code>explain</code>/<code>home</code> give <code>name</code> no text
(so <code>docs/commands.html</code> renders <code>&lt;code&gt;name&lt;/code&gt;&lt;span&gt;&lt;/span&gt;</code>).
No help screen in the audit shows an Examples block. The gaps hide real contracts: <code>run</code> never
mentions its SDK/key prerequisites (only the runtime error does), <code>discover --help</code> never says a
query hits GitHub live while bare/<code>--local</code> read the cache, <code>conflict</code>'s exit-1-on-findings
is undocumented, <code>cohort status</code> is an unadvertised alias of <code>list</code>, and <code>policy</code>'s
11 valid keys appear only in the error hint after a wrong <code>set</code>.

Verification confirmed this is omission, not style: the mechanism works and is used exactly once &mdash;
the only <code>epilog=</code> in all of <code>boost_cli</code> is cohort's membership-hash paragraph
(<code>team.py:74</code>), and <code>team.py:77</code> adds the action positional with no <code>help=</code>.
Nothing in CLAUDE.md declares terse help deliberate, and the content gap is unchanged at
<code>COLUMNS=60</code> under a TTY, so it is not a rendering artifact.

Fix as one sweep PR: add <code>help=</code> to every bare positional (action choices, <code>NAME</code>,
<code>--json</code>) and an Examples epilog per parser &mdash; <code>cliparse.parser</code> forwards
<code>**kwargs</code> to argparse, so no plumbing is needed. Extend
<code>scripts/build_command_reference.py</code> to render <code>parser.epilog</code> (lines 119/137 render
description and per-arg help but currently drop the epilog) and fail <code>--check</code> on empty help
strings, then regenerate <code>docs/commands.html</code>. Document the defaults (cohort/profile default action
= <code>list</code>) and the <code>cohort status</code> alias while there; the <code>list</code> summary in
<code>cli.py</code> COMMANDS should also say "skills, rules and workflows" to match its own description.
Found by the 2026-08 CLI audit (cluster help-examples-sweep); repro in the audit log.
