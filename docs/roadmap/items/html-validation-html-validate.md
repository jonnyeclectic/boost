---
id: html-validation-html-validate
board: code
section: docsite
status: shipped
category: Quality · Docs
complexity: S
impact: Med
wow: 3
note: hand-authored HTML
order: 4
owner: loop/htmlvalidate
pr: 199
title: HTML validation — <code>html-validate</code>
---
The guide and roadmap are hand-authored HTML whose tags are balanced by
           eye today. A CI <code>html-validate</code> pass catches unclosed
           elements, duplicate <code>id</code>s and invalid nesting before they
           ship a subtly broken layout — the automated version of the manual
           tag-count sanity check.
