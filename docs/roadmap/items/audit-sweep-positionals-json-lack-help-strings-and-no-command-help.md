---
id: audit-sweep-positionals-json-lack-help-strings-and-no-command-help
board: code
section: dx
status: shipped
category: CLI · UX
complexity: M
impact: Med
wow: 1
note: exactly one epilog= exists in all of boost_cli; ~30 commands ship bare positionals
order: 241
owner: loop/help-strings
pr: 943
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

<b>Shipped.</b> A sweep of every parser in <code>cli.COMMANDS</code>, sub-parsers included, found
<b>38</b> arguments with no help text across <b>33</b> commands, and 36 empty
<code>&lt;span&gt;&lt;/span&gt;</code> rows in <code>docs/commands.html</code> (the other two sit under
<code>context</code>'s sub-commands, which the page does not render). Each one now says what the
argument accepts, read from the code: which commands take any kind and which only skills, which
resolve a name from the tap when it is not installed, and the default action for
<code>cohort</code>, <code>profile</code>, <code>replay</code>, <code>protocol</code> and
<code>context</code>. The contracts the audit named are in the help screens now: <code>run</code>
names the Agents SDK and the provider key and says <code>--print</code> needs neither,
<code>discover</code>'s query says it searches GitHub live through <code>gh</code>,
<code>conflict</code>, <code>test</code>, <code>verify</code> and <code>attest --verify</code> say
they exit 1, <code>cohort status</code> is named as the same as <code>list</code>, and
<code>policy</code>'s key help lists the keys from <code>policy.DEFAULTS</code>, so the list
cannot fall out of date. The <code>list</code> summary says "skills, rules and workflows".

<code>build_command_reference.py --check</code> now also fails on any argument with no help text,
and <code>tests/unit/test_command_reference_fresh.py</code> walks every command's parser for the
same thing, and pins that the walk reaches the last command in <code>cli.COMMANDS</code>, so the gap
cannot come back. The generator also renders <code>parser.epilog</code> now, after the options as
<code>--help</code> prints it, so <code>cohort</code>'s note that membership is a deterministic hash
of user and cohort now appears on <code>docs/commands.html</code>. <code>explain</code> and
<code>preview</code> say they take a skill, rule or workflow, which is what they resolve: both were
run on a rule and a workflow in a sandbox, installed and from the tap.

<b>Not done: Examples blocks.</b> No command has one to follow. The only <code>epilog=</code> is
<code>cohort</code>'s paragraph about membership hashing, which is a note, not examples, so
there is no convention to extend. Adding one is a style choice for the whole CLI and belongs in its
own change. Since the generator now renders the epilog, an Examples epilog added later reaches the
page with no further work.
