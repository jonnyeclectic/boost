---
id: python-floor-moves-to-312
board: code
section: internals
status: shipped
category: Compat · Python
complexity: M
impact: High
wow: 3
note: the floor was blocking a CVE fix and a dependency major at once
order: 90
owner: loop/python-312-floor
title: the Python floor moves from 3.9 to 3.12
---
<code>requires-python</code> moves from <code>&gt;=3.9</code> to <code>&gt;=3.12</code>. The floor had
stopped being a free promise and started being a constraint that two unrelated pieces of work were
queued behind.

<b>What it was blocking.</b> A Dependabot alert that <b>no code change could close</b> —
CVE-2025-71176 against pytest, where the lock carried two markered pins and only the
<code>&gt;=3.10</code> one could move past the patch, because pytest 9.x declares
<code>requires-python &ge;3.10</code> and the advisory marks every 8.x release vulnerable. And a
dependency major: <code>langchain</code> 1.3.14 declares <code>&gt;=3.10.0,&lt;4.0.0</code>, so any
first-class LangChain surface had to be designed around the floor rather than written normally.

<b>What it cost, measured before deciding.</b> PyPI download stats for
<code>boost-skill-cli</code> over the preceding month: 43,192 downloads total, of which 6,872
reported a Python version. On 3.9: <b>132</b> — 1.9% of the identified share, 0.3% of the total. On
3.10: <b>zero</b>. On 3.11: 1,964. The 3.12 floor therefore costs ~30% of the identified share
rather than the ~2% a 3.11 floor would have, and that was the explicit trade accepted here. The
honest caveat is that 84% of downloads report no version at all — mirrors and CI — so the 1.9% is a
share of the 16% that is visible.

<b>What it bought, all of it verified in this change rather than predicted:</b>
<code>pytest</code> resolves to a single <code>9.1.1</code> pin, closing the CVE.
<b>Eight</b> packages lose their dual markered pins entirely (<code>attrs</code>,
<code>coverage</code>, <code>exceptiongroup</code>, <code>hypothesis</code>,
<code>iniconfig</code>, <code>pytest</code>, <code>tomli</code>,
<code>typing-extensions</code>), taking 255 lines out of the lock files.
<code>scripts/lock_toolchain.py</code>'s <code>GROUPS</code> table collapses from three different
interpreter versions to one, because refurb's <code>&gt;=3.10</code> and mutmut's
<code>&gt;=3.11</code> are now below the floor rather than above it. <code>mypy</code> stops
warning that its configured <code>python_version</code> is unsupported.
<code>core/util.rmtree</code> loses its <code>onexc</code>/<code>onerror</code> branch — the one
genuine version shim in <code>boost_cli</code>.

<b>The trap this nearly walked into.</b> <code>.github/required-checks.txt</code> named
<code>tests (ubuntu-latest, 3.9)</code> and its two siblings. Changing the matrix without changing
that file would have left branch protection waiting forever for three checks that no longer exist —
the exact deadlock the file's own header describes and that
<code>scripts/check_required_checks.py</code> exists to catch. The matrix moves to
3.12 / 3.13 / 3.14 and the required list moves with it, verified by that script.

<b>What is deliberately NOT in this change.</b> Raising the floor makes ruff's PEP 585/604 rules
legal for the first time, and they are still ignored — for a new reason, recorded in
<code>pyproject.toml</code>: the sweep rewrites annotations across ~60 modules, which obliterates
blame and conflicts with every branch in flight. The rule the old comment set ("revisit as one
deliberate sweep") is honoured by giving it its own PR. Same for <code>B905</code>
(<code>zip(strict=)</code>), which is a genuine correctness signal but needs a per-site judgement at
16 call sites, not a bulk fix. Both have their own cards. What <i>did</i> land here is the part with
no judgement in it: the 18 safe <code>UP017</code> fixes (<code>timezone.utc</code> →
<code>datetime.UTC</code>) and the now-dead version block.
