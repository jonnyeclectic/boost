---
id: install-from-path-bypasses-policy-and-pin-checks
board: code
section: trust
status: shipped
category: Security · Bug
complexity: S
impact: High
wow: 3
note: code-scan finding
order: 9
owner: loop/install-from-path-policy
pr:
title: <code>install_from_path</code> bypasses pin &amp; policy checks
---
<b>Shipped.</b> Confirmed by running it: <code>install_from_path</code> enforced <i>no</i> gate, so <code>import</code>, <code>create --install</code>, <code>migrate --from-skills-cli</code> and <code>distill/infer/absorb --install</code> each walked past a blocklist, <code>pin_only</code>, <code>max_skills</code> and <code>denied_capabilities</code>. Worse than filed: the lock write hardcoded <code>"pinned": False</code>, so a re-import did not merely skip the pin check — it silently <b>cleared an existing pin</b>. Fixed in <code>core/store.py</code> with a <code>force</code> flag for the legitimate reinstall path; <code>force</code> covers the pin, never policy. Three corrections to this card: <code>boost rename</code> does not exist (misread of the <code>rename=</code> parameter behind <code>import --name</code>); <code>evolve</code> does not route through this function (it writes the store in place — a separate pin bypass, still open); and <code>allowed_taps</code> would not have refused any of these, since <code>policy.py</code> exempts <code>local</code> explicitly. Adopting <code>install()</code>'s "already installed" refusal was rejected — this <i>is</i> the re-import path, so it would break <code>boost reinstall</code>. The multi-item callers (<code>import --all</code>, <code>reinstall --all</code>, <code>migrate</code>) now warn per item and keep going instead of aborting the run on the first refusal, and <code>_install_generated</code> catches the refusal so a paid LLM generation is written to disk rather than deleted with the tempdir.
