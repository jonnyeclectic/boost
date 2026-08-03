---
id: pep585-604-modernization-sweep
board: code
section: planned
status: planned
category: Tech-debt
complexity: M
impact: Low
wow: 1
note: unblocked by the 3.12 floor; deferred only because the diff touches ~60 modules
order: 91
title: the <code>typing.List</code> → <code>list</code> sweep the floor now allows
---
Three ruff rules sit in <code>pyproject.toml</code>'s ignore list: <code>UP006</code>
(<code>List[x]</code> → <code>list[x]</code>), <code>UP007</code>
(<code>Union[x, y]</code> → <code>x | y</code>), <code>UP035</code> (deprecated
<code>typing</code> imports) and <code>UP045</code> (<code>Optional[x]</code> → <code>x | None</code>).

<b>The reason they were ignored is gone.</b> It used to be a correctness argument, not a taste one:
60 of boost's 63 modules carry <code>from __future__ import annotations</code>, which <i>defers</i>
annotation evaluation but does not make the syntax legal — the moment anything actually evaluates
one (<code>typing.get_type_hints</code>, a dataclass, a plain <code>eval</code>), a PEP 604 union
was a <code>TypeError</code> on 3.9. ruff agreed, classifying all the fixes as <b>unsafe</b> at
<code>target-version = "py39"</code>. At <code>py312</code> it classifies them as <b>safe</b>.

<b>Why it is still deferred.</b> Purely diff size. The sweep rewrites annotations across roughly 60
modules, which obliterates <code>git blame</code> on almost every file and conflicts with every
branch in flight — the identical objection <code>UP031</code> (printf formatting) carries a few
lines below in the same ignore block, and the reason the original note said to do it "as one
deliberate sweep". Riding it in on the floor bump would have made a mechanical config change
unreviewable.

<b>What doing it looks like.</b> <code>ruff check --select UP006,UP007,UP035,UP045 --fix</code>,
then delete the four entries and their comment from the ignore list. It is one command and one
review pass, and it should land when no long-running branch is mid-flight. Worth checking first
whether any module still needs the <code>from __future__ import annotations</code> import
afterwards — at a 3.12 floor most of them do not, but removing those is a second, separable step and
should not be bundled in.
