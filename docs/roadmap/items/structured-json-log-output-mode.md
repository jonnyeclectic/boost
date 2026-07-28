---
id: structured-json-log-output-mode
board: code
section: internals
status: shipped
category: Observability
complexity: M
impact: Med
wow: 2
note:
order: 39
owner: loop/json-log-format
pr: 308
title: Diagnostic log has no structured/JSON output mode
---
<code>core/logs.py</code> uses stdlib <code>logging</code> with rotation and crash reports, but its
file formatter only ever emits fixed plain-text lines — unlike <code>core/journal.py</code>, which
already writes one JSON object per line for the pulse feed. A <code>BOOST_LOG_FORMAT=json</code>
option emitting the same fields as structured records would let
<code>~/.boost/logs/boost.log</code> feed straight into <code>jq</code> or a log aggregator instead
of needing regex parsing.
