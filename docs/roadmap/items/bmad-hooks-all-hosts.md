---
id: bmad-hooks-all-hosts
board: code
section: shipped
status: shipped
category: Agents · Parity
complexity: S
impact: Med
wow: 3
note: the autopilot wrote hooks to Claude and nowhere else, long after boost knew a second host
order: 12
owner: loop/bmad-all-hosts
pr:
title: bmad on knew about a second host and wrote to one anyway
---
<code>boost bmad on</code> installed its two hooks into Claude's
<code>settings.json</code> and nowhere else — not because of a decision, but because
<code>_autopilot_on</code> called <code>claude_settings.add_hook</code> without a
<code>host=</code> and took the default. That kept being true after
<code>core/hookhost.py</code> taught boost Gemini's event vocabulary and timeout units. The
capability was there; six call sites never used it.
<b>Six, not two.</b> <code>bmad on</code> and <code>off</code> were the obvious pair, but
<code>startup on|off</code>, <code>uninstall</code> and <code>disable</code> all manage the same
hooks, and a fan-out that fixed only the first two would have left
<code>boost bmad off</code> unable to remove what <code>boost bmad on</code> wrote.
<b>An existing test caught a real design error.</b> The first version chose hosts the way
<code>boost mcp register</code> does — <code>shutil.which</code> on the agent's CLI — and a test
that stubs <code>which</code> to <code>None</code> went red. It was right to. <code>mcp
register</code> <i>shells out</i> to <code>claude mcp add</code> and genuinely cannot work
without the binary; <code>bmad on</code> only writes a settings file. Gating on the binary
would have left a user running inside Claude Code with no hooks whenever the launcher was not
on boost's <code>PATH</code>. The rule is now <b>Claude unconditionally, any other host on
evidence of use</b> — its CLI on <code>PATH</code>, or its dotdir already present — so boost
never litters <code>~/.gemini/</code> for someone who has never run Gemini.
<b>What fans out and what does not.</b> Hooks do, translated: <code>UserPromptSubmit</code> is
written as Gemini's <code>BeforeAgent</code>, and ten seconds is written as
<code>10000</code> because Gemini's field is milliseconds. Matchers are not translated —
<code>hookhost</code> passes them through host-native — so Claude's
<code>startup|resume|clear</code> is applied only on Claude. The personas stay Claude-only: a
subagent is a Claude contract and Gemini's <code>agents/</code> slot would reject the dialect.
The module docstring claimed those events had "no equivalent in the other three agents", which
had quietly stopped being true; it says what is actually so now.
