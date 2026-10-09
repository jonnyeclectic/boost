---
id: quarantine-reports-a-link-removed-that-it-could-not-see
board: code
section: trust
status: planned
category: CLI · Bug
complexity: S
impact: Low
wow: 1
note: under a 0o600 agent dotdir, quarantine says it unlinked a skill whose link there it cannot see
order: 371
owner:
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
