---
id: log-timestamps-mislabeled-utc
board: code
section: health
status: shipped
category: Observability · Diagnostics
complexity: S
impact: Med
wow: 2
note: converter = time.gmtime
order: 10
owner: loop/utc-log-timestamps
pr: 104
title: Log timestamps are local time mislabeled <code>Z</code>
---
<code>core/logs.py</code> builds the <code>logging.Formatter</code> with
           <code>datefmt="%Y-%m-%dT%H:%M:%SZ"</code> but never sets
           <code>converter = time.gmtime</code>, so <code>%(asctime)s</code> uses
           <em>local</em> time while stamping a literal <code>Z</code> (UTC)
           suffix. Every line in <code>~/.boost/logs/boost.log</code> is therefore
           off by the machine's UTC offset — which nearly caused a 5-hour
           mis-correlation when matching the log against an OS crash report. Set
           the formatter's <code>converter</code> to <code>time.gmtime</code> (or
           drop the <code>Z</code>) so the trail is honestly UTC, making the
           pid/ppid crash-correlation breadcrumbs trustworthy.
