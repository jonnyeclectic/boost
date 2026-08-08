---
id: serve-404-reflected-the-request
board: code
section: trust
status: inflight
category: Security · Bug
complexity: S
impact: Med
wow: 3
note: the test suite pinned the echo in place as if it were the contract
order: 97
owner: loop/serve-no-reflected-request
pr: 489
title: <code>boost serve</code> echoed the request path back into its 404 body
---
<b>What happened.</b> <code>route()</code> unquotes the request path before matching, so
the segment after <code>/skill/</code> is arbitrary bytes of the caller's choosing. When
that segment failed <code>SKILL_NAME_RE</code>, it was interpolated straight back into the
response: <code>json.dumps({"error": "no skill named %r" % name})</code>. Ask for
<code>/skill/&lt;script&gt;alert(1)&lt;/script&gt;</code> and the script tag came back in the
body. Snyk Code files it as CWE-79, High.

<b>How bad, honestly.</b> Not a live cross-site scripting hole today, and saying otherwise
would be inflating it. The body is typed <code>application/json</code>, and no current
browser renders that as HTML. What made it worth fixing is the distance to one: the
server sent no <code>X-Content-Type-Options</code> header at all, so the only thing
standing between the reflection and execution was the browser choosing not to sniff — a
decision made outside this repo, for a body this repo hands to whoever asks. It is also
not purely a localhost surface: <code>--host</code> is a documented flag, and the code
elsewhere already reasons about <code>0.0.0.0</code> exposure (the generic 500 body exists
for exactly that reason).

<b>Two halves, because either alone leaves the other standing.</b> The invalid-name branch
no longer names anything — it answers <code>invalid skill name</code>. Nothing is lost:
the name is invalid <em>by definition</em> in that branch, so repeating it told the caller
only what it had just sent. The valid-but-unknown branch keeps <code>no skill named
'ghost'</code>, because it is reachable only for a name that already matched
<code>[A-Za-z0-9._-]</code> — a charset with nothing in it that can close a tag or a quote
— and that message is the one signal distinguishing a typo from a skill that simply is not
installed. Separately, <code>_send</code> now sets
<code>X-Content-Type-Options: nosniff</code>. It goes on the choke point rather than at
each <code>return</code>, so it also covers the generic 500 in <code>do_GET</code>, which
is the response most likely to grow a reflected detail later.

<b>The part worth keeping.</b> The suite already had a test for this path, and it asserted
the leak: <code>test_route_percent_encoded_traversal_is_404</code> pinned the body as
<code>no skill named '../../etc/passwd'</code>. So a refused traversal was checked for
being refused, and the echo it came back with was written down as the expected value. A
test can hold a defect in place as firmly as it can catch one, and this one had, for as
long as the endpoint has existed. It now asserts the opposite — that the attempt is not
repeated back — alongside four payload cases and a check that no <code>&lt;</code>,
<code>&gt;</code>, <code>&amp;</code> or <code>'</code> reaches the body at all, which are
bytes a structurally-correct JSON response never emits.
