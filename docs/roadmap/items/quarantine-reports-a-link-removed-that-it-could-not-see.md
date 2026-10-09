---
id: quarantine-reports-a-link-removed-that-it-could-not-see
board: code
section: trust
status: shipped
category: CLI · Bug
complexity: S
impact: Low
wow: 1
note: fixed — quarantine unlinks every agent it can, names each one it could not with its chmod, and a re-run finishes
order: 371
owner: loop/quarantine-unseen-link
pr:
title: "<code>boost quarantine</code> reports links removed that it could not see"
---
Found while measuring <code>agent-dir-shapes-install-still-trips-on</code>, and left out of that change.
Make <code>~/.cursor</code> mode <code>0o600</code> and quarantine an installed skill.
<code>unlink_agents</code> skips the cursor link because <code>os.path.islink</code> answers
<code>False</code> when it may not look. Quarantine then reports the skill's links as removed, but
the cursor link is still on disk and the agent keeps loading the skill boost meant to withhold.

Uninstall no longer strands that link. It refuses while a recorded or unseen agent's dir can't be
searched, and names <code>chmod u+wx</code>. Quarantine needs the same treatment. It should look at
each link with <code>os.lstat</code>, so that <code>PermissionError</code> means "could not look", not
"no link". Then it should either refuse with the same hint, or quarantine and say which agent may
still load the skill. Refusing matches uninstall. Quarantining with a warning matches what a user
reaching for quarantine wants. Measure both before choosing.

<b>Shipped.</b> Quarantine, not refusal. Measured in a sandbox with <code>~/.cursor</code> at
<code>0o600</code> and the skill linked into four agents: refusing, which is what
<code>boost uninstall</code> does there, exits 1 and leaves all four links live, so every agent
keeps loading the skill until the <code>chmod</code>. Quarantining unlinks claude-code, windsurf
and antigravity, keeps cursor's link, and says
<code>cursor may still load brainstorming: ~/.cursor is not searchable — run `chmod u+wx ~/.cursor`,
then `boost quarantine brainstorming` again</code>. While the dotdir is <code>0o600</code> cursor,
running as the same user, cannot read it either. The two commands differ for a reason: an
uninstall that skips a link strands it pointing into a deleted store, while a quarantine that
refused would leave the link live in every agent. The new <code>store.quarantine_skill</code> looks
at each link with <code>os.lstat</code> and records each agent it could not unlink in
<code>refused_agents</code>, so the uninstall guard keeps refusing over that agent. Running
<code>boost quarantine</code> again on a quarantined skill now retries those links. It used to answer
"already quarantined". The same change fixes a shape the card did not name: a link in a read-only
<code>~/.cursor/skills</code> made quarantine exit 70 after it had unlinked two agents, with the lock
still saying linked and not quarantined. It now exits 0 and names <code>chmod u+w ~/.cursor/skills</code>.
<code>boost doctor</code> said "1 skill quarantined, none active" with cursor's link live. It now
reports a quarantined skill with recorded refusals, or with a link on disk, as an issue.
