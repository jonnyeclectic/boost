---
id: config-json-edge-shapes-crash-or-disagree
board: code
section: planned
status: shipped
category: Robustness · Bug
complexity: S
impact: Med
wow: 2
note: A config.json holding invalid UTF-8 crashes every command, doctor included; {"taps": "x"} reads as a fresh install to doctor and as configured to --help…
order: 327
owner: loop/config-edge-shapes
pr: 915
title: Two <code>config.json</code> shapes still slip past the corrupt-config handling. Invalid UTF-8 crashes every command, <code>doctor</code> included. <code>{"taps": "x"}</code> is a fresh install to <code>doctor</code> and a configured machine to <code>--help</code>.
---
<b>Measured</b> on the 2026-09-21 release train, which carries PR 888 (corrupt <code>config.json</code> is an issue, not a fresh install) and PR 904 (the first-run pointer).

<b>Invalid UTF-8 crashes everything.</b> <code>printf '\xff\xfe' &gt; ~/.boost/config.json; boost doctor</code> prints a traceback ending in <code>UnicodeDecodeError</code>. <code>main</code> behaves the same, so this predates both PRs. <code>jsonstate.read_object</code> catches <code>OSError</code> and <code>JSONDecodeError</code>, but not the <code>ValueError</code> a failed decode raises. So the one command meant to diagnose a broken config cannot start. Only the <code>--help</code> pointer survives, because it sits behind <code>contextlib.suppress</code>.

<b>A non-list <code>taps</code> gets two answers.</b> With <code>{"taps": "x"}</code>, <code>config.first_run()</code> treats the file as configured, so <code>--help</code> shows no "new here?". But <code>config.check()</code> passes it, and <code>list_taps</code> yields nothing, so <code>doctor</code> says "ready to set up — tap a registry". The two agree on <code>[]</code>, <code>null</code>, <code>{}</code>, <code>{"taps": []}</code>, <code>{"taps": {}}</code> and an unreadable file.

Likely fix: <code>read_object</code> returns a decode failure as an error message, like a parse failure. And <code>check()</code> flags a <code>taps</code> that is not a list, so that doctor, heal and the pointer all read it as the same kind of broken file. Found by the release-train review.
