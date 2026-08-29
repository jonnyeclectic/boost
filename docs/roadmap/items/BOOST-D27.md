---
id: BOOST-D27
board: design
track: layout
status: proposed
impact: med
complexity: M
wow: 2
category: layout
ref: "core/output.py · dim()/empty_state() call sites; truncate()/search_layout()"
order: 8
owner: loop/aesthetics
pr:
title: Finish the wrap-law rollout across the CLI's remaining hand-rolled spots
---
A narrow-pane audit across all 80 commands fixed the concrete overflow bugs it found — a hardcoded <code>textwrap</code> width in <code>info</code>/<code>preview</code>/<code>explain</code>, two argparse usage lines with no <code>metavar</code>, help text that split a backtick-quoted command across lines, five "nothing here" screens that overflowed unwrapped, and a <code>print_help</code> command column painted in raw 16-color <code>CYAN</code> instead of the Aurora <code>accent</code> role — and added wide-character measurement (<code>unicodedata.east_asian_width</code>) to <code>visible_len()</code>/<code>_clip_visible()</code> so <code>table()</code> stays aligned when a cell holds CJK or an emoji. Three related gaps remain, deliberately left rather than folded into that pass because each is a wider, riskier sweep on its own:

<b>1. <code>dim("  text")</code>'s embedded 2-space indent has no wrap path.</b> 39 call sites (<code>bmad</code>'s hint lines, <code>schedule status</code>, <code>impact</code>'s caveat, …) hand-embed a leading <code>"  "</code> because <code>dim()</code> prints flush-left by contract; passing <code>wrap=True</code> today would silently drop that margin on the first wrapped line (the tokenizer discards leading whitespace). One of the 39 measurably overflows a 60-column pane by a single character (<code>schedule status</code>'s enable hint) — not worth an inconsistent one-off fix. <code>dim()</code> needs a real <code>indent</code>/margin parameter (mirroring <code>kv</code>'s lead-column math) before any of the 39 can safely opt into wrapping.

<b>2. <code>empty_state()</code> adoption is 7 of ~35 "nothing to show" screens.</b> This pass converted cohort/replay/pulse/who's overflowing messages to the standard helper; roughly 28 more (<code>hooks</code>, <code>hallmarks of "no taps configured"</code>, <code>no skills installed</code> across five modules, …) still print via ad hoc <code>out.info("no X")</code>. None of them currently overflow, so converting all 28 in one shot would be a same-behavior refactor risking 28 screens' worth of rendered-text drift for no measured bug — better done a few at a time, verified against real content.

<b>3. Wide-character width stopped at <code>visible_len()</code>/<code>_clip_visible()</code>.</b> <code>truncate()</code> (plain-text clipping before coloring) and <code>search_layout()</code>'s column-budget math still count with <code>len()</code>, not display width — so a skill description containing an emoji would still truncate mid-character or throw off a search row's column budget. Not observed in real catalog data (skill names/taps are near-universal ASCII slugs), and widening it touches layout-budget code, not just measurement, so it stayed out of the audit's contained fix.
