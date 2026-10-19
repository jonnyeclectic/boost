---
id: name-resolution
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: Medium
wow: 3
note: install took tap:name, and twelve commands that act on installed items answered "not installed" for the same string
order: 374
owner:
pr:
title: <code>tap:name</code> after install, and a dry run that refuses when the run would
---
<b>Twelve commands rejected the qualified name that install accepts.</b>
<code>boost install fix:brainstorming</code> works, and every ambiguity hint tells the user to
type that form. But <code>uninstall</code>, <code>pin</code>, <code>unpin</code>,
<code>reinstall</code>, <code>quarantine</code>, <code>verify</code>, <code>drift</code>,
<code>lint</code>, <code>test</code>, <code>attest</code>, <code>impact</code> and
<code>focus</code> looked the lock up with the still-qualified string. The lock keys items by
the bare name, so each one answered "fix:brainstorming is not installed" about an item
<code>boost list</code> shows. They now pass what was typed through one core helper,
<code>store.installed_name</code>, which returns the bare lock key. A qualifier that names a tap
the item was not installed from is refused and names the real tap, instead of acting on that
tap's copy. A qualifier that selects only a rule or workflow shadowed by a same-named skill is
refused as ambiguous, because the bare name resolves skill-first and the command would act on
the skill.

<b><code>install x --dry-run</code> promised an upgrade the run refuses.</b> Over an installed
<code>x</code>, the preview printed "would upgrade x v1.4.0" and exited 0. The run printed
"x is already installed" and exited 1. The preview picked its verb from whether the lock held
the name and never asked the run's question. The "already installed", "is pinned" and
cross-scope refusals now live in one function, <code>store.check_existing</code>. The skill,
project-skill, rule and workflow install paths call it, and so does each branch of the
preview. Without <code>--force</code> the preview now refuses in the same words with exit 1.
In a multi-name run that refusal is a per-entry warning, as it is in the run. With
<code>--force</code> it says "would reinstall".
