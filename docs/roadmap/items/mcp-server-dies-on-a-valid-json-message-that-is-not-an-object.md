---
id: mcp-server-dies-on-a-valid-json-message-that-is-not-an-object
board: code
section: planned
status: shipped
category: MCP · Bug
complexity: S
impact: High
wow: 4
note: One batch array or stray scalar takes the whole tool surface offline for the session, with no JSON-RPC error the host can report…
order: 339
owner: loop/mcp-request-shape
pr: 953
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

<br><br>
<b>Shipped.</b> <code>handle_request</code> checks the shape before it reads it: a message
that is not an object is one <code>-32600</code> carrying <code>id: null</code> (JSON-RPC 2.0 §5 —
an id that cannot be detected MUST be null, which is the convention <code>serve_stdio</code>
already used for <code>-32700</code>), a batch array included, since boost has never implemented
batching and answering one with silence would look to a host exactly like the crash. A malformed
<code>params</code>, <code>name</code> or <code>arguments</code> is <code>-32602</code> echoing the
id the host can still correlate on. Two neighbours found while reading the path: a missing or
non-string <code>method</code> answered <code>-32601 method not found:</code> (the same assumption,
reported as the wrong thing) and a bad <code>arguments</code> reached the handler, where it surfaced
as an <code>isError</code> result reading <code>'list' object has no attribute 'get'</code> — or, for
a tool that ignores its arguments, as plain success. Re-measured on the same nine lines: every one
is <code>rc=0</code>, one error line, and the following request answered.
