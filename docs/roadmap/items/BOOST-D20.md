---
id: BOOST-D20
board: design
track: system
status: done
impact: med
complexity: M
wow: 4
category: system
ref: core/output.py TOKENS · style/boost.css · future build_tokens.py
order: 2
owner:
pr:
title: Single source of design tokens (web ↔ CLI)
---
<b>Done:</b> the CLI palette is now single-sourced — one <code>output.TOKENS</code> dict holds every Aurora RGB triple, and the gradient, brand tints and badges all <em>derive</em> from it (previously cyan/violet/pink were re-typed across <code>_AURORA</code> and <code>_GRAD_STOPS</code>). A test locks the contract so a stray hex can't drift. <b>Remaining:</b> lift <code>TOKENS</code> into a shared <code>tokens.json</code> and generate <em>both</em> the CSS custom properties and this map from it, so the site and the terminal move in lockstep. <b>Shipped as enforcement instead of generation:</b> a unit test parses <code>style/boost.css</code> and asserts every <code>--token</code> matches <code>output.TOKENS</code>, so a hex changed in one place and not the other fails CI — the same guarantee without rewriting the hand-authored stylesheet.
