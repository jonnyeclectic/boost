---
id: browse-reskin-ranked-tmux-statusbar
board: code
section: dx
status: inflight
category: CLI · UX
complexity: M
impact: High
wow: 4
note: boost browse listed fuzzy matches alphabetically, so a typed name landed past the first screen; reskinned with ranked matches, a category scope and a tmux-style status bar
order: 372
owner: feat/browse-reskin
pr:
title: <code>boost browse</code> reskin — ranked matches, <code>#category</code> scope, slate selection and a tmux-style status bar
---
<b>Why.</b> Matching is fuzzy, so over a 2,402-entry corpus <code>code review</code> matched 1,722 rows — in alphabetical order, with <code>0-preflight</code> first and the <code>code-review</code> the user typed somewhere below it. Every row also carried a ★ (a curated catalogue stars everything), a full <code>[owner/repo]</code> badge, and the key hints took a chrome row of their own.

<b>What changed.</b>

- <b>Ranked matches</b> (<code>browse.match_tier</code> / <code>rank</code>): exact name, then prefix, substring, fuzzy-on-name, then description/tap only; catalogue order breaks ties. <code>code review</code> and <code>code-review</code> are the same name.
- <b>Category scope</b>: <code>category</code> joins the scope toggles, and rows show a <code>#category</code> chip from <code>browse.entry_category</code> — the same lookup the scope searches, so a chip is always findable.
- <b>Selection</b>: a cyan <code>▌</code> bar on a soft slate row instead of a solid reversed accent block; 8-colour and monochrome terminals keep reverse video.
- <b>Less noise</b>: the ★ column is gone (it is a detail chip now), kind badges take a hue each (skill cyan · rule violet · workflow pink; workflow is yellow on 8 colours, where violet and pink are one magenta), taps show the repo name only.
- <b>Status bar</b> under the frame: a mode pill (<code>SEARCH</code> / <code>SCOPE</code> / <code>LIST</code> / <code>DETAIL</code>), hints for that mode that drop from the middle and never lose <code>esc quit</code>, and the session install chip at the right. The list gains the row the hints used to take.
- <b>Detail pane</b>: a chips line (kind · version · #category · ★ curated), dim labels and bright values, wrapped values aligned under the value column, and FRONTMATTER no longer repeats the name and description.
- <b>Colour levels</b>: true Aurora hues where slots can be redefined, the nearest xterm-256 index where they cannot (tmux without <code>Tc</code> used to fall to 8 colours), base colours below that. <code>NO_COLOR</code> is honoured.

All of the above is pure logic in <code>core/browse.py</code> under unit tests and the mutation gate; the curses layer only paints it.
