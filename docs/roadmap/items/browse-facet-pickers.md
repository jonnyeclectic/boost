---
id: browse-facet-pickers
board: code
section: dx
status: shipped
category: CLI · UX
complexity: M
impact: Medium
wow: 3
note: the ^G category picker listed largest-first with a letter-jump; it now sorts A–Z, filters as you type, and the same picker filters by tap (^R) and kind (^K)
order: 377
owner: feat/browse-facet-pickers
pr:
title: <code>boost browse</code> facet pickers — sorted, searchable category, tap and kind filters
---
<b>Why.</b> The <code>^G</code> picker listed categories largest-first, so finding one by name meant reading the whole list, and typing a letter only jumped to the next row starting with it. Category was also the only list-style filter: a tap or a kind could be searched for as text, never picked.

<b>What changed.</b>

- <b>Sorted</b>: rows run A–Z (case-insensitive) with <code>all</code> pinned first and <code>uncategorized</code> last; <code>^T</code> inside the picker toggles to largest-first.
- <b>Searchable</b>: typing filters the rows with the browser's own label matcher (<code>browse.token_matches</code>, any subsequence), matched letters lit as in the list; Backspace edits, Esc clears a query before it closes, an empty result says so.
- <b>Every facet</b>: one picker for category (<code>^G</code>), tap (<code>^R</code>) and kind (<code>^K</code>), Tab or ←/→ to switch. Filters AND with each other and the query and ride in the query row as <code>#testing @acme/quality kind:rule</code>; each facet's counts are taken under the other active filters.
- The picker's key handling is a pure reducer (<code>browse.picker_step</code>), so it is unit- and mutation-tested rather than buried in the curses loop.
