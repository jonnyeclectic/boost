---
id: mcp-server-dies-on-a-valid-json-message-that-is-not-an-object
board: code
section: planned
status: planned
category: MCP · Bug
complexity: S
impact: High
wow: 4
note: One batch array or stray scalar takes the whole tool surface offline for the session, with no JSON-RPC error the host can report…
order: 339
title: One valid-JSON message that is not an object kills the whole MCP session
---
<b>Found by the audit of the MCP surface.</b> <code>serve_stdio</code> answers unparseable JSON
correctly with <code>-32700</code> and keeps looping, but a line that parses into anything other
than an object — a JSON-RPC batch array, a bare scalar, a string, <code>null</code> — reaches
<code>handle_request</code>, which calls <code>req.get("method")</code> with no shape check. The
<code>AttributeError</code> escapes every handler and lands in boost's top-level crash handler: exit
70, a crash report under <code>~/.boost/logs</code>, and <b>nothing on stdout</b>. The host gets no
response to that id and no response to anything after it — the session is dead. A second site has
the same shape one branch down: in <code>tools/call</code>, <code>params.get("name", "")</code> sits
outside the try that wraps the call, so <code>{"method":"tools/call","params":["boost_list"]}</code>
kills the server identically.
<br><br>
Measured at <code>origin/main</code>: each of <code>[{...}]</code>, <code>5</code>,
<code>"hello"</code>, <code>null</code> and the malformed <code>params</code> gives
<code>rc=70</code> with zero bytes of stdout, and a well-formed request on the next line is never
answered. JSON-RPC 2.0 §5 asks for a single <code>-32600</code> Invalid Request here — which boost
already gets right for a parse failure.
<br><br>
<b>Fix.</b> Return <code>-32600</code> when the message is not an object, guard
<code>params</code> with an <code>isinstance</code> check, and add both shapes to the
<code>serve_stdio</code> round-trip tests beside the existing parse-error case.
