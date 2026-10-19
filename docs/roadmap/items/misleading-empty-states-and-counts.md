---
id: misleading-empty-states-and-counts
board: code
section: dx
status: shipped
category: CLI · Bug
complexity: S
impact: Med
wow: 3
note: four commands that answered confidently and wrongly — each now names what actually happened
order: 373
owner: fix/misleading-messages
pr:
title: Four messages that sent the user the wrong way
---
<b>Each of these printed a plausible answer that was false, so the user acted on it.</b>
All four reproduced in a sandbox against the fixture tap.

<b><code>boost search Q --category C</code> blamed the query for the filter.</b> With
<code>ideation</code> matching one skill, <code>--category nope</code> printed
<i>no matches for 'ideation' → try <code>boost discover ideation</code></i> — sending the user to
GitHub for something already on disk, without naming the filter that emptied the list. Search now
records whether the query matched before <code>--category</code> narrowed it, and when only the
filter emptied the result it says <i>no matches for 'ideation' in category 'nope'</i> with a hint to
drop <code>--category</code> or list them via <code>boost browse --categories</code>. A query that
matched nothing at all keeps the discover hint.

<b><code>boost trending</code> counted upgrades as installs.</b> <code>boost update</code> and
<code>boost reinstall</code> both call <code>store.install(force=True)</code>, which journals an
<code>install</code> every time: one install plus one upgrade showed <i>2 installs</i>, a reinstall
made it 3. Those two paths now pass <code>via="update"</code> / <code>via="reinstall"</code>
(the parameter <code>store.install</code> already took), and <code>journal.is_new_install</code>
drops them from the count. An uninstall followed by an install still counts — that is a choice made
twice. The row's description now comes from the tap the event names, with first-tap-wins kept as the
fallback for an event that names none.

<b><code>boost outdated</code> told the user to re-tap a tap that was right there.</b> When a tap
drops an item, the footer read <i>source missing — <code>boost update</code> can't restore a deleted
tap; re-tap or <code>boost uninstall</code></i>, while <code>boost taps</code> listed the tap present
and current. <code>outdated_footer</code> now takes a <code>removed</code> count — missing rows whose
tap is still configured — and words those as <i>removed upstream</i>, advising uninstall or keeping
the copy. Re-tap advice is given only for the untapped rows; the JSON is unchanged.

<b><code>boost config set</code> with a typo printed a check mark and changed nothing.</b>
<code>agents.claude-code.enabeld false</code> and <code>agents.claud-code.enabled false</code> both
reported <i>✓ set</i> while <code>agents.claude-code.enabled</code> stayed true — and the second
invented a phantom agent with no dir. Unknown keys are still saved (integrations invent their own
top-level sections, a documented decision), but <code>config.unknown_key_warning</code> now warns on
stderr below any section boost owns, with a did-you-mean (<code>agents.claude-code.enabled</code>),
and names a new agent that has no <code>dir</code>. The per-agent key list is pinned against what
<code>agents.known_agents</code> actually reads, so a real setting such as
<code>links_skills</code> is never called a typo.

<b>Not changed:</b> <code>boost update</code> still prints <i>everything up to date</i> after
warning that an item is no longer in its tap.
