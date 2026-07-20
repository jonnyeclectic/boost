---
id: single-imperative-rule-extractor
board: code
section: internals
status: shipped
category: Tech-debt
complexity: M
impact: Med
wow: 2
note: 
order: 14
owner: loop/imperative-extractor
pr: 144
title: Single imperative-rule extractor
---
Three separate regexes scan SKILL.md bodies for "Always / Never / Must / Do&nbsp;not" lines across <code>cmd_explain</code>, <code>simulate</code> and <code>conflict</code> (<code>info.py:363 · intelligence.py:254 · quality.py:822</code>) — same concept, three implementations. Extract one shared <code>core</code> extractor.
