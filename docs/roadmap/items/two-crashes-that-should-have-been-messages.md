---
id: two-crashes-that-should-have-been-messages
board: code
section: compat
status: shipped
category: Bug
complexity: S
impact: Medium
wow: 3
note:
order: 13
owner: fix/audit-findings
pr:
title: Two crashes that should have been messages
---
Both were found by reading the crash reports on a real machine rather than by review, and both are
the same shape: an expected, fixable condition escaping as a traceback.

<strong>An unwritable store.</strong> <code>store._copy_skill</code> stages its copy with
<code>tempfile.mkdtemp</code> next to the destination. Where <code>~/.agents/skills</code> could not
be written — a sandboxed shell is the usual cause — the raw <code>PermissionError</code> escaped, so
<code>boost install &lt;skill&gt;</code> answered with a stack trace ending in a temp path nobody
recognises, and filed a crash report for a permissions problem. It now names the directory, which
is the whole diagnosis. A non-permissions <code>OSError</code> (disk full, read-only mount) is
reported as itself rather than described as denied.

<strong>A truncated embedding response.</strong> <code>embed._post</code> guarded with
<code>except (URLError, OSError, ValueError)</code>. <code>http.client.IncompleteRead</code> — what
a connection cut mid-body raises — subclasses <code>HTTPException</code> and <em>none</em> of those
three, so it went straight through <code>resp.read()</code> and out of <code>boost search</code>.
Seen as <code>IncompleteRead(6629 bytes read, 6200 more expected)</code> on
<code>boost search mempalace</code>. The right answer to a network hiccup is to return None and let
retrieval fall back to BM25, which is what it now does. <code>RemoteDisconnected</code> had been
covered only by accident — it also subclasses <code>ConnectionResetError</code>.
