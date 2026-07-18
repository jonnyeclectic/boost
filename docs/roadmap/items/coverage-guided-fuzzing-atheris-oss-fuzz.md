---
id: coverage-guided-fuzzing-atheris-oss-fuzz
board: code
section: health
status: planned
category: Testing · Bug
complexity: L
impact: Med
wow: 4
note: stretch
order: 8
owner:
pr:
title: Coverage-guided fuzzing — <code>atheris</code> / OSS-Fuzz
---
Google's <code>atheris</code> fuzzes the frontmatter and registry
           parsers under coverage guidance to mine deep crash inputs; OSS-Fuzz
           runs it continuously for free once boost qualifies as an open-source
           project. The stretch goal — the highest ceiling for finding the bug
           nobody thought to write a test for.
