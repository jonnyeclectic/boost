---
id: typosquat-and-name-confusion-detection
board: code
section: trust
status: shipped
category: Security · Registry
complexity: M
impact: Med
wow: 4
note: edit-distance guard
order: 4
owner: loop/typosquat-detect
pr: 107
title: Typosquat &amp; name-confusion detection
---
The classic package-manager attack: a skill named one edit-distance from
           a popular one, or a familiar name that quietly resolves to an unexpected
           <code>owner/repo</code>. Flag near-duplicate names and owner mismatches
           at search and install time so a user can't fat-finger their way into a
           malicious skill.
