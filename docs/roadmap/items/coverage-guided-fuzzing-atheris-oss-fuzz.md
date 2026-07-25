---
id: coverage-guided-fuzzing-atheris-oss-fuzz
board: code
section: health
status: shipped
category: Testing · Bug
complexity: L
impact: Med
wow: 4
note: stretch
order: 8
owner: loop/fuzz-parsers
pr: 242
title: Coverage-guided fuzzing — <code>atheris</code> / OSS-Fuzz
---
Google's <code>atheris</code> instruments the bytecode and evolves inputs toward
           uncovered branches in boost's two hand-rolled parsers — the SKILL.md frontmatter
           reader (a stdlib-only YAML subset, so no upstream project's fuzzing covers it)
           and the tap-spec parser. It has already paid for itself: the frontmatter harness
           found that numeric coercion was <em>lossy</em>. <code>version: 1.10</code> is ten
           patch releases past 1.1, but <code>float("1.10")</code> is <code>1.1</code> — so
           boost read a skill published at 1.10 as 1.1, compared it as older than 1.9, and
           never offered the update, with <code>boost outdated</code> reporting "everything
           up to date" while the tap was nine releases ahead. Note that "it doesn't crash"
           would have missed it entirely: the invariant has to compare the parsed value
           against the source text. The seeds through every invariant run in the required
           suite so a harness cannot rot; the coverage-guided run is a weekly non-blocking
           job, because a timed search is not reproducible enough to gate a merge. Targets
           follow the OSS-Fuzz Python contract, ready for continuous runs once boost
           qualifies.
