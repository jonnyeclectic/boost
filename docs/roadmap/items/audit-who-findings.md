---
id: audit-who-findings
board: code
section: dx
status: shipped
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: 29 "skills" = 20 tap names + "10152 passages" + 5 cohort names + 3 real items
order: 303
owner: loop/who-expertise
pr: 746
title: "<code>boost who</code>: CLI audit findings (2026-08)"
---
<b>who's SKILLS column (and JSON <code>skills</code>) counts every journal subject, not skills.</b> On the audit machine the table read <em>&ldquo;USER jonny &middot; EVENTS 35 &middot; SKILLS 29 &middot; INSTALLS 5&rdquo;</em> &mdash; and those 29 &ldquo;skills&rdquo; were 20 tap names, the string <em>&ldquo;10152 passages&rdquo;</em> (a reindex event), 5 cohort names and 3 real items; <code>who --json</code> lists <em>&ldquo;anthropics/skills&rdquo;</em>, <em>&ldquo;pilot&rdquo;</em> and <em>&ldquo;10152 passages&rdquo;</em> under <code>skills</code>. The verifier reproduced it on a narrower run: 25 entries, of which 19 tap owner/repo names from <code>update --force</code> plus <em>&ldquo;pilot&rdquo;</em> and <em>&ldquo;all&rdquo;</em>, against only 2 real installed items. Verified mechanism: <code>cmd_who</code>'s aggregate branch (<code>team.py:735-744</code>) does <code>if e.get('subject'): u['skills'].add(e['subject'])</code> unconditional on action, while the per-skill focus branch just above (<code>team.py:708-718</code>) already filters to the expertise tuple <code>('install','edit','evolve','distill','tag')</code>. Fix (verified recommendation): apply that same action filter in the aggregate loop &mdash; or, if the broader meaning is intended, rename the column and JSON key to SUBJECTS. No doc changes needed. Found by the 2026-08 CLI audit (cluster <code>who-subject-counting</code>); repro in the audit log.
