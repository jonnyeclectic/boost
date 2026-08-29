---
id: relicence-apache-2
board: code
section: shipped
status: shipped
category: Licensing
complexity: M
impact: High
wow: 4
note: GPL-3.0-only → Apache-2.0, while it was still a one-person decision
order: 11
owner: loop/apache-2
pr:
title: The copyleft protected nothing and cost the one thing boost needs
---
boost was <code>GPL-3.0-only</code>. Asked to review it, the answer was not the
<code>-only</code>-versus-<code>-or-later</code> question that prompted the review.
<b>The copyleft was doing no work where boost is actually used.</b> Running the CLI is not
distribution, and an installed skill is not a derivative work of boost — so the GPL asked
nothing of essentially every user. <b>It cost everything on the one component built to be
embedded.</b> <code>boost_langchain</code> exists to be imported into other people's LangChain
and LangGraph applications; under GPL-3.0 that made <i>their</i> whole application GPL. The
integration package's licence forbade the integration. That is the FSF's own carve-out — a
subroutine library should be LGPL, not GPL.
<b>Every comparable tool is permissive.</b> pip, poetry, uv, pipx, hatch, ruff and mypy are
MIT; uv is MIT/Apache-2.0; and Homebrew — which boost names itself after in its own tagline —
is BSD-2-Clause. Roughly 13.6% of PyPI is GPL-3.0, and a great many organisations
auto-reject it in dependency review.
<b>The window was the argument.</b> 520 commits from one human, one more from a second email
of the same person, and 53 from bots, which hold no copyright. No vendored third-party source,
and every dependency permissive (MIT, Apache-2.0, BSD) — nothing to block the move. So the
relicence was unilateral and free. It stops being either the moment a second person
contributes, which is precisely the thing boost is short of: <b>relicensing gets harder exactly
as a project succeeds.</b>
<b>What moved.</b> 319 files restamped, and the sweep now <i>migrates</i> a stale expression
rather than only adding a missing one, so the constant is genuinely the single source of truth.
<code>pyproject.toml</code> moved to PEP 639 (<code>license = "Apache-2.0"</code>, and the
<code>License ::</code> classifier deleted rather than edited, because PyPI rejects the pair).
And <code>scripts/check_licenses.py</code> <b>inverted</b>: GPL compatibility is one-way, so
the family the check used to permit is the family it now denies, while LGPL, MPL and EPL stay
consumable. The wheel's metadata was read back to confirm
<code>License-Expression: Apache-2.0</code> rather than assumed.
