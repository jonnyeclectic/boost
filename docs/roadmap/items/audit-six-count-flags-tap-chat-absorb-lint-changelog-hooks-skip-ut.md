---
id: audit-six-count-flags-tap-chat-absorb-lint-changelog-hooks-skip-ut
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: chat -k 0 fabricates "nothing matches"; hooks --timeout -5 lands in settings.json
order: 234
owner: loop/count-flags-reject-zero-negative
pr:
title: "Six count flags (<code>tap</code>/<code>chat</code>/<code>absorb</code>/<code>lint</code>/<code>changelog</code>/<code>hooks</code>) accept 0 and negatives"
---
The same defect class the shipped negative-limit-inverts-log-pulse-output card fixed, at six sites
that kept bare <code>type=int</code> although <code>util.positive_int</code> exists and sibling
flags in discovery/info/team already use it. The failures are not cosmetic &mdash; three fabricate
false answers and one writes a broken config. Verified live: <code>chat -k 0</code> &rarr;
<em>"Nothing in the tapped catalogue matches that. Try <code>boost tap --defaults</code>&hellip;"</em>
exit 0, although <code>search --limit 5</code> finds 60 matches; <code>chat -k -1</code> prints every
match (116 rows on the verifier's corpus). <code>absorb --limit 0</code> falsely reports <em>"no
recurring patterns"</em> and <code>--limit -1</code> silently drops one. <code>changelog -n 0</code>
claims <em>"no history found"</em> plus the shallow-clone hint, exit 0, while <code>-n -1</code>
means unlimited. <code>tap --catalog --limit -1</code> silently drops the last registry
(<code>entries[:args.limit]</code>: 463 of 464). <code>lint --min 500</code> fails every skill
&mdash; scores cap at 100. And <code>hooks add --timeout -5</code> prints <em>"&#10003; added Stop
hook"</em> and writes <code>"timeout": -5</code> into settings.json; the Gemini variant writes
<code>"timeout": 0</code> &mdash; in milliseconds, fed to <code>setTimeout</code>, a hook that times
out before it runs.

The fix is mechanical: set <code>type=util.positive_int</code>
(<code>boost_cli/core/util.py:119-129</code>) at <code>taps.py:120</code>,
<code>intelligence.py:534</code>, <code>intelligence.py:1157</code>, <code>quality.py:1136</code> and
<code>hooks.py:53</code>; give <code>lint --min</code> a 0&ndash;100 range type
(<code>quality.py:712</code>). Keep the "no matches"/"no patterns" messages gated on genuinely empty
<em>untruncated</em> results, so the empty-state text can never again be produced by a limit of
zero. Help strings change, so regenerate <code>docs/commands.html</code>; <code>docs/chat.html</code>
documents <code>-k</code> and needs the same line. Found by the 2026-08 CLI audit (cluster
<code>numeric-option-validation</code>); repro in the audit log.
