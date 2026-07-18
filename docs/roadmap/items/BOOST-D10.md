---
id: BOOST-D10
board: design
track: motion
status: done
impact: high
complexity: S
wow: 4
category: motion
ref: core/output.py · new spinner()
order: 1
owner:
pr:
title: Braille spinner for network waits
---
Network-bound commands — <code>search</code> (AI rank), <code>tap</code> clone, <code>discover</code>, <code>index</code> — currently freeze silently while they work. Add a lightweight braille-dot spinner (<code>⠋⠙⠹⠸…</code>) tinted with the Aurora accent, auto-suppressed on non-TTY and under <code>NO_COLOR</code>. The single biggest "feels fast" upgrade.
