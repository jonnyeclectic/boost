---
id: audit-config-findings
board: code
section: dx
status: shipped
category: CLI · Bug
complexity: S
impact: Low
wow: 2
note: `config unset` on a pristine HOME creates config.json and freezes all defaults into it
order: 258
owner: loop/config-unset-raw
pr: 650
title: "boost config: CLI audit findings (2026-08)"
---
<b><code>config unset</code> on a defaulted key always reports success and rewrites the file.</b>
A second <code>config unset ai.enabled</code> — the key already gone from
<code>config.json</code> — prints <em>"&#10003; unset ai.enabled"</em>, exits 0, and rewrites the
file (mtime verified moving); only a key with no default gets <em>"not set"</em>. Verification
found it worse than filed: on a pristine HOME with no <code>config.json</code> at all,
<code>config unset telemetry</code> prints <em>"&#10003; unset telemetry"</em> and <b>creates</b>
config.json with 797 bytes of the current DEFAULTS materialised into it — freezing them against
future default changes. Root: <code>core/config.py:263</code>'s <code>unset()</code> walks the
DEFAULTS-merged <code>load()</code> (its own docstring promises "False (no write) if absent"), so
every defaulted key is present forever and <code>save()</code> writes the merged view. Fix: walk
the raw on-disk overrides, save only that dict, return False with no write when the key is absent
from the file; pin the docstring parity with a unit test.

<br><br>Sibling: with <code>~/.boost</code> removed, <code>config list</code> prints the defaults
followed by <code>~/.boost/config.json</code> as their source — a path that does not exist
(<code>commands/configuration.py:78</code> prints it unconditionally). Vary the dim trailer when
<code>paths.config_path()</code> is missing: <em>"defaults — ~/.boost/config.json not created
yet"</em>. No doc changes. Found by the 2026-08 CLI audit (cluster
<code>config-state-reporting</code>); repro in the audit log.
