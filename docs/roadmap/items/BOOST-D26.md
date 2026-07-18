---
id: BOOST-D26
board: design
track: commands
status: done
impact: high
complexity: L
wow: 5
category: commands
ref: commands/discovery.py · _browse_tui / _aurora_theme
order: 7
owner: loop/browse-aurora
pr: 80
title: <code>browse</code> — Aurora the full-screen TUI
---
The interactive <code>browse</code> pane was the <b>last off-theme surface</b>: a curses screen drawn in raw <code>A_BOLD</code>/<code>A_DIM</code>/<code>A_REVERSE</code> — zero brand color while every other command spoke Aurora. Rebuilt it as a first-class TUI: a macOS <b>titlebar</b> (traffic-light dots + <code>boost browse</code> wordmark under a cyan→violet→pink gradient rule), an <code>❯</code> chevron prompt with a live <code>▏</code> caret, <b>fuzzy-match highlighting</b> (matched chars glow pink as you type), a cyan selection bar, yellow curated <code>★</code>, violet tap labels, a right-edge scrollbar, and a gradient-topped detail pane with <code>#tag</code> chips. Colors come from the single-source <code>out.TOKENS</code> via <code>init_color</code> — parity-locked to <code>style/boost.css</code> — and degrade truecolor → 8-color → monochrome. Stdlib only. With this, <b>every boost command is on-theme</b>.
