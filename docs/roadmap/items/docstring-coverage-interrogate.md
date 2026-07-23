---
id: docstring-coverage-interrogate
board: code
section: dx
status: shipped
category: Quality · Docs
complexity: S
impact: Low
wow: 2
note: keeps core/ documented
order: 5
owner: loop/interrogate
pr: 205
title: Docstring coverage — <code>interrogate</code>
---
Gate CI below a docstring-coverage threshold so the engine stays
           self-documenting as it grows. <code>core/</code> is already well
           commented; <code>interrogate</code> keeps it that way and flags the
           new public function that shipped without a word of explanation.
