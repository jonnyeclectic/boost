---
id: mcp-session-dies-on-a-deeply-nested-json-line
board: code
section: planned
status: planned
category: MCP · Bug
complexity: S
impact: Low
wow: 2
note: The parse layer catches JSONDecodeError, and a deep enough line raises RecursionError instead…
order: 343
title: A deeply nested JSON line kills the MCP session, because the parse guard names one exception
---
<b>Found while fixing <code>mcp-server-dies-on-a-valid-json-message-that-is-not-an-object</code>, and
left for its own card because it is the parse layer rather than the shape layer.</b>
<code>serve_stdio</code> wraps <code>json.loads</code> in <code>except json.JSONDecodeError</code>
and answers <code>-32700</code>, which is right for malformed JSON. A sufficiently nested line
raises <code>RecursionError</code> instead, which the guard does not name, so it escapes exactly as
the shape crashes did: exit 70, a crash report, nothing on stdout, and the session over.
<br><br>
Measured: object nesting 100,000 deep parses fine; at 1,000,000 (a ~7 MB line) CPython raises
<code>RecursionError: Stack overflow (used 16352 kB) while decoding a JSON object</code>.
<br><br>
<b>Fix.</b> Catch the recursion failure beside the decode failure — or bound the line length before
parsing, which also caps the memory one client line can cost — answer <code>-32700</code>, and keep
the loop alive. Pin it with a round-trip test that sends a deep line and then a well-formed request,
asserting the second is answered.
