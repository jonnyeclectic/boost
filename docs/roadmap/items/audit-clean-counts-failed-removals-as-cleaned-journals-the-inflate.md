---
id: audit-clean-counts-failed-removals-as-cleaned-journals-the-inflate
board: code
section: dx
status: shipped
category: CLI · Bug
complexity: S
impact: High
wow: 2
note: 5 failed removals still print "✓ cleaned 6 item(s)", journal the lie, and exit 0
order: 201
owner: loop/clean-failure-accounting
pr: 654
title: "<code>clean</code> counts failed removals as cleaned, journals the inflated count, and exits 0"
---
With 5 surplus lock-history files in a directory chmod'd 555 so unlink fails, <code>boost clean</code> prints five <em>&ldquo;! could not remove &hellip;: [Errno 13] Permission denied&rdquo;</em> warnings and then <em>&ldquo;&#10003; cleaned 6 item(s) &middot; 15B freed&rdquo;</em>, exit 0 &mdash; only 1 item was actually removed. Run it again: <em>&ldquo;&#10003; cleaned 5 item(s) &middot; 0B freed&rdquo;</em>, exit 0, nothing removed, files still present. The rerun repeating &ldquo;cleaned 5&rdquo; is the proof the count is fiction.

The mechanism is <code>boost_cli/commands/configuration.py:189-206</code>: the <code>except OSError</code> branch warns and continues, but the summary prints <code>len(items)</code> and the function unconditionally returns 0. Two verified aggravations: the <em>&ldquo;! could not remove&rdquo;</em> warnings go to stdout rather than stderr, and <code>journal.log</code> records the same inflated &ldquo;N items&rdquo; count (<code>configuration.py:204</code>) &mdash; so both the human and the audit trail are told the machine is clean when it is not.

Fix per the verified recommendation: increment a <code>removed</code> counter only after a successful unlink/rmtree, print <em>&ldquo;cleaned N item(s), M failed&rdquo;</em> when failures exist, log the real count to the journal, and <code>return 1</code> when any removal failed. No docs change beyond regenerating <code>docs/commands.html</code> if the summary wording moves into help text (behaviour-only otherwise).

Found by the 2026-08 CLI audit (cluster <code>clean-failure-accounting</code>); repro in the audit log. Verified 2026-08-31: reproduced, high confidence &mdash; a wrong count plus exit 0 on failure are both on the audit contract's high-severity list.
