---
id: audit-schedule-findings
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: S
impact: Med
wow: 2
note: "'interval every None' without StartInterval — and StartInterval 0 hangs status forever"
order: 290
owner: loop/schedule-interval-guard
pr:
title: "boost schedule: CLI audit findings (2026-08)"
---
With a launchd plist that lacks a <code>StartInterval</code> key, <code>boost schedule status</code> prints <em>"platform darwin (launchd) &middot; scheduled yes &middot; interval every None &middot; next run unknown"</em> — the kv line interpolates a bare <code>None</code> (the <code>--json</code> output is fine: <code>"interval": null</code>). Verification found the same unguarded parse is worse than cosmetic: with <code>&lt;integer&gt;0&lt;/integer&gt;</code> as the interval, the next-run loop <code>while nxt &lt; now: nxt += timedelta(seconds=secs)</code> never advances and <code>schedule status</code> hangs forever — the repro run was killed at 30&nbsp;s (exit 124). The control case <code>43200</code> renders correctly as "every 12h".

Boost's own <code>schedule enable</code> only writes the <code>_INTERVALS</code> values (6h/12h/daily), so a zero or absent interval means a hand-edited or third-party plist — but a status command that can hang forever on one is still a real defect. One guard fixes both: in <code>boost_cli/commands/configuration.py:878-889</code>, compute interval/next-run only when the regex matched <b>and</b> <code>int(m.group(1)) &gt; 0</code>, otherwise print <em>"interval&nbsp;&nbsp;unknown (plist has no usable StartInterval)"</em> at the kv line (<code>configuration.py:911-913</code>). Add a unit test over both plist shapes. No doc changes.

Found by the 2026-08 CLI audit (cluster <code>schedule-interval-display</code>); repro in the audit log.
